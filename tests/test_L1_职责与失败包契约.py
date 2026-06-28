from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from L1决策角色 import 聚合终态, 标记诊断项, 完成诊断闸门, 硬护栏角色
from L1模型 import 检测项, 闸门结果, 正文检测结果
from L1_语义审计 import 语义审计结果
from L15路由 import 执行路由
from L15路由规则加载 import 加载L15路由规则
from L2读取 import 读失败包完整
from 失败包生成 import 构建失败包, 分拆阻断项
from 运行状态 import 审计阻断, 机器初筛通过, 机器初筛退回, SCREENING_REVIEW
from tests.conftest import ROOT, failure_packet_item, failure_packet_payload, sample_chapter_text


def _item(
    gate: str,
    failure_type: str,
    *,
    role: str,
    blocking: bool,
    routeable: bool,
    severity: str = "error",
) -> 检测项:
    item = 检测项(
        闸门=gate,
        名称="测试项",
        状态="失败",
        说明="测试说明",
        证据=[],
        严重级别=severity,
        失败类型=failure_type,
        候选模块="",
        回流验收位置=gate,
        修复方向="测试修复",
        decision_role=role,
        blocking=blocking,
        routeable=routeable,
        source_component=gate,
    )
    if role == "DIAGNOSTIC":
        return 标记诊断项(item)
    return item


def test_hard_guard_blocking_routeable_enters_packet():
    item = _item("L1-00", "高重复正文", role=硬护栏角色, blocking=True, routeable=True)
    packet = 构建失败包([item], 机器初筛退回)
    assert len(packet) == 1
    assert packet[0].routeable is True
    assert packet[0].blocking is True


def test_hard_guard_blocking_not_content_routeable():
    item = _item("L1-01", "技术护栏失败", role=硬护栏角色, blocking=True, routeable=False)
    packet = 构建失败包([item], 机器初筛退回)
    assert any(i.失败类型 == "技术护栏失败" for i in packet)
    rule_set = 加载L15路由规则(ROOT)
    entry = rule_set.routes.get(("L1-01", "技术护栏失败"))
    assert entry and entry.route_action == "BLOCKED_TECHNICAL"


def test_content_decision_in_failure_packet():
    item = _item("L1-SEM", "语义失败", role="CONTENT_DECISION", blocking=True, routeable=True)
    packet = 构建失败包([item], 机器初筛退回)
    assert packet and packet[0].decision_role == "CONTENT_DECISION"


def test_diagnostic_does_not_change_terminal_state():
    gate = 闸门结果(
        闸门="L1-01",
        判断结果="HEURISTIC_DIAGNOSTIC",
        输入材料=[],
        失败类型=["叙事失败"],
        失败位置=[],
        是否进入L15="否",
        调用方向=[],
        回流验收位置="L1-01",
        最终状态="HEURISTIC_DIAGNOSTIC",
        检测项=[_item("L1-01", "叙事失败", role="DIAGNOSTIC", blocking=False, routeable=True)],
    )
    gate = 完成诊断闸门(gate)
    semantic = 语义审计结果(检测项列表=[], 可用=True, 整体结论="PASS")
    final = 聚合终态(semantic, gate.检测项, [])
    assert final.status == 机器初筛通过


def test_diagnostic_routeable_on_reject():
    diag = _item("L1-01", "叙事失败", role="DIAGNOSTIC", blocking=False, routeable=True)
    semantic = 语义审计结果(检测项列表=[], 可用=True, 整体结论="FAIL")
    content = _item("L1-SEM", "语义失败", role="CONTENT_DECISION", blocking=True, routeable=True)
    final = 聚合终态(semantic, [diag, content], [])
    assert final.status == 机器初筛退回
    packet = 构建失败包([diag, content], final.status)
    assert any(i.decision_role == "DIAGNOSTIC" and i.routeable for i in packet)


def test_diagnostic_on_pass_no_repair_packet():
    diag = _item("L1-02", "章末弱", role="DIAGNOSTIC", blocking=False, routeable=True)
    packet = 构建失败包([diag], 机器初筛通过)
    assert packet == []


def test_audit_blocker_blocks_content_routing(tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text(sample_chapter_text("audit"), encoding="utf-8")
    packet_path = tmp_path / "audit.json"
    packet_path.write_text(
        json.dumps(
            failure_packet_payload(chapter, [], status=审计阻断),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = 执行路由(
        packet_path,
        repo_root=ROOT,
        run_id="AUDIT-TEST",
        pipeline_run_id="PIPE",
        stage_run_id="STAGE",
    )
    assert report.final_status == "BLOCKED"
    assert report.route_rule_id == "AUDIT_BLOCKED"


def test_blocking_false_routeable_true_readable_by_l15(tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text(sample_chapter_text("route"), encoding="utf-8")
    item = failure_packet_item(
        "L1-01",
        "文风失败",
        routeable=True,
        blocking=False,
        decision_role="DIAGNOSTIC",
    )
    packet = failure_packet_payload(chapter, [item], status=机器初筛退回)
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    items, meta = 读失败包完整(packet_path)
    assert items[0].routeable is True
    report = 执行路由(
        packet_path,
        repo_root=ROOT,
        run_id="ROUTE-TEST",
        pipeline_run_id="PIPE",
        stage_run_id="STAGE",
    )
    assert report.target_module == "L2-02"


def test_routeable_false_not_selected_by_l15(tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text(sample_chapter_text("noroute"), encoding="utf-8")
    visible = failure_packet_item("L1-01", "文风失败", routeable=True, blocking=True)
    hidden = failure_packet_item("L1-01", "叙事失败", routeable=False, blocking=False)
    packet = failure_packet_payload(chapter, [visible, hidden], status=机器初筛退回)
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    report = 执行路由(
        packet_path,
        repo_root=ROOT,
        run_id="SEL-TEST",
        pipeline_run_id="PIPE",
        stage_run_id="STAGE",
    )
    assert report.primary_failure.失败类型 == "文风失败"


def test_screening_review_forms_review_packet():
    warn = _item("L1-SEM", "语义警告", role="CONTENT_DECISION", blocking=False, routeable=True, severity="warning")
    packet = 构建失败包([warn], SCREENING_REVIEW)
    assert packet
    semantic = 语义审计结果(检测项列表=[], 可用=True, 整体结论="REVIEW")
    final = 聚合终态(semantic, [warn], [])
    assert final.status == SCREENING_REVIEW


def test_screening_pass_no_failure_packet():
    assert 构建失败包([], 机器初筛通过) == []


def test_screening_reject_forms_repair_packet():
    item = _item("L1-SEM", "语义失败", role="CONTENT_DECISION", blocking=True, routeable=True)
    packet = 构建失败包([item], 机器初筛退回)
    assert len(packet) >= 1


def test_word_count_insufficient_input_required(tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text(sample_chapter_text("words"), encoding="utf-8")
    item = failure_packet_item(
        "L1-00",
        "字数不足",
        routeable=False,
        blocking=True,
        decision_role=硬护栏角色,
        source_component="L1-00",
    )
    packet = failure_packet_payload(chapter, [item], status=机器初筛退回)
    packet_path = tmp_path / "words.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    report = 执行路由(
        packet_path,
        repo_root=ROOT,
        run_id="WORD-TEST",
        pipeline_run_id="PIPE",
        stage_run_id="STAGE",
    )
    assert report.final_status == "INPUT_REQUIRED"
    assert not report.target_module


def test_duplicate_types_route_to_l2_02(tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text(sample_chapter_text("dup"), encoding="utf-8")
    rule_set = 加载L15路由规则(ROOT)
    for failure_type in ("重复窗口过高", "高重复正文", "低信息重复正文"):
        entry = rule_set.routes.get(("L1-00", failure_type))
        assert entry and entry.target_module == "L2-02"
        item = failure_packet_item(
            "L1-00",
            failure_type,
            routeable=True,
            blocking=True,
            decision_role=硬护栏角色,
            source_component="L1-00",
        )
        packet = failure_packet_payload(chapter, [item], status=机器初筛退回)
        packet_path = tmp_path / f"{failure_type}.json"
        packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
        report = 执行路由(
            packet_path,
            repo_root=ROOT,
            run_id=f"DUP-{failure_type}",
            pipeline_run_id="PIPE",
            stage_run_id="STAGE",
        )
        assert report.target_module == "L2-02"


def test_publish_authority_false():
    result = 正文检测结果(
        run_id="TEST",
        项目="pytest",
        章节路径="ch.md",
        章节标题="t",
        当前字数=100,
        段落数=1,
        方法声明="test",
        闸门结果=[],
        失败包=[],
        路由建议=[],
    )
    assert result.publish_authority is False


def test_reserved_propagation_payment_not_generated():
    import L1_02_读者投入检测 as l102

    source = Path(l102.__file__).read_text(encoding="utf-8")
    assert "传播点弱" not in source
    assert "付费预期弱" not in source


def test_old_packet_without_routeable_rejected(tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text("test", encoding="utf-8")
    legacy = {
        "schema_version": "xcue.failure-packet/1.0",
        "pipeline_run_id": "LEG",
        "stage_run_id": "LEG",
        "status": 机器初筛退回,
        "failure_count": 1,
        "blocking_count": 1,
        "routeable_count": 0,
        "items": [
            {
                "闸门": "L1-01",
                "名称": "旧包",
                "状态": "失败",
                "说明": "旧语义",
                "证据": [{"段落": 1, "摘句": "摘句"}],
                "严重级别": "error",
                "失败类型": "叙事失败",
                "候选模块": "L2-01",
                "回流验收位置": "L1-01",
                "修复方向": "修复",
                "decision_role": "CONTENT_DECISION",
                "blocking": True,
            }
        ],
        "extensions": {"chapter_path": str(chapter)},
    }
    packet_path = tmp_path / "legacy.json"
    packet_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="routeable"):
        读失败包完整(packet_path)


def test_l15_conflict_manual_review(tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text(sample_chapter_text("conflict"), encoding="utf-8")
    items = [
        failure_packet_item("L1-01", "文风失败", routeable=True, blocking=True, decision_role="CONTENT_DECISION"),
        failure_packet_item(
            "L1-01",
            "角色失败",
            routeable=True,
            blocking=True,
            decision_role="CONTENT_DECISION",
            source_component="L1-01",
        ),
    ]
    items[1]["候选模块"] = "L2-03"
    items[1]["失败类型"] = "角色失败"
    packet = failure_packet_payload(chapter, items, status=机器初筛退回)
    packet_path = tmp_path / "conflict.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    report = 执行路由(
        packet_path,
        repo_root=ROOT,
        run_id="CONFLICT",
        pipeline_run_id="PIPE",
        stage_run_id="STAGE",
    )
    assert report.final_status == "MANUAL_REVIEW"
