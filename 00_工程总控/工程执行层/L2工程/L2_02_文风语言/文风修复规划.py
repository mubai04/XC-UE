from __future__ import annotations

from typing import Any

from 文风模型 import 文风修改动作, 文风诊断结果, 文风问题


def 规划文风修复(diagnosis: 文风诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions: list[文风修改动作] = []
    for issue in diagnosis.style_issues:
        if not issue.quote:
            continue
        loc = f"段落{issue.paragraph}" + (f"句{issue.sentence}" if issue.sentence else "")
        actions.append(
            文风修改动作(
                目标位置=loc,
                动作=issue.constraint or f"调整{issue.issue_type}",
                保留范围="；".join(parsed.get("preserve_info") or []) or "failure_evidence 所指信息",
                禁止范围=str(parsed.get("forbid_modify_scope") or "事件顺序、人物目标、世界规则"),
                验收标准=f"{issue.issue_type}问题在{loc}可复验改善",
            )
        )
    fix_actions = [a.动作 for a in actions][:4] or [str(x) for x in parsed.get("fix_actions") or []][:4]
    acceptance = [a.验收标准 for a in actions][:4] or [str(x) for x in parsed.get("acceptance_criteria") or []][:4]
    return {
        "fix_actions": fix_actions,
        "acceptance_criteria": acceptance,
        "modify_scope": str(parsed.get("modify_scope") or "段落级"),
        "forbid_modify_scope": str(parsed.get("forbid_modify_scope") or "事件顺序、人物目标、世界规则"),
        "needs_reroute": bool(parsed.get("needs_reroute")),
        "style_actions": [{"位置": a.目标位置, "动作": a.动作} for a in actions],
    }


def 模块细节(diagnosis: 文风诊断结果) -> str:
    return "；".join(f"{i.issue_type}@{i.paragraph}" for i in diagnosis.style_issues[:3])
