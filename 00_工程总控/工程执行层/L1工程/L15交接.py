from __future__ import annotations

from L1模型 import 检测项
from 闸门标准解析 import L15路由规则


def 补路由(item: 检测项, routes: dict[str, L15路由规则]) -> 检测项:
    rule = routes.get(item.失败类型)
    if rule:
        item.候选模块 = rule.目标模块
        item.修复方向 = rule.修复产物
        item.回流验收位置 = rule.回流闸门
    return item


def 生成路由建议(items: list[检测项], routes: dict[str, L15路由规则]) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    for idx, item in enumerate(items, start=1):
        补路由(item, routes)
        suggestions.append(
            {
                "路由编号": f"L15-{item.闸门.replace('-', '')}-{idx:03d}",
                "来源闸门": item.闸门,
                "主失败类型": item.失败类型,
                "失败位置": "；".join(f"P{e.段落}:{e.摘句}" for e in item.证据),
                "作业场景": item.名称,
                "建议修复方向": item.修复方向 or "人工复核",
                "接口候选模块": item.候选模块 or "回L1.5",
                "回流验收位置": item.回流验收位置 or item.闸门,
                "最终状态": "已路由" if item.候选模块 else "需要人工复核",
            }
        )
    return suggestions
