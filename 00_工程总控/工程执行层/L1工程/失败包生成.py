from __future__ import annotations

from L1模型 import 检测项, 闸门结果


def 生成失败包(gates: list[闸门结果]) -> list[检测项]:
    packet: list[检测项] = []
    for gate in gates:
        for item in gate.检测项:
            if item.严重级别 in {"error", "warning"}:
                packet.append(item)
    return packet
