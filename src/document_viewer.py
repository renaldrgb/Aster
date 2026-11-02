"""Original PDF access for saved materials; never reconstruct PDFs from extracted text."""
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import threading

conversion_lock = threading.Lock()
OFFICE_MIMES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
GOOGLE_MIMES = {"application/vnd.google-apps.presentation", "application/vnd.google-apps.document"}
from src import store, library, school_reader


def original(material_id):
    material = next((m for m in store.rows('materials') if m['id'] == material_id), None)
    if not material:
        raise ValueError('This material is no longer available.')
    linked=store.setting('attachments:'+material_id,[]) or []
    if linked:
        if len(linked)!=1:
            raise ValueError('Choose an attached document from this lesson to view its original pages.')
        if linked[0]==material_id or store.setting('attachments:'+linked[0],[]):
            raise ValueError('Invalid attachment relationship. Review Classroom to refresh it.')
        return original(linked[0])
    local = next((f for f in library.list_files() if f['material_id'] == material_id), None)
    if local:
        path = library.file_path(local['id'])
        if local['mime'] == 'application/pdf':
            return path, local['name']
        if local['mime'] in OFFICE_MIMES:
            return convert_office(path), Path(local['name']).stem + '.pdf'
        raise ValueError('This document has no formatted page preview.')
    if ':' not in material_id:
        raise ValueError('No original document is available for this material.')
    file_id = material_id.split(':', 1)[1]
    meta = school_reader.document_metadata(file_id)
    mime = meta['mimeType']
    if mime not in {'application/pdf', *OFFICE_MIMES, *GOOGLE_MIMES}:
        raise ValueError('This document format does not support a page preview yet.')
    if int(meta.get('size', 0)) > library.MAX_BYTES:
        raise ValueError('This document exceeds the 20 MB viewing limit.')
    key = hashlib.sha256((file_id + ':' + str(meta.get('version', meta.get('modifiedTime', '')))).encode()).hexdigest()
    folder = store.DATA / 'pdf-originals'
    folder.mkdir(exist_ok=True)
    suffix = OFFICE_MIMES.get(mime, '.pdf')
    path = folder / (key + suffix)
    if not path.exists():
        if mime in GOOGLE_MIMES:
            data = school_reader.request('drive', 'files/' + file_id + '/export', {'mimeType': 'application/pdf'}, binary=True)
        else:
            data = school_reader.request('drive', 'files/' + file_id, {'alt': 'media', 'supportsAllDrives': 'true'}, binary=True)
        if len(data) > library.MAX_BYTES:
            raise ValueError('The original exceeds the 20 MB viewing limit.')
        if suffix == '.pdf' and not data.startswith(b'%PDF-'):
            raise ValueError('Google did not return a supported PDF original.')
        if suffix in OFFICE_MIMES.values():
            library._validate_archive(data, suffix)
        # Unique temporary files also allow simultaneous requests for the same document.
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as tmp:
            tmp.write(data)
            temp = Path(tmp.name)
        temp.replace(path)
    if suffix != '.pdf':
        path = convert_office(path)
    return path, Path(meta['name']).stem + '.pdf'


def office_executable():
    candidates = [store.DATA/'components/office/program/soffice.exe',
                  Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
                  Path(__import__('sys').executable).parent.parent/'Resources/LibreOffice.app/Contents/MacOS/soffice',
                  Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/AsterDocumentEngine/program/soffice.exe',
                  Path(os.environ.get('PROGRAMFILES', '')) / 'LibreOffice/program/soffice.exe',
                  Path(os.environ.get('PROGRAMFILES(X86)', '')) / 'LibreOffice/program/soffice.exe']
    found = shutil.which('soffice')
    if found:
        candidates.insert(0, Path(found))
    return next((p for p in candidates if p.is_file()), None)


def convert_office(source):
    """Render the actual Office file, preserving slides and page structure."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    cache = store.DATA / 'document-pages'
    cache.mkdir(exist_ok=True)
    result = cache / (digest + '.pdf')
    with conversion_lock:
        if result.exists():
            return result
        exe = office_executable()
        if not exe:
            from src.runtime_setup import ensure_office
            exe=ensure_office()
        with tempfile.TemporaryDirectory(prefix='render-', dir=cache) as temp:
            folder = Path(temp)
            input_path = folder / ('document' + source.suffix)
            shutil.copy2(source, input_path)
            profile = folder / 'profile'
            profile.mkdir()
            # Disable macros in the isolated conversion profile; never use the user's Office profile.
            (profile / 'user').mkdir()
            (profile / 'user/registrymodifications.xcu').write_text(
                '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
                '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
                '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item></oor:items>', encoding='utf-8')
            try:
                run = subprocess.run([str(exe), '-env:UserInstallation=' + profile.as_uri(), '--headless',
                    '--nologo', '--nodefault', '--norestore', '--convert-to', 'pdf', '--outdir', str(folder), str(input_path)],
                    capture_output=True, timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except subprocess.TimeoutExpired:
                raise ValueError('Rendering took too long. Try opening this document in Classroom.') from None
            output = folder / 'document.pdf'
            if run.returncode or not output.exists() or not output.read_bytes().startswith(b'%PDF-'):
                raise ValueError('The original document could not be rendered. Open it in Classroom to view it.')
            output.replace(result)
    return result


def open_chrome(material_id):
    path, _ = original(material_id)
    if __import__('sys').platform=='darwin':
        subprocess.Popen(['open','-a','Google Chrome',str(path)])
        return {'ok':True}
    candidates = [Path(os.environ.get(root, '')) / 'Google/Chrome/Application/chrome.exe'
                  for root in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA')]
    chrome = next((p for p in candidates if p.is_file()), None)
    if not chrome:
        raise ValueError('Chrome is not installed. Choose Open in Aster instead.')
    subprocess.Popen([str(chrome), path.resolve().as_uri()], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return {'ok': True}
