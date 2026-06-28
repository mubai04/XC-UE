from __future__ import annotations

from typing import Any

from 设定模型 import 设定诊断结果


def 规划设定修复(diagnosis: 设定诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions = []
    for p in diagnosis.setting_pressure_points[:4]:
        label = p.rule_or_setting or p.problem_type
        direction = p.choice_pressure or p.analysis
        actions.append(f"针对「{label}」：{direction}")
    acceptance = [
        f"设定 {p.rule_or_setting or p.problem_type} 推动角色做出可见选择"
        for p in diagnosis.setting_pressure_points[:4]
    ]
    for diff in diagnosis.differentiation_points[:2]:
        actions.append(f"突出差异：{diff.描述}（相对常规：{diff.与普通方案差别}）")
        acceptance.append(f"读者可感知设定差异：{diff.描述[:20]}")
    for var in diagnosis.sustainable_variants[:2]:
        actions.append(f"延展变体 {var.变体}：{var.可重复机制}")
        acceptance.append(f"变体 {var.变体} 可在后续章节重复触发")
    return {
        "fix_actions": actions or [str(x) for x in parsed.get("fix_actions") or []][:4],
        "acceptance_criteria": acceptance or [str(x) for x in parsed.get("acceptance_criteria") or []][:4],
        "modify_scope": "设定呈现与规则压力",
        "forbid_modify_scope": "项目硬规则",
        "needs_reroute": bool(parsed.get("needs_reroute")),
    }


def 模块细节(diagnosis: 设定诊断结果) -> str:
    parts = [p.analysis or p.choice_pressure for p in diagnosis.setting_pressure_points[:2]]
    if diagnosis.differentiation_points:
        parts.append(diagnosis.differentiation_points[0].描述)
    if diagnosis.sustainable_variants:
        parts.append(diagnosis.sustainable_variants[0].变体)
    return "；".join(parts[:3])
