from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from 工程异常 import 血缘错误, 输入错误
from 结构校验 import 按结构文件校验


MAX_JSON_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class 血缘期望:
    pipeline_run_id: str = ""
    stage_run_id: str = ""


@dataclass(frozen=True)
class 已校验文档:
    path: Path
    data: dict[str, Any]


def 校验JSON输入(
    path: Path,
    *,
    schema_path: Path,
    label: str,
    expected_schema_version: str,
    lineage: 血缘期望 | None = None,
) -> 已校验文档:
    if not path.exists():
        raise 输入错误(f"{label} 文件不存在：{path}")
    if not path.is_file():
        raise 输入错误(f"{label} 不是文件：{path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise 输入错误(f"{label} 无法读取文件状态：{path}") from exc
    if size <= 0:
        raise 输入错误(f"{label} 不能为空：{path}")
    if size > MAX_JSON_BYTES:
        raise 输入错误(f"{label} 超过大小限制：{path}")

    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise 输入错误(f"{label} 必须是 UTF-8 或 UTF-8-SIG：{path}") from exc
    except OSError as exc:
        raise 输入错误(f"{label} 读取失败：{path}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise 输入错误(f"{label} JSON 解析失败：{exc.msg}") from exc
    if not isinstance(data, dict):
        raise 输入错误(f"{label} 顶层必须是 JSON object")
    schema_version = data.get("schema_version")
    if schema_version != expected_schema_version:
        raise 输入错误(f"{label} schema_version 必须是 {expected_schema_version}，实际为 {schema_version!r}")

    try:
        按结构文件校验(data, schema_path, label)
    except Exception as exc:
        raise 输入错误(str(exc)) from exc

    if lineage:
        if lineage.pipeline_run_id and data.get("pipeline_run_id") != lineage.pipeline_run_id:
            raise 血缘错误(
                f"{label} 不属于本次流水线：expected={lineage.pipeline_run_id}, actual={data.get('pipeline_run_id')}"
            )
        if lineage.stage_run_id and data.get("stage_run_id") != lineage.stage_run_id:
            raise 血缘错误(
                f"{label} 阶段来源不匹配：expected={lineage.stage_run_id}, actual={data.get('stage_run_id')}"
            )

    return 已校验文档(path=path, data=data)
