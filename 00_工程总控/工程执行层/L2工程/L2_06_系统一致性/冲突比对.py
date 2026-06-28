from __future__ import annotations

import json
from typing import Any

from DeepSeek客户端 import DeepSeekClient
from JSON响应解析 import 提取JSON字典
from L2模型 import 失败输入
from 一致性上下文 import 上下文转诊断输入, 一致性上下文
from 事实模型 import 一致性冲突, 一致性诊断结果, 来源引用
from 事实索引 import CONSISTENCY_RESPONSE_SCHEMA
from 双来源校验 import 解析ID冲突
from 模型调用 import 调用模型JSON
from 属性归一 import 归一化属性, 归一化值

_TIME_ORDER: dict[str, int] = {
    "清晨": 1,
    "上午": 2,
    "中午": 3,
    "傍晚": 4,
    "入夜": 5,
    "深夜": 6,
    "此前": 0,
    "当时": 1,
    "此刻": 6,
    "次日": 10,
    "翌日": 10,
    "第二天": 10,
    "后来": 8,
    "随后": 8,
    "之后": 8,
    "数日后": 15,
    "几天后": 15,
    "几年后": 20,
}
_LOCATION_TRANSITION = (
    "进入", "离开", "抵达", "到达", "前往", "返回", "迁入", "搬到", "赶到",
    "走进", "走出", "穿过", "乘船", "乘车", "仍在", "还在",
)
_STATE_TRANSITION = (
    "恢复", "治愈", "受伤", "损坏", "修复", "变成", "改为", "升为", "降为",
    "获得", "失去", "不再", "重新", "完好", "完好无损",
)


def _time_rank(text: str) -> int | None:
    ranks = [rank for marker, rank in _TIME_ORDER.items() if marker in text]
    return max(ranks) if ranks else None


def _has_transition(text: str, *, norm_attr: str) -> bool:
    if norm_attr == "位置":
        return any(v in text for v in _LOCATION_TRANSITION)
    return any(v in text for v in _STATE_TRANSITION)


def _fact_values(
    ctx: 一致性上下文,
    *,
    entity: str,
    attribute: str,
    quote: str,
    source_type: str,
) -> list[str]:
    import re

    norm_attr = 归一化属性(attribute)
    vals: list[str] = []
    all_facts = ctx.正文事实 + ctx.IR事实 + ctx.前序章节事实 + ctx.规则事实
    for fact in all_facts:
        if fact.实体 != entity:
            continue
        if 归一化属性(fact.属性) != norm_attr:
            continue
        if quote and quote not in fact.摘句 and fact.摘句 not in quote:
            continue
        if source_type and fact.来源类型 != source_type:
            continue
        vals.append(fact.归一化值 or 归一化值(norm_attr, fact.值))
    if norm_attr == "位置":
        for pat in (
            rf"{re.escape(entity)}(?:仍在|还在|在|位于)([^，。！？]+)",
            rf"{re.escape(entity)}(?:乘船|乘车)?(?:抵达|到达|前往)([^，。！？]+)",
        ):
            m = re.search(pat, quote)
            if m:
                vals.append(归一化值(norm_attr, m.group(1).strip()))
    if norm_attr == "肢体状态":
        for kw in ("受伤", "完好", "治愈", "恢复"):
            if kw in quote:
                vals.append(归一化值(norm_attr, kw))
    return list(dict.fromkeys(vals))


def 复核冲突分类(
    ctx: 一致性上下文,
    *,
    entity: str = "",
    attribute: str = "",
    classification: str = "",
    source_a: dict | None = None,
    source_b: dict | None = None,
    fact_a=None,
    fact_b=None,
) -> str:
    if fact_a is not None:
        cls = classification if classification != "硬冲突" else "HARD_CONFLICT"
        if cls not in ("HARD_CONFLICT", "EXPLANATION_INSUFFICIENT", "ALLOWED_CHANGE"):
            return cls
        qa = str(fact_a.摘句 or "")
        qb = str(fact_b.摘句 or "") if fact_b else ""
        combined = qa + qb
        norm_attr = 归一化属性(fact_a.属性)
        val_a = fact_a.归一化值 or 归一化值(norm_attr, fact_a.值)
        val_b = (fact_b.归一化值 or 归一化值(norm_attr, fact_b.值)) if fact_b else ""
    else:
        cls = classification if classification != "硬冲突" else "HARD_CONFLICT"
        if cls not in ("HARD_CONFLICT", "EXPLANATION_INSUFFICIENT", "ALLOWED_CHANGE"):
            return cls
        qa = str((source_a or {}).get("quote", ""))
        qb = str((source_b or {}).get("quote", ""))
        combined = qa + qb
        norm_attr = 归一化属性(attribute)
        ta = str((source_a or {}).get("source_type", ""))
        tb = str((source_b or {}).get("source_type", ""))
        vals_a = _fact_values(ctx, entity=entity, attribute=attribute, quote=qa, source_type=ta)
        vals_b = _fact_values(ctx, entity=entity, attribute=attribute, quote=qb, source_type=tb)
        if not vals_a or not vals_b:
            return cls if cls != "HARD_CONFLICT" else "EXPLANATION_INSUFFICIENT"
        val_a = vals_a[0]
        val_b = vals_b[0]
        time_a = _time_rank(qa)
        time_b = _time_rank(qb)
        has_bridge = _has_transition(combined, norm_attr=norm_attr)
        if time_a is not None and time_b is not None:
            if time_a == time_b:
                return "HARD_CONFLICT"
            if time_a < time_b and has_bridge:
                return "ALLOWED_CHANGE"
            if time_a < time_b:
                return "EXPLANATION_INSUFFICIENT"
        if has_bridge and time_a is not None and time_b is not None:
            return "ALLOWED_CHANGE"
        return "EXPLANATION_INSUFFICIENT"

    if not val_b:
        return cls if cls != "HARD_CONFLICT" else "EXPLANATION_INSUFFICIENT"
    if val_a == val_b:
        return cls
    time_a = _time_rank(qa) or _time_rank(getattr(fact_a, "时间标记", "") or "")
    time_b = _time_rank(qb) or _time_rank(getattr(fact_b, "时间标记", "") or "" if fact_b else "")
    has_bridge = _has_transition(combined, norm_attr=norm_attr)
    if time_a is not None and time_b is not None:
        if time_a == time_b:
            return "HARD_CONFLICT"
        if time_a < time_b and has_bridge:
            return "ALLOWED_CHANGE"
        if time_a < time_b:
            return "EXPLANATION_INSUFFICIENT"
    if has_bridge and time_a is not None and time_b is not None:
        return "ALLOWED_CHANGE"
    return "EXPLANATION_INSUFFICIENT"


def _response_schema() -> dict[str, Any]:
    return {
        "response_schema_version": CONSISTENCY_RESPONSE_SCHEMA,
        "root_cause": "一致性根因",
        "consistency_conflicts": [
            {
                "fact_pair_id": "PAIR-0001",
                "source_a_fact_id": "FACT-0001",
                "source_b_fact_id": "FACT-0004",
                "classification": "HARD_CONFLICT",
                "reason": "判定理由",
                "repair_direction": "修复方向",
            }
        ],
        "fix_actions": ["动作1"],
        "acceptance_criteria": ["验收1"],
        "evidence_quotes": [{"paragraph": 1, "quote": "摘句A"}],
        "needs_reroute": False,
    }


def 执行冲突比对(ctx: 一致性上下文, item: 失败输入, *, client: DeepSeekClient | None = None) -> tuple[dict[str, Any], 一致性诊断结果]:
    payload = 上下文转诊断输入(ctx, item)
    schema = _response_schema()
    messages = [
        {
            "role": "system",
            "content": (
                "你是 L2-06 系统一致性诊断器。只输出 JSON。"
                f"必须使用 {CONSISTENCY_RESPONSE_SCHEMA}："
                "consistency_conflicts 通过 fact_pair_id、source_a_fact_id、source_b_fact_id 引用输入中的 indexed_facts/indexed_fact_pairs。"
                "不得自由重命名实体或属性作为主绑定键。"
                "classification 只能是 HARD_CONFLICT、EXPLANATION_INSUFFICIENT、ALLOWED_CHANGE、EVIDENCE_INSUFFICIENT。"
                "存在时间或状态转移信号时优先 ALLOWED_CHANGE 或 EXPLANATION_INSUFFICIENT，不得直接判 HARD_CONFLICT。"
                "EVIDENCE_INSUFFICIENT 可只引用 source_a_fact_id，但 reason 必须说明缺少的来源类型。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"输入：\n{json.dumps(payload, ensure_ascii=False)}\n\n"
                f"JSON：\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]
    parsed = 提取JSON字典(调用模型JSON(messages, client=client))
    conflicts: list[一致性冲突] = []
    for raw in parsed.get("consistency_conflicts") or []:
        if not isinstance(raw, dict):
            continue
        pair_id = str(raw.get("fact_pair_id", "")).strip()
        sa_id = str(raw.get("source_a_fact_id", "")).strip()
        sb_id = str(raw.get("source_b_fact_id", "")).strip()
        fact_a = ctx.索引事实表.get(sa_id)
        fact_b = ctx.索引事实表.get(sb_id)
        if not fact_a:
            continue
        classification = str(raw.get("classification", "HARD_CONFLICT")).strip()
        if classification == "硬冲突":
            classification = "HARD_CONFLICT"
        reviewed = 复核冲突分类(
            ctx,
            fact_a=fact_a,
            fact_b=fact_b,
            classification=classification,
        )
        raw["classification"] = reviewed
        sb = fact_b or fact_a
        conflicts.append(
            一致性冲突(
                conflict_type="事实",
                实体=str(fact_a.实体),
                属性=str(fact_a.属性),
                source_a=来源引用(
                    str(fact_a.来源类型),
                    str(fact_a.摘句),
                    int(fact_a.段落 or 0),
                    str(fact_a.来源路径 or ""),
                ),
                source_b=来源引用(
                    str(sb.来源类型),
                    str(sb.摘句),
                    int(sb.段落 or 0),
                    str(sb.来源路径 or ""),
                ),
                分类=reviewed,
            )
        )
        if pair_id:
            raw.setdefault("fact_pair_id", pair_id)
    if not conflicts:
        conflicts = 解析ID冲突(parsed, ctx)
    return parsed, 一致性诊断结果(
        root_cause=str(parsed.get("root_cause", "")).strip(),
        consistency_conflicts=conflicts,
    )
