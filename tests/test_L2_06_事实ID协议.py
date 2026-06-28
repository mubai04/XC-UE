from __future__ import annotations

from 一致性上下文 import 构造一致性上下文
from 事实索引 import CONSISTENCY_RESPONSE_SCHEMA
from 双来源校验 import 校验双来源
from L2模型 import 失败输入, 证据
from 事实模型 import 一致性诊断结果
from tests.conftest import sample_chapter_text


def _item(quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="t",
        状态="失败",
        说明="id",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型="技术护栏失败",
        候选模块="L2-06",
        回流验收位置="L1-01",
        修复方向="统一事实",
    )


def test_l2_06_indexed_facts_have_stable_ids(tmp_path):
    text = sample_chapter_text("f") + "\n\n甲位于北塔。乙位于南塔。"
    path = tmp_path / "ch.md"
    path.write_text(text, encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("北塔"))
    assert ctx.indexed_facts
    assert ctx.indexed_facts[0]["fact_id"] == "FACT-0001"
    assert ctx.response_schema_version == CONSISTENCY_RESPONSE_SCHEMA


def test_l2_06_rejects_legacy_free_text_response(tmp_path):
    path = tmp_path / "c.md"
    path.write_text(sample_chapter_text("l"), encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("规则正在收紧"))
    parsed = {
        "consistency_conflicts": [
            {
                "entity": "甲",
                "attribute": "位置",
                "source_a": {"quote": "x", "source_type": "正文"},
                "source_b": {"quote": "y", "source_type": "正文"},
            }
        ]
    }
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("x", []))
    assert any("LEGACY_RESPONSE_UNSUPPORTED" in e for e in errors)


def test_l2_06_id_binding_rejects_swapped_facts(tmp_path):
    text = "林泽在城北货栈。林泽在城南码头。"
    path = tmp_path / "ch.md"
    path.write_text(text, encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("林泽"))
    if not ctx.indexed_fact_pairs:
        return
    pair = ctx.indexed_fact_pairs[0]
    parsed = {
        "consistency_conflicts": [
            {
                "fact_pair_id": pair["fact_pair_id"],
                "source_a_fact_id": pair["source_b_fact_id"],
                "source_b_fact_id": pair["source_a_fact_id"],
                "classification": "HARD_CONFLICT",
                "reason": "测试",
            }
        ]
    }
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("x", []))
    assert any("不匹配" in e for e in errors)
