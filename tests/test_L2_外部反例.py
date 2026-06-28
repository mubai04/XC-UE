"""R4D 外部窄查反例固化测试 — 不得调用真实 API。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from L2模型 import 失败输入, 证据
from 一致性上下文 import 构造一致性上下文
from 双来源校验 import 校验双来源
from 冲突比对 import 复核冲突分类
from 事实模型 import 一致性诊断结果
from 前序章节 import 解析前序章节, 解析前序章节错误
from 文风上下文 import 构造文风上下文
from 文风证据校验 import 校验文风响应
from 文风模型 import 文风诊断结果
from 角色上下文 import 构造角色上下文
from 设定上下文 import 构造设定上下文
from 阅读阶段上下文 import 构造阅读阶段上下文

from tests.conftest import l2_06_v2_payload, repo_root


def _item(module: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="R4D",
        状态="失败",
        说明="R4D external counterexample",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型="外部反例",
        候选模块=module,
        回流验收位置="L1-01",
        修复方向="定向修复",
    )


# --- L2-02 ---


def test_l2_02_rejects_tone_drift_from_different_speakers(tmp_path):
    q1 = "李四说：“今晚就走。”"
    q2 = "王五说：“我绝不离开。”"
    path = tmp_path / "tone.md"
    path.write_text(f"{q1}\n\n{q2}", encoding="utf-8")
    ctx = 构造文风上下文(path, _item("L2-02", q1))
    parsed = {
        "root_cause": "语气",
        "style_issues": [
            {
                "issue_type": "人物语气漂移",
                "character": "张三",
                "source_a": {"paragraph": 1, "quote": q1},
                "source_b": {"paragraph": 2, "quote": q2},
                "difference": "语气不一致",
            }
        ],
        "fix_actions": ["统一语气"],
        "acceptance_criteria": ["可核对"],
        "evidence_quotes": [{"paragraph": 1, "quote": q1}],
        "forbid_modify_scope": "事件顺序、人物目标、世界规则",
    }
    errors = 校验文风响应(parsed, ctx.正文语料, 文风诊断结果("语气", []))
    assert errors
    assert any("说话人" in e or "人物" in e or "speaker" in e.lower() for e in errors)


def test_l2_02_rejects_same_sentence_dual_source(tmp_path):
    q = "张三说：“快走。”"
    path = tmp_path / "same.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造文风上下文(path, _item("L2-02", q))
    parsed = {
        "root_cause": "语气",
        "style_issues": [
            {
                "issue_type": "人物语气漂移",
                "character": "张三",
                "source_a": {"paragraph": 1, "quote": q},
                "source_b": {"paragraph": 1, "quote": q},
            }
        ],
        "fix_actions": ["统一语气"],
        "acceptance_criteria": ["可核对"],
        "evidence_quotes": [{"paragraph": 1, "quote": q}],
        "forbid_modify_scope": "事件顺序、人物目标、世界规则",
    }
    errors = 校验文风响应(parsed, ctx.正文语料, 文风诊断结果("语气", []))
    assert errors


def test_l2_02_accepts_same_character_dual_tone(tmp_path):
    q1 = "张三说：“快走。”"
    q2 = "张三问：“你们还在犹豫什么？”"
    path = tmp_path / "dual.md"
    path.write_text(f"{q1}\n\n{q2}", encoding="utf-8")
    ctx = 构造文风上下文(path, _item("L2-02", q1))
    ready = [c for c in ctx.语气比较候选 if c.get("status") == "dual_source_ready" and c.get("character") == "张三"]
    assert ready
    parsed = {
        "root_cause": "语气",
        "style_issues": [
            {
                "issue_type": "人物语气漂移",
                "character": "张三",
                "source_a": {"paragraph": 1, "quote": q1},
                "source_b": {"paragraph": 2, "quote": q2},
                "difference": "命令与疑问语气",
            }
        ],
        "fix_actions": ["统一张三语气"],
        "acceptance_criteria": ["可核对"],
        "evidence_quotes": [{"paragraph": 1, "quote": q1}],
        "forbid_modify_scope": "事件顺序、人物目标、世界规则",
    }
    errors = 校验文风响应(parsed, ctx.正文语料, 文风诊断结果("语气", []))
    assert not any("说话人" in e or "同句" in e for e in errors)


# --- L2-03 ---


def test_l2_03_dual_character_chains_no_crosswire(tmp_path):
    body = (
        "叶青想夺回账本。\n"
        "火门突然炸开，叶青翻窗躲开。\n"
        "苏晚想逃出地牢。\n"
        "守卫逼近，苏晚受伤倒地。"
    )
    path = tmp_path / "psy.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造角色上下文(path, _item("L2-03", "叶青"))
    names = {c["character"] for c in ctx.目标刺激行为链}
    assert names == {"叶青", "苏晚"}
    ye = next(c for c in ctx.目标刺激行为链 if c["character"] == "叶青")
    su = next(c for c in ctx.目标刺激行为链 if c["character"] == "苏晚")
    assert "夺回账本" in (ye.get("goal_evidence") or ye.get("goal") or "")
    assert "翻窗躲开" in (ye.get("behavior_evidence") or ye.get("behavior") or "")
    assert "逃出地牢" in (su.get("goal_evidence") or su.get("goal") or "")
    stim = su.get("stimulus_evidence") or su.get("stimulus") or ""
    assert "守卫逼近" in stim
    res = su.get("result_evidence") or su.get("result") or ""
    assert "受伤倒地" in res
    ye_res = ye.get("result_evidence") or ye.get("result") or ""
    assert "受伤倒地" not in ye_res or "叶青" in ye_res


def test_l2_03_guchuan_shi_trim_not_character(tmp_path):
    body = "顾川誓要带弟弟离开矿城。"
    path = tmp_path / "trim.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造角色上下文(path, _item("L2-03", body))
    names = [r["name"] for r in ctx.识别角色 if r.get("confirmed")]
    assert "顾川誓" not in names
    assert "顾川" in names


def test_l2_03_event_sentence_not_character(tmp_path):
    body = "火门突然炸开"
    path = tmp_path / "event.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造角色上下文(path, _item("L2-03", body))
    confirmed = [r["name"] for r in ctx.识别角色 if r.get("confirmed")]
    assert not confirmed


# --- L2-04 ---


def test_l2_04_fan_rule_pattern(tmp_path):
    q = "凡触碰银镜者，影子会先一步行动。"
    path = tmp_path / "rule_fan.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造设定上下文(path, _item("L2-04", q))
    assert ctx.规则表
    rule = ctx.规则表[0]
    assert "凡" in rule.触发条件 or "触碰" in rule.触发条件
    assert rule.quote == q


def test_l2_04_once_rule_pattern(tmp_path):
    q = "一旦点燃黑烛，门就会关闭。"
    path = tmp_path / "rule_once.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造设定上下文(path, _item("L2-04", q))
    assert ctx.规则表
    assert any("一旦" in r.触发条件 or "点燃" in r.触发条件 for r in ctx.规则表)


def test_l2_04_each_cost_forget_pattern(tmp_path):
    q = "每次借用镜术，施术者都会忘记一个人的名字。"
    path = tmp_path / "cost.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造设定上下文(path, _item("L2-04", q))
    assert ctx.代价表
    assert any("忘记" in c.描述 for c in ctx.代价表)
    assert ctx.规则表 or ctx.代价表


def test_l2_04_unless_limit_pattern(tmp_path):
    q = "除非献上一枚旧币，否则无法离开镜室。"
    path = tmp_path / "limit.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造设定上下文(path, _item("L2-04", q))
    assert ctx.限制表
    desc = ctx.限制表[0].描述
    assert "无法离开" in desc or "除非" in desc


# --- L2-05 ---


def test_l2_05_item_reward_from_mo_chu(tmp_path):
    q = "沈砚从尸体衣袋摸出一把黄铜钥匙。"
    path = tmp_path / "reward.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造阅读阶段上下文(path, _item("L2-05", q))
    rewards = ctx.即时收益列表
    assert rewards
    item_rewards = [r for r in rewards if getattr(r, "reward_type", None) == "ITEM" or "钥匙" in r.摘句]
    assert item_rewards


def test_l2_05_repeat_info_same_core_statement(tmp_path):
    body = "广播说东门封锁。\n守卫再次说东门封锁。"
    path = tmp_path / "repeat.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造阅读阶段上下文(path, _item("L2-05", body))
    repeats = ctx.重复信息列表
    assert repeats
    assert any("东门封锁" in (r.短语 or "") for r in repeats)


def test_l2_05_similar_words_not_repeat(tmp_path):
    body = "他推开门。\n他说出门要小心。"
    path = tmp_path / "norepeat.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造阅读阶段上下文(path, _item("L2-05", body))
    cores = [r.短语 for r in ctx.重复信息列表]
    assert not any(c in ("门", "说", "他") for c in cores)


# --- L2-06 ---


def test_l2_06_rejects_prior_path_escape(tmp_path):
    harness = tmp_path / "harness"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("外部内容", encoding="utf-8")
    ch01 = chapters / "ch01.md"
    ch01.write_text("本章。", encoding="utf-8")
    manifest = {
        "schema_version": "xcue.project-manifest/1.0",
        "content_root": "chapters",
        "chapter_sequence": ["../outside.md", "chapters/ch01.md"],
    }
    (harness / "project.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    errors = 解析前序章节错误(ch01)
    assert any("PRIOR_CHAPTER_PATH_OUT_OF_SCOPE" in e for e in errors)
    priors = 解析前序章节(ch01)
    assert not any(p.resolve() == outside.resolve() for p in priors)


def test_l2_06_negation_single_fact(tmp_path):
    q = "顾川不是守门人。"
    path = tmp_path / "neg.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("L2-06", q))
    identity_facts = [f for f in ctx.正文事实 if f.实体 == "顾川" and "身份" in f.属性 or f.属性 == "身份"]
    assert len(identity_facts) == 1
    assert identity_facts[0].否定
    assert identity_facts[0].值 == "守门人"
    assert not any(f.实体.endswith("不") for f in ctx.正文事实)


def test_l2_06_allowed_change_with_time_bridge(tmp_path):
    harness = tmp_path / "h"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    ch00 = chapters / "ch00.md"
    ch01 = chapters / "ch01.md"
    ch00.write_text("清晨，顾川还在城外。", encoding="utf-8")
    ch01.write_text("入夜后，顾川已经进入城内。", encoding="utf-8")
    (harness / "project.json").write_text(
        json.dumps(
            {
                "schema_version": "xcue.project-manifest/1.0",
                "content_root": "chapters",
                "chapter_sequence": ["chapters/ch00.md", "chapters/ch01.md"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    priors = 解析前序章节(ch01)
    ctx = 构造一致性上下文(ch01, _item("L2-06", "城内"), prior_chapters=priors)
    reviewed = 复核冲突分类(
        ctx,
        entity="顾川",
        attribute="位置",
        classification="HARD_CONFLICT",
        source_a={"source_type": "前序章节", "quote": "清晨，顾川还在城外。", "paragraph": 1},
        source_b={"source_type": "正文", "quote": "入夜后，顾川已经进入城内。", "paragraph": 1},
    )
    assert reviewed == "ALLOWED_CHANGE"


def test_l2_06_explanation_insufficient_without_bridge(tmp_path):
    harness = tmp_path / "h2"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    ch00 = chapters / "ch00.md"
    ch01 = chapters / "ch01.md"
    ch00.write_text("顾川还在城外。", encoding="utf-8")
    ch01.write_text("顾川已经进入城内。", encoding="utf-8")
    (harness / "project.json").write_text(
        json.dumps(
            {
                "schema_version": "xcue.project-manifest/1.0",
                "content_root": "chapters",
                "chapter_sequence": ["chapters/ch00.md", "chapters/ch01.md"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    priors = 解析前序章节(ch01)
    ctx = 构造一致性上下文(ch01, _item("L2-06", "城内"), prior_chapters=priors)
    reviewed = 复核冲突分类(
        ctx,
        entity="顾川",
        attribute="位置",
        classification="HARD_CONFLICT",
        source_a={"source_type": "前序章节", "quote": "顾川还在城外。", "paragraph": 1},
        source_b={"source_type": "正文", "quote": "顾川已经进入城内。", "paragraph": 1},
    )
    assert reviewed == "EXPLANATION_INSUFFICIENT"


def test_l2_06_rejects_wrong_entity_source_binding(tmp_path):
    body = "顾川不是守门人。李四在城内。"
    path = tmp_path / "bind.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("L2-06", "守门人"))
    if not ctx.indexed_fact_pairs:
        pytest.skip("未生成事实对")
    parsed = l2_06_v2_payload(ctx, swap_ids=True)
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("x", []))
    assert errors
    assert any("不匹配" in e for e in errors)


def test_l2_06_evidence_insufficient_allows_missing_source_b(tmp_path):
    q = "只有一句孤立陈述。"
    path = tmp_path / "insuf.md"
    path.write_text(q, encoding="utf-8")
    ctx = 构造一致性上下文(path, _item("L2-06", q))
    parsed = l2_06_v2_payload(
        ctx,
        classification="EVIDENCE_INSUFFICIENT",
        reason="缺少第二来源对照",
    )
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("x", []))
    assert not errors


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="平台不支持 symlink")
def test_l2_06_rejects_symlink_escape(tmp_path):
    harness = tmp_path / "h3"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    outside = tmp_path / "secret.md"
    outside.write_text("秘密", encoding="utf-8")
    link = chapters / "evil.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation blocked")
    ch01 = chapters / "ch01.md"
    ch01.write_text("本章。", encoding="utf-8")
    (harness / "project.json").write_text(
        json.dumps(
            {
                "schema_version": "xcue.project-manifest/1.0",
                "content_root": "chapters",
                "chapter_sequence": ["chapters/evil.md", "chapters/ch01.md"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    errors = 解析前序章节错误(ch01)
    assert any("PRIOR_CHAPTER_PATH_OUT_OF_SCOPE" in e for e in errors)
