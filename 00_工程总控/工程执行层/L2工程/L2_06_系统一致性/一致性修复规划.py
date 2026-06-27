from __future__ import annotations

from typing import Any

from 事实模型 import 一致性诊断结果


def 规划一致性修复(diagnosis: 一致性诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions = []
    acceptance = []
    for c in diagnosis.consistency_conflicts:
        actions.append(f"统一{c.实体}.{c.属性}：对齐 {c.source_a.来源类型} 与 {c.source_b.来源类型}")
        acceptance.append(f"{c.实体}.{c.属性} 双来源可核对且无硬冲突")
    return {
        "fix_actions": actions[:4] or [str(x) for x in parsed.get("fix_actions") or []][:4],
        "acceptance_criteria": acceptance[:4] or [str(x) for x in parsed.get("acceptance_criteria") or []][:4],
        "modify_scope": "事实陈述与状态",
        "forbid_modify_scope": "已成立的核心事件",
        "needs_reroute": bool(parsed.get("needs_reroute")),
    }


def 模块细节(diagnosis: 一致性诊断结果) -> str:
    return "；".join(c.conflict_type for c in diagnosis.consistency_conflicts[:3])
