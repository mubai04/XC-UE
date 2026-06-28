from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from 工程异常 import 工程错误
from 退出码 import ExitCode
from 闸门标准解析 import L101规则, L102规则, L103规则, L1规则


REQUIRED_SCHEMA = "xcue.l1-gate-rules/1.0"
REQUIRED_GATES = {"L1-01", "L1-02", "L1-03"}


class 闸门规则加载错误(工程错误):
    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.RULE_PARSE_FAILED)


def L1闸门规则路径(root: Path) -> Path:
    return root / "00_工程总控" / "工程执行层" / "L1工程" / "gate_rules.json"


def 加载闸门规则(path: Path) -> L1规则:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise 闸门规则加载错误(f"L1 结构化闸门规则不可读：{path}") from exc
    try:
        raw = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise 闸门规则加载错误(f"L1 结构化闸门规则解析失败：{path}") from exc

    _校验根结构(raw)
    gates = raw["gates"]
    return L1规则(
        L101=_解析L101(gates["L1-01"]),
        L102=_解析L102(gates["L1-02"]),
        L103=_解析L103(gates["L1-03"]),
    )


def _校验根结构(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise 闸门规则加载错误("L1 结构化闸门规则根节点必须是对象")
    for key in ["schema_version", "version", "status", "scope", "gates"]:
        if key not in raw:
            raise 闸门规则加载错误(f"L1 结构化闸门规则缺少字段：{key}")
    if raw["schema_version"] != REQUIRED_SCHEMA:
        raise 闸门规则加载错误("L1 结构化闸门规则 schema_version 不匹配")
    if raw["status"] != "active":
        raise 闸门规则加载错误("L1 结构化闸门规则 status 必须为 active")
    _非空字符串(raw["version"], "version")
    _非空字符串(raw["scope"], "scope")
    if not isinstance(raw["gates"], dict):
        raise 闸门规则加载错误("L1 结构化闸门规则 gates 必须是对象")
    missing = sorted(REQUIRED_GATES - set(raw["gates"]))
    if missing:
        raise 闸门规则加载错误(f"L1 结构化闸门规则缺少闸门：{'、'.join(missing)}")


def _解析L101(raw: Any) -> L101规则:
    _校验闸门(raw, "L1-01")
    return L101规则(
        失败类型=_字符串列表(raw["failure_types"], "L1-01.failure_types"),
        通过标准=_字符串列表(raw["pass_rules"], "L1-01.pass_rules"),
        表现词=_字符串列表字典(raw["signal_terms"], "L1-01.signal_terms"),
    )


def _解析L102(raw: Any) -> L102规则:
    _校验闸门(raw, "L1-02")
    thresholds = raw.get("thresholds", {})
    if not isinstance(thresholds, dict):
        raise 闸门规则加载错误("L1-02.thresholds 必须是对象")
    for key in ["E", "V", "C_max", "I_min"]:
        if not isinstance(thresholds.get(key), int):
            raise 闸门规则加载错误(f"L1-02.thresholds.{key} 必须是整数")
    return L102规则(
        公式=_非空字符串(raw["formula"], "L1-02.formula"),
        不足条件=_非空字符串(raw["insufficient_condition"], "L1-02.insufficient_condition"),
        失败类型=_字符串列表(raw["failure_types"], "L1-02.failure_types"),
        通过标准=_字符串列表(raw["pass_rules"], "L1-02.pass_rules"),
        变量词=_字符串列表字典(raw["variable_terms"], "L1-02.variable_terms"),
        低表现词=_字符串列表字典(raw["low_signal_terms"], "L1-02.low_signal_terms"),
        通过阈值={key: int(thresholds[key]) for key in ["E", "V", "C_max", "I_min"]},
    )


def _解析L103(raw: Any) -> L103规则:
    _校验闸门(raw, "L1-03")
    word_count = raw.get("word_count", {})
    if not isinstance(word_count, dict):
        raise 闸门规则加载错误("L1-03.word_count 必须是对象")
    lower = _整数(word_count.get("lower"), "L1-03.word_count.lower")
    upper = _整数(word_count.get("upper"), "L1-03.word_count.upper")
    floor = _整数(word_count.get("function_floor"), "L1-03.word_count.function_floor")
    if not (0 < floor <= lower <= upper):
        raise 闸门规则加载错误("L1-03.word_count 必须满足 0 < function_floor <= lower <= upper")
    return L103规则(
        字数下限=lower,
        字数上限=upper,
        功能稿下限=floor,
        发布判定表=_字符串字典(raw["publication_checks"], "L1-03.publication_checks"),
        当章收益项=_字符串列表(raw["chapter_benefits"], "L1-03.chapter_benefits"),
    )


def _校验闸门(raw: Any, gate: str) -> None:
    if not isinstance(raw, dict):
        raise 闸门规则加载错误(f"{gate} 必须是对象")
    for key in ["gate", "status", "scope"]:
        if key not in raw:
            raise 闸门规则加载错误(f"{gate} 缺少字段：{key}")
    if raw["gate"] != gate:
        raise 闸门规则加载错误(f"{gate}.gate 字段不一致")
    if raw["status"] != "active":
        raise 闸门规则加载错误(f"{gate}.status 必须为 active")
    _非空字符串(raw["scope"], f"{gate}.scope")


def _字符串列表(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise 闸门规则加载错误(f"{label} 必须是字符串数组")
    return [item for item in value if item]


def _字符串字典(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise 闸门规则加载错误(f"{label} 必须是字符串字典")
    return dict(value)


def _字符串列表字典(value: Any, label: str) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise 闸门规则加载错误(f"{label} 必须是字符串数组字典")
    return {str(key): _字符串列表(items, f"{label}.{key}") for key, items in value.items()}


def _整数(value: Any, label: str) -> int:
    if not isinstance(value, int):
        raise 闸门规则加载错误(f"{label} 必须是整数")
    return value


def _非空字符串(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise 闸门规则加载错误(f"{label} 必须是非空字符串")
    return value.strip()
