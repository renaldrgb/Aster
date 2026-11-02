import asyncio,json
from src import store,question_actions

def test_answers_every_selected_question_using_its_own_document(monkeypatch):
    tasks=[{'id':str(i),'source_id':'doc-'+str(i),'title':'Question '+str(i),'course':'Course','url':'https://example.org/'+str(i),'done':i%2} for i in range(7)]
    materials={t['source_id']:{'title':t['source_id'],'body':'Lesson '+t['id']} for t in tasks}
    calls=[];saved=[]
    async def model(**kwargs):
        data=json.loads(kwargs['messages'][1]['content']);calls.append(data);return 'Answer for '+data['question']
    monkeypatch.setattr(question_actions,'llm_call_async',model)
    monkeypatch.setattr(store,'message',lambda role,text:saved.append((role,text)))
    result=asyncio.run(question_actions.answer_questions(tasks,materials,lambda text:None))
    assert len(calls)==len(saved)==7 and 'all 7' in result
    assert [c['text'] for c in calls]==['Lesson '+str(i) for i in range(7)]
    assert [t['done'] for t in tasks]==[i%2 for i in range(7)]

def test_explicit_document_selection_includes_completed(monkeypatch):
    tasks=[{'source_id':'a','course':'A','created':'1','id':'1','done':1},{'source_id':'b','course':'B','created':'1','id':'2','done':0}]
    monkeypatch.setattr(store,'rows',lambda table:tasks if table=='tasks' else [])
    selected,_=question_actions.selection('a');assert selected==[tasks[0]]
    assert len(question_actions.selection()[0])==2

def test_research_action_saves_all_sections(monkeypatch):
    import server
    tasks=[{'source_id':'a','title':'Question '+str(i)} for i in range(2)]
    monkeypatch.setattr(question_actions,'selection',lambda source,kind='':(tasks,{'a':{'title':'Lesson'}}))
    class Engine:
        def __init__(self,*args,**kwargs):self.analyzed_urls=[{'url':'https://example.org','title':'Source'}]
        async def research(self,prompt):return 'Evidence for '+prompt
    monkeypatch.setattr(server,'DeepResearcher',Engine)
    async def run():
        created=await server.question_action(server.QuestionAction(source_id='a',mode='research'))
        await server.jobs[created['id']]['_task']
        assert server.jobs[created['id']]['status']=='done'
        report=server.report(created['id'])
        assert 'Question 0' in report['body'] and 'Question 1' in report['body']
        assert len(json.loads(report['sources']))==1
    asyncio.run(run())
