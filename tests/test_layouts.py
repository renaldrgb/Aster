import asyncio
from fastapi.testclient import TestClient
from src import store,school
import server

def test_layout_setting_default_persistence_and_validation(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init();server.quizzes.init()
    with TestClient(server.app) as c:
        h={'X-Aster-Token':server.TOKEN}
        assert c.get('/api/state',headers=h).json()['layout']=='study-desk'
        for name in ['floating','reading-room','study-desk']:
            assert c.post('/api/settings',headers=h,json={'layout':name}).status_code==200
            store.init()
            assert c.get('/api/state',headers=h).json()['layout']==name
        assert c.post('/api/settings',headers=h,json={'layout':'unknown'}).status_code==422
        assert c.post('/api/settings',json={'layout':'floating'}).status_code==403

def test_selected_reader_material_is_used_for_answer(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init();server.quizzes.init()
    store.save_material('chosen','MRK','Chosen lesson','The requested lesson body','')
    for i in range(5):store.save_material(str(i),'Other','Other material','Unrelated text','')
    cid=store.new_conversation();token=store.conversation.set(cid)
    async def model(**kwargs):
        context=kwargs['messages'][0]['content']
        assert 'The requested lesson body' in context and 'Unrelated text' not in context
        return 'Answer'
    monkeypatch.setattr(school,'llm_call_async',model)
    try:assert asyncio.run(school.answer('Explain it',material_id='chosen'))=='Answer'
    finally:store.conversation.reset(token)

