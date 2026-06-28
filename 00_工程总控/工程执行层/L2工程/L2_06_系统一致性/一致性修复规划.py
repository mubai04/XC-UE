from __future__ import annotations

from typing import Any

from 事实模型 import 一致性诊断结果


def 规划一致性修复(diagnosis: 一致性诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions: list[str] = []
    acceptance: list[str] = []
    reroute = bool(parsed.get("needs_reroute"))
    modify_scope = "事实陈述与状态"
    forbid_scope = "已成立的核心事件"

    for c in diagnosis.consistency_conflicts:
        cls = c.分类 if c.分类 != "硬冲突" else "HARD_CONFLICT"
        if cls == "ALLOWED_CHANGE":
            continue
        if cls == "EVIDENCE_INSUFFICIENT":
            actions.append(f"{c.实体}.{c.属性}：补充可核对的双来源证据")
            acceptance.append(f"{c.实体}.{c.属性} 具备正文或 IR/前序章节的摘句证据")
            reroute = True
            continue
        if cls == "EXPLANATION_INSUFFICIENT":
            actions.append(
                f"{c.实体}.{c.属性}：补写状态变化桥梁，连接 {c.source_a.来源类型} 与 {c.source_b.来源类型}"
            )
            acceptance.append(f"{c.实体}.{c.属性} 的时间或因果过渡可被读者理解")
            continue
        if cls == "HARD_CONFLICT":
            actions.append(
                f"统一{c.实体}.{c.属性}：对齐 {c.source_a.来源类型} 与 {c.source_b.来源类型}"
            )
            acceptance.append(f"{c.实体}.{c.属性} 双来源可核对且无 HARD_CONFLICT")

    if not actions and any(
        (c.分类 if c.分类 != "硬冲突" else "HARD_CONFLICT") == "ALLOWED_CHANGE"
        for c in diagnosis.consistency_conflicts
    ):
        modify_scope = "说明性过渡"
        forbid_scope = "已成立的核心事件与合法状态变化"

    return {
        "fix_actions": actions[:4] or [str(x) for x in parsed.get("fix_actions") or []][:4],
        "acceptance_criteria": acceptance[:4] or [str(x) for x in parsed.get("acceptance_criteria") or []][:4],
        "modify_scope": modify_scope,
        "forbid_modify_scope": forbid_scope,
        "needs_reroute": reroute or bool(parsed.get("needs_reroute")),
    }


def 模块细节(diagnosis: 一致性诊断结果) -> str:
    parts = []
    for c in diagnosis.consistency_conflicts[:3]:
        cls = c.分类 if c.分类 != "硬冲突" else "HARD_CONFLICT"
        parts.append(f"{c.conflict_type}:{cls}")
    return "；".join(parts)
