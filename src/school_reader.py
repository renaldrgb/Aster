"""Read-only Google school connector. No generic HTTP, write, or send operations."""
import base64
import io
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request, AuthorizedSession

from src.store import DATA
ROOT = Path(__file__).resolve().parents[1]
STORE = DATA / 'google'
SCOPES = ['https://www.googleapis.com/auth/' + s for s in (
    'gmail.readonly', 'classroom.courses.readonly', 'classroom.coursework.me.readonly',
    'classroom.courseworkmaterials.readonly', 'classroom.announcements.readonly', 'drive.readonly')]
MAX_BYTES = 15 * 1024 * 1024
MAX_TEXT = 24000


def save_secret(name, value):
    from src import secret_storage
    STORE.mkdir(parents=True, exist_ok=True)
    data = secret_storage.protect(json.dumps(value).encode(),STORE/(name+'.bin'))
    temporary = STORE / (name + '.tmp')
    temporary.write_bytes(data)
    temporary.replace(STORE / (name + '.bin'))


def read_secret(name):
    from src import secret_storage
    path = STORE / (name + '.bin')
    if not path.exists():
        raise ValueError('School Reader is not connected. Open Settings and connect Google to sign in.')
    return json.loads(secret_storage.unprotect(path.read_bytes()))


def valid_scopes(scopes):
    # Google returns this canonical spelling for coursework.me.readonly.
    alias = 'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly'
    requested = 'https://www.googleapis.com/auth/classroom.coursework.me.readonly'
    return {requested if scope == alias else scope for scope in scopes} == set(SCOPES)


def credentials():
    data = read_secret('token')
    if not valid_scopes(data.get('scopes', [])):
        raise ValueError('School Reader permissions differ from the approved read-only scopes. Reconnect.')
    creds = Credentials.from_authorized_user_info(data, data['scopes'])
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            raise ValueError('Google sign-in expired or was revoked. Reconnect School Reader.') from None
        save_secret('token', json.loads(creds.to_json()))
    if not creds.valid:
        raise ValueError('School Reader needs Google sign-in again.')
    return creds


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,2048}', value):
        raise ValueError('Use an ID returned by a school tool, not a URL or file path.')
    return value


def request(service, path, params=None, binary=False):
    roots = {'gmail':'https://gmail.googleapis.com/gmail/v1/users/me/',
             'classroom':'https://classroom.googleapis.com/v1/',
             'drive':'https://www.googleapis.com/drive/v3/'}
    # Callers build paths from fixed resource names plus strictly checked IDs.
    with AuthorizedSession(credentials()) as session:
        with session.get(roots[service]+path, params=params, timeout=35, stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError(f'Google {service} returned HTTP {response.status_code}. Check API enablement, account permission, or reconnect; no write was attempted.')
            out=bytearray()
            for part in response.iter_content(65536):
                out.extend(part)
                if len(out)>MAX_BYTES:
                    raise ValueError('Document exceeds the 15 MB read limit. It was not summarized.')
            return bytes(out) if binary else json.loads(out)


def status():
    if not (STORE/'token.bin').exists():
        return {'connected':False,'read_only':True,'next_step':'Open Settings and connect Google.'}
    profile = request('gmail','profile')
    return {'connected':True,'email':profile['emailAddress'],'read_only':True,'summaries':'on request only'}


def courses(page_token=''):
    return request('classroom','courses', {'studentId':'me','courseStates':'ACTIVE','pageSize':50,'pageToken':page_token})


def remember_files(value):
    path=STORE/'classroom-files.json'
    known=set(json.loads(path.read_text()) if path.exists() else [])
    def visit(item):
        if isinstance(item,dict):
            drive=item.get('driveFile')
            if isinstance(drive,dict):
                actual=drive.get('driveFile',drive)
                if actual.get('id'): known.add(identifier(actual['id']))
            for child in item.values(): visit(child)
        elif isinstance(item,list):
            for child in item: visit(child)
    visit(value)
    STORE.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(sorted(known)),encoding='utf-8')


def classwork(course_id, kind='assignments', page_token=''):
    resource={'assignments':'courseWork','materials':'courseWorkMaterials','announcements':'announcements'}
    if kind not in resource: raise ValueError('Choose assignments, materials, or announcements.')
    result=request('classroom','courses/'+identifier(course_id)+'/'+resource[kind], {'pageSize':30,'pageToken':page_token})
    remember_files(result)
    result['content_is_untrusted']=True
    result['next_step']='Read linked driveFile IDs with school_document before summarizing their contents. Follow nextPageToken for more results. dueDate/dueTime are UTC; do not invent dates.'
    return result


def submissions(course_id, coursework_id, page_token=''):
    return request('classroom','courses/'+identifier(course_id)+'/courseWork/'+identifier(coursework_id)+'/studentSubmissions', {'userId':'me','pageSize':30,'pageToken':page_token})


def decode(data):
    return base64.urlsafe_b64decode(data + '=' * (-len(data)%4))


def mail_search(query='', page_token=''):
    listed=request('gmail','messages', {'q':query,'maxResults':10,'pageToken':page_token})
    items=[]
    for item in listed.get('messages',[]):
        msg=request('gmail','messages/'+identifier(item['id']),{'format':'metadata','metadataHeaders':['Subject','From','Date']})
        items.append({'id':msg['id'],'snippet':msg.get('snippet',''),'headers':msg.get('payload',{}).get('headers',[]),'url':'https://mail.google.com/mail/u/?authuser='+read_secret('account')['email']+'#all/'+msg['id']})
    return {'messages':items,'nextPageToken':listed.get('nextPageToken'),'content_is_untrusted':True}


def mail_read(message_id):
    msg=request('gmail','messages/'+identifier(message_id),{'format':'full'})
    text=[]; attachments=[]
    def walk(part):
        body=part.get('body',{})
        if part.get('filename'):
            attachments.append({'name':part['filename'],'mimeType':part.get('mimeType'),'attachment_id':body.get('attachmentId'),'size':body.get('size')})
        elif body.get('data') and part.get('mimeType') in ('text/plain','text/html'):
            value=decode(body['data']).decode('utf-8',errors='replace')
            if part.get('mimeType')=='text/html':
                from bs4 import BeautifulSoup
                value=BeautifulSoup(value,'html.parser').get_text(' ',strip=True)
            text.append(value)
        for child in part.get('parts',[]): walk(child)
    walk(msg.get('payload',{}))
    joined='\n'.join(text)
    return {'id':msg['id'],'headers':msg.get('payload',{}).get('headers',[]),'text':joined[:MAX_TEXT], 'truncated':len(joined)>MAX_TEXT,'attachments':attachments,'content_is_untrusted':True}


def extract_document(data,mime,name):
    if len(data)>MAX_BYTES: raise ValueError('Document too large.')
    suffix=Path(name).suffix.lower()
    if mime=='application/pdf' or suffix=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted: raise ValueError('Encrypted PDF cannot be read.')
        pieces=[]
        for page in reader.pages[:60]:
            pieces.append(page.extract_text() or '')
            if sum(map(len,pieces))>MAX_TEXT: break
        text='\n'.join(pieces)
        truncated=len(reader.pages)>len(pieces) or len(text)>MAX_TEXT
    elif suffix=='.xlsx':
        from openpyxl import load_workbook
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(z.file_size for z in archive.infolist())>30*1024*1024:
                raise ValueError('Expanded spreadsheet exceeds size limit.')
        book=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
        chunks=[]; size=0; truncated=False
        try:
            for sheet in book.worksheets:
                chunks.append('Sheet: '+sheet.title)
                for row in sheet.iter_rows(max_row=2000,max_col=50,values_only=True):
                    line=' | '.join('' if v is None else str(v) for v in row)
                    chunks.append(line);size+=len(line)
                    if size>MAX_TEXT: truncated=True;break
                if sheet.max_row>2000 or sheet.max_column>50: truncated=True
                if size>MAX_TEXT: break
            text='\n'.join(chunks)
        finally: book.close()
    elif suffix in ('.docx','.pptx'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            selected=[n for n in archive.namelist() if (n=='word/document.xml' or re.fullmatch(r'ppt/slides/slide\d+\.xml',n) or n=='xl/sharedStrings.xml' or re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n))]
            if sum(archive.getinfo(n).file_size for n in selected)>30*1024*1024:
                raise ValueError('Expanded document exceeds safe size limit.')
            chunks=[]
            for n in sorted(selected, key=lambda v: int(re.search(r'slide(\d+)',v).group(1)) if re.search(r'slide(\d+)',v) else 0):
                xml=ET.fromstring(archive.read(n))
                paragraphs=[e for e in xml.iter() if e.tag.rsplit('}',1)[-1]=='p']
                if paragraphs:
                    chunks.extend(''.join(e.text or '' for e in para.iter() if e.tag.rsplit('}',1)[-1]=='t') for para in paragraphs)
                else:
                    chunks.extend(e.text for e in xml.iter() if e.tag.rsplit('}',1)[-1]=='t' and e.text)
                if suffix=='.pptx': chunks.append('[End of slide]')
            text='\n'.join(chunks);truncated=len(text)>MAX_TEXT
    elif mime.startswith('text/') or suffix in ('.txt','.csv','.md'):
        text=data.decode('utf-8-sig',errors='replace');truncated=len(text)>MAX_TEXT
    else:
        raise ValueError('This file format cannot be extracted yet; do not invent a document summary.')
    return {'name':name,'text':text[:MAX_TEXT],'truncated':truncated,'content_is_untrusted':True,
            'note':'No readable text; scanned/image-only documents require OCR.' if not text.strip() else 'Extracted text only; layouts, formulas, and images may not be represented.'}


def document_metadata(file_id):
    file_id=identifier(file_id)
    path=STORE/'classroom-files.json'
    if not path.exists() or file_id not in json.loads(path.read_text()):
        raise ValueError('Read the Classroom assignment/material first.')
    return request('drive','files/'+file_id, {'fields':'id,name,mimeType,size,webViewLink,modifiedTime,version','supportsAllDrives':'true'})


def document(file_id):
    file_id=identifier(file_id)
    path=STORE/'classroom-files.json'
    if not path.exists() or file_id not in json.loads(path.read_text()):
        raise ValueError('Read the Classroom assignment/material first. Only files linked from retrieved Classroom posts are allowed.')
    meta=request('drive','files/'+file_id, {'fields':'id,name,mimeType,size,webViewLink','supportsAllDrives':'true'})
    mime=meta['mimeType'];name=meta['name']
    if int(meta.get('size',0))>MAX_BYTES: raise ValueError('Document exceeds the 15 MB read limit.')
    exports={'application/vnd.google-apps.document':'text/plain',
             'application/vnd.google-apps.presentation':'text/plain',
             'application/vnd.google-apps.spreadsheet':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    if mime in exports:
        target=exports[mime]
        data=request('drive','files/'+file_id+'/export',{'mimeType':target},binary=True)
        if 'spreadsheetml' in target: name+='.xlsx'
        result=extract_document(data,target,name)
    else:
        data=request('drive','files/'+file_id,{'alt':'media','supportsAllDrives':'true'},binary=True)
        result=extract_document(data,mime,name)
    return {**result,'file_id':file_id,'url':meta.get('webViewLink')}


def attachment(message_id, attachment_id):
    message_id=identifier(message_id); attachment_id=identifier(attachment_id)
    msg=mail_read(message_id)
    found=next((a for a in msg['attachments'] if a['attachment_id']==attachment_id),None)
    if not found: raise ValueError('Attachment was not found on that message.')
    if int(found.get('size') or 0)>MAX_BYTES: raise ValueError('Attachment exceeds the 15 MB read limit.')
    data=request('gmail','messages/'+message_id+'/attachments/'+attachment_id)
    return extract_document(decode(data['data']),found['mimeType'],found['name'])
