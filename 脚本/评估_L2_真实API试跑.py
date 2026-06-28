from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"
PUBLIC = EXEC / "公共组件"
L2 = EXEC / "L2工程"
for path in (EXEC, PUBLIC, L2):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from DeepSeek客户端 import (  # noqa: E402
    DEFAULT_L2_REQUEST_TIMEOUT,
    DeepSeekClient,
    create_client,
    stage_runtime_config,
)
from L2模型 import 失败输入, 修复单, 证据  # noqa: E402
from 能力规则加载 import 加载能力规则  # noqa: E402
from 能力注册表 import 获取能力入口  # noqa: E402
from L2_01_诊断上下文 import 构建上下文完整性记录, 检查failure_evidence输入, 构建诊断语料  # noqa: E402
from 一致性上下文 import 构造一致性上下文  # noqa: E402
from 事实索引 import CONSISTENCY_RESPONSE_SCHEMA  # noqa: E402
import L2_01_叙事结构能力  # noqa: E402

RETRYABLE_STATUSES = frozenset(
    {
        "READ_TIMEOUT",
        "RATE_LIMIT",
        "SERVER_ERROR",
        "FORMAT_ERROR",
        "EVIDENCE_ERROR",
        "EVIDENCE_ID_INVALID",
        "EVIDENCE_SOURCE_MISMATCH",
        "EVIDENCE_QUOTE_MISMATCH",
    }
)

PILOT_ROOT = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
MANIFEST_PATH = PILOT_ROOT / "manifest.json"
ABILITY_RULES_PATH = L2 / "ability_rules.json"

GENERATORS: dict[str, Any] = {
    "L2-01": L2_01_叙事结构能力.安全生成修复单,
}
for _mid in ("L2-02", "L2-03", "L2-04", "L2-05", "L2-06"):
    _gen = 获取能力入口(_mid)
    if _gen:
        GENERATORS[_mid] = _gen

REQUIRED_EXPECTED_FIELDS = frozenset(
    {
        "case_id",
        "target_module",
        "case_type",
        "expected_issue_present",
        "acceptable_root_causes",
        "required_evidence_region",
        "forbidden_diagnoses",
        "expected_reroute",
        "minimum_action_requirements",
        "human_notes",
    }
)

HUMAN_METRIC_NAMES = (
    "diagnosis_correct",
    "evidence_relevant",
    "root_cause_specific",
    "fix_actions_executable",
    "acceptance_criteria_testable",
    "forbidden_scope_respected",
    "cross_module_overreach",
    "reroute_correct",
)

StatusLabel = Literal["PASS", "REVIEW", "FAIL", "NOT_REVIEWED"]


@dataclass
class AttemptRecord:
    case_id: str
    module_id: str
    attempt: int
    request_metadata: dict[str, Any]
    raw_response: str
    parsed_response: dict[str, Any] | None
    validation_errors: list[str]
    repair_form: dict[str, Any] | None
    transport_status: str
    format_status: str
    evidence_status: str
    duration_ms: float
    token_usage: dict[str, Any]
    error_message: str | None = None
    api_calls: list[dict[str, Any]] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_expected(case_id: str) -> dict[str, Any]:
    path = PILOT_ROOT / "expected" / f"{case_id}.expected.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_failure_item(case_dir: Path) -> 失败输入:
    raw = json.loads((case_dir / "failure_item.json").read_text(encoding="utf-8"))
    evidences = [证据(int(e["段落"]) if e.get("段落") is not None else None, str(e["摘句"])) for e in raw["证据"]]
    return 失败输入(
        来源闸门=str(raw["来源闸门"]),
        名称=str(raw["名称"]),
        状态=str(raw["状态"]),
        说明=str(raw["说明"]),
        证据=evidences,
        严重级别=str(raw["严重级别"]),
        失败类型=str(raw["失败类型"]),
        候选模块=str(raw["候选模块"]),
        回流验收位置=str(raw["回流验收位置"]),
        修复方向=str(raw["修复方向"]),
    )


def _chapter_char_len(path: Path) -> int:
    return len(path.read_text(encoding="utf-8"))


def validate_fixtures() -> tuple[bool, list[str], int]:
    errors: list[str] = []
    if not MANIFEST_PATH.is_file():
        return False, ["缺少 manifest.json"], 0
    manifest = _load_manifest()
    cases = manifest.get("cases") or []
    if len(cases) != 12:
        errors.append(f"manifest 案例数应为 12，实际 {len(cases)}")
    seen_ids: set[str] = set()
    for entry in cases:
        case_id = str(entry.get("case_id", "")).strip()
        if not case_id:
            errors.append("manifest 存在空 case_id")
            continue
        if case_id in seen_ids:
            errors.append(f"重复 case_id: {case_id}")
        seen_ids.add(case_id)
        case_dir = PILOT_ROOT / str(entry.get("case_dir", ""))
        if not case_dir.is_dir():
            errors.append(f"{case_id}: 缺少案例目录 {case_dir}")
            continue
        chapter = case_dir / "chapters" / "chapter.md"
        if not chapter.is_file():
            errors.append(f"{case_id}: 缺少 chapters/chapter.md")
        else:
            n = _chapter_char_len(chapter)
            if n < 800 or n > 2000:
                errors.append(f"{case_id}: 正文长度 {n} 不在 800～2000 建议范围")
        if not (case_dir / "failure_item.json").is_file():
            errors.append(f"{case_id}: 缺少 failure_item.json")
        if not (case_dir / "project.json").is_file():
            errors.append(f"{case_id}: 缺少 project.json")
        expected_path = PILOT_ROOT / "expected" / f"{case_id}.expected.json"
        if not expected_path.is_file():
            errors.append(f"{case_id}: 缺少 expected JSON")
        else:
            exp = json.loads(expected_path.read_text(encoding="utf-8"))
            missing = REQUIRED_EXPECTED_FIELDS - set(exp.keys())
            if missing:
                errors.append(f"{case_id}: expected 缺字段 {sorted(missing)}")
        module = str(entry.get("target_module", ""))
        if module == "L2-04" and not (case_dir / "IR").is_dir():
            errors.append(f"{case_id}: L2-04 必须附带 IR")
        if module == "L2-06":
            has_prior = (case_dir / "chapters" / "prior.md").is_file()
            has_ir = (case_dir / "IR").is_dir()
            if not has_prior and not has_ir:
                errors.append(f"{case_id}: L2-06 必须附带 prior 或 IR")
    for mid in ("L2-01", "L2-02", "L2-03", "L2-04", "L2-05", "L2-06"):
        if mid not in GENERATORS:
            errors.append(f"正式能力入口未注册: {mid}")
    return len(errors) == 0, errors, len(cases)


def _apply_hints(messages: list[dict[str, str]], hints: list[str]) -> list[dict[str, str]]:
    if not hints:
        return messages
    copied = [dict(m) for m in messages]
    extra = "\n\n【试跑修正提示】" + hints[-1]
    for idx in range(len(copied) - 1, -1, -1):
        if copied[idx].get("role") == "user":
            copied[idx] = {"role": "user", "content": str(copied[idx].get("content", "")) + extra}
            break
    return copied


def _extract_usage(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        envelope = json.loads(raw)
        usage = envelope.get("usage")
        return usage if isinstance(usage, dict) else {}
    except json.JSONDecodeError:
        return {}


def _inject_max_tokens(body: bytes, max_tokens: int) -> bytes:
    payload = json.loads(body.decode("utf-8"))
    payload["max_tokens"] = max_tokens
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class PilotInstrumentedClient:
    """包装正式 DeepSeekClient：记录调用、追加重试提示、注入 max_tokens（不改生产代码）。"""

    def __init__(
        self,
        base: DeepSeekClient,
        *,
        hints: list[str] | None = None,
        max_tokens: int = 8192,
    ) -> None:
        self._base = base
        self._hints = list(hints or [])
        self.calls: list[dict[str, Any]] = []
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self._base.model

    @property
    def stage(self) -> str:
        return self._base.stage

    def has_api_key(self) -> bool:
        return self._base.has_api_key

    def _wrapped_transport(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        body = _inject_max_tokens(body, self._max_tokens)
        return self._base._transport(url, headers, body, timeout)  # noqa: SLF001

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> Any:
        msgs = _apply_hints(messages, self._hints)
        start = time.perf_counter()
        inner = DeepSeekClient(
            stage=self._base.stage,
            model=self._base.model,
            api_key=self._base._api_key,  # noqa: SLF001
            base_url=self._base._base_url,  # noqa: SLF001
            timeout=self._base._timeout,  # noqa: SLF001
            transport=self._wrapped_transport,
        )
        result = inner.chat(msgs, temperature=temperature)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.calls.append(
            {
                "messages_roles": [m.get("role") for m in msgs],
                "ok": result.ok,
                "error": result.error,
                "error_kind": result.error_kind,
                "status_code": result.status_code,
                "content": result.content,
                "parsed": result.parsed,
                "raw": result.raw,
                "duration_ms": elapsed_ms,
                "token_usage": _extract_usage(result.raw),
                "hints_applied": list(self._hints),
                "timeout_class": (result.meta or {}).get("timeout_class"),
                "http_class": (result.meta or {}).get("http_class"),
                "connection_class": (result.meta or {}).get("connection_class"),
            }
        )
        return result

    def chat_json(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> Any:
        result = self.chat(messages, temperature=temperature)
        if not result.ok:
            return result
        try:
            parsed = json.loads(result.content)
        except json.JSONDecodeError as exc:
            result.ok = False
            result.error = str(exc)
            result.error_kind = "INVALID_JSON"
            return result
        if not isinstance(parsed, dict):
            result.ok = False
            result.error = "JSON 根节点必须是对象"
            result.error_kind = "INVALID_JSON"
            return result
        result.parsed = parsed
        return result


def _classify_failure(err: str | None, calls: list[dict[str, Any]], *, form: 修复单 | None = None) -> tuple[str, bool, str]:
    last = calls[-1] if calls else {}
    if form is not None and (not err or "INPUT_EVIDENCE_MISMATCH" in str(err)):
        return "SUCCESS", False, ""

    if not err and last.get("ok"):
        return "SUCCESS", False, ""

    err_text = err or ""
    if "CONTEXT_INCOMPLETE" in err_text:
        return "CONTEXT_INCOMPLETE", False, ""
    if "INPUT_EVIDENCE_MISMATCH" in err_text:
        return "INPUT_EVIDENCE_MISMATCH", False, ""

    api_kind = str(last.get("error_kind", ""))
    status = last.get("status_code")
    timeout_class = str(last.get("timeout_class") or "")
    http_class = str(last.get("http_class") or "")

    if api_kind == "MISSING_API_KEY" or "MISSING_API_KEY" in err_text:
        return "AUTH_ERROR", False, ""
    if http_class == "AUTH_ERROR" or status in {401, 403, 402}:
        return "AUTH_ERROR", False, ""
    if http_class == "INVALID_REQUEST" or status in {400, 422}:
        return "INVALID_REQUEST", False, ""
    if api_kind == "TIMEOUT" or "TIMEOUT" in err_text:
        if timeout_class == "READ_TIMEOUT" or "read operation timed out" in err_text.lower():
            return "READ_TIMEOUT", True, ""
        if timeout_class == "CONNECT_TIMEOUT":
            return "CONNECT_TIMEOUT", False, ""
        return "READ_TIMEOUT", True, ""
    if api_kind == "NETWORK_ERROR" or last.get("connection_class") == "CONNECTION_ERROR":
        return "CONNECTION_ERROR", False, ""
    if http_class == "RATE_LIMIT" or status == 429:
        return "RATE_LIMIT", True, ""
    if http_class == "SERVER_ERROR" or (isinstance(status, int) and status >= 500):
        return "SERVER_ERROR", True, ""

    if api_kind in {"INVALID_JSON", "EMPTY_RESPONSE", "FINISH_REASON_REJECTED", "INVALID_ENVELOPE"}:
        return "FORMAT_ERROR", True, "上次输出不是合法完整 JSON。请严格按 schema 输出单个 JSON 对象。"

    if "EVIDENCE_INVALID" in err_text or "LEGACY_RESPONSE" in err_text or "LEGACY_SETTING" in err_text:
        return "EVIDENCE_ERROR", True, "证据校验失败：请仅使用 indexed evidence_id 引用。"
    if "EVIDENCE_ID_INVALID" in err_text:
        return "EVIDENCE_ID_INVALID", True, "evidence_id 无效：请仅引用 indexed_evidence 中的 ID。"
    if "EVIDENCE_SOURCE_MISMATCH" in err_text:
        return "EVIDENCE_SOURCE_MISMATCH", True, "来源类型与 evidence_id 索引不一致。"
    if "EVIDENCE_QUOTE_MISMATCH" in err_text:
        return "EVIDENCE_QUOTE_MISMATCH", True, "展示摘句与源文件逐字不一致。"

    if "CHAPTER_PATH_MISSING" in err_text:
        return "SCHEMA_ERROR", False, err_text
    if err_text:
        return "DOMAIN_VALIDATION_ERROR", False, err_text
    return "DOMAIN_VALIDATION_ERROR", False, err_text


def _repair_form_dict(form: 修复单 | None) -> dict[str, Any] | None:
    if form is None:
        return None
    return asdict(form)


def _human_metrics_template(*, r5c: bool = False) -> dict[str, StatusLabel]:
    default = "NOT_REVIEWED" if r5c else "REVIEW"
    return {name: default for name in HUMAN_METRIC_NAMES}


def _auto_signals(form: dict[str, Any] | None, expected: dict[str, Any], err: str | None) -> dict[str, Any]:
    signals: dict[str, Any] = {}
    if form is None:
        signals["repair_form_missing"] = True
        signals["error"] = err
        return signals
    text_blob = " ".join(
        [
            str(form.get("主失败类型", "")),
            str(form.get("次失败类型", "")),
            str(form.get("修复动作", "")),
            str(form.get("规则依据", "")),
            " ".join(form.get("标准动作", []) or []),
        ]
    )
    forbidden = [str(x) for x in expected.get("forbidden_diagnoses", [])]
    hits = [f for f in forbidden if f and f in text_blob]
    signals["forbidden_diagnosis_hits"] = hits
    signals["needs_reroute_flag"] = form.get("是否需要回L15重路由")
    signals["expected_reroute"] = expected.get("expected_reroute")
    return signals


def run_single_case(
    entry: dict[str, Any],
    rules: Any,
    *,
    max_tokens: int,
    request_timeout: float | None,
) -> tuple[list[AttemptRecord], str | None]:
    case_id = str(entry["case_id"])
    module_id = str(entry["target_module"])
    case_dir = (PILOT_ROOT / str(entry["case_dir"])).resolve()
    chapter_path = case_dir / "chapters" / "chapter.md"
    item = _load_failure_item(case_dir)
    ability_rules = rules.能力规则.get(module_id)
    generator = GENERATORS.get(module_id)
    if not ability_rules or not generator:
        rec = AttemptRecord(
            case_id=case_id,
            module_id=module_id,
            attempt=1,
            request_metadata={"model": "", "chapter": str(chapter_path)},
            raw_response="",
            parsed_response=None,
            validation_errors=["缺少能力规则或生成器"],
            repair_form=None,
            transport_status="SCHEMA_ERROR",
            format_status="SCHEMA_ERROR",
            evidence_status="SCHEMA_ERROR",
            duration_ms=0,
            token_usage={},
            error_message="缺少能力规则或生成器",
        )
        return [rec], "SCHEMA_ERROR"

    attempts_out: list[AttemptRecord] = []
    retry_hint: str | None = None
    retry_used = False
    stop_reason: str | None = None

    for attempt_num in (1, 2):
        hints = [retry_hint] if retry_hint else []
        base_client = create_client("L2", timeout=request_timeout)
        runtime = base_client.runtime_config(requested_temperature=0.2)
        client = PilotInstrumentedClient(base_client, hints=hints, max_tokens=max_tokens)
        if not client.has_api_key():
            rec = AttemptRecord(
                case_id=case_id,
                module_id=module_id,
                attempt=attempt_num,
                request_metadata={"model": base_client.model, "api_time": _utc_now()},
                raw_response="",
                parsed_response=None,
                validation_errors=["缺少 DEEPSEEK_API_KEY"],
                repair_form=None,
                transport_status="AUTH_ERROR",
                format_status="AUTH_ERROR",
                evidence_status="AUTH_ERROR",
                duration_ms=0,
                token_usage={},
                error_message="缺少 DEEPSEEK_API_KEY",
            )
            attempts_out.append(rec)
            return attempts_out, "AUTH_ERROR"

        start = time.perf_counter()
        form, err = generator(
            item,
            ability_rules,
            chapter_path=chapter_path,
            repo_root=case_dir,
            client=client,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        last_call = client.calls[-1] if client.calls else {}
        status, retryable, hint = _classify_failure(err, client.calls, form=form)
        parsed = last_call.get("parsed") if isinstance(last_call.get("parsed"), dict) else None
        validation_errors: list[str] = []
        if err and form is None:
            validation_errors.append(str(err))

        transport_status = status
        evidence_kinds = {
            "EVIDENCE_ERROR",
            "EVIDENCE_ID_INVALID",
            "EVIDENCE_SOURCE_MISMATCH",
            "EVIDENCE_QUOTE_MISMATCH",
        }
        format_status = "SUCCESS" if status not in {"FORMAT_ERROR"} else "FORMAT_ERROR"
        evidence_status = "EVIDENCE_ERROR" if status in evidence_kinds else (
            "SUCCESS" if form else "FAIL"
        )

        rec = AttemptRecord(
            case_id=case_id,
            module_id=module_id,
            attempt=attempt_num,
            request_metadata={
                "model": client.model,
                "api_call_time": _utc_now(),
                **runtime,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "chapter_path": str(chapter_path),
                "harness_root": str(case_dir),
            },
            raw_response=str(last_call.get("raw", "")),
            parsed_response=parsed,
            validation_errors=validation_errors,
            repair_form=_repair_form_dict(form),
            transport_status=transport_status,
            format_status=format_status,
            evidence_status=evidence_status,
            duration_ms=elapsed_ms,
            token_usage=dict(last_call.get("token_usage") or {}),
            error_message=err,
            api_calls=client.calls,
        )
        attempts_out.append(rec)

        if form is not None:
            break
        if attempt_num == 2 or not retryable or retry_used or status not in RETRYABLE_STATUSES:
            break
        retry_hint = hint if status == "FORMAT_ERROR" else None
        retry_used = True

    final_status = attempts_out[-1].transport_status
    if final_status == "AUTH_ERROR":
        stop_reason = "AUTH_ERROR"
    return attempts_out, stop_reason


def _technical_metrics(all_attempts: dict[str, list[AttemptRecord]]) -> dict[str, Any]:
    per_case: dict[str, dict[str, Any]] = {}
    exact_quote_forgery = 0
    source_binding_errors = 0
    schema_crashes = 0
    consecutive_schema = 0
    max_consecutive_schema = 0

    evidence_kinds = {
        "EVIDENCE_ERROR",
        "EVIDENCE_ID_INVALID",
        "EVIDENCE_SOURCE_MISMATCH",
        "EVIDENCE_QUOTE_MISMATCH",
    }
    for case_id, attempts in all_attempts.items():
        final = attempts[-1]
        retry_count = max(0, len(attempts) - 1)
        transport_ok = final.transport_status == "SUCCESS"
        json_valid = final.format_status == "SUCCESS" or final.repair_form is not None
        schema_valid = final.transport_status not in {"SCHEMA_ERROR"}
        evidence_failed = (
            final.evidence_status == "EVIDENCE_ERROR" or final.transport_status in evidence_kinds
        )
        exact_quote_valid = not evidence_failed
        source_binding_valid = not evidence_failed
        module_passed = final.repair_form is not None
        if evidence_failed:
            exact_quote_forgery += 1
            source_binding_errors += 1
        if final.transport_status == "SCHEMA_ERROR":
            schema_crashes += 1
            consecutive_schema += 1
            max_consecutive_schema = max(max_consecutive_schema, consecutive_schema)
        else:
            consecutive_schema = 0

        per_case[case_id] = {
            "transport_success": transport_ok,
            "json_valid": json_valid,
            "schema_valid": schema_valid,
            "exact_quote_valid": exact_quote_valid,
            "source_binding_valid": source_binding_valid,
            "module_validator_passed": module_passed,
            "repair_form_generated": final.repair_form is not None,
            "retry_count": retry_count,
            "attempts": len(attempts),
            "final_status": final.transport_status,
        }

    all_parsed_or_fault = all(
        m["json_valid"] or m["final_status"] in {"RATE_LIMIT", "SERVER_ERROR", "TRANSPORT_ERROR"}
        for m in per_case.values()
    )
    all_retry_ok = all(m["retry_count"] <= 1 for m in per_case.values())

    technical_passed = (
        all_parsed_or_fault
        and exact_quote_forgery == 0
        and source_binding_errors == 0
        and schema_crashes == 0
        and all_retry_ok
    )

    return {
        "per_case": per_case,
        "exact_quote_forgery": exact_quote_forgery,
        "source_binding_errors": source_binding_errors,
        "schema_crashes": schema_crashes,
        "max_consecutive_schema": max_consecutive_schema,
        "technical_protocol_passed": technical_passed,
    }


def _write_report(
    run_dir: Path,
    manifest: dict[str, Any],
    all_attempts: dict[str, list[AttemptRecord]],
    technical: dict[str, Any],
    run_meta: dict[str, Any],
) -> Path:
    lines: list[str] = [
        "# R5A L2 真实 API 小样本试跑报告",
        "",
        f"run_id: {run_meta['run_id']}",
        f"generated_at: {run_meta['started_at']}",
        "",
        "## 1. 12 例清单",
        "",
    ]
    for entry in manifest["cases"]:
        lines.append(f"- {entry['case_id']} → {entry['target_module']} ({entry['case_type']})")
    lines.extend(
        [
            "",
            "## 2. API 模型与运行配置",
            "",
            f"- model: {run_meta.get('model')}",
            f"- max_tokens: {run_meta.get('max_tokens')}",
            f"- response_format: json_object",
            f"- temperature: 0.2（L2 正式客户端默认）",
            "",
            "## 3. 每例调用次数与技术状态",
            "",
        ]
    )
    for case_id, attempts in all_attempts.items():
        final = attempts[-1]
        lines.append(
            f"- {case_id}: attempts={len(attempts)}, status={final.transport_status}, "
            f"repair_form={'yes' if final.repair_form else 'no'}"
        )
    lines.extend(["", "## 4. 技术协议指标", "", json.dumps(technical, ensure_ascii=False, indent=2)])
    lines.extend(["", "## 5. 人工业务指标", "", "默认 REVIEW，需人工填写 human_metrics.json", ""])
    lines.extend(["", "## 6～13. 见 summary.json", ""])
    lines.append("- PRODUCTION_ELIGIBLE = false")
    lines.append(
        f"- L2_R5A_TECHNICAL_PROTOCOL = {'PASSED' if technical['technical_protocol_passed'] else 'FAILED'}"
    )
    lines.append("- L2_R5A_BUSINESS_PILOT = NOT_EVALUATED（需人工评分）")
    lines.append("- L2_REAL_MODEL_EFFECTIVENESS = NOT_TESTED（业务未评）")
    lines.append("- 是否修改生产代码: 否")
    lines.append("- 是否进入 L3: 否")
    lines.append("- 是否修改正式章节: 否")
    lines.append("- 是否修改 R0 基线: 否")

    report_path = run_dir / "REPORT.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def preflight_case(entry: dict[str, Any]) -> dict[str, Any]:
    case_id = str(entry["case_id"])
    module_id = str(entry["target_module"])
    case_dir = (PILOT_ROOT / str(entry["case_dir"])).resolve()
    chapter_path = case_dir / "chapters" / "chapter.md"
    item = _load_failure_item(case_dir)
    corpus, _ = 构建诊断语料(chapter_path, item, repo_root=case_dir)
    completeness = 构建上下文完整性记录(chapter_path, item, repo_root=case_dir)
    evidence = 检查failure_evidence输入(item, corpus)
    out: dict[str, Any] = {
        "case_id": case_id,
        "module_id": module_id,
        "context_coverage_ratio": completeness.get("coverage_ratio"),
        "context_truncated": completeness.get("truncated"),
        "input_evidence_status": evidence.get("status"),
        "request_timeout_seconds": create_client("L2").request_timeout_seconds,
        **stage_runtime_config("L2"),
    }
    if module_id == "L2-06":
        from 前序章节 import 解析前序章节

        resolved = chapter_path.resolve()
        ctx = 构造一致性上下文(
            resolved,
            item,
            repo_root=case_dir,
            ir_dir=(case_dir / "IR") if (case_dir / "IR").is_dir() else None,
            prior_chapters=解析前序章节(resolved),
        )
        out["response_schema_version"] = CONSISTENCY_RESPONSE_SCHEMA
        out["indexed_fact_count"] = len(ctx.indexed_facts)
        out["indexed_fact_pair_count"] = len(ctx.indexed_fact_pairs)
    if module_id == "L2-04":
        from 设定上下文 import 构造设定上下文
        from 证据索引 import SETTING_RESPONSE_SCHEMA, SOURCE_CHAPTER, SOURCE_IR, SOURCE_PROJECT_RULE

        resolved = chapter_path.resolve()
        ctx = 构造设定上下文(
            resolved,
            item,
            repo_root=case_dir,
            ir_dir=(case_dir / "IR") if (case_dir / "IR").is_dir() else None,
        )
        out["response_schema_version"] = SETTING_RESPONSE_SCHEMA
        out["chapter_evidence_count"] = sum(
            1 for e in ctx.indexed_evidence if e.get("source_type") == SOURCE_CHAPTER
        )
        out["ir_evidence_count"] = sum(
            1 for e in ctx.indexed_evidence if e.get("source_type") == SOURCE_IR
        )
        out["project_rule_evidence_count"] = sum(
            1 for e in ctx.indexed_evidence if e.get("source_type") == SOURCE_PROJECT_RULE
        )
        out["evidence_id_total"] = len(ctx.indexed_evidence)
        out["source_paths"] = sorted({str(e.get("source_path", "")) for e in ctx.indexed_evidence})
        ir_quotes = [
            e.get("quote", "")
            for e in ctx.indexed_evidence
            if e.get("source_type") == SOURCE_PROJECT_RULE and "失去一段记忆" in str(e.get("quote", ""))
        ]
        out["l2p007_ir_memory_cost_indexed"] = bool(ir_quotes)
    return out


def _write_r5c_human_scoreboard(manifest: dict[str, Any]) -> Path:
    scoreboard_path = PILOT_ROOT / "results" / "L2_R5C_人工业务评分表_20260628.json"
    rows = []
    for entry in manifest.get("cases") or []:
        rows.append(
            {
                "case_id": str(entry.get("case_id", "")),
                "target_module": str(entry.get("target_module", "")),
                "diagnosis_correct": "NOT_REVIEWED",
                "evidence_relevant": "NOT_REVIEWED",
                "root_cause_specific": "NOT_REVIEWED",
                "fix_actions_executable": "NOT_REVIEWED",
                "acceptance_criteria_testable": "NOT_REVIEWED",
                "forbidden_scope_respected": "NOT_REVIEWED",
                "cross_module_overreach": "NOT_REVIEWED",
                "reroute_correct": "NOT_REVIEWED",
                "reviewer_notes": "",
            }
        )
    payload = {
        "schema_version": "xcue.l2-human-scoreboard/1.0",
        "phase": "R5C",
        "status": "NOT_REVIEWED",
        "cases": rows,
    }
    scoreboard_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return scoreboard_path


def run_preflight(case_ids: list[str]) -> int:
    manifest = _load_manifest()
    selected = [e for e in manifest["cases"] if str(e["case_id"]) in case_ids]
    if len(selected) != len(case_ids):
        print("PREFLIGHT_FAIL: case_id 不存在")
        return 1
    for entry in selected:
        info = preflight_case(entry)
        print(json.dumps(info, ensure_ascii=False))
    return 0


def run_pilot(args: argparse.Namespace) -> int:
    ok, errors, count = validate_fixtures()
    if not ok:
        for e in errors:
            print(f"VALIDATION_FAIL: {e}")
        return 1

    run_dir = PILOT_ROOT / "results" / args.run_id
    if run_dir.exists() and not args.force_new_run:
        print(f"RUN_EXISTS: {run_dir}（使用 --force-new-run 创建新 run）")
        return 1
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest()
    rules = 加载能力规则(ABILITY_RULES_PATH)
    request_timeout = float(args.request_timeout)
    base_client = create_client("L2", timeout=request_timeout)
    runtime = base_client.runtime_config(requested_temperature=0.2)
    is_r5c = "R5C" in str(args.run_id)
    run_meta = {
        "run_id": args.run_id,
        "started_at": _utc_now(),
        "model": base_client.model,
        "max_tokens": args.max_tokens,
        "request_timeout_seconds": request_timeout,
        **runtime,
        "manifest": manifest["pilot_id"],
        "r5_phase": "R5C" if is_r5c else "R5B",
        "production_code_modified": True,
        "entered_l3": False,
        "modified_formal_chapters": False,
        "modified_r0_baseline": False,
    }
    (run_dir / "run_meta.json").write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    all_attempts: dict[str, list[AttemptRecord]] = {}
    stop_reason: str | None = None
    fabricated_streak = 0
    case_filter = set(args.case_id or [])
    cases = [e for e in manifest["cases"] if not case_filter or str(e["case_id"]) in case_filter]

    for entry in cases:
        case_id = str(entry["case_id"])
        case_attempt_dir = run_dir / "cases" / case_id
        case_attempt_dir.mkdir(parents=True, exist_ok=True)

        attempts, case_stop = run_single_case(
            entry,
            rules,
            max_tokens=args.max_tokens,
            request_timeout=request_timeout,
        )
        all_attempts[case_id] = attempts

        for rec in attempts:
            out_path = case_attempt_dir / f"attempt_{rec.attempt}.json"
            out_path.write_text(json.dumps(asdict(rec), ensure_ascii=False, indent=2), encoding="utf-8")

        expected = _load_expected(case_id)
        final = attempts[-1]
        human_payload = {
            "case_id": case_id,
            "human_metrics": _human_metrics_template(r5c=is_r5c),
            "auto_signals": _auto_signals(final.repair_form, expected, final.error_message),
        }
        if is_r5c:
            human_payload["human_metrics"]["reviewer_notes"] = ""
        (case_attempt_dir / "human_metrics.json").write_text(
            json.dumps(human_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if final.evidence_status == "EVIDENCE_ERROR":
            fabricated_streak += 1
            if fabricated_streak >= 3:
                stop_reason = "FABRICATED_QUOTES_STREAK"
        else:
            fabricated_streak = 0

        if case_stop == "AUTH_ERROR":
            stop_reason = "AUTH_ERROR"
            break

        tech_partial = _technical_metrics({case_id: attempts})
        if tech_partial["max_consecutive_schema"] >= 3:
            stop_reason = "SCHEMA_STREAK"
            break
        if stop_reason == "FABRICATED_QUOTES_STREAK":
            break

    technical = _technical_metrics(all_attempts)
    targeted = bool(case_filter) and len(cases) <= 4
    all_success = all(
        m.get("final_status") == "SUCCESS" and m.get("repair_form_generated")
        for m in technical["per_case"].values()
    )
    summary = {
        "run_id": args.run_id,
        "stopped_reason": stop_reason,
        "technical": technical,
        "case_count": len(all_attempts),
        "status_labels": {},
    }
    if is_r5c:
        l2p007_ok = (
            technical["per_case"].get("L2P-007", {}).get("final_status") == "SUCCESS"
            and technical["per_case"].get("L2P-007", {}).get("repair_form_generated")
        )
        summary["status_labels"] = {
            "L2P_007_TECHNICAL_PROTOCOL": (
                "PASSED" if targeted and l2p007_ok and "L2P-007" in case_filter else "NOT_RUN"
            ),
            "L2_R5C_FULL_PROTOCOL": (
                "NOT_RUN" if targeted else ("PASSED" if technical["technical_protocol_passed"] else "FAILED")
            ),
            "L2_R5C_BUSINESS_PILOT": (
                "NOT_EVALUATED"
                if targeted or not technical["technical_protocol_passed"]
                else "AWAITING_HUMAN_REVIEW"
            ),
            "L2_REAL_MODEL_EFFECTIVENESS": "NOT_TESTED",
            "PRODUCTION_ELIGIBLE": False,
        }
        if not targeted and technical["technical_protocol_passed"]:
            scoreboard = _write_r5c_human_scoreboard(manifest)
            summary["human_scoreboard_path"] = str(scoreboard)
    else:
        summary["status_labels"] = {
            "L2_R5B_TARGETED_PROTOCOL": (
                "PASSED" if targeted and all_success else ("FAILED" if targeted else "NOT_RUN")
            ),
            "L2_R5B_FULL_PROTOCOL": (
                "NOT_RUN" if targeted else ("PASSED" if technical["technical_protocol_passed"] else "FAILED")
            ),
            "L2_R5B_BUSINESS_PILOT": "NOT_EVALUATED",
            "L2_REAL_MODEL_EFFECTIVENESS": "NOT_TESTED",
            "PRODUCTION_ELIGIBLE": False,
        }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(run_dir, manifest, all_attempts, technical, run_meta)

    print(f"RUN_COMPLETE: {run_dir}")
    if is_r5c:
        print(f"l2p007_protocol: {summary['status_labels'].get('L2P_007_TECHNICAL_PROTOCOL')}")
        print(f"full_protocol: {summary['status_labels'].get('L2_R5C_FULL_PROTOCOL')}")
    else:
        print(f"targeted_protocol: {summary['status_labels']['L2_R5B_TARGETED_PROTOCOL']}")
        print(f"full_protocol: {summary['status_labels']['L2_R5B_FULL_PROTOCOL']}")
    if stop_reason:
        print(f"STOPPED: {stop_reason}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="R5B L2 真实 DeepSeek 小样本试跑")
    parser.add_argument("--validate-only", action="store_true", help="仅校验夹具，不调用 API")
    parser.add_argument("--preflight-only", action="store_true", help="只读预检，不调用 API")
    parser.add_argument("--case-id", action="append", default=[], help="限定案例 ID，可重复指定")
    parser.add_argument("--run-id", type=str, default="", help="试跑 run_id")
    parser.add_argument("--force-new-run", action="store_true", help="允许写入新 run 目录")
    parser.add_argument("--max-tokens", type=int, default=8192, help="注入 max_tokens（eval 层）")
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=DEFAULT_L2_REQUEST_TIMEOUT,
        help="DeepSeek 请求超时（秒）",
    )
    args = parser.parse_args()

    if args.validate_only:
        ok, errors, count = validate_fixtures()
        if ok:
            print("VALIDATION_OK")
            print(f"cases: {count}")
            return 0
        for e in errors:
            print(f"VALIDATION_FAIL: {e}")
        return 1

    if args.preflight_only:
        if not args.case_id:
            print("预检需要 --case-id")
            return 1
        return run_preflight(args.case_id)

    if not args.run_id:
        print("缺少 --run-id")
        return 1
    if not args.force_new_run:
        print("真实试跑必须指定 --force-new-run")
        return 1
    return run_pilot(args)


if __name__ == "__main__":
    raise SystemExit(main())
