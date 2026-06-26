from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_DIMENSIONS = ("因果", "动机", "冲突", "读者收益", "认知成本", "章末追读")
ALLOWED_VERDICTS = frozenset({"PASS", "FAIL", "REVIEW"})


@dataclass
class 证据校验结果:
    ok: bool
    errors: list[str]
    valid_quotes: list[dict[str, Any]]


def 摘句在正文中(quote: str, source_text: str) -> bool:
    if not quote or not quote.strip():
        return False
    return quote in source_text


def _overall与维度一致(overall: str, verdicts: list[str]) -> list[str]:
    errors: list[str] = []
    if "FAIL" in verdicts and overall != "FAIL":
        errors.append("overall 与维度不一致：存在 FAIL 时 overall 必须为 FAIL")
    elif "REVIEW" in verdicts and overall == "PASS":
        errors.append("overall 与维度不一致：存在 REVIEW 时 overall 不得为 PASS")
    elif all(v == "PASS" for v in verdicts) and overall != "PASS":
        errors.append("overall 与维度不一致：全部 PASS 时 overall 必须为 PASS")
    return errors


def 校验维度证据(dimensions: list[dict[str, Any]], source_text: str) -> 证据校验结果:
    errors: list[str] = []
    valid: list[dict[str, Any]] = []
    names = [str(dim.get("name", "")) for dim in dimensions if isinstance(dim, dict)]
    if len(names) != len(REQUIRED_DIMENSIONS):
        errors.append("dimensions 必须且只能包含 6 个维度")
    if set(names) != set(REQUIRED_DIMENSIONS):
        errors.append(f"维度必须且只能为：{', '.join(REQUIRED_DIMENSIONS)}")
    if len(names) != len(set(names)):
        errors.append("dimensions 存在重复维度")
    for dim in dimensions:
        if not isinstance(dim, dict):
            errors.append("dimensions 项必须是对象")
            continue
        name = str(dim.get("name", ""))
        verdict = str(dim.get("verdict", "")).upper()
        quotes = dim.get("evidence_quotes") or dim.get("quotes") or []
        if verdict not in ALLOWED_VERDICTS:
            errors.append(f"{name}: verdict 非法")
        if not isinstance(quotes, list) or not quotes:
            errors.append(f"{name}: 所有 verdict 必须提供 evidence_quotes")
            continue
        for idx, item in enumerate(quotes):
            if not isinstance(item, dict):
                errors.append(f"{name}: 证据项 {idx} 必须是对象")
                continue
            quote = str(item.get("quote", ""))
            if not quote.strip():
                errors.append(f"{name}: 摘句不能为空")
                continue
            if not 摘句在正文中(quote, source_text):
                errors.append(f"{name}: 摘句无法在输入正文中逐字找到")
                continue
            valid.append({"dimension": name, "quote": quote, "paragraph": item.get("paragraph")})
        score = dim.get("score")
        if score is not None:
            try:
                score_val = int(score)
            except (TypeError, ValueError):
                errors.append(f"{name}: score 必须是整数")
            else:
                if score_val < 1 or score_val > 5:
                    errors.append(f"{name}: score 必须在 1-5")
    return 证据校验结果(ok=not errors, errors=errors, valid_quotes=valid)


def 校验语义审计响应(parsed: dict[str, Any], source_text: str) -> tuple[bool, list[str]]:
    dimensions = parsed.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return False, ["响应缺少 dimensions 数组"]
    overall = str(parsed.get("overall", "")).upper()
    if overall not in ALLOWED_VERDICTS:
        return False, ["overall 必须是 PASS / FAIL / REVIEW"]
    result = 校验维度证据(dimensions, source_text)
    errors = list(result.errors)
    verdicts = [str(dim.get("verdict", "")).upper() for dim in dimensions if isinstance(dim, dict)]
    errors.extend(_overall与维度一致(overall, verdicts))
    return not errors, errors
