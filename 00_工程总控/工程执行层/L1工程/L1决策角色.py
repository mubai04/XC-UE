from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from L1模型 import 检测项, 闸门结果
from 退出码 import ExitCode
from 运行状态 import 审计阻断, 机器初筛通过, 机器初筛退回, SCREENING_REVIEW

诊断角色 = "DIAGNOSTIC"
硬护栏角色 = "HARD_GUARD"
内容决策角色 = "CONTENT_DECISION"
审计阻断角色 = "AUDIT_BLOCKER"

诊断闸门判断 = "HEURISTIC_DIAGNOSTIC"

理由_输入无效 = "INPUT_INVALID"
理由_API不可用 = "API_UNAVAILABLE"
理由_证据无效 = "EVIDENCE_INVALID"
理由_Schema无效 = "SCHEMA_INVALID"

角色权限说明: dict[str, str] = {
    硬护栏角色: "确定性输入、工程或最低质量阻断；可影响 L1 终态；是否进入 L1.5 路由由 routeable 决定",
    内容决策角色: "L1-SEM 全章内容结论；影响 L1 终态；routeable=true 时进入修复路由候选",
    诊断角色: "L1-01/02/03 诊断信号；不单独决定终态；routeable=true 时可进入 L1.5 候选",
    审计阻断角色: "API/证据/协议无效；终态 AUDIT_BLOCKED；不得进入内容路由",
}


@dataclass(frozen=True)
class 终态结果:
    status: str
    exit_code: ExitCode
    audit_reason_type: str = ""
    semantic_audit_status: str = ""
    human_review_required: bool = True


class 语义审计可读(Protocol):
    可用: bool
    整体结论: str


def 标记诊断项(item: 检测项) -> 检测项:
    item.decision_role = 诊断角色
    item.blocking = False
    item.heuristic = True
    item.reason_type = ""
    item.source_component = item.闸门
    if item.失败类型 and item.严重级别 in {"error", "warning"}:
        item.routeable = True
        item.route_reason = "为L1.5提供领域路由线索"
    else:
        item.routeable = False
        item.route_reason = ""
    if item.状态 in {"失败", "风险", "阻断"}:
        item.状态 = "检测到代理信号"
    return item


def 完成诊断闸门(gate: 闸门结果) -> 闸门结果:
    gate.检测项 = [标记诊断项(item) for item in gate.检测项]
    gate.判断结果 = 诊断闸门判断
    gate.最终状态 = 诊断闸门判断
    gate.失败类型 = []
    gate.失败位置 = []
    gate.是否进入L15 = "否"
    gate.调用方向 = []
    return gate


def 收集检测项(gates: list[闸门结果]) -> list[检测项]:
    items: list[检测项] = []
    for gate in gates:
        items.extend(gate.检测项)
    return items


def _语义层状态(semantic: 语义审计可读, audit_blockers: list[检测项]) -> tuple[str, str]:
    if audit_blockers or not semantic.可用:
        reason = audit_blockers[0].reason_type if audit_blockers else (
            理由_API不可用 if semantic.整体结论 == "UNAVAILABLE" else 理由_证据无效
        )
        return 审计阻断, reason
    return semantic.整体结论, ""


def 聚合终态(
    semantic: 语义审计可读,
    gate_items: list[检测项],
    audit_blockers: list[检测项],
) -> 终态结果:
    semantic_audit_status, audit_reason = _语义层状态(semantic, audit_blockers)
    has_audit_issue = semantic_audit_status == 审计阻断

    hard_guards = [i for i in gate_items if i.decision_role == 硬护栏角色 and i.blocking]
    if hard_guards:
        return 终态结果(
            机器初筛退回,
            ExitCode.GATE_REJECTED,
            audit_reason if has_audit_issue else "",
            semantic_audit_status,
            True,
        )

    if audit_blockers or has_audit_issue:
        return 终态结果(审计阻断, ExitCode.BLOCKED, audit_reason, 审计阻断, True)

    content_items = [i for i in gate_items if i.decision_role == 内容决策角色]
    if semantic.整体结论 == "FAIL" or any(i.严重级别 == "error" for i in content_items):
        return 终态结果(机器初筛退回, ExitCode.GATE_REJECTED, "", semantic_audit_status, True)

    if semantic.整体结论 == "REVIEW" or any(i.严重级别 == "warning" for i in content_items):
        return 终态结果(SCREENING_REVIEW, ExitCode.REVIEW_REQUIRED, "", semantic_audit_status, True)

    if semantic.可用 and semantic.整体结论 == "PASS":
        return 终态结果(机器初筛通过, ExitCode.OK, "", "PASS", True)

    return 终态结果(审计阻断, ExitCode.BLOCKED, 理由_证据无效, 审计阻断, True)
