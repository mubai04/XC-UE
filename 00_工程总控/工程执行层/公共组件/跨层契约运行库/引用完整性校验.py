from __future__ import annotations

from typing import Any

from 迁移模型 import 迁移上下文


def 校验引用链(
    *,
    l1_packet: dict[str, Any] | None,
    l15: dict[str, Any] | None,
    l2_report: dict[str, Any] | None,
    l3_task: dict[str, Any] | None,
    l3_result: dict[str, Any] | None,
    ctx: 迁移上下文,
) -> list[str]:
    errors: list[str] = []
    pipeline = ctx.pipeline_run_id
    finding_ids: set[str] = set()
    fix_ids: set[str] = set()

    if l1_packet:
        for item in l1_packet.get("发现项列表") or []:
            fid = item.get("L1发现编号", "")
            if fid in finding_ids:
                errors.append(f"重复 L1发现编号：{fid}")
            finding_ids.add(fid)
            if pipeline not in fid:
                errors.append(f"L1发现编号跨 pipeline：{fid}")

    if l15:
        main = l15.get("主发现引用", {})
        mid = main.get("对象编号", "")
        if mid and mid not in finding_ids:
            errors.append(f"悬空主发现引用：{mid}")
        if l1_packet and l15.get("来源失败包编号") != l1_packet.get("L1失败包编号"):
            errors.append("L1.5 来源失败包编号不匹配")
        if l15.get("路由状态") != "ROUTED" and l15.get("目标模块"):
            errors.append("非 ROUTED 携带目标模块")
        if l15.get("路由状态") == "ROUTED" and not l15.get("目标模块"):
            errors.append("ROUTED 缺少目标模块")

    if l2_report:
        if l15 and l2_report.get("来源路由决策编号") != l15.get("L1_5路由决策编号"):
            errors.append("L2 来源路由决策编号不匹配")
        for form in l2_report.get("修复单列表") or []:
            fid = form.get("L2修复单编号", "")
            fix_ids.add(fid)
            ref = form.get("来源发现引用", {}).get("对象编号", "")
            if ref and ref not in finding_ids:
                errors.append(f"L2 悬空来源发现引用：{ref}")
            if l15 and form.get("接收模块") != l15.get("目标模块"):
                errors.append("L2 接收模块与 L1.5 目标模块不一致")

    if l3_task:
        if l2_report and l3_task.get("来源L2报告编号") != l2_report.get("L2报告编号"):
            errors.append("L3 来源L2报告编号不匹配")
        prot = l3_task.get("正式正文保护", {})
        if prot.get("允许修改") is not False:
            errors.append("正式正文保护未启用")
        fix_ref = l3_task.get("来源修复单编号", "")
        if fix_ref and fix_ref not in fix_ids:
            errors.append(f"L3 悬空来源修复单：{fix_ref}")
        for task in l3_task.get("任务列表") or []:
            if task.get("关联修复单编号") not in fix_ids:
                errors.append("任务缺少有效修复单引用")

    if l3_result:
        if l3_task and l3_result.get("来源执行任务包编号") != l3_task.get("L3执行任务包编号"):
            errors.append("L3 执行结果来源任务包编号不匹配")
        for art in l3_result.get("候选产物列表") or []:
            if art.get("来源修复单编号") not in fix_ids:
                errors.append("候选产物缺少有效修复单引用")
            if art.get("是否修改正式正文"):
                errors.append("候选产物标记修改正式正文")

    return errors
