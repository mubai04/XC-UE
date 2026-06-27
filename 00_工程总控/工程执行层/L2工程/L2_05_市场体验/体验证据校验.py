from __future__ import annotations

from typing import Any

from 体验模型 import 体验诊断结果
from 通用证据定位 import 摘句在语料中

_FORBIDDEN_ROOT = ("SCREENING_REJECT", "SCREENING_PASS", "PASS", "FAIL")
_FORBIDDEN_ACTION = ("提高爽点", "增强吸引力", "加强钩子")
_RISK_TYPES = {"弃读", "认知负担", "信息重复", "入口弱", "末段推动力不足", "即时收益弱"}


def 校验体验响应(parsed: dict[str, Any], corpus: str, diagnosis: 体验诊断结果) -> list[str]:
    errors: list[str] = []
    root = str(parsed.get("root_cause", "")).strip()
    if root in _FORBIDDEN_ROOT:
        errors.append("root_cause 不得复述 L1 状态")
    risks = parsed.get("experience_risks")
    if not isinstance(risks, list) or not risks:
        return ["experience_risks 必须是非空数组"]
    for idx, risk in enumerate(risks):
        if not isinstance(risk, dict):
            errors.append(f"experience_risks[{idx}] 必须是对象")
            continue
        quote = str(risk.get("location_quote", "")).strip()
        if not quote or not 摘句在语料中(quote, corpus):
            errors.append(f"experience_risks[{idx}] location_quote 无法在正文中定位")
        rtype = str(risk.get("risk_type", "")).strip()
        if rtype and rtype not in _RISK_TYPES and rtype not in corpus:
            errors.append(f"experience_risks[{idx}] risk_type 未归类")
        target = str(risk.get("modification_target", "")).strip()
        if not target or len(target) < 4:
            errors.append(f"experience_risks[{idx}] modification_target 必须说明改哪一处及读者效果")
    for action in parsed.get("fix_actions") or []:
        if any(f in str(action) for f in _FORBIDDEN_ACTION):
            errors.append(f"修复动作过于空泛：{action}")
    if "SCREENING" in str(parsed):
        errors.append("不得复述 SCREENING 状态")
    return errors
