from __future__ import annotations

import re

_PREFIX = {
    "L1发现": "L1F",
    "L1失败包": "L1P",
    "L1.5路由": "L15R",
    "L2修复单": "L2F",
    "L2报告": "L2R",
    "L3任务包": "L3T",
    "L3执行结果": "L3O",
    "证据": "EV",
    "产物": "ART",
    "任务": "TASK",
}


def 归一化pipeline_id(pipeline_run_id: str) -> str:
    text = re.sub(r"[^\w\-]", "-", pipeline_run_id.strip())
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:48] or "PIPE"


def 生成对象编号(类别: str, pipeline_run_id: str, 序号: int) -> str:
    prefix = _PREFIX.get(类别, 类别)
    return f"{prefix}-{归一化pipeline_id(pipeline_run_id)}-{序号:04d}"


def 下一序号(计数: dict[str, int], 类别: str) -> int:
    计数[类别] = 计数.get(类别, 0) + 1
    return 计数[类别]
