from __future__ import annotations

from typing import Any


def 摘句在语料中(quote: str, corpus: str) -> bool:
    if not quote or not quote.strip():
        return False
    return quote in corpus


def 校验诊断响应(parsed: dict[str, Any], corpus: str) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []

    root_cause = parsed.get("root_cause")
    if not isinstance(root_cause, str) or not root_cause.strip():
        errors.append("root_cause 必须是非空字符串")
    else:
        root_cause = root_cause.strip()

    fix_actions = parsed.get("fix_actions")
    if not isinstance(fix_actions, list) or not fix_actions:
        errors.append("fix_actions 必须是非空数组")
    else:
        actions = [str(item).strip() for item in fix_actions if str(item).strip()]
        if not actions:
            errors.append("fix_actions 无有效项")
        elif len(actions) > 4:
            errors.append("fix_actions 最多 4 项")

    acceptance = parsed.get("acceptance_criteria")
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("acceptance_criteria 必须是非空数组")
    else:
        criteria = [str(item).strip() for item in acceptance if str(item).strip()]
        if not criteria:
            errors.append("acceptance_criteria 无有效项")
        elif len(criteria) > 4:
            errors.append("acceptance_criteria 最多 4 项")

    quotes_raw = parsed.get("evidence_quotes")
    if not isinstance(quotes_raw, list) or not quotes_raw:
        errors.append("evidence_quotes 必须是非空数组")
        return [], errors

    validated: list[dict[str, Any]] = []
    for idx, item in enumerate(quotes_raw):
        if not isinstance(item, dict):
            errors.append(f"evidence_quotes[{idx}] 必须是对象")
            continue
        quote = str(item.get("quote", "")).strip()
        if not quote:
            errors.append(f"evidence_quotes[{idx}] 摘句不能为空")
            continue
        if not 摘句在语料中(quote, corpus):
            errors.append(f"evidence_quotes[{idx}] 摘句无法在正文上下文或失败证据中逐字找到")
            continue
        validated.append(
            {
                "paragraph": item.get("paragraph"),
                "quote": quote,
            }
        )

    if errors:
        return validated, errors

    if isinstance(root_cause, str) and validated and not any(entry["quote"] in root_cause for entry in validated):
        errors.append("root_cause 必须引用至少一条已校验 evidence_quotes 摘句")

    return validated, errors
