from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from tests.conftest import ROOT, failure_packet_item, failure_packet_payload, sample_chapter_text

L15_DIR = ROOT / "00_工程总控" / "工程执行层" / "L1.5工程"
L1_DIR = ROOT / "00_工程总控" / "工程执行层" / "L1工程"
L2_DIR = ROOT / "00_工程总控" / "工程执行层" / "L2工程"
PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
for path in (PUBLIC, L1_DIR, L2_DIR, L15_DIR):
    text = str(path)
    if text not in __import__("sys").path:
        __import__("sys").path.insert(0, text)

from L15路由 import 执行路由  # noqa: E402


def _packet(chapter: Path, gate: str, failure_type: str, *, blocking: bool = True, routeable: bool = True) -> dict:
    item = failure_packet_item(
        gate,
        failure_type,
        routeable=routeable,
        blocking=blocking,
        decision_role="CONTENT_DECISION" if blocking else "DIAGNOSTIC",
        source_component=gate,
    )
    return failure_packet_payload(chapter, [item], pipeline_run_id="S1A-TEST", stage_run_id="S1A-TEST-L1")


def _route(tmp_path: Path, gate: str, failure_type: str) -> dict:
    seed = uuid.uuid4().hex[:8]
    chapter = tmp_path / f"{seed}.md"
    chapter.write_text(sample_chapter_text(seed), encoding="utf-8")
    packet_path = tmp_path / f"{seed}.json"
    packet_path.write_text(json.dumps(_packet(chapter, gate, failure_type), ensure_ascii=False), encoding="utf-8")
    report = 执行路由(
        packet_path,
        repo_root=ROOT,
        run_id=f"S1A-{seed}",
        pipeline_run_id="S1A-PIPE",
        stage_run_id="S1A-STAGE",
    )
    return report.to_dict()


def test_narrative_to_l2_01(tmp_path):
    report = _route(tmp_path, "L1-01", "叙事失败")
    assert report["final_status"] == "ROUTED"
    assert report["target_module"] == "L2-01"
    assert report["route_rule_id"] == "L15-R001"


def test_ai_taste_to_l2_02(tmp_path):
    report = _route(tmp_path, "L1-01", "AI味失败")
    assert report["target_module"] == "L2-02"


def test_character_to_l2_03(tmp_path):
    report = _route(tmp_path, "L1-01", "角色失败")
    assert report["target_module"] == "L2-03"


def test_creative_to_l2_04(tmp_path):
    report = _route(tmp_path, "L1-01", "创意设定失败")
    assert report["target_module"] == "L2-04"


def test_reader_cognitive_cost_l1_02_to_l2_05(tmp_path):
    report = _route(tmp_path, "L1-02", "C高：认知成本过高")
    assert report["target_module"] == "L2-05"


def test_story_fact_conflict_to_l2_06(tmp_path):
    report = _route(tmp_path, "L1-01", "前后事实冲突")
    assert report["target_module"] == "L2-06"


def test_technical_guard_not_l2_06(tmp_path):
    report = _route(tmp_path, "L1-01", "技术护栏失败")
    assert report["final_status"] == "BLOCKED"
    assert report["target_module"] == ""
    assert report["extensions"].get("route_action") == "BLOCKED_TECHNICAL"


def test_input_required(tmp_path):
    report = _route(tmp_path, "L1-01", "输入不足")
    assert report["final_status"] == "INPUT_REQUIRED"


def test_l1_01_not_passed_return_to_l1(tmp_path):
    report = _route(tmp_path, "L1-02", "L1-01未通过")
    assert report["final_status"] == "RETURN_TO_L1"


def test_unknown_failure_return_to_l1(tmp_path):
    report = _route(tmp_path, "L1-01", "未知失败类型XYZ")
    assert report["final_status"] == "RETURN_TO_L1"


def test_missing_rules_file_blocks(tmp_path):
    missing_root = tmp_path / "empty_repo"
    missing_root.mkdir()
    (missing_root / "30_L1.5_路由矩阵层").mkdir(parents=True)
    chapter = tmp_path / "ch.md"
    chapter.write_text("测试", encoding="utf-8")
    packet_path = tmp_path / "p.json"
    packet_path.write_text(json.dumps(_packet(chapter, "L1-01", "叙事失败")), encoding="utf-8")
    report = 执行路由(
        packet_path,
        repo_root=missing_root,
        run_id="S1A-MISS",
        pipeline_run_id="S1A-PIPE",
        stage_run_id="S1A-STAGE",
    )
    assert report.final_status == "BLOCKED"
    assert report.route_rule_id == "L15_ROUTING_RULES_MISSING"


def test_invalid_rules_file_blocks(tmp_path):
    bad_root = tmp_path / "bad_repo"
    layer = bad_root / "30_L1.5_路由矩阵层"
    layer.mkdir(parents=True)
    (layer / "L1.5_路由规则.json").write_text("{", encoding="utf-8")
    chapter = tmp_path / "ch2.md"
    chapter.write_text("测试", encoding="utf-8")
    packet_path = tmp_path / "p2.json"
    packet_path.write_text(json.dumps(_packet(chapter, "L1-01", "叙事失败")), encoding="utf-8")
    report = 执行路由(
        packet_path,
        repo_root=bad_root,
        run_id="S1A-BAD",
        pipeline_run_id="S1A-PIPE",
        stage_run_id="S1A-STAGE",
    )
    assert report.final_status == "BLOCKED"
    assert report.route_rule_id == "L15_ROUTING_RULES_INVALID"


def test_l15_source_uses_canonical_json_only():
    src = (ROOT / "00_工程总控" / "工程执行层" / "L1.5工程" / "L15路由.py").read_text(encoding="utf-8")
    assert "l15_routes" not in src
    assert "加载闸门规则" not in src
    assert "routes.json" not in src
    assert "L1.5_路由规则.json" in src or "加载L15路由规则" in src


def test_gate_rules_has_no_l15_routes():
    raw = json.loads(
        (ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "gate_rules.json").read_text(encoding="utf-8-sig")
    )
    assert "l15_routes" not in raw


def test_l2_routes_deprecated():
    raw = json.loads((ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "routes.json").read_text(encoding="utf-8-sig"))
    assert raw.get("routing_authority") == "DEPRECATED_NOT_ROUTING_AUTHORITY"


def test_source_gate_distinguishes_cognitive_cost(tmp_path):
    r02 = _route(tmp_path, "L1-02", "C高：认知成本过高")
    r03 = _route(tmp_path, "L1-03", "认知成本过高")
    assert r02["target_module"] == "L2-05"
    assert r03["target_module"] == "L2-02"


def test_chapter_end_routes_to_l2_05(tmp_path):
    r_weak = _route(tmp_path, "L1-02", "章末弱")
    r_hook = _route(tmp_path, "L1-03", "章末追读弱")
    assert r_weak["target_module"] == "L2-05"
    assert r_hook["target_module"] == "L2-05"


def test_matrix_points_to_json_not_duplicate_table():
    text = (ROOT / "30_L1.5_路由矩阵层" / "L1.5_Routing_Matrix.md").read_text(encoding="utf-8")
    assert "L1.5_路由规则.json" in text
    assert "| 文风失败" not in text
