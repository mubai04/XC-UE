from __future__ import annotations

from typing import Any

from 角色模型 import 角色诊断结果


def 规划角色修复(diagnosis: 角色诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions = []
    acceptance = []
    for gap in diagnosis.motivation_gaps:
        actions.append(f"在「{gap.behavior_quote[:12]}…」前补全{gap.missing_link}")
        acceptance.append(f"{gap.character} 的行为链含目标—刺激—行为—结果")
    return {
        "fix_actions": actions[:4] or [str(x) for x in parsed.get("fix_actions") or []][:4],
        "acceptance_criteria": acceptance[:4] or [str(x) for x in parsed.get("acceptance_criteria") or []][:4],
        "modify_scope": "角色行为与动机描写",
        "forbid_modify_scope": "与人物既有目标冲突的新设定",
        "needs_reroute": bool(parsed.get("needs_reroute")),
    }


def 模块细节(diagnosis: 角色诊断结果) -> str:
    return "；".join(f"{g.character}:{g.missing_link}" for g in diagnosis.motivation_gaps[:3])
