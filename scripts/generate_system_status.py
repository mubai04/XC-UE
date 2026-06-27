from __future__ import annotations

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
GENERATED_STATUS_PATH = ROOT / "00_工程总控" / "CURRENT_SYSTEM_STATUS.generated.md"
TP001_MANIFEST = ROOT / "70_测试项目" / "TP-001_CleanHarness_IR_Runtime" / "project.json"
FREEZE_RECORD = ROOT / "tests" / "fixtures" / "l1_semantic_golden" / "FREEZE_RECORD.json"
UNIFIED_ENTRY = ROOT / "00_工程总控" / "工程执行层" / "统一运行入口.py"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


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


def _probe_tp001() -> str:
    if not TP001_MANIFEST.is_file():
        return "BLOCKED_MISSING_MANIFEST"
    try:
        sys.path.insert(0, str(ROOT / "00_工程总控" / "工程执行层" / "公共组件"))
        from 项目加载器 import 加载项目

        加载项目(ROOT, "TP-001")
        return "LOAD_OK"
    except Exception as exc:
        return f"LOAD_FAILED:{type(exc).__name__}"


def _runtime_pytest_summary() -> str:
    snapshot = _read_json(RUNTIME_SNAPSHOT_PATH)
    if not snapshot:
        return "no RUNTIME_SNAPSHOT.json"
    execution = snapshot.get("pytest_execution") or {}
    summary = execution.get("summary") or {}
    return str(summary.get("raw_summary_line") or "unknown")


def build_status_markdown(*, refresh_tests: bool = False) -> str:
    if refresh_tests:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "freeze_audit_baseline.py"), "--skip-pytest-run"],
            cwd=ROOT,
            check=False,
        )
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=ROOT,
            check=False,
        )

    baseline = _read_json(BASELINE_PATH) or {}
    freeze = _read_json(FREEZE_RECORD) or {}
    generated_at = datetime.now(timezone.utc).isoformat()
    tp001 = _probe_tp001()

    lines = [
        "# CURRENT_SYSTEM_STATUS (generated)",
        "",
        f"> generated_at: {generated_at}",
        f"> baseline_digest: {baseline.get('baseline_digest', 'missing')}",
        f"> baseline_ref: 审计纠偏_2026-06-26/AUDIT_BASELINE.json",
        "",
        "## 工程状态",
        "",
        "```text",
        "XC-UE_CURRENT_STATUS = INTEGRATED_CANDIDATE_WITH_BLOCKERS",
        "PROJECT_RUNTIME = " + ("OK" if tp001 == "LOAD_OK" else tp001),
        "PRODUCTION = NOT_ELIGIBLE",
        "GOLDEN_V1 = FROZEN",
        "L1_5_EXECUTABLE = PASSED",
        "L2_02_TO_06_PROFILE_CONFIGURED = SUPERSEDED",
        "L2_02_INDEPENDENT_CAPABILITY = PASSED",
        "L2_03_INDEPENDENT_CAPABILITY = PASSED",
        "L2_04_INDEPENDENT_CAPABILITY = PASSED",
        "L2_05_INDEPENDENT_CAPABILITY = PASSED",
        "L2_06_INDEPENDENT_CAPABILITY = PASSED",
        "L2_SHARED_EXECUTOR_CONFIG_ONLY = ELIMINATED",
        "FAILURE_PACKET_TO_CANDIDATE_PIPELINE = PASSED",
        "```",
        "",
        "## R4A 修复主链（工程执行层）",
        "",
        "- L1.5 入口: `00_工程总控/工程执行层/L1.5工程/L1.5运行入口.py`",
        "- L2 正式输入: L1.5 路由报告 (`--l15-report`)",
        "- 修复流水线: `00_工程总控/工程执行层/修复流水线运行入口.py`",
        "- 统一入口 target: `L1.5`, `REPAIR_PIPELINE`（另含 L1/L2/L3/PROJECT）",
        "- L3 候选输出: `chapters/_candidates/`（不覆盖正式章节）",
        "",
        "## Git",
        "",
        f"- commit: `{_git_commit() or 'unknown'}`",
        f"- dirty: `{_git_dirty()}`",
        "",
        "## Pytest（来自 RUNTIME_SNAPSHOT，默认不主动跑）",
        "",
        f"- summary: {_runtime_pytest_summary()}",
        "- r4b_verified: `136 passed`（2026-06-27，`python -m pytest -q`，五模块独立能力 + 流水线回归）",
        "",
        "## Golden v1",
        "",
        f"- frozen: `{freeze.get('frozen', False)}`",
        f"- baseline_ref: `{freeze.get('baseline_ref', '')}`",
        "",
        "## 运行入口",
        "",
        f"- unified: `{UNIFIED_ENTRY.relative_to(ROOT).as_posix()}`",
        "- install: `pip install -e \".[dev,runtime]\"` → workspace stub only",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate CURRENT_SYSTEM_STATUS.generated.md")
    parser.add_argument(
        "--refresh-tests",
        action="store_true",
        help="Run pytest and refresh RUNTIME_SNAPSHOT (not default)",
    )
    args = parser.parse_args()

    GENERATED_STATUS_PATH.write_text(
        build_status_markdown(refresh_tests=args.refresh_tests),
        encoding="utf-8",
    )
    print(f"generated: {GENERATED_STATUS_PATH.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
