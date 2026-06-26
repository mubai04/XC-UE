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

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from L3读取 import 读L2修复单
from 执行任务生成 import 生成 as 生成任务
from 输出生成 import 生成输出
from 任务单校验 import 校验 as 校验任务单
from 文件操作校验 import 校验 as 校验文件操作
from 正文任务校验 import 校验 as 校验正文任务
from 验收回填校验 import 校验 as 校验回填
from 版本回滚校验 import 校验 as 校验版本
from L3禁止项检查 import 检查 as 检查禁止项
from L3报告 import 写报告, 拒绝覆盖既有报告
from L3模型 import L3报告, 追加状态, 允许状态跳转
from IR输入映射校验 import 校验IR存在
from ProjectHarness运行校验 import 发现Harness, 确保Harness目录
from 协议规则加载 import L3协议规则路径, 加载协议规则
from 退出码 import ExitCode
from 运行状态 import 状态说明, 已完成, 已阻断, 结构无效, 等待执行器
from 标准加载器 import 候选试验模式, 生产模式
from 生产资格 import 判定结果转标准字段, 要求生产资格
from 工程异常 import 工程错误
from 安全路径 import resolve_inside_root, safe_id
from 输入校验 import 校验JSON输入, 血缘期望
from 错误信封 import 打印错误信封


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义"
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


def _解析输入输出路径(value: str | Path, label: str) -> Path:
    if _允许测试外部IO():
        resolved = Path(value).resolve()
        try:
            resolved.relative_to(Path(tempfile.gettempdir()).resolve())
        except ValueError:
            return resolve_inside_root(ROOT, value)
        return resolved
    return resolve_inside_root(ROOT, value)


def main() -> int:
    parser = argparse.ArgumentParser(description="XC-UE L3工程：把 L2 修复单转成执行任务单，并按 L3 协议校验。")
    parser.add_argument("--l2-report", default=None, help="L2 报告 JSON 路径。")
    parser.add_argument("--project-harness", default=None, help="Project Harness 根目录；未指定时从项目注册表加载。")
    parser.add_argument("--project", default=None, help="项目 ID；未指定时加载默认项目。")
    parser.add_argument("--project-registry", default=None, help="项目注册表路径。")
    parser.add_argument("--run-id", default=None, help="报告编号。")
    parser.add_argument("--out-dir", default=None, help="输出目录。")
    parser.add_argument("--pipeline-run-id", default="", help="流水线编号。")
    parser.add_argument("--stage-run-id", default="", help="阶段运行编号。")
    parser.add_argument("--protocol-rules", default=None, help="L3 结构化协议规则 JSON 路径。")
    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式], help="标准加载模式。")
    args = parser.parse_args()
    if not args.l2_report:
        print(json.dumps({"error": "P0 后 L3 必须显式提供 --l2-report"}, ensure_ascii=False), file=sys.stderr)
        return int(ExitCode.INPUT_INVALID)

    try:
        run_id = safe_id(args.run_id or "L3_RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S"), "run_id")
        pipeline_run_id = safe_id(args.pipeline_run_id, "pipeline_run_id") if args.pipeline_run_id else ""
        stage_run_id = safe_id(args.stage_run_id, "stage_run_id") if args.stage_run_id else ""
        source = _解析输入输出路径(args.l2_report, "l2_report")
        out_dir = _解析输入输出路径(args.out_dir, "out_dir") if args.out_dir else Path(__file__).resolve().parent / "reports"
        拒绝覆盖既有报告(run_id, out_dir)
    except 工程错误 as exc:
        打印错误信封(exc, stage="L3", run_id=locals().get("run_id", ""), path=locals().get("out_dir", ""))
        return int(exc.exit_code)
    try:
        validated_l2 = 校验JSON输入(
            source,
            schema_path=SCHEMA_DIR / "第二层报告结构.json",
            label="L3 输入 L2 报告",
            expected_schema_version="xcue.l2-report/1.0",
            lineage=血缘期望(pipeline_run_id=pipeline_run_id) if pipeline_run_id else None,
        )
    except 工程错误 as exc:
        打印错误信封(exc, stage="L3", run_id=run_id, path=source)
        return int(exc.exit_code)
    l2_meta = validated_l2.data
    if l2_meta.get("status") == "BLOCKED":
        print(json.dumps({"error": "L2 报告已阻断，L3 不生成任务包", "path": str(source)}, ensure_ascii=False), file=sys.stderr)
        return int(ExitCode.BLOCKED)

    try:
        protocol_rules_path = Path(args.protocol_rules) if args.protocol_rules else L3协议规则路径(ROOT)
        if not protocol_rules_path.is_absolute():
            protocol_rules_path = (ROOT / protocol_rules_path).resolve()
        mode_decision = 要求生产资格(
            requested_mode=args.standard_mode,
            rule_source=protocol_rules_path,
            entrypoint="L3",
            project_identity=pipeline_run_id,
        )
        rules = 加载协议规则(protocol_rules_path)
        允许状态跳转.clear()
        允许状态跳转.update(rules.状态跳转)
    except 工程错误 as exc:
        打印错误信封(exc, stage="L3", run_id=run_id, path=locals().get("protocol_rules_path", ""))
        return int(exc.exit_code)
    standard_errors: list[str] = []
    forms = 读L2修复单(source)
    try:
        harness = 发现Harness(ROOT, args.project_harness, args.project, args.project_registry)
        确保Harness目录(harness)
    except 工程错误 as exc:
        打印错误信封(exc, stage="L3", run_id=run_id, path=args.project_harness or args.project or "")
        return int(exc.exit_code)
    tasks = 生成任务(forms, str(source), run_id, ROOT, harness, rules)
    for task in tasks:
        task.校验问题 = []
        task.状态历史 = []
        task.校验问题.extend(校验任务单(task))
        task.校验问题.extend(校验IR存在(task, ROOT))
        task.校验问题.extend(校验文件操作(task))
        task.校验问题.extend(校验正文任务(task))
        task.校验问题.extend(校验回填(task, rules))
        task.校验问题.extend(校验版本(task))
        task.校验问题.extend(检查禁止项(task))
        if task.校验问题:
            追加状态(task, "VALIDATION_FAILED", "任务校验失败", "L3工程.运行", str(source))
            追加状态(task, "BLOCKED", "校验问题阻断任务", "L3工程.运行", str(source))
        else:
            追加状态(task, "INPUT_VALIDATED", "任务输入校验通过", "L3工程.运行", str(source))
            追加状态(task, "TASK_PLANNED", "任务规划完成", "L3工程.运行", str(source))

    outputs = [生成输出(task, ROOT, harness_root=harness) for task in tasks]
    blocked = [task for task in tasks if task.校验问题]
    created_outputs = [output for output in outputs if output.task_package_created]
    if standard_errors:
        status = 结构无效
        exit_code = ExitCode.SCHEMA_INVALID
    elif blocked and not created_outputs:
        status = 已阻断
        exit_code = ExitCode.BLOCKED
    else:
        status = 等待执行器 if tasks else 已完成
        exit_code = ExitCode.OK
    result = L3报告(
        run_id=run_id,
        输入文件=str(source),
        输入修复单数量=len(forms),
        方法声明=f"L3工程生成受约束任务包与 DeepSeek 候选正文；候选正文仅写入 chapters/_candidates/，不修改正式正文。Project Harness：{harness}",
        标准校验问题=standard_errors,
        协议规则摘要={
            "状态机步骤数": len(rules.状态机),
            "权限矩阵项": len(rules.权限矩阵),
            "任务字段": rules.任务字段,
            "输出字段": rules.输出字段,
            "执行顺序": rules.执行顺序,
            "IR推荐文件数": len(rules.IR推荐文件),
            "候选必备目录": rules.候选必备目录,
            "禁止项数": len(rules.禁止项),
        },
        任务单=tasks,
        执行输出=outputs,
        阻断任务=blocked,
        protocol_rule_version=rules.规则版本,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id or f"{pipeline_run_id}-L3" if pipeline_run_id else run_id,
        status=status,
        状态说明=状态说明[status],
        task_package_created=bool(created_outputs),
    )
    md_path, json_path = 写报告(result, out_dir)
    standard_fields = 判定结果转标准字段(mode_decision)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "l2_report": str(source),
                "input_fix_count": len(forms),
                "task_count": len(tasks),
                "blocked_count": len(blocked),
                "task_package_created_count": len(created_outputs),
                "standard_error_count": len(standard_errors),
                "report_md": str(md_path),
                "report_json": str(json_path),
                "protocol_rules": str(protocol_rules_path),
                "status": status,
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
