from __future__ import annotations

from typing import Any

from 一致性上下文 import 一致性上下文
from 事实模型 import 一致性诊断结果, 来源引用
from 事实索引 import CONSISTENCY_RESPONSE_SCHEMA, 协议到来源类型
from 属性归一 import 归一化属性

_STYLE_CONFLICT = ("文风", "语气", "态度变化")
_VALID_CLASSIFICATIONS = frozenset(
    {
        "HARD_CONFLICT",
        "EXPLANATION_INSUFFICIENT",
        "ALLOWED_CHANGE",
        "EVIDENCE_INSUFFICIENT",
        "硬冲突",
    }
)
_CLASSIFICATION_ALIASES = {"硬冲突": "HARD_CONFLICT"}


def _规范化分类(raw: str) -> str:
    text = str(raw or "HARD_CONFLICT").strip()
    return _CLASSIFICATION_ALIASES.get(text, text)


def _is_legacy_response(parsed: dict[str, Any]) -> bool:
    conflicts = parsed.get("consistency_conflicts")
    if not isinstance(conflicts, list):
        return False
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        if conflict.get("fact_pair_id"):
            continue
        if conflict.get("entity") or conflict.get("attribute") or conflict.get("source_a"):
            return True
    return False


def _fact_to_source_ref(fact) -> 来源引用:
    return 来源引用(
        str(fact.来源类型),
        str(fact.摘句),
        int(fact.段落 or 0),
        str(fact.来源路径 or ""),
    )


def 解析ID冲突(parsed: dict[str, Any], ctx: 一致性上下文) -> list:
    from 事实模型 import 一致性冲突

    conflicts = []
    for raw in parsed.get("consistency_conflicts") or []:
        if not isinstance(raw, dict):
            continue
        pair_id = str(raw.get("fact_pair_id", "")).strip()
        sa_id = str(raw.get("source_a_fact_id", "")).strip()
        sb_id = str(raw.get("source_b_fact_id", "")).strip()
        pair = ctx.索引事实对表.get(pair_id)
        fact_a = ctx.索引事实表.get(sa_id)
        fact_b = ctx.索引事实表.get(sb_id)
        if not pair or not fact_a:
            continue
        classification = _规范化分类(str(raw.get("classification", "HARD_CONFLICT")))
        sb_ref = 来源引用("正文", "", 0, "")
        if fact_b:
            sb_ref = _fact_to_source_ref(fact_b)
        conflicts.append(
            一致性冲突(
                conflict_type="事实",
                实体=str(fact_a.实体),
                属性=str(fact_a.属性),
                source_a=_fact_to_source_ref(fact_a),
                source_b=sb_ref,
                分类=classification,
            )
        )
    return conflicts


def 校验双来源(
    parsed: dict[str, Any],
    corpus: str,
    ctx: 一致性上下文,
    diagnosis: 一致性诊断结果,
) -> list[str]:
    del corpus, diagnosis
    errors: list[str] = []

    if _is_legacy_response(parsed):
        return [f"LEGACY_RESPONSE_UNSUPPORTED_IN_R5B：需使用 {CONSISTENCY_RESPONSE_SCHEMA} 的 fact_id 引用"]

    conflicts = parsed.get("consistency_conflicts")
    if not isinstance(conflicts, list) or not conflicts:
        return ["consistency_conflicts 必须是非空数组"]

    for idx, conflict in enumerate(conflicts):
        if not isinstance(conflict, dict):
            errors.append(f"consistency_conflicts[{idx}] 必须是对象")
            continue

        pair_id = str(conflict.get("fact_pair_id", "")).strip()
        sa_id = str(conflict.get("source_a_fact_id", "")).strip()
        sb_id = str(conflict.get("source_b_fact_id", "")).strip()
        classification = _规范化分类(str(conflict.get("classification", "HARD_CONFLICT")))
        if classification not in _VALID_CLASSIFICATIONS:
            errors.append(f"consistency_conflicts[{idx}] classification 无效")

        if classification == "EVIDENCE_INSUFFICIENT":
            if not sa_id or sa_id not in ctx.索引事实表:
                errors.append(f"consistency_conflicts[{idx}] EVIDENCE_INSUFFICIENT 需要有效 source_a_fact_id")
            if not str(conflict.get("reason", "")).strip():
                errors.append(f"consistency_conflicts[{idx}] EVIDENCE_INSUFFICIENT 必须说明缺少的来源类型")
            if pair_id:
                if pair_id not in ctx.索引事实对表:
                    errors.append(f"consistency_conflicts[{idx}] fact_pair_id 不存在：{pair_id}")
                else:
                    pair = ctx.索引事实对表[pair_id]
                    expected_sa = str(pair.get("source_a_fact_id", ""))
                    expected_sb = str(pair.get("source_b_fact_id", ""))
                    if sa_id and sa_id != expected_sa:
                        errors.append(
                            f"consistency_conflicts[{idx}] source fact_id 与 fact_pair 不匹配"
                        )
                    if sb_id and sb_id != expected_sb:
                        errors.append(
                            f"consistency_conflicts[{idx}] source fact_id 与 fact_pair 不匹配"
                        )
            continue

        if not pair_id:
            errors.append(f"consistency_conflicts[{idx}] 缺少 fact_pair_id")
            continue
        if pair_id not in ctx.索引事实对表:
            errors.append(f"consistency_conflicts[{idx}] fact_pair_id 不存在：{pair_id}")
            continue

        pair = ctx.索引事实对表[pair_id]
        expected_sa = str(pair.get("source_a_fact_id", ""))
        expected_sb = str(pair.get("source_b_fact_id", ""))
        if sa_id != expected_sa or sb_id != expected_sb:
            errors.append(
                f"consistency_conflicts[{idx}] source fact_id 与 fact_pair 不匹配"
            )

        if sa_id not in ctx.索引事实表:
            errors.append(f"consistency_conflicts[{idx}] source_a_fact_id 不存在")
        if sb_id and sb_id not in ctx.索引事实表:
            errors.append(f"consistency_conflicts[{idx}] source_b_fact_id 不存在")
        if sa_id and sb_id and sa_id == sb_id:
            errors.append(f"consistency_conflicts[{idx}] 双来源 fact_id 不能相同")

        if sa_id in ctx.索引事实表 and sb_id in ctx.索引事实表:
            fa = ctx.索引事实表[sa_id]
            fb = ctx.索引事实表[sb_id]
            if 归一化属性(fa.属性) != 归一化属性(fb.属性):
                errors.append(f"consistency_conflicts[{idx}] 双 fact 属性不一致")
            if fa.实体 != fb.实体:
                errors.append(f"consistency_conflicts[{idx}] 双 fact 实体不一致")

        display = str(conflict.get("entity", "")) + str(conflict.get("attribute", ""))
        if any(w in display for w in _STYLE_CONFLICT):
            errors.append(f"consistency_conflicts[{idx}] 不得把文风/态度变化判为系统冲突")

    return errors
