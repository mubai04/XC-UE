from __future__ import annotations

from typing import Any

from 设定模型 import 设定诊断结果


def 规划设定修复(diagnosis: 设定诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions = [f"在「{p.quote[:10]}…」强化{p.rule_or_setting}对选择的压力：{p.choice_pressure}" for p in diagnosis.setting_pressure_points][:4]
    acceptance = [f"规则 {p.rule_or_setting} 推动角色做出可见选择" for p in diagnosis.setting_pressure_points][:4]
    return {
        "fix_actions": actions or [str(x) for x in parsed.get("fix_actions") or []][:4],
        "acceptance_criteria": acceptance or [str(x) for x in parsed.get("acceptance_criteria") or []][:4],
        "modify_scope": "设定呈现与规则压力",
        "forbid_modify_scope": "项目硬规则",
        "needs_reroute": bool(parsed.get("needs_reroute")),
    }


def 模块细节(diagnosis: 设定诊断结果) -> str:
    return "；".join(p.choice_pressure for p in diagnosis.setting_pressure_points[:3])
