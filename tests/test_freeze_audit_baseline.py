from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "freeze_audit_baseline.py"
BASELINE = ROOT / "审计纠偏_2026-06-26" / "AUDIT_BASELINE.json"
FREEZE = ROOT / "tests" / "fixtures" / "l1_semantic_golden" / "FREEZE_RECORD.json"
CAL_PLAN = ROOT / "tests" / "fixtures" / "l1_semantic_golden" / "CALIBRATION_PLAN.json"
RUNTIME = ROOT / "审计纠偏_2026-06-26" / "RUNTIME_SNAPSHOT.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_default_refuses_overwrite_when_baseline_exists():
    assert BASELINE.is_file()
    before = _sha256(BASELINE)
    proc = _run(["--skip-pytest-run"])
    assert proc.returncode == 2
    assert "REFUSE_OVERWRITE" in (proc.stderr or "")
    assert _sha256(BASELINE) == before


def test_verify_digest_is_readonly():
    before_baseline = _sha256(BASELINE)
    before_freeze = _sha256(FREEZE)
    before_plan = _sha256(CAL_PLAN)
    _run(["--verify-digest", "--skip-pytest-run"])
    assert _sha256(BASELINE) == before_baseline
    assert _sha256(FREEZE) == before_freeze
    assert _sha256(CAL_PLAN) == before_plan


def test_refresh_runtime_only_does_not_modify_baseline():
    before_baseline = _sha256(BASELINE)
    before_freeze = _sha256(FREEZE)
    proc = _run(["--refresh-runtime-only", "--skip-pytest-run"])
    assert proc.returncode == 0
    assert "RUNTIME_SNAPSHOT_REFRESHED" in (proc.stdout or "")
    assert _sha256(BASELINE) == before_baseline
    assert _sha256(FREEZE) == before_freeze
    assert RUNTIME.is_file()


def test_force_regenerate_overwrites_isolated_copy(repo_root: Path):
    work = repo_root / "运行记录" / f"freeze-force-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    baseline = work / "AUDIT_BASELINE.json"
    runtime = work / "RUNTIME_SNAPSHOT.json"
    freeze = work / "FREEZE_RECORD.json"
    plan = work / "CALIBRATION_PLAN.json"
    baseline.write_text('{"baseline_digest":"old"}\n', encoding="utf-8")
    before = _sha256(baseline)

    sys.path.insert(0, str(ROOT / "scripts"))
    import freeze_audit_baseline as fab

    old = (
        fab.BASELINE_PATH,
        fab.RUNTIME_SNAPSHOT_PATH,
        fab.FREEZE_RECORD_PATH,
        fab.CALIBRATION_PLAN_PATH,
    )
    try:
        fab.BASELINE_PATH = baseline
        fab.RUNTIME_SNAPSHOT_PATH = runtime
        fab.FREEZE_RECORD_PATH = freeze
        fab.CALIBRATION_PLAN_PATH = plan
        payload, runtime_snapshot, generated_at = fab.collect_baseline(run_pytest=False)
        fab.write_baseline_artifacts(payload, runtime_snapshot, generated_at=generated_at)
    finally:
        (
            fab.BASELINE_PATH,
            fab.RUNTIME_SNAPSHOT_PATH,
            fab.FREEZE_RECORD_PATH,
            fab.CALIBRATION_PLAN_PATH,
        ) = old

    assert _sha256(baseline) != before
    assert json.loads(baseline.read_text(encoding="utf-8")).get("schema_version")
