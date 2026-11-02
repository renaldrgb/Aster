import asyncio,sqlite3
from src import store,school

def test_legacy_messages_migrate_and_chats_are_isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    with sqlite3.connect(tmp_path/'aster.db') as c:
        c.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,role TEXT,body TEXT,created TEXT)')
        c.execute("INSERT INTO messages VALUES(1,'user','Old question','2026-01-01')")
    store.init();store.init()
    assert store.chat_messages('legacy')[0]['body']=='Old question'
    a=store.new_conversation();b=store.new_conversation()
    token=store.conversation.set(a)
    try:store.message('user','Explain routers')
    finally:store.conversation.reset(token)
    assert len(store.chat_messages(a))==1 and store.chat_messages(b)==[]
    assert next(c for c in store.conversations() if c['id']==a)['title']=='Explain routers'

def test_incremental_review_retries_failure_and_checks_changes(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    version=['1'];calls=[];fail=[False]
    async def pages(fn,key,*args):
        if key=='courses':return [{'id':'c','name':'Networks'}]
        if key=='courseWork':return []
        return [{'id':'p','title':'Lesson','materials':[{'driveFile':{'id':'d'}}]}]
    monkeypatch.setattr(school,'pages',pages)
    monkeypatch.setattr(school.google,'document_metadata',lambda fid:{'version':version[0]})
    monkeypatch.setattr(school.google,'document',lambda fid:{'name':'Lesson','text':'Some lesson','url':'https://example.org'})
    async def analyze(*args):
        calls.append(version[0])
        if fail[0]:raise ValueError('Temporary error')
        return 0
    monkeypatch.setattr(school,'analyze_document',analyze)
    asyncio.run(school.sync(lambda s:None));assert calls==['1']
    asyncio.run(school.sync(lambda s:None));assert calls==['1']
    last=store.setting('last_sync');version[0]='2';fail[0]=True
    asyncio.run(school.sync(lambda s:None));assert store.setting('last_sync')==last
    fail[0]=False;asyncio.run(school.sync(lambda s:None));assert calls==['1','2','2']
    asyncio.run(school.sync(lambda s:None));assert calls==['1','2','2']

def test_chat_jobs_keep_their_history(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    seen=[]
    async def answer(text):
        seen.append([m['body'] for m in store.chat_messages()]);return 'Reply: '+text
    monkeypatch.setattr(school,'answer',answer)
    async def run():
        first=await server.chat(server.Question(text='First topic'))
        await server.jobs[first['id']]['_task']
        second=await server.chat(server.Question(text='Different topic'))
        await server.jobs[second['id']]['_task']
        third=await server.chat(server.Question(text='Follow up',conversation_id=first['conversation_id']))
        await server.jobs[third['id']]['_task']
        assert all(server.jobs[j['id']]['status']=='done' for j in (first,second,third))
        assert seen==[['First topic'],['Different topic'],['First topic','Reply: First topic','Follow up']]
    asyncio.run(run())

def test_email_review_uses_own_timestamp_and_skips_seen_ids(tmp_path,monkeypatch):
    import server
    from src import llm_core
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    queries=[];read=[]
    async def pages(fn,key,query):
        queries.append(query);return [{'id':'mail1'}]
    monkeypatch.setattr(school,'pages',pages)
    def mail(mid):read.append(mid);return {'text':'Lesson tomorrow'}
    monkeypatch.setattr(server.school_reader,'mail_read',mail)
    async def model(**kwargs):return 'Lesson tomorrow'
    monkeypatch.setattr(llm_core,'llm_call_async',model)
    async def run():
        for _ in range(2):
            job=await server.chat(server.Question(text='Review my email'))
            await server.jobs[job['id']]['_task']
            assert server.jobs[job['id']]['status']=='done'
    asyncio.run(run())
    assert queries[0]=='newer_than:14d' and queries[1].startswith('after:')
    assert read==['mail1'] and store.setting('last_mail_scan')
    assert store.setting('last_sync') is None
