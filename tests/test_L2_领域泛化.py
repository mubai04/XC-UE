from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from L2模型 import 失败输入, 证据
from 一致性上下文 import 构造一致性上下文
from 双来源校验 import 校验双来源
from 事实模型 import 一致性诊断结果, 事实声明
from 文风上下文 import 构造文风上下文
from 文风模型 import 文风诊断结果, 文风问题
from 文风证据校验 import 校验文风响应
from 角色上下文 import 构造角色上下文
from 设定上下文 import 构造设定上下文
from 阅读阶段上下文 import 构造阅读阶段上下文

# 与 test_l2_no_fixture_hardcoding 对齐：只禁止「生产注入默认值」，不禁止探针正文用词
_INJECTED_DEFAULT_FORBIDDEN = (
    "生存/达成目标",
    "规则正在收紧",
    "审查/层级规则",
    "触发异常或违规则生效",
    "违规则名单减少或承担后果",
    "名字减少意味着淘汰",
)


def _item(module: str, failure_type: str, quote: str = "x") -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="泛化探针",
        状态="失败",
        说明="R4C domain probe",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型=failure_type,
        候选模块=module,
        回流验收位置="L1-01",
        修复方向="修复",
    )


_NAME_POOL = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"


def _rand_label(prefix: str = "") -> str:
    seed = int(uuid.uuid4().hex[:6], 16)
    a = _NAME_POOL[seed % len(_NAME_POOL)]
    b = _NAME_POOL[(seed // len(_NAME_POOL)) % len(_NAME_POOL)]
    return f"{prefix}{a}{b}" if prefix else f"{a}{b}"


def _assert_no_injected_defaults(blob: str) -> None:
    for forbidden in _INJECTED_DEFAULT_FORBIDDEN:
        assert forbidden not in blob, f"提取结果不得含旧硬编码：{forbidden}"


def _fact_quote(fact: 事实声明) -> str:
    return (getattr(fact, "quote", None) or fact.摘句 or "").strip()


# --- A. L2-02 语气双来源 / 单来源 / 同句拒绝 ---


def _dual_tone_body(speaker: str) -> str:
    return (
        f"{speaker}说：今晚必须走，不能再等。\n\n"
        f"{speaker}问：你们还打算在这里耗到什么时候？"
    )


def test_probe_a_l2_02_dual_source_tone_candidate(tmp_path):
    speaker = _rand_label()
    text = _dual_tone_body(speaker)
    path = tmp_path / "tone_dual.md"
    path.write_text(text, encoding="utf-8")
    ctx = 构造文风上下文(path, _item("L2-02", "文风失败", text.split("，")[0]))

    ready = [c for c in ctx.语气比较候选 if c.get("status") == "dual_source_ready"]
    assert ready, "同一说话人两处发言应形成 dual_source_ready"
    sample = next(c for c in ready if c.get("character") == speaker)
    sa, sb = sample["source_a"], sample["source_b"]
    assert sa["quote"] != sb["quote"]
    assert sa["quote"] in text and sb["quote"] in text
    assert (sa["paragraph"], sa.get("sentence")) != (sb["paragraph"], sb.get("sentence"))


def test_probe_a_l2_02_single_source_evidence_insufficient(tmp_path):
    speaker = _rand_label()
    line = f"{speaker}说：我先走了，别拦我。"
    path = tmp_path / "tone_single.md"
    path.write_text(line, encoding="utf-8")
    ctx = 构造文风上下文(path, _item("L2-02", "文风失败", "我先走了"))

    hits = [c for c in ctx.语气比较候选 if c.get("character") == speaker]
    assert hits, "应识别说话人"
    assert all(c.get("status") == "evidence_insufficient" for c in hits)
    assert all(c.get("source_b") is None for c in hits)


def test_probe_a_l2_02_same_sentence_dual_source_rejected(tmp_path):
    speaker = _rand_label()
    quote = f"{speaker}说：同一句话。"
    path = tmp_path / "tone_same.md"
    path.write_text(quote, encoding="utf-8")
    ctx = 构造文风上下文(path, _item("L2-02", "文风失败", quote))
    parsed = {
        "root_cause": "语气漂移",
        "style_issues": [
            {
                "issue_type": "人物语气漂移",
                "character": speaker,
                "source_a": {"paragraph": 1, "quote": quote},
                "source_b": {"paragraph": 1, "quote": quote},
                "difference": "语气不一致",
            }
        ],
        "fix_actions": [f"统一{speaker}两处语气"],
        "acceptance_criteria": ["两处语气可区分又一致"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "forbid_modify_scope": "事件顺序、人物目标、世界规则",
    }
    diag = 文风诊断结果("语气", [文风问题("人物语气漂移", 1, 1, quote, "统一语气")])
    errors = 校验文风响应(parsed, ctx.正文语料, diag)
    assert errors, "同句同位置双来源应被拒绝"


# --- B. L2-03 动机链 ---


def _make_psych_body(
    hero: str,
    *,
    goal_tail: str,
    stim_clause: str,
    act: str,
    block_clause: str,
    pay_act: str,
) -> str:
    return f"{hero}{goal_tail}。{stim_clause}，{hero}{act}。{block_clause}，他{pay_act}。"


def _assert_psychology_chain(ctx, hero: str, body: str) -> None:
    blob = json.dumps(
        {"chains": ctx.目标刺激行为链, "states": [s.__dict__ for s in ctx.角色状态表]},
        ensure_ascii=False,
    )
    _assert_no_injected_defaults(blob)

    confirmed = {r.get("name") for r in ctx.识别角色 if r.get("confirmed")}
    assert hero in confirmed

    chain = next((c for c in ctx.目标刺激行为链 if c.get("character") == hero), None)
    assert chain

    goal_ev = (chain.get("goal_evidence") or chain.get("goal") or "").strip()
    stim_ev = (chain.get("stimulus_evidence") or chain.get("stimulus") or "").strip()
    beh_ev = (chain.get("behavior_evidence") or chain.get("behavior") or "").strip()

    for label, ev in (("goal", goal_ev), ("stimulus", stim_ev), ("behavior", beh_ev)):
        assert ev and ev in body, f"{label} 证据必须是正文子串"
    assert goal_ev != beh_ev


def test_probe_b_l2_03_motivation_chain_from_body(tmp_path):
    hero = _rand_label()
    body = _make_psych_body(
        hero,
        goal_tail="想救妹妹",
        stim_clause="钟声响起后",
        act="冲向城门",
        block_clause="守卫拦住他",
        pay_act="交出玉佩",
    )
    path = tmp_path / "psych_a.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造角色上下文(path, _item("L2-03", "角色失败", body[:12]))
    _assert_psychology_chain(ctx, hero, body)


def test_probe_b_l2_03_motivation_chain_variant(tmp_path):
    hero = _rand_label()
    body = _make_psych_body(
        hero,
        goal_tail="想夺回信物",
        stim_clause="号炮齐响后",
        act="奔向关隘",
        block_clause="敌哨拦住他",
        pay_act="弃下马鞍",
    )
    path = tmp_path / "psych_b.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造角色上下文(path, _item("L2-03", "角色失败", body[:12]))
    _assert_psychology_chain(ctx, hero, body)


# --- C. L2-04 设定 ---


def _make_setting_body(technique: str, *, cost_clause: str, limit_clause: str) -> str:
    return f"每次施展{technique}，{cost_clause}。{limit_clause}。"


def _setting_quote(item) -> str:
    return (
        getattr(item, "quote", "")
        or getattr(item, "摘句", "")
        or getattr(item, "描述", "")
        or getattr(item, "触发条件", "")
        or ""
    ).strip()


def _assert_setting_extraction(ctx, body: str) -> None:
    blob = json.dumps(
        {
            "rules": [r.__dict__ for r in ctx.规则表],
            "limits": [l.__dict__ for l in ctx.限制表],
            "costs": [c.__dict__ for c in ctx.代价表],
        },
        ensure_ascii=False,
    )
    _assert_no_injected_defaults(blob)

    extracted = ctx.规则表 + ctx.限制表 + ctx.代价表
    assert extracted

    quotes = [_setting_quote(x) for x in extracted if _setting_quote(x)]
    assert quotes
    assert all(q in body for q in quotes)


def test_probe_c_l2_04_setting_extraction_variant_a(tmp_path):
    technique = f"术式{uuid.uuid4().hex[:4]}"
    body = _make_setting_body(
        technique,
        cost_clause="施术者都会失去一天记忆",
        limit_clause="只有持有通行符的人才能进入旧塔",
    )
    path = tmp_path / "setting_a.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造设定上下文(path, _item("L2-04", "创意设定失败", body[:10]))
    _assert_setting_extraction(ctx, body)


def test_probe_c_l2_04_setting_extraction_variant_b(tmp_path):
    technique = f"法门{uuid.uuid4().hex[:4]}"
    body = _make_setting_body(
        technique,
        cost_clause="施术者都会消耗十年寿命",
        limit_clause="只有持有铁符的人才能踏入禁库",
    )
    path = tmp_path / "setting_b.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造设定上下文(path, _item("L2-04", "创意设定失败", body[:10]))
    _assert_setting_extraction(ctx, body)


# --- D. L2-05 阅读体验 ---


def _chapter_market_body(
    actor: str,
    *,
    repeat_phrase: str,
    danger_clause: str,
    choice_clause: str,
) -> str:
    opening = f"{actor} {danger_clause}"
    repeat_a = f"广播反复提醒：{repeat_phrase}，声音在空荡大厅里回荡。"
    repeat_b = f"守卫再次强调：{repeat_phrase}，仍无人解释原因。"
    middle = f"{actor} 绕到侧廊，发现封锁线后藏着未标记的检修口。"
    closing = f"{actor} {choice_clause}"
    return "\n\n".join((opening, repeat_a, repeat_b, middle, closing))


def _体验摘句(item) -> str:
    if isinstance(item, dict):
        return str(item.get("quote") or item.get("摘句") or "").strip()
    return str(getattr(item, "摘句", "") or getattr(item, "quote", "")).strip()


def _assert_market_context(ctx, text: str, *, repeat_phrase: str) -> None:
    blob = json.dumps(
        {
            "entrance": [e.__dict__ for e in ctx.入口承诺列表],
            "repeat": [r.__dict__ for r in ctx.重复信息列表],
            "ending": [e.__dict__ for e in ctx.末段推动力列表],
        },
        ensure_ascii=False,
    )
    _assert_no_injected_defaults(blob)

    entrance = ctx.入口承诺列表
    assert entrance
    first_para = ctx.段落列表[0]
    assert any(_体验摘句(e) in first_para for e in entrance if _体验摘句(e))

    repeats = ctx.重复信息
    assert repeats
    assert repeats[0].位置A != repeats[0].位置B
    norm = repeat_phrase.replace(" ", "")
    repeat_blob = json.dumps([r.__dict__ for r in repeats], ensure_ascii=False)
    assert norm in repeat_blob.replace(" ", "") or norm in text.replace(" ", "")

    ending = ctx.末段推动力列表
    assert ending
    last_para = ctx.段落列表[-1]
    assert any(_体验摘句(e) in last_para for e in ending if _体验摘句(e))


def test_probe_d_l2_05_market_context_variant_a(tmp_path):
    actor = _rand_label()
    repeat_phrase = f"{uuid.uuid4().hex[:6]} 不得靠近轨道"
    text = _chapter_market_body(
        actor,
        repeat_phrase=repeat_phrase,
        danger_clause="刚踏入废弃车站，月台尽头站着持械陌生人，危险一触即发。",
        choice_clause="必须在跳轨逃命与退回月台之间做出选择，而陌生人已举起信号弹。",
    )
    path = tmp_path / "market_a.md"
    path.write_text(text, encoding="utf-8")
    ctx = 构造阅读阶段上下文(path, _item("L2-05", "E低：即时情绪反馈弱", text[:8]))
    _assert_market_context(ctx, text, repeat_phrase=repeat_phrase)


def test_probe_d_l2_05_market_context_variant_b(tmp_path):
    actor = _rand_label()
    repeat_phrase = f"{uuid.uuid4().hex[:6]} 禁止进入核心区"
    text = _chapter_market_body(
        actor,
        repeat_phrase=repeat_phrase,
        danger_clause="刚进入地下管廊，前方传来机械守卫的启动声，局面紧迫。",
        choice_clause="必须决定是原路撤回还是继续深入，而警报已经亮起。",
    )
    path = tmp_path / "market_b.md"
    path.write_text(text, encoding="utf-8")
    ctx = 构造阅读阶段上下文(path, _item("L2-05", "E低：即时情绪反馈弱", text[:8]))
    _assert_market_context(ctx, text, repeat_phrase=repeat_phrase)


# --- E. L2-06 双来源 / 时序变化 ---


def _setup_ir_harness(
    base: Path,
    *,
    chapter_text: str,
    ir_text: str,
    ir_name: str = "IR-08_状态快照.md",
) -> tuple[Path, Path]:
    ir_dir = base / "IR"
    ir_dir.mkdir(parents=True)
    (ir_dir / ir_name).write_text(ir_text, encoding="utf-8")
    chapter = base / "ch.md"
    chapter.write_text(chapter_text, encoding="utf-8")
    return chapter, ir_dir


def _facts_for_text(facts: list[事实声明], text: str) -> list[事实声明]:
    return [f for f in facts if _fact_quote(f) and _fact_quote(f) in text]


def _assert_limb_cross_source(ctx, *, chapter_text: str, ir_text: str) -> None:
    body_facts = _facts_for_text(ctx.正文事实, chapter_text)
    ir_facts = _facts_for_text(ctx.IR事实, ir_text)
    assert body_facts and ir_facts

    assert all(f.来源类型 == "正文" for f in body_facts)
    assert all(f.来源类型 == "IR" for f in ir_facts)

    entity = body_facts[0].实体
    assert entity and any(f.实体 == entity for f in ir_facts)

    pairs = [
        p
        for p in ctx.事实对候选
        if p.get("entity") == entity
        and isinstance(p.get("source_a"), dict)
        and isinstance(p.get("source_b"), dict)
    ]
    assert pairs
    sample = pairs[0]
    assert sample["source_a"].get("来源类型") == "正文"
    assert sample["source_b"].get("来源类型") == "IR"
    assert sample["source_a"].get("摘句") in chapter_text
    assert sample["source_b"].get("摘句") in ir_text


def test_probe_e_l2_06_limb_conflict_cross_source(tmp_path):
    entity = _rand_label()
    chapter_text = f"{entity}左手已经断了。"
    ir_text = f"{entity}双手完好。"
    chapter, ir_dir = _setup_ir_harness(tmp_path, chapter_text=chapter_text, ir_text=ir_text)
    ctx = 构造一致性上下文(chapter, _item("L2-06", "技术护栏失败", chapter_text[:8]), ir_dir=ir_dir)
    _assert_limb_cross_source(ctx, chapter_text=chapter_text, ir_text=ir_text)


def test_probe_e_l2_06_temporal_location_allowed_change(tmp_path):
    entity = _rand_label()
    place_a, place_b = "河东", "河西"
    prior_text = f"清晨，{entity}还在{place_a}。"
    current_text = f"入夜后，{entity}已经进入{place_b}。"

    harness = tmp_path / "seq"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    prior = chapters / "ch00.md"
    current = chapters / "ch01.md"
    prior.write_text(prior_text, encoding="utf-8")
    current.write_text(current_text, encoding="utf-8")
    (harness / "project.json").write_text(
        json.dumps(
            {
                "schema_version": "xcue.project-manifest/1.0",
                "chapter_sequence": ["chapters/ch00.md", "chapters/ch01.md"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    from 前序章节 import 解析前序章节

    priors = 解析前序章节(current)
    assert len(priors) == 1

    ctx = 构造一致性上下文(
        current,
        _item("L2-06", "技术护栏失败", current_text[:8]),
        prior_chapters=priors,
    )
    prior_facts = _facts_for_text(ctx.前序章节事实, prior_text)
    current_facts = _facts_for_text(ctx.正文事实, current_text)
    assert prior_facts and current_facts

    prior_quote = _fact_quote(prior_facts[0])
    current_quote = _fact_quote(current_facts[0])
    entity_fact = prior_facts[0].实体

    parsed = {
        "root_cause": "位置变化",
        "consistency_conflicts": [
            {
                "conflict_type": "事实",
                "entity": entity_fact,
                "attribute": "位置",
                "source_a": {"paragraph": prior_facts[0].段落, "quote": prior_quote, "source_type": "前序章节"},
                "source_b": {"paragraph": current_facts[0].段落, "quote": current_quote, "source_type": "正文"},
                "classification": "ALLOWED_CHANGE",
            }
        ],
        "fix_actions": [],
        "acceptance_criteria": ["状态变化可解释"],
        "evidence_quotes": [{"paragraph": current_facts[0].段落, "quote": current_quote}],
    }
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("位置", []))
    assert not any("硬冲突" in e for e in errors if "ALLOWED" not in e.upper())
