from __future__ import annotations

import json

from DeepSeek客户端 import DeepSeekClient
from tests.conftest import make_error_transport, make_mock_transport, make_timeout_transport


def test_missing_api_key():
    client = DeepSeekClient(api_key="")
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "MISSING_API_KEY"


def test_chat_json_success():
    payload = {"dimensions": [], "overall": "PASS"}
    client = DeepSeekClient(api_key="test-key", transport=make_mock_transport(payload))
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert result.ok
    assert result.parsed == payload


def test_http_error():
    client = DeepSeekClient(api_key="k", transport=make_error_transport(status=503))
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "HTTP_ERROR"


def test_timeout():
    client = DeepSeekClient(api_key="k", transport=make_timeout_transport())
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "TIMEOUT"


def test_invalid_json_content():
    def transport(url, headers, body, timeout):
        envelope = {"choices": [{"message": {"content": "not-json"}}]}
        return 200, json.dumps(envelope)

    client = DeepSeekClient(api_key="k", transport=transport)
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "INVALID_JSON"
