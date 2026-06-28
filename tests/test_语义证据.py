from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import ROOT, dimension_semantic_fields
from 语义证据校验 import (
    REQUIRED_DIMENSIONS,
    SCOPE_CURRENT,
    定位摘句,
    摘句在正文中,
    计算整体结论,
    校验语义审计响应,
)

EXEC = ROOT / "00_工程总控" / "工程执行层"
RUBRIC_SCAN_PATHS = (
    EXEC / "L1工程" / "L1_语义审计.py",
    EXEC / "L1工程" / "L1_语义标尺.py",
)
FORBIDDEN_RUBRIC_TOKENS = (
    "GS-001",
    "GS-005",
    "李子夜",
    "贺按",
    "路满",
    "王磊",
    "借运",
    "拍门就结账",
    "人工期望结果",
)


def _full_payload(quote: str, *, target_overall: str = "REVIEW", paragraph_id: str = "P0001") -> dict:
    dimensions = []
    for name in REQUIRED_DIMENSIONS:
        verdict = "PASS" if target_overall == "PASS" else "REVIEW"
        fields = dimension_semantic_fields(name, verdict)
        dimensions.append(
            {
                "name": name,
                "verdict": verdict,
                **fields,
                "evidence": [
                    {
                        "paragraph_id": paragraph_id,
                        "exact_text": quote,
                        "source_scope": SCOPE_CURRENT,
                        "occurrence_index": 0,
                        "evidence_rationale": (
                            f"该摘句作为{name}维度的代表性锚点，支持 strength_summary，不等同于整章证明。"
                        ),
                    }
                ],
            }
        )
    return {"dimensions": dimensions}


def test_quote_must_exist_verbatim():
    source = "忽然察觉异常，因为规则正在收紧。"
    assert 摘句在正文中("忽然察觉异常", source)
    assert not 摘句在正文中("不存在的句子", source)


def test_no_whitespace_fuzzy_match():
    source = "hello world"
    assert 摘句在正文中("hello world", source)
    assert not 摘句在正文中("helloworld", source)


def test_compute_overall_from_dimensions():
    assert 计算整体结论(["PASS", "PASS"]) == "PASS"
    assert 计算整体结论(["PASS", "REVIEW"]) == "REVIEW"
    assert 计算整体结论(["PASS", "FAIL"]) == "FAIL"


def test_semantic_response_requires_six_unique_dimensions():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    quote = "他必须做出选择"
    result = 校验语义审计响应(_full_payload(quote), current_paragraphs=corpus)
    assert result.ok
    assert result.computed_overall == "REVIEW"
    assert len(result.dimension_reports) == 6


def test_fail_on_missing_dimension():
    corpus = {"P0001": "冲突升级。"}
    parsed = {
        "dimensions": [
            {
                "name": "冲突",
                "verdict": "FAIL",
                "analysis_summary": "弱",
                "evidence": [
                    {
                        "paragraph_id": "P0001",
                        "exact_text": "冲突升级",
                        "source_scope": SCOPE_CURRENT,
                        "occurrence_index": 0,
                    }
                ],
            }
        ]
    }
    result = 校验语义审计响应(parsed, current_paragraphs=corpus)
    assert not result.ok
    assert any("6 个维度" in e or "必须且只能" in e for e in result.errors)


def test_fail_without_evidence():
    corpus = {"P0001": "冲突升级。"}
    parsed = {
        "dimensions": [
            {"name": name, "verdict": "PASS", "analysis_summary": "ok"}
            for name in REQUIRED_DIMENSIONS
        ]
    }
    result = 校验语义审计响应(parsed, current_paragraphs=corpus)
    assert not result.ok
    assert any("evidence" in e for e in result.errors)


def test_reject_legacy_overall_field():
    corpus = {"P0001": "冲突升级。"}
    payload = _full_payload("冲突升级")
    payload["overall"] = "PASS"
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("overall" in e for e in result.errors)


def test_occurrence_index_selects_second_match():
    text = "他选择。再次他选择。"
    assert 定位摘句(text, "他选择", 0) == (0, 3)
    assert 定位摘句(text, "他选择", 1) == (6, 9)


def test_prior_chapter_evidence_validates_against_prior_corpus():
    current = {"P0001": "当章正文。", "P0002": "章末留下新的问题。"}
    prior = {"P0001": "前章钩子仍在。"}
    parsed = {
        "dimensions": [
            {
                "name": name,
                "verdict": "PASS",
                **dimension_semantic_fields(name, "PASS"),
                "evidence": [
                    {
                        "paragraph_id": "P0001" if name != "章末追读" else "P0002",
                        "exact_text": "前章钩子仍在" if name != "章末追读" else "章末留下新的问题",
                        "source_scope": "PRIOR_CHAPTER" if name != "章末追读" else SCOPE_CURRENT,
                        "occurrence_index": 0,
                        "evidence_rationale": f"该摘句支持{name}维度的 strength_summary，不等同于整章证明。",
                    }
                ],
            }
            for name in REQUIRED_DIMENSIONS
        ]
    }
    result = 校验语义审计响应(parsed, current_paragraphs=current, prior_paragraphs=prior)
    assert result.ok
    assert result.validated_evidence[0].start_offset == 0


def test_paragraph_id_wrong_rejected_even_when_unique_in_scope():
    corpus = {
        "P0001": "标题",
        "P0002": "其中一枚缺了角，放上秤，分量要少半块。",
    }
    parsed = {
        "dimensions": [
            {
                "name": name,
                "verdict": "PASS",
                **dimension_semantic_fields(name, "PASS"),
                "evidence": [
                    {
                        "paragraph_id": "P0099",
                        "exact_text": "其中一枚缺了角",
                        "source_scope": SCOPE_CURRENT,
                        "occurrence_index": 0,
                        "evidence_rationale": f"该摘句支持{name}维度的 strength_summary，不等同于整章证明。",
                    }
                ],
            }
            for name in REQUIRED_DIMENSIONS
        ]
    }
    result = 校验语义审计响应(parsed, current_paragraphs=corpus)
    assert not result.ok
    assert any("PARAGRAPH_NOT_FOUND" in e for e in result.errors)
    assert not any("PARAGRAPH_ID_REPAIRED" in w for w in result.warnings)


def test_reject_more_than_max_evidence_items():
    corpus = {"P0001": "其中一枚缺了角，放上秤，分量要少半块。"}
    items = [
        {
            "paragraph_id": "P0001",
            "exact_text": "其中一枚缺了角",
            "source_scope": SCOPE_CURRENT,
            "occurrence_index": 0,
            "evidence_rationale": f"证据{i}。",
        }
        for i in range(4)
    ]
    parsed = {
        "dimensions": [
            {
                "name": name,
                "verdict": "PASS",
                **dimension_semantic_fields(name, "PASS"),
                "evidence": items,
            }
            for name in REQUIRED_DIMENSIONS
        ]
    }
    result = 校验语义审计响应(parsed, current_paragraphs=corpus)
    assert not result.ok
    assert any("最多 3 条" in e for e in result.errors)


def test_analysis_summary_must_explain_strength_risk_and_decision():
    corpus = {"P0001": "同句测试。"}
    quote = "同句测试"
    payload = _full_payload(quote)
    for dim in payload["dimensions"]:
        dim["analysis_summary"] = quote
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("analysis_summary" in e for e in result.errors)


def test_reject_vague_final_reason():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择")
    for dim in payload["dimensions"]:
        dim["final_reason"] = "情节清晰，容易理解。"
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("空泛" in e for e in result.errors)


def test_causal_pass_requires_semantic_slots_not_literal_action_only():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果":
            dim["verdict"] = "PASS"
            dim["final_reason"] = "全章因果成立：准点下班（起因）→系统收割（结果）"
            dim["analysis_summary"] = "主要优点：链条连续；主要风险：无；最终 PASS 因为主角随后做出选择推进。"
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok


def test_chapter_end_evidence_must_be_in_last_twenty_percent():
    corpus = {
        "P0001": "开篇。",
        "P0002": "中段。",
        "P0003": "中段二。",
        "P0004": "中段三。",
        "P0005": "章末钩子仍在。",
    }
    payload = _full_payload("开篇", paragraph_id="P0001")
    for dim in payload["dimensions"]:
        if dim["name"] == "章末追读":
            dim["evidence"][0]["exact_text"] = "开篇"
            dim["evidence"][0]["paragraph_id"] = "P0001"
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("最后 20%" in e for e in result.errors)


def test_protocol_compliant_does_not_imply_semantic_support():
    """Quote exists and passes protocol keywords, but claim is unrelated — known limitation."""
    corpus = {"P0001": "天气很好，阳光照在窗台上。"}
    quote = "天气很好"
    payload = _full_payload(quote)
    for dim in payload["dimensions"]:
        dim["final_reason"] = "全章信息密度高，对话与场景切换频繁，故判PASS。"
        dim["strength_summary"] = "与摘句无关的强结论。"
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok
    report = result.dimension_reports[0]
    assert report.evidence_protocol_compliant is True
    assert report.evidence_semantically_sufficient is True
    assert report.semantic_support is None


def _override_dimension(payload: dict, name: str, **fields) -> None:
    for dim in payload["dimensions"]:
        if dim["name"] == name:
            dim.update(fields)


@pytest.mark.parametrize(
    ("dimension", "final_reason"),
    [
        ("动机", "他始终想保住职位，因此没有公开主管的异常要求。"),
        ("动机", "主角目标（积累资历、避免问责）在全章保持一致，无目标漂移或矛盾行为。"),
        ("冲突", "主管要求继续加班，主角坚持按时离开，双方立场无法同时满足。"),
        ("读者收益", "设计图从未备案，使大楼的合法性产生新的疑问。"),
    ],
)
def test_具体表达不含预设现象词仍通过(dimension: str, final_reason: str):
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择", target_overall="PASS")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果" and dim["verdict"] == "PASS":
            dim["final_reason"] = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级，故判PASS。"
    _override_dimension(payload, dimension, final_reason=final_reason)
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok, result.errors


def test_动机具体目标表达不含动机二字仍通过():
    corpus = {"P0001": "原因有两个。第一，他不想暴露自己其实懂。"}
    payload = _full_payload("原因有两个", target_overall="PASS")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果" and dim["verdict"] == "PASS":
            dim["final_reason"] = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级，故判PASS。"
    _override_dimension(
        payload,
        "动机",
        final_reason="主角目标（最大化积分、避免暴露）在全章保持一致，无目标漂移或矛盾行为。",
    )
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok


def test_具体行为一致性表达不含预设现象词仍通过():
    corpus = {"P0001": "他始终想保住职位，因此没有公开主管的异常要求。"}
    payload = _full_payload("他始终想保住职位", target_overall="PASS")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果" and dim["verdict"] == "PASS":
            dim["final_reason"] = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级，故判PASS。"
    _override_dimension(
        payload,
        "动机",
        final_reason="他始终想保住职位，因此没有公开主管的异常要求。",
    )
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok


def test_具体原因结果表达不含因果二字仍通过():
    corpus = {"P0001": "设计图从未备案，使大楼的合法性产生新的疑问。"}
    payload = _full_payload("设计图从未备案", target_overall="PASS")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果" and dim["verdict"] == "PASS":
            dim["final_reason"] = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级，故判PASS。"
    _override_dimension(
        payload,
        "读者收益",
        final_reason="设计图从未备案，使大楼的合法性产生新的疑问。",
    )
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok


def test_具体冲突双方表达不含冲突二字仍通过():
    corpus = {"P0001": "主管要求继续加班，主角坚持按时离开，双方立场无法同时满足。"}
    payload = _full_payload("主管要求继续加班", target_overall="PASS")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果" and dim["verdict"] == "PASS":
            dim["final_reason"] = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级，故判PASS。"
    _override_dimension(
        payload,
        "冲突",
        final_reason="主管要求继续加班，主角坚持按时离开，双方立场无法同时满足。",
    )
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok


def test_final_reason具体而analysis_summary简短仍通过():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择", target_overall="PASS")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果":
            dim["verdict"] = "PASS"
            dim["final_reason"] = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级，故判PASS。"
        if dim["name"] == "动机":
            dim["final_reason"] = "主角目标（积累资历、避免问责）在全章保持一致，无目标漂移或矛盾行为。"
            dim["analysis_summary"] = "主要优点：成立；主要风险：无明显；最终 PASS。"
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok


def test_analysis_summary具体而final_reason简短仍通过():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择", target_overall="PASS")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果":
            dim["verdict"] = "PASS"
            dim["final_reason"] = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级，故判PASS。"
        if dim["name"] == "动机":
            dim["final_reason"] = "目标清晰且持续。"
            dim["analysis_summary"] = (
                "主要优点：主角坚持保住职位并回避公开对抗；主要风险：无；"
                "最终选择 PASS 因为主角目标清晰且持续。"
            )
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok


def test_具体文本配合有效证据通过():
    corpus = {"P0001": "设计图从未备案，使大楼的合法性产生新的疑问。"}
    payload = _full_payload("设计图从未备案", target_overall="PASS")
    _override_dimension(
        payload,
        "读者收益",
        final_reason="设计图从未备案，使大楼的合法性产生新的疑问。",
    )
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok
    assert len(result.validated_evidence) == 6


@pytest.mark.parametrize(
    "final_reason",
    [
        "整体表现良好。",
        "没有明显问题。",
        "该维度通过。",
        "动机方面整体符合要求。",
        "整体来看表现较好，没有发现明显问题。",
        "该部分基本完整，可以判定通过。",
        "本章在这一维度上的处理总体正常。",
        "相关内容较为合理，满足基本要求。",
    ],
)
def test_通用套话仍阻断(final_reason: str):
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择")
    for dim in payload["dimensions"]:
        dim["final_reason"] = final_reason
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("空泛" in e for e in result.errors)


def test_长篇通用套话仍阻断():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择")
    boilerplate = (
        "整体来看表现较好，没有发现明显问题；该部分基本完整，可以判定通过；"
        "本章在这一维度上的处理总体正常；相关内容较为合理，满足基本要求。"
    )
    for dim in payload["dimensions"]:
        dim["final_reason"] = boilerplate
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("空泛" in e for e in result.errors)


def test_只有维度名称没有具体内容仍阻断():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择")
    _override_dimension(payload, "动机", final_reason="动机维度通过。")
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("空泛" in e for e in result.errors)


def test_无有效证据仍阻断():
    corpus = {"P0001": "真实正文。"}
    payload = _full_payload("不存在摘句")
    for dim in payload["dimensions"]:
        dim["final_reason"] = "主角目标（积累资历、避免问责）在全章保持一致，无目标漂移或矛盾行为。"
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("EXACT_TEXT_NOT_IN_PARAGRAPH" in e or "PARAGRAPH_NOT_FOUND" in e for e in result.errors)


def test_业务结论缺失仍阻断():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择")
    _override_dimension(
        payload,
        "动机",
        strength_summary="",
        final_reason="主角目标（积累资历、避免问责）在全章保持一致，无目标漂移或矛盾行为。",
    )
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("strength_summary 不能为空" in e for e in result.errors)


def test_空字符串仍阻断():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full_payload("他必须做出选择")
    _override_dimension(payload, "动机", final_reason="")
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("final_reason 不能为空" in e for e in result.errors)


def test_证据无效仍优先EVIDENCE_INVALID():
    corpus = {"P0001": "真实正文。"}
    payload = _full_payload("不存在摘句")
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("EXACT_TEXT_NOT_IN_PARAGRAPH" in e or "PARAGRAPH_NOT_FOUND" in e for e in result.errors)
    assert not any("空泛" in e for e in result.errors)


@pytest.mark.parametrize("path", RUBRIC_SCAN_PATHS)
def test_rubric_files_do_not_contain_sample_leakage(path: Path):
    text = path.read_text(encoding="utf-8")
    hits = [token for token in FORBIDDEN_RUBRIC_TOKENS if token in text]
    assert not hits, f"{path.name} 含样本专属内容：{hits}"
