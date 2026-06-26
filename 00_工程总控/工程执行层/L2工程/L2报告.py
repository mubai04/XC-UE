from __future__ import annotations

import json
import sys
from pathlib import Path

from L2模型 import L2报告

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 原子写入 import 原子写文本
from 工程异常 import 输入错误


def 报告路径(result: L2报告, out_dir: Path) -> tuple[Path, Path]:
    if out_dir.name == "第二层":
        return out_dir / "修复报告.md", out_dir / "修复报告.json"
    return out_dir / f"{result.run_id}.md", out_dir / f"{result.run_id}.json"


def 预期报告路径(run_id: str, out_dir: Path) -> tuple[Path, Path]:
    if out_dir.name == "第二层":
        return out_dir / "修复报告.md", out_dir / "修复报告.json"
    return out_dir / f"{run_id}.md", out_dir / f"{run_id}.json"


def 拒绝覆盖既有报告(run_id: str, out_dir: Path) -> None:
    md_path, json_path = 预期报告路径(run_id, out_dir)
    existing = [path for path in [json_path, md_path] if path.exists()]
    if existing:
        raise 输入错误("L2 输出已存在，拒绝覆盖：" + "、".join(str(path) for path in existing))


def 写报告(result: L2报告, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path, json_path = 报告路径(result, out_dir)
    原子写文本(json_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    lines = [
        f"# L2工程报告 {result.run_id}",
        "",
        f"- 机器状态：{result.status}",
        f"- 状态说明：{result.状态说明}",
        f"- 输入文件：`{result.输入文件}`",
        f"- 输入失败包数量：{result.输入数量}",
        f"- 方法声明：{result.方法声明}",
        "",
        "## 工程自检",
        "",
        f"- 标准校验问题：{len(result.标准校验问题)}",
        f"- 回流校验问题：{len(result.回流校验问题)}",
        f"- 派生复验目标：{len(result.复验目标)}",
    ]
    if result.标准校验问题:
        lines.extend(["", "### 标准校验问题"])
        lines.extend(f"- {item}" for item in result.标准校验问题)
    if result.回流校验问题:
        lines.extend(["", "### 回流校验问题"])
        lines.extend(f"- {item}" for item in result.回流校验问题)
    l201_diagnostics = result.extensions.get("L2-01真实诊断", []) if result.extensions else []
    if l201_diagnostics:
        lines.extend(["", "## L2-01 真实诊断"])
        for idx, diagnosis in enumerate(l201_diagnostics, start=1):
            anchors = diagnosis.get("证据锚点", [])
            anchor_text = "；".join(
                f"P{anchor.get('段落')}：{anchor.get('摘句')}" for anchor in anchors
            ) or "无"
            lines.extend(
                [
                    "",
                    f"### L2-01-DIAG-{idx:03d}",
                    f"- 问题类型：{diagnosis.get('问题类型', '')}",
                    f"- 证据锚点：{anchor_text}",
                    f"- 修改目标：{diagnosis.get('修改目标', '')}",
                    f"- 候选修改策略：{'、'.join(diagnosis.get('候选修改策略', [])) or '无'}",
                    f"- 自动修复资格判定：{diagnosis.get('自动修复资格判定', '')}",
                    f"- 置信度：{diagnosis.get('置信度', '')}",
                ]
            )
    lines.extend(
        [
        "",
        "## 接口判断",
        "",
        "| 来源 | 输入问题 | 初步归属 | 主候选模块 | 状态 | 依据 |",
        "|---|---|---|---|---|---|",
        ]
    )
    for item in result.接口判断:
        lines.append(
            f"| {item.来源闸门} | {item.输入问题} | {item.初步归属} | {item.主候选模块} | {item.最终状态} | {item.判断依据} |"
        )

    lines.extend(["", "## 修复单"])
    if not result.修复单:
        lines.append("无。")
    for idx, form in enumerate(result.修复单, start=1):
        lines.extend(
            [
                "",
                f"### L2-FIX-{idx:03d} {form.接收模块}",
                f"- 来源闸门：{form.来源闸门}",
                f"- 主失败类型：{form.主失败类型}",
                f"- 标准来源：{form.标准来源}",
                f"- 规则编号：{form.规则编号 or '未命中具体规则'}",
                f"- 规则依据：{form.规则依据 or '无'}",
                f"- 输入问题：{form.输入问题}",
                f"- 修复动作：{form.修复动作}",
                f"- 标准动作：{('、'.join(form.标准动作) if form.标准动作 else '无')}",
                f"- 修复产物：{form.修复产物}",
                f"- 验收问题：{form.验收问题}",
                f"- 标准验收：{('、'.join(form.标准验收) if form.标准验收 else '无')}",
                f"- 回流位置：{form.回流位置}",
                f"- 是否需要其他 L2 辅助：{form.是否需要其他L2辅助}",
                f"- 是否需要回 L1.5 重路由：{form.是否需要回L15重路由}",
                f"- 最终状态：{form.最终状态}",
            ]
        )

    lines.extend(["", "## 派生复验目标"])
    if not result.复验目标:
        lines.append("无。")
    for item in result.复验目标:
        lines.extend(
            [
                "",
                f"### {item.回流验收位置}",
                f"- 来源闸门：{item.来源闸门}",
                f"- 输入问题：{item.输入问题}",
                f"- 建议动作：{'、'.join(item.建议动作)}",
                f"- 备注：{item.备注 or '仅记录复验目标，不生成 L2 修复单。'}",
            ]
        )

    lines.extend(["", "## 阻断 / 回流"])
    if not result.阻断项:
        lines.append("无。")
    for item in result.阻断项:
        lines.extend(
            [
                "",
                f"### {item.最终状态}",
                f"- 来源闸门：{item.来源闸门}",
                f"- 输入问题：{item.输入问题}",
                f"- 接口失败类型：{item.接口失败类型}",
                f"- 建议动作：{'、'.join(item.建议动作)}",
                f"- 回流验收位置：{item.回流验收位置}",
            ]
        )

    原子写文本(md_path, "\n".join(lines) + "\n")
    return md_path, json_path
