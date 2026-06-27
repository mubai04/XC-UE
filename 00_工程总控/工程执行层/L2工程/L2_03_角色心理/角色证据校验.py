from __future__ import annotations

import json
from typing import Any

from 角色上下文 import 角色上下文
from 角色模型 import 角色诊断结果
from 通用证据定位 import 摘句在语料中

_FORBIDDEN = ("增强人物", "补充心理描写", "加强角色")


def 校验角色响应(parsed: dict[str, Any], corpus: str, ctx: 角色上下文, diagnosis: 角色诊断结果) -> list[str]:
    errors: list[str] = []
    gaps = parsed.get("motivation_gaps")
    if not isinstance(gaps, list) or not gaps:
        return ["motivation_gaps 必须是非空数组"]
    known_chars = set(ctx.识别角色) | {"主角", "他", "她"}
    for idx, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            errors.append(f"motivation_gaps[{idx}] 必须是对象")
            continue
        char = str(gap.get("character", "")).strip()
        if char and char not in known_chars and char not in corpus:
            errors.append(f"motivation_gaps[{idx}] character 无法在上下文中定位")
        quote = str(gap.get("behavior_quote", "")).strip()
        if not quote or not 摘句在语料中(quote, corpus):
            errors.append(f"motivation_gaps[{idx}] behavior_quote 无法在正文中定位")
        if not str(gap.get("missing_link", "")).strip():
            errors.append(f"motivation_gaps[{idx}] 缺少 missing_link")
        if any(f in str(gap.get("missing_link", "")) for f in _FORBIDDEN):
            errors.append(f"motivation_gaps[{idx}] missing_link 过于空泛")
    for action in parsed.get("fix_actions") or []:
        if any(f in str(action) for f in _FORBIDDEN):
            errors.append(f"修复动作过于空泛：{action}")
    if "增强人物" in json.dumps(parsed, ensure_ascii=False):
        errors.append("响应命中禁止空泛表达")
    return errors
