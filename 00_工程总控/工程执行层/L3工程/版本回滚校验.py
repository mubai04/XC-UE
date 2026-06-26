from __future__ import annotations

from L3模型 import L3执行任务


def 校验(task: L3执行任务) -> list[str]:
    if task.是否允许改正式正文 == "是":
        return ["L3 任务规划层不得修改正式正文"]
    return []
