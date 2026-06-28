from __future__ import annotations

from dataclasses import dataclass

from L1决策角色 import 审计阻断角色, 内容决策角色, 硬护栏角色, 诊断角色
from L1模型 import 检测项, 闸门结果
from 运行状态 import 审计阻断, 机器初筛通过, SCREENING_REVIEW

HARD_GUARD_ROUTEABLE: dict[str, bool] = {
    "重复窗口过高": True,
    "高重复正文": True,
    "低信息重复正文": True,
    "字数不足": False,
}


@dataclass(frozen=True)
class 阻断分拆结果:
    失败包: list[检测项]
    审计阻断项: list[检测项]


def 收集全部检测项(gates: list[闸门结果]) -> list[检测项]:
    items: list[检测项] = []
    for gate in gates:
        items.extend(gate.检测项)
    return items


def _应用硬护栏路由语义(item: 检测项) -> None:
    if item.decision_role != 硬护栏角色:
        return
    routeable = HARD_GUARD_ROUTEABLE.get(item.失败类型, False)
    item.routeable = routeable
    item.source_component = item.source_component or item.闸门
    if routeable:
        item.route_reason = "正文质量护栏问题可供 L1.5 路由"
    elif item.失败类型 == "字数不足":
        item.route_reason = "字数不足需补齐输入，不直接派单 L2"
    else:
        item.route_reason = ""


def 构建失败包(items: list[检测项], screening_status: str) -> list[检测项]:
    if screening_status in {机器初筛通过, 审计阻断}:
        return []

    packet: list[检测项] = []
    for item in items:
        if item.decision_role == 审计阻断角色:
            continue
        if item.decision_role == 硬护栏角色:
            _应用硬护栏路由语义(item)
            if item.routeable or item.blocking:
                packet.append(item)
            continue
        if item.decision_role == 内容决策角色:
            item.routeable = True
            item.route_reason = item.route_reason or "L1-SEM 内容结论需修复"
            item.source_component = item.source_component or "L1-SEM"
            packet.append(item)
            continue
        if item.decision_role == 诊断角色 and item.routeable:
            packet.append(item)
    return packet


def 分拆阻断项(gates: list[闸门结果], screening_status: str) -> 阻断分拆结果:
    all_items = 收集全部检测项(gates)
    audit_blockers = [item for item in all_items if item.decision_role == 审计阻断角色]
    failure_packet = 构建失败包(all_items, screening_status)
    return 阻断分拆结果(失败包=failure_packet, 审计阻断项=audit_blockers)


def 生成失败包(gates: list[闸门结果], screening_status: str) -> list[检测项]:
    return 分拆阻断项(gates, screening_status).失败包
