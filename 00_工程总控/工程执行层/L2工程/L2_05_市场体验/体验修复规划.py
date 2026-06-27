from __future__ import annotations

from typing import Any

from 体验模型 import 体验诊断结果


def 规划体验修复(diagnosis: 体验诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions = [f"{r.risk_type}：{r.modification_target}" for r in diagnosis.experience_risks][:4]
    acceptance = [f"在「{r.location_quote[:10]}…」读者可感知{r.modification_target}" for r in diagnosis.experience_risks][:4]
    return {
        "fix_actions": actions or [str(x) for x in parsed.get("fix_actions") or []][:4],
        "acceptance_criteria": acceptance or [str(x) for x in parsed.get("acceptance_criteria") or []][:4],
        "modify_scope": "阅读阶段局部",
        "forbid_modify_scope": "核心情节事实",
        "needs_reroute": bool(parsed.get("needs_reroute")),
    }


def 模块细节(diagnosis: 体验诊断结果) -> str:
    return "；".join(f"{r.risk_type}→{r.modification_target}" for r in diagnosis.experience_risks[:3])
