from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from 工程异常 import 结构错误

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ModuleNotFoundError:  # pragma: no cover - exercised when dependency is absent
    Draft202012Validator = None
    FormatChecker = None


def 读取结构(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def 校验必填字段(data: dict[str, Any], required: list[str], label: str) -> None:
    missing = [field for field in required if field not in data]
    if missing:
        raise 结构错误(f"{label} 缺少必填字段：{'、'.join(missing)}")


def 校验列表字段(data: dict[str, Any], field: str, label: str) -> None:
    if field not in data or not isinstance(data[field], list):
        raise 结构错误(f"{label} 字段必须是列表：{field}")


def 校验JSONSchema(data: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    if Draft202012Validator is None:
        raise 结构错误(f"{label} JSON Schema 校验失败：缺少 jsonschema 依赖")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise 结构错误(f"{label} JSON Schema 校验失败：{location}: {first.message}")


def 按结构文件校验(data: dict[str, Any], schema_path: Path, label: str) -> None:
    校验JSONSchema(data, 读取结构(schema_path), label)
