from __future__ import annotations

from L3模型 import L3执行任务


def 校验(task: L3执行任务) -> list[str]:
    errors: list[str] = []
    if "正文" not in task.任务类型 and "修复" not in task.任务类型 and "扩写" not in task.任务类型:
        return errors
    if not task.修复方向:
        errors.append("正文任务缺少修复方向")
    if not task.IR输入:
        errors.append("正文任务缺少 IR 输入，不能自由写正文")
    if not task.目标文件:
        errors.append("正文任务缺少目标文件引用")
    if task.是否允许改正式正文 == "是":
        errors.append("TASK_PLANNING_ONLY 不允许修改正式正文")
    return errors
