from __future__ import annotations

from typing import Any

from 一致性上下文 import 一致性上下文
from 事实模型 import 一致性诊断结果
from 通用证据定位 import 摘句在语料中

_STYLE_CONFLICT = ("文风", "语气", "态度变化")


def 校验双来源(parsed: dict[str, Any], corpus: str, ctx: 一致性上下文, diagnosis: 一致性诊断结果) -> list[str]:
    errors: list[str] = []
    conflicts = parsed.get("consistency_conflicts")
    if not isinstance(conflicts, list) or not conflicts:
        return ["consistency_conflicts 必须是非空数组"]
    all_quotes = corpus
    for ir in ctx.IR事实:
        all_quotes += ir.摘句
    for prior in ctx.前序章节事实:
        all_quotes += prior.摘句
    for idx, conflict in enumerate(conflicts):
        if not isinstance(conflict, dict):
            errors.append(f"consistency_conflicts[{idx}] 必须是对象")
            continue
        if any(w in str(conflict.get("conflict_type", "")) for w in _STYLE_CONFLICT):
            errors.append(f"consistency_conflicts[{idx}] 不得把文风/态度变化判为系统冲突")
        entity = str(conflict.get("entity", "")).strip()
        attr = str(conflict.get("attribute", "")).strip()
        if not entity or not attr:
            errors.append(f"consistency_conflicts[{idx}] 必须指定同一实体与属性")
        for side in ("source_a", "source_b"):
            block = conflict.get(side)
            if not isinstance(block, dict):
                errors.append(f"consistency_conflicts[{idx}] 缺少 {side}")
                continue
            quote = str(block.get("quote", "")).strip()
            if not quote:
                errors.append(f"consistency_conflicts[{idx}] {side}.quote 不能为空")
            elif not 摘句在语料中(quote, all_quotes):
                errors.append(f"consistency_conflicts[{idx}] {side}.quote 无法在来源中定位")
        sa = conflict.get("source_a") or {}
        sb = conflict.get("source_b") or {}
        if sa.get("quote") == sb.get("quote") and sa.get("source_type") == sb.get("source_type"):
            errors.append(f"consistency_conflicts[{idx}] 双来源不能相同")
        classification = str(conflict.get("classification", "硬冲突"))
        if classification == "硬冲突" and not (sa and sb):
            errors.append(f"consistency_conflicts[{idx}] 硬冲突需要完整双来源")
    if len(conflicts) == 1 and not conflicts[0].get("source_b"):
        errors.append("单一来源不得生成冲突修复单")
    return errors
