import asyncio
import json

import pytest

from src import question_actions, store


def test_selection_filters_type_within_document_and_keeps_completed(monkeypatch):
    tasks = [
        {'id': '1', 'source_id': 'a', 'course': 'Class', 'created': '1', 'kind': 'Homework', 'done': 0},
        {'id': '2', 'source_id': 'a', 'course': 'Class', 'created': '1', 'kind': 'Review', 'done': 1},
        {'id': '3', 'source_id': 'b', 'course': 'Class', 'created': '1', 'kind': 'Review', 'done': 0},
    ]
    monkeypatch.setattr(store, 'rows', lambda table: tasks if table == 'tasks' else [])
    assert question_actions.selection('a', 'Homework')[0] == tasks[:1]
    assert question_actions.selection('a', 'Review')[0] == tasks[1:2]
    assert question_actions.selection('', 'Review')[0] == tasks[1:]
    assert len(question_actions.selection('a')[0]) == 2
    with pytest.raises(ValueError, match='assignments'):
        question_actions.selection('b', 'Homework')
    with pytest.raises(ValueError, match='Choose'):
        question_actions.selection('', 'arbitrary')


def test_assignment_guidance_uses_deliverable_deadline_and_preserves_status(monkeypatch):
    task = {'id': 'a', 'source_id': 'doc', 'title': 'Build a network diagram',
            'kind': 'Homework', 'due': '2026-11-01', 'course': 'Networks', 'url': '', 'done': 0}
    calls, saved = [], []

    async def model(**kwargs):
        calls.append(kwargs)
        return 'Make a diagram showing the required connections.'

    monkeypatch.setattr(question_actions, 'llm_call_async', model)
    monkeypatch.setattr(store, 'message', lambda *args: saved.append(args))
    result = asyncio.run(question_actions.answer_questions([task], {'doc': {'body': 'Lesson text'}}, lambda _: None))
    context = json.loads(calls[0]['messages'][1]['content'])
    assert context['type'] == 'assignment'
    assert context['due_date'] == '2026-11-01'
    assert 'handed in' in calls[0]['messages'][0]['content']
    assert 'Do not claim the task is completed' in calls[0]['messages'][0]['content']
    assert 'remain on your to-do list' in result
    assert len(saved) == 1 and task['done'] == 0
