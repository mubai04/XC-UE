from __future__ import annotations

from typing import Any

from L2模型 import 失败输入, 修复单, 证据
from 能力标准解析 import 能力规则
from 能力修复单 import 选择失败规则


def 诊断计划转修复单(
    item: 失败输入,
    rules: 能力规则,
    *,
    module_id: str,
    fix_form_type: str,
    root_cause: str,
    validated_quotes: list[dict[str, Any]],
    plan: dict[str, Any],
    module_detail: str = "",
) -> 修复单:
    rule = 选择失败规则(item, rules)
    actions = [str(a).strip() for a in plan.get("fix_actions") or [] if str(a).strip()][:4]
    acceptance = [str(a).strip() for a in plan.get("acceptance_criteria") or [] if str(a).strip()][:4]
    reroute = "是" if plan.get("needs_reroute") else "否"
    modify_scope = str(plan.get("modify_scope", "")).strip() or "章节局部"
    forbid_modify = str(plan.get("forbid_modify_scope", "")).strip() or "核心事实"
    diagnostic_evidence = [
        证据(int(entry["paragraph"]) if isinstance(entry.get("paragraph"), int) else None, str(entry["quote"]))
        for entry in validated_quotes
    ]
    detail_suffix = f" | 模块细节：{module_detail}" if module_detail else ""
    return 修复单(
        修复单类型=fix_form_type,
        来源闸门=item.来源闸门,
        接收模块=module_id,
        输入问题=f"{item.说明} | 根因：{root_cause}{detail_suffix}",
        主失败类型=item.失败类型,
        次失败类型=rule.编号 if rule else "",
        修复动作=" / ".join(actions),
        修复产物=item.修复方向 or rules.输出产物 or fix_form_type,
        验收问题="；".join(acceptance) if acceptance else module_detail,
        回流位置=item.回流验收位置 or item.来源闸门,
        是否需要其他L2辅助="否",
        是否需要回L15重路由=reroute,
        最终状态="回原闸门复验",
        标准来源=rules.标准来源,
        规则编号=rule.编号 if rule else "",
        规则依据=f"{root_cause} | 修改范围：{modify_scope} | 禁止：{forbid_modify}",
        标准动作=actions,
        标准验收=acceptance,
        rule_id=f"{module_id}:{rule.编号}" if rule else f"{module_id}:domain",
        rule_version=rule.规则版本 if rule else rules.规则版本,
        诊断证据=diagnostic_evidence,
    )
