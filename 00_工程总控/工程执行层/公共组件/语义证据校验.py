from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class 证据校验结果:
    ok: bool
    errors: list[str]
    valid_quotes: list[dict[str, Any]]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def 摘句在正文中(quote: str, source_text: str) -> bool:
    if not quote or not quote.strip():
        return False
    if quote in source_text:
        return True
    return _normalize(quote) in _normalize(source_text)


def 校验维度证据(
    dimensions: list[dict[str, Any]],
    source_text: str,
    *,
    require_quotes_on_fail: bool = True,
) -> 证据校验结果:
    errors: list[str] = []
    valid: list[dict[str, Any]] = []
    for dim in dimensions:
        name = str(dim.get("name", ""))
        verdict = str(dim.get("verdict", "")).upper()
        quotes = dim.get("evidence_quotes") or dim.get("quotes") or []
        if not isinstance(quotes, list):
            errors.append(f"{name}: evidence_quotes 必须是数组")
            continue
        if verdict in {"FAIL", "REVIEW", "WARN", "WARNING"} and require_quotes_on_fail and not quotes:
            errors.append(f"{name}: 非 PASS 结论必须提供 evidence_quotes")
            continue
        for idx, item in enumerate(quotes):
            if not isinstance(item, dict):
                errors.append(f"{name}: 证据项 {idx} 必须是对象")
                continue
            quote = str(item.get("quote", "")).strip()
            if not 摘句在正文中(quote, source_text):
                errors.append(f"{name}: 摘句无法在输入正文中逐字找到")
                continue
            valid.append({"dimension": name, "quote": quote, "paragraph": item.get("paragraph")})
    return 证据校验结果(ok=not errors, errors=errors, valid_quotes=valid)


def 校验语义审计响应(parsed: dict[str, Any], source_text: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    dimensions = parsed.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return False, ["响应缺少 dimensions 数组"]
    result = 校验维度证据(dimensions, source_text)
    errors.extend(result.errors)
    overall = str(parsed.get("overall", "")).upper()
    allowed_overall = {"PASS", "FAIL", "REVIEW"}
    if overall not in allowed_overall:
        errors.append("overall 必须是 PASS / FAIL / REVIEW")
    for dim in dimensions:
        verdict = str(dim.get("verdict", "")).upper()
        if verdict not in allowed_overall:
            errors.append(f"维度 {dim.get('name')} verdict 非法")
        score = dim.get("score")
        if score is not None:
            try:
                score_val = int(score)
            except (TypeError, ValueError):
                errors.append(f"维度 {dim.get('name')} score 必须是整数")
            else:
                if score_val < 1 or score_val > 5:
                    errors.append(f"维度 {dim.get('name')} score 必须在 1-5")
    return not errors, errors
