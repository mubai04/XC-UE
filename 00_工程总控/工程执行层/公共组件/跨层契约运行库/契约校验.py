from __future__ import annotations

from typing import Any

from Schema注册表 import SCHEMA_IDS, 校验对象


def 校验L1发现项(payload: dict[str, Any]) -> None:
    校验对象(SCHEMA_IDS["l1-finding/v2"], payload)


def 校验L1失败包(payload: dict[str, Any]) -> None:
    校验对象(SCHEMA_IDS["l1-failure-packet/v2"], payload)


def 校验L15路由决策(payload: dict[str, Any]) -> None:
    校验对象(SCHEMA_IDS["l15-route-decision/v2"], payload)


def 校验L2修复单(payload: dict[str, Any]) -> None:
    校验对象(SCHEMA_IDS["l2-fix-form/v2"], payload)


def 校验L2报告(payload: dict[str, Any]) -> None:
    校验对象(SCHEMA_IDS["l2-report/v2"], payload)


def 校验L3任务包(payload: dict[str, Any]) -> None:
    校验对象(SCHEMA_IDS["l3-task-bundle/v2"], payload)


def 校验L3执行结果(payload: dict[str, Any]) -> None:
    校验对象(SCHEMA_IDS["l3-execution-result/v2"], payload)
