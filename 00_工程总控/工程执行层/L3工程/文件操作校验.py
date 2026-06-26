from __future__ import annotations

from pathlib import PureWindowsPath

from L3模型 import L3执行任务


FORMAL_CHAPTER_PART = "chapters\\ch"
AUTH_SOURCE_PARTS = ["20_L1_闸门层", "30_L1.5_路由矩阵层", "40_L2_正式能力层", "50_L3_执行协议层"]


def 校验(task: L3执行任务) -> list[str]:
    errors: list[str] = []
    target = str(PureWindowsPath(task.目标文件)).replace("/", "\\")
    if FORMAL_CHAPTER_PART in target and task.是否允许改正式正文 != "是":
        errors.append("目标疑似正式正文，但未授权修改正式正文")
    for part in AUTH_SOURCE_PARTS:
        if part in target:
            errors.append("目标文件属于系统真源/协议层，L3 默认不得修改")
    if "99_归档_不要索引" in target:
        errors.append("不得从归档或对归档执行覆盖任务")
    if any("删除" in text for text in [task.任务类型, task.修复方向, task.修复产物要求]):
        errors.append("任务包含删除倾向，触发 L3-99 阻断")
    return errors
