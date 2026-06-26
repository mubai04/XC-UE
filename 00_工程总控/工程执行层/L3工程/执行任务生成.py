from __future__ import annotations

from pathlib import Path

from L3模型 import L2修复单, L3执行任务, L3协议规则
from IR输入映射校验 import 映射IR
from ProjectHarness运行校验 import 默认候选目标, 相对


def 任务类型(form: L2修复单, rules: L3协议规则) -> str:
    for rule in rules.任务类型规则:
        match = rule.get("match", {})
        if match.get("main_failure_type") == form.主失败类型:
            return str(rule.get("task_type", ""))
        modules = match.get("receiver_modules", [])
        if form.接收模块 in modules or "*" in modules:
            return str(rule.get("task_type", ""))
    return "正文改写任务规划"


def 生成(forms: list[L2修复单], source_file: str, run_id: str, root: Path, harness: Path, rules: L3协议规则) -> list[L3执行任务]:
    tasks: list[L3执行任务] = []
    for idx, form in enumerate(forms, start=1):
        formal_chapters = [相对(root, path) for path in sorted((harness / "chapters").glob(rules.正文章节Glob))]
        tasks.append(
            L3执行任务(
                执行编号=f"L3RUN-{run_id}-{idx:03d}",
                来源层=form.接收模块,
                来源文件=source_file,
                ProjectHarness根=相对(root, harness),
                任务类型=任务类型(form, rules),
                输入材料=form.输入问题,
                IR输入=映射IR(form, root, harness, rules),
                目标文件=默认候选目标(root, harness, run_id, idx, rules),
                禁止修改文件=[
                    *formal_chapters,
                    *rules.默认禁止目标,
                ],
                修复方向=form.修复动作,
                修复产物要求=form.修复产物,
                回流验收位置=form.回流位置,
                是否允许改正式正文=rules.是否允许改正式正文,
                是否需要备份=rules.是否需要备份,
            )
        )
    return tasks
