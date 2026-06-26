from __future__ import annotations

from L3模型 import L3执行任务


def 校验(task: L3执行任务) -> list[str]:
    errors: list[str] = []
    if not task.来源层:
        errors.append("来源层不明")
    if not task.任务类型:
        errors.append("任务类型不明")
    if not task.目标文件:
        errors.append("目标文件不明")
    if not task.回流验收位置:
        errors.append("未指定回流验收位置")
    if task.是否允许改正式正文 not in {"是", "否"}:
        errors.append("是否允许改正式正文不明")
    if task.是否允许改正式正文 == "是":
        errors.append("L3 已冻结为 TASK_PLANNING_ONLY，不允许修改正式正文")
    if task.是否需要备份 not in {"不适用", "否"}:
        errors.append("TASK_PLANNING_ONLY 不要求正文备份")
    return errors
