from __future__ import annotations

from typing import Any

from 文风模型 import 文风修改动作, 文风诊断结果, 文风问题

_ACTION_BY_TYPE = {
    "重复": "删除或合并重复短语的具体出现位置，保留首次有效表达",
    "解释腔": "保留必要事实，删除解释性转述与旁白归纳",
    "过长句": "按动作或信息单位拆分为两句以上，保持事件顺序",
    "连续短句": "仅在节奏破碎处合并相邻短句，避免堆叠",
    "人物语气漂移": "限定同一人物两处表达风格一致，不修改人物目标与事件事实",
    "语气漂移": "限定同一人物两处表达风格一致，不修改人物目标与事件事实",
}


def _动作文案(issue: 文风问题) -> str:
    if issue.constraint and issue.constraint not in ("优化语言", "增强文风"):
        return issue.constraint
    return _ACTION_BY_TYPE.get(issue.issue_type, f"在段落{issue.paragraph}调整{issue.issue_type}")


def 规划文风修复(diagnosis: 文风诊断结果, parsed: dict[str, Any]) -> dict[str, Any]:
    actions: list[文风修改动作] = []
    for issue in diagnosis.style_issues:
        if not issue.quote and issue.issue_type not in {"人物语气漂移", "语气漂移"}:
            continue
        loc = f"段落{issue.paragraph}" + (f"句{issue.sentence}" if issue.sentence else "")
        actions.append(
            文风修改动作(
                目标位置=loc,
                动作=_动作文案(issue),
                保留范围="；".join(parsed.get("preserve_info") or []) or "failure_evidence 所指信息",
                禁止范围=str(parsed.get("forbid_modify_scope") or "事件顺序、人物目标、世界规则"),
                验收标准=f"{issue.issue_type}在{loc}可复验改善",
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
