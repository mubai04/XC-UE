from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from L3模型 import L3执行任务, L3执行输出, 追加状态

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 原子写入 import 原子写文本

def _abs(root: Path, rel: str) -> Path:
    return (root / rel).resolve()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _candidate_text(task: L3执行任务, ir_summaries: list[str]) -> str:
    return "\n".join(
        [
            f"# L3 正文修复任务包 {task.执行编号}",
            "",
            "> 本文件由 L3 工程生成，只承载正文修复任务说明；不生成候选正文，不自动覆盖正式正文。",
            "",
            f"- 来源层：{task.来源层}",
            f"- 任务类型：{task.任务类型}",
            f"- 回流验收位置：{task.回流验收位置}",
            f"- 修复产物要求：{task.修复产物要求}",
            "",
            "## 输入问题",
            "",
            task.输入材料,
            "",
            "## 修复方向",
            "",
            task.修复方向,
            "",
            "## IR 输入摘要",
            "",
            *ir_summaries,
            "",
            "## 执行边界",
            "",
            "- 不修改正式正文。",
            "- 不修改 L0-L3 / L1.5 真源。",
            "- 本文件等待人工或后续执行器处理，不代表正文已修复。",
            "",
        ]
    )


def _ir_summaries(root: Path, task: L3执行任务) -> list[str]:
    summaries = []
    for rel in task.IR输入:
        path = _abs(root, rel)
        text = _read_text(path).strip().replace("\r\n", "\n")
        first = next((line.strip() for line in text.splitlines() if line.strip()), "空文件")
        summaries.append(f"- `{rel}`：{first[:80]}")
    return summaries


def _任务目录(root: Path, task: L3执行任务) -> Path:
    source_path = Path(task.来源文件)
    if source_path.is_absolute() and source_path.parent.name == "第二层":
        return source_path.parent.parent / "第三层" / "分项任务"
    return root / "运行记录" / "未归属运行" / "第三层" / "分项任务"


def _安全文件名(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", value)


def _相对或原路径(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def 生成输出(task: L3执行任务, root: Path) -> L3执行输出:
    blocked = bool(task.校验问题)
    task_dir = _任务目录(root, task)
    target = task_dir / f"{_安全文件名(task.执行编号)}.md"
    task_rel = _相对或原路径(root, target)
    if blocked:
        return L3执行输出(
            执行编号=task.执行编号,
            执行状态="BLOCKED",
            实际读取文件=[task.来源文件, *task.IR输入],
            任务包文件="",
            分项任务文件="",
            任务依赖=task.IR输入,
            约束=task.禁止修改文件,
            目标文件引用=task.目标文件,
            修复产物=task.修复产物要求,
            复验入口=task.回流验收位置,
            待复验问题=task.输入材料,
            断点记录="；".join(task.校验问题),
            task_package_created=False,
        )

    after = _candidate_text(task, _ir_summaries(root, task))
    原子写文本(target, after)
    追加状态(task, "TASK_PACKAGE_CREATED", "任务包写入完成", "L3工程.输出生成", task_rel)
    追加状态(task, "AWAITING_EXECUTOR", "等待人工或后续执行器", "L3工程.输出生成", task_rel)

    return L3执行输出(
        执行编号=task.执行编号,
        执行状态="AWAITING_EXECUTOR",
        实际读取文件=[task.来源文件, *task.IR输入],
        任务包文件=task_rel,
        分项任务文件=task_rel,
        任务依赖=task.IR输入,
        约束=task.禁止修改文件,
        目标文件引用=task.目标文件,
        修复产物=task.修复产物要求,
        复验入口=task.回流验收位置,
        待复验问题=task.输入材料,
        断点记录="",
        task_package_created=True,
    )
