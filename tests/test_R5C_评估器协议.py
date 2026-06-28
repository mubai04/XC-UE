from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_r5c_preflight_module_has_l2p007_ir_index():
    import importlib.util
    import sys

    path = ROOT / "脚本" / "评估_L2_真实API试跑.py"
    spec = importlib.util.spec_from_file_location("eval_l2", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    manifest = mod._load_manifest()
    entry = next(e for e in manifest["cases"] if e["case_id"] == "L2P-007")
    info = mod.preflight_case(entry)
    assert info.get("l2p007_ir_memory_cost_indexed")
    assert info.get("evidence_id_total", 0) > 0
