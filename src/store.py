import os, sqlite3, json, hashlib, re, uuid
from contextvars import ContextVar
conversation = ContextVar("conversation", default="legacy")
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone

DATA=Path(os.environ.get('ASTER_DATA_DIR',str((Path.home()/'Library/Application Support' if __import__('sys').platform=='darwin' else Path(os.environ.get('LOCALAPPDATA',Path.home())))/'Aster')))
DATA.mkdir(parents=True,exist_ok=True)
def now(): return datetime.now(timezone.utc).isoformat()
@contextmanager
def db():
    con=sqlite3.connect(DATA/'aster.db',timeout=30)
    con.row_factory=sqlite3.Row
    try:
        yield con
        con.commit()
    finally: con.close()
def init():
    with db() as c:
        c.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,source_id TEXT,course TEXT,title TEXT,kind TEXT,due TEXT,url TEXT,done INTEGER DEFAULT 0,created TEXT,updated TEXT);
        CREATE TABLE IF NOT EXISTS materials(id TEXT PRIMARY KEY,course TEXT,title TEXT,body TEXT,url TEXT,updated TEXT);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,role TEXT,body TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,title TEXT,body TEXT,sources TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY,body TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        ''')
        c.execute('CREATE TABLE IF NOT EXISTS coursework(source_id TEXT PRIMARY KEY,due TEXT,work_type TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT,created TEXT,updated TEXT)')
        if 'conversation_id' not in {r[1] for r in c.execute('PRAGMA table_info(messages)')}:
            c.execute("ALTER TABLE messages ADD COLUMN conversation_id TEXT NOT NULL DEFAULT 'legacy'")
        if c.execute('SELECT 1 FROM messages WHERE conversation_id=? LIMIT 1',('legacy',)).fetchone():
            c.execute("INSERT OR IGNORE INTO conversations VALUES('legacy','Previous conversations',?,?)",(now(),now()))
def rows(table):
    assert table in {'tasks','materials','messages','reports','activity'}
    with db() as c: return [dict(r) for r in c.execute('SELECT * FROM '+table+' ORDER BY '+('id' if table in {'messages','activity'} else 'updated' if table in {'tasks','materials'} else 'created')+' DESC')]
def log(text):
    with db() as c:c.execute('INSERT INTO activity(body,created) VALUES(?,?)',(text,now()))
def message(role,text):
    cid=conversation.get()
    with db() as c:
        c.execute('INSERT OR IGNORE INTO conversations VALUES(?,?,?,?)',(cid,'School updates' if cid=='legacy' else 'New chat',now(),now()))
        c.execute('INSERT INTO messages(role,body,created,conversation_id) VALUES(?,?,?,?)',(role,text,now(),cid))
        c.execute('UPDATE conversations SET updated=? WHERE id=?',(now(),cid))
        if role=='user':
            c.execute("UPDATE conversations SET title=? WHERE id=? AND title='New chat'",(' '.join(text.split())[:70],cid))

def new_conversation(title='New chat'):
    cid=uuid.uuid4().hex
    with db() as c:c.execute('INSERT INTO conversations VALUES(?,?,?,?)',(cid,title,now(),now()))
    return cid

def conversations():
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM conversations ORDER BY updated DESC,id DESC')]

def chat_messages(cid=None,limit=None):
    cid=cid or conversation.get()
    with db() as c:
        if not c.execute('SELECT 1 FROM conversations WHERE id=?',(cid,)).fetchone():raise ValueError('Chat not found.')
        if limit:
            rows=c.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?',(cid,limit)).fetchall()
            return [dict(r) for r in reversed(rows)]
        return [dict(r) for r in c.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id',(cid,))]

def setting(key,default=None):
    with db() as c:r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return json.loads(r[0]) if r else default
def set_setting(key,value):
    with db() as c:c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
def save_task(source_id,course,title,kind='Review',due=None,url=''):
    title=' '.join(title.split()).strip()
    if not title:raise ValueError('Empty task')
    with db() as c:official=c.execute('SELECT due FROM coursework WHERE source_id=?',(source_id,)).fetchone()
    kind='Homework' if official and official['due'] else 'Review'
    due=official['due'] if kind=='Homework' else None
    if due:
        datetime.fromisoformat(due.replace('Z','+00:00'))
    key=hashlib.sha256((source_id+'|'+re.sub(r'\W+','',title.casefold())).encode()).hexdigest()[:24]
    with db() as c:
        existing=c.execute('SELECT id FROM tasks WHERE id=?',(key,)).fetchone()
        c.execute('''INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET course=excluded.course,kind=excluded.kind,due=excluded.due,url=excluded.url,updated=excluded.updated''',
        (key,source_id,course,title,kind,due,url,0,now(),now()))
    return not bool(existing)
def save_material(id,course,title,body,url):
    with db() as c:c.execute('INSERT OR REPLACE INTO materials VALUES(?,?,?,?,?,?)',(id,course,title,body,url,now()))

def material_catalog():
    """One visible section per source post, with its actual attached documents.

    Keep source rows and IDs intact for quizzes, task completion and incremental
    scans. Never guess relationships from similar titles or extracted text.
    """
    materials=rows('materials')
    by_id={m['id']:m for m in materials}
    parents={}
    for material in materials:
        linked=list(dict.fromkeys(setting('attachments:'+material['id'],[]) or []))
        attached=[dict(by_id[id]) for id in linked if id in by_id and id!=material['id']]
        if not attached:continue
        material['attachments']=attached
        material['description']=material['body'] or ''
        material['body']='\n\n'.join([material['description']]+[
            document['title']+'\n\n'+(document['body'] or '') for document in attached]).strip()
        material['search_text']=' '.join([material['title'],material['body']]+[d['title'] for d in attached])
        material['missing_attachments']=len(linked)-len(attached)
        for document in attached:parents.setdefault(document['id'],[]).append(material['id'])
    for material in materials:
        if material['id'] in parents:
            material['hidden_in_library']=True
            material['parent_ids']=parents[material['id']]
    return materials
def toggle(id,done):
    with db() as c:
        r=c.execute('UPDATE tasks SET done=?,updated=? WHERE id=?',(int(done),now(),id))
        if not r.rowcount:raise ValueError('Task not found')


def register_coursework(source_id,due,work_type='ASSIGNMENT'):
    with db() as c:
        c.execute('INSERT OR REPLACE INTO coursework VALUES(?,?,?)',(source_id,due,work_type))
        c.execute('UPDATE tasks SET kind=?,due=? WHERE source_id=?',('Homework' if due else 'Review',due,source_id))

def reclassify_tasks():
    """Only API-verified dated Classroom coursework is an assignment."""
    with db() as c:
        c.execute("UPDATE tasks SET kind='Review',due=NULL WHERE source_id NOT IN (SELECT source_id FROM coursework WHERE due IS NOT NULL)")
        c.execute("UPDATE tasks SET kind='Homework',due=(SELECT due FROM coursework WHERE coursework.source_id=tasks.source_id) WHERE source_id IN (SELECT source_id FROM coursework WHERE due IS NOT NULL)")
