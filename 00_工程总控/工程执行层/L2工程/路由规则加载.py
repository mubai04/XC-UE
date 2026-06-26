from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from 工程异常 import 工程错误
from 退出码 import ExitCode


REQUIRED_SCHEMA = "xcue.l2-routes/1.0"
ALLOWED_STATUS = {"active"}
ALLOWED_TARGETS = {"L2-01", "L2-02", "L2-03", "L2-04", "L2-05", "L2-06", "L1.5"}


class 路由规则加载错误(工程错误):
    def __init__(self, reason: str, location: str, detail: str = "") -> None:
        message = f"L2 结构化路由规则无效：{reason} at {location}"
        super().__init__(message, ExitCode.RULE_PARSE_FAILED)
        self.reason = reason
        self.location = location
        self.details = {
            "error_code": "RULE_PARSE_FAILED",
            "rule_source": "routes.json",
            "reason": reason,
            "location": location,
            "detail": detail or message,
        }


@dataclass(frozen=True)
class 路由规则:
    rule_id: str
    version: str
    keywords: list[str]
    target: str


@dataclass(frozen=True)
class 路由规则集:
    version: str
    rules: list[路由规则]


def 加载路由规则(path: Path) -> 路由规则集:
    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise 路由规则加载错误("RULE_FILE_NOT_FOUND", "routes.json", str(exc)) from exc
    except OSError as exc:
        raise 路由规则加载错误("RULE_FILE_NOT_FOUND", "routes.json", str(exc)) from exc
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise 路由规则加载错误("RULE_ENCODING_INVALID", "routes.json", str(exc)) from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise 路由规则加载错误("RULE_JSON_INVALID", "routes.json", str(exc)) from exc

    _校验根结构(raw)
    version = _非空字符串(raw.get("version", ""), "version")
    routes = raw["routes"]
    rules = [_解析规则(item, index, version) for index, item in enumerate(routes)]
    _校验冲突(rules)
    _校验显式同优先级歧义(routes)
    return 路由规则集(version=version, rules=rules)


def _校验冲突(rules: list[路由规则]) -> None:
    seen: dict[str, str] = {}
    seen_location: dict[str, str] = {}
    for rule_index, rule in enumerate(rules):
        for keyword_index, keyword in enumerate(rule.keywords):
            existing = seen.get(keyword)
            if existing and existing != rule.target:
                raise 路由规则加载错误(
                    "RULE_DUPLICATE_CONFLICT",
                    f"routes[{rule_index}].keywords[{keyword_index}]",
                    f"{keyword} 同时指向 {existing} 与 {rule.target}；首次位置 {seen_location[keyword]}",
                )
            seen[keyword] = rule.target
            seen_location[keyword] = f"routes[{rule_index}].keywords[{keyword_index}]"


def _校验根结构(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise 路由规则加载错误("RULE_ROOT_INVALID", "routes.json", "根节点必须是 object")
    if "schema_version" not in raw:
        raise 路由规则加载错误("RULE_SCHEMA_VERSION_MISSING", "schema_version", "缺少 schema_version")
    if raw["schema_version"] != REQUIRED_SCHEMA:
        raise 路由规则加载错误(
            "RULE_SCHEMA_VERSION_UNSUPPORTED",
            "schema_version",
            f"仅支持 {REQUIRED_SCHEMA}",
        )
    if raw.get("status") not in ALLOWED_STATUS:
        raise 路由规则加载错误("RULE_STATUS_INVALID", "status", "status 必须为 active")
    if "routes" not in raw or not isinstance(raw["routes"], list) or not raw["routes"]:
        raise 路由规则加载错误("RULE_ROUTES_INVALID", "routes", "routes 必须是非空数组")


def _解析规则(raw: Any, index: int, version: str) -> 路由规则:
    location = f"routes[{index}]"
    if not isinstance(raw, dict):
        raise 路由规则加载错误("RULE_ROUTES_INVALID", location, "route 必须是 object")
    rule_id = _非空字符串(raw.get("rule_id", ""), f"{location}.rule_id")
    keywords = _关键词列表(raw.get("keywords"), f"{location}.keywords")
    target = _target(raw.get("target"), f"{location}.target")
    return 路由规则(rule_id=rule_id, version=version, keywords=keywords, target=target)


def _关键词列表(value: Any, location: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise 路由规则加载错误("RULE_KEYWORD_INVALID", location, "keywords 必须是非空字符串数组")
    keywords: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise 路由规则加载错误("RULE_KEYWORD_INVALID", f"{location}[{index}]", "keyword 必须是非空字符串")
        keywords.append(item.strip())
    return keywords


def _target(value: Any, location: str) -> str:
    if not isinstance(value, str) or value not in ALLOWED_TARGETS:
        raise 路由规则加载错误("RULE_TARGET_INVALID", location, f"target 必须属于 {sorted(ALLOWED_TARGETS)}")
    return value


def _非空字符串(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise 路由规则加载错误("RULE_ROUTES_INVALID", location, "字段必须是非空字符串")
    return value.strip()


def _校验显式同优先级歧义(routes: list[Any]) -> None:
    explicit: list[tuple[int, int, str, str]] = []
    for index, route in enumerate(routes):
        if not isinstance(route, dict) or "priority" not in route:
            continue
        priority = route["priority"]
        if not isinstance(priority, int):
            raise 路由规则加载错误("RULE_ROUTE_AMBIGUOUS", f"routes[{index}].priority", "priority 必须是整数")
        keywords = route.get("keywords", [])
        target = route.get("target", "")
        if isinstance(keywords, list) and isinstance(target, str):
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.strip():
                    explicit.append((priority, len(keyword.strip()), target, f"routes[{index}]"))
    for i, left in enumerate(explicit):
        for right in explicit[i + 1 :]:
            if left[0] == right[0] and left[1] == right[1] and left[2] != right[2]:
                raise 路由规则加载错误(
                    "RULE_ROUTE_AMBIGUOUS",
                    "routes",
                    f"同 priority={left[0]} 且同关键词长度={left[1]} 的规则指向 {left[2]} 与 {right[2]}",
                )
