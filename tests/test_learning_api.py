"""Authenticated learning flows through the actual ASGI routes, using local fakes."""
import asyncio
import io
import json

import httpx
import pytest
from pypdf import PdfWriter

import server
from src import library, quizzes, school, store


SOURCE = ('A computer network connects computers to exchange information. '
          'A star topology connects each device to a central switch. '
          'A bus topology connects devices to one shared cable.')


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path)
    monkeypatch.setattr(server, 'jobs', {})
    monkeypatch.setattr(server, 'active_tasks', set())
    monkeypatch.setattr(server, 'researchers', {})
    monkeypatch.setattr(server.google_setup, 'state', lambda: {'connected': False})
    library.init()
    quizzes.init()

    async def unexpected_model(**kwargs):
        raise AssertionError('This test must not call the real model.')

    monkeypatch.setattr(quizzes, 'llm_call_async', unexpected_model)
    monkeypatch.setattr(school, 'llm_call_async', unexpected_model)


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),
                             base_url='http://testserver',
                             headers={'X-Aster-Token': server.TOKEN})


async def upload(session, content=SOURCE, filename='lesson.txt', course='Networks', topic='Tema 1'):
    response = await session.post('/api/library/upload',
                                  params={'filename': filename, 'course': course, 'topic': topic},
                                  content=content.encode() if isinstance(content, str) else content)
    assert response.status_code == 200, response.text
    return response.json()


async def finish_job(session, response):
    assert response.status_code == 200, response.text
    job_id = response.json()['id']
    await server.jobs[job_id]['_task']
    snapshots = (await session.get('/api/jobs')).json()
    result = next(job for job in snapshots if job['id'] == job_id)
    assert '_task' not in result
    assert result['status'] == 'done', result
    return result['result']


def fake_quiz_model(monkeypatch):
    calls = []

    async def model(**kwargs):
        request = json.loads(kwargs['messages'][1]['content'])
        calls.append(request)
        return json.dumps({'questions': [
            {'prompt': 'Which statement is supported by the lesson (' + str(index + 1) + ')?',
             'options': ['Devices use the central switch', 'There are no cables',
                         'Only printers connect', 'Every network is wireless'],
             'correct': 0, 'explanation': 'Each device connects to the central switch.',
             'evidence': 'A star topology connects each device to a central switch.'}
            for index in range(request['question_count'])]})

    monkeypatch.setattr(quizzes, 'llm_call_async', model)
    return calls


def test_upload_original_and_state_keep_class_and_topic_and_require_auth():
    async def run():
        async with client() as session:
            item = await upload(session)
            assert item['course'] == 'Networks' and item['topic'] == 'Tema 1'
            content = await session.get(item['url'])
            assert content.status_code == 200 and content.content == SOURCE.encode()
            assert content.headers['content-type'].startswith('text/plain')
            assert content.headers['content-disposition'].startswith('inline;')
            assert content.headers['cache-control'] == 'no-store'
            assert content.headers['x-content-type-options'] == 'nosniff'
            state = (await session.get('/api/state')).json()
            assert state['library'][0]['id'] == item['id']
            material = next(m for m in state['materials'] if m['id'] == item['material_id'])
            assert material['course'] == 'Networks' and material['title'] == 'Tema 1'
            assert material['body'] == SOURCE
            assert str(store.DATA) not in json.dumps(state)
            session.headers.pop('X-Aster-Token')
            denied = [
                await session.get(item['url']),
                await session.get(item['url'], params={'token': server.TOKEN}),
                await session.get('/api/state'),
                await session.post('/api/library/' + item['id'] + '/analyze'),
                await session.post('/api/library/upload', params={'filename': 'other.txt'}, content=b'secret'),
                await session.post('/api/quizzes', json={'material_id': item['material_id'],
                                                       'course': 'Networks', 'count': 3}),
                await session.get('/api/quizzes/unknown'),
                await session.post('/api/quizzes/unknown/submit', json={'answers': {}}),
            ]
            assert all(response.status_code == 403 for response in denied)
            assert all(SOURCE not in response.text for response in denied)
            assert server.jobs == {} and len(library.list_files()) == 1
    asyncio.run(run())


def test_quiz_http_flow_rejects_wrong_class_and_hides_answers_until_submission(monkeypatch):
    calls = fake_quiz_model(monkeypatch)

    async def run():
        async with client() as session:
            item = await upload(session)
            request = {'material_id': item['material_id'], 'course': 'Biology', 'count': 3}
            rejected = await session.post('/api/quizzes', json=request)
            assert rejected.status_code == 400 and server.jobs == {} and calls == []
            request['course'] = 'Networks'
            quiz_id = await finish_job(session, await session.post('/api/quizzes', json=request))
            assert calls == [{'course': 'Networks', 'topic': 'Tema 1',
                              'question_count': 3, 'source_passages': {'0': SOURCE}}]
            response = await session.get('/api/quizzes/' + quiz_id)
            assert response.status_code == 200
            quiz = response.json()
            assert quiz['material_id'] == item['material_id'] and quiz['total'] == 3
            assert all(set(q) == {'id', 'prompt', 'options'} for q in quiz['questions'])
            assert quiz['submitted'] is None and quiz['score'] is None
            state = (await session.get('/api/state')).json()
            assert len(state['quizzes']) == 1
            assert not {'questions', 'answers', 'correct', 'explanation', 'evidence'} & state['quizzes'][0].keys()
            partial = await session.post('/api/quizzes/' + quiz_id + '/submit', json={'answers': {'q1': 0}})
            assert partial.status_code == 400
            answers = {q['id']: (1 if index == 1 else 0) for index, q in enumerate(quiz['questions'])}
            submitted = await session.post('/api/quizzes/' + quiz_id + '/submit', json={'answers': answers})
            assert submitted.status_code == 200
            result = submitted.json()
            assert result['score'] == 2 and result['submitted'] and result['feedback']
            assert all({'correct', 'selected', 'is_correct', 'explanation', 'evidence'} <= q.keys()
                       for q in result['questions'])
            assert (await session.get('/api/quizzes/' + quiz_id)).json() == result
            assert (await session.post('/api/quizzes/' + quiz_id + '/submit',
                                       json={'answers': answers})).json() == result
            changed = dict(answers, q2=0)
            assert (await session.post('/api/quizzes/' + quiz_id + '/submit',
                                       json={'answers': changed})).status_code == 400
    asyncio.run(run())


def test_document_exercises_stay_practice_and_preserve_completed(monkeypatch):
    homework = 'Draw and label a star network diagram.'
    review = 'Explain how a switch connects network devices.'
    text = 'Student exercises\n' + homework + '\n' + review + '\nDeadline: 04.11.2026'
    calls = []

    async def model(**kwargs):
        calls.append(kwargs['messages'][1]['content'])
        return json.dumps({'tasks': [
            {'text': homework, 'evidence': homework, 'kind': 'Homework'},
            {'text': review, 'evidence': review, 'kind': 'Review'}]})

    monkeypatch.setattr(school, 'llm_call_async', model)

    async def run():
        async with client() as session:
            item = await upload(session, text)
            analyzed = await finish_job(session, await session.post('/api/library/' + item['id'] + '/analyze'))
            assert 'Added 2 new tasks' in analyzed
            tasks = (await session.get('/api/state')).json()['tasks']
            assert {task['kind'] for task in tasks} == {'Review'}
            assert {task['source_id'] for task in tasks} == {item['material_id']}
            assert {task['course'] for task in tasks} == {'Networks'}
            assert all(task['due'] is None for task in tasks)
            completed = next(task for task in tasks if task['title'] == homework)
            assert (await session.patch('/api/tasks/' + completed['id'], json={'done': True})).status_code == 200
            duplicate = await upload(session, text)
            assert duplicate['id'] == item['id'] and duplicate['duplicate']
            repeated = await finish_job(session, await session.post('/api/library/' + item['id'] + '/analyze'))
            assert 'Added 0 new tasks' in repeated
            final = (await session.get('/api/state')).json()
            assert len(final['tasks']) == 2 and len(final['library']) == 1
            assert next(task for task in final['tasks'] if task['id'] == completed['id'])['done'] == 1
            assert calls == [text, text]
    asyncio.run(run())


def test_invalid_and_image_only_documents_fail_without_starting_jobs():
    async def run():
        async with client() as session:
            unsupported = await session.post('/api/library/upload', params={'filename': 'script.html'},
                                             content=b'<script>not schoolwork</script>')
            assert unsupported.status_code == 400 and library.list_files() == []
            assert (await session.get('/api/library/' + 'f' * 32 + '/file')).status_code == 404
            assert (await session.post('/api/library/' + 'f' * 32 + '/analyze')).status_code == 404
            stream = io.BytesIO()
            pdf = PdfWriter()
            pdf.add_blank_page(width=100, height=100)
            pdf.write(stream)
            item = await upload(session, stream.getvalue(), filename='scan.pdf')
            assert item['warning'] and not item['text']
            assert (await session.get(item['url'])).headers['content-type'] == 'application/pdf'
            refused = await session.post('/api/library/' + item['id'] + '/analyze')
            assert refused.status_code == 400 and 'No readable text' in refused.text
            assert server.jobs == {}
            missing = await session.post('/api/quizzes',
                                         json={'material_id': 'missing', 'course': 'Networks', 'count': 3})
            assert missing.status_code == 400
            assert (await session.get('/api/quizzes/missing')).status_code == 404
    asyncio.run(run())


@pytest.mark.parametrize('invalid_answer', [True, '0'])
def test_http_submission_rejects_coercible_answer_values(monkeypatch, invalid_answer):
    fake_quiz_model(monkeypatch)

    async def run():
        async with client() as session:
            item = await upload(session)
            quiz_id = await finish_job(session, await session.post('/api/quizzes',
                json={'material_id': item['material_id'], 'course': 'Networks', 'count': 3}))
            response = await session.post('/api/quizzes/' + quiz_id + '/submit',
                                           json={'answers': {'q1': invalid_answer, 'q2': 0, 'q3': 0}})
            assert response.status_code in (400, 422)
            assert (await session.get('/api/quizzes/' + quiz_id)).json()['submitted'] is None
    asyncio.run(run())
