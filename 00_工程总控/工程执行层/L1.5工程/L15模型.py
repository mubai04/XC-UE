from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class 失败快照:
    闸门: str
    名称: str
    失败类型: str
    说明: str
    状态: str = "失败"
    严重级别: str = "error"
    候选模块: str = ""
    回流验收位置: str = ""
    修复方向: str = ""
    证据: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class L15路由报告:
    run_id: str
    pipeline_run_id: str
    stage_run_id: str
    source_failure_packet: str
    primary_failure: 失败快照
    secondary_failures: list[失败快照]
    target_module: str
    repair_product: str
    return_gate: str
    route_rule_id: str
    route_rule_version: str
    final_status: str
    blockers: list[str]
    routing_basis: str = ""
    schema_version: str = "xcue.l15-route-report/1.0"
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["primary_failure"] = self.primary_failure.to_dict()
        payload["secondary_failures"] = [item.to_dict() for item in self.secondary_failures]
        return payload
