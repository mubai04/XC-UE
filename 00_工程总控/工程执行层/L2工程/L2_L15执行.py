from __future__ import annotations

import json
from pathlib import Path

from L2模型 import 失败输入, 接口判断, 证据
from L2读取 import 读失败包完整
from L15模型 import 失败快照


def 读L15报告(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def 快照转输入(snapshot: dict) -> 失败输入:
    evidence = [证据(e.get("段落"), e.get("摘句", "")) for e in snapshot.get("证据", [])]
    return 失败输入(
        来源闸门=snapshot.get("闸门", ""),
        名称=snapshot.get("名称", ""),
        状态=snapshot.get("状态", "失败"),
        说明=snapshot.get("说明", ""),
        证据=evidence,
        严重级别=snapshot.get("严重级别", "error"),
        失败类型=snapshot.get("失败类型", ""),
        候选模块=snapshot.get("候选模块", ""),
        回流验收位置=snapshot.get("回流验收位置", ""),
        修复方向=snapshot.get("修复方向", ""),
    )


def 从L15报告提取执行上下文(
    l15_report_path: Path,
) -> tuple[失败输入, str, str, str, list[str]]:
    report = 读L15报告(l15_report_path)
    final_status = str(report.get("final_status", ""))
    blockers = [str(item) for item in report.get("blockers", []) if str(item).strip()]
    if final_status != "ROUTED":
        return 失败输入("", "", "", "", [], "", "", "", "", ""), "", "", final_status, blockers

    target_module = str(report.get("target_module", "")).strip()
    primary = report.get("primary_failure") or {}
    item = 快照转输入(primary)
    item.候选模块 = target_module
    item.修复方向 = str(report.get("repair_product", item.修复方向))
    item.回流验收位置 = str(report.get("return_gate", item.回流验收位置))

    packet_path = str(report.get("source_failure_packet", "")).strip()
    _, meta = 读失败包完整(Path(packet_path))
    chapter_path = str((report.get("extensions") or {}).get("chapter_path") or meta.chapter_path).strip()
    return item, chapter_path, target_module, final_status, blockers


def 构建L15分配判断(item: 失败输入, target_module: str, route_rule_id: str, route_rule_version: str) -> 接口判断:
    return 接口判断(
        来源闸门=item.来源闸门,
        输入来源模式="L1.5路由报告",
        输入问题=item.说明,
        初步归属=target_module,
        主候选模块=target_module,
        判断依据=f"L1.5 已分配唯一主路由 {target_module}，L2 不再重新裁决。",
        建议动作=[f"执行 {target_module}"],
        回流验收位置=item.回流验收位置 or item.来源闸门,
        最终状态="接口明确",
        route_rule_id=route_rule_id or "L15_ASSIGNED",
        route_rule_version=route_rule_version or "L1.5",
    )
