#!/usr/bin/env python3

from __future__ import annotations



import argparse

import json

import os

import sys

import tempfile

import warnings

from datetime import datetime

from pathlib import Path



sys.dont_write_bytecode = True



L2_DIR = Path(__file__).resolve().parent

公共组件 = L2_DIR.parents[0] / "公共组件"

if str(公共组件) not in sys.path:

    sys.path.insert(0, str(公共组件))

if str(L2_DIR) not in sys.path:

    sys.path.insert(0, str(L2_DIR))

from L2路径注册 import 注册L2子路径

注册L2子路径()



from L2_L15执行 import 从L15报告提取执行上下文, 读L15报告

from L2报告 import 写报告, 拒绝覆盖既有报告

from L2模型 import L2报告

from L2读取 import L2路由规则路径, 读失败包完整

from L2_99_接口判断 import 判断

from 修复单生成 import 执行L15分配模块, 生成

from L2禁止项检查 import 检查

from 能力规则加载 import L2能力规则路径, 加载能力规则

from 路由规则加载 import 加载路由规则

from 回流校验 import 校验

from 退出码 import ExitCode

from 运行状态 import 状态说明, 已完成, 已阻断, 结构无效, 部分阻断, 模型阻断

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

    parser = argparse.ArgumentParser(description="XC-UE L2工程：接收 L1.5 路由报告并执行已分配模块。")

    parser.add_argument("--l15-report", default=None, help="L1.5 路由报告 JSON 路径（正式输入）。")

    parser.add_argument("--failure-packet", default=None, help="[deprecated] 旧 L1 failure packet 直连入口。")

    parser.add_argument("--run-id", default=None, help="报告编号。")

    parser.add_argument("--out-dir", default=None, help="输出目录。")

    parser.add_argument("--pipeline-run-id", default="", help="流水线编号。")

    parser.add_argument("--stage-run-id", default="", help="阶段运行编号。")

    parser.add_argument("--ability-rules", default=None, help="L2 结构化能力规则 JSON 路径。")

    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式], help="标准加载模式。")

    args = parser.parse_args()



    if not args.l15_report and not args.failure_packet:

        print(json.dumps({"error": "L2 必须提供 --l15-report（正式）或 --failure-packet（deprecated）"}, ensure_ascii=False), file=sys.stderr)

        return int(ExitCode.INPUT_INVALID)



    deprecated_mode = bool(args.failure_packet and not args.l15_report)

    if deprecated_mode:

        warnings.warn(

            "L2 --failure-packet 已 deprecated：正式流水线必须经过 L1.5；此路径不得产生正式执行成功状态。",

            DeprecationWarning,

            stacklevel=2,

        )

        print(

            "DEPRECATED: --failure-packet bypasses L1.5; formal pipeline must use --l15-report.",

            file=sys.stderr,

        )



    try:

        run_id = safe_id(args.run_id or "L2_RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S"), "run_id")

        pipeline_run_id = safe_id(args.pipeline_run_id, "pipeline_run_id") if args.pipeline_run_id else ""

        stage_run_id = safe_id(args.stage_run_id, "stage_run_id") if args.stage_run_id else ""

        out_dir = _解析输入输出路径(args.out_dir, "out_dir") if args.out_dir else Path(__file__).resolve().parent / "reports"

        拒绝覆盖既有报告(run_id, out_dir)

    except 工程错误 as exc:

        打印错误信封(exc, stage="L2", run_id=locals().get("run_id", ""), path=locals().get("out_dir", ""))

        return int(exc.exit_code)



    input_label = ""

    input_path: Path | None = None

    l15_meta: dict = {}



    if args.l15_report:

        input_path = _解析输入输出路径(args.l15_report, "l15_report")

        input_label = str(input_path)

        try:

            校验JSON输入(

                input_path,

                schema_path=SCHEMA_DIR / "L1.5路由报告结构.json",

                label="L2 输入 L1.5 报告",

                expected_schema_version="xcue.l15-route-report/1.0",

                lineage=血缘期望(pipeline_run_id=pipeline_run_id) if pipeline_run_id else None,

            )

        except 工程错误 as exc:

            打印错误信封(exc, stage="L2", run_id=run_id, path=input_path)

            return int(exc.exit_code)

        l15_meta = 读L15报告(input_path)

    else:

        input_path = _解析输入输出路径(args.failure_packet, "failure_packet")

        input_label = str(input_path)

        try:

            校验JSON输入(

                input_path,

                schema_path=SCHEMA_DIR / "失败包结构.json",

                label="L2 失败包",

                expected_schema_version="xcue.failure-packet/1.0",

                lineage=血缘期望(pipeline_run_id=pipeline_run_id) if pipeline_run_id else None,

            )

        except 工程错误 as exc:

            打印错误信封(exc, stage="L2", run_id=run_id, path=input_path)

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



    method = (

        "L2 正式输入为 L1.5 路由报告：只执行 target_module，不再重新裁决 L1 失败项。"

        if not deprecated_mode

        else "DEPRECATED failure-packet 直连：仅供兼容；不得用于正式流水线。"

    )



    if args.l15_report:

        item, chapter_path, target_module, l15_status, l15_blockers = 从L15报告提取执行上下文(input_path)

        if l15_status != "ROUTED":

            result = L2报告(

                run_id=run_id,

                输入文件=input_label,

                输入数量=1,

                方法声明=method,

                标准校验问题=l15_blockers,

                回流校验问题=[],

                接口判断=[],

                修复单=[],

                阻断项=[],

                pipeline_run_id=pipeline_run_id,

                stage_run_id=stage_run_id or f"{pipeline_run_id}-L2" if pipeline_run_id else run_id,

                status=已阻断,

                状态说明=f"L1.5 状态 {l15_status}，L2 未执行",

                extensions={"l15_final_status": l15_status},

            )

            md_path, json_path = 写报告(result, out_dir)

            print(json.dumps({"run_id": run_id, "status": 已阻断, "exit_code": int(ExitCode.BLOCKED), "report_json": str(json_path)}, ensure_ascii=False))

            return int(ExitCode.BLOCKED)



        forms, generation_errors, judgement, blocked = 执行L15分配模块(

            item,

            target_module,

            rules,

            chapter_path=chapter_path,

            repo_root=ROOT,

            route_rule_id=str(l15_meta.get("route_rule_id", "")),

            route_rule_version=str(l15_meta.get("route_rule_version", "")),

        )

        judgements = [judgement]

        recheck_targets: list = []

    else:

        items, packet_meta = 读失败包完整(input_path)

        chapter_path = packet_meta.chapter_path

        judgements = [判断(item, rules) for item in items]

        forms, generation_errors = 生成(items, judgements, rules, chapter_path=chapter_path, repo_root=ROOT)

        blocked = 检查(judgements)

        recheck_targets = [item for item in judgements if item.最终状态 == "派生复验"]

        if not deprecated_mode:

            blocked = blocked

        else:

            blocked = blocked + [

                judgement

                for judgement in judgements

                if judgement.最终状态 == "接口明确" and forms

            ]



    if args.l15_report:

        blocked = blocked

    elif not deprecated_mode:

        blocked = 检查(judgements)

    else:

        pass



    if not args.l15_report:

        blocked = 检查(judgements)



    model_errors: list[str] = list(generation_errors)

    return_errors = 校验(forms)

    standard_errors: list[str] = []

    if deprecated_mode and forms:

        status = 部分阻断

        exit_code = ExitCode.BLOCKED

        standard_errors.append("deprecated failure-packet 路径不得标记正式执行成功")

    elif blocked and not forms:

        status = 已阻断

        exit_code = ExitCode.BLOCKED

    elif return_errors:

        status = 结构无效

        exit_code = ExitCode.SCHEMA_INVALID

        standard_errors = list(return_errors)

    elif model_errors:

        status = 部分阻断 if forms else 模型阻断

        exit_code = ExitCode.BLOCKED

    else:

        status = 已完成 if not deprecated_mode else 部分阻断

        exit_code = ExitCode.OK if not deprecated_mode else ExitCode.BLOCKED



    result = L2报告(

        run_id=run_id,

        输入文件=input_label,

        输入数量=1 if args.l15_report else len(judgements),

        方法声明=method,

        标准校验问题=standard_errors,

        回流校验问题=return_errors,

        接口判断=judgements,

        修复单=forms,

        阻断项=blocked,

        复验目标=recheck_targets,

        pipeline_run_id=pipeline_run_id,

        stage_run_id=stage_run_id or f"{pipeline_run_id}-L2" if pipeline_run_id else run_id,

        status=status,

        状态说明=状态说明.get(status, status),

        extensions={"model_errors": model_errors, "deprecated_failure_packet": deprecated_mode},

    )

    md_path, json_path = 写报告(result, out_dir)

    standard_fields = 判定结果转标准字段(mode_decision)

    print(

        json.dumps(

            {

                "run_id": run_id,

                "input_file": input_label,

                "input_count": result.输入数量,

                "fix_count": len(forms),

                "blocked_count": len(result.阻断项),

                "recheck_target_count": len(recheck_targets),

                "standard_error_count": len(standard_errors),

                "model_error_count": len(model_errors),

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

