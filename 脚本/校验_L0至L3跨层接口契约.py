#!/usr/bin/env python3
"""校验 L0 至 L3 跨层接口契约（D-SYS-05 S2A）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MD = ROOT / "00_工程总控" / "跨层接口契约"
SCHEMA_V2_DIR = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义" / "跨层契约"
SCHEMA_V1_DIR = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义"
MIGRATION_MD = CONTRACT_MD / "02_旧字段迁移映射表.md"
AUDIT_COLLISION = (
    ROOT / "审计纠偏_2026-06-26" / "L0_L3_全系统定义与实现审计_20260628" / "09_字段语义冲突清单.md"
)

V2_SCHEMAS = [
    "公共引用结构_v1.json",
    "L1发现项结构_v2.json",
    "L1失败包结构_v2.json",
    "L1_5路由决策结构_v2.json",
    "L2修复单结构_v2.json",
    "L2报告结构_v2.json",
    "L3执行任务包结构_v2.json",
    "L3执行结果结构_v2.json",
]

V1_FINGERPRINTS = {
    "失败包结构.json": "xcue.schema/failure-packet/1.0",
    "L1.5路由报告结构.json": "xcue.schema/l15-route-report/1.0",
    "第二层报告结构.json": "xcue.schema/l2-report/1.0",
    "第三层任务包结构.json": "xcue.schema/l3-task-bundle/1.0",
    "第一层报告结构.json": "xcue.schema/l1-report/1.0",
    "审计阻断项结构.json": "xcue.schema/audit-blockers/1.0",
}

SFC_IDS = [f"SFC-{i:02d}" for i in range(1, 16)]

FORBIDDEN_V2_ROOT_FIELDS = {"status", "最终状态", "处理状态", "primary_failure", "rule_source"}

PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
if str(PUBLIC) not in sys.path:
    sys.path.insert(0, str(PUBLIC))

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def _fail(msg: str) -> None:
    print(msg)
    sys.exit(1)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _collect_property_names(schema: dict, names: set[str]) -> None:
    if not isinstance(schema, dict):
        return
    props = schema.get("properties")
    if isinstance(props, dict):
        names.update(props.keys())
    for key in ("$defs", "definitions", "allOf", "anyOf", "oneOf"):
        sub = schema.get(key)
        if isinstance(sub, dict):
            for item in sub.values():
                if isinstance(item, dict):
                    _collect_property_names(item, names)
        elif isinstance(sub, list):
            for item in sub:
                if isinstance(item, dict):
                    _collect_property_names(item, names)
    items = schema.get("items")
    if isinstance(items, dict):
        _collect_property_names(items, names)


COMMON_URI = "xcue://schemas/cross-layer/common-reference/v1"

SCHEMA_URI_BY_FILE = {
    "公共引用结构_v1.json": COMMON_URI,
    "L1发现项结构_v2.json": "xcue://schemas/cross-layer/l1-finding/v2",
    "L1失败包结构_v2.json": "xcue://schemas/cross-layer/l1-failure-packet/v2",
    "L1_5路由决策结构_v2.json": "xcue://schemas/cross-layer/l15-route-decision/v2",
    "L2修复单结构_v2.json": "xcue://schemas/cross-layer/l2-fix-form/v2",
    "L2报告结构_v2.json": "xcue://schemas/cross-layer/l2-report/v2",
    "L3执行任务包结构_v2.json": "xcue://schemas/cross-layer/l3-task-bundle/v2",
    "L3执行结果结构_v2.json": "xcue://schemas/cross-layer/l3-execution-result/v2",
}


def _build_registry() -> Registry:
    resources: list[tuple[str, Resource]] = []
    seen: set[str] = set()
    for name in V2_SCHEMAS:
        data = _load_json(SCHEMA_V2_DIR / name)
        uri = data["$id"]
        if uri in seen:
            raise ValueError(f"重复 $id：{uri}")
        seen.add(uri)
        Draft202012Validator.check_schema(data)
        resources.append((uri, Resource.from_contents(data)))
    return Registry().with_resources(resources)


def _evidence(eid: str = "EV-001") -> dict:
    return {
        "证据编号": eid,
        "来源类型": "CHAPTER",
        "来源路径": "chapters/demo.md",
        "段落编号": 2,
        "行号范围": {"起始行": 5, "结束行": 8},
        "逐字摘句": "示例摘句。",
        "证据用途": "SCREENING",
    }


def _positive_fixtures() -> list[tuple[str, dict]]:
    return [
        (
            "L1发现项结构_v2.json",
            {
                "schema_version": "xcue.l1-finding/2.0",
                "L1发现编号": "L1F-T-001",
                "来源闸门": "L1-01",
                "来源组件": "L1-01",
                "发现名称": "测试",
                "发现状态": "失败",
                "L1问题域": "文风",
                "L1失败类型": "文风失败",
                "说明": "说明",
                "证据引用": [_evidence()],
                "严重级别": "warning",
                "decision_role": "DIAGNOSTIC",
                "blocking": False,
                "routeable": True,
                "route_reason": "r",
                "候选模块提示": "",
                "修复提示": "",
                "回流闸门": {"回流闸门": "L1-01"},
            },
        ),
        (
            "L1_5路由决策结构_v2.json",
            {
                "schema_version": "xcue.l15-route-decision/2.0",
                "L1_5路由决策编号": "L15R-T-001",
                "来源失败包编号": "L1P-T-001",
                "主发现引用": {"对象类型": "L1发现项", "对象编号": "L1F-T-001"},
                "次级发现引用": [],
                "路由规则编号": "L15-R002",
                "路由动作": "ROUTE_TO_L2",
                "目标模块": "L2-02",
                "修复产物类型": "文风语言修复单",
                "回流闸门": {"回流闸门": "L1-01"},
                "路由原因": "测试",
                "路由状态": "ROUTED",
            },
        ),
        (
            "L2修复单结构_v2.json",
            {
                "schema_version": "xcue.l2-fix-form/2.0",
                "L2修复单编号": "L2F-T-001",
                "来源路由决策编号": "L15R-T-001",
                "来源发现引用": {"对象类型": "L1发现项", "对象编号": "L1F-T-001"},
                "接收模块": "L2-02",
                "模块内主问题": "句式模板重复",
                "模块内次级问题": [],
                "根因": "测试",
                "诊断证据引用": [_evidence("EV-L2")],
                "修复规则": ["规则1"],
                "修复动作": ["动作1"],
                "修复产物类型": "文风语言修复单",
                "禁止修改范围": [],
                "必须保留内容": [],
                "验收条件": ["通过"],
                "回流闸门": {"回流闸门": "L1-01"},
                "重路由请求": {
                    "是否请求重路由": False,
                    "请求原因": "",
                    "建议问题域": "",
                    "禁止直接指定新目标模块": True,
                },
                "修复单状态": "READY_FOR_L3",
            },
        ),
        (
            "L3执行任务包结构_v2.json",
            {
                "schema_version": "xcue.l3-task-bundle/2.0",
                "L3执行任务包编号": "L3T-T-001",
                "来源L2报告编号": "L2R-T-001",
                "来源修复单编号": "L2F-T-001",
                "执行模式": "CANDIDATE_GENERATION",
                "任务列表": [
                    {
                        "任务编号": "TASK-001",
                        "任务描述": "生成候选",
                        "关联修复单编号": "L2F-T-001",
                    }
                ],
                "允许写入范围": ["candidates/"],
                "禁止写入范围": ["chapters/"],
                "候选输出路径": ["candidates/patch.md"],
                "正式正文保护": {"正式正文路径": "chapters/demo.md", "允许修改": False},
                "复验入口": {"回流闸门": "L1-01"},
                "执行状态": "PLANNED",
            },
        ),
        (
            "L3执行结果结构_v2.json",
            {
                "schema_version": "xcue.l3-execution-result/2.0",
                "L3执行结果编号": "L3O-T-001",
                "来源执行任务包编号": "L3T-T-001",
                "执行状态": "CANDIDATE_WRITTEN",
                "候选产物列表": [
                    {
                        "产物编号": "ART-001",
                        "来源修复单编号": "L2F-T-001",
                        "相对路径": "candidates/patch.md",
                        "产物类型": "候选正文补丁",
                        "是否存在": True,
                        "是否修改正式正文": False,
                    }
                ],
                "未执行任务": [],
                "错误列表": [],
                "正式正文是否修改": False,
                "复验入口": {"回流闸门": "L1-01"},
                "回流状态": "AWAITING_L1",
            },
        ),
    ]


def _negative_fixtures() -> list[tuple[str, dict]]:
    pos = {name: sample for name, sample in _positive_fixtures()}
    l1_bad = dict(pos["L1发现项结构_v2.json"])
    del l1_bad["routeable"]
    l2_bad = dict(pos["L2修复单结构_v2.json"])
    l2_bad["主失败类型"] = "旧字段"
    l3_bad = dict(pos["L3执行结果结构_v2.json"])
    del l3_bad["正式正文是否修改"]
    return [
        ("L1发现项结构_v2.json", l1_bad),
        ("L2修复单结构_v2.json", l2_bad),
        ("L3执行结果结构_v2.json", l3_bad),
    ]


def _validate_sample(schema_path: Path, sample: dict, label: str, registry: Registry, expect_valid: bool) -> None:
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(sample), key=lambda e: list(e.path))
    if expect_valid and errors:
        first = errors[0]
        loc = ".".join(str(p) for p in first.path) or "<root>"
        raise ValueError(f"{label}: {loc}: {first.message}")
    if not expect_valid and not errors:
        raise ValueError(f"{label}: 期望校验失败但未失败")


def main() -> None:
    errors: list[str] = []

    if not HAS_JSONSCHEMA:
        errors.append("缺少 jsonschema / referencing 依赖")

    required_md = [
        "00_跨层契约说明.md",
        "01_字段命名与语义规范.md",
        "02_旧字段迁移映射表.md",
        "03_状态机边界.md",
        "04_证据与引用规范.md",
        "05_L1到L3数据流示例.md",
        "06_契约版本与兼容策略.md",
    ]
    for name in required_md:
        if not (CONTRACT_MD / name).exists():
            errors.append(f"缺少契约文档：{name}")

    for name in V2_SCHEMAS:
        if not (SCHEMA_V2_DIR / name).exists():
            errors.append(f"缺少 v2 Schema：{name}")

    ids: list[str] = []
    for name in V2_SCHEMAS:
        data = _load_json(SCHEMA_V2_DIR / name)
        sid = data.get("$id", "")
        if not sid:
            errors.append(f"{name} 缺少 $id")
        elif sid in ids:
            errors.append(f"$id 重复：{sid}")
        else:
            ids.append(sid)

    migration_text = MIGRATION_MD.read_text(encoding="utf-8")
    for sfc in SFC_IDS:
        if sfc not in migration_text:
            errors.append(f"迁移表未覆盖 {sfc}")
    if SFC_IDS[0] not in AUDIT_COLLISION.read_text(encoding="utf-8"):
        errors.append("审计碰撞清单不可读")

    for name, expected in V1_FINGERPRINTS.items():
        path = SCHEMA_V1_DIR / name
        if not path.exists():
            errors.append(f"v1 Schema 缺失：{name}")
            continue
        data = _load_json(path)
        if data.get("$id") != expected:
            errors.append(f"v1 {name} $id 异常：{data.get('$id')} != {expected}")

    v2_property_names: set[str] = set()
    for name in V2_SCHEMAS:
        data = _load_json(SCHEMA_V2_DIR / name)
        _collect_property_names(data, v2_property_names)

    bad = FORBIDDEN_V2_ROOT_FIELDS.intersection(v2_property_names)
    if bad:
        errors.append(f"v2 Schema 含禁止字段名：{sorted(bad)}")

    if "L1顶层状态" not in v2_property_names:
        errors.append("缺少 L1顶层状态")
    if "路由状态" not in v2_property_names:
        errors.append("缺少 路由状态")
    if "修复单状态" not in v2_property_names:
        errors.append("缺少 修复单状态")
    if "执行状态" not in v2_property_names:
        errors.append("缺少 执行状态")

    l15 = _load_json(SCHEMA_V2_DIR / "L1_5路由决策结构_v2.json")
    if "目标模块" not in l15.get("properties", {}):
        errors.append("L1.5 缺少 目标模块")

    l2 = _load_json(SCHEMA_V2_DIR / "L2修复单结构_v2.json")
    reroute = l2["properties"]["重路由请求"]
    reroute_props = reroute.get("properties", {})
    if "建议目标模块" in reroute_props or "新目标模块" in reroute_props:
        errors.append("L2 重路由请求允许直接指定目标模块")
    if reroute_props.get("禁止直接指定新目标模块", {}).get("const") is not True:
        errors.append("L2 重路由请求未冻结禁止直接指定新目标模块")

    l3 = _load_json(SCHEMA_V2_DIR / "L3执行任务包结构_v2.json")
    if l3["properties"]["执行模式"]["enum"] == l3["properties"]["执行状态"]["enum"]:
        errors.append("L3 执行模式与执行状态枚举相同")

    common = _load_json(SCHEMA_V2_DIR / "公共引用结构_v1.json")
    route_src = common["$defs"]["route_rule_source"]["properties"]["来源路径"]["const"]
    if "L1.5_路由规则.json" not in route_src:
        errors.append("路由规则来源路径错误")
    if "routes.json" in json.dumps(common, ensure_ascii=False):
        errors.append("公共引用结构含 routes.json")

    schema_check_ok = False
    ref_ok = False
    positive_ok = False
    negative_ok = False

    if HAS_JSONSCHEMA:
        import re

        for name in V2_SCHEMAS:
            data = _load_json(SCHEMA_V2_DIR / name)
            sid = data.get("$id", "")
            if not sid.startswith("xcue://"):
                errors.append(f"{name} $id 非绝对 ASCII URI：{sid}")
            blob = json.dumps(data, ensure_ascii=False)
            for ref in re.findall(r'"\$ref": "([^"]+)"', blob):
                if re.search(r"[\u4e00-\u9fff]", ref) or ".json" in ref:
                    errors.append(f"{name} 含非法 $ref：{ref}")
            for anchor in re.findall(r'"\$anchor": "([^"]+)"', blob):
                if not re.fullmatch(r"[-A-Za-z0-9_.:]+", anchor):
                    errors.append(f"{name} 含非法 anchor：{anchor}")

        try:
            registry = _build_registry()
            schema_check_ok = True
            for name in V2_SCHEMAS:
                schema = _load_json(SCHEMA_V2_DIR / name)
                Draft202012Validator(schema, registry=registry)
            ref_ok = True
        except Exception as exc:
            errors.append(f"Schema/Registry 失败：{exc}")

        if ref_ok:
            try:
                for name, sample in _positive_fixtures():
                    _validate_sample(SCHEMA_V2_DIR / name, sample, f"positive:{name}", registry, True)
                positive_ok = True
            except Exception as exc:
                errors.append(f"正向样例失败：{exc}")

            try:
                for name, sample in _negative_fixtures():
                    _validate_sample(SCHEMA_V2_DIR / name, sample, f"negative:{name}", registry, False)
                negative_ok = True
            except Exception as exc:
                errors.append(f"负向样例失败：{exc}")

    if errors:
        for item in errors:
            print(f"ERROR: {item}")
        sys.exit(1)

    if HAS_JSONSCHEMA:
        print("SCHEMA_CHECK = PASSED" if schema_check_ok else "SCHEMA_CHECK = FAILED")
        print("REFERENCE_RESOLUTION = PASSED" if ref_ok else "REFERENCE_RESOLUTION = FAILED")
        print("POSITIVE_FIXTURES = PASSED" if positive_ok else "POSITIVE_FIXTURES = FAILED")
        print("NEGATIVE_FIXTURES = PASSED" if negative_ok else "NEGATIVE_FIXTURES = FAILED")
    print("VALIDATION_OK")


if __name__ == "__main__":
    main()
