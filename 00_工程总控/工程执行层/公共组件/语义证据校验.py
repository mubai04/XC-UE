from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from 证据语料 import 规范化证据文本

REQUIRED_DIMENSIONS = ("因果", "动机", "冲突", "读者收益", "认知成本", "章末追读")
ALLOWED_VERDICTS = frozenset({"PASS", "FAIL", "REVIEW"})
SCOPE_CURRENT = "CURRENT_CHAPTER"
SCOPE_PRIOR = "PRIOR_CHAPTER"
ALLOWED_SCOPES = frozenset({SCOPE_CURRENT, SCOPE_PRIOR})
PARAGRAPH_ID_PATTERN = re.compile(r"^P\d{4}$")
MAX_EVIDENCE_PER_DIMENSION = 3

FORBIDDEN_LEGACY_FIELDS = ("overall", "score", "explanation", "evidence_quotes", "quotes")
VAGUE_FINAL_REASON_PHRASES = ("情节清晰", "信息丰富", "容易理解", "叙事流畅", "描写生动")
GENERIC_BOILERPLATE_MARKERS = (
    "整体表现",
    "表现良好",
    "表现较好",
    "整体较好",
    "没有明显问题",
    "未发现明显问题",
    "没有发现明显问题",
    "该维度通过",
    "该部分基本完整",
    "基本符合",
    "表现正常",
    "可以通过",
    "内容比较完整",
    "较为合理",
    "满足基本要求",
    "总体正常",
    "可以判定通过",
    "处理总体正常",
    "基本完整",
    "相关内容较为合理",
    "整体来看",
    "在这一维度上的处理总体正常",
    "本章在这一维度",
)
SPECIFIC_SUBJECT_MARKERS = (
    "主角",
    "他",
    "她",
    "主管",
    "双方",
    "角色",
    "人物",
    "总监",
    "大楼",
    "设计图",
    "读者",
    "章末",
    "全章",
)
SPECIFIC_RELATION_MARKERS = (
    "一致",
    "漂移",
    "矛盾",
    "冲突",
    "对立",
    "立场",
    "坚持",
    "无法同时",
    "疑问",
    "悬念",
    "承接",
    "备案",
    "加班",
    "离开",
    "要求",
    "目标",
    "职位",
    "公开",
)
SPECIFIC_CAUSE_RESULT_MARKERS = ("起因", "结果", "导致", "因此", "从而", "因为", "由于", "使")
PHENOMENON_KEYWORDS = (
    "重复",
    "主体",
    "切换",
    "事件增量",
    "支线",
    "规则",
    "兑现",
    "章末",
    "承接",
    "空转",
    "回读",
    "因果",
    "起因",
    "行动",
    "结果",
    "冲突",
    "动机",
    "悬念",
    "钩子",
    "信息",
    "专名",
    "对话",
    "场景",
)


@dataclass
class 已校验证据:
    dimension: str
    paragraph_id: str
    exact_text: str
    source_scope: str
    occurrence_index: int
    start_offset: int
    end_offset: int
    evidence_rationale: str = ""
    legacy_paragraph: int | None = None
    repaired: bool = False


@dataclass
class 维度校验报告:
    dimension: str
    evidence_location_valid: bool
    evidence_protocol_compliant: bool
    evidence_semantically_sufficient: bool
    strength_summary: str
    risk_summary: str
    final_reason: str
    evidence_rationale: str
    verdict: str = ""
    semantic_support: None = None


@dataclass
class 证据校验结果:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validated_evidence: list[已校验证据] = field(default_factory=list)
    computed_overall: str = ""
    failed_dimensions: list[str] = field(default_factory=list)
    dimension_reports: list[维度校验报告] = field(default_factory=list)
    anchor_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    location_failed_dimensions: list[str] = field(default_factory=list)


def 计算整体结论(verdicts: list[str]) -> str:
    normalized = [str(v).upper() for v in verdicts]
    if any(v == "FAIL" for v in normalized):
        return "FAIL"
    if any(v == "REVIEW" for v in normalized):
        return "REVIEW"
    return "PASS"


def 段落ID合法(paragraph_id: str) -> bool:
    return bool(PARAGRAPH_ID_PATTERN.match(paragraph_id))


def 规范化摘句(text: str) -> str:
    return 规范化证据文本(text)


def exact_text含省略号(exact_text: str) -> bool:
    return "..." in exact_text or "…" in exact_text or "。。。" in exact_text


def 校验exact_text协议(exact_text: str) -> str | None:
    if not exact_text or not exact_text.strip():
        return "exact_text 不能为空"
    if exact_text含省略号(exact_text):
        return "exact_text 不得包含省略号或截断标记"
    if "\n" in exact_text:
        return "exact_text 不得跨越换行符（请摘单行）"
    if "\n\n" in exact_text:
        return "exact_text 不得跨段拼接（含空行）"
    return None


def 定位摘句(text: str, exact_text: str, occurrence_index: int = 0) -> tuple[int, int] | None:
    protocol_err = 校验exact_text协议(exact_text)
    if protocol_err:
        return None
    norm_text = 规范化摘句(text)
    norm_exact = 规范化摘句(exact_text)
    if not norm_exact:
        return None
    start = 0
    found = 0
    while True:
        idx = norm_text.find(norm_exact, start)
        if idx < 0:
            return None
        if found == occurrence_index:
            return idx, idx + len(norm_exact)
        found += 1
        start = idx + 1


def 收集锚定诊断(
    *,
    dimension: str,
    paragraph_id: str,
    exact_text: str,
    source_scope: str,
    occurrence_index: int,
    corpus: dict[str, str],
) -> dict[str, Any]:
    """诊断锚定失败，不含业务结论。"""
    info: dict[str, Any] = {
        "dimension": dimension,
        "paragraph_id": paragraph_id,
        "exact_text_length": len(exact_text),
        "exact_text_preview": exact_text[:120],
        "source_scope": source_scope,
        "occurrence_index": occurrence_index,
        "protocol_error": 校验exact_text协议(exact_text),
    }
    if paragraph_id in corpus:
        para = corpus[paragraph_id]
        info["paragraph_text_length"] = len(para)
        span = 定位摘句(para, exact_text, occurrence_index)
        info["in_declared_paragraph"] = span is not None
    else:
        info["in_declared_paragraph"] = False
        info["paragraph_id_missing"] = True
    matches = _collect_scope_matches(corpus, exact_text)
    info["scope_match_count"] = len(matches)
    info["scope_matches"] = [
        {"paragraph_id": pid, "start": s, "end": e} for pid, s, e in matches[:5]
    ]
    return info


def _legacy_paragraph_number(paragraph_id: str) -> int | None:
    if not 段落ID合法(paragraph_id):
        return None
    return int(paragraph_id[1:])


def _sorted_paragraph_ids(corpus: dict[str, str]) -> list[str]:
    return sorted(corpus.keys(), key=lambda pid: int(pid[1:]))


def _last_twenty_percent_ids(corpus: dict[str, str]) -> set[str]:
    ids = _sorted_paragraph_ids(corpus)
    if not ids:
        return set()
    start_idx = max(0, int(len(ids) * 0.8))
    return set(ids[start_idx:])


def _collect_scope_matches(corpus: dict[str, str], exact_text: str) -> list[tuple[str, int, int]]:
    if 校验exact_text协议(exact_text):
        return []
    matches: list[tuple[str, int, int]] = []
    for paragraph_id in _sorted_paragraph_ids(corpus):
        text = corpus[paragraph_id]
        occ = 0
        while True:
            found = 定位摘句(text, exact_text, occ)
            if found is None:
                break
            matches.append((paragraph_id, found[0], found[1]))
            occ += 1
    return matches


def _paragraph_occurrence_count(text: str, exact_text: str) -> int:
    count = 0
    while 定位摘句(text, exact_text, count) is not None:
        count += 1
    return count


def _resolve_evidence(
    *,
    dimension: str,
    paragraph_id: str,
    exact_text: str,
    source_scope: str,
    occurrence_index: int,
    corpus: dict[str, str],
) -> tuple[已校验证据 | None, str | None, str | None]:
    """严格位置合同：仅在指定 paragraph_id 段内校验，不得全章搜索后自动修复。"""
    if paragraph_id not in corpus:
        return (
            None,
            f"{dimension}: PARAGRAPH_NOT_FOUND {paragraph_id} 不在 {source_scope} 语料中",
            None,
        )

    para_text = corpus[paragraph_id]
    span = 定位摘句(para_text, exact_text, occurrence_index)
    if span is not None:
        start_offset, end_offset = span
        return (
            已校验证据(
                dimension=dimension,
                paragraph_id=paragraph_id,
                exact_text=exact_text,
                source_scope=source_scope,
                occurrence_index=occurrence_index,
                start_offset=start_offset,
                end_offset=end_offset,
                legacy_paragraph=_legacy_paragraph_number(paragraph_id),
                repaired=False,
            ),
            None,
            None,
        )

    if _paragraph_occurrence_count(para_text, exact_text) == 0:
        return (
            None,
            f"{dimension}: EXACT_TEXT_NOT_IN_PARAGRAPH {paragraph_id}",
            None,
        )
    return (
        None,
        f"{dimension}: OCCURRENCE_INDEX_INVALID occurrence_index={occurrence_index} 在 {paragraph_id} 中越界",
        None,
    )


def _analysis_summary_complete(text: str) -> bool:
    if len(text) < 24:
        return False
    has_positive = any(token in text for token in ("优点", "优势", "成立", "有效", "清晰"))
    has_risk = any(token in text for token in ("风险", "问题", "不足", "重复", "回读", "空转", "不清"))
    has_decision = any(token in text for token in ("PASS", "REVIEW", "FAIL", "通过", "复核", "失败", "最终"))
    return has_positive and has_risk and has_decision


def _has_specific_semantic_content(text: str) -> bool:
    """是否表达可识别的具体判断对象、状态、行为、目标、关系或章节现象。"""
    if not text.strip():
        return False
    if any(keyword in text for keyword in PHENOMENON_KEYWORDS):
        return True
    if re.search(r"[（(][^）)]{2,}[）)]", text):
        return True
    if "→" in text or "->" in text:
        return True
    has_subject = any(marker in text for marker in SPECIFIC_SUBJECT_MARKERS)
    has_relation = any(marker in text for marker in SPECIFIC_RELATION_MARKERS)
    if has_subject and has_relation:
        return True
    has_cause = any(marker in text for marker in SPECIFIC_CAUSE_RESULT_MARKERS)
    if has_subject and has_cause:
        return True
    return False


def _is_generic_boilerplate(text: str) -> bool:
    """通用套话：缺少具体对象/关系/状态，且命中空泛或模板化表述。"""
    if not text.strip():
        return True
    if any(phrase in text for phrase in VAGUE_FINAL_REASON_PHRASES):
        return True
    if not any(marker in text for marker in GENERIC_BOILERPLATE_MARKERS):
        return False
    return not _has_specific_semantic_content(text)


def _is_dimension_label_only(text: str) -> bool:
    stripped = text.strip()
    for name in REQUIRED_DIMENSIONS:
        if not stripped.startswith(name):
            continue
        remainder = stripped[len(name) :].lstrip("维度方面层面上的")
        if not remainder or _is_generic_boilerplate(remainder):
            return True
        if not _has_specific_semantic_content(remainder):
            return True
    return False


def _final_reason_specific(final_reason: str, *, analysis_summary: str = "") -> bool:
    """具体性合同：综合 final_reason 与 analysis_summary，不要求字面命中现象词表。"""
    reason = final_reason.strip()
    summary = analysis_summary.strip()
    combined = f"{reason}\n{summary}".strip()
    if not combined:
        return False
    if _is_dimension_label_only(reason):
        return False
    if reason and _is_generic_boilerplate(reason):
        return False
    if reason and _has_specific_semantic_content(reason):
        return True
    if summary and _has_specific_semantic_content(summary) and not _is_generic_boilerplate(summary):
        return True
    return _has_specific_semantic_content(combined) and not _is_generic_boilerplate(combined)


def _因果链条完整(final_reason: str, *, analysis_summary: str = "") -> bool:
    """语义槽位检查：不再要求 final_reason 字面含「行动」等固定词（避免误阻断）。"""
    combined = f"{final_reason}\n{analysis_summary}"
    has_cause = any(t in combined for t in ("起因", "因", "由于", "因为"))
    has_result = any(t in combined for t in ("结果", "导致", "因此", "从而"))
    has_action = any(
        t in combined
        for t in ("行动", "选择", "推进", "发生", "做出", "采取", "→", "然后", "随后", "接着")
    )
    return has_cause and has_action and has_result


def _reject_legacy_fields(parsed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in FORBIDDEN_LEGACY_FIELDS:
        if key in parsed:
            errors.append(f"响应不得包含已废弃字段 {key}")
    return errors


def _reject_legacy_dimension_fields(dim: dict[str, Any], name: str) -> list[str]:
    errors: list[str] = []
    for key in ("score", "explanation", "evidence_quotes", "quotes"):
        if key in dim:
            errors.append(f"{name}: 不得包含已废弃字段 {key}")
    return errors


def _validate_dimension_semantics(
    name: str,
    dim: dict[str, Any],
    *,
    verdict: str,
    resolved: 已校验证据 | None,
    evidence_rationale: str,
    current_paragraphs: dict[str, str],
) -> tuple[list[str], bool]:
    errors: list[str] = []
    strength_summary = str(dim.get("strength_summary", "")).strip()
    risk_summary = str(dim.get("risk_summary", "")).strip()
    final_reason = str(dim.get("final_reason", "")).strip()
    analysis_summary = str(dim.get("analysis_summary", "")).strip()

    if not strength_summary:
        errors.append(f"{name}: strength_summary 不能为空")
    if not risk_summary:
        errors.append(f"{name}: risk_summary 不能为空")
    if not final_reason:
        errors.append(f"{name}: final_reason 不能为空")
    if not evidence_rationale:
        errors.append(f"{name}: evidence_rationale 不能为空")
    if not _analysis_summary_complete(analysis_summary):
        errors.append(f"{name}: analysis_summary 必须同时说明优点、风险与最终结论")
    if final_reason and not _final_reason_specific(final_reason, analysis_summary=analysis_summary):
        errors.append(f"{name}: final_reason 过于空泛，必须引用具体全章现象类别")
    if name == "因果" and verdict == "PASS" and not _因果链条完整(final_reason, analysis_summary=analysis_summary):
        errors.append(f"{name}: 因果 PASS 时须在 final_reason 或 analysis_summary 中表达起因、行动、结果语义槽位")
    if name == "章末追读" and resolved is not None:
        last_ids = _last_twenty_percent_ids(current_paragraphs)
        if resolved.paragraph_id not in last_ids:
            errors.append(f"{name}: 章末追读 evidence 必须来自当章最后 20% 段落")
    if resolved and evidence_rationale and len(evidence_rationale.strip()) < 8:
        errors.append(f"{name}: evidence_rationale 过短，无法说明摘句与结论的关系")

    sufficient = not errors and resolved is not None
    return errors, sufficient


def 校验语义审计响应(
    parsed: dict[str, Any],
    *,
    current_paragraphs: dict[str, str],
    prior_paragraphs: dict[str, str] | None = None,
) -> 证据校验结果:
    prior = prior_paragraphs or {}
    errors = _reject_legacy_fields(parsed)
    dimensions = parsed.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return 证据校验结果(ok=False, errors=errors or ["响应缺少 dimensions 数组"])

    names = [str(dim.get("name", "")) for dim in dimensions if isinstance(dim, dict)]
    if len(names) != len(REQUIRED_DIMENSIONS):
        errors.append("dimensions 必须且只能包含 6 个维度")
    if set(names) != set(REQUIRED_DIMENSIONS):
        errors.append(f"维度必须且只能为：{', '.join(REQUIRED_DIMENSIONS)}")
    if len(names) != len(set(names)):
        errors.append("dimensions 存在重复维度")

    warnings: list[str] = []
    validated: list[已校验证据] = []
    verdicts: list[str] = []
    failed_dimensions: list[str] = []
    location_failed_dimensions: list[str] = []
    dimension_reports: list[维度校验报告] = []
    anchor_diagnostics: list[dict[str, Any]] = []

    for dim in dimensions:
        if not isinstance(dim, dict):
            errors.append("dimensions 项必须是对象")
            continue
        name = str(dim.get("name", ""))
        dim_errors_before = len(errors)
        errors.extend(_reject_legacy_dimension_fields(dim, name))
        verdict = str(dim.get("verdict", "")).upper()
        verdicts.append(verdict)
        if verdict not in ALLOWED_VERDICTS:
            errors.append(f"{name}: verdict 非法")

        analysis_summary = str(dim.get("analysis_summary", "")).strip()
        if not analysis_summary:
            errors.append(f"{name}: analysis_summary 不能为空")

        evidence_items = dim.get("evidence")
        resolved: 已校验证据 | None = None
        evidence_rationale = ""
        location_valid = False

        if not isinstance(evidence_items, list) or not evidence_items:
            errors.append(f"{name}: 所有 verdict 必须提供 evidence")
        elif len(evidence_items) > MAX_EVIDENCE_PER_DIMENSION:
            errors.append(f"{name}: evidence 最多 {MAX_EVIDENCE_PER_DIMENSION} 条")
        else:
            corpus_base = current_paragraphs
            dim_resolved: list[已校验证据] = []
            for idx, item in enumerate(evidence_items):
                label = f"evidence[{idx}]"
                if not isinstance(item, dict):
                    errors.append(f"{name}: {label} 必须是对象")
                    continue
                paragraph_id = str(item.get("paragraph_id", "")).strip()
                exact_text = str(item.get("exact_text", ""))
                source_scope = str(item.get("source_scope", SCOPE_CURRENT)).strip()
                occurrence_raw = item.get("occurrence_index", 0)
                item_rationale = str(item.get("evidence_rationale", "")).strip()
                if idx == 0:
                    evidence_rationale = item_rationale
                if not 段落ID合法(paragraph_id):
                    errors.append(f"{name}: {label} paragraph_id 必须是 P0001 格式")
                elif not exact_text:
                    errors.append(f"{name}: {label} exact_text 不能为空")
                elif (proto_err := 校验exact_text协议(exact_text)):
                    errors.append(f"{name}: {proto_err}")
                    location_failed_dimensions.append(name)
                    anchor_diagnostics.append(
                        收集锚定诊断(
                            dimension=name,
                            paragraph_id=paragraph_id if 段落ID合法(paragraph_id) else "",
                            exact_text=exact_text,
                            source_scope=source_scope if source_scope in ALLOWED_SCOPES else SCOPE_CURRENT,
                            occurrence_index=int(occurrence_raw) if isinstance(occurrence_raw, int) else 0,
                            corpus=current_paragraphs if source_scope != SCOPE_PRIOR else prior,
                        )
                    )
                elif source_scope not in ALLOWED_SCOPES:
                    errors.append(f"{name}: {label} source_scope 非法")
                elif isinstance(occurrence_raw, bool) or not isinstance(occurrence_raw, int) or occurrence_raw < 0:
                    errors.append(f"{name}: {label} occurrence_index 必须是非负整数")
                elif source_scope == SCOPE_PRIOR and not prior:
                    errors.append(f"{name}: {label} 引用 PRIOR_CHAPTER 但无前章语料")
                else:
                    corpus = current_paragraphs if source_scope == SCOPE_CURRENT else prior
                    item_resolved, err, warn = _resolve_evidence(
                        dimension=name,
                        paragraph_id=paragraph_id,
                        exact_text=exact_text,
                        source_scope=source_scope,
                        occurrence_index=occurrence_raw,
                        corpus=corpus,
                    )
                    if err:
                        errors.append(err)
                        location_failed_dimensions.append(name)
                        anchor_diagnostics.append(
                            收集锚定诊断(
                                dimension=name,
                                paragraph_id=paragraph_id,
                                exact_text=exact_text,
                                source_scope=source_scope,
                                occurrence_index=occurrence_raw,
                                corpus=corpus,
                            )
                        )
                    else:
                        assert item_resolved is not None
                        item_resolved.evidence_rationale = item_rationale
                        dim_resolved.append(item_resolved)
                        validated.append(item_resolved)
            if dim_resolved:
                resolved = dim_resolved[0]
                location_valid = True
                if analysis_summary == dim_resolved[0].exact_text:
                    warnings.append(f"{name}: analysis_summary 与 exact_text 相同，建议分离解读与摘句")

        semantic_errors, sufficient = _validate_dimension_semantics(
            name,
            dim,
            verdict=verdict,
            resolved=resolved if location_valid else None,
            evidence_rationale=evidence_rationale,
            current_paragraphs=current_paragraphs,
        )
        errors.extend(semantic_errors)

        protocol_compliant = location_valid and sufficient
        dimension_reports.append(
            维度校验报告(
                dimension=name,
                evidence_location_valid=location_valid,
                evidence_protocol_compliant=protocol_compliant,
                evidence_semantically_sufficient=protocol_compliant,
                strength_summary=str(dim.get("strength_summary", "")).strip(),
                risk_summary=str(dim.get("risk_summary", "")).strip(),
                final_reason=str(dim.get("final_reason", "")).strip(),
                evidence_rationale=evidence_rationale,
                verdict=verdict,
                semantic_support=None,
            )
        )

        if len(errors) > dim_errors_before and name in REQUIRED_DIMENSIONS and name not in failed_dimensions:
            failed_dimensions.append(name)

    computed = 计算整体结论(verdicts) if len(verdicts) == len(REQUIRED_DIMENSIONS) else ""
    return 证据校验结果(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        validated_evidence=validated,
        computed_overall=computed,
        failed_dimensions=failed_dimensions,
        dimension_reports=dimension_reports,
        anchor_diagnostics=anchor_diagnostics,
        location_failed_dimensions=list(dict.fromkeys(location_failed_dimensions)),
    )


def 摘句在正文中(quote: str, source_text: str) -> bool:
    if not quote or not quote.strip():
        return False
    return 定位摘句(source_text, quote, 0) is not None
