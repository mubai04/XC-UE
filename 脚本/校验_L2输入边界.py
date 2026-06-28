#!/usr/bin/env python3
"""L2 输入边界冻结校验（L2-BND-V2）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L2_DEF = ROOT / "40_L2_正式能力层"
BOUNDARY_MD = L2_DEF / "L2_输入与证据上下文边界.md"
RULES_JSON = ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "L2输入边界规则.json"
L2_ENTRY = ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "L2运行入口.py"
L2_BOUNDARY_PY = ROOT / "00_工程总控" / "工程执行层" / "L2工程" / "L2输入边界.py"
PIPELINE = ROOT / "00_工程总控" / "工程执行层" / "修复流水线运行入口.py"
SCHEMA_V2_DIR = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义" / "跨层契约"

MODULES = ("L2-01", "L2-02", "L2-03", "L2-04", "L2-05", "L2-06")


def _fail(msg: str) -> None:
    print(f"VALIDATION_FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    errors: list[str] = []

    if not BOUNDARY_MD.is_file():
        errors.append("缺少 L2_输入与证据上下文边界.md")
    else:
        text = BOUNDARY_MD.read_text(encoding="utf-8")
        if "L1 失败包 + L1.5 路由决策" not in text:
            errors.append("权威文档未定义 L1 失败包 + L1.5 路由决策")
        if "L2_UPSTREAM_PACKAGE_REQUIRED" not in text:
            errors.append("权威文档未定义 raw chapter-only 拒绝码")
        if "证据上下文" not in text or "修复目标上下文" not in text:
            errors.append("权威文档未定义正文/IR 地位")
        if "RETURN_TO_L1_5" not in text:
            errors.append("权威文档未定义 RETURN_TO_L1_5")
        if "INPUT_REQUIRED" not in text:
            errors.append("权威文档未定义 INPUT_REQUIRED")
        for mod in MODULES:
            if mod not in text:
                errors.append(f"权威文档缺少 {mod} 上下文矩阵")

    if not RULES_JSON.is_file():
        errors.append("缺少 L2输入边界规则.json")
    else:
        rules = json.loads(RULES_JSON.read_text(encoding="utf-8-sig"))
        if rules.get("production_runtime") != "v1":
            errors.append("production_runtime 必须为 v1")
        pi = rules.get("primary_input", {})
        if "L1_failure_packet" not in pi.get("required_objects", []):
            errors.append("机器规则未要求 L1_failure_packet")
        if "L1_5_route_report" not in pi.get("required_objects", []):
            errors.append("机器规则未要求 L1_5_route_report")
        if rules.get("context_role") != "EVIDENCE_AND_REPAIR_CONTEXT":
            errors.append("context_role 不正确")
        if rules.get("rejections", {}).get("raw_chapter_only", {}).get("code") != "L2_UPSTREAM_PACKAGE_REQUIRED":
            errors.append("raw chapter-only 拒绝码未配置")
        for mod in MODULES:
            if mod not in rules.get("modules", {}):
                errors.append(f"机器规则缺少 {mod}")
        if rules.get("legacy_entry", {}).get("failure_packet_direct") != "LEGACY_EXPLICIT_ONLY":
            errors.append("legacy 入口未标记 LEGACY_EXPLICIT_ONLY")

    if not L2_BOUNDARY_PY.is_file():
        errors.append("缺少 L2输入边界.py")
    else:
        src = L2_BOUNDARY_PY.read_text(encoding="utf-8")
        for sym in ("校验裸章节入口", "校验模块输入边界", "过滤相关角色IR", "L2阶段禁止候选正文"):
            if sym not in src:
                errors.append(f"L2输入边界.py 缺少 {sym}")

    if L2_ENTRY.is_file():
        entry = L2_ENTRY.read_text(encoding="utf-8")
        if "LEGACY_EXPLICIT_ONLY" not in entry:
            errors.append("L2运行入口未标记 LEGACY_EXPLICIT_ONLY")
        if "校验裸章节入口" not in entry:
            errors.append("L2运行入口未接入裸章节拒绝")

    if PIPELINE.is_file():
        pipe = PIPELINE.read_text(encoding="utf-8")
        if '"--l15-report"' not in pipe:
            errors.append("正式流水线未使用 --l15-report")
        l2_match = re.search(r"L2运行入口\.main,\s*\[(.*?)\]\s*,\s*\)", pipe, re.S)
        if l2_match and "--failure-packet" in l2_match.group(1):
            errors.append("正式流水线 L2 阶段不得使用 --failure-packet")

    l2_00 = L2_DEF / "L2-00_正式能力层定义_v0.2.md"
    if l2_00.is_file() and "L2_输入与证据上下文边界.md" not in l2_00.read_text(encoding="utf-8"):
        errors.append("L2-00 未引用输入边界真源")

    l2_99 = L2_DEF / "L2-99_能力层接口总表_v0.1.1_自检修正版.md"
    if l2_99.is_file() and "L2_输入与证据上下文边界.md" not in l2_99.read_text(encoding="utf-8"):
        errors.append("L2-99 未引用输入边界真源")

    fix_schema = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义" / "跨层契约" / "L2修复单结构_v2.json"
    if fix_schema.is_file():
        schema = json.loads(fix_schema.read_text(encoding="utf-8-sig"))
        reroute = schema.get("properties", {}).get("重路由请求", {}).get("properties", {})
        if reroute.get("禁止直接指定新目标模块", {}).get("const") is not True:
            errors.append("L2 修复单 schema 未禁止直接指定新目标模块")

    if SCHEMA_V2_DIR.is_dir():
        new_schemas = list(SCHEMA_V2_DIR.glob("*.json"))
        if len(new_schemas) > 20:
            errors.append("检测到异常规模的跨层 Schema 目录扩建")

    s2b2_cutover = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "跨层契约运行库"
    if s2b2_cutover.is_dir():
        for fp in s2b2_cutover.glob("*.py"):
            if "生产切换" in fp.read_text(encoding="utf-8", errors="ignore"):
                errors.append("检测到 S2B-2 生产切换代码")

    if errors:
        for e in errors:
            _fail(e)

    print("VALIDATION_OK")
    print("L2_PRIMARY_INPUT = ROUTED_FAILURE_PACKAGE")
    print("L2_CONTEXT_ROLE = EVIDENCE_AND_REPAIR_CONTEXT")


if __name__ == "__main__":
    main()
