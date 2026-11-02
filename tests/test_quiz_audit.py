import asyncio,json,pytest
from src import quizzes

def test_equivalent_driver_versions_rejected_before_review(monkeypatch):
    async def unexpected(**kwargs):
        pytest.fail('Ambiguous version identifiers should be caught before the AI review')
    monkeypatch.setattr(quizzes,'llm_call_async',unexpected)
    q={'id':'q1','prompt':'Cili është versioni i driver-it?',
       'options':['32.0.15.9649','32.0.16.1742','617.42','32.0.16.1741']}
    with pytest.raises(ValueError,match='potentially equivalent'):
        asyncio.run(quizzes.audit_questions([q]))

def test_explicit_label_not_positional_guess():
    q=quizzes.prepare_question({'prompt':'Which program?\nOptions:\nB. 7-Zip\nCorrect Answer: B','options':['B. 7-Zip','A. VLC','C. Mouse','D. Keyboard'],'correct_answer':'B'})
    assert q['correct']==0 and q['prompt']=='Which program?' and q['options'][0]=='7-Zip'
    with pytest.raises(ValueError):quizzes.prepare_question({'options':['VLC','7-Zip'],'correct_answer':'B'})

@pytest.mark.parametrize('valid',[['7-Zip'],['VLC'],['7-Zip','VLC'],[]])
def test_independent_review_rejects_wrong_or_multiple_answers(monkeypatch,valid):
    q={'id':'q1','prompt':'Which compresses files?','options':['VLC','7-Zip','Mouse','Keyboard'],'correct':1,'evidence':'7-Zip compresses files. VLC plays media.'}
    async def model(**kwargs):
        data=json.loads(kwargs['messages'][1]['content']);assert 'correct' not in data[0] and 'explanation' not in data[0]
        return json.dumps({'answers':[{'id':'q1','correct_answer':valid[0] if valid else '', 'ambiguous':len(valid)>1,'reason':'Checked source'}]})
    monkeypatch.setattr(quizzes,'llm_call_async',model)
    if valid==['7-Zip']:asyncio.run(quizzes.audit_questions([q]))
    else:
        with pytest.raises(ValueError):asyncio.run(quizzes.audit_questions([q]))
