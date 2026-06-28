from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_SCHEMA = "xcue.l15-routing-rules/1.0"
ALLOWED_ACTIONS = {
    "ROUTE_TO_L2",
    "RETURN_TO_L1",
    "INPUT_REQUIRED",
    "MANUAL_REVIEW",
    "BLOCKED_TECHNICAL",
}
ALLOWED_MODULES = {"L2-01", "L2-02", "L2-03", "L2-04", "L2-05", "L2-06"}


@dataclass
class L15路由条目:
    route_id: str
    source_gate: str
    failure_type: str
    route_action: str
    target_module: str | None
    repair_product: str
    return_gate: str
    reason: str


@dataclass
class L15路由规则集:
    schema_version: str
    authority: str
    scope: str
    default_unmatched_action: str
    rules_path: str
    routes: dict[tuple[str, str], L15路由条目]


class L15路由规则错误(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def L15路由规则路径(root: Path) -> Path:
    return root / "30_L1.5_路由矩阵层" / "L1.5_路由规则.json"


def 加载L15路由规则(root: Path) -> L15路由规则集:
    path = L15路由规则路径(root)
    if not path.is_file():
        raise L15路由规则错误("L15_ROUTING_RULES_MISSING", f"L1.5 路由规则文件不存在：{path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"L1.5 路由规则不可读：{path} ({exc})") from exc
    return _解析路由规则(raw, path)


def _解析路由规则(raw: Any, path: Path) -> L15路由规则集:
    if not isinstance(raw, dict):
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", "L1.5 路由规则根节点必须是对象")
    for key in ["schema_version", "authority", "scope", "default_unmatched_action", "routes"]:
        if key not in raw:
            raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"L1.5 路由规则缺少字段：{key}")
    schema_version = raw["schema_version"]
    if schema_version != REQUIRED_SCHEMA:
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"schema_version 必须为 {REQUIRED_SCHEMA}")
    if raw["authority"] != "CANONICAL":
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", "authority 必须为 CANONICAL")
    if raw["scope"] != "L1.5":
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", "scope 必须为 L1.5")
    default_action = raw["default_unmatched_action"]
    if default_action not in ALLOWED_ACTIONS:
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", "default_unmatched_action 不在允许范围")
    routes_raw = raw["routes"]
    if not isinstance(routes_raw, list) or not routes_raw:
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", "routes 必须是非空数组")

    routes: dict[tuple[str, str], L15路由条目] = {}
    route_ids: set[str] = set()
    for idx, item in enumerate(routes_raw):
        if not isinstance(item, dict):
            raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"routes[{idx}] 必须是对象")
        for key in [
            "route_id",
            "source_gate",
            "failure_type",
            "route_action",
            "target_module",
            "repair_product",
            "return_gate",
            "reason",
        ]:
            if key not in item:
                raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"routes[{idx}] 缺少字段：{key}")
        route_id = _非空字符串(item["route_id"], f"routes[{idx}].route_id")
        if route_id in route_ids:
            raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"route_id 重复：{route_id}")
        route_ids.add(route_id)
        source_gate = _非空字符串(item["source_gate"], f"routes[{idx}].source_gate")
        failure_type = _非空字符串(item["failure_type"], f"routes[{idx}].failure_type")
        route_action = _非空字符串(item["route_action"], f"routes[{idx}].route_action")
        if route_action not in ALLOWED_ACTIONS:
            raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"routes[{idx}].route_action 无效：{route_action}")
        target_module = item["target_module"]
        if route_action == "ROUTE_TO_L2":
            if not isinstance(target_module, str) or target_module not in ALLOWED_MODULES:
                raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"routes[{idx}] ROUTE_TO_L2 需要有效 target_module")
        else:
            if target_module is not None:
                raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"routes[{idx}] 非 ROUTE_TO_L2 不得带 target_module")
        key = (source_gate, failure_type)
        if key in routes:
            raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"source_gate+failure_type 重复：{source_gate}/{failure_type}")
        routes[key] = L15路由条目(
            route_id=route_id,
            source_gate=source_gate,
            failure_type=failure_type,
            route_action=route_action,
            target_module=target_module if isinstance(target_module, str) else None,
            repair_product=_非空字符串(item["repair_product"], f"routes[{idx}].repair_product"),
            return_gate=_非空字符串(item["return_gate"], f"routes[{idx}].return_gate"),
            reason=_非空字符串(item["reason"], f"routes[{idx}].reason"),
        )
    return L15路由规则集(
        schema_version=schema_version,
        authority=raw["authority"],
        scope=raw["scope"],
        default_unmatched_action=default_action,
        rules_path=str(path),
        routes=routes,
    )


def _非空字符串(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise L15路由规则错误("L15_ROUTING_RULES_INVALID", f"{label} 必须是非空字符串")
    return value.strip()
