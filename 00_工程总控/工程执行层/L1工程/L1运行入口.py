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
from 失败包生成 import 分拆阻断项
import L1_前置质量护栏
import L1_00_闸门接口校验
import L1_01_内部创作检测
import L1_02_读者投入检测
import L1_03_发布锁检测
import L1_语义审计
from L1_语义上下文 import 构建语义上下文
from 退出码 import ExitCode
from 工程异常 import 工程错误
from 运行状态 import 状态说明, 审计阻断
from L1决策角色 import 聚合终态
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
    l102 = L1_02_读者投入检测.检测(paragraphs, rules.L102, True, rules.L15路由)
    l103 = L1_03_发布锁检测.检测(paragraphs, word_count, rules.L103, True, rules.L15路由)

    gates = [l101, l102, l103]
    l100 = L1_00_闸门接口校验.检测(gates)
    guard_items = L1_前置质量护栏.检测(paragraphs, l103=rules.L103)
    semantic_ctx = 构建语义上下文(
        chapter_path=chapter_path,
        title=title,
        body=body,
        paragraphs=paragraphs,
        project=project_context,
    )
    semantic = L1_语义审计.审计(semantic_ctx)
    l100.检测项.extend(guard_items)
    l100.检测项.extend(semantic.检测项列表)
    gates = [l100, *gates]
    split = 分拆阻断项(gates)
    failure_packet = split.失败包
    audit_blockers = split.审计阻断项
    routes = 生成路由建议(failure_packet, rules.L15路由) if failure_packet else []
    final = 聚合终态(semantic, failure_packet, audit_blockers)
    status = final.status
    exit_code = final.exit_code

    result = 正文检测结果(
        run_id=run_id,
        项目=project_context.project_id,
        章节路径=str(chapter_path),
        章节标题=title,
        当前字数=word_count,
        段落数=len(paragraphs),
        方法声明="L1 词面闸门仅输出 DIAGNOSTIC 诊断信号；客观硬护栏与 L1-SEM DeepSeek 语义审计承担裁决；API 不可用或证据无效时输出 AUDIT_BLOCKED，不回退词面结论。",
        闸门结果=gates,
        失败包=failure_packet,
        审计阻断项=audit_blockers,
        路由建议=routes,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id or f"{pipeline_run_id}-L1",
        status=status,
        状态说明=状态说明.get(status, 状态说明[审计阻断]),
        audit_reason_type=final.audit_reason_type,
        semantic_audit_status=final.semantic_audit_status,
        validation_status="UNVALIDATED",
        human_review_required=final.human_review_required,
        decision_scope="SEMANTIC_SCREENING" if status != 审计阻断 else "AUDIT_BLOCKED",
        rule_version=gate_rule_version,
    )

    try:
        md_path, json_path, packet_path, audit_path = 写报告(result, out_dir)
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
                "audit_blockers": str(audit_path),
                "gate_results": {gate.闸门: gate.判断结果 for gate in gates},
                "failure_count": len(failure_packet),
                "status": status,
                "audit_reason_type": result.audit_reason_type,
                "semantic_audit_status": result.semantic_audit_status,
                "audit_blocker_count": len(audit_blockers),
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
