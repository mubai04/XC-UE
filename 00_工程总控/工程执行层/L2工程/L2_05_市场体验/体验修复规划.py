from __future__ import annotations



from typing import Any



from 体验模型 import 体验诊断结果





def 规划体验修复(diagnosis: 体验诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:

    actions = [f"{r.risk_type}：{r.modification_target}" for r in diagnosis.experience_risks][:4]

    acceptance = [f"在「{r.location_quote[:10]}…」读者可感知{r.modification_target}" for r in diagnosis.experience_risks][:4]

    if diagnosis.入口承诺列表 and len(actions) < 4:

        p = diagnosis.入口承诺列表[0]

        actions.append(f"入口承诺：在 P{p.段落} 强化读者预期")

        acceptance.append(f"首段摘句「{p.摘句[:12]}…」形成可追踪承诺")

    if diagnosis.末段推动力列表 and len(actions) < 4:

        m = diagnosis.末段推动力列表[-1]

        actions.append(f"末段推动力：在 P{m.段落} 留下可追读问题")

        acceptance.append(f"章末摘句「{m.摘句[:12]}…」驱动继续阅读")

    return {

        "fix_actions": actions or [str(x) for x in parsed.get("fix_actions") or []][:4],

        "acceptance_criteria": acceptance or [str(x) for x in parsed.get("acceptance_criteria") or []][:4],

        "modify_scope": "阅读阶段局部",

        "forbid_modify_scope": "核心情节事实",

        "needs_reroute": bool(parsed.get("needs_reroute")),

    }





def 模块细节(diagnosis: 体验诊断结果) -> str:

    parts = [f"{r.risk_type}→{r.modification_target}" for r in diagnosis.experience_risks[:2]]

    if diagnosis.认知负担列表:

        parts.append(f"认知负担:{diagnosis.认知负担列表[0].类型}")

    if diagnosis.重复信息列表:

        parts.append(f"重复:{diagnosis.重复信息列表[0].短语}")

    return "；".join(parts[:3])

