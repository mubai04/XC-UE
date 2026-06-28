from __future__ import annotations

from typing import Any

from 事实模型 import 事实声明
from 属性归一 import 归一化属性

CONSISTENCY_RESPONSE_SCHEMA = "xcue.l2-consistency-response/2.0"

_PROTOCOL_SOURCE = {
    "正文": "CURRENT_CHAPTER",
    "IR": "IR",
    "前序章节": "PRIOR_CHAPTER",
    "规则": "RULE",
}
_SOURCE_PROTOCOL = {v: k for k, v in _PROTOCOL_SOURCE.items()}


def 来源类型到协议(来源类型: str) -> str:
    return _PROTOCOL_SOURCE.get(来源类型, 来源类型)


def 协议到来源类型(protocol: str) -> str:
    return _SOURCE_PROTOCOL.get(protocol, protocol)


def _fact_key(fact: 事实声明) -> tuple:
    return (
        fact.来源类型,
        fact.来源路径,
        fact.段落,
        fact.摘句,
        fact.实体,
        归一化属性(fact.属性),
        fact.归一化值,
        fact.否定,
    )


def _fact_dict_key(raw: dict) -> tuple:
    return (
        raw.get("来源类型"),
        raw.get("来源路径"),
        raw.get("段落"),
        raw.get("摘句"),
        raw.get("实体"),
        归一化属性(str(raw.get("属性", ""))),
        raw.get("归一化值"),
        raw.get("否定"),
    )


def 分配事实ID(facts: list[事实声明]) -> tuple[list[dict[str, Any]], dict[str, 事实声明]]:
    indexed: list[dict[str, Any]] = []
    by_id: dict[str, 事实声明] = {}
    for idx, fact in enumerate(facts, start=1):
        fact_id = f"FACT-{idx:04d}"
        by_id[fact_id] = fact
        indexed.append(
            {
                "fact_id": fact_id,
                "source_type": 来源类型到协议(fact.来源类型),
                "source_path": fact.来源路径,
                "paragraph": fact.段落,
                "quote": fact.摘句,
                "entity": fact.实体,
                "attribute": fact.属性,
                "normalized_attribute": 归一化属性(fact.属性),
                "value": fact.值,
                "normalized_value": fact.归一化值,
                "time_marker": fact.时间标记 or None,
            }
        )
    return indexed, by_id


def _lookup_fact_id(raw: dict, key_to_id: dict[tuple, str]) -> str | None:
    return key_to_id.get(_fact_dict_key(raw))


def 分配事实对ID(
    pairs: list[dict],
    fact_by_id: dict[str, 事实声明],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    key_to_id = {_fact_key(f): fid for fid, f in fact_by_id.items()}
    indexed_pairs: list[dict[str, Any]] = []
    pair_map: dict[str, dict[str, Any]] = {}
    pair_idx = 1
    for pair in pairs:
        sa = pair.get("source_a") or {}
        sb = pair.get("source_b") or {}
        sa_id = _lookup_fact_id(sa, key_to_id) if isinstance(sa, dict) else None
        sb_id = _lookup_fact_id(sb, key_to_id) if isinstance(sb, dict) else None
        if not sa_id or not sb_id:
            continue
        pair_id = f"PAIR-{pair_idx:04d}"
        pair_idx += 1
        entry = {
            "fact_pair_id": pair_id,
            "source_a_fact_id": sa_id,
            "source_b_fact_id": sb_id,
            "candidate_relation": pair.get("candidate_relation", "POSSIBLE_CONFLICT"),
            "entity": pair.get("entity") or sa.get("实体"),
            "attribute": pair.get("attribute") or sa.get("属性"),
            "normalized_attribute": pair.get("normalized_attribute")
            or 归一化属性(str(sa.get("属性", ""))),
        }
        indexed_pairs.append(entry)
        pair_map[pair_id] = entry
    return indexed_pairs, pair_map


def 构建索引包(ctx) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, 事实声明], dict[str, dict]]:
    all_facts = ctx.正文事实 + ctx.IR事实 + ctx.前序章节事实 + ctx.规则事实
    indexed_facts, fact_by_id = 分配事实ID(all_facts)
    raw_pairs = list(ctx.事实对候选 or [])
    for pair in raw_pairs:
        if "candidate_relation" not in pair:
            pair["candidate_relation"] = "POSSIBLE_CONFLICT"
    indexed_pairs, pair_by_id = 分配事实对ID(raw_pairs, fact_by_id)
    return indexed_facts, indexed_pairs, fact_by_id, pair_by_id
