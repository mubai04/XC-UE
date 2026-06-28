from __future__ import annotations

import re
from typing import Any


def 摘句在语料中(quote: str, corpus: str) -> bool:
    if not quote or not quote.strip():
        return False
    return quote in corpus


def 切分段落(正文: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", 正文.strip()) if b.strip()]
    return blocks if blocks else ([正文.strip()] if 正文.strip() else [])


def 切分句子(段落: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])", 段落)
    return [p.strip() for p in parts if p.strip()]


def 通用字段检查(parsed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = parsed.get("root_cause")
    if not isinstance(root, str) or not root.strip():
        errors.append("root_cause 必须是非空字符串")
    actions = parsed.get("fix_actions")
    if not isinstance(actions, list) or not [a for a in actions if str(a).strip()]:
        errors.append("fix_actions 必须是非空数组")
    acceptance = parsed.get("acceptance_criteria")
    if not isinstance(acceptance, list) or not [a for a in acceptance if str(a).strip()]:
        errors.append("acceptance_criteria 必须是非空数组")
    quotes = parsed.get("evidence_quotes")
    if not isinstance(quotes, list) or not quotes:
        errors.append("evidence_quotes 必须是非空数组")
    else:
        for idx, item in enumerate(quotes):
            if not isinstance(item, dict):
                errors.append(f"evidence_quotes[{idx}] 必须是对象")
                continue
            q = str(item.get("quote", "")).strip()
            if not q:
                errors.append(f"evidence_quotes[{idx}].quote 不能为空")
    return errors


def 校验通用证据引用(parsed: dict[str, Any], corpus: str) -> tuple[list[dict[str, Any]], list[str]]:
    errors = 通用字段检查(parsed)
    validated: list[dict[str, Any]] = []
    for idx, item in enumerate(parsed.get("evidence_quotes") or []):
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        if quote and not 摘句在语料中(quote, corpus):
            errors.append(f"evidence_quotes[{idx}].quote 无法在正文中定位")
        else:
            validated.append(item)
    return validated, errors
