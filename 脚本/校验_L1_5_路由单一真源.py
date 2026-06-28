#!/usr/bin/env python3
"""校验 L1.5 路由单一真源（D-SYS-03 S1A）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L15_DIR = ROOT / "00_工程总控" / "工程执行层" / "L1.5工程"
L1_DIR = ROOT / "00_工程总控" / "工程执行层" / "L1工程"
L2_DIR = ROOT / "00_工程总控" / "工程执行层" / "L2工程"
PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
for path in (PUBLIC, L1_DIR, L2_DIR, L15_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from L15路由规则加载 import 加载L15路由规则, L15路由规则错误  # noqa: E402
from 闸门规则加载 import L1闸门规则路径, 加载闸门规则  # noqa: E402

MATRIX = ROOT / "30_L1.5_路由矩阵层" / "L1.5_Routing_Matrix.md"
L15_ROUTE_PY = ROOT / "00_工程总控" / "工程执行层" / "L1.5工程" / "L15路由.py"
L2_ROUTES = ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "routes.json"
L2_99 = ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "L2_99_接口判断.py"


def _fail(msg: str) -> None:
    print(msg)
    sys.exit(1)


def main() -> None:
    errors: list[str] = []

    try:
        rule_set = 加载L15路由规则(ROOT)
    except L15路由规则错误 as exc:
        _fail(f"路由规则加载失败：{exc.code} {exc.message}")

    gate_path = L1闸门规则路径(ROOT)
    gate_raw = json.loads(gate_path.read_text(encoding="utf-8-sig"))
    if "l15_routes" in gate_raw:
        errors.append("gate_rules.json 仍包含 l15_routes")

    try:
        加载闸门规则(gate_path)
    except Exception as exc:
        errors.append(f"gate_rules 加载失败：{exc}")

    for gate_key in ["L1-01", "L1-02"]:
        for failure_type in gate_raw["gates"][gate_key]["failure_types"]:
            if (gate_key, failure_type) not in rule_set.routes:
                errors.append(f"L1 已声明失败类型未覆盖：{gate_key}/{failure_type}")

    l1_03_types = [
        "字数不足",
        "字数超出默认发布体量",
        "当章收益不足",
        "章末追读弱",
        "认知成本过高",
        "功能锁失败",
    ]
    for failure_type in l1_03_types:
        if ("L1-03", failure_type) not in rule_set.routes:
            errors.append(f"L1-03 常见失败类型未覆盖：{failure_type}")

    matrix_text = MATRIX.read_text(encoding="utf-8")
    if "| 文风失败" in matrix_text and "待建 L2" in matrix_text:
        errors.append("Matrix 仍含旧版具体路由表（待建 L2 + 表格行）")

    l15_src = L15_ROUTE_PY.read_text(encoding="utf-8")
    if "l15_routes" in l15_src or "加载闸门规则" in l15_src:
        errors.append("L15路由.py 仍引用 gate_rules/l15_routes")
    if "routes.json" in l15_src:
        errors.append("L15路由.py 仍引用 L2 routes.json")
    if "加载L15路由规则" not in l15_src:
        errors.append("L15路由.py 未通过 加载L15路由规则 读取正式路由")

    routes_raw = json.loads(L2_ROUTES.read_text(encoding="utf-8-sig"))
    if routes_raw.get("routing_authority") != "DEPRECATED_NOT_ROUTING_AUTHORITY":
        errors.append("L2 routes.json 未标记 DEPRECATED_NOT_ROUTING_AUTHORITY")

    c_high_l02 = rule_set.routes.get(("L1-02", "C高：认知成本过高"))
    c_high_l03 = rule_set.routes.get(("L1-03", "认知成本过高"))
    if not c_high_l02 or c_high_l02.target_module != "L2-05":
        errors.append("L1-02 C高：认知成本过高 未路由到 L2-05")
    if not c_high_l03 or c_high_l03.target_module != "L2-02":
        errors.append("L1-03 认知成本过高 未路由到 L2-02")

    chapter_l02 = rule_set.routes.get(("L1-02", "章末弱"))
    chapter_l03 = rule_set.routes.get(("L1-03", "章末追读弱"))
    if not chapter_l02 or chapter_l02.target_module != "L2-05":
        errors.append("L1-02 章末弱 未路由到 L2-05")
    if not chapter_l03 or chapter_l03.target_module != "L2-05":
        errors.append("L1-03 章末追读弱 未路由到 L2-05")

    tech = rule_set.routes.get(("L1-01", "技术护栏失败"))
    if not tech or tech.route_action != "BLOCKED_TECHNICAL":
        errors.append("L1-01 技术护栏失败 未标记 BLOCKED_TECHNICAL")
    if tech and tech.target_module:
        errors.append("技术护栏失败 不得带 target_module")

    fact = rule_set.routes.get(("L1-01", "前后事实冲突"))
    if not fact or fact.target_module != "L2-06":
        errors.append("故事内部前后事实冲突 未路由到 L2-06")

    if errors:
        for item in errors:
            print(f"ERROR: {item}")
        sys.exit(1)

    print("VALIDATION_OK")


if __name__ == "__main__":
    main()
