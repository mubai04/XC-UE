#!/usr/bin/env python3
"""Freeze pre-remediation audit baseline (R0).

Collects working-tree state BEFORE writing any artifacts.
Generates AUDIT_BASELINE.json (stable_payload → baseline_digest),
RUNTIME_SNAPSHOT.json, FREEZE_RECORD.json, CALIBRATION_PLAN.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "审计纠偏_2026-06-26" / "AUDIT_BASELINE.json"
RUNTIME_SNAPSHOT_PATH = ROOT / "审计纠偏_2026-06-26" / "RUNTIME_SNAPSHOT.json"
GOLDEN_ROOT = ROOT / "tests" / "fixtures" / "l1_semantic_golden"
FREEZE_RECORD_PATH = GOLDEN_ROOT / "FREEZE_RECORD.json"
CALIBRATION_PLAN_PATH = GOLDEN_ROOT / "CALIBRATION_PLAN.json"
API_ARCHIVE_DIR = ROOT / "审计纠偏_2026-06-26" / "L1_Phase2A_首次真实API评估"
EXEC = ROOT / "00_工程总控" / "工程执行层"
STRUCT_DEF = EXEC / "公共组件" / "结构定义"

BASELINE_STATE = "INTEGRATED_CANDIDATE_WITH_BLOCKERS"
LEGACY_STATE_TAG = "CURRENT_STATE_A2_MINUS"

RULE_SCHEMA_PATHS = [
    STRUCT_DEF / "第三层任务包结构.json",
    STRUCT_DEF / "第一层报告结构.json",
    STRUCT_DEF / "流水线清单结构.json",
    STRUCT_DEF / "产物记录结构.json",
    STRUCT_DEF / "第三层补丁审计结构.json",
    STRUCT_DEF / "审计阻断项结构.json",
    STRUCT_DEF / "失败包结构.json",
    STRUCT_DEF / "第二层报告结构.json",
    STRUCT_DEF / "L1语义审计响应结构.json",
    EXEC / "L1工程" / "gate_rules.json",
    EXEC / "L2工程" / "ability_rules.json",
    EXEC / "L2工程" / "routes.json",
    EXEC / "L3工程" / "protocol_rules.json",
]

GOVERNED_PROMPT_EVALUATOR_PATHS = [
    EXEC / "L1工程" / "L1_语义标尺.py",
    EXEC / "L1工程" / "L1_语义审计.py",
    EXEC / "L1工程" / "L1_语义上下文.py",
    EXEC / "公共组件" / "语义证据校验.py",
    EXEC / "L2工程" / "L2_01_叙事结构能力.py",
    EXEC / "L3工程" / "候选正文生成.py",
    ROOT / "scripts" / "eval_l1_semantic_golden.py",
    ROOT / "scripts" / "validate_l1_semantic_golden.py",
]

BASELINE_ARTIFACT_RELS = frozenset(
    {
        "审计纠偏_2026-06-26/AUDIT_BASELINE.json",
        "审计纠偏_2026-06-26/RUNTIME_SNAPSHOT.json",
        "审计纠偏_2026-06-26/REMEDIATION_RESULT_R0_R3.json",
        "tests/fixtures/l1_semantic_golden/FREEZE_RECORD.json",
        "tests/fixtures/l1_semantic_golden/CALIBRATION_PLAN.json",
    }
)

CALIBRATION_SUBSET_DEFAULT = ["GS-001", "GS-005"]

FREEZE_POLICY = {
    "golden_v1_read_only": True,
    "phase2a_archive_read_only": True,
    "calibration_plan_mutable_control_file": True,
    "forbidden_during_remediation": [
        "modify GS-001/GS-005 labels to chase calibration pass",
        "modify golden v1 chapter bodies or human labels",
        "modify L1 prompts to chase calibration pass",
        "third full real API evaluation",
        "add frozen/baseline_ref/calibration_subset to v1 manifest.json",
    ],
    "notes": "Golden v1 manifest/chapters/labels/paragraph_maps frozen after R0. "
    "CALIBRATION_PLAN.json is mutable control metadata, not frozen corpus. "
    "Freeze metadata lives in FREEZE_RECORD.json (not hashed into golden_v1_hashes).",
}


def _norm_rel(path: str) -> str:
    return path.replace("\\", "/").strip()


def _relative_to_root(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _is_baseline_artifact(rel_path: str) -> bool:
    return _norm_rel(rel_path) in BASELINE_ARTIFACT_RELS


def _filter_baseline_artifacts(paths: list[str]) -> list[str]:
    return sorted({p for p in paths if not _is_baseline_artifact(p)})


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_paths(paths: list[Path], *, label: str) -> dict[str, Any]:
    entries: list[dict[str, str]] = []
    missing: list[str] = []
    for path in sorted(paths, key=lambda p: p.as_posix()):
        if not path.is_file():
            missing.append(path.as_posix())
            continue
        rel = path.relative_to(ROOT).as_posix()
        entries.append({"path": rel, "sha256": _sha256_file(path)})
    if missing:
        print(f"WARNING: missing {label} files: {', '.join(missing)}", file=sys.stderr)
    return {"files": entries, "count": len(entries)}


def _collect_golden_v1_hashes() -> dict[str, Any]:
    """Golden v1 frozen corpus only — excludes FREEZE_RECORD and CALIBRATION_PLAN."""
    groups: dict[str, list[Path]] = {
        "chapters": sorted((GOLDEN_ROOT / "chapters").glob("*.md")),
        "labels": sorted((GOLDEN_ROOT / "labels").glob("*.json")),
        "paragraph_maps": sorted((GOLDEN_ROOT / "paragraph_maps").glob("*.json")),
    }
    manifest_path = GOLDEN_ROOT / "manifest.json"
    result: dict[str, Any] = {}
    for name, paths in groups.items():
        result[name] = _hash_paths(list(paths), label=f"golden v1 {name}")
    result["manifest"] = _hash_paths([manifest_path], label="golden v1 manifest")
    return result


def _collect_rule_schema_hashes() -> dict[str, Any]:
    struct_paths = sorted(STRUCT_DEF.glob("*.json"), key=lambda p: p.as_posix())
    seen: set[str] = set()
    unique: list[Path] = []
    for path in struct_paths + RULE_SCHEMA_PATHS:
        key = path.resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return _hash_paths(unique, label="rules/schemas")


def _collect_governed_hashes() -> dict[str, Any]:
    return _hash_paths(GOVERNED_PROMPT_EVALUATOR_PATHS, label="governed prompts/evaluators")


def _collect_api_archive_index() -> dict[str, Any]:
    if not API_ARCHIVE_DIR.is_dir():
        print(f"WARNING: API archive missing: {API_ARCHIVE_DIR}", file=sys.stderr)
        return {"files": [], "count": 0}
    files = sorted(API_ARCHIVE_DIR.iterdir(), key=lambda p: p.name)
    entries = [
        {
            "path": p.relative_to(ROOT).as_posix(),
            "sha256": _sha256_file(p),
        }
        for p in files
        if p.is_file()
    ]
    return {"files": entries, "count": len(entries)}


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=False,
        check=False,
    )


def _parse_porcelain_z(raw: bytes) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not raw:
        return entries
    parts = raw.split(b"\0")
    i = 0
    while i < len(parts):
        chunk = parts[i]
        if not chunk:
            i += 1
            continue
        try:
            line = chunk.decode("utf-8", errors="replace")
        except Exception:
            i += 1
            continue
        if len(line) < 3:
            i += 1
            continue
        xy = line[:2]
        body = line[3:]
        entry: dict[str, str] = {"xy": xy, "raw": line}
        if xy.startswith("R") and i + 1 < len(parts) and parts[i + 1]:
            old_path = body
            new_path = parts[i + 1].decode("utf-8", errors="replace")
            entry["path"] = new_path
            entry["old_path"] = old_path
            i += 2
        else:
            entry["path"] = body
            i += 1
        entries.append(entry)
    return entries


def _collect_git_state() -> dict[str, Any]:
    state: dict[str, Any] = {
        "git_commit": None,
        "git_status_porcelain": [],
        "git_dirty_files": [],
        "git_untracked_files": [],
        "git_dirty_diff_hash": None,
        "git_dirty_diff_hash_excluding_baseline_artifacts": None,
        "warnings": [],
    }
    if _run_git(["rev-parse", "HEAD"]).returncode != 0:
        state["warnings"].append("git not available or not a repository")
        return state

    state["git_commit"] = _run_git(["rev-parse", "HEAD"]).stdout.decode("utf-8", errors="replace").strip()
    porcelain_raw = _run_git(["status", "--porcelain=v1", "-z"]).stdout
    parsed = _parse_porcelain_z(porcelain_raw)

    porcelain_lines: list[str] = []
    dirty_files: list[str] = []
    untracked_entries: list[dict[str, str]] = []

    for entry in parsed:
        porcelain_lines.append(entry["raw"])
        rel_path = _norm_rel(entry["path"])
        if _is_baseline_artifact(rel_path):
            continue
        dirty_files.append(rel_path)
        if entry["xy"] == "??":
            abs_path = (ROOT / rel_path).resolve()
            if abs_path.is_file():
                untracked_entries.append(
                    {"path": rel_path, "sha256": _sha256_file(abs_path)}
                )
            elif abs_path.is_dir():
                state["warnings"].append(f"untracked directory not hashed: {rel_path}")

    state["git_status_porcelain"] = porcelain_lines
    state["git_dirty_files"] = sorted(set(dirty_files))
    state["git_untracked_files"] = sorted(untracked_entries, key=lambda e: e["path"])

    diff_parts: list[str] = []
    for diff_cmd in (["diff"], ["diff", "--cached"]):
        proc = _run_git(diff_cmd)
        if proc.stdout:
            diff_parts.append(proc.stdout.decode("utf-8", errors="replace"))
    combined = "\n".join(diff_parts)
    state["git_dirty_diff_hash"] = _sha256_text(combined) if combined else _sha256_text("")

    pathspec_args = ["--", "."] + [f":!{rel}" for rel in sorted(BASELINE_ARTIFACT_RELS)]
    filtered_diff_parts: list[str] = []
    for diff_cmd in (["diff"], ["diff", "--cached"]):
        proc = _run_git(diff_cmd + pathspec_args)
        if proc.stdout:
            filtered_diff_parts.append(proc.stdout.decode("utf-8", errors="replace"))
    filtered_combined = "\n".join(filtered_diff_parts)
    state["git_dirty_diff_hash_excluding_baseline_artifacts"] = (
        _sha256_text(filtered_combined) if filtered_combined else _sha256_text("")
    )
    return state


def _parse_pytest_summary(output: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "xfailed": 0,
        "xpassed": 0,
        "deselected": 0,
        "raw_summary_line": None,
    }
    candidates: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("="):
            continue
        if re.search(r"\d+\s+(passed|failed|skipped|error)", stripped):
            candidates.append(stripped)
    if candidates:
        summary["raw_summary_line"] = candidates[-1]

    if not summary["raw_summary_line"]:
        return summary

    text = summary["raw_summary_line"]
    for key, pattern in (
        ("failed", r"(\d+)\s+failed"),
        ("passed", r"(\d+)\s+passed"),
        ("skipped", r"(\d+)\s+skipped"),
        ("errors", r"(\d+)\s+error"),
        ("xfailed", r"(\d+)\s+xfailed"),
        ("xpassed", r"(\d+)\s+xpassed"),
        ("deselected", r"(\d+)\s+deselected"),
    ):
        match = re.search(pattern, text)
        if match:
            summary[key] = int(match.group(1))
    return summary


def _run_pytest_collection() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    nodeids: list[str] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("=") or stripped.endswith("tests collected"):
            continue
        if stripped.startswith("no tests collected"):
            continue
        if "::" in stripped and not stripped.startswith("<"):
            nodeids.append(stripped)
    sorted_nodeids = sorted(nodeids)
    return {
        "exit_code": proc.returncode,
        "nodeids": sorted_nodeids,
        "count": len(sorted_nodeids),
        "stderr": proc.stderr.strip() or None,
    }


def _run_pytest_execution() -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    finished = datetime.now(timezone.utc)
    summary = _parse_pytest_summary(proc.stdout + "\n" + proc.stderr)
    return {
        "exit_code": proc.returncode,
        "summary": summary,
        "duration_seconds": (finished - started).total_seconds(),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "stderr": proc.stderr.strip() or None,
    }


def _build_stable_payload(
    *,
    git_state: dict[str, Any],
    pytest_collection: dict[str, Any],
    golden_v1_hashes: dict[str, Any],
    rules_schemas_hashes: dict[str, Any],
    governed_prompt_evaluator_hashes: dict[str, Any],
    api_archive_index: dict[str, Any],
) -> dict[str, Any]:
    filtered_porcelain = [
        line
        for line in git_state["git_status_porcelain"]
        if not _is_baseline_artifact(_norm_rel(line[3:].split(" -> ", 1)[-1].strip()))
    ]
    return {
        "schema_version": "xcue.audit-baseline-stable/1.0",
        "baseline_state": BASELINE_STATE,
        "legacy_state_tag": LEGACY_STATE_TAG,
        "git_commit": git_state["git_commit"],
        "git_status_porcelain": filtered_porcelain,
        "git_dirty_files": _filter_baseline_artifacts(list(git_state["git_dirty_files"])),
        "git_untracked_files": git_state["git_untracked_files"],
        "git_dirty_diff_hash": git_state["git_dirty_diff_hash_excluding_baseline_artifacts"],
        "pytest_collection": {
            "count": pytest_collection["count"],
            "nodeids": pytest_collection["nodeids"],
        },
        "golden_v1_hashes": golden_v1_hashes,
        "rules_schemas_hashes": rules_schemas_hashes,
        "governed_prompt_evaluator_hashes": governed_prompt_evaluator_hashes,
        "api_archive_index": api_archive_index,
        "freeze_policy": FREEZE_POLICY,
    }


def _compute_baseline_digest(stable_payload: dict[str, Any]) -> str:
    return _sha256_text(_canonical_json(stable_payload))


def _write_calibration_plan() -> None:
    plan = {
        "schema_version": "xcue.l1-calibration-plan/1.0",
        "phase": "2A",
        "calibration_subset": CALIBRATION_SUBSET_DEFAULT,
        "notes": "Mutable control file — not part of golden_v1_hashes. "
        "R3 eval reads calibration_subset from this file, not manifest.json. "
        "Does not authorize label or chapter edits.",
    }
    CALIBRATION_PLAN_PATH.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_freeze_record(*, baseline_rel: str, generated_at: str) -> None:
    record = {
        "schema_version": "xcue.l1-golden-freeze-record/1.0",
        "frozen": True,
        "baseline_ref": baseline_rel,
        "frozen_at": generated_at,
        "freeze_policy_ref": "AUDIT_BASELINE.json.freeze_policy",
        "notes": "Do not add frozen/baseline_ref to manifest.json. "
        "This file is not hashed into golden_v1_hashes (no self-reference).",
    }
    FREEZE_RECORD_PATH.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def collect_baseline(*, run_pytest: bool = True) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Collect all state before writing any artifact files."""
    generated_at = datetime.now(timezone.utc).isoformat()
    baseline_rel = _relative_to_root(BASELINE_PATH)

    git_state = _collect_git_state()
    pytest_collection = _run_pytest_collection()
    runtime_observation: dict[str, Any] = {
        "observed_at": generated_at,
        "pytest_collection_raw": {
            "exit_code": pytest_collection["exit_code"],
            "stderr": pytest_collection.get("stderr"),
        },
    }
    if run_pytest:
        runtime_observation["pytest_execution"] = _run_pytest_execution()

    golden_v1_hashes = _collect_golden_v1_hashes()
    rules_schemas_hashes = _collect_rule_schema_hashes()
    governed_hashes = _collect_governed_hashes()
    api_archive_index = _collect_api_archive_index()

    stable_payload = _build_stable_payload(
        git_state=git_state,
        pytest_collection=pytest_collection,
        golden_v1_hashes=golden_v1_hashes,
        rules_schemas_hashes=rules_schemas_hashes,
        governed_prompt_evaluator_hashes=governed_hashes,
        api_archive_index=api_archive_index,
    )
    baseline_digest = _compute_baseline_digest(stable_payload)

    payload: dict[str, Any] = {
        "schema_version": "xcue.audit-baseline/1.0",
        "baseline_state": BASELINE_STATE,
        "legacy_state_tag": LEGACY_STATE_TAG,
        "generated_at": generated_at,
        "baseline_digest": baseline_digest,
        "stable_payload": stable_payload,
        "runtime_observation_ref": _relative_to_root(RUNTIME_SNAPSHOT_PATH),
        "git_commit": git_state["git_commit"],
        "git_status_porcelain": git_state["git_status_porcelain"],
        "git_dirty_files": git_state["git_dirty_files"],
        "git_untracked_files": git_state["git_untracked_files"],
        "git_dirty_diff_hash": git_state["git_dirty_diff_hash"],
        "git_dirty_diff_hash_excluding_baseline_artifacts": git_state[
            "git_dirty_diff_hash_excluding_baseline_artifacts"
        ],
        "pytest_collection": pytest_collection,
        "golden_v1_hashes": golden_v1_hashes,
        "rules_schemas_hashes": rules_schemas_hashes,
        "governed_prompt_evaluator_hashes": governed_hashes,
        "api_archive_index": api_archive_index,
        "freeze_policy": FREEZE_POLICY,
        "golden_freeze_record_path": _relative_to_root(FREEZE_RECORD_PATH),
        "calibration_plan_path": _relative_to_root(CALIBRATION_PLAN_PATH),
    }
    if git_state["warnings"]:
        payload["git_warnings"] = git_state["warnings"]

    runtime_snapshot = {
        "schema_version": "xcue.runtime-snapshot/1.0",
        "baseline_ref": baseline_rel,
        "baseline_digest": baseline_digest,
        **runtime_observation,
    }
    return payload, runtime_snapshot, generated_at


def write_baseline_artifacts(
    payload: dict[str, Any],
    runtime_snapshot: dict[str, Any],
    *,
    generated_at: str,
) -> None:
    baseline_rel = _relative_to_root(BASELINE_PATH)
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RUNTIME_SNAPSHOT_PATH.write_text(
        json.dumps(runtime_snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_freeze_record(baseline_rel=baseline_rel, generated_at=generated_at)
    _write_calibration_plan()


def write_runtime_snapshot_only(*, run_pytest: bool = True) -> int:
    """Write RUNTIME_SNAPSHOT.json only; never touch AUDIT_BASELINE or freeze records."""
    if not BASELINE_PATH.is_file():
        print("REFRESH_FAILED: AUDIT_BASELINE.json missing", file=sys.stderr)
        return 1
    existing = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    generated_at = datetime.now(timezone.utc).isoformat()
    baseline_rel = _relative_to_root(BASELINE_PATH)
    runtime_observation: dict[str, Any] = {
        "observed_at": generated_at,
        "pytest_collection_raw": _run_pytest_collection(),
    }
    if run_pytest:
        runtime_observation["pytest_execution"] = _run_pytest_execution()
    runtime_snapshot = {
        "schema_version": "xcue.runtime-snapshot/1.0",
        "baseline_ref": baseline_rel,
        "baseline_digest": existing.get("baseline_digest"),
        **runtime_observation,
    }
    RUNTIME_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_SNAPSHOT_PATH.write_text(
        json.dumps(runtime_snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"RUNTIME_SNAPSHOT_REFRESHED: {_relative_to_root(RUNTIME_SNAPSHOT_PATH)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze pre-remediation audit baseline (R0)")
    parser.add_argument(
        "--skip-pytest-run",
        action="store_true",
        help="Skip full pytest execution (still runs collect-only)",
    )
    parser.add_argument(
        "--verify-digest",
        action="store_true",
        help="Compare baseline_digest with existing AUDIT_BASELINE.json stable_payload",
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Overwrite existing AUDIT_BASELINE.json (default: refuse if file exists)",
    )
    parser.add_argument(
        "--refresh-runtime-only",
        action="store_true",
        help="Refresh RUNTIME_SNAPSHOT.json only; never modify AUDIT_BASELINE.json",
    )
    args = parser.parse_args()

    if args.refresh_runtime_only:
        return write_runtime_snapshot_only(run_pytest=not args.skip_pytest_run)

    if BASELINE_PATH.is_file() and not args.force_regenerate and not args.verify_digest:
        print(
            "REFUSE_OVERWRITE: AUDIT_BASELINE.json is frozen. "
            "Use --verify-digest to check digest, or --force-regenerate to overwrite.",
            file=sys.stderr,
        )
        return 2

    if args.verify_digest:
        if not BASELINE_PATH.is_file():
            print("VERIFY_FAILED: AUDIT_BASELINE.json missing", file=sys.stderr)
            return 1
        existing = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        payload, _, _ = collect_baseline(run_pytest=not args.skip_pytest_run)
        new_digest = payload["baseline_digest"]
        old_digest = existing.get("baseline_digest")
        if new_digest == old_digest:
            print(f"VERIFY_OK baseline_digest={new_digest}")
            return 0
        print(f"VERIFY_FAILED old={old_digest} new={new_digest}", file=sys.stderr)
        return 1

    payload, runtime_snapshot, generated_at = collect_baseline(run_pytest=not args.skip_pytest_run)
    write_baseline_artifacts(payload, runtime_snapshot, generated_at=generated_at)

    print("BASELINE_FROZEN")
    print(f"path: {_relative_to_root(BASELINE_PATH)}")
    print(f"runtime_snapshot: {_relative_to_root(RUNTIME_SNAPSHOT_PATH)}")
    print(f"baseline_digest: {payload['baseline_digest']}")
    print(f"pytest_collection_count: {payload['pytest_collection']['count']}")
    if runtime_snapshot.get("pytest_execution"):
        ex = runtime_snapshot["pytest_execution"]
        print(f"pytest_exit_code: {ex['exit_code']}")
        print(f"pytest_summary: {ex['summary'].get('raw_summary_line')}")
    print(f"git_commit: {payload['git_commit']}")
    print(f"dirty_files: {len(payload['git_dirty_files'])}")
    print(f"untracked_hashed: {len(payload['git_untracked_files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
