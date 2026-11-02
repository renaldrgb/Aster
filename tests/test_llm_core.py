import asyncio

import pytest

from src import llm_core


@pytest.mark.parametrize('format_value', [None, 'json', {'type': 'object', 'properties': {'answer': {'type': 'string'}}}])
def test_ollama_format_is_forwarded_without_changing_plain_text_calls(monkeypatch, format_value):
    requests = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'message': {'content': '{"answer":"ready"}'}}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            requests.append((url, json))
            return Response()

    monkeypatch.setattr(llm_core.httpx, 'AsyncClient', Client)
    result = asyncio.run(llm_core.llm_call_async(model='local-test', messages=[{'role': 'user', 'content': 'Test'}],
                                                format=format_value, temperature=0))
    assert result == '{"answer":"ready"}'
    url, payload = requests[0]
    assert url == 'http://127.0.0.1:11434/api/chat'
    assert payload['model'] == 'local-test' and payload['think'] is False
    assert payload['options']['temperature'] == 0
    if format_value is None:
        assert 'format' not in payload
    else:
        assert payload['format'] == format_value
