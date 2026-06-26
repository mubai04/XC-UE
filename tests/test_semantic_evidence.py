from __future__ import annotations

from 语义证据校验 import REQUIRED_DIMENSIONS, 摘句在正文中, 校验语义审计响应


def _full_payload(quote: str, *, overall: str = "REVIEW") -> dict:
    return {
        "overall": overall,
        "dimensions": [
            {
                "name": name,
                "verdict": "PASS" if overall == "PASS" else "REVIEW",
                "score": 3,
                "explanation": "ok",
                "evidence_quotes": [{"paragraph": 1, "quote": quote}],
            }
            for name in REQUIRED_DIMENSIONS
        ],
    }


def test_quote_must_exist_verbatim():
    source = "忽然察觉异常，因为规则正在收紧。"
    assert 摘句在正文中("忽然察觉异常", source)
    assert not 摘句在正文中("不存在的句子", source)


def test_no_whitespace_fuzzy_match():
    source = "hello world"
    assert 摘句在正文中("hello world", source)
    assert not 摘句在正文中("helloworld", source)


def test_semantic_response_requires_six_unique_dimensions():
    source = "他必须做出选择，否则代价会落在所有人身上。"
    quote = "他必须做出选择"
    ok, errors = 校验语义审计响应(_full_payload(quote), source)
    assert ok
    assert not errors


def test_fail_on_missing_dimension():
    source = "冲突升级。"
    parsed = {
        "overall": "FAIL",
        "dimensions": [
            {
                "name": "冲突",
                "verdict": "FAIL",
                "score": 2,
                "explanation": "弱",
                "evidence_quotes": [{"paragraph": 1, "quote": "冲突升级"}],
            }
        ],
    }
    ok, errors = 校验语义审计响应(parsed, source)
    assert not ok
    assert any("6 个维度" in e or "必须且只能" in e for e in errors)


def test_fail_without_evidence_on_pass():
    source = "冲突升级。"
    parsed = {
        "overall": "PASS",
        "dimensions": [
            {"name": name, "verdict": "PASS", "score": 5, "explanation": "ok"}
            for name in REQUIRED_DIMENSIONS
        ],
    }
    ok, errors = 校验语义审计响应(parsed, source)
    assert not ok
    assert any("evidence_quotes" in e for e in errors)


def test_overall_must_match_dimensions():
    source = "他必须做出选择，否则代价会落在所有人身上。"
    quote = "他必须做出选择"
    payload = _full_payload(quote, overall="PASS")
    payload["dimensions"][0]["verdict"] = "FAIL"
    ok, errors = 校验语义审计响应(payload, source)
    assert not ok
    assert any("overall" in e for e in errors)
