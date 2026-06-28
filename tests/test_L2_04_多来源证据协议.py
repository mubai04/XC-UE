from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from L2模型 import 失败输入, 证据
from 设定上下文 import 构造设定上下文
from 设定模型 import 设定诊断结果
from 设定证据校验 import 校验设定响应
from 证据索引 import (
    SETTING_RESPONSE_SCHEMA,
    SOURCE_CHAPTER,
    SOURCE_IR,
    SOURCE_PROJECT_RULE,
    构建证据索引,
)
from tests.conftest import l2_04_v2_payload, repo_root


def _item(quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="t",
        状态="失败",
        说明="R5C",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型="创意设定失败",
        候选模块="L2-04",
        回流验收位置="L1-01",
        修复方向="加压",
    )


def _setup_case(tmp_path: Path) -> tuple[Path, Path]:
    case = tmp_path / "case"
    chapters = case / "chapters"
    ir = case / "IR"
    chapters.mkdir(parents=True)
    ir.mkdir()
    chapter = chapters / "chapter.md"
    chapter.write_text(
        "塔院试炼开启。执事宣布：入塔者需持木牌。\n\n"
        "正文未写：不持牌者不得入塔，也未写持牌代价。\n\n"
        "仍无具体后果。角色可进可退。",
        encoding="utf-8",
    )
    (ir / "IR-02_世界约束.md").write_text(
        "# IR-02 世界约束\n\n"
        "| 编号 | 规则 | 触发条件 | 代价 | 后果 |\n"
        "|---|---|---|---|---|\n"
        "| R-101 | 入塔需持木牌 | 踏入塔门 | 失去一段记忆 | 遗忘重要之人 |\n",
        encoding="utf-8",
    )
    return chapter, case


def test_l2_04_chapter_evidence_id_passes(tmp_path):
    chapter, case = _setup_case(tmp_path)
    ctx = 构造设定上下文(chapter, _item("仍无具体后果"), repo_root=case, ir_dir=case / "IR")
    parsed = l2_04_v2_payload(ctx)
    errors = 校验设定响应(parsed, ctx, 设定诊断结果("x"))
    assert not errors


def test_l2_04_ir_evidence_id_passes(tmp_path):
    chapter, case = _setup_case(tmp_path)
    ctx = 构造设定上下文(chapter, _item("仍无具体后果"), repo_root=case, ir_dir=case / "IR")
    ir_id = next(eid for eid, e in ctx.证据表.items() if e.source_type == SOURCE_PROJECT_RULE)
    parsed = l2_04_v2_payload(ctx)
    assert ir_id in parsed["setting_pressure_points"][0]["evidence_ids"]
    assert not 校验设定响应(parsed, ctx, 设定诊断结果("x"))


def test_l2_04_rejects_ir_quote_as_chapter(tmp_path):
    chapter, case = _setup_case(tmp_path)
    ctx = 构造设定上下文(chapter, _item("仍无具体后果"), repo_root=case, ir_dir=case / "IR")
    ir_id = next(eid for eid, e in ctx.证据表.items() if e.source_type == SOURCE_PROJECT_RULE)
    ch_id = next(eid for eid, e in ctx.证据表.items() if e.source_type == SOURCE_CHAPTER)
    parsed = l2_04_v2_payload(ctx)
    parsed["evidence_quotes"] = [{"evidence_id": ir_id}]
    parsed["setting_pressure_points"][0]["evidence_ids"] = [ir_id]
    errors = 校验设定响应(parsed, ctx, 设定诊断结果("x"))
    assert any("CHOICE_PRESSURE_NOT_DEMONSTRATED" in e for e in errors)


def test_l2_04_rejects_missing_evidence_id(tmp_path):
    chapter, case = _setup_case(tmp_path)
    ctx = 构造设定上下文(chapter, _item("仍无具体后果"), repo_root=case, ir_dir=case / "IR")
    parsed = l2_04_v2_payload(ctx, bad_evidence_id="EVID-9999")
    errors = 校验设定响应(parsed, ctx, 设定诊断结果("x"))
    assert any("EVIDENCE_ID_INVALID" in e for e in errors)


def test_l2_04_rejects_legacy_free_text(tmp_path):
    chapter, case = _setup_case(tmp_path)
    ctx = 构造设定上下文(chapter, _item("仍无"), repo_root=case, ir_dir=case / "IR")
    parsed = {
        "setting_pressure_points": [
            {"rule_or_setting": "规则", "quote": "自由摘句", "choice_pressure": "迫使角色选择"}
        ],
        "fix_actions": ["x"],
        "acceptance_criteria": ["x"],
        "evidence_quotes": [{"paragraph": 1, "quote": "仍无"}],
    }
    errors = 校验设定响应(parsed, ctx, 设定诊断结果("x"))
    assert any("LEGACY_SETTING_EVIDENCE_UNSUPPORTED_IN_R5C" in e for e in errors)


def test_l2_04_same_quote_different_files_distinct_ids(tmp_path):
    case = tmp_path / "dup"
    chapters = case / "chapters"
    ir = case / "IR"
    chapters.mkdir(parents=True)
    ir.mkdir()
    text = "失去一段记忆。"
    chapter = chapters / "chapter.md"
    chapter.write_text(text, encoding="utf-8")
    (ir / "IR-99.md").write_text(text, encoding="utf-8")
    ctx = 构造设定上下文(chapter, _item("失去"), repo_root=case, ir_dir=ir)
    ids = [eid for eid, e in ctx.证据表.items() if e.quote == text]
    assert len(ids) == 2


def test_l2p007_preflight_indexes_ir_memory_cost(tmp_path):
    pilot = Path(__file__).resolve().parent / "fixtures" / "l2_real_api_pilot"
    case_dir = pilot / "cases" / "L2P-007"
    chapter = case_dir / "chapters" / "chapter.md"
    item = _item("仍无具体后果")
    ctx = 构造设定上下文(chapter, item, repo_root=case_dir, ir_dir=case_dir / "IR")
    assert ctx.indexed_evidence
    assert any("失去一段记忆" in e.get("quote", "") for e in ctx.indexed_evidence)
    assert ctx.response_schema_version == SETTING_RESPONSE_SCHEMA


def test_l2_04_conflict_should_reroute_to_l2_06(tmp_path):
    chapter, case = _setup_case(tmp_path)
    ctx = 构造设定上下文(chapter, _item("仍无"), repo_root=case, ir_dir=case / "IR")
    parsed = l2_04_v2_payload(ctx)
    parsed["root_cause"] = "正文与 IR 硬冲突 source_a 一致性冲突"
    errors = 校验设定响应(parsed, ctx, 设定诊断结果("x"))
    assert any("L2-06" in e or "needs_reroute" in e for e in errors)
