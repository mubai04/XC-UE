from __future__ import annotations

from typing import Any

from 设定模型 import 设定诊断结果
from 通用证据定位 import 摘句在语料中

_FORBIDDEN = ("加强设定", "增强设定差异", "加强设定差异")
_CONFLICT_WORDS = ("硬冲突", "source_a", "source_b", "一致性冲突")


def 校验设定响应(parsed: dict[str, Any], corpus: str, diagnosis: 设定诊断结果) -> list[str]:
    errors: list[str] = []
    points = parsed.get("setting_pressure_points")
    if not isinstance(points, list) or not points:
        return ["setting_pressure_points 必须是非空数组"]
    for idx, point in enumerate(points):
        if not isinstance(point, dict):
            errors.append(f"setting_pressure_points[{idx}] 必须是对象")
            continue
        quote = str(point.get("quote", "")).strip()
        if not quote or not 摘句在语料中(quote, corpus):
            errors.append(f"setting_pressure_points[{idx}] quote 无法在正文中定位")
        if not str(point.get("choice_pressure", "")).strip():
            errors.append(f"setting_pressure_points[{idx}] 缺少 choice_pressure")
        elif "迫使" not in str(point.get("choice_pressure", "")) and "放弃" not in str(point.get("choice_pressure", "")) and "选择" not in str(point.get("choice_pressure", "")):
            errors.append(f"setting_pressure_points[{idx}] choice_pressure 未说明选择压力")
    if not str(parsed.get("sustainable_variant", "")).strip() or parsed.get("sustainable_variant") == "可扩展":
        errors.append("sustainable_variant 必须给出可重复变体")
    blob = str(parsed)
    if any(w in blob for w in _CONFLICT_WORDS):
        errors.append("设定模块不得直接宣判一致性冲突，应转交 L2-06")
    for f in _FORBIDDEN:
        if f in blob:
            errors.append(f"命中禁止空泛表达：{f}")
    return errors
