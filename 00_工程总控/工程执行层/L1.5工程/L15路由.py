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

from L15模型 import L15路由报告, 失败快照
from L15路由规则加载 import L15路由条目, L15路由规则错误, L15路由规则集, 加载L15路由规则
from 运行状态 import 审计阻断, 机器初筛通过, SCREENING_REVIEW

GATE_ORDER = {"L1-01": 1, "L1-02": 2, "L1-03": 3, "L1-SEM": 4, "L1-00": 0}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class 路由候选:
    item: 失败输入
    rule: L15路由条目
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


def _可路由项(items: list[失败输入]) -> list[失败输入]:
    return [item for item in items if item.routeable]


def _失败项(items: list[失败输入]) -> list[失败输入]:
    return _可路由项(items)


def _查找路由(item: 失败输入, rule_set: L15路由规则集) -> L15路由条目 | None:
    return rule_set.routes.get((item.来源闸门, item.失败类型))


def _路由候选(item: 失败输入, rule_set: L15路由规则集) -> 路由候选 | None:
    entry = _查找路由(item, rule_set)
    if not entry or entry.route_action != "ROUTE_TO_L2":
        return None
    return 路由候选(item=item, rule=entry, route_rule_id=entry.route_id)


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


def _规则元数据(rule_set: L15路由规则集) -> dict[str, str]:
    return {
        "routing_rules_path": rule_set.rules_path,
        "routing_rules_schema_version": rule_set.schema_version,
    }


def _阻断报告(
    *,
    run_id: str,
    pipeline_run_id: str,
    stage_run_id: str,
    packet_path: Path,
    rule_set: L15路由规则集 | None,
    code: str,
    message: str,
    primary: 失败快照 | None = None,
) -> L15路由报告:
    meta = _规则元数据(rule_set) if rule_set else {}
    return L15路由报告(
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id,
        source_failure_packet=str(packet_path),
        primary_failure=primary or _空快照(),
        secondary_failures=[],
        target_module="",
        repair_product="",
        return_gate="",
        route_rule_id=code,
        route_rule_version=rule_set.schema_version if rule_set else "",
        final_status="BLOCKED",
        blockers=[message],
        routing_basis=message,
        extensions=meta,
    )


def 执行路由(
    packet_path: Path,
    *,
    repo_root: Path,
    run_id: str,
    pipeline_run_id: str,
    stage_run_id: str,
) -> L15路由报告:
    try:
        rule_set = 加载L15路由规则(repo_root)
    except L15路由规则错误 as exc:
        return _阻断报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            packet_path=packet_path,
            rule_set=None,
            code=exc.code,
            message=exc.message,
        )

    items, meta = 读失败包完整(packet_path)
    meta_ext = _规则元数据(rule_set)

    if meta.status == 审计阻断:
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
            route_rule_id="AUDIT_BLOCKED",
            route_rule_version=rule_set.schema_version,
            final_status="BLOCKED",
            blockers=["L1 状态为 AUDIT_BLOCKED，禁止进入内容路由"],
            routing_basis="审计阻断，不进入 L2 内容修复。",
            extensions={**meta_ext, "route_action": "AUDIT_BLOCKED"},
        )

    if meta.status == 机器初筛通过:
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
            route_rule_id="SCREENING_PASS",
            route_rule_version=rule_set.schema_version,
            final_status="RETURN_TO_L1",
            blockers=["SCREENING_PASS 不生成内容修复包"],
            routing_basis="无内容修复项。",
            extensions={**meta_ext, "route_action": "SCREENING_PASS"},
        )

    mapped_all = [(item, _查找路由(item, rule_set)) for item in items]
    input_required_all = [
        item
        for item, entry in mapped_all
        if (entry and entry.route_action == "INPUT_REQUIRED") or item.失败类型 == "输入不足"
    ]
    if input_required_all or not meta.chapter_path.strip():
        primary = input_required_all[0] if input_required_all else items[0]
        entry = _查找路由(primary, rule_set)
        return L15路由报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            source_failure_packet=str(packet_path),
            primary_failure=_快照(primary),
            secondary_failures=[_快照(item) for item in items if item != primary],
            target_module="",
            repair_product=entry.repair_product if entry else "",
            return_gate=entry.return_gate if entry else "",
            route_rule_id=entry.route_id if entry else "INPUT_REQUIRED",
            route_rule_version=rule_set.schema_version,
            final_status="INPUT_REQUIRED",
            blockers=["failure packet.extensions.chapter_path 缺失"] if not meta.chapter_path.strip() else ["输入不足"],
            routing_basis="需要补输入或章节路径。",
            extensions={**meta_ext, "route_action": "INPUT_REQUIRED"},
        )

    blocked_all = [item for item, entry in mapped_all if entry and entry.route_action == "BLOCKED_TECHNICAL"]
    if blocked_all:
        primary = blocked_all[0]
        entry = _查找路由(primary, rule_set)
        return L15路由报告(
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            stage_run_id=stage_run_id,
            source_failure_packet=str(packet_path),
            primary_failure=_快照(primary),
            secondary_failures=[_快照(item) for item in items if item != primary],
            target_module="",
            repair_product=entry.repair_product if entry else "",
            return_gate=entry.return_gate if entry else "",
            route_rule_id=entry.route_id if entry else "BLOCKED_TECHNICAL",
            route_rule_version=rule_set.schema_version,
            final_status="BLOCKED",
            blockers=[f"工程技术阻断：{primary.失败类型}"],
            routing_basis="命中 BLOCKED_TECHNICAL，不进入 L2。",
            extensions={**meta_ext, "route_action": "BLOCKED_TECHNICAL"},
        )

    failures = _失败项(items)

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
            route_rule_id="RETURN_TO_L1",
            route_rule_version=rule_set.schema_version,
            final_status="RETURN_TO_L1",
            blockers=["failure packet 无失败项"],
            routing_basis="无失败项，返回 L1 复验。",
            extensions=meta_ext,
        )

    mapped = [(item, _查找路由(item, rule_set)) for item in failures]

    reroute_only = all(
        item.候选模块 in {"回L1.5", "回 L1.5", "L1", "L1-01", "L1-02", "L1-03"}
        for item in failures
    )
    if reroute_only and not any(_路由候选(item, rule_set) for item in failures):
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
            route_rule_version=rule_set.schema_version,
            final_status="RETURN_TO_L1",
            blockers=["全部失败项需回 L1 或人工复核"],
            routing_basis="失败项未映射到 L2 模块。",
            extensions={**meta_ext, "route_action": "RETURN_TO_L1"},
        )

    manual = [item for item, entry in mapped if entry and entry.route_action == "MANUAL_REVIEW"]
    candidates = [c for item in failures if (c := _路由候选(item, rule_set))]
    unrouted = [item for item in failures if item not in [c.item for c in candidates]]

    if not candidates:
        if manual:
            entry = _查找路由(manual[0], rule_set)
            return L15路由报告(
                run_id=run_id,
                pipeline_run_id=pipeline_run_id,
                stage_run_id=stage_run_id,
                source_failure_packet=str(packet_path),
                primary_failure=_快照(manual[0]),
                secondary_failures=[_快照(item) for item in failures[1:]],
                target_module="",
                repair_product=entry.repair_product if entry else "",
                return_gate=entry.return_gate if entry else "",
                route_rule_id=entry.route_id if entry else "MANUAL_REVIEW",
                route_rule_version=rule_set.schema_version,
                final_status="MANUAL_REVIEW",
                blockers=[f"需人工复核：{manual[0].失败类型}"],
                routing_basis="命中 MANUAL_REVIEW。",
                extensions={**meta_ext, "route_action": "MANUAL_REVIEW"},
            )
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
            route_rule_version=rule_set.schema_version,
            final_status="RETURN_TO_L1",
            blockers=[f"未匹配路由规则：{item.来源闸门}/{item.失败类型}" for item in unrouted],
            routing_basis="未匹配项按 default_unmatched_action 返回 L1。",
            extensions={**meta_ext, "route_action": rule_set.default_unmatched_action},
        )

    ranked = sorted(candidates, key=_排序键)
    top = ranked[0]
    same_priority = [c for c in ranked if _排序键(c) == _排序键(top)]
    modules = {c.rule.target_module for c in same_priority if c.rule.target_module}
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
            route_rule_version=rule_set.schema_version,
            final_status="MANUAL_REVIEW",
            blockers=[f"同优先级冲突模块：{', '.join(sorted(modules))}"],
            routing_basis="多个失败项映射到不同 L2 模块，需人工复核。",
            extensions=meta_ext,
        )

    primary = top.item
    secondary_items = [c.item for c in ranked[1:]] + unrouted
    if primary.候选模块 and primary.候选模块 not in {"", top.rule.target_module or "", "回L1.5"}:
        if primary.候选模块 != top.rule.target_module:
            return L15路由报告(
                run_id=run_id,
                pipeline_run_id=pipeline_run_id,
                stage_run_id=stage_run_id,
                source_failure_packet=str(packet_path),
                primary_failure=_快照(primary),
                secondary_failures=[_快照(item) for item in secondary_items],
                target_module=top.rule.target_module or "",
                repair_product=top.rule.repair_product,
                return_gate=top.rule.return_gate,
                route_rule_id=top.route_rule_id,
                route_rule_version=rule_set.schema_version,
                final_status="MANUAL_REVIEW",
                blockers=[f"候选模块 {primary.候选模块} 与路由规则 {top.rule.target_module} 冲突"],
                routing_basis="failure packet 候选模块与 L1.5 路由规则不一致。",
                extensions={**meta_ext, "route_action": "ROUTE_TO_L2"},
            )

    enriched = _快照转输入(_快照(primary))
    enriched.候选模块 = top.rule.target_module or ""
    enriched.修复方向 = top.rule.repair_product
    enriched.回流验收位置 = top.rule.return_gate

    return L15路由报告(
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        stage_run_id=stage_run_id,
        source_failure_packet=str(packet_path),
        primary_failure=_快照(enriched),
        secondary_failures=[_快照(item) for item in secondary_items],
        target_module=top.rule.target_module or "",
        repair_product=top.rule.repair_product,
        return_gate=top.rule.return_gate,
        route_rule_id=top.route_rule_id,
        route_rule_version=rule_set.schema_version,
        final_status="ROUTED",
        blockers=[],
        routing_basis=f"主失败 {primary.失败类型} → {top.rule.target_module}；次级 {len(secondary_items)} 项仅记录不并行执行。",
        extensions={**meta_ext, "route_action": "ROUTE_TO_L2", "chapter_path": meta.chapter_path},
    )
