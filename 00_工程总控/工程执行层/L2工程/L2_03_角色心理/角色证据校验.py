from __future__ import annotations

import json
from typing import Any

from 角色上下文 import 角色上下文
from 角色模型 import 角色诊断结果
from 领域证据 import PRONOUNS
from 通用证据定位 import 摘句在语料中

_FORBIDDEN = ("增强人物", "补充心理描写", "加强角色")
_VALID_MISSING = (
    "缺少目标",
    "缺少刺激",
    "缺少目标到行为的连接",
    "缺少选择理由",
    "缺少行为结果",
    "情绪变化缺少过渡",
    "缺恐惧来源",
    "未交代恐惧来源",
)


def _已知角色名(ctx: 角色上下文) -> set[str]:
    names: set[str] = set()
    for item in ctx.识别角色:
        if isinstance(item, dict):
            if item.get("confirmed"):
                names.add(str(item.get("name", "")))
            elif item.get("name"):
                names.add(str(item["name"]))
        else:
            names.add(str(item))
    for chain in ctx.目标刺激行为链:
        if chain.get("character"):
            names.add(str(chain["character"]))
    return {n for n in names if n}


def 校验角色响应(parsed: dict[str, Any], corpus: str, ctx: 角色上下文, diagnosis: 角色诊断结果) -> list[str]:
    errors: list[str] = []
    gaps = parsed.get("motivation_gaps")
    if not isinstance(gaps, list) or not gaps:
        return ["motivation_gaps 必须是非空数组"]
    known_chars = _已知角色名(ctx)
    for idx, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            errors.append(f"motivation_gaps[{idx}] 必须是对象")
            continue
        char = str(gap.get("character", "")).strip()
        quote = str(gap.get("behavior_quote", "")).strip()
        if char and char not in known_chars:
            if not (char in PRONOUNS and quote and 摘句在语料中(quote, corpus)) and char not in corpus:
                errors.append(f"motivation_gaps[{idx}] character 无法在上下文中定位")
        if not quote or not 摘句在语料中(quote, corpus):
            errors.append(f"motivation_gaps[{idx}] behavior_quote 无法在正文中定位")
        missing = str(gap.get("missing_link", "")).strip()
        if not missing:
            errors.append(f"motivation_gaps[{idx}] 缺少 missing_link")
        elif any(f in missing for f in _FORBIDDEN):
            errors.append(f"motivation_gaps[{idx}] missing_link 过于空泛")
        elif missing in ("动机不足", "增强人物") or missing == "增强人物":
            errors.append(f"motivation_gaps[{idx}] missing_link 过于空泛")
    for action in parsed.get("fix_actions") or []:
        if any(f in str(action) for f in _FORBIDDEN):
            errors.append(f"修复动作过于空泛：{action}")
    if "增强人物" in json.dumps(parsed, ensure_ascii=False):
        errors.append("响应命中禁止空泛表达")
    return errors
