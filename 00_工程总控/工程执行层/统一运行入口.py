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

from 流水线运行 import 运行流水线
from 标准加载器 import 候选试验模式, 生产模式
from 安全路径 import resolve_inside_root, safe_id
from 工程异常 import 工程错误, 输入错误
from 项目加载器 import 加载项目, 读取默认项目ID
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
    "正文检测": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "正文检测" / "正文检测运行入口.py",
        "default_run_id": "正文检测_COMPAT-RUN-UNIFIED",
        "forward_args": {"chapter", "project", "standard_mode"},
        "rule_source": ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "gate_rules.json",
    },
    "L2": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "L2运行入口.py",
        "default_run_id": "L2_RUN-UNIFIED",
        "forward_args": {"standard_mode"},
        "rule_source": [
            ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json",
            ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "routes.json",
        ],
    },
    "L3": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "L3工程" / "L3运行入口.py",
        "default_run_id": "L3_RUN-UNIFIED",
        "forward_args": {"standard_mode"},
        "rule_source": ROOT / "00_工程总控" / "工程执行层" / "L3工程" / "protocol_rules.json",
    },
    "L3_PATCH": {
        "cwd": ROOT,
        "entry": ROOT / "00_工程总控" / "工程执行层" / "L3工程" / "L3补丁执行入口.py",
        "default_run_id": "L3_PATCH-UNIFIED",
        "forward_args": {"standard_mode"},
        "rule_source": ROOT / "00_工程总控" / "工程执行层" / "L3工程" / "protocol_rules.json",
    },
}


def main() -> int:
    try:
        default_project_id = 读取默认项目ID(ROOT)
    except 输入错误 as exc:
        打印错误信封(exc, stage="PROJECT_LOADER")
        return int(exc.exit_code)
    runtime_targets = {
        **TARGETS,
        default_project_id: {
            "project_target": default_project_id,
            "entry_relative": Path("engine") / "TP001运行入口.py",
            "rule_relative": Path("engine") / "rules_tp001_v0.1.json",
            "default_run_id": f"ENGINE-RUN-UNIFIED-{default_project_id}",
            "forward_args": set(),
        },
    }
    parser = argparse.ArgumentParser(description="XC-UE 统一工程执行入口。")
    parser.add_argument("--target", required=True, choices=sorted([*runtime_targets, "PIPELINE", "PROJECT"]), help="运行目标。")
    parser.add_argument("--run-id", default=None, help="报告编号。")
    parser.add_argument("--chapter", default=None, help="PIPELINE 使用的章节正文路径。")
    parser.add_argument("--project", default=None, help="PIPELINE 使用的项目 ID；未指定时加载默认项目。")
    parser.add_argument("--project-registry", default=None, help="项目注册表路径；默认使用工程执行层项目注册表。")
    parser.add_argument("--project-root", default=None, help="显式项目根目录。")
    parser.add_argument("--project-manifest", default=None, help="显式项目清单路径。")
    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式], help="标准加载模式。")
    args, extra = parser.parse_known_args()

    try:
        chapter_arg = args.chapter
        if chapter_arg and args.target != "PIPELINE":
            chapter_arg = str(resolve_inside_root(ROOT, chapter_arg))
        run_id_arg = safe_id(args.run_id, "run_id") if args.run_id else None
    except 输入错误 as exc:
        打印错误信封(exc, stage="ENTRY", run_id=args.run_id or "")
        return 20

    if args.target == "PIPELINE":
        try:
            project = 加载项目(
                ROOT,
                args.project,
                args.project_registry,
                project_root=args.project_root,
                project_manifest=args.project_manifest,
            )
        except 工程错误 as exc:
            打印错误信封(exc, stage="PROJECT_LOADER", run_id=run_id_arg or "", details={"project": args.project or ""})
            return int(exc.exit_code)
        return 运行流水线(Path(chapter_arg) if chapter_arg else project.chapter_source, project, run_id_arg, args.standard_mode)

    if args.target == "PROJECT":
        try:
            project = 加载项目(
                ROOT,
                args.project,
                args.project_registry,
                project_root=args.project_root,
                project_manifest=args.project_manifest,
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
        target = dict(runtime_targets[args.target])
        if "project_target" in target:
            try:
                project = 加载项目(ROOT, target["project_target"], args.project_registry)
            except 工程错误 as exc:
                打印错误信封(exc, stage="PROJECT_LOADER", run_id=run_id_arg or "", details={"project": target["project_target"]})
                return int(exc.exit_code)
            target["cwd"] = project.project_root
            target["entry"] = project.entrypoint
            target["rule_source"] = project.project_manifest
            target["project_identity"] = project.project_id
            target["payload_target"] = project.project_id

    forward_args = target["forward_args"]

    if chapter_arg and "chapter" in forward_args:
        extra = ["--chapter", chapter_arg, *extra]
    if args.project and "project" in forward_args:
        extra = ["--project", args.project, *extra]
    if args.project_registry and "project_registry" in forward_args:
        extra = ["--project-registry", args.project_registry, *extra]
    if args.project_root and "project_root" in forward_args:
        extra = ["--project-root", args.project_root, *extra]
    if args.project_manifest and "project_manifest" in forward_args:
        extra = ["--project-manifest", args.project_manifest, *extra]
    if "standard_mode" in forward_args:
        extra = ["--standard-mode", args.standard_mode, *extra]

    entry = target["entry"]
    cwd = target["cwd"]
    run_id = run_id_arg or target["default_run_id"]

    if not entry.exists():
        raise FileNotFoundError(f"Missing target entry: {entry}")
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
