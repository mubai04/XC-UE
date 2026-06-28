from __future__ import annotations

import json
import uuid

from DeepSeek客户端 import create_client
from L1_语义审计 import 审计
from tests.conftest import find_chapter_evidence, make_semantic_context, sample_chapter_text, semantic_audit_payload


def test_evidence_retry_recovers_on_second_response():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    context = make_semantic_context(text)
    quote = f"{seed} 忽然察觉异常"
    paragraph_id, _ = find_chapter_evidence(text, quote)
    bad = semantic_audit_payload("不存在", target_overall="PASS", chapter_text=text)
    good = semantic_audit_payload(
        quote, target_overall="PASS", paragraph_id=paragraph_id, chapter_text=text
    )
    responses = [bad, good]
    call_count = {"n": 0}

    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        payload = responses[min(call_count["n"], len(responses) - 1)]
        call_count["n"] += 1
        envelope = {
            "choices": [
                {
                    "message": {"content": json.dumps(payload, ensure_ascii=False)},
                    "finish_reason": "stop",
                }
            ]
        }
        return 200, json.dumps(envelope, ensure_ascii=False)

    client = create_client("L1", api_key="k", transport=transport)
    result = 审计(context, client=client)
    assert result.可用
    assert result.整体结论 == "PASS"
    assert result.meta.evidence_retry_count >= 1


def test_transport_retry_recovers_after_timeout():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    context = make_semantic_context(text)
    quote = f"{seed} 忽然察觉异常"
    paragraph_id, _ = find_chapter_evidence(text, quote)
    payload = semantic_audit_payload(
        quote, target_overall="PASS", paragraph_id=paragraph_id, chapter_text=text
    )
    attempts = {"n": 0}

    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TimeoutError("timed out")
        envelope = {
            "choices": [
                {
                    "message": {"content": json.dumps(payload, ensure_ascii=False)},
                    "finish_reason": "stop",
                }
            ]
        }
        return 200, json.dumps(envelope, ensure_ascii=False)

    client = create_client("L1", api_key="k", transport=transport)
    result = 审计(context, client=client)
    assert result.可用
    assert result.meta.transport_retry_count >= 1
