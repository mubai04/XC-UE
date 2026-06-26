from __future__ import annotations

import json

from DeepSeek客户端 import STAGE_MODEL_ENV, create_client
from tests.conftest import make_mock_transport


def test_missing_api_key():
    client = create_client("L1", api_key="")
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "MISSING_API_KEY"


def test_chat_json_success():
    payload = {"ping": True}
    client = create_client("L2", api_key="test-key", transport=make_mock_transport(payload))
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert result.ok
    assert result.parsed == payload
    assert result.meta.get("finish_reason") == "stop"


def test_finish_reason_length_fails():
    client = create_client("L3", api_key="k", transport=make_mock_transport({"a": 1}, finish_reason="length"))
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "LENGTH"


def test_stage_default_models(monkeypatch):
    monkeypatch.delenv("XCUE_L1_MODEL", raising=False)
    monkeypatch.delenv("XCUE_L2_MODEL", raising=False)
    monkeypatch.delenv("XCUE_L3_MODEL", raising=False)
    assert create_client("L1", api_key="k").model == STAGE_MODEL_ENV["L1"][1]
    assert create_client("L2", api_key="k").model == STAGE_MODEL_ENV["L2"][1]
    assert create_client("L3", api_key="k").model == STAGE_MODEL_ENV["L3"][1]


def test_l1_thinking_disabled_l3_enabled(monkeypatch):
    captured: list[dict] = []

    def transport(url, headers, body, timeout):
        captured.append(json.loads(body.decode("utf-8")))
        return 200, json.dumps(
            {
                "choices": [
                    {"message": {"content": "{}"}, "finish_reason": "stop"},
                ]
            }
        )

    create_client("L1", api_key="k", transport=transport).chat_json([{"role": "user", "content": "x"}])
    create_client("L3", api_key="k", transport=transport).chat_json([{"role": "user", "content": "x"}])
    assert captured[0]["thinking"] == {"type": "disabled"}
    assert captured[1]["thinking"] == {"type": "enabled"}
    assert captured[1]["reasoning_effort"] == "high"


def test_http_error():
    from tests.conftest import make_error_transport

    client = create_client("L2", api_key="k", transport=make_error_transport(status=503))
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "HTTP_ERROR"


def test_timeout():
    from tests.conftest import make_timeout_transport

    client = create_client("L2", api_key="k", transport=make_timeout_transport())
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "TIMEOUT"


def test_invalid_json_content():
    def transport(url, headers, body, timeout):
        envelope = {"choices": [{"message": {"content": "not-json"}, "finish_reason": "stop"}]}
        return 200, json.dumps(envelope)

    client = create_client("L2", api_key="k", transport=transport)
    result = client.chat_json([{"role": "user", "content": "hi"}])
    assert not result.ok
    assert result.error_kind == "INVALID_JSON"
