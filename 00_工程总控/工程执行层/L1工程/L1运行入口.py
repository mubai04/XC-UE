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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 正文切分 import 切段, 正文字数, 清理正文
from L1报告 import 写报告, 拒绝覆盖既有报告
from L1模型 import 正文检测结果
from L1读取 import 读文本
from 闸门规则加载 import L1闸门规则路径, 加载闸门规则
from L15交接 import 生成路由建议
from 失败包生成 import 生成失败包
import L1_前置质量护栏
import L1_00_闸门接口校验
import L1_01_内部创作检测
import L1_02_读者投入检测
import L1_03_发布锁检测
from 退出码 import ExitCode
from 工程异常 import 工程错误
from 运行状态 import 状态说明, 机器初筛通过, 机器初筛退回, 需要人工复核
from 标准加载器 import 候选试验模式, 生产模式
from 生产资格 import 判定结果转标准字段, 要求生产资格
from 安全路径 import resolve_inside_root, safe_id
from 错误信封 import 打印错误信封
from 项目加载器 import 加载项目, 校验项目正文路径


ROOT = Path(__file__).resolve().parents[3]
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


def _是流水线输入快照(path: Path, pipeline_run_id: str) -> bool:
    if not pipeline_run_id:
        return False
    try:
        path.resolve().relative_to((ROOT / "运行记录" / pipeline_run_id / "输入快照").resolve())
    except ValueError:
        return False
    return True


def _是测试注入正文(path: Path) -> bool:
    if not _允许测试外部IO():
        return False
    try:
        path.resolve().relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="XC-UE L1工程：按结构化 L1 闸门规则生成章节正文检测报告。")
    parser.add_argument("--chapter", default=None, help="待检测正文 Markdown 路径；未指定时使用默认项目候选正文。")
    parser.add_argument("--run-id", default=None, help="报告编号。")
    parser.add_argument("--project", default=None, help="项目 ID；未指定时加载默认项目。")
    parser.add_argument("--project-registry", default=None, help="项目注册表路径。")
    parser.add_argument("--project-root", default=None, help="显式项目根目录。")
    parser.add_argument("--project-manifest", default=None, help="显式项目清单路径。")
    parser.add_argument("--out-dir", default=None, help="输出目录。")
    parser.add_argument("--pipeline-run-id", default="", help="流水线编号。")
    parser.add_argument("--stage-run-id", default="", help="阶段运行编号。")
    parser.add_argument("--gate-rules", default=None, help="L1 结构化闸门规则 JSON 路径。")
    parser.add_argument("--standard-mode", default=候选试验模式, choices=[生产模式, 候选试验模式], help="标准加载模式。")
    args = parser.parse_args()

    try:
        run_id = safe_id(args.run_id or "L1_RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S"), "run_id")
        pipeline_run_id = safe_id(args.pipeline_run_id, "pipeline_run_id") if args.pipeline_run_id else run_id
        stage_run_id = safe_id(args.stage_run_id, "stage_run_id") if args.stage_run_id else ""
        project_context = 加载项目(
            ROOT,
            args.project,
            args.project_registry,
            project_root=args.project_root,
            project_manifest=args.project_manifest,
        )
        out_dir = _解析输入输出路径(args.out_dir, "out_dir") if args.out_dir else Path(__file__).resolve().parent / "reports"
        拒绝覆盖既有报告(run_id, out_dir)
    except 工程错误 as exc:
        打印错误信封(exc, stage="L1", run_id=locals().get("run_id", ""), path=locals().get("out_dir", ""))
        return int(exc.exit_code)
    try:
        gate_rules_path = Path(args.gate_rules) if args.gate_rules else L1闸门规则路径(ROOT)
        if not gate_rules_path.is_absolute():
            gate_rules_path = (ROOT / gate_rules_path).resolve()
        mode_decision = 要求生产资格(
            requested_mode=args.standard_mode,
            rule_source=gate_rules_path,
            entrypoint="L1",
            project_identity=project_context.project_id,
        )
        if args.chapter:
            chapter_input = _解析输入输出路径(args.chapter, "chapter")
            if _是流水线输入快照(chapter_input, pipeline_run_id) or _是测试注入正文(chapter_input):
                chapter_path = chapter_input
            else:
                chapter_path = 校验项目正文路径(project_context, chapter_input)
        else:
            chapter_path = project_context.chapter_source
        if not chapter_path.exists():
            raise SystemExit(ExitCode.INPUT_INVALID)
        raw = 读文本(chapter_path)
        if not raw.strip():
            raise SystemExit(ExitCode.INPUT_INVALID)
        rules = 加载闸门规则(gate_rules_path)
        gate_rules_raw = json.loads(gate_rules_path.read_text(encoding="utf-8-sig"))
        gate_rule_version = gate_rules_raw["version"]
    except 工程错误 as exc:
        打印错误信封(exc, stage="L1", run_id=run_id, path=locals().get("gate_rules_path", ""))
        return int(exc.exit_code)
    title, body = 清理正文(raw)
    paragraphs = 切段(body)
    if not paragraphs:
        raise SystemExit(ExitCode.INPUT_INVALID)
    word_count = 正文字数(paragraphs)

    l101 = L1_01_内部创作检测.检测(paragraphs, rules.L101, rules.L15路由)
    l101_passed = l101.判断结果 == "STRUCTURE_SIGNAL_PRESENT"
    l102 = L1_02_读者投入检测.检测(paragraphs, rules.L102, l101_passed, rules.L15路由)
    l102_passed = l102.判断结果 == "STRUCTURE_SIGNAL_PRESENT"
    l103 = L1_03_发布锁检测.检测(paragraphs, word_count, rules.L103, l102_passed, rules.L15路由)

    gates = [l101, l102, l103]
    l100 = L1_00_闸门接口校验.检测(gates)
    guard_items = L1_前置质量护栏.检测(paragraphs)
    l100.检测项.extend(guard_items)
    if guard_items:
        l100.失败类型.extend([item.失败类型 for item in guard_items if item.失败类型])
        l100.失败位置.extend([e for item in guard_items for e in item.证据])
        l100.是否进入L15 = "是"
        l100.调用方向.extend([item.候选模块 for item in guard_items if item.候选模块])
        if any(item.严重级别 == "error" for item in guard_items):
            l100.判断结果 = "SCREENING_REJECT"
        else:
            l100.判断结果 = "HUMAN_REVIEW_REQUIRED"
        l100.最终状态 = l100.判断结果
    gates = [l100, *gates]
    failure_packet = 生成失败包(gates)
    routes = 生成路由建议(failure_packet, rules.L15路由)
    has_error = any(item.严重级别 == "error" for item in failure_packet)
    has_warning = any(item.严重级别 == "warning" for item in failure_packet)
    if has_error:
        status = 机器初筛退回
        exit_code = ExitCode.GATE_REJECTED
    elif has_warning:
        status = 需要人工复核
        exit_code = ExitCode.REVIEW_REQUIRED
    else:
        status = 机器初筛通过
        exit_code = ExitCode.OK

    result = 正文检测结果(
        run_id=run_id,
        项目=project_context.project_id,
        章节路径=str(chapter_path),
        章节标题=title,
        当前字数=word_count,
        段落数=len(paragraphs),
        方法声明="自动检测只做未验证的启发式风险筛查：按结构化 L1 闸门规则提取可证据化的正文风险；Markdown 仅作解释材料，不能冒充最终文学判断、读者投入判断或发布授权。",
        闸门结果=gates,
        失败包=failure_packet,
        路由建议=routes,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id or f"{pipeline_run_id}-L1",
        status=status,
        状态说明=状态说明[status],
        rule_version=gate_rule_version,
    )

    try:
        md_path, json_path, packet_path = 写报告(result, out_dir)
    except 工程错误 as exc:
        打印错误信封(exc, stage="L1", run_id=run_id, path=out_dir)
        return int(exc.exit_code)
    standard_fields = 判定结果转标准字段(mode_decision)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "chapter": str(chapter_path),
                "word_count": word_count,
                "paragraphs": len(paragraphs),
                "report_md": str(md_path),
                "report_json": str(json_path),
                "failure_packet": str(packet_path),
                "gate_results": {gate.闸门: gate.判断结果 for gate in gates},
                "failure_count": len(failure_packet),
                "status": status,
                "heuristic": result.heuristic,
                "publish_authority": result.publish_authority,
                "human_review_required": result.human_review_required,
                "validation_status": result.validation_status,
                "exit_code": int(exit_code),
                **standard_fields,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
