from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNLIB = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "跨层契约运行库"
PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
FIXTURE = ROOT / "tests" / "fixtures" / "跨层契约迁移"

for path in (PUBLIC, RUNLIB):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from 迁移模型 import 迁移上下文  # noqa: E402
from 迁移错误 import 迁移错误  # noqa: E402
from v1到v2迁移 import (  # noqa: E402
    迁移L1失败包,
    迁移L15路由报告,
    迁移L2修复单,
    迁移L3任务包,
    迁移L3执行结果,
    迁移完整链路,
)


def _load(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8-sig"))


def _ctx(**kwargs) -> 迁移上下文:
    base = {
        "pipeline_run_id": "S2B1-PIPE-DEMO",
        "chapter_path": "chapters/demo_chapter.md",
        "project_id": "demo",
    }
    base.update(kwargs)
    return 迁移上下文(**base)


def test_l1_migration_success():
    r = 迁移L1失败包(_load("v1输入/chain/L1_failure_packet.json"), _ctx())
    assert r.迁移状态.startswith("SUCCESS")
    assert r.目标对象["发现项列表"][0]["L1问题域"] == "文风"


def test_l1_missing_routeable_fails():
    r = 迁移L1失败包(_load("无效输入/缺routeable.json"), _ctx(pipeline_run_id="S2B1-BAD-NOROUTE"))
    assert r.迁移状态 == "FAILED"


def test_l1_unknown_domain_fails():
    r = 迁移L1失败包(_load("无效输入/未知L1问题域.json"), _ctx(pipeline_run_id="S2B1-BAD-DOMAIN"))
    assert r.迁移状态 == "FAILED"
    assert any("L1_DOMAIN_MAPPING_MISSING" in e for e in r.迁移错误)


def test_l15_migration_success():
    ctx = _ctx()
    迁移L1失败包(_load("v1输入/chain/L1_failure_packet.json"), ctx)
    r = 迁移L15路由报告(_load("v1输入/chain/L15_route_report.json"), ctx)
    assert r.迁移状态.startswith("SUCCESS")
    assert r.目标对象["主发现引用"]["对象类型"] == "L1发现项"


def test_l15_primary_missing_fails():
    ctx = _ctx()
    with pytest.raises(迁移错误):
        迁移L15路由报告(_load("v1输入/chain/L15_route_report.json"), ctx)


def test_l2_migration_success():
    ctx = _ctx()
    迁移L1失败包(_load("v1输入/chain/L1_failure_packet.json"), ctx)
    迁移L15路由报告(_load("v1输入/chain/L15_route_report.json"), ctx)
    form = _load("v1输入/chain/L2_report.json")["修复单"][0]
    r = 迁移L2修复单(form, ctx)
    assert r.迁移状态.startswith("SUCCESS")
    assert r.目标对象["模块内主问题"] == "句式模板重复"


def test_l2_ambiguous_repair_fails():
    ctx = _ctx()
    ctx.L1_5路由决策编号 = "L15R-x"
    r = 迁移L2修复单(_load("无效输入/L2修复语义模糊.json"), ctx)
    assert r.迁移状态 == "FAILED"


def test_l3_task_migration_success():
    ctx = _ctx()
    迁移L1失败包(_load("v1输入/chain/L1_failure_packet.json"), ctx)
    迁移L15路由报告(_load("v1输入/chain/L15_route_report.json"), ctx)
    from v1到v2迁移 import 迁移L2报告

    迁移L2报告(_load("v1输入/chain/L2_report.json"), ctx)
    r = 迁移L3任务包(_load("v1输入/chain/L3_task_bundle.json"), ctx)
    assert r.迁移状态.startswith("SUCCESS")
    assert r.目标对象["执行模式"] == "TASK_PLANNING_ONLY"
    assert r.目标对象["执行状态"] == "PLANNED"


def test_l3_status_mode_mix_fails():
    ctx = _ctx()
    ctx.L2报告编号 = "L2R-x"
    ctx.L2修复单编号列表 = ["L2F-x"]
    bad = _load("v1输入/chain/L3_task_bundle.json")
    bad["status"] = "TASK_PLANNING_ONLY"
    r = 迁移L3任务包(bad, ctx)
    assert r.迁移状态 == "FAILED"


def test_full_chain():
    ctx = _ctx()
    results = 迁移完整链路(
        l1_packet=_load("v1输入/chain/L1_failure_packet.json"),
        l15_report=_load("v1输入/chain/L15_route_report.json"),
        l2_report=_load("v1输入/chain/L2_report.json"),
        l3_task=_load("v1输入/chain/L3_task_bundle.json"),
        l3_result=_load("v1输入/chain/L3_execution_result.json"),
        ctx=ctx,
    )
    assert len(results) == 5
    assert all(r.迁移状态.startswith("SUCCESS") for r in results)


def test_missing_context_fails():
    with pytest.raises(迁移错误):
        迁移L1失败包(
            _load("v1输入/chain/L1_failure_packet.json"),
            迁移上下文(pipeline_run_id="", chapter_path=""),
        )
