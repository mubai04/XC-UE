from __future__ import annotations

import json
import sys
from pathlib import Path

from L15模型 import L15路由报告

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 原子写入 import 原子写文本
from 工程异常 import 输入错误


def 预期报告路径(run_id: str, out_dir: Path) -> tuple[Path, Path]:
    return out_dir / f"{run_id}.md", out_dir / f"{run_id}.json"


def 拒绝覆盖既有报告(run_id: str, out_dir: Path) -> None:
    md_path, json_path = 预期报告路径(run_id, out_dir)
    existing = [path for path in [json_path, md_path] if path.exists()]
    if existing:
        raise 输入错误("L1.5 输出已存在，拒绝覆盖：" + "、".join(str(path) for path in existing))


def 写报告(result: L15路由报告, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path, json_path = 预期报告路径(result.run_id, out_dir)
    原子写文本(json_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    lines = [
        f"# L1.5 路由报告 {result.run_id}",
        "",
        f"- 最终状态：{result.final_status}",
        f"- 目标模块：{result.target_module or '无'}",
        f"- 修复产物：{result.repair_product or '无'}",
        f"- 回流闸门：{result.return_gate or '无'}",
        f"- 路由规则：{result.route_rule_id} ({result.route_rule_version})",
        f"- 来源 failure packet：`{result.source_failure_packet}`",
        "",
        "## 主失败项",
        "",
        f"- 闸门：{result.primary_failure.闸门}",
        f"- 失败类型：{result.primary_failure.失败类型}",
        f"- 说明：{result.primary_failure.说明}",
        "",
        "## 路由依据",
        "",
        result.routing_basis or "无",
        "",
        "## 次级失败项",
        "",
    ]
    if not result.secondary_failures:
        lines.append("无。")
    for idx, item in enumerate(result.secondary_failures, start=1):
        lines.append(f"{idx}. [{item.闸门}] {item.失败类型} — {item.说明}")
    lines.extend(["", "## 阻断项", ""])
    if not result.blockers:
        lines.append("无。")
    else:
        lines.extend(f"- {item}" for item in result.blockers)
    原子写文本(md_path, "\n".join(lines) + "\n")
    return md_path, json_path
