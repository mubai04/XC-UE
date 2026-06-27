from __future__ import annotations

from typing import Any

from 文风模型 import 文风诊断结果, 文风问题
from 通用证据定位 import 摘句在语料中

_FORBIDDEN_CONSTRAINTS = ("优化语言", "增强文风", "改善文风")
_FORBIDDEN_ACTIONS = ("优化语言", "增强文风")


def 校验文风响应(parsed: dict[str, Any], corpus: str, diagnosis: 文风诊断结果) -> list[str]:
    errors: list[str] = []
    issues = parsed.get("style_issues")
    if not isinstance(issues, list) or not issues:
        return ["style_issues 必须是非空数组"]
    for idx, issue in enumerate(issues):
        if not isinstance(issue, dict):
            errors.append(f"style_issues[{idx}] 必须是对象")
            continue
        if not str(issue.get("issue_type", "")).strip():
            errors.append(f"style_issues[{idx}] 缺少 issue_type")
        quote = str(issue.get("quote", "")).strip()
        if not quote or not 摘句在语料中(quote, corpus):
            errors.append(f"style_issues[{idx}] quote 无法在正文中定位")
        constraint = str(issue.get("constraint", "")).strip()
        if not constraint:
            errors.append(f"style_issues[{idx}] 缺少 constraint")
        elif any(f in constraint for f in _FORBIDDEN_CONSTRAINTS):
            errors.append(f"style_issues[{idx}] constraint 过于空泛")
    for action in parsed.get("fix_actions") or []:
        text = str(action).strip()
        if any(f in text for f in _FORBIDDEN_ACTIONS):
            errors.append(f"修复动作过于空泛：{text}")
    forbid = str(parsed.get("forbid_modify_scope", ""))
    if "事件顺序" not in forbid and "人物目标" not in forbid and "世界规则" not in forbid:
        if not forbid:
            errors.append("forbid_modify_scope 必须明确禁止改动事件顺序/人物目标/世界规则")
    tone_issues = [i for i in diagnosis.style_issues if i.issue_type in {"人物语气漂移", "语气漂移"}]
    for ti in tone_issues:
        if ti.issue_type and "证据不足" not in ti.constraint:
            count = corpus.count(ti.quote[:4]) if ti.quote else 0
            if count < 1:
                errors.append("人物语气漂移需在同一人物两处来源或标记证据不足")
    return errors
