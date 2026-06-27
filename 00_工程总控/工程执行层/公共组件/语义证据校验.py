from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

REQUIRED_DIMENSIONS = ("因果", "动机", "冲突", "读者收益", "认知成本", "章末追读")
ALLOWED_VERDICTS = frozenset({"PASS", "FAIL", "REVIEW"})
SCOPE_CURRENT = "CURRENT_CHAPTER"
SCOPE_PRIOR = "PRIOR_CHAPTER"
ALLOWED_SCOPES = frozenset({SCOPE_CURRENT, SCOPE_PRIOR})
PARAGRAPH_ID_PATTERN = re.compile(r"^P\d{4}$")
MAX_EVIDENCE_PER_DIMENSION = 1

FORBIDDEN_LEGACY_FIELDS = ("overall", "score", "explanation", "evidence_quotes", "quotes")
VAGUE_FINAL_REASON_PHRASES = ("情节清晰", "信息丰富", "容易理解", "叙事流畅", "描写生动")
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


def 计算整体结论(verdicts: list[str]) -> str:
    normalized = [str(v).upper() for v in verdicts]
    if any(v == "FAIL" for v in normalized):
        return "FAIL"
    if any(v == "REVIEW" for v in normalized):
        return "REVIEW"
    return "PASS"


def 段落ID合法(paragraph_id: str) -> bool:
    return bool(PARAGRAPH_ID_PATTERN.match(paragraph_id))


def 定位摘句(text: str, exact_text: str, occurrence_index: int = 0) -> tuple[int, int] | None:
    if not exact_text:
        return None
    start = 0
    found = 0
    while True:
        idx = text.find(exact_text, start)
        if idx < 0:
            return None
        if found == occurrence_index:
            return idx, idx + len(exact_text)
        found += 1
        start = idx + 1


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
    matches: list[tuple[str, int, int]] = []
    for paragraph_id in _sorted_paragraph_ids(corpus):
        text = corpus[paragraph_id]
        start = 0
        while True:
            idx = text.find(exact_text, start)
            if idx < 0:
                break
            matches.append((paragraph_id, idx, idx + len(exact_text)))
            start = idx + 1
    return matches


def _resolve_evidence(
    *,
    dimension: str,
    paragraph_id: str,
    exact_text: str,
    source_scope: str,
    occurrence_index: int,
    corpus: dict[str, str],
) -> tuple[已校验证据 | None, str | None, str | None]:
    if paragraph_id in corpus:
        span = 定位摘句(corpus[paragraph_id], exact_text, occurrence_index)
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

    matches = _collect_scope_matches(corpus, exact_text)
    if not matches:
        return (None, f"{dimension}: exact_text 无法在 {source_scope} 语料中定位", None)
    if len(matches) == 1:
        resolved_id, start_offset, end_offset = matches[0]
        warning = f"{dimension}: PARAGRAPH_ID_REPAIRED {paragraph_id} -> {resolved_id}"
        return (
            已校验证据(
                dimension=dimension,
                paragraph_id=resolved_id,
                exact_text=exact_text,
                source_scope=source_scope,
                occurrence_index=0,
                start_offset=start_offset,
                end_offset=end_offset,
                legacy_paragraph=_legacy_paragraph_number(resolved_id),
                repaired=True,
            ),
            None,
            warning,
        )
    if occurrence_index < 0 or occurrence_index >= len(matches):
        return (
            None,
            f"{dimension}: exact_text 在 {source_scope} 多处匹配，occurrence_index={occurrence_index} 越界",
            None,
        )
    resolved_id, start_offset, end_offset = matches[occurrence_index]
    warning = None
    if resolved_id != paragraph_id:
        warning = f"{dimension}: PARAGRAPH_ID_REPAIRED {paragraph_id} -> {resolved_id}"
    return (
        已校验证据(
            dimension=dimension,
            paragraph_id=resolved_id,
            exact_text=exact_text,
            source_scope=source_scope,
            occurrence_index=occurrence_index,
            start_offset=start_offset,
            end_offset=end_offset,
            legacy_paragraph=_legacy_paragraph_number(resolved_id),
            repaired=warning is not None,
        ),
        None,
        warning,
    )


def _analysis_summary_complete(text: str) -> bool:
    if len(text) < 24:
        return False
    has_positive = any(token in text for token in ("优点", "优势", "成立", "有效", "清晰"))
    has_risk = any(token in text for token in ("风险", "问题", "不足", "重复", "回读", "空转", "不清"))
    has_decision = any(token in text for token in ("PASS", "REVIEW", "FAIL", "通过", "复核", "失败", "最终"))
    return has_positive and has_risk and has_decision


def _final_reason_specific(final_reason: str) -> bool:
    if any(phrase in final_reason for phrase in VAGUE_FINAL_REASON_PHRASES):
        return False
    return any(keyword in final_reason for keyword in PHENOMENON_KEYWORDS)


def _因果链条完整(final_reason: str) -> bool:
    return all(token in final_reason for token in ("起因", "行动", "结果"))


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
    if final_reason and not _final_reason_specific(final_reason):
        errors.append(f"{name}: final_reason 过于空泛，必须引用具体全章现象类别")
    if name == "因果" and verdict == "PASS" and not _因果链条完整(final_reason):
        errors.append(f"{name}: 因果 PASS 时 final_reason 必须包含起因、行动、结果")
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
    dimension_reports: list[维度校验报告] = []

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
            item = evidence_items[0]
            if not isinstance(item, dict):
                errors.append(f"{name}: evidence[0] 必须是对象")
            else:
                paragraph_id = str(item.get("paragraph_id", "")).strip()
                exact_text = str(item.get("exact_text", ""))
                source_scope = str(item.get("source_scope", SCOPE_CURRENT)).strip()
                occurrence_raw = item.get("occurrence_index", 0)
                evidence_rationale = str(item.get("evidence_rationale", "")).strip()
                if not 段落ID合法(paragraph_id):
                    errors.append(f"{name}: evidence[0] paragraph_id 必须是 P0001 格式")
                elif not exact_text:
                    errors.append(f"{name}: evidence[0] exact_text 不能为空")
                elif source_scope not in ALLOWED_SCOPES:
                    errors.append(f"{name}: evidence[0] source_scope 非法")
                elif isinstance(occurrence_raw, bool) or not isinstance(occurrence_raw, int) or occurrence_raw < 0:
                    errors.append(f"{name}: evidence[0] occurrence_index 必须是非负整数")
                elif source_scope == SCOPE_PRIOR and not prior:
                    errors.append(f"{name}: evidence[0] 引用 PRIOR_CHAPTER 但无前章语料")
                else:
                    corpus = current_paragraphs if source_scope == SCOPE_CURRENT else prior
                    resolved, err, warn = _resolve_evidence(
                        dimension=name,
                        paragraph_id=paragraph_id,
                        exact_text=exact_text,
                        source_scope=source_scope,
                        occurrence_index=occurrence_raw,
                        corpus=corpus,
                    )
                    if err:
                        errors.append(err)
                    else:
                        location_valid = True
                        if warn:
                            warnings.append(warn)
                        assert resolved is not None
                        resolved.evidence_rationale = evidence_rationale
                        validated.append(resolved)
                        if analysis_summary == exact_text:
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
    )


def 摘句在正文中(quote: str, source_text: str) -> bool:
    if not quote or not quote.strip():
        return False
    return quote in source_text
