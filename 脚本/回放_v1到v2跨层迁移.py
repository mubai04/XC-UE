#!/usr/bin/env python3
"""离线回放 v1→v2 跨层迁移（S2B-1）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNLIB = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "跨层契约运行库"
PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
for path in (PUBLIC, RUNLIB):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from Schema注册表 import 预检Schema  # noqa: E402
from 引用完整性校验 import 校验引用链  # noqa: E402
from 迁移模型 import 迁移上下文  # noqa: E402
from v1到v2迁移 import 迁移L3执行结果, 迁移完整链路  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _preflight() -> bool:
    errors = 预检Schema()
    if errors:
        print("S2B1_SCHEMA_PREFLIGHT = FAILED")
        for item in errors:
            print(f"ERROR: {item}")
        return False
    print("VALIDATION_OK")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="v1→v2 跨层迁移离线回放")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--input-dir", default="")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    if not _preflight():
        print("S2B1_MIGRATION = NOT_STARTED")
        return 1

    if args.validate_only:
        print("MIGRATION_CHAIN_READY")
        return 0

    input_dir = Path(args.input_dir) if args.input_dir else ROOT / "tests/fixtures/跨层契约迁移/v1输入/chain"
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / "运行记录/S2B1_离线迁移回放"

    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"ERROR: 输出目录非空：{output_dir}")
        return 1

    chain = input_dir
    l1 = _load(chain / "L1_failure_packet.json")
    l15 = _load(chain / "L15_route_report.json")
    l2 = _load(chain / "L2_report.json")
    l3 = _load(chain / "L3_task_bundle.json")
    l3r_path = chain / "L3_execution_result.json"
    l3r = _load(l3r_path) if l3r_path.exists() else None

    ext = l1.get("extensions") or {}
    ctx = 迁移上下文(
        pipeline_run_id=l1.get("pipeline_run_id", "PIPE"),
        chapter_path=ext.get("chapter_path", ""),
        project_id="demo-project",
    )

    results = 迁移完整链路(
        l1_packet=l1,
        l15_report=l15,
        l2_report=l2,
        l3_task=l3,
        l3_result=None,
        ctx=ctx,
    )
    if l3r and results and results[-1].迁移状态.startswith("SUCCESS"):
        results.append(迁移L3执行结果(l3r, ctx))

    print("=== 迁移摘要 ===")
    failed = False
    v2_objects: dict[str, dict] = {}
    for r in results:
        print(f"{r.来源对象类型}: {r.迁移状态}")
        if r.迁移错误:
            for e in r.迁移错误:
                print(f"  ERROR: {e}")
            failed = True
        if r.未迁移字段:
            print(f"  未迁移字段: {r.未迁移字段}")
        if r.已消费但不保留的旧字段:
            print(f"  已消费但不保留的旧字段: {r.已消费但不保留的旧字段}")
        if r.迁移警告:
            print(f"  警告: {r.迁移警告}")
        if r.迁移状态.startswith("SUCCESS"):
            v2_objects[r.来源对象类型] = r.目标对象

    if failed:
        print("MIGRATION_CHAIN = FAILED")
        return 1

    ref_errors = 校验引用链(
        l1_packet=v2_objects.get("L1_FAILURE_PACKET_V1"),
        l15=v2_objects.get("L15_ROUTE_REPORT_V1"),
        l2_report=v2_objects.get("L2_REPORT_V1"),
        l3_task=v2_objects.get("L3_TASK_BUNDLE_V1"),
        l3_result=v2_objects.get("L3_EXECUTION_RESULT_V1"),
        ctx=ctx,
    )
    if ref_errors:
        print("引用闭合 = FAILED")
        for e in ref_errors:
            print(f"  {e}")
        return 1
    print("引用闭合 = OK")

    if not args.validate_only:
        output_dir.mkdir(parents=True, exist_ok=False)
        names = {
            "L1_FAILURE_PACKET_V1": "L1_failure_packet_v2.json",
            "L15_ROUTE_REPORT_V1": "L15_route_decision_v2.json",
            "L2_REPORT_V1": "L2_report_v2.json",
            "L3_TASK_BUNDLE_V1": "L3_task_bundle_v2.json",
            "L3_EXECUTION_RESULT_V1": "L3_execution_result_v2.json",
        }
        for key, obj in v2_objects.items():
            out = output_dir / names.get(key, f"{key}.json")
            out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print("MIGRATION_CHAIN = SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
