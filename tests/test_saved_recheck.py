import asyncio
import pytest
from src import school,store

@pytest.fixture(autouse=True)
def workspace(tmp_path,monkeypatch):
 monkeypatch.setattr(store,'DATA',tmp_path);store.init()

def test_recheck_uses_saved_text_and_preserves_completion(monkeypatch):
 store.save_material('c:post','Class','Lesson','Short description','')
 store.save_material('c:file','Class','Slides','Pyetje për kontroll\nWhat is a network?\nWhat is a client?\n[End of slide]','')
 store.set_setting('attachments:c:post',['c:file'])
 async def no_model(**kwargs):raise AssertionError('Explicit questions must not require AI')
 monkeypatch.setattr(school,'llm_call_async',no_model)
 asyncio.run(school.recheck_saved(lambda *a:None))
 first=store.rows('tasks');assert len(first)==2
 store.toggle(first[0]['id'],True)
 asyncio.run(school.recheck_saved(lambda *a:None))
 assert len(store.rows('tasks'))==2
 assert sum(t['done'] for t in store.rows('tasks'))==1

def test_continued_question_heading():
 assert school.review_questions('Review questions (continued)\nQuestion two?\n[End of slide]')==['Question two?']

def test_chunked_ai_reads_end_of_document(monkeypatch):
 seen=[]
 async def model(**kwargs):
  seen.append(kwargs);return '{"tasks":[]}'
 monkeypatch.setattr(school,'llm_call_async',model)
 text=('Lesson content. '*900)+'FINAL PAGE'
 asyncio.run(school.analyze_document({'name':'Large','text':text,'url':''},'Class','c:file',None,lambda *a:None))
 assert len(seen)>1 and all(len(call['messages'][-1]['content'])<=4500 for call in seen)
 assert 'FINAL PAGE' in seen[-1]['messages'][-1]['content']
 assert all(call['context_size']==8192 for call in seen)
