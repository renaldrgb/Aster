import asyncio,json
import httpx,pytest
from src import ai_settings,store,llm_core,quizzes

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init();quizzes.init()

def test_encrypted_key_and_local_switch():
    ai_settings.configure('openrouter','test/model','test-private-key')
    assert b'test-private-key' not in ai_settings.key_path().read_bytes()
    assert ai_settings.cloud_key()=='test-private-key'
    assert 'key' not in ai_settings.status()
    ai_settings.configure('local','')
    assert ai_settings.status()['provider']=='local'

def test_cloud_route_uses_cloud_model(monkeypatch):
    ai_settings.configure('openrouter','test/model','private-test')
    captured=[]
    def handle(request):
        captured.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'OK'}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(llm_core.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handle)))
    assert asyncio.run(llm_core.llm_call_async(model='local',messages=[{'role':'user','content':'Test'}]))=='OK'
    assert json.loads(captured[0].content)['model']=='test/model'
    assert captured[0].url.host=='openrouter.ai'

def test_download_progress_and_completion(monkeypatch):
    from src import runtime_setup
    monkeypatch.setattr(runtime_setup,"ensure_ai",lambda progress:None)
    def handle(request):
        return httpx.Response(200,text='\n'.join(json.dumps(x) for x in [
            {'status':'pulling','digest':'abc','total':100,'completed':20},
            {'status':'pulling','digest':'abc','total':100,'completed':100},{'status':'success'}]))
    original=httpx.AsyncClient
    monkeypatch.setattr(ai_settings.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handle)))
    updates=[]
    result=asyncio.run(ai_settings.pull('qwen3.5:2b',lambda text,**kw:updates.append(kw)))
    assert 'Downloaded' in result and updates[0]['percent']==20

def test_quiz_passage_ids_attach_exact_source(monkeypatch):
    source='A star topology connects each device to one central switch. A bus uses one shared cable.'
    store.save_material('m','Networks','Topology',source,'')
    async def model(**kw):return json.dumps({'questions':[{'prompt':str(i)+' Which device is central?','options':['Switch','Monitor','Mouse','Keyboard'],'correct':0,'explanation':'The source describes a central switch.','evidence_id':0} for i in range(3)]})
    monkeypatch.setattr(quizzes,'llm_call_async',model)
    id=asyncio.run(quizzes.generate('m',3));result=quizzes.submit(id,{'q1':0,'q2':0,'q3':0})
    assert result['score']==3 and all(q['evidence']==source for q in result['questions'])

def test_16gb_ram_rounding_recommends_4b_on_8gb_gpu(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(ai_settings.psutil,'virtual_memory',lambda:SimpleNamespace(total=int(15.9*1024**3)))
    monkeypatch.setattr(ai_settings.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout='NVIDIA GeForce RTX 4060, 8192'))
    assert [m['name'] for m in ai_settings.hardware()['models'] if m['recommended']]==['qwen3.5:4b']
