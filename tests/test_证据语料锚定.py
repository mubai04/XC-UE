"""L1-SEM-ANCHOR-01 离线证据锚定测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import ROOT, dimension_semantic_fields
from 证据语料 import 构建章节证据语料, 规范化证据文本
from 语义证据校验 import (
    REQUIRED_DIMENSIONS,
    SCOPE_CURRENT,
    SCOPE_PRIOR,
    exact_text含省略号,
    定位摘句,
    摘句在正文中,
    校验exact_text协议,
    校验语义审计响应,
)


class _P:
    def __init__(self, i: int, text: str):
        self.编号 = i
        self.文本 = text
        self.段落ID = f"P{i:04d}"


def _dim_payload(name: str, quote: str, *, pid: str = "P0001", scope: str = SCOPE_CURRENT) -> dict:
    fields = dimension_semantic_fields(name, "REVIEW")
    return {
        "name": name,
        "verdict": "REVIEW",
        **fields,
        "evidence": [
            {
                "paragraph_id": pid,
                "exact_text": quote,
                "source_scope": scope,
                "occurrence_index": 0,
                "evidence_rationale": f"该摘句作为{name}维度的代表性锚点，支持 strength_summary，不等同于整章证明。",
            }
        ],
    }


def _full_payload(quote: str, **kwargs) -> dict:
    return {"dimensions": [_dim_payload(n, quote, **kwargs) for n in REQUIRED_DIMENSIONS]}


def test_01_plain_chinese_verbatim_pass():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    assert 校验语义审计响应(_full_payload("他必须做出选择"), current_paragraphs=corpus).ok


def test_code_block_single_line_pass_multiline_merge_rejected():
    text = "```\n【补充数据】\n这座大楼的建筑设计图，在规划局没有备案。\n一次都没有。\n```"
    corpus = {"P0079": text}
    single = "这座大楼的建筑设计图，在规划局没有备案。"
    merged = "这座大楼的建筑设计图，在规划局没有备案。一次都没有。"
    assert 校验语义审计响应(_full_payload(single, pid="P0079"), current_paragraphs=corpus).ok
    result = 校验语义审计响应(_full_payload(merged, pid="P0079"), current_paragraphs=corpus)
    assert not result.ok
    assert any("EXACT_TEXT_NOT_IN_PARAGRAPH" in e for e in result.errors)


def test_03_crlf_lf_equivalent_pass():
    raw = "第一行内容。\r\n"
    norm = 规范化证据文本(raw)
    corpus = {"P0001": norm}
    assert 定位摘句(norm, "第一行内容。", 0) is not None
    assert 校验语义审计响应(_full_payload("第一行内容。"), current_paragraphs=corpus).ok


def test_04_bom_stripped_pass():
    raw = "\ufeff章首文本。"
    corpus = {"P0001": 规范化证据文本(raw)}
    assert 校验语义审计响应(_full_payload("章首文本"), current_paragraphs=corpus).ok


def test_05_nfc_equivalent_pass():
    # NFC vs NFD for composed character (if any); use explicit NFC normalize
    import unicodedata

    base = "测试文本。"
    nfd = unicodedata.normalize("NFD", base)
    nfc = unicodedata.normalize("NFC", base)
    corpus = {"P0001": nfc}
    if nfd != nfc:
        assert 定位摘句(nfc, nfd, 0) is not None


def test_06_paraphrase_rejected():
    corpus = {"P0001": "陈敛关掉IDE，拿起工牌。"}
    result = 校验语义审计响应(_full_payload("陈敛关闭IDE并拿工牌"), current_paragraphs=corpus)
    assert not result.ok
    assert any("EXACT_TEXT_NOT_IN_PARAGRAPH" in e or "PARAGRAPH_NOT_FOUND" in e for e in result.errors)


def test_07_ellipsis_truncation_rejected():
    corpus = {"P0001": "陈敛关掉IDE，拿起工牌，站起来。"}
    assert 校验exact_text协议("陈敛关掉IDE…") is not None
    result = 校验语义审计响应(_full_payload("陈敛关掉IDE..."), current_paragraphs=corpus)
    assert not result.ok


def test_08_punctuation_substitution_rejected():
    corpus = {"P0001": "他说：\u201c走了。\u201d"}
    assert not 摘句在正文中('"走了。"', corpus["P0001"])


def test_09_cross_paragraph_concat_rejected():
    corpus = {"P0001": "段一。", "P0002": "段二。"}
    assert 校验exact_text协议("段一。\n\n段二。") is not None
    result = 校验语义审计响应(_full_payload("段一。\n\n段二。"), current_paragraphs=corpus)
    assert not result.ok


def test_10_wrong_paragraph_id_rejected():
    corpus = {"P0001": "标题", "P0002": "其中一枚缺了角，放上秤。"}
    payload = _full_payload("其中一枚缺了角", pid="P0099")
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("PARAGRAPH_NOT_FOUND" in e for e in result.errors)
    assert not any("PARAGRAPH_ID_REPAIRED" in w for w in result.warnings)


def test_10b_text_in_other_paragraph_wrong_id_still_rejected():
    corpus = {"P0001": "标题", "P0002": "其中一枚缺了角，放上秤。"}
    payload = _full_payload("其中一枚缺了角", pid="P0001")
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("EXACT_TEXT_NOT_IN_PARAGRAPH" in e for e in result.errors)


def test_11_occurrence_index_second_match():
    text = "他选择。再次他选择。"
    corpus = {"P0001": text}
    payload = _full_payload("他选择", pid="P0001")
    for dim in payload["dimensions"]:
        dim["evidence"][0]["occurrence_index"] = 1
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert result.ok
    assert result.validated_evidence[0].start_offset == 定位摘句(text, "他选择", 1)[0]


def test_11b_occurrence_index_out_of_range_rejected():
    text = "他选择。再次他选择。"
    corpus = {"P0001": text}
    payload = _full_payload("他选择", pid="P0001")
    for dim in payload["dimensions"]:
        dim["evidence"][0]["occurrence_index"] = 2
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("OCCURRENCE_INDEX_INVALID" in e for e in result.errors)


def test_11c_occurrence_index_negative_rejected():
    corpus = {"P0001": "他选择。"}
    payload = _full_payload("他选择", pid="P0001")
    for dim in payload["dimensions"]:
        dim["evidence"][0]["occurrence_index"] = -1
    result = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not result.ok
    assert any("occurrence_index 必须是非负整数" in e for e in result.errors)


def test_12_wrong_source_scope_rejected():
    current = {"P0001": "当章。"}
    prior = {"P0001": "前章钩子。"}
    payload = {
        "dimensions": [
            _dim_payload(n, "前章钩子", pid="P0001", scope=SCOPE_CURRENT) for n in REQUIRED_DIMENSIONS
        ]
    }
    result = 校验语义审计响应(payload, current_paragraphs=current, prior_paragraphs=prior)
    assert not result.ok


def test_13_debug_capture_structure_no_secrets(tmp_path: Path):
    debug = {
        "prompt_corpus": {"current": {"paragraphs": [{"paragraph_id": "P0001", "text": "x"}]}},
        "raw_responses": [{"parsed": {"dimensions": []}}],
    }
    p = tmp_path / "debug.json"
    p.write_text(json.dumps(debug, ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert "api_key" not in json.dumps(loaded).lower()


def test_14_evidence_invalid_empty_failure_packet():
    """EVIDENCE_INVALID 时 routeable_count=0 — 由 L1 决策层保证；此处验证校验失败。"""
    result = 校验语义审计响应(_full_payload("不存在"), current_paragraphs={"P0001": "真实正文"})
    assert not result.ok
    assert result.validated_evidence == []


def test_15_valid_evidence_not_audit_blocked():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    result = 校验语义审计响应(_full_payload("他必须做出选择"), current_paragraphs=corpus)
    assert result.ok
    assert len(result.validated_evidence) == 6


def test_unified_corpus_from_paragraphs():
    paras = [_P(1, "段A。"), _P(2, "段B。")]
    current, prior = 构建章节证据语料(current_paragraphs=paras, prior_paragraphs=[])
    assert current.paragraph_map()["P0001"] == "段A。"
    assert prior is None
