from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_s2a_validator_still_ok():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "脚本" / "校验_L0至L3跨层接口契约.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert "VALIDATION_OK" in proc.stdout


def test_replay_validate_only():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "脚本" / "回放_v1到v2跨层迁移.py"), "--validate-only"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0
    assert "VALIDATION_OK" in proc.stdout
    assert "MIGRATION_CHAIN_READY" in proc.stdout


def test_replay_offline_chain(tmp_path):
    out = tmp_path / "replay_out"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "脚本" / "回放_v1到v2跨层迁移.py"),
            "--input-dir",
            str(ROOT / "tests/fixtures/跨层契约迁移/v1输入/chain"),
            "--output-dir",
            str(out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out_text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out_text
    assert (out / "L1_failure_packet_v2.json").exists()
    assert "MIGRATION_CHAIN = SUCCESS" in proc.stdout


def test_production_entries_not_using_migration_lib():
    entries = [
        ROOT / "00_工程总控/工程执行层/L1工程/L1运行入口.py",
        ROOT / "00_工程总控/工程执行层/L1.5工程/L1.5运行入口.py",
        ROOT / "00_工程总控/工程执行层/L2工程/L2运行入口.py",
        ROOT / "00_工程总控/工程执行层/L3工程/L3运行入口.py",
    ]
    for path in entries:
        text = path.read_text(encoding="utf-8")
        assert "跨层契约运行库" not in text
        assert "v1到v2迁移" not in text


def test_production_still_v1_schema():
    l1_report = ROOT / "00_工程总控/工程执行层/L1工程/L1报告.py"
    text = l1_report.read_text(encoding="utf-8")
    assert "失败包结构.json" in text or "FAILURE_PACKET_SCHEMA" in text
    assert "跨层契约" not in text
