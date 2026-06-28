from __future__ import annotations

from typing import Any

from 证据索引 import (
    ROLE_CHAPTER_ACTION,
    ROLE_CHAPTER_META,
    ROLE_FAILURE_INPUT,
    ROLE_SETTING_RULE,
    SETTING_RESPONSE_SCHEMA,
    SOURCE_CHAPTER,
    SOURCE_FAILURE_EVIDENCE,
    SOURCE_IR,
    SOURCE_PROJECT_RULE,
    读取源文件摘句,
    证据条目,
)
from 设定上下文 import 设定上下文
from 设定模型 import 设定诊断结果
from 验收禁止词 import 命中禁止词

_FORBIDDEN = ("加强设定", "增强设定差异", "加强设定差异")
_CONFLICT_WORDS = ("硬冲突", "source_a", "source_b", "一致性冲突")

_RULE_SOURCE_TYPES = frozenset({SOURCE_IR, SOURCE_PROJECT_RULE, SOURCE_CHAPTER})
_ACTION_ROLES = frozenset({ROLE_CHAPTER_ACTION, ROLE_CHAPTER_META, ROLE_FAILURE_INPUT})


def _是旧版响应(parsed: dict[str, Any]) -> bool:
    version = str(parsed.get("response_schema_version", "")).strip()
    if version == SETTING_RESPONSE_SCHEMA:
        return False
    for key in ("setting_pressure_points", "differentiation_points", "sustainable_variants"):
        items = parsed.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("evidence_ids"):
                return False
            if item.get("quote") or item.get("rule_or_setting") or item.get("choice_pressure"):
                return True
    if str(parsed.get("sustainable_variant", "")).strip():
        return True
    return False


def _分析字段(parsed: dict[str, Any]) -> str:
    parts = [str(parsed.get("root_cause", "")), str(parsed.get("sustainable_variant", ""))]
    for action in parsed.get("fix_actions") or []:
        parts.append(str(action))
    for item in parsed.get("acceptance_criteria") or []:
        parts.append(str(item))
    for point in parsed.get("setting_pressure_points") or []:
        if isinstance(point, dict):
            parts.extend(
                [
                    str(point.get("setting", "")),
                    str(point.get("analysis", "")),
                    str(point.get("repair_direction", "")),
                    str(point.get("problem_type", "")),
                ]
            )
    for item in parsed.get("differentiation_points") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("description", "")))
            parts.append(str(item.get("contrast_with_convention", "")))
    for item in parsed.get("sustainable_variants") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("variant", "")))
            parts.append(str(item.get("repeatable_mechanism", "")))
    return " ".join(parts)


def _校验证据ID(
    ctx: 设定上下文,
    evidence_id: str,
    *,
    field: str,
    declared_source_type: str | None = None,
) -> list[str]:
    errors: list[str] = []
    entry = ctx.证据表.get(evidence_id)
    if not entry:
        return [f"EVIDENCE_ID_INVALID: {field} 引用不存在的 evidence_id {evidence_id}"]
    if declared_source_type and entry.source_type != declared_source_type:
        errors.append(
            f"EVIDENCE_SOURCE_MISMATCH: {field} 声明来源 {declared_source_type} 与索引 {entry.source_type} 不一致"
        )
    source_text = 读取源文件摘句(ctx.案例根目录, entry)
    if source_text is None:
        errors.append(f"EVIDENCE_SOURCE_MISMATCH: {field} 源文件不可读或越界 {entry.source_path}")
    elif entry.quote not in source_text:
        errors.append(f"EVIDENCE_QUOTE_MISMATCH: {field} 摘句与源文件不一致")
    return errors


def _收集证据ID列表(raw: dict[str, Any], field: str) -> list[str]:
    ids = raw.get("evidence_ids")
    if isinstance(ids, list):
        return [str(x).strip() for x in ids if str(x).strip()]
    single = str(raw.get("evidence_id", "")).strip()
    return [single] if single else []


def 校验设定证据引用(parsed: dict[str, Any], ctx: 设定上下文) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    validated: list[dict[str, Any]] = []
    quotes = parsed.get("evidence_quotes")
    if not isinstance(quotes, list) or not quotes:
        errors.append("evidence_quotes 必须是非空数组")
        return validated, errors
    for idx, item in enumerate(quotes):
        if not isinstance(item, dict):
            errors.append(f"evidence_quotes[{idx}] 必须是对象")
            continue
        eid = str(item.get("evidence_id", "")).strip()
        if eid:
            errors.extend(_校验证据ID(ctx, eid, field=f"evidence_quotes[{idx}]"))
            entry = ctx.证据表.get(eid)
            if entry:
                validated.append(
                    {
                        "evidence_id": eid,
                        "paragraph": entry.paragraph or item.get("paragraph"),
                        "quote": entry.quote,
                    }
                )
            else:
                validated.append({"evidence_id": eid})
        else:
            quote = str(item.get("quote", "")).strip()
            if not quote:
                errors.append(f"evidence_quotes[{idx}] 需要 evidence_id 或 quote")
            else:
                matched = [
                    e
                    for e in ctx.证据表.values()
                    if e.source_type == SOURCE_CHAPTER and quote in e.quote
                ]
                if not matched:
                    errors.append(f"EVIDENCE_QUOTE_MISMATCH: evidence_quotes[{idx}] 无法在章节索引中定位")
                else:
                    validated.append({"paragraph": item.get("paragraph"), "quote": quote})
    return validated, errors


def 校验设定通用字段(parsed: dict[str, Any]) -> list[str]:
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
    return errors


def 校验设定响应(parsed: dict[str, Any], ctx: 设定上下文, diagnosis: 设定诊断结果) -> list[str]:
    if _是旧版响应(parsed):
        return ["LEGACY_SETTING_EVIDENCE_UNSUPPORTED_IN_R5C"]

    errors = 校验设定通用字段(parsed)
    if str(parsed.get("response_schema_version", "")).strip() != SETTING_RESPONSE_SCHEMA:
        errors.append(f"response_schema_version 必须是 {SETTING_RESPONSE_SCHEMA}")

    points = parsed.get("setting_pressure_points")
    if not isinstance(points, list) or not points:
        errors.append("setting_pressure_points 必须是非空数组")
    else:
        for idx, point in enumerate(points):
            if not isinstance(point, dict):
                errors.append(f"setting_pressure_points[{idx}] 必须是对象")
                continue
            problem_type = str(point.get("problem_type", "")).strip()
            if not problem_type:
                errors.append(f"setting_pressure_points[{idx}] 缺少 problem_type")
            ids = _收集证据ID列表(point, f"setting_pressure_points[{idx}]")
            if not ids:
                errors.append(f"EVIDENCE_ID_INVALID: setting_pressure_points[{idx}] 缺少 evidence_ids")
                continue
            rule_sources: list[证据条目] = []
            action_sources: list[证据条目] = []
            for eid in ids:
                errors.extend(_校验证据ID(ctx, eid, field=f"setting_pressure_points[{idx}]"))
                entry = ctx.证据表.get(eid)
                if not entry:
                    continue
                if entry.source_type in _RULE_SOURCE_TYPES and entry.source_role == ROLE_SETTING_RULE:
                    rule_sources.append(entry)
                elif entry.source_type == SOURCE_IR or entry.source_type == SOURCE_PROJECT_RULE:
                    rule_sources.append(entry)
                if entry.source_role in _ACTION_ROLES or entry.source_type == SOURCE_CHAPTER:
                    if entry.source_role != ROLE_SETTING_RULE:
                        action_sources.append(entry)
            if problem_type == "RULE_DOES_NOT_PRESS_CHOICE":
                if not rule_sources:
                    errors.append(
                        f"EVIDENCE_ID_INVALID: setting_pressure_points[{idx}] 需要规则/设定来源证据"
                    )
                if not action_sources:
                    errors.append(f"CHOICE_PRESSURE_NOT_DEMONSTRATED: setting_pressure_points[{idx}] 缺少章节行为证据")
            if not str(point.get("analysis", "")).strip():
                errors.append(f"setting_pressure_points[{idx}] 缺少 analysis")
            if not str(point.get("repair_direction", "")).strip():
                errors.append(f"setting_pressure_points[{idx}] 缺少 repair_direction")

    variants = parsed.get("sustainable_variants")
    if isinstance(variants, list) and variants:
        for idx, item in enumerate(variants):
            if not isinstance(item, dict):
                errors.append(f"sustainable_variants[{idx}] 必须是对象")
                continue
            ids = _收集证据ID列表(item, f"sustainable_variants[{idx}]")
            if not ids:
                errors.append(f"EVIDENCE_ID_INVALID: sustainable_variants[{idx}] 缺少 evidence_ids")
            for eid in ids:
                errors.extend(_校验证据ID(ctx, eid, field=f"sustainable_variants[{idx}]"))
            if not str(item.get("variant", "")).strip() or not str(item.get("repeatable_mechanism", "")).strip():
                errors.append(f"sustainable_variants[{idx}] 必须给出变体与可重复机制")

    diffs = parsed.get("differentiation_points")
    if isinstance(diffs, list) and diffs:
        for idx, item in enumerate(diffs):
            if not isinstance(item, dict):
                errors.append(f"differentiation_points[{idx}] 必须是对象")
                continue
            ids = _收集证据ID列表(item, f"differentiation_points[{idx}]")
            if not ids:
                errors.append(f"EVIDENCE_ID_INVALID: differentiation_points[{idx}] 缺少 evidence_ids")
            for eid in ids:
                errors.extend(_校验证据ID(ctx, eid, field=f"differentiation_points[{idx}]"))
            if not str(item.get("description", "")).strip():
                errors.append(f"differentiation_points[{idx}] 缺少 description")

    analytic = _分析字段(parsed)
    if any(w in analytic for w in _CONFLICT_WORDS):
        if not parsed.get("needs_reroute"):
            errors.append("设定与正文冲突应设置 needs_reroute=true 并转交 L2-06")
    for f in _FORBIDDEN:
        if f in analytic:
            errors.append(f"命中禁止空泛表达：{f}")
    for f in 命中禁止词(analytic):
        errors.append(f"命中禁止硬编码表达：{f}")

    return errors


def 提取校验错误类型(errors: list[str]) -> str:
    for code in (
        "EVIDENCE_ID_INVALID",
        "EVIDENCE_SOURCE_MISMATCH",
        "EVIDENCE_QUOTE_MISMATCH",
        "CHOICE_PRESSURE_NOT_DEMONSTRATED",
    ):
        if any(code in e for e in errors):
            return code
    if any("LEGACY_SETTING_EVIDENCE_UNSUPPORTED_IN_R5C" in e for e in errors):
        return "EVIDENCE_INVALID"
    return "EVIDENCE_INVALID"
