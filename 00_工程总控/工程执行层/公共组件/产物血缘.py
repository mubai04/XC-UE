from __future__ import annotations

from typing import Any

from 工程异常 import 血缘错误


def 产物记录(kind: str, path: str, producer_stage: str, producer_run_id: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path),
        "producer_stage": producer_stage,
        "producer_run_id": producer_run_id,
    }


def 校验流水线归属(data: dict[str, Any], pipeline_run_id: str, label: str) -> None:
    actual = data.get("pipeline_run_id")
    if actual and actual != pipeline_run_id:
        raise 血缘错误(f"{label} 不属于本次流水线：expected={pipeline_run_id} actual={actual}")
