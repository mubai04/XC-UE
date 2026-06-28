"""R5D：汇总 L2 人工业务评分（只读校验与统计，不修改评分）。"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
MANIFEST_PATH = PILOT / "manifest.json"
EXPECTED_DIR = PILOT / "expected"

SCORE_FIELDS = (
    "diagnosis_correct",
    "evidence_relevant",
    "root_cause_specific",
    "fix_actions_executable",
    "acceptance_criteria_testable",
    "forbidden_scope_respected",
    "cross_module_overreach",
    "reroute_correct",
    "overall_business_result",
)

RECOMMENDED_ACTIONS = frozenset({"ACCEPT", "CALIBRATE", "REROUTE", "REJECT", "NOT_REVIEWED"})
VERDICTS = frozenset({"PASS", "REVIEW", "FAIL", "NOT_REVIEWED"})

GATES = {
    "diagnosis_correct_pass_min": 10,
    "evidence_relevant_pass_min": 10,
    "fix_actions_executable_pass_min": 9,
    "forbidden_scope_fail_max": 0,
    "b_class_misdiagnosis_max": 2,
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_score_paths(review_dir: Path) -> list[Path]:
    score_dir = review_dir / "案例评审表"
    return sorted(score_dir.glob("L2P-*_评分.json"))


PHASE2_EXTRA_FIELDS = (
    "phase_1_overall",
    "phase_2_overall",
    "rating_changed",
    "change_reason",
)


def _validate_row(row: dict[str, Any], *, path: Path) -> list[str]:
    errors: list[str] = []
    for key in ("case_id", "module_id"):
        if not str(row.get(key, "")).strip():
            errors.append(f"{path.name}: 缺少 {key}")
    for field in SCORE_FIELDS:
        value = str(row.get(field, "NOT_REVIEWED")).strip()
        if value not in VERDICTS:
            errors.append(f"{path.name}: {field} 无效值 {value}")
    action = str(row.get("recommended_action", "NOT_REVIEWED")).strip()
    if action not in RECOMMENDED_ACTIONS:
        errors.append(f"{path.name}: recommended_action 无效")
    if not isinstance(row.get("decisive_evidence"), list):
        errors.append(f"{path.name}: decisive_evidence 必须是数组")
    if not isinstance(row.get("major_defects"), list):
        errors.append(f"{path.name}: major_defects 必须是数组")
    if path.name.endswith("_评分.json"):
        for field in PHASE2_EXTRA_FIELDS:
            if field not in row:
                errors.append(f"{path.name}: 缺少第二阶段字段 {field}")
        if "rating_changed" in row and not isinstance(row["rating_changed"], bool):
            errors.append(f"{path.name}: rating_changed 必须是布尔值")
    return errors


def load_case_scores(review_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    paths = _case_score_paths(review_dir)
    if len(paths) != 12:
        errors.append(f"评分文件数量应为 12，实际 {len(paths)}")
    for path in paths:
        row = _load_json(path)
        if not isinstance(row, dict):
            errors.append(f"{path.name}: 不是 JSON 对象")
            continue
        errors.extend(_validate_row(row, path=path))
        rows.append(row)
    rows.sort(key=lambda r: str(r.get("case_id", "")))
    return rows, errors


def _count_verdict(rows: list[dict[str, Any]], field: str) -> Counter:
    counter: Counter = Counter()
    for row in rows:
        counter[str(row.get(field, "NOT_REVIEWED"))] += 1
    return counter


def _module_case_types(manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for entry in manifest.get("cases") or []:
        case_id = str(entry.get("case_id", ""))
        mapping[case_id] = {
            "module_id": str(entry.get("target_module", "")),
            "case_type": str(entry.get("case_type", "")),
        }
    return mapping


def compute_statistics(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    meta = _module_case_types(manifest)
    per_metric = {field: dict(_count_verdict(rows, field)) for field in SCORE_FIELDS}
    per_module: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        module = str(row.get("module_id", ""))
        per_module.setdefault(module, []).append(
            {
                "case_id": str(row.get("case_id", "")),
                "overall_business_result": str(row.get("overall_business_result", "NOT_REVIEWED")),
            }
        )
    a_cases = [r for r in rows if meta.get(str(r.get("case_id", "")), {}).get("case_type") == "A"]
    b_cases = [r for r in rows if meta.get(str(r.get("case_id", "")), {}).get("case_type") == "B"]
    a_pass = sum(1 for r in a_cases if r.get("diagnosis_correct") == "PASS")
    b_misdiag = sum(
        1
        for r in b_cases
        if r.get("diagnosis_correct") == "FAIL" or r.get("overall_business_result") == "FAIL"
    )
    reroute_pass = sum(1 for r in rows if r.get("reroute_correct") == "PASS")
    overreach_fail = sum(1 for r in rows if r.get("cross_module_overreach") == "FAIL")
    forbidden_fail = sum(1 for r in rows if r.get("forbidden_scope_respected") == "FAIL")
    vague_fix = sum(
        1
        for r in rows
        if r.get("fix_actions_executable") == "FAIL"
        or any("空泛" in str(d) for d in (r.get("major_defects") or []))
    )
    evidence_semantic_fail = sum(1 for r in rows if r.get("evidence_relevant") == "FAIL")
    module_all_fail = [
        module
        for module, items in per_module.items()
        if len(items) >= 2 and all(i["overall_business_result"] == "FAIL" for i in items)
    ]
    strict_pass = sum(1 for r in rows if r.get("overall_business_result") == "PASS")
    relaxed_pass = sum(
        1 for r in rows if r.get("overall_business_result") in {"PASS", "REVIEW"}
    )
    return {
        "per_metric": per_metric,
        "per_module": per_module,
        "a_class_diagnosis_pass": a_pass,
        "a_class_total": len(a_cases),
        "b_class_misdiagnosis": b_misdiag,
        "b_class_total": len(b_cases),
        "reroute_pass_count": reroute_pass,
        "cross_module_overreach_fail": overreach_fail,
        "forbidden_scope_fail": forbidden_fail,
        "vague_fix_fail_count": vague_fix,
        "evidence_semantic_fail_count": evidence_semantic_fail,
        "modules_with_all_fail": module_all_fail,
        "overall_strict_pass_count": strict_pass,
        "overall_relaxed_pass_count": relaxed_pass,
    }


def evaluate_gates(rows: list[dict[str, Any]], stats: dict[str, Any]) -> dict[str, Any]:
    diag_pass = stats["per_metric"]["diagnosis_correct"].get("PASS", 0)
    ev_pass = stats["per_metric"]["evidence_relevant"].get("PASS", 0)
    fix_pass = stats["per_metric"]["fix_actions_executable"].get("PASS", 0)
    forbidden_fail = stats["forbidden_scope_fail"]
    b_mis = stats["b_class_misdiagnosis"]
    l2p012 = next((r for r in rows if r.get("case_id") == "L2P-012"), {})
    l2p012_hard = any(
        "HARD_CONFLICT" in str(x)
        for x in [
            l2p012.get("reviewer_notes", ""),
            " ".join(str(d) for d in (l2p012.get("major_defects") or [])),
        ]
    )
    checks = {
        "diagnosis_correct_at_least_10_12": diag_pass >= GATES["diagnosis_correct_pass_min"],
        "evidence_relevant_at_least_10_12": ev_pass >= GATES["evidence_relevant_pass_min"],
        "fix_actions_executable_at_least_9_12": fix_pass >= GATES["fix_actions_executable_pass_min"],
        "forbidden_scope_severe_violations_zero": forbidden_fail <= GATES["forbidden_scope_fail_max"],
        "b_class_misdiagnosis_at_most_2": b_mis <= GATES["b_class_misdiagnosis_max"],
        "l2p012_not_hard_conflict": not l2p012_hard,
        "no_module_all_fail": not stats["modules_with_all_fail"],
    }
    veto_reasons: list[str] = []
    for row in rows:
        notes = " ".join(
            [
                str(row.get("reviewer_notes", "")),
                " ".join(str(x) for x in (row.get("major_defects") or [])),
            ]
        )
        if any(k in notes for k in ("伪造", "错引关键证据", "静态一致", "破坏性修复", "跨域修改")):
            veto_reasons.append(str(row.get("case_id")))
    passed = all(checks.values()) and not veto_reasons
    return {
        "checks": checks,
        "veto_cases": veto_reasons,
        "strict_gate_passed": passed,
    }


def has_unreviewed(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        for field in SCORE_FIELDS:
            if row.get(field) == "NOT_REVIEWED":
                return True
        if row.get("recommended_action") == "NOT_REVIEWED":
            return True
    return False


def summarize(review_dir: Path, *, write_report: bool = True) -> dict[str, Any]:
    review_dir = review_dir.resolve()
    summary_path = review_dir / "人工评分汇总.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"缺少 {summary_path}")

    rows, errors = load_case_scores(review_dir)
    manifest = _load_json(MANIFEST_PATH)
    incomplete = has_unreviewed(rows)
    status = "INCOMPLETE" if incomplete else "READY_FOR_SUMMARY"

    result: dict[str, Any] = {
        "review_dir": str(review_dir),
        "validation_errors": errors,
        "status": status,
        "case_count": len(rows),
        "unreviewed_remaining": incomplete,
    }

    if errors:
        result["L2_R5D_BUSINESS_PILOT"] = "INCOMPLETE"
        result["L2_REAL_MODEL_EFFECTIVENESS"] = "NOT_TESTED"
        result["PRODUCTION_ELIGIBLE"] = False
        if write_report:
            _write_outputs(review_dir, rows, None, None, result)
        return result

    stats = compute_statistics(rows, manifest)
    gate = evaluate_gates(rows, stats)
    result["statistics"] = stats
    result["gate_result"] = gate

    if incomplete:
        result["L2_R5D_BUSINESS_PILOT"] = "INCOMPLETE"
        result["L2_REAL_MODEL_EFFECTIVENESS"] = "NOT_TESTED"
    elif gate["strict_gate_passed"]:
        result["L2_R5D_BUSINESS_PILOT"] = "PASSED"
        result["L2_REAL_MODEL_EFFECTIVENESS"] = "PILOT_PASSED"
    else:
        result["L2_R5D_BUSINESS_PILOT"] = "REJECTED"
        result["L2_REAL_MODEL_EFFECTIVENESS"] = "CALIBRATION_REQUIRED"
    result["PRODUCTION_ELIGIBLE"] = False

    if write_report:
        _write_outputs(review_dir, rows, stats, gate, result)
    return result


def _write_outputs(
    review_dir: Path,
    rows: list[dict[str, Any]],
    stats: dict[str, Any] | None,
    gate: dict[str, Any] | None,
    result: dict[str, Any],
) -> None:
    payload = {
        "schema_version": "xcue.l2-human-review-summary/1.0",
        "phase": "R5D",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": result.get("status"),
        "cases": rows,
        "statistics": stats,
        "gate_result": gate,
        "labels": {
            "L2_R5D_BUSINESS_PILOT": result.get("L2_R5D_BUSINESS_PILOT"),
            "L2_REAL_MODEL_EFFECTIVENESS": result.get("L2_REAL_MODEL_EFFECTIVENESS"),
            "PRODUCTION_ELIGIBLE": result.get("PRODUCTION_ELIGIBLE"),
        },
    }
    (review_dir / "人工评分汇总.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# R5D 人工评分汇总",
        "",
        f"- 状态: `{result.get('L2_R5D_BUSINESS_PILOT')}`",
        f"- 模型效果: `{result.get('L2_REAL_MODEL_EFFECTIVENESS')}`",
        f"- 未完成评分: `{result.get('unreviewed_remaining')}`",
        "",
    ]
    if stats:
        lines.append("## 指标统计（严格口径：仅 PASS 计通过）")
        lines.append("")
        for field in SCORE_FIELDS:
            counts = stats["per_metric"][field]
            lines.append(
                f"- `{field}`: PASS={counts.get('PASS', 0)}, REVIEW={counts.get('REVIEW', 0)}, FAIL={counts.get('FAIL', 0)}"
            )
        lines.extend(
            [
                "",
                f"- A 类 diagnosis PASS: {stats['a_class_diagnosis_pass']}/{stats['a_class_total']}",
                f"- B 类误诊: {stats['b_class_misdiagnosis']}/{stats['b_class_total']}",
                f"- 跨模块越权 FAIL: {stats['cross_module_overreach_fail']}",
                f"- 范围违规 FAIL: {stats['forbidden_scope_fail']}",
                "",
            ]
        )
    if gate:
        lines.append("## 门槛判定")
        lines.append("")
        for name, ok in gate["checks"].items():
            lines.append(f"- {name}: {'PASS' if ok else 'FAIL'}")
        if gate.get("veto_cases"):
            lines.append(f"- 否决案例: {', '.join(gate['veto_cases'])}")
        lines.append("")
    (review_dir / "人工评分汇总.md").write_text("\n".join(lines), encoding="utf-8")

    if result.get("status") != "INCOMPLETE" and stats and gate:
        report_lines = [
            "# R5D 最终业务评审报告",
            "",
            f"生成时间：{datetime.now(timezone.utc).isoformat()}",
            "",
            "## 状态标签",
            "",
            "```",
            f"L2_R5D_BUSINESS_PILOT = {result.get('L2_R5D_BUSINESS_PILOT')}",
            f"L2_REAL_MODEL_EFFECTIVENESS = {result.get('L2_REAL_MODEL_EFFECTIVENESS')}",
            "PRODUCTION_ELIGIBLE = false",
            "```",
            "",
            "## 历史对照（只读）",
            "",
            "- R5A 技术协议：FAILED（L2P-004/011/012）",
            "- R5B 定向四例：PASSED；全量：FAILED（L2P-007）",
            "- R5C 全量技术协议：PASSED",
            "",
        ]
        (review_dir / "R5D_最终业务评审报告.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="R5D L2 人工业务评分汇总（只读）")
    parser.add_argument(
        "--review-dir",
        type=str,
        default=str(PILOT / "results" / "R5D_人工业务评审_20260628"),
        help="评审目录",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="仅校验字段与 NOT_REVIEWED 状态，不写入最终结论",
    )
    args = parser.parse_args()
    review_dir = Path(args.review_dir)
    if not review_dir.is_dir():
        print(f"MISSING_REVIEW_DIR: {review_dir}")
        return 1
    result = summarize(review_dir, write_report=not args.validate_only)
    if result.get("validation_errors"):
        print("VALIDATION_FAIL")
        for err in result["validation_errors"]:
            print(err)
        return 1
    if result.get("unreviewed_remaining"):
        print("VALIDATION_OK")
        print("STATUS: AWAITING_HUMAN_REVIEW")
        print(f"cases: {result.get('case_count')}")
        print("L2_R5D_BUSINESS_PILOT = INCOMPLETE")
        print("L2_REAL_MODEL_EFFECTIVENESS = NOT_TESTED")
        return 0
    print("SUMMARY_OK")
    print(f"L2_R5D_BUSINESS_PILOT = {result.get('L2_R5D_BUSINESS_PILOT')}")
    print(f"L2_REAL_MODEL_EFFECTIVENESS = {result.get('L2_REAL_MODEL_EFFECTIVENESS')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
