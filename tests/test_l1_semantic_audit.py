from __future__ import annotations

import uuid

from DeepSeek客户端 import DeepSeekClient
from L1_语义审计 import 审计
from 正文切分 import 切段, 清理正文
from tests.conftest import make_mock_transport, sample_chapter_text


def test_semantic_audit_api_failure_blocks_pass():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    title, body = 清理正文(text)
    paragraphs = 切段(body)
    client = DeepSeekClient(api_key="")
    result = 审计(paragraphs, title, body, client=client)
    assert not result.可用
    assert any(item.严重级别 == "error" for item in result.检测项列表)


def test_semantic_audit_valid_response():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    title, body = 清理正文(text)
    paragraphs = 切段(body)
    quote = f"{seed} 忽然察觉异常"
    payload = {
        "overall": "REVIEW",
        "dimensions": [
            {
                "name": name,
                "verdict": "REVIEW" if name != "因果" else "PASS",
                "score": 3,
                "explanation": f"{name} 信号",
                "evidence_quotes": [{"paragraph": 1, "quote": quote}],
            }
            for name in ("因果", "动机", "冲突", "读者收益", "认知成本", "章末追读")
        ],
    }
    client = DeepSeekClient(api_key="k", transport=make_mock_transport(payload))
    result = 审计(paragraphs, title, body, client=client)
    assert result.可用
    assert result.整体结论 == "REVIEW"
    assert len(result.检测项列表) == 6


def test_semantic_audit_invalid_quote_rejected():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    title, body = 清理正文(text)
    paragraphs = 切段(body)
    payload = {
        "overall": "FAIL",
        "dimensions": [
            {
                "name": "因果",
                "verdict": "FAIL",
                "score": 1,
                "explanation": "弱",
                "evidence_quotes": [{"paragraph": 1, "quote": "完全不存在的摘句"}],
            }
        ],
    }
    client = DeepSeekClient(api_key="k", transport=make_mock_transport(payload))
    result = 审计(paragraphs, title, body, client=client)
    assert not result.可用
    assert any("证据" in item.名称 or "校验" in item.名称 for item in result.检测项列表)
