#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
L15_DIR = Path(__file__).resolve().parent
公共组件 = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
for path in (公共组件, L15_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from L15报告 import 写报告, 拒绝覆盖既有报告
from L15路由 import 执行路由
from 退出码 import ExitCode
from 标准加载器 import 候选试验模式, 生产模式
from 生产资格 import 判定结果转标准字段, 要求生产资格
from 工程异常 import 工程错误
from 安全路径 import resolve_inside_root, safe_id
from 输入校验 import 校验JSON输入, 血缘期望
from 错误信封 import 打印错误信封

SCHEMA_DIR = 公共组件 / "结构定义"
测试IO令牌内容 = "XCUE_TEST_EXTERNAL_IO_TOKEN_V1"


def _允许测试外部IO() -> bool:
    if os.environ.get("XCUE_TEST_ALLOW_EXTERNAL_IO") != "1":
        return False
    token_path = os.environ.get("XCUE_TEST_IO_TOKEN_FILE", "")
    if not token_path:
        return False
    resolved = Path(token_path).resolve()
    try:
        resolved.relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError:
        return False
    try:
        return resolved.read_text(encoding="utf-8") == 测试IO令牌内容
    except OSError:
        return False


def _解析路径(value: str | Path, label: str) -> Path:
    if _允许测试外部IO():
        resolved = Path(value).resolve()
        try:
            resolved.relative_to(Path(tempfile.gettempdir()).resolve())
        except ValueError:
            return resolve_inside_root(ROOT, value)
        return resolved
    return resolve_inside_root(ROOT, value)


def main() -> int:
    parser = argparse.ArgumentParser(description="XC-UE L1.5：读取 L1 failure packet，输出唯一主路由报告。")
    parser.add_argument("--failure-packet", required=True, help="L1 failure packet JSON 路径。")
    parser.add_argument("--run-id", default=None, help="报告编号。")
    parser.add_argument("--out-dir", default=None, help="输出目录。")
    parser.add_argument("--pipeline-run-id", default="", help="流水线编号。")
    parser.add_argument("--stage-run-id", default="", help="阶段运行编号。")
    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式], help="标准加载模式。")
    args = parser.parse_args()

    try:
        run_id = safe_id(args.run_id or "L15_RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S"), "run_id")
        pipeline_run_id = safe_id(args.pipeline_run_id, "pipeline_run_id") if args.pipeline_run_id else run_id
        stage_run_id = safe_id(args.stage_run_id, "stage_run_id") if args.stage_run_id else f"{pipeline_run_id}-L15"
        packet_path = _解析路径(args.failure_packet, "failure_packet")
        out_dir = _解析路径(args.out_dir, "out_dir") if args.out_dir else L15_DIR / "reports"
        拒绝覆盖既有报告(run_id, out_dir)
    except 工程错误 as exc:
        打印错误信封(exc, stage="L1.5", run_id=locals().get("run_id", ""), path=locals().get("out_dir", ""))
        return int(exc.exit_code)

    try:
        校验JSON输入(
            packet_path,
            schema_path=SCHEMA_DIR / "失败包结构.json",
            label="L1.5 失败包",
            expected_schema_version="xcue.failure-packet/1.0",
            lineage=血缘期望(pipeline_run_id=pipeline_run_id) if pipeline_run_id else None,
        )
    except 工程错误 as exc:
        打印错误信封(exc, stage="L1.5", run_id=run_id, path=packet_path)
        return int(exc.exit_code)

    try:
        mode_decision = 要求生产资格(
            requested_mode=args.standard_mode,
            rule_source=ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "gate_rules.json",
            entrypoint="L1.5",
            project_identity=pipeline_run_id,
        )
    except 工程错误 as exc:
        打印错误信封(exc, stage="L1.5", run_id=run_id)
        return int(exc.exit_code)

    report = 执行路由(
        packet_path,
        repo_root=ROOT,
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id,
    )
    md_path, json_path = 写报告(report, out_dir)
    exit_map = {
        "ROUTED": ExitCode.OK,
        "INPUT_REQUIRED": ExitCode.INPUT_INVALID,
        "MANUAL_REVIEW": ExitCode.BLOCKED,
        "RETURN_TO_L1": ExitCode.BLOCKED,
        "BLOCKED": ExitCode.BLOCKED,
    }
    exit_code = exit_map.get(report.final_status, ExitCode.BLOCKED)
    standard_fields = 判定结果转标准字段(mode_decision)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "failure_packet": str(packet_path),
                "final_status": report.final_status,
                "target_module": report.target_module,
                "repair_product": report.repair_product,
                "return_gate": report.return_gate,
                "secondary_failure_count": len(report.secondary_failures),
                "report_md": str(md_path),
                "report_json": str(json_path),
                **standard_fields,
                "exit_code": int(exit_code),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
