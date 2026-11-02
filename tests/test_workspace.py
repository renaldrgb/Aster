import os,tempfile,asyncio,json
os.environ['ASTER_DATA_DIR']=tempfile.mkdtemp(prefix='aster-test-')
from src import store,school
store.init()

def test_completion_survives_sync_and_restart():
    assert store.save_task('course:doc','Networks','What is a network?')
    task=store.rows('tasks')[0];store.toggle(task['id'],True)
    assert not store.save_task('course:doc','Networks','What is a network?',due='2026-11-03T10:00:00+00:00')
    store.init();task=store.rows('tasks')[0]
    assert task['done']==1 and task['due'] is None and task['kind']=='Review'
    assert store.save_task('different:doc','Other class','What is a network?')

def test_questions_and_due():
    text='Lesson\nPyetje për kontroll\n1. Çfarë është rrjeti?\n2. Si funksionon?\n[End of slide]\nOther content'
    assert len(school.review_questions(text))==2
    assert school.due_date({}) is None
    assert school.due_date({'dueDate':{'year':2026,'month':11,'day':3},'dueTime':{'hours':14}})=='2026-11-03T14:00:00+00:00'
    assert school.document_due_date('Afati për dorëzim: 03.11.2026')=='2026-11-03T12:00:00+00:00'
    assert school.document_due_date('This lesson happened on 03.11.2026') is None

def test_document_saves_without_model():
    doc={'text':'Pyetje për kontroll\nExplain a router?\n[End of slide]','url':'https://classroom.google.com','name':'Lesson'}
    assert asyncio.run(school.analyze_document(doc,'Networks','testdoc',None,lambda x:None))==1
    assert asyncio.run(school.analyze_document(doc,'Networks','testdoc',None,lambda x:None))==0

def test_api_security_and_job_serialization():
    from fastapi.testclient import TestClient
    import server
    with TestClient(server.app) as c:
        assert c.get('/api/state').status_code==403
        h={'X-Aster-Token':server.TOKEN}
        r=c.get('/api/state',headers=h);assert r.status_code==200
        assert 'client_secret' not in r.text
        assert c.get('/').status_code==200
        assert c.post('/api/open',headers=h,json={'text':'http://127.0.0.1:7000'}).status_code==400
        assert c.post('/api/settings',headers=h,json={'email':'test@example.org','client_json':'{"installed":null}'}).status_code==400

def test_empty_course_and_theme_are_persistent():
    from fastapi.testclient import TestClient
    import server
    store.set_setting('courses',[{'id':'one','name':'Networks'},{'id':'two','name':'Lab'},{'id':'three','name':'AI (no materials)'}])
    with TestClient(server.app) as c:
        h={'X-Aster-Token':server.TOKEN}
        assert len(c.get('/api/state',headers=h).json()['courses'])==3
        assert c.post('/api/settings',headers=h,json={'theme':'dark'}).status_code==200
        store.init()
        assert c.get('/api/state',headers=h).json()['theme']=='dark'
        assert c.post('/api/settings',headers=h,json={'theme':'invalid'}).status_code==422

def test_research_engine_with_adapters(monkeypatch):
    from src.deep_research import DeepResearcher
    async def execute():
        engine=DeepResearcher('local','test',max_rounds=1,min_rounds=1)
        async def plan(*a):return 'plan'
        async def queries(*a):return ['school networks']
        async def extract(*a):return [{'url':'https://example.org','title':'Network','summary':'Evidence'}]
        async def synthesis(*a):return 'A researched report with evidence.'
        monkeypatch.setattr(engine,'_create_plan',plan);monkeypatch.setattr(engine,'_generate_queries',queries)
        monkeypatch.setattr(engine,'_search_and_extract',extract);monkeypatch.setattr(engine,'_synthesize',synthesis)
        assert 'researched report' in await engine.research('Networks')
    asyncio.run(execute())
