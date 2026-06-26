from __future__ import annotations

from 语义证据校验 import 摘句在正文中, 校验语义审计响应


def test_quote_must_exist_verbatim():
    source = "忽然察觉异常，因为规则正在收紧。"
    assert 摘句在正文中("忽然察觉异常", source)
    assert not 摘句在正文中("不存在的句子", source)


def test_semantic_response_validation():
    source = "他必须做出选择，否则代价会落在所有人身上。"
    parsed = {
        "overall": "REVIEW",
        "dimensions": [
            {
                "name": "动机",
                "verdict": "REVIEW",
                "score": 3,
                "explanation": "动机存在但压力不足",
                "evidence_quotes": [{"paragraph": 2, "quote": "他必须做出选择"}],
            }
        ],
    }
    ok, errors = 校验语义审计响应(parsed, source)
    assert ok
    assert not errors


def test_fail_without_evidence_on_non_pass():
    source = "冲突升级。"
    parsed = {
        "overall": "FAIL",
        "dimensions": [{"name": "冲突", "verdict": "FAIL", "score": 2, "explanation": "弱"}],
    }
    ok, errors = 校验语义审计响应(parsed, source)
    assert not ok
    assert any("evidence_quotes" in e for e in errors)
