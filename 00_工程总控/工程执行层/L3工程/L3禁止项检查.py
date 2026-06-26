from __future__ import annotations

from L3模型 import L3执行任务


def 检查(task: L3执行任务) -> list[str]:
    errors: list[str] = []
    joined = " ".join([task.任务类型, task.目标文件, task.修复方向, task.修复产物要求])
    if "删除" in joined:
        errors.append("禁止删除文件")
    if "覆盖正式正文" in joined or "自动合并" in joined:
        errors.append("禁止候选正文自动覆盖正式正文")
    if "图片覆盖" in joined:
        errors.append("禁止用图片覆盖 Markdown")
    if "判断作品好坏" in joined:
        errors.append("禁止 L3 判断作品好坏")
    return errors
