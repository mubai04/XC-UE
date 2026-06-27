from __future__ import annotations

from dataclasses import dataclass

from L1决策角色 import 审计阻断角色, 内容决策角色, 硬护栏角色
from L1模型 import 检测项, 闸门结果


@dataclass(frozen=True)
class 阻断分拆结果:
    失败包: list[检测项]
    审计阻断项: list[检测项]


def _收集阻断项(gates: list[闸门结果]) -> list[检测项]:
    items: list[检测项] = []
    for gate in gates:
        for item in gate.检测项:
            if item.blocking:
                items.append(item)
    return items


def 分拆阻断项(gates: list[闸门结果]) -> 阻断分拆结果:
    failure_packet: list[检测项] = []
    audit_blockers: list[检测项] = []
    for item in _收集阻断项(gates):
        if item.decision_role == 审计阻断角色:
            audit_blockers.append(item)
        elif item.decision_role in {硬护栏角色, 内容决策角色}:
            failure_packet.append(item)
    return 阻断分拆结果(失败包=failure_packet, 审计阻断项=audit_blockers)


def 生成失败包(gates: list[闸门结果]) -> list[检测项]:
    return 分拆阻断项(gates).失败包
