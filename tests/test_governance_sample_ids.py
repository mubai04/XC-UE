from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"

SAMPLE_ID_PATTERN = re.compile(r"GS-\d{3}")
ALLOWED_PREFIXES = (
    "tests/",
    "tests\\",
    "审计纠偏_2026-06-26/",
    "审计纠偏_2026-06-26\\",
)

SCAN_PATHS = [
    EXEC / "L1工程" / "L1_语义审计.py",
    EXEC / "L1工程" / "L1_语义标尺.py",
    EXEC / "L1工程" / "L1_语义上下文.py",
    EXEC / "公共组件" / "语义证据校验.py",
    ROOT / "scripts" / "eval_l1_semantic_golden.py",
    ROOT / "scripts" / "validate_l1_semantic_golden.py",
]

CALIBRATION_PLAN = ROOT / "tests" / "fixtures" / "l1_semantic_golden" / "CALIBRATION_PLAN.json"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _allowed_file(path: Path) -> bool:
    rel = _rel(path)
    if rel == _rel(CALIBRATION_PLAN):
        return True
    return any(rel.startswith(prefix.replace("\\", "/")) for prefix in ALLOWED_PREFIXES)


@pytest.mark.parametrize("path", SCAN_PATHS, ids=lambda p: p.name)
def test_production_eval_code_has_no_hardcoded_sample_ids(path: Path):
    text = path.read_text(encoding="utf-8")
    hits = SAMPLE_ID_PATTERN.findall(text)
    assert not hits, f"{_rel(path)} 含样本 ID：{sorted(set(hits))}"


def test_calibration_plan_is_only_fixture_control_file_with_sample_ids():
    rel = _rel(CALIBRATION_PLAN)
    text = CALIBRATION_PLAN.read_text(encoding="utf-8")
    assert SAMPLE_ID_PATTERN.search(text), "CALIBRATION_PLAN 应声明 calibration_subset"
    assert _allowed_file(CALIBRATION_PLAN)
