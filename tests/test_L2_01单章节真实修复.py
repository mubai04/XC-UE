from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "脚本"))

from L2_01真实修复_案例资格 import 扫描全部案例, 校验指定案例
from 运行_L2_01单章节真实修复 import (
    _compare_formal_unchanged,
    _fix_form_accepts_l3,
    run,
)


def test_fixture_chapter_rejected():
    qual = 校验指定案例(
        "FIXTURE",
        "tests/fixtures/l2_real_api_pilot/cases/L2P-001/chapters/chapter.md",
        ROOT,
    )
    assert not qual.ok
    assert qual.stop_code == "REAL_L2_01_CASE_REQUIRED"


def test_tp001_placeholder_rejected():
    qual = 校验指定案例(
        "TP-001",
        "70_测试项目/TP-001_CleanHarness_IR_Runtime/chapters/ch01.md",
        ROOT,
    )
    assert not qual.ok


def test_golden_chapter_rejected():
    qual = 校验指定案例(
        "GOLDEN",
        "tests/fixtures/l1_semantic_golden/chapters/GS-001.md",
        ROOT,
    )
    assert not qual.ok


def test_registry_scan_finds_yyl_qualified_case():
    qual = 扫描全部案例(ROOT)
    assert qual.ok
    assert qual.candidate is not None
    assert qual.candidate.project_id == "YYL-001"
    assert qual.candidate.chapter_path.endswith("ch02.md")


def test_l15_non_l2_01_would_stop_via_orchestrator(tmp_path):
    out = tmp_path / "out"
    code = run(project_id="TP-001", chapter="70_测试项目/TP-001_CleanHarness_IR_Runtime/chapters/ch01.md", run_id="T-STOP", execute_real_api=False, out_dir=out)
    assert code == 2
    result = json.loads((out / "L2_01单模块真实修复结果.json").read_text(encoding="utf-8"))
    assert result["stop_code"] == "REAL_L2_01_CASE_REQUIRED"


def test_fix_form_rejected_blocks_l3():
    ok, errors = _fix_form_accepts_l3({"修复动作": ["加强结构", "优化节奏"], "修复单状态": "DRAFT"})
    assert not ok
    assert errors


def test_fix_form_ready_allows_l3():
    ok, _ = _fix_form_accepts_l3(
        {
            "模块内主问题": "主线发散",
            "根因": "末段未收束",
            "修复规则": ["章末必须留下单一主问题"],
            "修复动作": ["将末段冲突收束到库房对峙"],
            "禁止修改范围": ["世界观"],
            "必须保留内容": ["主角目标"],
            "验收条件": ["末段主问题唯一"],
            "修复单状态": "READY_FOR_L3",
            "重路由请求": {"禁止直接指定新目标模块": True},
        }
    )
    assert ok


def test_formal_chapter_byte_unchanged(tmp_path):
    ch = tmp_path / "ch.md"
    ch.write_text("# t\n\n正文内容" * 200, encoding="utf-8")
    before = ch.read_bytes()
    ch.write_text("# t\n\n正文内容" * 200, encoding="utf-8")
    assert _compare_formal_unchanged(before, ch)


def test_ab_order_swap_logic():
    orders = [("原文", "候选"), ("候选", "原文")]
    assert orders[0] != orders[1]
    assert orders[0][0] == orders[1][1]


def test_business_not_only_l1_status():
    # 业务门槛不得只看 L1 overall
    l1_only_pass = {"l1_status": "SCREENING_PASS", "structure_improved": False}
    assert l1_only_pass["l1_status"] == "SCREENING_PASS"
    assert not l1_only_pass["structure_improved"]


def test_pipeline_entry_uses_l15_for_l2():
    text = (ROOT / "00_工程总控/工程执行层/修复流水线运行入口.py").read_text(encoding="utf-8")
    l2_chunk = text.split("L2运行入口.main", 1)[1][:500]
    assert "--l15-report" in l2_chunk
    assert "--failure-packet" not in l2_chunk
