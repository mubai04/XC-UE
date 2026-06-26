from __future__ import annotations

import json
import sys
from pathlib import Path

from L1模型 import 正文检测结果

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 工程异常 import 输入错误
from 原子写入 import 原子写文本


状态显示 = {
    "SCREENING_PASS": "未命中已配置的启发式硬风险",
    "SCREENING_REJECT": "命中已配置的启发式硬风险",
    "REVIEW_REQUIRED": "需要人工复核",
    "HUMAN_REVIEW_REQUIRED": "需要人工复核",
    "STRUCTURE_SIGNAL_PRESENT": "检测到结构代理信号",
    "INTERFACE_SIGNAL_PRESENT": "检测到接口代理信号",
    "接口成立": "接口字段检测未发现指定风险",
    "需要派单修复": "接口检测需要派单修复",
    "需要补输入": "接口检测需要补输入",
}


检测项状态显示 = {
    "成立": "检测到代理信号",
    "通过": "启发式检查未发现指定风险",
    "失败": "命中启发式硬风险",
    "风险": "命中启发式复核风险",
    "阻断": "前置条件未满足",
}


def _显示状态(value: str) -> str:
    return 状态显示.get(value, value)


def _显示检测项状态(value: str) -> str:
    return 检测项状态显示.get(value, value)


def _列表(value: list[str]) -> str:
    return "；".join(value) if value else "无"


def 报告路径(run_id: str, out_dir: Path) -> tuple[Path, Path, Path]:
    if out_dir.name == "第一层":
        json_path = out_dir / "检测报告.json"
        md_path = out_dir / "检测报告.md"
        packet_path = out_dir / "失败包.json"
    else:
        json_path = out_dir / f"{run_id}.json"
        md_path = out_dir / f"{run_id}.md"
        packet_path = out_dir / f"{run_id}_failure_packet.json"
    return md_path, json_path, packet_path


def 拒绝覆盖既有报告(run_id: str, out_dir: Path) -> None:
    existing = [path for path in 报告路径(run_id, out_dir) if path.exists()]
    if existing:
        joined = "；".join(str(path) for path in existing)
        raise 输入错误(f"L1 输出已存在，拒绝覆盖：{joined}")


def 写报告(result: 正文检测结果, out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path, json_path, packet_path = 报告路径(result.run_id, out_dir)
    拒绝覆盖既有报告(result.run_id, out_dir)

    原子写文本(json_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    packet_payload = {
        "schema_version": "xcue.failure-packet/1.0",
        "pipeline_run_id": result.pipeline_run_id,
        "stage_run_id": result.stage_run_id,
        "status": result.status,
        "failure_count": len(result.失败包),
        "items": [item.__dict__ | {"证据": [e.__dict__ for e in item.证据]} for item in result.失败包],
    }
    原子写文本(
        packet_path,
        json.dumps(packet_payload, ensure_ascii=False, indent=2),
    )

    lines = [
        f"# L1工程报告 {result.run_id}",
        "",
        f"- 机器状态：{result.status}",
        f"- 状态说明：{_显示状态(result.status)}；{result.状态说明}",
        f"- 启发式结果：{str(result.heuristic).lower()}",
        f"- 发布权限：{str(result.publish_authority).lower()}",
        f"- 需要人工复核：{str(result.human_review_required).lower()}",
        f"- 验证状态：{result.validation_status}",
        f"- 决策范围：{result.decision_scope}",
        f"- 规则版本：{result.rule_version}",
        f"- 信号强度：{result.signal_strength}",
        f"- 置信度：{result.confidence}",
        f"- 已知限制：{_列表(result.known_limitations)}",
        f"- 人工复核原因：{_列表(result.human_review_reasons)}",
        f"- 禁止外推：{_列表(result.forbidden_extrapolations)}",
        f"- 项目：{result.项目}",
        f"- 章节：{result.章节标题}",
        f"- 正文路径：`{result.章节路径}`",
        f"- 当前字数：{result.当前字数}",
        f"- 段落数：{result.段落数}",
        f"- 方法声明：{result.方法声明}",
        "",
        "## 闸门结论",
    ]

    for gate in result.闸门结果:
        lines.extend(
            [
                "",
                f"### {gate.闸门}",
                f"- 判断结果：{_显示状态(gate.判断结果)}（{gate.判断结果}）",
                f"- 输入材料：{('、'.join(gate.输入材料) if gate.输入材料 else '未声明')}",
                f"- 失败类型：{('、'.join(gate.失败类型) if gate.失败类型 else '无硬失败；见检测项风险')}",
                f"- 是否进入 L1.5：{gate.是否进入L15}",
                f"- 调用方向：{('、'.join(gate.调用方向) if gate.调用方向 else '无')}",
                f"- 回流验收位置：{gate.回流验收位置}",
                f"- 规则摘要：`{json.dumps(gate.规则摘要, ensure_ascii=False)}`",
                "",
                "| 检测项 | 状态 | 级别 | 说明 | 证据 |",
                "|---|---|---|---|---|",
            ]
        )
        for item in gate.检测项:
            ev = "<br>".join(f"P{e.段落}：{e.摘句}" for e in item.证据) or "无"
            lines.append(f"| {item.名称} | {_显示检测项状态(item.状态)} | {item.严重级别} | {item.说明} | {ev} |")

    lines.extend(["", "## 失败包"])
    if not result.失败包:
        lines.append("无。")
    else:
        for idx, item in enumerate(result.失败包, start=1):
            evidence = "；".join(f"P{e.段落}：{e.摘句}" for e in item.证据) or "无"
            lines.extend(
                [
                    "",
                    f"### FP-{idx:03d} {item.失败类型 or item.名称}",
                    f"- 来源闸门：{item.闸门}",
                    f"- 失败位置：{evidence}",
                    f"- 影响：{item.说明}",
                    f"- 候选模块：{item.候选模块 or '回L1.5/人工复核'}",
                    f"- 修复方向：{item.修复方向 or '人工复核'}",
                    f"- 回流验收位置：{item.回流验收位置 or item.闸门}",
                ]
            )

    lines.extend(["", "## 路由建议"])
    for route in result.路由建议:
        lines.extend(
            [
                "",
                f"### {route['路由编号']}",
                f"- 来源闸门：{route['来源闸门']}",
                f"- 主失败类型：{route['主失败类型']}",
                f"- 失败位置：{route['失败位置']}",
                f"- 建议修复方向：{route['建议修复方向']}",
                f"- 接口候选模块：{route['接口候选模块']}",
                f"- 回流验收位置：{route['回流验收位置']}",
                f"- 最终状态：{route['最终状态']}",
            ]
        )

    原子写文本(md_path, "\n".join(lines) + "\n")
    return md_path, json_path, packet_path
