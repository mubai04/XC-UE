#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "公共组件"))

from 标准加载器 import 候选试验模式, 生产模式
from 安全路径 import resolve_inside_root, safe_id
from 工程异常 import 工程错误, 输入错误
from 项目加载器 import 加载项目
from 错误信封 import 打印错误信封
from 生产资格 import 要求生产资格


TARGETS = {
    "L1": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "L1运行入口.py",
        "default_run_id": "L1_RUN-UNIFIED",
        "forward_args": {"chapter", "project", "project_registry", "project_root", "project_manifest", "standard_mode"},
        "rule_source": ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "gate_rules.json",
    },
    "L1.5": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "L1.5工程" / "L1.5运行入口.py",
        "default_run_id": "L15_RUN-UNIFIED",
        "forward_args": {"failure_packet", "standard_mode", "pipeline_run_id", "stage_run_id", "out_dir"},
        "rule_source": ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "gate_rules.json",
    },
    "L2": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "L2运行入口.py",
        "default_run_id": "L2_RUN-UNIFIED",
        "forward_args": {"failure_packet", "l15_report", "standard_mode", "pipeline_run_id", "stage_run_id", "out_dir"},
        "rule_source": [
            ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json",
            ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "routes.json",
        ],
    },
    "L3": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "L3工程" / "L3运行入口.py",
        "default_run_id": "L3_RUN-UNIFIED",
        "forward_args": {"l2_report", "project_harness", "project", "project_registry", "standard_mode", "pipeline_run_id", "stage_run_id", "out_dir"},
        "rule_source": ROOT / "00_工程总控" / "工程执行层" / "L3工程" / "protocol_rules.json",
    },
    "REPAIR_PIPELINE": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "修复流水线运行入口.py",
        "default_run_id": "PIPELINE-UNIFIED",
        "forward_args": {"failure_packet", "project", "project_registry", "standard_mode", "pipeline_run_id", "workspace"},
        "rule_source": ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "gate_rules.json",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="XC-UE 统一工程执行入口。")
    parser.add_argument("--target", required=True, choices=sorted([*TARGETS, "PROJECT"]), help="运行目标。")
    parser.add_argument("--run-id", default=None, help="报告编号。")
    parser.add_argument("--chapter", default=None, help="L1 使用的章节正文路径。")
    parser.add_argument("--failure-packet", default=None, help="L1 failure packet 或修复流水线输入。")
    parser.add_argument("--l15-report", default=None, help="L1.5 路由报告 JSON。")
    parser.add_argument("--l2-report", default=None, help="L2 报告 JSON。")
    parser.add_argument("--project-harness", default=None, help="L3 Project Harness 根目录。")
    parser.add_argument("--project", default=None, help="项目 ID。")
    parser.add_argument("--project-registry", default=None, help="项目注册表路径。")
    parser.add_argument("--project-root", default=None, help="显式项目根目录；PROJECT 目标必须与项目清单二选一提供。")
    parser.add_argument("--project-manifest", default=None, help="显式项目清单路径；PROJECT 目标必须与项目根目录二选一提供。")
    parser.add_argument("--pipeline-run-id", default=None, help="流水线编号。")
    parser.add_argument("--stage-run-id", default=None, help="阶段运行编号。")
    parser.add_argument("--out-dir", default=None, help="阶段输出目录。")
    parser.add_argument("--workspace", default=None, help="修复流水线工作目录。")
    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式], help="标准加载模式。")
    args, extra = parser.parse_known_args()

    try:
        chapter_arg = str(resolve_inside_root(ROOT, args.chapter)) if args.chapter else None
        failure_packet_arg = str(resolve_inside_root(ROOT, args.failure_packet)) if args.failure_packet else None
        l15_report_arg = str(resolve_inside_root(ROOT, args.l15_report)) if args.l15_report else None
        l2_report_arg = str(resolve_inside_root(ROOT, args.l2_report)) if args.l2_report else None
        project_harness_arg = str(resolve_inside_root(ROOT, args.project_harness)) if args.project_harness else None
        out_dir_arg = str(resolve_inside_root(ROOT, args.out_dir)) if args.out_dir else None
        workspace_arg = str(resolve_inside_root(ROOT, args.workspace)) if args.workspace else None
        run_id_arg = safe_id(args.run_id, "run_id") if args.run_id else None
        pipeline_run_id_arg = safe_id(args.pipeline_run_id, "pipeline_run_id") if args.pipeline_run_id else None
        stage_run_id_arg = safe_id(args.stage_run_id, "stage_run_id") if args.stage_run_id else None
    except 输入错误 as exc:
        打印错误信封(exc, stage="ENTRY", run_id=args.run_id or "")
        return int(exc.exit_code)

    if args.target == "PROJECT":
        if not args.project_root and not args.project_manifest:
            exc = 输入错误("PROJECT 目标必须显式提供 --project-root 或 --project-manifest")
            打印错误信封(exc, stage="PROJECT_LOADER", run_id=run_id_arg or "")
            return int(exc.exit_code)
        try:
            project = 加载项目(
                ROOT,
                args.project,
                args.project_registry,
                project_root=args.project_root,
                project_manifest=args.project_manifest,
                allow_default=False,
            )
        except 工程错误 as exc:
            打印错误信封(exc, stage="PROJECT_LOADER", run_id=run_id_arg or "", details={"project": args.project or ""})
            return int(exc.exit_code)
        target = {
            "cwd": project.project_root,
            "entry": project.entrypoint,
            "default_run_id": f"PROJECT-RUN-UNIFIED-{project.project_id}",
            "forward_args": set(),
            "project_identity": project.project_id,
            "rule_source": project.project_manifest,
            "payload_target": project.project_id,
        }
    else:
        target = dict(TARGETS[args.target])

    forward_args = target["forward_args"]
    if chapter_arg and "chapter" in forward_args:
        extra = ["--chapter", chapter_arg, *extra]
    if failure_packet_arg and "failure_packet" in forward_args:
        extra = ["--failure-packet", failure_packet_arg, *extra]
    if l15_report_arg and "l15_report" in forward_args:
        extra = ["--l15-report", l15_report_arg, *extra]
    if l2_report_arg and "l2_report" in forward_args:
        extra = ["--l2-report", l2_report_arg, *extra]
    if project_harness_arg and "project_harness" in forward_args:
        extra = ["--project-harness", project_harness_arg, *extra]
    if args.project and "project" in forward_args:
        extra = ["--project", args.project, *extra]
    if args.project_registry and "project_registry" in forward_args:
        extra = ["--project-registry", args.project_registry, *extra]
    if args.project_root and "project_root" in forward_args:
        extra = ["--project-root", args.project_root, *extra]
    if args.project_manifest and "project_manifest" in forward_args:
        extra = ["--project-manifest", args.project_manifest, *extra]
    if pipeline_run_id_arg and "pipeline_run_id" in forward_args:
        extra = ["--pipeline-run-id", pipeline_run_id_arg, *extra]
    if stage_run_id_arg and "stage_run_id" in forward_args:
        extra = ["--stage-run-id", stage_run_id_arg, *extra]
    if out_dir_arg and "out_dir" in forward_args:
        extra = ["--out-dir", out_dir_arg, *extra]
    if workspace_arg and "workspace" in forward_args:
        extra = ["--workspace", workspace_arg, *extra]
    if "standard_mode" in forward_args:
        extra = ["--standard-mode", args.standard_mode, *extra]

    entry = target["entry"]
    cwd = target["cwd"]
    run_id = run_id_arg or target["default_run_id"]

    if not entry.exists():
        exc = 输入错误(f"运行目标入口不存在：{entry}")
        打印错误信封(exc, stage=args.target, run_id=run_id, path=entry)
        return int(exc.exit_code)
    try:
        要求生产资格(
            requested_mode=args.standard_mode,
            rule_source=target.get("rule_source"),
            entrypoint=args.target,
            project_identity=target.get("project_identity", args.project or args.target),
        )
    except 工程错误 as exc:
        打印错误信封(exc, stage=args.target, run_id=run_id, path=target.get("rule_source", ""), details=getattr(exc, "details", {}))
        return int(exc.exit_code)

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, str(entry), "--run-id", run_id, *extra]
    result = subprocess.run(cmd, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", capture_output=True, env=env)
    if result.returncode != 0 and (result.stderr or "").strip().startswith("{"):
        print((result.stderr or "").strip(), file=sys.stderr)
        return result.returncode

    payload = {
        "target": target.get("payload_target", args.target),
        "entry": str(entry.relative_to(ROOT)) if entry.is_relative_to(ROOT) else str(entry),
        "cwd": str(cwd.relative_to(ROOT)) if cwd.is_relative_to(ROOT) else str(cwd),
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
