from __future__ import annotations

from typing import Any

from 文风模型 import 文风诊断结果
from 领域证据 import 识别对话证据
from 通用证据定位 import 摘句在语料中

_FORBIDDEN_CONSTRAINTS = ("优化语言", "增强文风", "改善文风")
_FORBIDDEN_ACTIONS = ("优化语言", "增强文风")


def _明确说话人(quote: str) -> tuple[str | None, str]:
    ev = 识别对话证据(quote)
    return ev.get("speaker"), str(ev.get("speaker_confidence") or "UNKNOWN")


def 校验文风响应(parsed: dict[str, Any], corpus: str, diagnosis: 文风诊断结果) -> list[str]:
    errors: list[str] = []
    issues = parsed.get("style_issues")
    if not isinstance(issues, list) or not issues:
        return ["style_issues 必须是非空数组"]
    for idx, issue in enumerate(issues):
        if not isinstance(issue, dict):
            errors.append(f"style_issues[{idx}] 必须是对象")
            continue
        issue_type = str(issue.get("issue_type", "")).strip()
        if not issue_type:
            errors.append(f"style_issues[{idx}] 缺少 issue_type")
        if issue_type in {"人物语气漂移", "语气漂移"}:
            status = str(issue.get("status", "")).strip()
            if status == "evidence_insufficient":
                sa = issue.get("source_a") if isinstance(issue.get("source_a"), dict) else None
                if sa:
                    qa = str(sa.get("quote", "")).strip()
                    if not qa or not 摘句在语料中(qa, corpus):
                        errors.append(f"style_issues[{idx}] evidence_insufficient 的 source_a quote 无法定位")
                continue
            sa = issue.get("source_a") if isinstance(issue.get("source_a"), dict) else None
            sb = issue.get("source_b") if isinstance(issue.get("source_b"), dict) else None
            character = str(issue.get("character", "")).strip()
            if not sa or not sb:
                errors.append(f"style_issues[{idx}] 人物语气漂移缺少 source_a/source_b")
                continue
            qa = str(sa.get("quote", "")).strip()
            qb = str(sb.get("quote", "")).strip()
            if not qa or not qb or not 摘句在语料中(qa, corpus) or not 摘句在语料中(qb, corpus):
                errors.append(f"style_issues[{idx}] 语气漂移双来源 quote 无法定位")
                continue
            if qa == qb and sa.get("paragraph") == sb.get("paragraph"):
                errors.append(f"style_issues[{idx}] 语气漂移双来源不能同句同位置")
                continue
            sp_a, conf_a = _明确说话人(qa)
            sp_b, conf_b = _明确说话人(qb)
            if conf_a != "EXPLICIT" or conf_b != "EXPLICIT":
                errors.append(f"style_issues[{idx}] 语气漂移需要两处明确说话人")
                continue
            if not sp_a or not sp_b:
                errors.append(f"style_issues[{idx}] 语气漂移说话人无法确认")
                continue
            if sp_a != sp_b:
                errors.append(f"style_issues[{idx}] 语气漂移双来源说话人不一致")
                continue
            if character and character != sp_a:
                errors.append(f"style_issues[{idx}] character 与摘句说话人不一致")
            continue
        quote = str(issue.get("quote", "")).strip()
        if not quote or not 摘句在语料中(quote, corpus):
            errors.append(f"style_issues[{idx}] quote 无法在正文中定位")
        constraint = str(issue.get("constraint", "")).strip()
        if not constraint:
            errors.append(f"style_issues[{idx}] 缺少 constraint")
        elif any(f in constraint for f in _FORBIDDEN_CONSTRAINTS):
            errors.append(f"style_issues[{idx}] constraint 过于空泛")
    for action in parsed.get("fix_actions") or []:
        if any(f in str(action) for f in _FORBIDDEN_ACTIONS):
            errors.append(f"修复动作过于空泛：{action}")
    forbid = str(parsed.get("forbid_modify_scope", ""))
    if not forbid or not any(k in forbid for k in ("事件顺序", "人物目标", "世界规则")):
        errors.append("forbid_modify_scope 必须明确禁止改动事件顺序/人物目标/世界规则")
    return errors
