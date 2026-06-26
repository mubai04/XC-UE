from __future__ import annotations

import json
import sys
from pathlib import Path

from L3模型 import L3报告

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 原子写入 import 原子写文本
from 工程异常 import 输入错误


def 报告路径(result: L3报告, out_dir: Path) -> tuple[Path, Path]:
    if out_dir.name == "第三层":
        return out_dir / "任务包.md", out_dir / "任务包.json"
    return out_dir / f"{result.run_id}.md", out_dir / f"{result.run_id}.json"


def 预期报告路径(run_id: str, out_dir: Path) -> tuple[Path, Path]:
    if out_dir.name == "第三层":
        return out_dir / "任务包.md", out_dir / "任务包.json"
    return out_dir / f"{run_id}.md", out_dir / f"{run_id}.json"


def 拒绝覆盖既有报告(run_id: str, out_dir: Path) -> None:
    md_path, json_path = 预期报告路径(run_id, out_dir)
    existing = [path for path in [json_path, md_path] if path.exists()]
    if existing:
        raise 输入错误("L3 输出已存在，拒绝覆盖：" + "、".join(str(path) for path in existing))


def 写报告(result: L3报告, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path, json_path = 报告路径(result, out_dir)
    原子写文本(json_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    lines = [
        f"# L3 正文修复任务包报告 {result.run_id}",
        "",
        f"- 机器状态：{result.status}",
        f"- 状态说明：{result.状态说明}",
        f"- 执行模式：{result.execution_mode}",
        f"- 是否修改正文：{str(result.prose_modified).lower()}",
        f"- 是否等待执行器：{str(result.awaiting_executor).lower()}",
        f"- 输入文件：`{result.输入文件}`",
        f"- 输入修复单数量：{result.输入修复单数量}",
        f"- 方法声明：{result.方法声明}",
        "",
        "## 工程自检",
        "",
        f"- 标准校验问题：{len(result.标准校验问题)}",
        f"- 阻断任务：{len(result.阻断任务)}",
        f"- 协议规则摘要：`{json.dumps(result.协议规则摘要, ensure_ascii=False)}`",
    ]
    if result.标准校验问题:
        lines.extend(["", "### 标准校验问题"])
        lines.extend(f"- {item}" for item in result.标准校验问题)

    lines.extend(["", "## L3 执行任务单"])
    for task in result.任务单:
        history = " → ".join(
            item.get("后状态", "") if isinstance(item, dict) else str(item)
            for item in task.状态历史
        )
        lines.extend(
            [
                "",
                f"### {task.执行编号}",
                f"- 来源层：{task.来源层}",
                f"- Project Harness：`{task.ProjectHarness根}`",
                f"- 任务类型：{task.任务类型}",
                f"- IR 输入：{', '.join(task.IR输入) or '无'}",
                f"- 目标文件：`{task.目标文件}`",
                f"- 修复方向：{task.修复方向}",
                f"- 修复产物要求：{task.修复产物要求}",
                f"- 回流验收位置：{task.回流验收位置}",
                f"- 是否允许改正式正文：{task.是否允许改正式正文}",
                f"- 是否需要备份：{task.是否需要备份}",
                f"- 状态历史：{history if history else task.执行状态}",
                f"- 校验问题：{('；'.join(task.校验问题) if task.校验问题 else '无')}",
            ]
        )

    lines.extend(["", "## L3 任务包输出"])
    for output in result.执行输出:
        lines.extend(
            [
                "",
                f"### {output.执行编号}",
                f"- 执行状态：{output.执行状态}",
                f"- 实际读取文件：{', '.join(output.实际读取文件)}",
                f"- 任务包文件：`{output.任务包文件 or '无'}`",
                f"- 分项任务文件：`{output.分项任务文件 or '无'}`",
                f"- 任务依赖：{', '.join(output.任务依赖) or '无'}",
                f"- 约束：{', '.join(output.约束) or '无'}",
                f"- 目标文件引用：`{output.目标文件引用}`",
                f"- 复验入口：{output.复验入口}",
                f"- 断点记录：{output.断点记录 or '无'}",
            ]
        )

    原子写文本(md_path, "\n".join(lines) + "\n")
    return md_path, json_path
