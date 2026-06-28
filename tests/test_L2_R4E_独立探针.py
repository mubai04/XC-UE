"""R4E 独立探针与变形测试 — 不得调用真实 API。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from L2模型 import 失败输入, 证据
from 一致性上下文 import 构造一致性上下文
from 冲突比对 import 复核冲突分类, 执行冲突比对
from 双来源校验 import 校验双来源
from 事实模型 import 一致性诊断结果
from 前序章节 import 解析前序章节, 解析前序章节错误
from 文风上下文 import 构造文风上下文
from 文风证据校验 import 校验文风响应
from 文风模型 import 文风诊断结果
from 角色上下文 import 构造角色上下文
from 设定上下文 import 构造设定上下文
from 阅读阶段上下文 import 构造阅读阶段上下文
from 领域证据 import 识别对话证据


def _item(module: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="R4E",
        状态="失败",
        说明="R4E independent probe",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型="R4E探针",
        候选模块=module,
        回流验收位置="L1-01",
        修复方向="定向修复",
    )


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "sentence,expected_speaker",
    [
        ("赵衡低声问：“还走吗？”", "赵衡"),
        ("赵衡冷冷地说道：“立刻离开。”", "赵衡"),
        ("“再等等。”赵衡压低声音回答。", "赵衡"),
        ("赵衡笑着问道：“你确定？”", "赵衡"),
    ],
)
def test_l2_02_manner_speech_explicit(sentence: str, expected_speaker: str):
    ev = 识别对话证据(sentence)
    assert ev.get("speaker") == expected_speaker
    assert ev.get("speaker_confidence") == "EXPLICIT"
    assert ev.get("speech_verb")


@pytest.mark.parametrize(
    "sentence",
    [
        "赵衡看见陆舟低声问守卫。",
        "门外有人低声说话。",
        "他似乎听见赵衡的声音。",
    ],
)
def test_l2_02_manner_speech_not_misidentified(sentence: str):
    ev = 识别对话证据(sentence)
    assert ev.get("speaker_confidence") != "EXPLICIT" or ev.get("speaker") is None


def test_l2_02_probe_dual_tone_same_character(tmp_path):
    body = (
        "周砚说：“立刻撤离。”\n\n"
        "周砚低声问：“还能再等一刻吗？”\n\n"
        "陆遥说：“谁也不准离开。”"
    )
    path = _write(tmp_path / "tone.md", body)
    ctx = 构造文风上下文(path, _item("L2-02", "周砚"))
    ready = [
        c
        for c in ctx.语气比较候选
        if c.get("character") == "周砚" and c.get("status") == "dual_source_ready"
    ]
    assert ready
    cross = {
        "root_cause": "语气",
        "style_issues": [{
            "issue_type": "人物语气漂移",
            "character": "周砚",
            "source_a": {"paragraph": 1, "quote": "周砚说：“立刻撤离。”"},
            "source_b": {"paragraph": 3, "quote": "陆遥说：“谁也不准离开。”"},
        }],
        "fix_actions": ["x"],
        "acceptance_criteria": ["x"],
        "evidence_quotes": [{"paragraph": 1, "quote": "周砚说：“立刻撤离。”"}],
        "forbid_modify_scope": "事件顺序、人物目标、世界规则",
    }
    assert 校验文风响应(cross, ctx.正文语料, 文风诊断结果("x", []))


def test_l2_02_variant_cold_speech(tmp_path):
    body = "沈默冷冷地说道：“别动。”\n\n沈默沉声问：“谁在那里？”"
    path = _write(tmp_path / "v.md", body)
    ctx = 构造文风上下文(path, _item("L2-02", "沈默"))
    ready = [c for c in ctx.语气比较候选 if c.get("character") == "沈默" and c.get("status") == "dual_source_ready"]
    assert ready


def test_l2_03_probe_character_event_separation(tmp_path):
    body = (
        "程野决心找回药箱。\n"
        "警铃响起，程野撞开侧门冲进库房。\n"
        "许棠准备护送伤员离开。\n"
        "吊灯坠落，许棠推开伤员，自己被碎片划伤。"
    )
    path = _write(tmp_path / "psy.md", body)
    ctx = 构造角色上下文(path, _item("L2-03", "程野"))
    confirmed = {r["name"] for r in ctx.识别角色 if r.get("confirmed")}
    assert confirmed <= {"程野", "许棠"}
    chain_names = {c["character"] for c in ctx.目标刺激行为链}
    assert chain_names <= {"程野", "许棠"}
    assert any("警铃" in e.quote or "响起" in e.quote for e in ctx.环境事件表)
    assert any("吊灯" in e.quote or "坠落" in e.quote for e in ctx.环境事件表)
    xu = next(c for c in ctx.目标刺激行为链 if c["character"] == "许棠")
    goal = xu.get("goal") or xu.get("goal_evidence") or ""
    assert goal == "护送伤员离开" or ("护送" in goal and "许棠准备" not in goal)
    assert "推开" in (xu.get("behavior") or xu.get("behavior_evidence") or "")
    assert "划伤" in (xu.get("result") or xu.get("result_evidence") or "")


def test_l2_03_variant_alert_beam(tmp_path):
    body = (
        "方遥决心取回印章。\n"
        "警报响起，方遥撞开侧门冲进库房。\n"
        "秦晚准备护送伤员离开。\n"
        "横梁坠落，秦晚推开伤员，自己被碎片划伤。"
    )
    path = _write(tmp_path / "v.md", body)
    ctx = 构造角色上下文(path, _item("L2-03", "方遥"))
    chain_names = {c["character"] for c in ctx.目标刺激行为链}
    assert chain_names <= {"方遥", "秦晚"}
    assert any("警报" in e.quote or "横梁" in e.quote for e in ctx.环境事件表)


def test_l2_03_no_confirmed_characters_empty_chains(tmp_path):
    body = "警铃响起。门突然关闭。火焰蔓延。"
    path = _write(tmp_path / "empty.md", body)
    ctx = 构造角色上下文(path, _item("L2-03", "警铃"))
    assert ctx.目标刺激行为链 == []


def test_l2_04_probe_only_cai_with_subject(tmp_path):
    body = (
        "若佩戴青环，伤口就会停止流血。\n"
        "一旦青环破裂，佩戴者会失去最近一小时的记忆。\n"
        "只有交出通行牌，守门人才允许进入内城。"
    )
    path = _write(tmp_path / "set.md", body)
    ctx = 构造设定上下文(path, _item("L2-04", "青环"))
    assert ctx.限制表
    lim = next(l for l in ctx.限制表 if "只有" in l.描述 or l.前置条件)
    assert "通行牌" in lim.前置条件 or "交出" in lim.前置条件


def test_l2_04_only_comma_subject_cai(tmp_path):
    body = "只有修为达到三境，弟子才可下山。"
    path = _write(tmp_path / "m.md", body)
    ctx = 构造设定上下文(path, _item("L2-04", "修为"))
    lim = ctx.限制表[0]
    assert "三境" in lim.前置条件 or "修为" in lim.前置条件


def test_l2_04_variant_seal_archive(tmp_path):
    body = "只有呈上印章，守卫才允许进入藏书楼。"
    path = _write(tmp_path / "v.md", body)
    ctx = 构造设定上下文(path, _item("L2-04", "印章"))
    assert ctx.限制表


def test_l2_04_only_one_person_not_limit(tmp_path):
    body = "只有一个人来了。"
    path = _write(tmp_path / "q.md", body)
    ctx = 构造设定上下文(path, _item("L2-04", "人"))
    assert not any(getattr(l, "constraint_type", "") == "REQUIRED_CONDITION" for l in ctx.限制表)


def _market_body(prefix: str = "顾临") -> str:
    return (
        f"地下仓库突然断电，{prefix}被锁在冷藏室。\n\n"
        "广播通知北梯关闭。\n\n"
        "巡逻员又说北梯已经关闭。\n\n"
        f"{prefix}在工具箱里找到一张备用门卡。\n\n"
        f"他准备刷卡时，门外传来妹妹的求救声。"
    )


def test_l2_05_probe_item_and_repeat(tmp_path):
    path = _write(tmp_path / "mkt.md", _market_body())
    ctx = 构造阅读阶段上下文(path, _item("L2-05", "顾临"))
    items = [r for r in ctx.即时收益列表 if r.reward_type == "ITEM"]
    assert items
    assert any(r.段落 >= 4 for r in items)
    assert ctx.重复信息列表
    assert "北梯" in ctx.重复信息列表[0].短语


def test_l2_05_repeat_variant_announce_guard(tmp_path):
    body = "公告通知西门封锁。\n\n守卫又说西门已经封锁。"
    path = _write(tmp_path / "r.md", body)
    ctx = 构造阅读阶段上下文(path, _item("L2-05", "西门"))
    assert ctx.重复信息列表
    assert "西门" in ctx.重复信息列表[0].短语


def test_l2_05_not_repeat_different_facts(tmp_path):
    body = "广播通知北梯关闭。\n\n广播通知北梯发生爆炸。"
    path = _write(tmp_path / "nr.md", body)
    ctx = 构造阅读阶段上下文(path, _item("L2-05", "北梯"))
    assert not any("关闭" in r.短语 and "爆炸" in r.短语 for r in ctx.重复信息列表)


def _prior_harness(tmp_path: Path, ch00: str, ch01: str) -> tuple[Path, list[Path]]:
    harness = tmp_path / "h"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    ch00p = chapters / "ch00.md"
    ch01p = chapters / "ch01.md"
    ch00p.write_text(ch00, encoding="utf-8")
    ch01p.write_text(ch01, encoding="utf-8")
    (harness / "project.json").write_text(
        json.dumps({
            "schema_version": "xcue.project-manifest/1.0",
            "content_root": "chapters",
            "chapter_sequence": ["chapters/ch00.md", "chapters/ch01.md"],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return ch01p, 解析前序章节(ch01p)


def test_l2_06_probe_time_bridge_allowed_change(tmp_path):
    ch01, priors = _prior_harness(
        tmp_path,
        "清晨，周砚仍在北岸。",
        "傍晚，周砚乘船抵达南岸。",
    )
    ctx = 构造一致性上下文(ch01, _item("L2-06", "南岸"), prior_chapters=priors)
    reviewed = 复核冲突分类(
        ctx,
        entity="周砚",
        attribute="位置",
        classification="HARD_CONFLICT",
        source_a={"source_type": "前序章节", "quote": "清晨，周砚仍在北岸。", "paragraph": 1},
        source_b={"source_type": "正文", "quote": "傍晚，周砚乘船抵达南岸。", "paragraph": 1},
    )
    assert reviewed == "ALLOWED_CHANGE"


def test_l2_06_probe_no_bridge_explanation(tmp_path):
    ch01, priors = _prior_harness(tmp_path, "周砚在北岸。", "周砚在南岸。")
    ctx = 构造一致性上下文(ch01, _item("L2-06", "南岸"), prior_chapters=priors)
    reviewed = 复核冲突分类(
        ctx,
        entity="周砚",
        attribute="位置",
        classification="HARD_CONFLICT",
        source_a={"source_type": "前序章节", "quote": "周砚在北岸。", "paragraph": 1},
        source_b={"source_type": "正文", "quote": "周砚在南岸。", "paragraph": 1},
    )
    assert reviewed == "EXPLANATION_INSUFFICIENT"


def test_l2_06_variant_foot_hill(tmp_path):
    ch01, priors = _prior_harness(
        tmp_path,
        "清晨，方遥仍在山脚。",
        "傍晚，方遥乘船抵达山顶。",
    )
    ctx = 构造一致性上下文(ch01, _item("L2-06", "山顶"), prior_chapters=priors)
    reviewed = 复核冲突分类(
        ctx,
        entity="方遥",
        attribute="位置",
        classification="HARD_CONFLICT",
        source_a={"source_type": "前序章节", "quote": "清晨，方遥仍在山脚。", "paragraph": 1},
        source_b={"source_type": "正文", "quote": "傍晚，方遥乘船抵达山顶。", "paragraph": 1},
    )
    assert reviewed == "ALLOWED_CHANGE"


def test_l2_06_pipeline_applies_review(tmp_path):
    from DeepSeek客户端 import create_client
    from tests.conftest import l2_06_v2_payload, make_mock_transport

    ch01, priors = _prior_harness(
        tmp_path,
        "清晨，周砚仍在北岸。",
        "傍晚，周砚乘船抵达南岸。",
    )
    ctx = 构造一致性上下文(ch01, _item("L2-06", "南岸"), prior_chapters=priors)
    payload = l2_06_v2_payload(ctx, classification="HARD_CONFLICT")
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    parsed, diagnosis = 执行冲突比对(ctx, _item("L2-06", "南岸"), client=client)
    assert diagnosis.consistency_conflicts[0].分类 == "ALLOWED_CHANGE"
    assert parsed["consistency_conflicts"][0]["classification"] == "ALLOWED_CHANGE"
