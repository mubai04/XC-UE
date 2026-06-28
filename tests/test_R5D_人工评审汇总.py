from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_empty_scoreboard_validate_only(tmp_path):
    gen = _load_module("gen_r5d", ROOT / "脚本" / "生成_R5D_评审材料.py")
    review_dir = tmp_path / "R5D_人工业务评审_test"
    review_dir.mkdir()
    gen.generate(review_dir)

    agg = _load_module("agg_r5d", ROOT / "脚本" / "汇总_L2_人工业务评分.py")
    result = agg.summarize(review_dir, write_report=False)
    assert result["case_count"] == 12
    assert result["unreviewed_remaining"] is True
    assert result["L2_R5D_BUSINESS_PILOT"] == "INCOMPLETE"
    assert result["L2_REAL_MODEL_EFFECTIVENESS"] == "NOT_TESTED"
    assert not result["validation_errors"]


def test_score_paths_count(tmp_path):
    gen = _load_module("gen_r5d", ROOT / "脚本" / "生成_R5D_评审材料.py")
    review_dir = tmp_path / "bundle"
    gen.generate(review_dir)
    agg = _load_module("agg_r5d", ROOT / "脚本" / "汇总_L2_人工业务评分.py")
    rows, errors = agg.load_case_scores(review_dir)
    assert len(rows) == 12
    assert not errors
