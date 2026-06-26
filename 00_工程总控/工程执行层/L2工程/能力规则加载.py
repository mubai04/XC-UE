from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from 工程异常 import 工程错误
from 退出码 import ExitCode
from 能力标准解析 import L2规则, 失败规则, 能力规则


REQUIRED_SCHEMA = "xcue.l2-ability-rules/1.0"
REQUIRED_MODULES = {"L2-01", "L2-02", "L2-03", "L2-04", "L2-05", "L2-06"}


class 能力规则加载错误(工程错误):
    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.RULE_PARSE_FAILED)


def L2能力规则路径(root: Path) -> Path:
    return root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json"


def 加载能力规则(path: Path) -> L2规则:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise 能力规则加载错误(f"L2 结构化能力规则不可读：{path}") from exc
    try:
        raw = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise 能力规则加载错误(f"L2 结构化能力规则解析失败：{path}") from exc

    _校验根结构(raw)
    version = raw["version"]
    abilities_raw = raw["abilities"]
    abilities = {module: _解析能力(module, abilities_raw[module], version) for module in sorted(REQUIRED_MODULES)}
    return L2规则(
        能力接口表={module: ability for module, ability in abilities.items()},
        能力规则=abilities,
        接口失败类型=_字符串字典(raw.get("interface_failure_types", {}), "interface_failure_types"),
    )


def _校验根结构(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise 能力规则加载错误("L2 结构化能力规则根节点必须是对象")
    if raw.get("schema_version") != REQUIRED_SCHEMA:
        raise 能力规则加载错误("L2 结构化能力规则 schema_version 不匹配")
    for key in ["version", "status", "scope", "abilities"]:
        if key not in raw:
            raise 能力规则加载错误(f"L2 结构化能力规则缺少字段：{key}")
    if raw["status"] != "active":
        raise 能力规则加载错误("L2 结构化能力规则 status 必须为 active")
    if not isinstance(raw["version"], str) or not raw["version"].strip():
        raise 能力规则加载错误("L2 结构化能力规则 version 不能为空")
    if not isinstance(raw["scope"], str) or not raw["scope"].strip():
        raise 能力规则加载错误("L2 结构化能力规则 scope 不能为空")
    if not isinstance(raw["abilities"], dict):
        raise 能力规则加载错误("L2 结构化能力规则 abilities 必须是对象")
    missing = sorted(REQUIRED_MODULES - set(raw["abilities"]))
    if missing:
        raise 能力规则加载错误(f"L2 结构化能力规则缺少模块：{'、'.join(missing)}")
def _解析能力(module: str, raw: Any, version: str) -> 能力规则:
    if not isinstance(raw, dict):
        raise 能力规则加载错误(f"{module} 能力规则必须是对象")
    required = [
        "module",
        "source",
        "status",
        "scope",
        "input_keywords",
        "output_product",
        "default_returns",
        "failure_types",
        "repair_actions",
        "default_actions",
        "acceptance_questions",
        "forbidden",
    ]
    for key in required:
        if key not in raw:
            raise 能力规则加载错误(f"{module} 缺少字段：{key}")
    if raw["module"] != module:
        raise 能力规则加载错误(f"{module} module 字段不一致")
    if raw["status"] != "active":
        raise 能力规则加载错误(f"{module} status 必须为 active")
    source = _非空字符串(raw["source"], f"{module}.source")
    _非空字符串(raw["scope"], f"{module}.scope")
    failure_types = [_解析失败规则(module, item, version) for item in _对象列表(raw["failure_types"], f"{module}.failure_types")]
    if not failure_types:
        raise 能力规则加载错误(f"{module} failure_types 不能为空")
    ability = 能力规则(
        模块=module,
        标准来源=source,
        输入关键词=_字符串列表(raw["input_keywords"], f"{module}.input_keywords"),
        输出产物=_非空字符串(raw["output_product"], f"{module}.output_product"),
        默认回流=_字符串列表(raw["default_returns"], f"{module}.default_returns"),
        失败类型库=failure_types,
        修复动作库=_字符串列表(raw["repair_actions"], f"{module}.repair_actions"),
        回流验收问题=_字符串列表(raw["acceptance_questions"], f"{module}.acceptance_questions"),
        禁止项=_字符串列表(raw["forbidden"], f"{module}.forbidden"),
        默认动作=_字符串列表字典(raw["default_actions"], f"{module}.default_actions"),
        规则版本=version,
    )
    ability.标准来源 = source
    return ability


def _解析失败规则(module: str, raw: dict[str, Any], version: str) -> 失败规则:
    for key in ["id", "name", "definition", "signals", "repair_rules", "acceptance"]:
        if key not in raw:
            raise 能力规则加载错误(f"{module}.failure_types 缺少字段：{key}")
    return 失败规则(
        编号=_非空字符串(raw["id"], f"{module}.failure_types.id"),
        名称=_非空字符串(raw["name"], f"{module}.failure_types.name"),
        定义=_字符串(raw["definition"], f"{module}.failure_types.definition"),
        表现=_字符串列表(raw["signals"], f"{module}.failure_types.signals"),
        修复规则=_字符串列表(raw["repair_rules"], f"{module}.failure_types.repair_rules"),
        验收标准=_字符串列表(raw["acceptance"], f"{module}.failure_types.acceptance"),
        匹配关键词=_字符串列表(raw.get("match_keywords", []), f"{module}.failure_types.match_keywords"),
        规则版本=version,
    )


def _对象列表(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise 能力规则加载错误(f"{label} 必须是对象数组")
    return value


def _字符串列表(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise 能力规则加载错误(f"{label} 必须是字符串数组")
    return [item for item in value if item]


def _字符串字典(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise 能力规则加载错误(f"{label} 必须是字符串字典")
    return dict(value)


def _字符串列表字典(value: Any, label: str) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise 能力规则加载错误(f"{label} 必须是字符串数组字典")
    result: dict[str, list[str]] = {}
    for key, items in value.items():
        if not isinstance(key, str):
            raise 能力规则加载错误(f"{label} 键必须是字符串")
        result[key] = _字符串列表(items, f"{label}.{key}")
    return result


def _字符串(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise 能力规则加载错误(f"{label} 必须是字符串")
    return value


def _非空字符串(value: Any, label: str) -> str:
    text = _字符串(value, label).strip()
    if not text:
        raise 能力规则加载错误(f"{label} 不能为空")
    return text
