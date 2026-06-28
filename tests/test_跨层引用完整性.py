from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNLIB = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "跨层契约运行库"
PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
FIXTURE = ROOT / "tests" / "fixtures" / "跨层契约迁移"

for path in (PUBLIC, RUNLIB):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from 引用完整性校验 import 校验引用链  # noqa: E402
from 迁移模型 import 迁移上下文  # noqa: E402
from v1到v2迁移 import 迁移完整链路  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8-sig"))


def test_chain_reference_closure():
    ctx = 迁移上下文(
        pipeline_run_id="S2B1-PIPE-DEMO",
        chapter_path="chapters/demo_chapter.md",
    )
    results = 迁移完整链路(
        l1_packet=_load("v1输入/chain/L1_failure_packet.json"),
        l15_report=_load("v1输入/chain/L15_route_report.json"),
        l2_report=_load("v1输入/chain/L2_report.json"),
        l3_task=_load("v1输入/chain/L3_task_bundle.json"),
        l3_result=_load("v1输入/chain/L3_execution_result.json"),
        ctx=ctx,
    )
    objs = {r.来源对象类型: r.目标对象 for r in results if r.迁移状态.startswith("SUCCESS")}
    errors = 校验引用链(
        l1_packet=objs["L1_FAILURE_PACKET_V1"],
        l15=objs["L15_ROUTE_REPORT_V1"],
        l2_report=objs["L2_REPORT_V1"],
        l3_task=objs["L3_TASK_BUNDLE_V1"],
        l3_result=objs["L3_EXECUTION_RESULT_V1"],
        ctx=ctx,
    )
    assert errors == []
