from __future__ import annotations

from typing import Any


def 摘句在语料中(quote: str, corpus: str) -> bool:
    if not quote or not quote.strip():
        return False
    return quote in corpus


def 校验诊断响应(
    parsed: dict[str, Any],
    corpus: str,
    *,
    failure_type: str = "",
    description: str = "",
    repair_direction: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []

    root_cause = parsed.get("root_cause")
    if not isinstance(root_cause, str) or not root_cause.strip():
        errors.append("root_cause 必须是非空字符串")
    else:
        root_cause = root_cause.strip()
        forbidden = {value.strip() for value in (failure_type, description, repair_direction) if value and value.strip()}
        if root_cause in forbidden:
            errors.append("root_cause 不得仅等于 failure_type、description 或 repair_direction")

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

    indices_raw = parsed.get("root_cause_evidence_indices")
    if not isinstance(indices_raw, list) or not indices_raw:
        errors.append("root_cause_evidence_indices 必须是非空整数数组")
        return validated, errors

    indices: list[int] = []
    for idx, value in enumerate(indices_raw):
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"root_cause_evidence_indices[{idx}] 必须是整数")
            continue
        if value < 0:
            errors.append(f"root_cause_evidence_indices[{idx}] 不能为负数")
            continue
        if value >= len(validated):
            errors.append(f"root_cause_evidence_indices[{idx}] 越界")
            continue
        indices.append(value)

    if len(indices) != len(indices_raw):
        return validated, errors

    if len(set(indices)) != len(indices):
        errors.append("root_cause_evidence_indices 不允许重复索引")

    return validated, errors
