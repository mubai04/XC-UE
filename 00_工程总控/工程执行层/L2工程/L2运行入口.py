#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from L2报告 import 写报告, 拒绝覆盖既有报告
from L2模型 import L2报告
from L2读取 import L2路由规则路径, 读失败包
from L2_99_接口判断 import 判断
from 修复单生成 import 生成
import L2_01_叙事结构能力
from L2禁止项检查 import 检查
from 能力规则加载 import L2能力规则路径, 加载能力规则
from 路由规则加载 import 加载路由规则
from 回流校验 import 校验
from 退出码 import ExitCode
from 运行状态 import 状态说明, 已完成, 已阻断, 结构无效
from 文件哈希 import 计算文件哈希
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
    parser = argparse.ArgumentParser(description="XC-UE L2工程：接收 L1 failure packet，按 L2-99 接口判断并生成 L2 修复单。")
    parser.add_argument("--failure-packet", default=None, help="L1 failure packet JSON 路径。")
    parser.add_argument("--run-id", default=None, help="报告编号。")
    parser.add_argument("--out-dir", default=None, help="输出目录。")
    parser.add_argument("--pipeline-run-id", default="", help="流水线编号。")
    parser.add_argument("--stage-run-id", default="", help="阶段运行编号。")
    parser.add_argument("--expected-input-sha256", default="", help="期望输入哈希。")
    parser.add_argument("--ability-rules", default=None, help="L2 结构化能力规则 JSON 路径。")
    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式], help="标准加载模式。")
    args = parser.parse_args()
    if not args.failure_packet:
        print(json.dumps({"error": "P0 后 L2 必须显式提供 --failure-packet"}, ensure_ascii=False), file=sys.stderr)
        return int(ExitCode.INPUT_INVALID)

    try:
        run_id = safe_id(args.run_id or "L2_RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S"), "run_id")
        pipeline_run_id = safe_id(args.pipeline_run_id, "pipeline_run_id") if args.pipeline_run_id else ""
        stage_run_id = safe_id(args.stage_run_id, "stage_run_id") if args.stage_run_id else ""
        packet_path = _解析输入输出路径(args.failure_packet, "failure_packet")
        out_dir = _解析输入输出路径(args.out_dir, "out_dir") if args.out_dir else Path(__file__).resolve().parent / "reports"
        拒绝覆盖既有报告(run_id, out_dir)
    except 工程错误 as exc:
        打印错误信封(exc, stage="L2", run_id=locals().get("run_id", ""), path=locals().get("out_dir", ""))
        return int(exc.exit_code)
    try:
        validated_packet = 校验JSON输入(
            packet_path,
            schema_path=SCHEMA_DIR / "失败包结构.json",
            label="L2 失败包",
            expected_schema_version="xcue.failure-packet/1.0",
            lineage=血缘期望(pipeline_run_id=pipeline_run_id) if pipeline_run_id else None,
        )
    except 工程错误 as exc:
        打印错误信封(exc, stage="L2", run_id=run_id, path=packet_path)
        return int(exc.exit_code)
    if args.expected_input_sha256:
        actual_hash = 计算文件哈希(packet_path)
        if actual_hash != args.expected_input_sha256:
            from 工程异常 import 哈希错误

            exc = 哈希错误("输入哈希不一致")
            打印错误信封(
                exc,
                stage="L2",
                run_id=run_id,
                path=packet_path,
                details={"expected": args.expected_input_sha256, "actual": actual_hash},
            )
            return int(exc.exit_code)

    try:
        ability_rules_path = Path(args.ability_rules) if args.ability_rules else L2能力规则路径(ROOT)
        if not ability_rules_path.is_absolute():
            ability_rules_path = (ROOT / ability_rules_path).resolve()
        mode_decision = 要求生产资格(
            requested_mode=args.standard_mode,
            rule_source=[ability_rules_path, L2路由规则路径(ROOT)],
            entrypoint="L2",
            project_identity=pipeline_run_id,
        )
        rules = 加载能力规则(ability_rules_path)
        rules.路由规则集 = 加载路由规则(L2路由规则路径(ROOT))
    except 工程错误 as exc:
        打印错误信封(exc, stage="L2", run_id=run_id, path=locals().get("ability_rules_path", ""))
        return int(exc.exit_code)
    items = 读失败包(packet_path)
    judgements = [判断(item, rules) for item in items]
    l201_diagnostics = []
    l201_rules = rules.能力规则.get("L2-01")
    if l201_rules:
        for item, judgement in zip(items, judgements):
            if judgement.主候选模块 == "L2-01" or judgement.次候选模块 == "L2-01":
                l201_diagnostics.append(L2_01_叙事结构能力.生成真实诊断(item, l201_rules))
    forms = 生成(items, judgements, rules)
    blocked = 检查(judgements)
    recheck_targets = [item for item in judgements if item.最终状态 == "派生复验"]
    standard_errors: list[str] = []
    return_errors = 校验(forms)
    if blocked and not forms:
        status = 已阻断
        exit_code = ExitCode.BLOCKED
    elif standard_errors or return_errors:
        status = 结构无效
        exit_code = ExitCode.SCHEMA_INVALID
    else:
        status = 已完成
        exit_code = ExitCode.OK

    result = L2报告(
        run_id=run_id,
        输入文件=str(packet_path),
        输入数量=len(items),
        方法声明="L2工程只做接口判断与修复单生成，不写正文、不替 L1.5 裁决；运行真源为结构化能力规则 JSON 与结构化路由规则 JSON，Markdown 仅作解释材料。",
        标准校验问题=standard_errors,
        回流校验问题=return_errors,
        接口判断=judgements,
        修复单=forms,
        阻断项=blocked,
        复验目标=recheck_targets,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id or f"{pipeline_run_id}-L2" if pipeline_run_id else run_id,
        status=status,
        状态说明=状态说明[status],
        extensions={"L2-01真实诊断": [asdict(diagnosis) for diagnosis in l201_diagnostics]} if l201_diagnostics else {},
    )
    md_path, json_path = 写报告(result, out_dir)
    standard_fields = 判定结果转标准字段(mode_decision)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "failure_packet": str(packet_path),
                "input_count": len(items),
                "fix_count": len(forms),
                "blocked_count": len(blocked),
                "recheck_target_count": len(recheck_targets),
                "standard_error_count": len(standard_errors),
                "return_error_count": len(return_errors),
                "report_md": str(md_path),
                "report_json": str(json_path),
                "ability_rules": str(ability_rules_path),
                **standard_fields,
                "status": status,
                "exit_code": int(exit_code),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
