"""L1-SEM-ANCHOR-02 离线预检、严格位置合同与锚定测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import ROOT, dimension_semantic_fields
from 语义证据校验 import (
    REQUIRED_DIMENSIONS,
    SCOPE_CURRENT,
    定位摘句,
    校验exact_text协议,
    校验语义审计响应,
    摘句在正文中,
)

EXEC = ROOT / "00_工程总控" / "工程执行层"
L1_SEM = EXEC / "L1工程" / "L1_语义审计.py"
RR02_DEBUG = (
    ROOT
    / "审计纠偏_2026-06-26"
    / "REAL_REPAIR_02_准点下班怎么了"
    / "runs"
    / "RR02-ANCHOR-R2"
    / "l1"
    / "RR02-ANCHOR-R2-L1_semantic_evidence_debug.json"
)


def _dim(name: str, quote: str, *, pid: str = "P0001", verdict: str = "REVIEW") -> dict:
    fields = dimension_semantic_fields(name, verdict)
    return {
        "name": name,
        "verdict": verdict,
        **fields,
        "evidence": [
            {
                "paragraph_id": pid,
                "exact_text": quote,
                "source_scope": SCOPE_CURRENT,
                "occurrence_index": 0,
                "evidence_rationale": f"该摘句作为{name}维度的代表性锚点，支持 strength_summary，不等同于整章证明。",
            }
        ],
    }


def _full(quote: str, **kwargs) -> dict:
    return {"dimensions": [_dim(n, quote, **kwargs) for n in REQUIRED_DIMENSIONS]}


def test_正确paragraph_id与occurrence_index通过():
    corpus = {"P0001": "门开了。门开了。"}
    payload = _full("门开了", pid="P0001")
    r = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert r.ok
    assert r.validated_evidence[0].occurrence_index == 0


def test_错误paragraph_id拒绝():
    corpus = {"P0002": "其中一枚缺了角，放上秤。"}
    r = 校验语义审计响应(_full("其中一枚缺了角", pid="P0099"), current_paragraphs=corpus)
    assert not r.ok
    assert any("PARAGRAPH_NOT_FOUND" in e for e in r.errors)


def test_文本存在于其他段落但paragraph_id错误仍拒绝():
    corpus = {"P0001": "标题", "P0002": "其中一枚缺了角，放上秤。"}
    r = 校验语义审计响应(_full("其中一枚缺了角", pid="P0001"), current_paragraphs=corpus)
    assert not r.ok
    assert any("EXACT_TEXT_NOT_IN_PARAGRAPH" in e for e in r.errors)


def test_不存在paragraph_id拒绝():
    corpus = {"P0001": "真实正文。"}
    r = 校验语义审计响应(_full("真实正文", pid="P9999"), current_paragraphs=corpus)
    assert not r.ok
    assert any("PARAGRAPH_NOT_FOUND" in e for e in r.errors)


def test_重复文本occurrence_index_0通过():
    text = "门开了。门开了。"
    assert 定位摘句(text, "门开了", 0) == (0, 3)


def test_重复文本occurrence_index_1通过():
    text = "门开了。门开了。"
    corpus = {"P0001": text}
    payload = _full("门开了", pid="P0001")
    for dim in payload["dimensions"]:
        dim["evidence"][0]["occurrence_index"] = 1
    r = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert r.ok
    assert r.validated_evidence[0].start_offset == 定位摘句(text, "门开了", 1)[0]


def test_重复文本occurrence_index越界拒绝():
    text = "门开了。门开了。"
    corpus = {"P0001": text}
    payload = _full("门开了", pid="P0001")
    for dim in payload["dimensions"]:
        dim["evidence"][0]["occurrence_index"] = 2
    r = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not r.ok
    assert any("OCCURRENCE_INDEX_INVALID" in e for e in r.errors)


def test_occurrence_index负数拒绝():
    corpus = {"P0001": "门开了。"}
    payload = _full("门开了", pid="P0001")
    for dim in payload["dimensions"]:
        dim["evidence"][0]["occurrence_index"] = -1
    r = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not r.ok
    assert any("occurrence_index 必须是非负整数" in e for e in r.errors)


def test_全章唯一命中不得自动修复paragraph_id():
    corpus = {"P0001": "标题", "P0002": "其中一枚缺了角，放上秤。"}
    r = 校验语义审计响应(_full("其中一枚缺了角", pid="P0099"), current_paragraphs=corpus)
    assert not r.ok
    assert not any("PARAGRAPH_ID_REPAIRED" in w for w in r.warnings)


def test_不再返回PARAGRAPH_ID_REPAIRED():
    corpus = {"P0001": "其中一枚缺了角，放上秤。"}
    r = 校验语义审计响应(_full("其中一枚缺了角"), current_paragraphs=corpus)
    assert r.ok
    assert not any("PARAGRAPH_ID_REPAIRED" in w for w in r.warnings)
    assert all(not ev.repaired for ev in r.validated_evidence)


def test_代码块单行证据通过():
    text = "```\n【补充数据】\n这座大楼的建筑设计图，在规划局没有备案。\n一次都没有。\n```"
    corpus = {"P0079": text}
    assert 校验语义审计响应(_full("这座大楼的建筑设计图，在规划局没有备案。", pid="P0079"), current_paragraphs=corpus).ok


def test_代码块删除换行拼接拒绝():
    text = "```\n【补充数据】\n这座大楼的建筑设计图，在规划局没有备案。\n一次都没有。\n```"
    corpus = {"P0079": text}
    r = 校验语义审计响应(_full("备案。一次都没有。", pid="P0079"), current_paragraphs=corpus)
    assert not r.ok


def test_多行证据拆分为多个item通过():
    text = "```\n【补充数据】\n这座大楼的建筑设计图，在规划局没有备案。\n一次都没有。\n```"
    corpus = {"P0079": text}
    dims = []
    for name in REQUIRED_DIMENSIONS:
        fields = dimension_semantic_fields(name, "REVIEW")
        ev = [
            {
                "paragraph_id": "P0079",
                "exact_text": "这座大楼的建筑设计图，在规划局没有备案。",
                "source_scope": SCOPE_CURRENT,
                "occurrence_index": 0,
                "evidence_rationale": "第一条单行证据。",
            },
            {
                "paragraph_id": "P0079",
                "exact_text": "一次都没有。",
                "source_scope": SCOPE_CURRENT,
                "occurrence_index": 0,
                "evidence_rationale": "第二条单行证据。",
            },
        ]
        dims.append({"name": name, "verdict": "REVIEW", **fields, "evidence": ev})
    r = 校验语义审计响应({"dimensions": dims}, current_paragraphs=corpus)
    assert r.ok
    assert len(r.validated_evidence) == 12


def test_直引号原文通过():
    corpus = {"P0001": '"走了。"小刘抬头。'}
    assert 摘句在正文中('"走了。"', corpus["P0001"])
    assert 校验语义审计响应(_full('"走了。"', pid="P0001"), current_paragraphs=corpus).ok


def test_弯引号替换拒绝():
    corpus = {"P0001": '"走了。"小刘抬头。'}
    assert not 摘句在正文中("\u201c走了。\u201d", corpus["P0001"])


def test_省略号截断拒绝():
    assert 校验exact_text协议("陈敛关掉IDE...") is not None


def test_多个独立evidence_item仍分别通过():
    corpus = {
        "P0001": "甲句。乙句。",
        "P0002": "丙句。",
        "P0003": "丁句。",
        "P0004": "戊句。",
        "P0005": "己句。",
    }
    dims = []
    for name in REQUIRED_DIMENSIONS:
        fields = dimension_semantic_fields(name, "REVIEW")
        if name == "章末追读":
            ev = [
                {
                    "paragraph_id": "P0005",
                    "exact_text": "己句。",
                    "source_scope": SCOPE_CURRENT,
                    "occurrence_index": 0,
                    "evidence_rationale": "章末摘句支持追读维度的 strength_summary。",
                }
            ]
        else:
            ev = [
                {
                    "paragraph_id": "P0001",
                    "exact_text": "甲句。",
                    "source_scope": SCOPE_CURRENT,
                    "occurrence_index": 0,
                    "evidence_rationale": "该摘句支持本维度 strength_summary 的第一部分。",
                },
                {
                    "paragraph_id": "P0002",
                    "exact_text": "丙句。",
                    "source_scope": SCOPE_CURRENT,
                    "occurrence_index": 0,
                    "evidence_rationale": "该摘句支持本维度 strength_summary 的第二部分。",
                },
            ]
        dims.append({"name": name, "verdict": "REVIEW", **fields, "evidence": ev})
    r = 校验语义审计响应({"dimensions": dims}, current_paragraphs=corpus)
    assert r.ok
    assert len(r.validated_evidence) == 11


def test_final_reason缺固定词但结构字段完整不阻断():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    payload = _full("他必须做出选择")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果":
            dim["verdict"] = "PASS"
            dim["final_reason"] = "全章事件增量清晰：准点下班（起因）→系统收割（结果）→匿名信（新起因）"
            dim["analysis_summary"] = "主要优点：链条连续；主要风险：无；最终选择 PASS 因为随后主角做出选择并推进。"
    r = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert r.ok


def test_结构化因果字段缺失仍阻断():
    corpus = {"P0001": "天气很好。"}
    payload = _full("天气很好")
    for dim in payload["dimensions"]:
        if dim["name"] == "因果":
            dim["verdict"] = "PASS"
            dim["final_reason"] = "情节清晰，容易理解。"
            dim["analysis_summary"] = "主要优点：无；主要风险：无因果；最终 PASS。"
    r = 校验语义审计响应(payload, current_paragraphs=corpus)
    assert not r.ok


def test_证据无效时失败包为空():
    r = 校验语义审计响应(_full("不存在"), current_paragraphs={"P0001": "真实正文"})
    assert not r.ok
    assert r.validated_evidence == []


def test_证据有效时解除EVIDENCE_INVALID():
    corpus = {"P0001": "他必须做出选择，否则代价会落在所有人身上。"}
    r = 校验语义审计响应(_full("他必须做出选择"), current_paragraphs=corpus)
    assert r.ok
    assert len(r.validated_evidence) == 6


def test_prompt_exact_text不得跨越换行符():
    text = L1_SEM.read_text(encoding="utf-8")
    assert "exact_text 不得跨越换行符" in text


def test_prompt_多行代码块规则():
    text = L1_SEM.read_text(encoding="utf-8")
    assert "若相关证据位于多行代码块中" in text


def test_prompt_代码块正确JSON示例():
    text = L1_SEM.read_text(encoding="utf-8")
    assert '"exact_text": "这座大楼的建筑设计图，在规划局没有备案。"' in text


def test_prompt_代码块错误JSON示例():
    text = L1_SEM.read_text(encoding="utf-8")
    assert '"exact_text": "备案。一次都没有。"' in text


def test_prompt_禁止跨行拼接原因():
    text = L1_SEM.read_text(encoding="utf-8")
    assert "删除换行后不再是连续子串" in text


def test_prompt_不得替换弯引号():
    text = L1_SEM.read_text(encoding="utf-8")
    assert "不得将正文直引号" in text


@pytest.mark.skipif(not RR02_DEBUG.is_file(), reason="RR02-ANCHOR-R2 debug 产物缺失")
def test_RR02_ANCHOR_R2_offline_replay():
    """使用已保存 parsed_final 离线重放，不得修改模型响应。"""
    debug = json.loads(RR02_DEBUG.read_text(encoding="utf-8"))
    corpus = {
        p["paragraph_id"]: p["text"]
        for p in debug["prompt_corpus"]["current"]["paragraphs"]
    }
    parsed = debug["parsed_final"]
    replay_records: list[dict] = []

    for dim in parsed["dimensions"]:
        for ev in dim["evidence"]:
            pid = ev["paragraph_id"]
            exact = ev["exact_text"]
            occ = ev["occurrence_index"]
            span = 定位摘句(corpus[pid], exact, occ)
            replay_records.append(
                {
                    "dimension": dim["name"],
                    "source_scope": ev["source_scope"],
                    "paragraph_id": pid,
                    "exact_text": exact,
                    "occurrence_index": occ,
                    "anchor_result": span is not None,
                    "failure_reason": None if span is not None else "anchor_failed",
                }
            )

    result = 校验语义审计响应(parsed, current_paragraphs=corpus)
    assert result.location_failed_dimensions == []
    assert result.anchor_diagnostics == []
    assert all(r["anchor_result"] for r in replay_records)
    assert result.ok
    assert result.computed_overall == "PASS"
    assert not any("PARAGRAPH_ID_REPAIRED" in w for w in result.warnings)
