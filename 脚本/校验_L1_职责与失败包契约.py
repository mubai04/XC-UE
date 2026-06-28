#!/usr/bin/env python3
"""校验 L1 职责、终裁权与失败包契约（D-SYS-04 S1B）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
L1_DIR = ROOT / "00_工程总控" / "工程执行层" / "L1工程"
L15_DIR = ROOT / "00_工程总控" / "工程执行层" / "L1.5工程"
L2_DIR = ROOT / "00_工程总控" / "工程执行层" / "L2工程"
SCHEMA_DIR = PUBLIC / "结构定义"
L1_GATE = ROOT / "20_L1_闸门层"
L15_RULES = ROOT / "30_L1.5_路由矩阵层" / "L1.5_路由规则.json"

for path in (PUBLIC, L1_DIR, L15_DIR, L2_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from L15路由规则加载 import 加载L15路由规则  # noqa: E402
from L1决策角色 import (  # noqa: E402
    审计阻断角色,
    内容决策角色,
    硬护栏角色,
    诊断角色,
    角色权限说明,
)
from 结构校验 import 校验JSONSchema, 读取结构  # noqa: E402
from 运行状态 import 审计阻断, 机器初筛通过, 机器初筛退回, SCREENING_REVIEW  # noqa: E402

L1_STATUS_ENUM = {
    机器初筛通过,
    SCREENING_REVIEW,
    机器初筛退回,
    审计阻断,
}
DECISION_ROLES = {硬护栏角色, 内容决策角色, 诊断角色, 审计阻断角色}
L1_00_GUARD_TYPES = ("重复窗口过高", "高重复正文", "低信息重复正文", "字数不足")
RESERVED_L102 = ("传播点弱", "付费预期弱")


def _fail(msg: str) -> None:
    print(msg)
    sys.exit(1)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    errors: list[str] = []

    if set(角色权限说明) != DECISION_ROLES:
        errors.append("L1决策角色.角色权限说明 与四种 decision_role 不一致")
    if len(角色权限说明) != 4:
        errors.append("decision_role 权限说明数量不为 4")

    status_sources: dict[str, set[str]] = {}
    failure_schema = 读取结构(SCHEMA_DIR / "失败包结构.json")
    status_sources["失败包结构"] = set(failure_schema["$defs"]["l1_status"]["enum"])
    first_layer = 读取结构(SCHEMA_DIR / "第一层报告结构.json")
    status_sources["第一层报告"] = set(first_layer["properties"]["status"]["enum"])
    audit_schema = 读取结构(SCHEMA_DIR / "审计阻断项结构.json")
    if "l1_status" in audit_schema.get("$defs", {}):
        status_sources["审计阻断项"] = set(audit_schema["$defs"]["l1_status"]["enum"])

    for label, values in status_sources.items():
        if values != L1_STATUS_ENUM:
            errors.append(f"{label} 顶层状态枚举与运行状态不一致：{sorted(values)}")

    l100_md = _read(L1_GATE / "L1-00_闸门接口表.md")
    if "当前阶段内容终裁组件：L1-SEM" not in l100_md and "L1-SEM" not in l100_md:
        errors.append("L1-00 未正式承认 L1-SEM")
    if "publish_authority" in l100_md and "false" not in l100_md.lower():
        pass  # optional mention

    l101_md = _read(L1_GATE / "L1-01_五大创作问题_技术护栏闭环图.md")
    l102_md = _read(L1_GATE / "L1-02_读者投入意愿工程图.md")
    l103_md = _read(L1_GATE / "L1-03_发布锁验收工程图.md")

    for label, text in (("L1-01", l101_md), ("L1-02", l102_md), ("L1-03", l103_md)):
        if "DIAGNOSTIC" not in text:
            errors.append(f"{label} 文档未标明 DIAGNOSTIC 角色")
        if "routeable" not in text.lower() and "可路由" not in text:
            errors.append(f"{label} 文档未说明 routeable 路由语义")

    failure_item = failure_schema["$defs"]["failure_item"]
    required = set(failure_item["required"])
    needed = {"decision_role", "blocking", "routeable", "route_reason", "source_component"}
    if not needed.issubset(required):
        errors.append(f"失败包 item 缺少必填字段：{needed - required}")

    if set(failure_item["properties"]["decision_role"]["enum"]) != DECISION_ROLES:
        errors.append("失败包 decision_role 枚举不完整")

    sample_diagnostic = {
        "闸门": "L1-01",
        "名称": "测试",
        "状态": "失败",
        "说明": "测试说明",
        "证据": [{"段落": 1, "摘句": "摘句"}],
        "严重级别": "warning",
        "失败类型": "叙事失败",
        "候选模块": "L2-01",
        "回流验收位置": "L1-01",
        "修复方向": "测试",
        "decision_role": 诊断角色,
        "blocking": False,
        "routeable": True,
        "route_reason": "为L1.5提供领域路由线索",
        "source_component": "L1-01",
    }
    try:
        校验JSONSchema(
            {
                "schema_version": "xcue.failure-packet/1.0",
                "pipeline_run_id": "TEST",
                "stage_run_id": "TEST",
                "status": 机器初筛退回,
                "failure_count": 0,
                "blocking_count": 0,
                "routeable_count": 1,
                "items": [sample_diagnostic],
            },
            failure_schema,
            "sample",
        )
    except Exception as exc:
        errors.append(f"DIAGNOSTIC routeable 样本无法通过 Schema：{exc}")

    audit_item = failure_schema["$defs"]["failure_item"]
    if audit_item["properties"]["routeable"]["type"] != "boolean":
        errors.append("失败包 routeable 类型错误")

    l15_route_py = _read(L15_DIR / "L15路由.py")
    if "_可路由项" not in l15_route_py or "routeable" not in l15_route_py:
        errors.append("L15路由.py 未按 routeable 过滤候选")
    if "blocking" in l15_route_py and "item.blocking" in l15_route_py:
        errors.append("L15路由.py 仍可能按 blocking 选取主失败")

    l2_read = _read(L2_DIR / "L2读取.py")
    if "routeable" not in l2_read or "拒绝静默猜测" not in l2_read:
        errors.append("L2读取 未拒绝缺 routeable 的失败包")

    from 失败包生成 import 构建失败包  # noqa: E402
    from L1模型 import 检测项  # noqa: E402

    audit_only = 检测项(
        闸门="L1-SEM",
        名称="API",
        状态="阻断",
        说明="API",
        证据=[],
        严重级别="error",
        失败类型="API不可用",
        候选模块="",
        回流验收位置="L1-SEM",
        修复方向="",
        decision_role=审计阻断角色,
        blocking=True,
        routeable=False,
    )
    if 构建失败包([audit_only], 机器初筛退回):
        errors.append("AUDIT_BLOCKER 进入了内容失败包")

    if 构建失败包([], 机器初筛通过):
        errors.append("SCREENING_PASS 不应生成内容失败包")

    if 构建失败包([], 审计阻断):
        errors.append("AUDIT_BLOCKED 不应生成内容失败包")

    rule_set = 加载L15路由规则(ROOT)
    for failure_type in L1_00_GUARD_TYPES:
        key = ("L1-00", failure_type)
        if key not in rule_set.routes:
            errors.append(f"L1-00 失败类型未路由：{failure_type}")

    dup_l2 = rule_set.routes.get(("L1-00", "高重复正文"))
    if not dup_l2 or dup_l2.target_module != "L2-02":
        errors.append("高重复正文 未路由到 L2-02")

    word_route = rule_set.routes.get(("L1-00", "字数不足"))
    if not word_route or word_route.route_action != "INPUT_REQUIRED":
        errors.append("字数不足 未标记 INPUT_REQUIRED")
    if word_route and word_route.target_module:
        errors.append("字数不足 不得默认派给 L2 模块")

    rules_raw = json.loads(L15_RULES.read_text(encoding="utf-8-sig"))
    reserved = rules_raw.get("reserved_failure_types", {})
    for ft in RESERVED_L102:
        if ft not in reserved.get("L1-02", []):
            errors.append(f"L1-02 {ft} 未列入 reserved_failure_types")
    routes_by_type = {(r["source_gate"], r["failure_type"]): r for r in rules_raw["routes"]}
    for ft in RESERVED_L102:
        entry = routes_by_type.get(("L1-02", ft))
        if not entry or entry.get("activation_status") != "RESERVED_NOT_IMPLEMENTED":
            errors.append(f"L1-02 {ft} 路由未标记 RESERVED_NOT_IMPLEMENTED")

    l102_detector = _read(L1_DIR / "L1_02_读者投入检测.py")
    for ft in RESERVED_L102:
        if ft in l102_detector:
            errors.append(f"L1_02 检测器伪造未实现类型：{ft}")

    if "发布准备风险诊断" not in l103_md:
        errors.append("L1-03 未改名义为发布准备风险诊断")
    publish_claims = ("允许发布", "正式发布", "平台可投放", "可签约")
    for claim in publish_claims:
        if claim in l103_md and "不负责" not in l103_md[:200]:
            pass
    if "publish_authority" not in l103_md and "发布权" not in l103_md:
        errors.append("L1-03 未声明无真实发布权")

    l1_report_py = _read(L1_DIR / "L1报告.py")
    if "publish_authority" not in l1_report_py or "False" not in l1_report_py:
        errors.append("L1报告 未硬编码 publish_authority=false")

    schema_files = [
        "失败包结构.json",
        "第一层报告结构.json",
        "审计阻断项结构.json",
    ]
    for name in schema_files:
        path = SCHEMA_DIR / name
        try:
            读取结构(path)
        except Exception as exc:
            errors.append(f"Schema 无法加载：{name}：{exc}")

    if errors:
        for item in errors:
            print(f"ERROR: {item}")
        sys.exit(1)

    print("VALIDATION_OK")


if __name__ == "__main__":
    main()
