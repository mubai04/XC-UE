from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"
PUBLIC = EXEC / "公共组件"
L1 = EXEC / "L1工程"
for path in (PUBLIC, L1):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from L1_语义审计 import 审计  # noqa: E402
from L1_语义上下文 import 构建语义上下文  # noqa: E402
from L1读取 import 读文本  # noqa: E402
from L1模型 import 检测项, 证据  # noqa: E402
from 正文切分 import 切段, 清理正文  # noqa: E402
from 语义证据校验 import REQUIRED_DIMENSIONS  # noqa: E402
from 运行状态 import 审计阻断  # noqa: E402

GOLDEN_ROOT = ROOT / "tests" / "fixtures" / "l1_semantic_golden"
ARCHIVE_ROOT = ROOT / "审计纠偏_2026-06-26" / "L1_Phase2A_首次真实API评估"
BASELINE_PATH = ROOT / "审计纠偏_2026-06-26" / "AUDIT_BASELINE.json"
EVALUATOR_VERSION = "xcue.l1-evaluator/r3"
RESPONSE_SCHEMA_VERSION = "xcue.l1-semantic-response/phase2a"
DATASET_ID = "l1_semantic_golden_v1"
DATASET_VERSION = "1.0"

REQUIRED_SCENARIO_TAGS = frozenset(
    {
        "clear_pass",
        "clear_fail",
        "debatable_review",
        "low_lexical_good_narrative",
        "high_lexical_bad_narrative",
    }
)
SEMANTIC_DIMENSION_NAMES = frozenset(REQUIRED_DIMENSIONS)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_calibration_subset(golden_root: Path) -> list[str]:
    plan_path = golden_root / "CALIBRATION_PLAN.json"
    if not plan_path.is_file():
        raise SystemExit(f"缺少 CALIBRATION_PLAN.json：{plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    subset = plan.get("calibration_subset") or []
    if not isinstance(subset, list) or not subset:
        raise SystemExit("CALIBRATION_PLAN.json 缺少 calibration_subset")
    return [str(item) for item in subset]


def _git_commit() -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _git_dirty() -> bool:
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return bool(proc.stdout.strip())


def _evaluation_archive_metadata(golden_root: Path) -> dict[str, Any]:
    baseline = {}
    if BASELINE_PATH.is_file():
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    prompt_hashes: dict[str, str] = {}
    governed = baseline.get("governed_prompt_evaluator_hashes", {}).get("files", [])
    for entry in governed:
        prompt_hashes[entry["path"]] = entry["sha256"]

    label_hashes: dict[str, str] = {}
    labels_dir = golden_root / "labels"
    for path in sorted(labels_dir.glob("*.json")):
        label_hashes[path.relative_to(ROOT).as_posix()] = _sha256_file(path)

    return {
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "baseline_digest": baseline.get("baseline_digest"),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "evaluator_version": EVALUATOR_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "prompt_hashes": prompt_hashes,
        "label_hashes": label_hashes,
    }


def _scenario_tags(label: dict) -> set[str]:
    tags: set[str] = set()
    primary = str(label.get("scenario_tag", "")).strip()
    if primary:
        tags.add(primary)
    secondary = label.get("secondary_scenario_tags", [])
    if isinstance(secondary, list):
        tags.update(str(tag).strip() for tag in secondary if str(tag).strip())
    return tags


def _semantic_dimension_items(items: list[检测项]) -> list[检测项]:
    selected: list[检测项] = []
    for item in items:
        if not item.名称.startswith("语义审计·"):
            continue
        dim_name = item.名称.replace("语义审计·", "")
        if dim_name in SEMANTIC_DIMENSION_NAMES:
            selected.append(item)
    return selected


@dataclass
class EvalMetrics:
    first_pass_evidence_valid_rate: float = 0.0
    eventual_evidence_valid_rate: float = 0.0
    evidence_retry_rate: float = 0.0
    transport_retry_rate: float = 0.0
    format_retry_rate: float = 0.0
    audit_blocked_rate: float = 0.0
    overall_agreement: float = 0.0
    dimension_agreement: float | None = None
    chapter_results: list[dict] = field(default_factory=list)


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_label(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _in_range(actual: str, allowed: list[str]) -> bool:
    return actual in allowed


def _item_to_dict(item: 检测项) -> dict[str, Any]:
    return {
        **item.__dict__,
        "证据": [asdict(e) if isinstance(e, 证据) else e for e in item.证据],
    }


def _dimension_allowed(label: dict, dim_name: str, actual: str) -> tuple[str, list[str], bool, str]:
    acceptance = label.get("acceptance_range", {})
    dimension_acceptance = acceptance.get("dimensions", {})
    expected_dimensions = label.get("expected_dimensions", {})
    expected_spec = expected_dimensions.get(dim_name, {})
    human_rationale = ""
    if isinstance(expected_spec, dict):
        expected_verdict = str(expected_spec.get("expected_verdict", actual)).upper()
        default_allowed = expected_spec.get("acceptance_range", [expected_verdict])
        human_rationale = str(expected_spec.get("rationale", "")).strip()
    else:
        expected_verdict = str(expected_spec or actual).upper()
        default_allowed = [expected_verdict]
    allowed = dimension_acceptance.get(dim_name, default_allowed)
    return expected_verdict, allowed, _in_range(actual, allowed), human_rationale


def _reports_by_dimension(result) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for report in result.维度报告:
        if isinstance(report, dict):
            grouped[str(report.get("dimension", ""))] = report
        else:
            grouped[str(report.dimension)] = asdict(report)
    return grouped


def _evaluate_chapter(chapter_path: Path, label: dict) -> dict[str, Any]:
    raw = 读文本(chapter_path)
    title, body = 清理正文(raw)
    paragraphs = 切段(body)
    context = 构建语义上下文(
        chapter_path=chapter_path,
        title=title,
        body=body,
        paragraphs=paragraphs,
        project=None,
    )
    result = 审计(context)
    first_pass = result.meta.evidence_retry_count == 0 and result.meta.format_retry_count == 0
    eventual_valid = result.可用
    overall = result.整体结论 if result.可用 else 审计阻断
    acceptance = label.get("acceptance_range", {})
    overall_allowed = acceptance.get("overall", [label["expected_overall"]])
    overall_ok = _in_range(overall, overall_allowed)
    report_map = _reports_by_dimension(result)

    audit_blocked = overall == 审计阻断 or not result.可用
    dim_scores: list[bool] = []
    dimension_details: list[dict[str, Any]] = []
    if not audit_blocked:
        for item in _semantic_dimension_items(result.检测项列表):
            dim_name = item.名称.replace("语义审计·", "")
            actual = {"通过": "PASS", "风险": "REVIEW", "失败": "FAIL"}.get(item.状态, item.状态)
            expected_verdict, allowed, ok, human_rationale = _dimension_allowed(label, dim_name, actual)
            dim_scores.append(ok)
            report = report_map.get(dim_name, {})
            dimension_details.append(
                {
                    "dimension": dim_name,
                    "expected": expected_verdict,
                    "actual": actual,
                    "allowed": allowed,
                    "verdict_agreement": ok,
                    "human_rationale": human_rationale,
                    "evidence_location_valid": report.get("evidence_location_valid"),
                    "evidence_protocol_compliant": report.get("evidence_protocol_compliant"),
                    "evidence_semantically_sufficient": report.get("evidence_semantically_sufficient"),
                    "semantic_support": report.get("semantic_support"),
                    "strength_summary": report.get("strength_summary", ""),
                    "risk_summary": report.get("risk_summary", ""),
                    "final_reason": report.get("final_reason", ""),
                    "evidence_rationale": report.get("evidence_rationale", ""),
                }
            )

    expected = str(label["expected_overall"]).upper()
    hard_pass = expected == "PASS" and overall != "FAIL"
    hard_fail = expected == "FAIL" and overall != "PASS"
    review_ok = expected != "REVIEW" or overall_ok
    dimension_agreement = sum(dim_scores) / len(dim_scores) if dim_scores else None

    return {
        "chapter_id": label.get("chapter_id", chapter_path.stem),
        "scenario_tag": label.get("scenario_tag", ""),
        "secondary_scenario_tags": label.get("secondary_scenario_tags", []),
        "scenario_tags": sorted(_scenario_tags(label)),
        "expected_overall": expected,
        "actual_overall": overall,
        "first_pass_evidence_valid": first_pass and eventual_valid,
        "eventual_evidence_valid": eventual_valid,
        "evidence_retry_count": result.meta.evidence_retry_count,
        "transport_retry_count": result.meta.transport_retry_count,
        "format_retry_count": result.meta.format_retry_count,
        "audit_blocked": audit_blocked,
        "overall_agreement": overall_ok,
        "dimension_agreement": dimension_agreement,
        "hard_pass": hard_pass,
        "hard_fail": hard_fail,
        "review_ok": review_ok,
        "dimension_details": dimension_details,
        "errors": result.错误 or [],
        "warnings": result.meta.warnings,
        "raw_api_response": result.原始响应,
        "meta": asdict(result.meta),
        "dimension_reports": list(report_map.values()),
        "detection_items": [_item_to_dict(item) for item in result.检测项列表],
    }


def _pilot_verdict(rows: list[dict], scenario_tags: set[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    for row in rows:
        cid = row["chapter_id"]
        expected = row["expected_overall"]
        actual = row["actual_overall"]
        if expected == "PASS" and actual == "FAIL":
            reasons.append(f"{cid}: 明确 PASS 章不得 FAIL（实际 {actual}）")
        if expected == "FAIL" and actual == "PASS":
            reasons.append(f"{cid}: 明确 FAIL 章不得 PASS（实际 {actual}）")
        if expected == "REVIEW" and not row["review_ok"]:
            reasons.append(f"{cid}: REVIEW 章超出 acceptance_range（实际 {actual}）")
        if row["audit_blocked"] and expected in {"PASS", "FAIL", "REVIEW"}:
            reasons.append(f"{cid}: 非输入损坏章节出现 AUDIT_BLOCKED")
    missing = REQUIRED_SCENARIO_TAGS - scenario_tags
    if missing:
        reasons.append(f"五类场景未全覆盖：{', '.join(sorted(missing))}")
    if reasons:
        return "PILOT_REJECTED", reasons
    return "PILOT_VALIDATED", []


def _calibration_verdict(row: dict, label: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    cid = row["chapter_id"]
    if not row["eventual_evidence_valid"]:
        reasons.append(f"{cid}: eventual evidence 无效")
    if row["audit_blocked"]:
        reasons.append(f"{cid}: AUDIT_BLOCKED")
    if not row["overall_agreement"]:
        reasons.append(
            f"{cid}: overall 模型={row['actual_overall']} 不在 acceptance_range={label['acceptance_range']['overall']}"
        )
    for dim in row["dimension_details"]:
        if dim.get("evidence_location_valid") is False:
            reasons.append(f"{cid}/{dim['dimension']}: evidence_location_valid=False")
        protocol_ok = dim.get("evidence_protocol_compliant")
        if protocol_ok is False or (
            protocol_ok is None and dim.get("evidence_semantically_sufficient") is False
        ):
            reasons.append(f"{cid}/{dim['dimension']}: evidence_protocol_compliant=False")
        if not dim.get("verdict_agreement"):
            reasons.append(
                f"{cid}/{dim['dimension']}: 模型={dim['actual']} 人工={dim['expected']}；"
                f"模型理由={dim.get('final_reason', '')}；人工理由={dim.get('human_rationale', '')}"
            )
    if reasons:
        return "MODEL_CALIBRATION_REJECTED", reasons
    return "MODEL_CALIBRATION_PASSED", []


def _aggregate_metrics(rows: list[dict]) -> EvalMetrics:
    metrics = EvalMetrics()
    metrics.chapter_results = rows
    total = len(rows)
    if total == 0:
        return metrics

    first_pass = sum(int(row["first_pass_evidence_valid"]) for row in rows)
    eventual = sum(int(row["eventual_evidence_valid"]) for row in rows)
    evidence_retry = sum(int(row["evidence_retry_count"] > 0) for row in rows)
    transport_retry = sum(int(row["transport_retry_count"] > 0) for row in rows)
    format_retry = sum(int(row["format_retry_count"] > 0) for row in rows)
    blocked = sum(int(row["audit_blocked"]) for row in rows)
    overall_hits = sum(int(row["overall_agreement"]) for row in rows)

    dim_rows = [row for row in rows if row.get("dimension_agreement") is not None]
    dim_hits = sum(float(row["dimension_agreement"]) for row in dim_rows)

    metrics.first_pass_evidence_valid_rate = first_pass / total
    metrics.eventual_evidence_valid_rate = eventual / total
    metrics.evidence_retry_rate = evidence_retry / total
    metrics.transport_retry_rate = transport_retry / total
    metrics.format_retry_rate = format_retry / total
    metrics.audit_blocked_rate = blocked / total
    metrics.overall_agreement = overall_hits / total
    metrics.dimension_agreement = dim_hits / len(dim_rows) if dim_rows else None
    return metrics


def run_eval(*, golden_root: Path, chapter_id: str | None = None) -> tuple[EvalMetrics, dict, set[str]]:
    import os

    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        raise SystemExit("缺少 DEEPSEEK_API_KEY，请先配置后再运行 Phase 2A 真实 API 评估。")

    manifest = _load_manifest(golden_root / "manifest.json")
    chapters = manifest.get("chapters") or []
    if chapter_id:
        chapters = [entry for entry in chapters if entry.get("chapter_id") == chapter_id]
        if not chapters:
            raise SystemExit(f"manifest 中未找到 chapter_id={chapter_id}")

    if not chapters:
        raise SystemExit(f"验收集为空：{golden_root}")

    chapter_results: list[dict] = []
    scenario_tags: set[str] = set()
    labels_by_id: dict[str, dict] = {}
    for entry in chapters:
        chapter_path = golden_root / str(entry["chapter_path"])
        label_path = golden_root / str(entry["label_path"])
        if not label_path.is_file():
            raise SystemExit(f"标签未就绪：{label_path}")
        label = _load_label(label_path)
        row = _evaluate_chapter(chapter_path, label)
        chapter_results.append(row)
        labels_by_id[row["chapter_id"]] = label
        scenario_tags.update(row.get("scenario_tags", []))

    metrics = _aggregate_metrics(chapter_results)
    if chapter_id:
        label = labels_by_id[chapter_id]
        pilot_status, pilot_reasons = _calibration_verdict(chapter_results[0], label)
        evaluation_kind = "SINGLE_CHAPTER_CALIBRATION"
    else:
        pilot_status, pilot_reasons = _pilot_verdict(chapter_results, scenario_tags)
        evaluation_kind = "REAL_API_RUN"

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "2A.1",
        "evaluation_kind": evaluation_kind,
        "pilot_status": pilot_status,
        "pilot_reasons": pilot_reasons,
        "metrics": {k: v for k, v in asdict(metrics).items() if k != "chapter_results"},
        "chapter_results": chapter_results,
        "scenario_tags_present": sorted(scenario_tags),
        **_evaluation_archive_metadata(golden_root),
    }
    return metrics, payload, scenario_tags


def _archive_path(run_id: str) -> Path:
    return ARCHIVE_ROOT / f"{run_id}.json"


def _run_calibration_gate(golden_root: Path, subset: list[str]) -> int:
    for cid in subset:
        label_path = golden_root / "labels" / f"{cid}.labels.json"
        if not label_path.is_file():
            raise SystemExit(f"校准子集标签不存在：{label_path}")
        label = _load_label(label_path)
        _, cal_payload, _ = run_eval(golden_root=golden_root, chapter_id=cid)
        if cal_payload["pilot_status"] == "MODEL_CALIBRATION_REJECTED":
            print(json.dumps(cal_payload, ensure_ascii=False, indent=2))
            print("MODEL_CALIBRATION_REJECTED: 单章校准未通过。")
            return 2
        _ = label
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="L1 Phase 2A golden corpus evaluation (real API only)")
    parser.add_argument("--golden-root", default=str(GOLDEN_ROOT))
    parser.add_argument("--chapter-id", default="", help="仅评估单章，配合 --no-archive 做试跑")
    parser.add_argument("--no-archive", action="store_true", help="不写归档文件，仅 stdout 输出")
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--force-new-run",
        action="store_true",
        help="允许追加新 run-id；不得覆盖已有归档文件",
    )
    parser.add_argument(
        "--require-calibration-pass",
        action="store_true",
        help="全量评估前按 CALIBRATION_PLAN.json 跑单章校准门禁",
    )
    args = parser.parse_args()

    golden_root = Path(args.golden_root)
    chapter_id = args.chapter_id.strip() or None

    if args.require_calibration_pass and not chapter_id:
        gate_code = _run_calibration_gate(golden_root, _load_calibration_subset(golden_root))
        if gate_code != 0:
            return gate_code

    _, payload, _ = run_eval(golden_root=golden_root, chapter_id=chapter_id)

    if args.no_archive:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if chapter_id:
            row = payload["chapter_results"][0]
            print(
                json.dumps(
                    {
                        "chapter_id": chapter_id,
                        "pilot_status": payload["pilot_status"],
                        "eventual_evidence_valid": row["eventual_evidence_valid"],
                        "audit_blocked": row["audit_blocked"],
                        "evidence_retry_count": row["evidence_retry_count"],
                        "overall_agreement": row["overall_agreement"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0 if payload["pilot_status"] != "MODEL_CALIBRATION_REJECTED" else 2

    run_id = args.run_id or f"L1_Phase2A_FIRST_REAL_API_{datetime.now():%Y%m%d_%H%M%S}"
    archive = _archive_path(run_id)

    if (
        not args.force_new_run
        and not args.run_id
        and ARCHIVE_ROOT.exists()
        and any(ARCHIVE_ROOT.glob("L1_Phase2A_FIRST_REAL_API_*.json"))
    ):
        existing = sorted(ARCHIVE_ROOT.glob("L1_Phase2A_FIRST_REAL_API_*.json"))
        raise SystemExit(
            "首次真实 API 评估归档已存在，不得覆盖："
            + "；".join(p.name for p in existing)
            + "。如需追加新 run，请显式传入 --run-id 与 --force-new-run。"
        )
    if archive.exists():
        raise SystemExit(f"归档已存在，拒绝覆盖：{archive}")

    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    payload["run_id"] = run_id
    payload["evaluation_kind"] = "REAL_API_RUN"
    archive.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"pilot_status": payload["pilot_status"], "metrics": payload["metrics"]}, ensure_ascii=False, indent=2))
    if payload["pilot_reasons"]:
        print("pilot_reasons:")
        for reason in payload["pilot_reasons"]:
            print(f"- {reason}")
    print(f"archived: {archive}")
    return 0 if payload["pilot_status"] == "PILOT_VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
