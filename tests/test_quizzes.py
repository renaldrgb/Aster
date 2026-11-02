import asyncio
import json

import pytest

from src import quizzes, store


SOURCE = ('A computer network connects computers to exchange information. '
          'A star topology connects each device to a central switch. '
          'A bus topology connects devices to one shared cable. '
          'Network redundancy provides an alternative path when a connection fails.')
EVIDENCE = 'A star topology connects each device to a central switch.'

def test_correct_answer_text_overrides_wrong_model_index(monkeypatch):
    payload=model_response(3)
    for q in payload['questions']:
        q['correct']=3
        q['correct_answer']='Each device'
    install_model(monkeypatch,[json.dumps(payload)])
    quiz_id=asyncio.run(quizzes.generate('lesson',3))
    result=quizzes.submit(quiz_id,{'q1':0,'q2':0,'q3':0})
    assert result['score']==3

def test_classroom_description_uses_linked_document(monkeypatch):
    store.save_material('course:post','Networks','Leksioni 3','A short lesson description.','https://classroom.google.com/c/course/m/post')
    store.set_setting('attachments:course:post',['lesson'])
    calls=install_model(monkeypatch)
    quiz_id=asyncio.run(quizzes.generate('course:post',5))
    request=json.loads(calls[0]['messages'][1]['content'])
    assert request['source_passages']=={'0':SOURCE}
    assert quizzes.get_quiz(quiz_id)['topic']=='Leksioni 3'

def test_short_classroom_post_without_attachments_is_clear():
    material={'id':'course:empty','title':'Empty lesson','body':'Only a short description','url':'https://classroom.google.com/c/course/m/empty'}
    store.set_setting('attachments:course:empty',[])
    with pytest.raises(ValueError,match='short description'):
        asyncio.run(quizzes.lesson_source(material,lambda x:None))


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path)
    store.init()
    quizzes.init()
    store.save_material('lesson', 'Networks', 'Network topologies', SOURCE, 'https://example.org/lesson')


def model_response(count=3):
    return {'questions': [
        {'prompt': 'Question ' + str(index + 1) + ': what is connected to the switch?',
         'options': ['Each device', 'Only servers', 'No devices', 'Only printers'],
         'correct': 0, 'explanation': 'The document says each device uses the central switch.',
         'evidence': EVIDENCE}
        for index in range(count)
    ]}


def install_model(monkeypatch, responses=None):
    calls = []

    async def model(**kwargs):
        calls.append(kwargs)
        if responses is not None:
            result = responses[len(calls) - 1]
            if isinstance(result, Exception):
                raise result
            return result
        count = json.loads(kwargs['messages'][1]['content'])['question_count']
        return json.dumps(model_response(count))

    monkeypatch.setattr(quizzes, 'llm_call_async', model)
    return calls


@pytest.mark.parametrize('count', [3, 10])
def test_selected_source_and_count_boundaries(monkeypatch, count):
    store.save_material('unrelated', 'Biology', 'Wrong topic', 'Do not use this unrelated material.', '')
    calls = install_model(monkeypatch)
    progress = []
    quiz_id = asyncio.run(quizzes.generate('lesson', count, progress.append))
    quiz = quizzes.get_quiz(quiz_id)
    request = json.loads(calls[0]['messages'][1]['content'])
    assert request['source_passages'] == {'0': SOURCE}
    assert request['course'] == quiz['course'] == 'Networks'
    assert request['topic'] == quiz['topic'] == 'Network topologies'
    schema = calls[0]['format']
    assert schema['properties']['questions']['maxItems'] == count
    assert schema['properties']['questions']['items']['properties']['correct_answer']['type'] == 'string'
    assert quiz['material_id'] == 'lesson'
    assert len(quiz['questions']) == quiz['total'] == count
    assert len({question['id'] for question in quiz['questions']}) == count
    assert progress[-1] == 'Your quiz is ready'
    assert all(set(question) == {'id', 'prompt', 'options'} for question in quiz['questions'])
    assert quiz['score'] is quiz['submitted'] is None
    summary = quizzes.list_quizzes()[0]
    assert 'questions' not in summary and 'answers' not in summary
    assert not {'correct', 'evidence', 'explanation', 'answers'} & summary.keys()


@pytest.mark.parametrize('count', [2, 11, True, '5', 3.5])
def test_rejects_invalid_count_without_model_call(monkeypatch, count):
    calls = install_model(monkeypatch)
    with pytest.raises(ValueError, match='3 and 10'):
        asyncio.run(quizzes.generate('lesson', count))
    assert not calls and quizzes.list_quizzes() == []


@pytest.mark.parametrize('material_id,body', [('missing', None), ('blank', ''), ('short', 'Not enough.')])
def test_missing_or_unreadable_document_does_not_call_model(monkeypatch, material_id, body):
    if body is not None:
        store.save_material(material_id, 'Networks', 'Empty', body, '')
    calls = install_model(monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(quizzes.generate(material_id, 3))
    assert not calls and quizzes.list_quizzes() == []


def test_malformed_response_is_retried_once(monkeypatch):
    calls = install_model(monkeypatch, ['invalid json', json.dumps(model_response())])
    quiz_id = asyncio.run(quizzes.generate('lesson', 3))
    assert len(calls) == 2
    assert 'previous result failed validation' in calls[1]['messages'][-1]['content']
    assert calls[1]['messages'][-2] == {'role': 'assistant', 'content': 'invalid json'}
    assert quizzes.get_quiz(quiz_id)['total'] == 3
    assert len(quizzes.list_quizzes()) == 1


@pytest.mark.parametrize('corruption', ['evidence', 'correct_bool', 'correct_range', 'duplicates',
                                       'option_count', 'duplicate_prompt', 'question_count', 'blank_explanation'])
def test_unreliable_questions_are_never_saved(monkeypatch, corruption):
    invalid = model_response()
    first = invalid['questions'][0]
    if corruption == 'evidence':
        first['evidence'] = 'This supporting fact does not occur in the selected document.'
    elif corruption == 'correct_bool':
        first['correct'] = True
    elif corruption == 'correct_range':
        first['correct'] = 4
    elif corruption == 'duplicates':
        first['options'][1] = '  EACH DEVICE  '
    elif corruption == 'option_count':
        first['options'].pop()
    elif corruption == 'duplicate_prompt':
        invalid['questions'][1]['prompt'] = first['prompt']
    elif corruption == 'question_count':
        invalid['questions'].pop()
    elif corruption == 'blank_explanation':
        first['explanation'] = ''
    serialized = json.dumps(invalid)
    calls = install_model(monkeypatch, [serialized, serialized])
    with pytest.raises(ValueError, match='No quiz was saved'):
        asyncio.run(quizzes.generate('lesson', 3))
    assert len(calls) == 2 and quizzes.list_quizzes() == []


def test_model_connection_failure_is_not_saved(monkeypatch):
    calls = install_model(monkeypatch, [RuntimeError('model unavailable')])
    with pytest.raises(RuntimeError, match='unavailable'):
        asyncio.run(quizzes.generate('lesson', 3))
    assert len(calls) == 1 and quizzes.list_quizzes() == []


def test_grading_persists_feedback_and_is_immutable(monkeypatch):
    install_model(monkeypatch)
    quiz_id = asyncio.run(quizzes.generate('lesson', 3))
    before = quizzes.get_quiz(quiz_id)
    answers = {question['id']: (1 if index == 1 else 0)
               for index, question in enumerate(before['questions'])}
    result = quizzes.submit(quiz_id, answers)
    assert result['score'] == 2 and result['total'] == 3 and result['submitted']
    assert result['feedback'].startswith('2 of 3 correct.')
    assert [question['is_correct'] for question in result['questions']] == [True, False, True]
    for question in result['questions']:
        assert question['correct'] == 0
        assert question['evidence'] == EVIDENCE
        assert question['explanation']
    quizzes.init()
    assert quizzes.get_quiz(quiz_id) == result
    assert quizzes.submit(quiz_id, answers) == result
    with pytest.raises(ValueError, match='already been submitted'):
        quizzes.submit(quiz_id, {question['id']: 0 for question in before['questions']})
    assert quizzes.get_quiz(quiz_id) == result
    summary = quizzes.list_quizzes()[0]
    assert summary['score'] == 2 and summary['submitted'] == result['submitted']
    assert 'questions' not in summary


@pytest.mark.parametrize('answers', [{'q1': 0}, {'q1': 0, 'q2': 0, 'q3': 0, 'q4': 0},
                                  {'q1': 0, 'q2': True, 'q3': 0},
                                  {'q1': 0, 'q2': '0', 'q3': 0},
                                  {'q1': 0, 'q2': 4, 'q3': 0}, None])
def test_invalid_submission_leaves_unfinished_quiz(monkeypatch, answers):
    install_model(monkeypatch)
    quiz_id = asyncio.run(quizzes.generate('lesson', 3))
    with pytest.raises(ValueError):
        quizzes.submit(quiz_id, answers)
    quiz = quizzes.get_quiz(quiz_id)
    assert quiz['submitted'] is None and quiz['score'] is None
    assert all(set(question) == {'id', 'prompt', 'options'} for question in quiz['questions'])


def test_saved_quiz_survives_removal_of_original_document(monkeypatch):
    install_model(monkeypatch)
    quiz_id = asyncio.run(quizzes.generate('lesson', 3))
    with store.db() as con:
        con.execute('DELETE FROM materials WHERE id=?', ('lesson',))
    quiz = quizzes.get_quiz(quiz_id)
    assert quiz['topic'] == 'Network topologies'
    result = quizzes.submit(quiz_id, {question['id']: 0 for question in quiz['questions']})
    assert result['score'] == 3


def test_unknown_quiz_has_clear_error():
    with pytest.raises(ValueError, match='Quiz not found'):
        quizzes.get_quiz('absent')
    with pytest.raises(ValueError, match='Quiz not found'):
        quizzes.submit('absent', {})


@pytest.mark.parametrize('opening,closing', [('"', '"'), ('“', '”'), ('«', '»')])
def test_extra_quotation_delimiters_preserve_exact_grounding(opening, closing):
    response = model_response()
    for question in response['questions']:
        question['evidence'] = opening + EVIDENCE + closing
    result = quizzes._validate(json.dumps(response), 3, SOURCE)
    assert all(question['evidence'] == EVIDENCE for question in result)


@pytest.mark.parametrize('evidence', [
    '"A star topology links each device to a central switch."',
    'A star topology connects each device to a central switch. Network redundancy provides an alternative path',
    '“Every network requires a central switch.”',
    'Source: ' + EVIDENCE,
])
def test_quote_repair_never_accepts_paraphrases_or_joined_passages(evidence):
    response = model_response()
    response['questions'][0]['evidence'] = evidence
    with pytest.raises(ValueError, match='Question 1: Evidence must be copied exactly'):
        quizzes._validate(json.dumps(response), 3, SOURCE)
