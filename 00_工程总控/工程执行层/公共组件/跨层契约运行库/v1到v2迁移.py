from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from Schema注册表 import SCHEMA_IDS
from 对象编号 import 下一序号, 生成对象编号
from 契约校验 import (
    校验L1失败包,
    校验L15路由决策,
    校验L2修复单,
    校验L2报告,
    校验L3任务包,
    校验L3执行结果,
)
from 迁移模型 import 字段映射记录, 迁移上下文, 迁移结果
from 迁移错误 import (
    EVIDENCE_SOURCE_AMBIGUOUS,
    L1_DOMAIN_MAPPING_MISSING,
    L2_REPAIR_SEMANTICS_AMBIGUOUS,
    L3_RESULT_INCONSISTENT,
    MIGRATION_CONTEXT_REQUIRED,
    PRIMARY_FINDING_REFERENCE_MISSING,
    ROUTE_RULE_NOT_FOUND,
    UNKNOWN_STATUS,
    UNKNOWN_V1_FIELD,
    迁移错误,
)

ROOT = Path(__file__).resolve().parents[4]
ROUTING_RULES_PATH = ROOT / "30_L1.5_路由矩阵层" / "L1.5_路由规则.json"

L1_ITEM_KNOWN = {
    "闸门",
    "名称",
    "状态",
    "说明",
    "证据",
    "严重级别",
    "失败类型",
    "候选模块",
    "回流验收位置",
    "修复方向",
    "decision_role",
    "blocking",
    "routeable",
    "route_reason",
    "source_component",
    "heuristic",
    "signal_strength",
    "confidence",
    "reason_type",
}

TYPE_TO_DOMAIN: dict[str, str] = {
    "叙事失败": "叙事",
    "文风失败": "文风",
    "AI味失败": "文风",
    "角色失败": "角色",
    "创意设定失败": "设定",
    "C高：认知成本过高": "读者体验",
    "E低：即时情绪反馈弱": "读者体验",
    "V低：未来价值预期弱": "读者体验",
    "入口弱": "读者体验",
    "章末弱": "读者体验",
    "弃读点明显": "读者体验",
    "传播点弱": "读者体验",
    "付费预期弱": "读者体验",
    "技术护栏失败": "工程技术",
    "重复窗口过高": "文风",
    "高重复正文": "文风",
    "低信息重复正文": "文风",
    "字数不足": "工程技术",
    "输入不足": "工程技术",
    "系统一致性失败": "故事一致性",
    "前后事实冲突": "故事一致性",
    "章末追读弱": "发布准备",
    "认知成本过高": "读者体验",
    "字数超出默认发布体量": "发布准备",
    "当章收益不足": "发布准备",
    "功能锁失败": "发布准备",
}

GATE_TYPE_DOMAIN: dict[tuple[str, str], str] = {
    ("L1-03", "认知成本过高"): "发布准备",
    ("L1-02", "认知成本过高"): "读者体验",
    ("L1-SEM", "语义失败"): "语义审计",
}

VALID_GATES = {"L1-00", "L1-01", "L1-02", "L1-03", "L1-SEM", "L1.5", "L2", "L3"}

L15_STATUS_MAP = {
    "ROUTED": "ROUTED",
    "INPUT_REQUIRED": "INPUT_REQUIRED",
    "MANUAL_REVIEW": "MANUAL_REVIEW",
    "RETURN_TO_L1": "RETURN_TO_L1",
    "BLOCKED": "BLOCKED_TECHNICAL",
}

L2_STATUS_MAP = {
    "回原闸门复验": "READY_FOR_L3",
    "回L1.5": "RETURN_TO_L1_5",
    "进入L3": "READY_FOR_L3",
}

L3_STATUS_MAP = {
    "AWAITING_EXECUTOR": "PLANNED",
    "COMPLETED": "COMPLETED",
    "BLOCKED": "BLOCKED",
    "SCHEMA_INVALID": "FAILED",
    "CANDIDATE_FAILED": "FAILED",
}

L3_V2_EXEC_STATES = {
    "PLANNED",
    "EXECUTING",
    "CANDIDATE_WRITTEN",
    "BLOCKED",
    "FAILED",
    "COMPLETED",
}


def _fail(result: 迁移结果, code: str, msg: str = "") -> 迁移结果:
    result.迁移状态 = "FAILED"
    result.迁移错误.append(f"{code}: {msg or code}")
    return result


def _success(result: 迁移结果, warnings: list[str] | None = None) -> 迁移结果:
    if warnings:
        result.迁移警告.extend(warnings)
        result.迁移状态 = "SUCCESS_WITH_WARNINGS"
    else:
        result.迁移状态 = "SUCCESS"
    return result


def _回流闸门(gate: str) -> dict[str, str]:
    g = gate if gate in VALID_GATES else "L1-01"
    if g == "L1.5":
        g = "L1.5"
    return {"回流闸门": g}


def _映射L1问题域(来源闸门: str, 失败类型: str) -> str:
    key = (来源闸门, 失败类型)
    if key in GATE_TYPE_DOMAIN:
        return GATE_TYPE_DOMAIN[key]
    if 失败类型 in TYPE_TO_DOMAIN:
        return TYPE_TO_DOMAIN[失败类型]
    raise 迁移错误(L1_DOMAIN_MAPPING_MISSING, f"{来源闸门}/{失败类型}")


def _证据来源类型(scope: str, ctx: 迁移上下文) -> str:
    mapping = {
        "CURRENT_CHAPTER": "CHAPTER",
        "PRIOR_CHAPTER": "PRIOR_CHAPTER",
        "IR": "IR",
    }
    if scope in mapping:
        return mapping[scope]
    return ctx.默认证据来源


def _迁移证据列表(
    items: list[dict],
    ctx: 迁移上下文,
    *,
    用途: str,
    计数: dict[str, int],
) -> list[dict]:
    ctx.要求("chapter_path")
    refs: list[dict] = []
    for raw in items or []:
        scope = raw.get("source_scope", "")
        source_type = _证据来源类型(scope, ctx)
        path = ctx.chapter_path
        if source_type == "PRIOR_CHAPTER" and not raw.get("来源路径"):
            if ctx.chapter_path.count("/") > 0:
                path = str(Path(ctx.chapter_path).parent / "prior.md")
            else:
                raise 迁移错误(EVIDENCE_SOURCE_AMBIGUOUS, "前序章节证据缺少来源路径")
        elif source_type == "IR":
            path = raw.get("来源路径") or raw.get("path") or ""
            if not path:
                raise 迁移错误(EVIDENCE_SOURCE_AMBIGUOUS, "IR 证据缺少来源路径")
        seq = 下一序号(计数, "证据")
        para = raw.get("段落")
        line_start = para if isinstance(para, int) else 1
        refs.append(
            {
                "证据编号": 生成对象编号("证据", ctx.pipeline_run_id, seq),
                "来源类型": source_type,
                "来源路径": path,
                "段落编号": para if isinstance(para, int) else None,
                "行号范围": {"起始行": line_start, "结束行": line_start + 3},
                "逐字摘句": raw.get("摘句", ""),
                "证据用途": 用途,
            }
        )
    return refs


def _发现键(item: dict, index: int) -> str:
    return f"{item.get('闸门', '')}|{item.get('失败类型', '')}|{index}"


def _加载路由规则() -> tuple[dict[tuple[str, str], dict], str]:
    raw = json.loads(ROUTING_RULES_PATH.read_text(encoding="utf-8-sig"))
    table: dict[tuple[str, str], dict] = {}
    for route in raw.get("routes", []):
        table[(route["source_gate"], route["failure_type"])] = route
    return table, raw.get("schema_version", "")


def 迁移L1失败包(v1: dict[str, Any], ctx: 迁移上下文) -> 迁移结果:
    result = 迁移结果(
        迁移状态="FAILED",
        来源对象类型="L1_FAILURE_PACKET_V1",
        目标Schema编号=SCHEMA_IDS["l1-failure-packet/v2"],
    )
    ctx.要求("pipeline_run_id", "chapter_path")
    known_top = {
        "schema_version",
        "pipeline_run_id",
        "stage_run_id",
        "status",
        "failure_count",
        "blocking_count",
        "routeable_count",
        "items",
        "extensions",
    }
    for key in v1:
        if key not in known_top:
            return _fail(result, UNKNOWN_V1_FIELD, key)

    items_v1 = v1.get("items") or []
    findings: list[dict] = []
    计数 = ctx._序号计数

    for idx, item in enumerate(items_v1, start=1):
        for key in item:
            if key not in L1_ITEM_KNOWN:
                return _fail(result, UNKNOWN_V1_FIELD, f"items[].{key}")
        if "routeable" not in item:
            return _fail(result, MIGRATION_CONTEXT_REQUIRED, "items 缺少 routeable")

        gate = item.get("闸门", "")
        ftype = item.get("失败类型", "")
        try:
            domain = _映射L1问题域(gate, ftype)
        except 迁移错误 as exc:
            return _fail(result, exc.code, exc.message)

        seq = 下一序号(计数, "L1发现")
        fid = 生成对象编号("L1发现", ctx.pipeline_run_id, seq)
        ctx.注册发现(_发现键(item, idx), fid)

        finding = {
            "schema_version": "xcue.l1-finding/2.0",
            "L1发现编号": fid,
            "来源闸门": gate,
            "来源组件": item.get("source_component") or gate,
            "发现名称": item.get("名称", ""),
            "发现状态": item.get("状态", "失败"),
            "L1问题域": domain,
            "L1失败类型": ftype,
            "说明": item.get("说明", ""),
            "证据引用": _迁移证据列表(item.get("证据") or [], ctx, 用途="SCREENING", 计数=计数),
            "严重级别": item.get("严重级别", "error"),
            "decision_role": item.get("decision_role", "DIAGNOSTIC"),
            "blocking": bool(item.get("blocking", False)),
            "routeable": bool(item.get("routeable")),
            "route_reason": item.get("route_reason", ""),
            "候选模块提示": item.get("候选模块", ""),
            "修复提示": item.get("修复方向", ""),
            "回流闸门": _回流闸门(item.get("回流验收位置") or gate),
        }
        if item.get("reason_type"):
            finding["reason_type"] = item["reason_type"]
        findings.append(finding)

    seq_p = 下一序号(计数, "L1失败包")
    packet_id = 生成对象编号("L1失败包", ctx.pipeline_run_id, seq_p)
    ctx.L1失败包编号 = packet_id

    ext = v1.get("extensions") or {}
    chapter = ext.get("chapter_path") or ctx.chapter_path

    v2 = {
        "schema_version": "xcue.l1-failure-packet/2.0",
        "L1失败包编号": packet_id,
        "pipeline_run_id": v1.get("pipeline_run_id", ctx.pipeline_run_id),
        "stage_run_id": v1.get("stage_run_id", ""),
        "L1顶层状态": v1.get("status", "SCREENING_REJECT"),
        "failure_count": v1.get("failure_count", len(findings)),
        "blocking_count": v1.get("blocking_count", 0),
        "routeable_count": v1.get("routeable_count", 0),
        "发现项列表": findings,
        "章节路径": chapter,
        "publish_authority": False,
    }
    result.旧字段到新字段映射 = [
        字段映射记录("status", "L1顶层状态"),
        字段映射记录("items", "发现项列表"),
        字段映射记录("失败类型", "L1失败类型"),
        字段映射记录("修复方向", "修复提示"),
        字段映射记录("候选模块", "候选模块提示"),
    ]
    try:
        校验L1失败包(v2)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)
    result.目标对象 = v2
    return _success(result)


def _解析主发现编号(primary: dict, ctx: 迁移上下文) -> str:
    gate = primary.get("闸门", "")
    ftype = primary.get("失败类型", "")
    for key, fid in ctx.L1发现编号映射.items():
        parts = key.split("|")
        if len(parts) >= 2 and parts[0] == gate and parts[1] == ftype:
            return fid
    raise 迁移错误(PRIMARY_FINDING_REFERENCE_MISSING, f"{gate}/{ftype}")


def 迁移L15路由报告(v1: dict[str, Any], ctx: 迁移上下文) -> 迁移结果:
    result = 迁移结果(
        迁移状态="FAILED",
        来源对象类型="L15_ROUTE_REPORT_V1",
        目标Schema编号=SCHEMA_IDS["l15-route-decision/v2"],
    )
    ctx.要求("pipeline_run_id", "L1失败包编号")
    if "primary_failure" not in v1:
        return _fail(result, PRIMARY_FINDING_REFERENCE_MISSING, "缺少 primary_failure")

    primary = v1["primary_failure"]
    if not isinstance(primary, dict):
        return _fail(result, PRIMARY_FINDING_REFERENCE_MISSING, "primary_failure 非对象")

    try:
        main_fid = _解析主发现编号(primary, ctx)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)

    route_table, rules_schema_version = _加载路由规则()
    gate = primary.get("闸门", "")
    ftype = primary.get("失败类型", "")
    route = route_table.get((gate, ftype))
    if not route:
        return _fail(result, ROUTE_RULE_NOT_FOUND, f"{gate}/{ftype}")
    route_id = route["route_id"]

    final = v1.get("final_status", "")
    if final not in L15_STATUS_MAP:
        return _fail(result, UNKNOWN_STATUS, final)
    route_status = L15_STATUS_MAP[final]

    target = v1.get("target_module", "") if route_status == "ROUTED" else ""
    if route_status != "ROUTED" and target:
        target = ""

    secondary_refs = []
    for sec in v1.get("secondary_failures") or []:
        try:
            fid = _解析主发现编号(sec, ctx)
            secondary_refs.append({"对象类型": "L1发现项", "对象编号": fid})
        except 迁移错误:
            result.迁移警告.append(f"次级发现无法解析：{sec.get('失败类型', '')}")

    seq = 下一序号(ctx._序号计数, "L1.5路由")
    rid = 生成对象编号("L1.5路由", ctx.pipeline_run_id, seq)
    ctx.L1_5路由决策编号 = rid
    ctx.主发现编号 = main_fid
    v2: dict[str, Any] = {
        "schema_version": "xcue.l15-route-decision/2.0",
        "L1_5路由决策编号": rid,
        "来源失败包编号": ctx.L1失败包编号,
        "主发现引用": {"对象类型": "L1发现项", "对象编号": main_fid},
        "次级发现引用": secondary_refs,
        "路由规则编号": route_id,
        "路由动作": route.get("route_action", "ROUTE_TO_L2"),
        "修复产物类型": v1.get("repair_product", route.get("repair_product", "")),
        "回流闸门": _回流闸门(v1.get("return_gate") or gate),
        "路由原因": v1.get("routing_basis", route.get("reason", "")),
        "路由状态": route_status,
        "路由规则来源": {
            "来源路径": "30_L1.5_路由矩阵层/L1.5_路由规则.json",
            "规则版本": rules_schema_version,
            "路由规则编号": route_id,
        },
    }
    if route_status == "ROUTED":
        v2["目标模块"] = target or route.get("target_module", "")
    else:
        v2["目标模块"] = ""
    if v1.get("blockers"):
        v2["blockers"] = v1["blockers"]
    if route_status == "MANUAL_REVIEW":
        v2["人工复核原因"] = "; ".join(v1.get("blockers") or [])

    consumed = [k for k in ("primary_failure", "secondary_failures", "final_status", "target_module") if k in v1]
    result.已消费但不保留的旧字段 = consumed
    try:
        校验L15路由决策(v2)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)
    result.目标对象 = v2
    return _success(result)


def _拆分L2修复语义(v1: dict) -> tuple[list[str], list[str], list[str], str]:
    修复动作_raw = v1.get("修复动作", "")
    标准动作 = v1.get("标准动作") or []
    规则依据 = v1.get("规则依据", "")
    修复产物 = v1.get("修复产物", "")
    标准验收 = v1.get("标准验收") or []

    actions: list[str] = []
    if 标准动作:
        actions = list(标准动作)
    elif isinstance(修复动作_raw, str) and 修复动作_raw.strip():
        if "\n" in 修复动作_raw:
            actions = [line.strip() for line in 修复动作_raw.splitlines() if line.strip()]
        else:
            actions = [修复动作_raw.strip()]

    rules: list[str] = []
    if 规则依据:
        rules = [规则依据] if isinstance(规则依据, str) else list(规则依据)

    acceptance = []
    if 标准验收:
        acceptance = list(标准验收)
    elif v1.get("验收问题"):
        acceptance = [v1["验收问题"]]

    product = 修复产物 or v1.get("修复单类型", "")

    if not actions and not rules and not product:
        raise 迁移错误(L2_REPAIR_SEMANTICS_AMBIGUOUS, "修复语义全部为空")
    if actions and product and len(actions) == 1 and actions[0] == product and not rules:
        raise 迁移错误(L2_REPAIR_SEMANTICS_AMBIGUOUS, "修复动作与修复产物无法区分")
    if isinstance(修复动作_raw, str) and 修复动作_raw == 修复产物 and 标准动作 and 规则依据:
        if 修复动作_raw.strip() and 修复动作_raw == 规则依据:
            raise 迁移错误(L2_REPAIR_SEMANTICS_AMBIGUOUS, "混合文本无法拆分")

    return rules, actions, acceptance, product


def 迁移L2修复单(v1: dict[str, Any], ctx: 迁移上下文, *, index: int = 1) -> 迁移结果:
    result = 迁移结果(
        迁移状态="FAILED",
        来源对象类型="L2_FIX_FORM_V1",
        目标Schema编号=SCHEMA_IDS["l2-fix-form/v2"],
    )
    ctx.要求("pipeline_run_id", "L1_5路由决策编号", "chapter_path")

    known = {
        "修复单类型", "来源闸门", "接收模块", "输入问题", "主失败类型", "次失败类型",
        "修复动作", "修复产物", "验收问题", "回流位置", "是否需要其他L2辅助",
        "是否需要回L15重路由", "最终状态", "rule_id", "rule_version", "标准来源",
        "规则编号", "规则依据", "标准动作", "标准验收", "诊断证据",
    }
    for key in v1:
        if key not in known:
            return _fail(result, UNKNOWN_V1_FIELD, key)

    try:
        rules, actions, acceptance, product = _拆分L2修复语义(v1)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)

    gate = v1.get("来源闸门", "L1-01")
    ftype = v1.get("主失败类型", "")
    finding_id = ctx.主发现编号
    if not finding_id:
        finding_id = ctx.查找发现(f"{gate}|{ftype}|1")
    if not finding_id:
        for key, fid in ctx.L1发现编号映射.items():
            if key.startswith(f"{gate}|"):
                finding_id = fid
                break
    if not finding_id:
        return _fail(result, PRIMARY_FINDING_REFERENCE_MISSING, ftype)

    final = v1.get("最终状态", "")
    if final not in L2_STATUS_MAP:
        return _fail(result, UNKNOWN_STATUS, final)

    seq = 下一序号(ctx._序号计数, "L2修复单")
    fid = 生成对象编号("L2修复单", ctx.pipeline_run_id, seq)
    ctx.L2修复单编号列表.append(fid)

    reroute = v1.get("是否需要回L15重路由") == "是"
    evidence_src = v1.get("诊断证据") or []
    if evidence_src:
        ev_refs = _迁移证据列表(evidence_src, ctx, 用途="DIAGNOSIS", 计数=ctx._序号计数)
    else:
        ev_refs = []

    ability_path = v1.get("标准来源") or f"40_L2_正式能力层/{v1.get('接收模块', 'L2-02')}_能力/ability_rules.json"
    v2 = {
        "schema_version": "xcue.l2-fix-form/2.0",
        "L2修复单编号": fid,
        "来源路由决策编号": ctx.L1_5路由决策编号,
        "来源发现引用": {"对象类型": "L1发现项", "对象编号": finding_id},
        "接收模块": v1.get("接收模块", ""),
        "模块内主问题": v1.get("主失败类型", ""),
        "模块内次级问题": [v1["次失败类型"]] if v1.get("次失败类型") else [],
        "根因": v1.get("规则依据") or v1.get("输入问题", ""),
        "诊断证据引用": ev_refs,
        "修复规则": rules,
        "修复动作": actions,
        "修复产物类型": product,
        "禁止修改范围": [],
        "必须保留内容": [],
        "验收条件": acceptance,
        "回流闸门": _回流闸门(v1.get("回流位置") or gate),
        "重路由请求": {
            "是否请求重路由": reroute,
            "请求原因": "L1.5 重路由" if reroute else "",
            "建议问题域": "",
            "禁止直接指定新目标模块": True,
        },
        "修复单状态": L2_STATUS_MAP[final],
        "能力规则来源": {
            "来源路径": ability_path if "ability_rules" in ability_path else f"40_L2_正式能力层/{v1.get('接收模块')}/ability_rules.json",
            "规则版本": v1.get("rule_version", ""),
            "规则编号": v1.get("rule_id") or v1.get("规则编号", ""),
        },
    }
    try:
        校验L2修复单(v2)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)
    result.目标对象 = v2
    return _success(result)


def 迁移L2报告(v1: dict[str, Any], ctx: 迁移上下文) -> 迁移结果:
    result = 迁移结果(
        迁移状态="FAILED",
        来源对象类型="L2_REPORT_V1",
        目标Schema编号=SCHEMA_IDS["l2-report/v2"],
    )
    ctx.要求("pipeline_run_id", "L1_5路由决策编号")
    forms_v2 = []
    for idx, form in enumerate(v1.get("修复单") or [], start=1):
        sub = 迁移L2修复单(form, ctx, index=idx)
        if sub.迁移状态 == "FAILED":
            result.迁移错误.extend(sub.迁移错误)
            return result
        forms_v2.append(sub.目标对象)

    seq = 下一序号(ctx._序号计数, "L2报告")
    rid = 生成对象编号("L2报告", ctx.pipeline_run_id, seq)
    ctx.L2报告编号 = rid

    l2_status = v1.get("status", "COMPLETED")
    v2 = {
        "schema_version": "xcue.l2-report/2.0",
        "L2报告编号": rid,
        "pipeline_run_id": v1.get("pipeline_run_id", ctx.pipeline_run_id),
        "stage_run_id": v1.get("stage_run_id", ""),
        "L2报告状态": l2_status,
        "来源路由决策编号": ctx.L1_5路由决策编号,
        "修复单列表": forms_v2,
        "阻断项": [str(x) for x in v1.get("阻断项") or []],
        "方法声明": v1.get("方法声明", ""),
    }
    try:
        校验L2报告(v2)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)
    result.目标对象 = v2
    return _success(result)


def 迁移L3任务包(v1: dict[str, Any], ctx: 迁移上下文) -> 迁移结果:
    result = 迁移结果(
        迁移状态="FAILED",
        来源对象类型="L3_TASK_BUNDLE_V1",
        目标Schema编号=SCHEMA_IDS["l3-task-bundle/v2"],
    )
    ctx.要求("pipeline_run_id", "L2报告编号", "chapter_path")
    if not ctx.L2修复单编号列表:
        return _fail(result, MIGRATION_CONTEXT_REQUIRED, "L2修复单编号")

    exec_mode = v1.get("execution_mode", "TASK_PLANNING_ONLY")
    v1_status = v1.get("status", "")
    if v1_status in ("TASK_PLANNING_ONLY", "CANDIDATE_GENERATION"):
        return _fail(result, UNKNOWN_STATUS, "status 与 execution_mode 混用")

    exec_state = L3_STATUS_MAP.get(v1_status)
    if not exec_state:
        return _fail(result, UNKNOWN_STATUS, v1_status)

    fix_id = ctx.L2修复单编号列表[0]
    tasks = []
    for t in v1.get("任务单") or []:
        seq = 下一序号(ctx._序号计数, "任务")
        tasks.append(
            {
                "任务编号": 生成对象编号("任务", ctx.pipeline_run_id, seq),
                "任务描述": t.get("修复方向") or t.get("任务类型", ""),
                "关联修复单编号": fix_id,
            }
        )
    if not tasks:
        seq = 下一序号(ctx._序号计数, "任务")
        tasks.append(
            {
                "任务编号": 生成对象编号("任务", ctx.pipeline_run_id, seq),
                "任务描述": "迁移默认任务",
                "关联修复单编号": fix_id,
            }
        )

    allow: list[str] = []
    deny: list[str] = []
    candidates: list[str] = []
    for t in v1.get("任务单") or []:
        if t.get("目标文件"):
            candidates.append(t["目标文件"])
            allow.append(t["目标文件"])
        if t.get("禁止修改文件"):
            deny.append(t["禁止修改文件"])

    chapter = ctx.chapter_path
    for path in candidates:
        if path == chapter or path.endswith("/" + Path(chapter).name):
            return _fail(result, L3_RESULT_INCONSISTENT, "候选路径指向正式章节")

    seq = 下一序号(ctx._序号计数, "L3任务包")
    tid = 生成对象编号("L3任务包", ctx.pipeline_run_id, seq)
    ctx.L3执行任务包编号 = tid

    v2 = {
        "schema_version": "xcue.l3-task-bundle/2.0",
        "L3执行任务包编号": tid,
        "来源L2报告编号": ctx.L2报告编号,
        "来源修复单编号": fix_id,
        "执行模式": exec_mode if exec_mode in ("TASK_PLANNING_ONLY", "CANDIDATE_GENERATION") else "TASK_PLANNING_ONLY",
        "任务列表": tasks,
        "允许写入范围": allow or ["candidates/"],
        "禁止写入范围": deny or [chapter],
        "候选输出路径": candidates or ["candidates/patch.md"],
        "正式正文保护": {"正式正文路径": chapter, "允许修改": False},
        "复验入口": _回流闸门("L1-01"),
        "执行状态": exec_state,
    }
    try:
        校验L3任务包(v2)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)
    result.目标对象 = v2
    return _success(result)


def 迁移L3执行结果(v1: dict[str, Any], ctx: 迁移上下文) -> 迁移结果:
    result = 迁移结果(
        迁移状态="FAILED",
        来源对象类型="L3_EXECUTION_RESULT_V1",
        目标Schema编号=SCHEMA_IDS["l3-execution-result/v2"],
    )
    ctx.要求("pipeline_run_id", "L3执行任务包编号", "chapter_path")
    if not ctx.L2修复单编号列表:
        return _fail(result, MIGRATION_CONTEXT_REQUIRED, "L2修复单编号")

    raw_status = v1.get("执行状态") or v1.get("status", "")
    if raw_status in L3_V2_EXEC_STATES:
        exec_state = raw_status
    else:
        exec_state = L3_STATUS_MAP.get(raw_status)
    if not exec_state:
        if raw_status in ("TASK_PLANNING_ONLY", "CANDIDATE_GENERATION"):
            return _fail(result, UNKNOWN_STATUS, "执行模式误作执行状态")
        return _fail(result, UNKNOWN_STATUS, raw_status)

    outputs = v1.get("候选产物") or v1.get("candidate_outputs") or []
    if not outputs and v1.get("要求候选产物"):
        return _fail(result, L3_RESULT_INCONSISTENT, "声明有候选但未提供列表")

    fix_id = ctx.L2修复单编号列表[0]
    artifacts = []
    for idx, out in enumerate(outputs, start=1):
        if isinstance(out, str):
            path = out
            exists = True
        else:
            path = out.get("相对路径") or out.get("path", "")
            exists = bool(out.get("是否存在", True))
            ref = out.get("来源修复单编号", "")
            if ref in ("", "PLACEHOLDER"):
                if len(ctx.L2修复单编号列表) != 1:
                    return _fail(result, L3_RESULT_INCONSISTENT, "候选产物缺少修复单引用")
                ref = ctx.L2修复单编号列表[0]
            fix_id = ref
        seq = 下一序号(ctx._序号计数, "产物")
        artifacts.append(
            {
                "产物编号": 生成对象编号("产物", ctx.pipeline_run_id, seq),
                "来源修复单编号": fix_id,
                "相对路径": path,
                "产物类型": "候选正文补丁",
                "是否存在": exists,
                "是否修改正式正文": False,
            }
        )

    seq = 下一序号(ctx._序号计数, "L3执行结果")
    oid = 生成对象编号("L3执行结果", ctx.pipeline_run_id, seq)

    v2 = {
        "schema_version": "xcue.l3-execution-result/2.0",
        "L3执行结果编号": oid,
        "来源执行任务包编号": ctx.L3执行任务包编号,
        "执行状态": exec_state,
        "候选产物列表": artifacts,
        "未执行任务": [],
        "错误列表": list(v1.get("错误列表") or []),
        "正式正文是否修改": bool(v1.get("正式正文是否修改", False)),
        "复验入口": _回流闸门("L1-01"),
        "回流状态": v1.get("回流状态", "AWAITING_L1"),
    }
    try:
        校验L3执行结果(v2)
    except 迁移错误 as exc:
        return _fail(result, exc.code, exc.message)
    result.目标对象 = v2
    return _success(result)


def 迁移完整链路(
    *,
    l1_packet: dict,
    l15_report: dict,
    l2_report: dict,
    l3_task: dict,
    l3_result: dict | None,
    ctx: 迁移上下文,
) -> list[迁移结果]:
    results: list[迁移结果] = []
    for label, fn, arg in (
        ("L1", 迁移L1失败包, l1_packet),
        ("L1.5", 迁移L15路由报告, l15_report),
        ("L2", 迁移L2报告, l2_report),
        ("L3", 迁移L3任务包, l3_task),
    ):
        r = fn(arg, ctx)
        results.append(r)
        if r.迁移状态 == "FAILED":
            return results
    if l3_result is not None:
        r = 迁移L3执行结果(l3_result, ctx)
        results.append(r)
    return results
