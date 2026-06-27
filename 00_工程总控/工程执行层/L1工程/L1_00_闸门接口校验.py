from __future__ import annotations

from L1决策角色 import (
    完成诊断闸门,
    标记诊断项,
    审计阻断角色,
    理由_Schema无效,
    理由_输入无效,
    诊断闸门判断,
)
from L1模型 import 检测项, 闸门结果


REQUIRED_FIELDS = [
    "闸门",
    "判断结果",
    "输入材料",
    "失败类型",
    "失败位置",
    "是否进入L15",
    "调用方向",
    "回流验收位置",
    "最终状态",
]


def _审计阻断项(名称: str, 说明: str, *, reason_type: str, failure_type: str = "输入不足") -> 检测项:
    return 检测项(
        "L1-00",
        名称,
        "失败",
        说明,
        [],
        "error",
        failure_type,
        候选模块="回L1-00",
        回流验收位置="L1-00",
        修复方向="修正 L1 输入上下文或闸门输出结构",
        heuristic=False,
        decision_role=审计阻断角色,
        blocking=True,
        reason_type=reason_type,
    )


def 检测(gates: list[闸门结果]) -> 闸门结果:
    items: list[检测项] = []

    bad_fields = []
    for gate in gates:
        for field in REQUIRED_FIELDS:
            if not hasattr(gate, field):
                bad_fields.append(f"{gate.闸门}.{field}")
    if bad_fields:
        items.append(
            _审计阻断项(
                "统一输出格式",
                "闸门输出缺少 L1-00 要求字段：" + "、".join(bad_fields),
                reason_type=理由_输入无效,
            )
        )
    else:
        items.append(
            标记诊断项(
                检测项("L1-00", "统一输出格式", "检测到接口信号", "L1-01/L1-02/L1-03 输出字段符合 L1-00 接口。")
            )
        )

    route_errors = []
    for gate in gates:
        has_failure = bool(gate.失败类型)
        if has_failure and gate.是否进入L15 != "是":
            route_errors.append(f"{gate.闸门} 有失败类型但未进入 L1.5")
        if (not has_failure) and gate.是否进入L15 == "是":
            route_errors.append(f"{gate.闸门} 无失败类型但进入 L1.5")
    if route_errors:
        items.append(
            _审计阻断项(
                "L1.5交接条件",
                "；".join(route_errors),
                reason_type=理由_Schema无效,
                failure_type="技术护栏失败",
            )
        )
    else:
        items.append(
            标记诊断项(
                检测项("L1-00", "L1.5交接条件", "检测到接口信号", "失败闸门进入 L1.5，非失败闸门不强行派单。")
            )
        )

    blockers = [item for item in items if item.blocking]
    if blockers:
        result = "需要补输入"
    else:
        result = 诊断闸门判断
    return 闸门结果(
        闸门="L1-00",
        判断结果=result,
        输入材料=["L1-01/L1-02/L1-03闸门输出", "结构化 gate_rules.json 校验结果"],
        失败类型=[item.失败类型 for item in blockers if item.失败类型],
        失败位置=[],
        是否进入L15="否",
        调用方向=[],
        回流验收位置="L1-00",
        最终状态=result,
        检测项=items,
        规则摘要={"必填字段": REQUIRED_FIELDS},
    )
