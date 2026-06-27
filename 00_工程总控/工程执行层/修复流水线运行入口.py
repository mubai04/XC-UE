#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
EXEC = ROOT / "00_工程总控" / "工程执行层"
公共组件 = EXEC / "公共组件"
L15_DIR = EXEC / "L1.5工程"
L2_DIR = EXEC / "L2工程"
L3_DIR = EXEC / "L3工程"
for path in (公共组件, L15_DIR, L2_DIR, L3_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

import L2运行入口  # noqa: E402
import L3运行入口  # noqa: E402
from ProjectHarness运行校验 import 发现Harness  # noqa: E402
from 退出码 import ExitCode  # noqa: E402
from 标准加载器 import 候选试验模式, 生产模式  # noqa: E402
from 工程异常 import 工程错误  # noqa: E402
from 安全路径 import resolve_inside_root, safe_id  # noqa: E402
from 项目加载器 import 加载项目  # noqa: E402
from 错误信封 import 打印错误信封  # noqa: E402

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


def _run_stage(main_fn, argv: list[str]) -> tuple[int, dict[str, Any]]:
    old_argv = sys.argv
    sys.argv = argv
    try:
        code = main_fn()
    finally:
        sys.argv = old_argv
    payload = json.loads((sys.stdout if False else "") or "{}")
    return code, payload


def _capture_stage(main_fn, argv: list[str]) -> tuple[int, dict[str, Any]]:
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    buffer = StringIO()
    error_buffer = StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with redirect_stdout(buffer), redirect_stderr(error_buffer):
            code = main_fn()
    finally:
        sys.argv = old_argv
    text = (buffer.getvalue() or error_buffer.getvalue() or "").strip()
    payload: dict[str, Any] = {}
    if text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            for line in reversed(text.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        payload = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
    return code, payload


def 执行修复流水线(
    *,
    failure_packet: Path,
    project_id: str | None,
    project_registry: str | None,
    run_id: str,
    pipeline_run_id: str,
    standard_mode: str = 候选试验模式,
    workspace: Path | None = None,
    project_harness: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    workspace = workspace or (ROOT / "运行记录" / "repair-pipeline" / run_id)
    workspace.mkdir(parents=True, exist_ok=True)
    l15_dir = workspace / "l15"
    l2_dir = workspace / "l2"
    l3_dir = workspace / "l3"
    stages: list[dict[str, Any]] = []

    l15_entry = L15_DIR / "L1.5运行入口.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("L15运行入口", l15_entry)
    l15_mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(l15_mod)

    l15_code, l15_payload = _capture_stage(
        l15_mod.main,
        [
            str(l15_entry),
            "--failure-packet",
            str(failure_packet),
            "--run-id",
            f"{run_id}-L15",
            "--out-dir",
            str(l15_dir),
            "--pipeline-run-id",
            pipeline_run_id,
            "--stage-run-id",
            f"{pipeline_run_id}-L15",
            "--standard-mode",
            standard_mode,
        ],
    )
    stages.append(
        {
            "stage": "L1.5",
            "exit_code": l15_code,
            "input": str(failure_packet),
            "output_json": l15_payload.get("report_json", ""),
            "status": l15_payload.get("final_status", ""),
        }
    )
    if l15_code != 0 or l15_payload.get("final_status") != "ROUTED":
        summary = {
            "run_id": run_id,
            "pipeline_run_id": pipeline_run_id,
            "stages": stages,
            "final_status": "STOPPED_AT_L15",
            "exit_code": int(l15_code or ExitCode.BLOCKED),
        }
        (workspace / f"{run_id}_pipeline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return int(summary["exit_code"]), summary

    l2_code, l2_payload = _capture_stage(
        L2运行入口.main,
        [
            "L2运行入口.py",
            "--l15-report",
            l15_payload["report_json"],
            "--run-id",
            f"{run_id}-L2",
            "--out-dir",
            str(l2_dir),
            "--pipeline-run-id",
            pipeline_run_id,
            "--stage-run-id",
            f"{pipeline_run_id}-L2",
            "--standard-mode",
            standard_mode,
        ],
    )
    stages.append(
        {
            "stage": "L2",
            "exit_code": l2_code,
            "input": l15_payload.get("report_json", ""),
            "output_json": l2_payload.get("report_json", ""),
            "status": l2_payload.get("status", ""),
        }
    )
    if l2_code != 0 or l2_payload.get("fix_count", 0) < 1:
        summary = {
            "run_id": run_id,
            "pipeline_run_id": pipeline_run_id,
            "stages": stages,
            "final_status": "STOPPED_AT_L2",
            "exit_code": int(l2_code or ExitCode.BLOCKED),
        }
        (workspace / f"{run_id}_pipeline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return int(summary["exit_code"]), summary

    project = None
    if project_harness:
        harness = Path(project_harness).resolve()
        from ProjectHarness运行校验 import 确保Harness目录

        确保Harness目录(harness)
        manifest = json.loads((harness / "project.json").read_text(encoding="utf-8-sig"))
        project_id_for_l3 = str(manifest.get("project_id") or project_id or "harness")
    else:
        project = 加载项目(ROOT, project_id, project_registry, allow_default=True)
        harness = 发现Harness(ROOT, None, project.project_id, project_registry)
        project_id_for_l3 = project.project_id

    l3_code, l3_payload = _capture_stage(
        L3运行入口.main,
        [
            "L3运行入口.py",
            "--l2-report",
            l2_payload["report_json"],
            "--run-id",
            f"{run_id}-L3",
            "--out-dir",
            str(l3_dir),
            "--project-harness",
            str(harness.relative_to(ROOT)) if harness.is_relative_to(ROOT) else str(harness),
            "--project",
            project_id_for_l3,
            "--pipeline-run-id",
            pipeline_run_id,
            "--stage-run-id",
            f"{pipeline_run_id}-L3",
            "--standard-mode",
            standard_mode,
        ],
    )
    stages.append(
        {
            "stage": "L3",
            "exit_code": l3_code,
            "input": l2_payload.get("report_json", ""),
            "output_json": l3_payload.get("report_json", ""),
            "status": l3_payload.get("status", ""),
            "candidate_outputs": l3_payload.get("candidate_outputs", []),
        }
    )
    final_status = "COMPLETED" if l3_code == 0 else "STOPPED_AT_L3"
    summary = {
        "run_id": run_id,
        "pipeline_run_id": pipeline_run_id,
        "stages": stages,
        "final_status": final_status,
        "exit_code": int(l3_code),
        "l15_report": l15_payload.get("report_json", ""),
        "l2_report": l2_payload.get("report_json", ""),
        "l3_report": l3_payload.get("report_json", ""),
    }
    summary_path = workspace / f"{run_id}_pipeline_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["pipeline_summary"] = str(summary_path)
    return int(l3_code), summary


def main() -> int:
    parser = argparse.ArgumentParser(description="XC-UE 修复流水线：failure packet → L1.5 → L2 → L3 候选正文。")
    parser.add_argument("--failure-packet", required=True)
    parser.add_argument("--project", default=None)
    parser.add_argument("--project-registry", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--pipeline-run-id", default="")
    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式])
    parser.add_argument("--project-harness", default=None)
    parser.add_argument("--workspace", default=None)
    args = parser.parse_args()
    try:
        run_id = safe_id(args.run_id or "PIPELINE-" + datetime.now().strftime("%Y%m%d-%H%M%S"), "run_id")
        pipeline_run_id = safe_id(args.pipeline_run_id, "pipeline_run_id") if args.pipeline_run_id else run_id
        packet_path = _解析路径(args.failure_packet, "failure_packet")
        workspace = _解析路径(args.workspace, "workspace") if args.workspace else None
        harness_path = _解析路径(args.project_harness, "project_harness") if args.project_harness else None
    except 工程错误 as exc:
        打印错误信封(exc, stage="REPAIR_PIPELINE", run_id=locals().get("run_id", ""))
        return int(exc.exit_code)

    code, summary = 执行修复流水线(
        failure_packet=packet_path,
        project_id=args.project,
        project_registry=args.project_registry,
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        standard_mode=args.standard_mode,
        workspace=workspace,
        project_harness=harness_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
