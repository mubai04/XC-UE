from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

from 迁移错误 import (
    CROSS_LAYER_SCHEMA_ID_DUPLICATED,
    CROSS_LAYER_SCHEMA_MISSING,
    CROSS_LAYER_SCHEMA_REF_UNRESOLVED,
    迁移错误,
)

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "结构定义" / "跨层契约"

SCHEMA_FILES = [
    "公共引用结构_v1.json",
    "L1发现项结构_v2.json",
    "L1失败包结构_v2.json",
    "L1_5路由决策结构_v2.json",
    "L2修复单结构_v2.json",
    "L2报告结构_v2.json",
    "L3执行任务包结构_v2.json",
    "L3执行结果结构_v2.json",
]

SCHEMA_IDS = {
    "common-reference/v1": "xcue://schemas/cross-layer/common-reference/v1",
    "l1-finding/v2": "xcue://schemas/cross-layer/l1-finding/v2",
    "l1-failure-packet/v2": "xcue://schemas/cross-layer/l1-failure-packet/v2",
    "l15-route-decision/v2": "xcue://schemas/cross-layer/l15-route-decision/v2",
    "l2-fix-form/v2": "xcue://schemas/cross-layer/l2-fix-form/v2",
    "l2-report/v2": "xcue://schemas/cross-layer/l2-report/v2",
    "l3-task-bundle/v2": "xcue://schemas/cross-layer/l3-task-bundle/v2",
    "l3-execution-result/v2": "xcue://schemas/cross-layer/l3-execution-result/v2",
}


def _load_schema(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise 迁移错误(CROSS_LAYER_SCHEMA_MISSING, str(path))
    return json.loads(path.read_text(encoding="utf-8-sig"))


def 预检Schema() -> list[str]:
    errors: list[str] = []
    ids: list[str] = []
    for name in SCHEMA_FILES:
        path = SCHEMA_DIR / name
        if not path.exists():
            errors.append(f"缺失：{name}")
            continue
        data = _load_schema(path)
        if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name} 非 Draft 2020-12")
        sid = data.get("$id", "")
        if not sid or not sid.startswith("xcue://"):
            errors.append(f"{name} $id 非绝对 ASCII URI")
        if sid in ids:
            errors.append(f"重复 $id：{sid}")
        ids.append(sid)
        try:
            Draft202012Validator.check_schema(data)
        except SchemaError as exc:
            errors.append(f"{name} check_schema 失败：{exc.message}")
    if not errors:
        try:
            registry = _build_registry()
            for name in SCHEMA_FILES:
                data = _load_schema(SCHEMA_DIR / name)
                Draft202012Validator(data, registry=registry)
        except Exception as exc:
            errors.append(f"$ref 解析失败：{exc}")
    return errors


@lru_cache(maxsize=1)
def _build_registry() -> Registry:
    resources: list[tuple[str, Resource]] = []
    seen_ids: set[str] = set()
    for name in SCHEMA_FILES:
        path = SCHEMA_DIR / name
        data = _load_schema(path)
        uri = data["$id"]
        if uri in seen_ids:
            raise 迁移错误(CROSS_LAYER_SCHEMA_ID_DUPLICATED, uri)
        seen_ids.add(uri)
        try:
            Draft202012Validator.check_schema(data)
        except SchemaError as exc:
            raise 迁移错误(CROSS_LAYER_SCHEMA_REF_UNRESOLVED, f"{name}: {exc.message}") from exc
        resources.append((uri, Resource.from_contents(data)))
    return Registry().with_resources(resources)


def 获取Schema注册表() -> Registry:
    return _build_registry()


def 获取Schema(schema_id: str) -> dict[str, Any]:
    for name in SCHEMA_FILES:
        data = _load_schema(SCHEMA_DIR / name)
        if data["$id"] == schema_id:
            return data
    raise 迁移错误(CROSS_LAYER_SCHEMA_MISSING, schema_id)


def 校验对象(schema_id: str, payload: dict[str, Any]) -> None:
    schema = 获取Schema(schema_id)
    registry = _build_registry()
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        loc = ".".join(str(p) for p in first.path) or "<root>"
        raise 迁移错误(CROSS_LAYER_SCHEMA_REF_UNRESOLVED, f"{loc}: {first.message}")
