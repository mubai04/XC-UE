from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

L1工程 = Path(__file__).resolve().parents[1] / "L1工程"
L2工程 = Path(__file__).resolve().parents[1] / "L2工程"
for path in (L1工程, L2工程):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from L2模型 import 失败输入, 证据
from L2读取 import 读失败包完整
from 闸门规则加载 import L1闸门规则路径, 加载闸门规则
from 闸门标准解析 import L15路由规则

from L15模型 import L15路由报告, 失败快照

GATE_ORDER = {"L1-01": 1, "L1-02": 2, "L1-03": 3, "L1-SEM": 4, "L1-00": 0}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
L15_ROUTE_VERSION = "gate_rules.l15_routes"


@dataclass
class 路由候选:
    item: 失败输入
    rule: L15路由规则
    route_rule_id: str


def _快照(item: 失败输入) -> 失败快照:
    return 失败快照(
        闸门=item.来源闸门,
        名称=item.名称,
        失败类型=item.失败类型,
        说明=item.说明,
        状态=item.状态,
        严重级别=item.严重级别,
        候选模块=item.候选模块,
        回流验收位置=item.回流验收位置,
        修复方向=item.修复方向,
        证据=[{"段落": e.段落, "摘句": e.摘句} for e in item.证据],
    )


def _空快照() -> 失败快照:
    return 失败快照(闸门="", 名称="", 失败类型="", 说明="")


def _失败项(items: list[失败输入]) -> list[失败输入]:
    return [item for item in items if item.状态 == "失败" or item.严重级别 == "error"]


def _路由候选(item: 失败输入, routes: dict[str, L15路由规则]) -> 路由候选 | None:
    rule = routes.get(item.失败类型)
    if not rule:
        return None
    return 路由候选(item=item, rule=rule, route_rule_id=f"L15-{item.失败类型}")


def _排序键(candidate: 路由候选) -> tuple[int, int]:
    item = candidate.item
    severity = SEVERITY_ORDER.get(item.严重级别, 9)
    gate = GATE_ORDER.get(item.来源闸门, 99)
    return (severity, gate)


def _快照转输入(snapshot: 失败快照) -> 失败输入:
    return 失败输入(
        来源闸门=snapshot.闸门,
        名称=snapshot.名称,
        状态=snapshot.状态 or "失败",
        说明=snapshot.说明,
        证据=[证据(e.get("段落"), e.get("摘句", "")) for e in snapshot.证据],
        严重级别=snapshot.严重级别 or "error",
        失败类型=snapshot.失败类型,
        候选模块=snapshot.候选模块,
        回流验收位置=snapshot.回流验收位置,
        修复方向=snapshot.修复方向,
    )


def 执行路由(
    packet_path: Path,
    *,
    repo_root: Path,
    run_id: str,
    pipeline_run_id: str,
    stage_run_id: str,
) -> L15路由报告:
    items, meta = 读失败包完整(packet_path)
    rules = 加载闸门规则(L1闸门规则路径(repo_root))
    routes = rules.L15路由
    failures = _失败项(items)
    blockers: list[str] = []

    if not failures:
        return L15路由报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            source_failure_packet=str(packet_path),
            primary_failure=_空快照(),
            secondary_failures=[],
            target_module="",
            repair_product="",
            return_gate="",
            route_rule_id="",
            route_rule_version=L15_ROUTE_VERSION,
            final_status="RETURN_TO_L1",
            blockers=["failure packet 无失败项"],
            routing_basis="无失败项，返回 L1 复验。",
        )

    reroute_only = all(item.候选模块 in {"回L1.5", "回 L1.5", "L1", "L1-01", "L1-02", "L1-03"} for item in failures)
    if reroute_only and not any(_路由候选(item, routes) for item in failures):
        return L15路由报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            source_failure_packet=str(packet_path),
            primary_failure=_快照(failures[0]),
            secondary_failures=[_快照(item) for item in failures[1:]],
            target_module="",
            repair_product="",
            return_gate=failures[0].回流验收位置 or failures[0].来源闸门,
            route_rule_id="RETURN_TO_L1",
            route_rule_version=L15_ROUTE_VERSION,
            final_status="RETURN_TO_L1",
            blockers=["全部失败项需回 L1 或人工复核"],
            routing_basis="失败项未映射到 L2 模块。",
        )

    candidates = [c for item in failures if (c := _路由候选(item, routes))]
    unrouted = [item for item in failures if item not in [c.item for c in candidates]]

    if not candidates:
        return L15路由报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            source_failure_packet=str(packet_path),
            primary_failure=_快照(failures[0]),
            secondary_failures=[_快照(item) for item in failures[1:]],
            target_module="",
            repair_product="",
            return_gate="",
            route_rule_id="ROUTE_NOT_FOUND",
            route_rule_version=L15_ROUTE_VERSION,
            final_status="MANUAL_REVIEW",
            blockers=[f"未找到 l15_routes 映射：{item.失败类型}" for item in failures],
            routing_basis="结构化路由规则未命中任何失败项。",
        )

    if not meta.chapter_path.strip():
        return L15路由报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            source_failure_packet=str(packet_path),
            primary_failure=_快照(candidates[0].item),
            secondary_failures=[_快照(c.item) for c in candidates[1:]] + [_快照(u) for u in unrouted],
            target_module="",
            repair_product="",
            return_gate="",
            route_rule_id="INPUT_REQUIRED",
            route_rule_version=L15_ROUTE_VERSION,
            final_status="INPUT_REQUIRED",
            blockers=["failure packet.extensions.chapter_path 缺失"],
            routing_basis="L2 诊断需要章节正文路径。",
        )

    ranked = sorted(candidates, key=_排序键)
    top = ranked[0]
    same_priority = [c for c in ranked if _排序键(c) == _排序键(top)]
    modules = {c.rule.目标模块 for c in same_priority}
    if len(modules) > 1:
        return L15路由报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            source_failure_packet=str(packet_path),
            primary_failure=_快照(top.item),
            secondary_failures=[_快照(c.item) for c in ranked[1:]] + [_快照(u) for u in unrouted],
            target_module="",
            repair_product="",
            return_gate="",
            route_rule_id="ROUTE_CONFLICT",
            route_rule_version=L15_ROUTE_VERSION,
            final_status="MANUAL_REVIEW",
            blockers=[f"同优先级冲突模块：{', '.join(sorted(modules))}"],
            routing_basis="多个失败项映射到不同 L2 模块，需人工复核。",
        )

    primary = top.item
    secondary_items = [c.item for c in ranked[1:]] + unrouted
    if primary.候选模块 and primary.候选模块 not in {"", top.rule.目标模块, "回L1.5"}:
        if primary.候选模块 != top.rule.目标模块:
            return L15路由报告(
                run_id=run_id,
                pipeline_run_id=pipeline_run_id,
                stage_run_id=stage_run_id,
                source_failure_packet=str(packet_path),
                primary_failure=_快照(primary),
                secondary_failures=[_快照(item) for item in secondary_items],
                target_module=top.rule.目标模块,
                repair_product=top.rule.修复产物,
                return_gate=top.rule.回流闸门,
                route_rule_id=top.route_rule_id,
                route_rule_version=L15_ROUTE_VERSION,
                final_status="MANUAL_REVIEW",
                blockers=[f"候选模块 {primary.候选模块} 与 l15_routes {top.rule.目标模块} 冲突"],
                routing_basis="failure packet 候选模块与 gate_rules 不一致。",
            )

    enriched = _快照转输入(_快照(primary))
    enriched.候选模块 = top.rule.目标模块
    enriched.修复方向 = top.rule.修复产物
    enriched.回流验收位置 = top.rule.回流闸门

    return L15路由报告(
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id,
        source_failure_packet=str(packet_path),
        primary_failure=_快照(enriched),
        secondary_failures=[_快照(item) for item in secondary_items],
        target_module=top.rule.目标模块,
        repair_product=top.rule.修复产物,
        return_gate=top.rule.回流闸门,
        route_rule_id=top.route_rule_id,
        route_rule_version=L15_ROUTE_VERSION,
        final_status="ROUTED",
        blockers=blockers,
        routing_basis=f"主失败 {primary.失败类型} → {top.rule.目标模块}；次级 {len(secondary_items)} 项仅记录不并行执行。",
        extensions={"chapter_path": meta.chapter_path},
    )
