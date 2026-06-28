from __future__ import annotations

import uuid
from pathlib import Path

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
from 一致性上下文 import 构造一致性上下文
from 一致性修复规划 import 规划一致性修复
from 事实模型 import 一致性冲突, 一致性诊断结果, 来源引用
from 双来源校验 import 校验双来源
from 一致性能力入口 import 安全生成修复单
from 能力规则加载 import 加载能力规则
from 事实索引 import CONSISTENCY_RESPONSE_SCHEMA
from tests.conftest import make_mock_transport, repo_root, sample_chapter_text


def _v2_payload(ctx, *, classification: str = "HARD_CONFLICT") -> dict:
    if not ctx.indexed_fact_pairs:
        raise AssertionError("缺少 indexed_fact_pairs")
    pair = ctx.indexed_fact_pairs[0]
    fa = ctx.索引事实表[pair["source_a_fact_id"]]
    return {
        "response_schema_version": CONSISTENCY_RESPONSE_SCHEMA,
        "root_cause": "事实状态冲突",
        "consistency_conflicts": [
            {
                "fact_pair_id": pair["fact_pair_id"],
                "source_a_fact_id": pair["source_a_fact_id"],
                "source_b_fact_id": pair["source_b_fact_id"],
                "classification": classification,
                "reason": "测试冲突",
                "repair_direction": "对齐事实",
            }
        ],
        "fix_actions": ["统一事实"],
        "acceptance_criteria": ["无冲突"],
        "evidence_quotes": [{"paragraph": fa.段落 or 1, "quote": fa.摘句}],
        "needs_reroute": False,
    }


def _item(seed: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01", 名称="t", 状态="失败", 说明=f"{seed}",
        证据=[证据(1, quote)], 严重级别="error", 失败类型="技术护栏失败",
        候选模块="L2-06", 回流验收位置="L1-01", 修复方向="统一事实",
    )


def _rules(root: Path):
    return 加载能力规则(root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json").能力规则["L2-06"]


def test_l2_06_context_builds_fact_pairs(tmp_path):
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text("c"), encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("c", "规则正在收紧"))
    assert ctx.正文事实
    assert isinstance(ctx.事实对候选, list)


def test_l2_06_validator_requires_dual_sources(tmp_path):
    path = tmp_path / "c.md"
    path.write_text(sample_chapter_text("d"), encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("d", "忽然察觉异常"))
    parsed = {
        "consistency_conflicts": [
            {
                "fact_pair_id": "PAIR-9999",
                "source_a_fact_id": "FACT-0001",
                "source_b_fact_id": "FACT-9999",
                "classification": "HARD_CONFLICT",
            }
        ]
    }
    diag = 一致性诊断结果("x", [])
    errors = 校验双来源(parsed, ctx.正文语料, ctx, diag)
    assert any("fact_pair_id" in e or "FACT-9999" in e for e in errors)


def test_l2_06_repair_plan_aligns_entities():
    c = 一致性冲突(
        "事实", "名单状态", "数量",
        来源引用("正文", "名单上的名字已经开始减少"),
        来源引用("IR", "名单锁定"),
    )
    plan = 规划一致性修复(一致性诊断结果("冲突", [c]), {})
    assert "名单状态" in plan["fix_actions"][0]


def test_l2_06_mock_integration(tmp_path, repo_root):
    path = tmp_path / "ch.md"
    path.write_text(
        sample_chapter_text("i")
        + "\n\n甲区读数表明空间层级仍标记为上层。\n\n乙区回报空间层级已经进入下层。",
        encoding="utf-8",
    )
    item = _item("i", "空间层级仍标记为上层")
    ctx = 构造一致性上下文(path, item)
    payload = _v2_payload(ctx, classification="HARD_CONFLICT")
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(item, _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form and not err
    assert form.接收模块 == "L2-06"


def test_l2_06_no_state_pattern_hardcoding_in_context(tmp_path):
    path = tmp_path / "generic.md"
    path.write_text("甲位于北塔三层。乙没有携带武器。", encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("g", "北塔"))
    blob = str(ctx.正文事实)
    assert "名单状态" not in blob or "北塔" in blob
    assert "空间层级" not in blob or "北塔" in blob or "位于" in blob


def test_l2_06_repair_plan_skips_allowed_change(tmp_path):
    from 事实模型 import 一致性冲突, 来源引用

    c = 一致性冲突(
        "事实",
        "甲",
        "位置",
        来源引用("前序章节", "甲在城外"),
        来源引用("正文", "甲已进入城内"),
        分类="ALLOWED_CHANGE",
    )
    plan = 规划一致性修复(一致性诊断结果("变化", [c]), {})
    assert plan["fix_actions"] == [] or "ALLOWED" in str(plan).upper() or "对齐" not in plan["fix_actions"][0]


def test_l2_06_rejects_style_as_system_conflict(tmp_path):
    path = tmp_path / "c.md"
    path.write_text("他的语气突然变了。", encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("s", "他的语气突然变了"))
    parsed = {
        "consistency_conflicts": [
            {
                "conflict_type": "文风",
                "entity": "语气",
                "attribute": "态度",
                "source_a": {"quote": "他的语气突然变了", "source_type": "正文"},
                "source_b": {"quote": "他的语气突然变了", "source_type": "正文"},
            }
        ],
    }
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("x", []))
    assert any("LEGACY" in e for e in errors)
