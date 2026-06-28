from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义" / "跨层契约"
V1_DIR = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义"
MIGRATION_MD = ROOT / "00_工程总控" / "跨层接口契约" / "02_旧字段迁移映射表.md"

V2_FILES = [
    "公共引用结构_v1.json",
    "L1发现项结构_v2.json",
    "L1失败包结构_v2.json",
    "L1_5路由决策结构_v2.json",
    "L2修复单结构_v2.json",
    "L2报告结构_v2.json",
    "L3执行任务包结构_v2.json",
    "L3执行结果结构_v2.json",
]

V1_SNAPSHOT = {
    "失败包结构.json": "xcue.schema/failure-packet/1.0",
    "L1.5路由报告结构.json": "xcue.schema/l15-route-report/1.0",
    "第二层报告结构.json": "xcue.schema/l2-report/1.0",
    "第三层任务包结构.json": "xcue.schema/l3-task-bundle/1.0",
}

SFC_IDS = [f"SFC-{i:02d}" for i in range(1, 16)]

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _registry() -> Registry:
    resources: list[tuple[str, Resource]] = []
    for name in V2_FILES:
        data = _load(SCHEMA_DIR / name)
        uri = data["$id"]
        Draft202012Validator.check_schema(data)
        resources.append((uri, Resource.from_contents(data)))
    return Registry().with_resources(resources)


def _validator(name: str) -> Draft202012Validator:
    schema = _load(SCHEMA_DIR / name)
    return Draft202012Validator(schema, registry=_registry())


def _evidence(eid: str = "EV-001") -> dict:
    return {
        "证据编号": eid,
        "来源类型": "CHAPTER",
        "来源路径": "chapters/demo.md",
        "段落编号": 2,
        "行号范围": {"起始行": 5, "结束行": 8},
        "逐字摘句": "示例摘句内容。",
        "证据用途": "SCREENING",
    }


def _finding(**overrides) -> dict:
    base = {
        "schema_version": "xcue.l1-finding/2.0",
        "L1发现编号": "L1F-T-001",
        "来源闸门": "L1-01",
        "来源组件": "L1-01",
        "发现名称": "测试发现",
        "发现状态": "失败",
        "L1问题域": "文风",
        "L1失败类型": "文风失败",
        "说明": "测试说明",
        "证据引用": [_evidence()],
        "严重级别": "warning",
        "decision_role": "DIAGNOSTIC",
        "blocking": False,
        "routeable": True,
        "route_reason": "为L1.5提供领域路由线索",
        "候选模块提示": "L2-02",
        "修复提示": "降低重复",
        "回流闸门": {"回流闸门": "L1-01"},
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="module")
def l1_finding_validator():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    return _validator("L1发现项结构_v2.json")


@pytest.fixture(scope="module")
def l15_validator():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    return _validator("L1_5路由决策结构_v2.json")


@pytest.fixture(scope="module")
def l2_fix_validator():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    return _validator("L2修复单结构_v2.json")


@pytest.fixture(scope="module")
def l3_task_validator():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    return _validator("L3执行任务包结构_v2.json")


@pytest.fixture(scope="module")
def l3_result_validator():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    return _validator("L3执行结果结构_v2.json")


def test_valid_l1_finding_passes(l1_finding_validator):
    l1_finding_validator.validate(_finding())


def test_missing_routeable_fails(l1_finding_validator):
    bad = _finding()
    del bad["routeable"]
    with pytest.raises(Exception):
        l1_finding_validator.validate(bad)


def test_l1_extra_field_fails(l1_finding_validator):
    bad = _finding(失败类型="旧字段")
    with pytest.raises(Exception):
        l1_finding_validator.validate(bad)


def test_l15_primary_uses_reference(l15_validator):
    sample = {
        "schema_version": "xcue.l15-route-decision/2.0",
        "L1_5路由决策编号": "L15R-T-001",
        "来源失败包编号": "L1P-T-001",
        "主发现引用": {
            "对象类型": "L1发现项",
            "对象编号": "L1F-T-001",
        },
        "次级发现引用": [],
        "路由规则编号": "L15-R002",
        "路由动作": "ROUTE_TO_L2",
        "目标模块": "L2-02",
        "修复产物类型": "文风语言修复单",
        "回流闸门": {"回流闸门": "L1-01"},
        "路由原因": "测试",
        "路由状态": "ROUTED",
    }
    l15_validator.validate(sample)


def test_l15_primary_failure_object_rejected(l15_validator):
    bad = {
        "schema_version": "xcue.l15-route-decision/2.0",
        "L1_5路由决策编号": "L15R-T-002",
        "来源失败包编号": "L1P-T-001",
        "primary_failure": {"闸门": "L1-01", "失败类型": "文风失败"},
        "次级发现引用": [],
        "路由规则编号": "L15-R002",
        "路由动作": "ROUTE_TO_L2",
        "目标模块": "L2-02",
        "修复产物类型": "文风语言修复单",
        "回流闸门": {"回流闸门": "L1-01"},
        "路由原因": "测试",
        "路由状态": "ROUTED",
    }
    with pytest.raises(Exception):
        l15_validator.validate(bad)


def test_l15_non_routed_no_target_module(l15_validator):
    sample = {
        "schema_version": "xcue.l15-route-decision/2.0",
        "L1_5路由决策编号": "L15R-T-003",
        "来源失败包编号": "L1P-T-001",
        "主发现引用": {"对象类型": "L1发现项", "对象编号": "L1F-T-001"},
        "次级发现引用": [],
        "路由规则编号": "L15-R050",
        "路由动作": "INPUT_REQUIRED",
        "目标模块": "",
        "修复产物类型": "补齐后的输入表",
        "回流闸门": {"回流闸门": "L1-00"},
        "路由原因": "字数不足",
        "路由状态": "INPUT_REQUIRED",
    }
    l15_validator.validate(sample)
    bad = dict(sample)
    bad["目标模块"] = "L2-01"
    with pytest.raises(Exception):
        l15_validator.validate(bad)


def test_l2_module_problem_separate_from_l1(l2_fix_validator):
    sample = {
        "schema_version": "xcue.l2-fix-form/2.0",
        "L2修复单编号": "L2F-T-001",
        "来源路由决策编号": "L15R-T-001",
        "来源发现引用": {"对象类型": "L1发现项", "对象编号": "L1F-T-001"},
        "接收模块": "L2-02",
        "模块内主问题": "句式模板重复",
        "模块内次级问题": [],
        "根因": "测试",
        "诊断证据引用": [_evidence("EV-L2")],
        "修复规则": ["不得改动机"],
        "修复动作": ["合并重复句"],
        "修复产物类型": "文风语言修复单",
        "禁止修改范围": [],
        "必须保留内容": [],
        "验收条件": ["复验通过"],
        "回流闸门": {"回流闸门": "L1-01"},
        "重路由请求": {
            "是否请求重路由": False,
            "请求原因": "",
            "建议问题域": "",
            "禁止直接指定新目标模块": True,
        },
        "修复单状态": "READY_FOR_L3",
    }
    l2_fix_validator.validate(sample)
    bad = dict(sample, 主失败类型="文风失败")
    with pytest.raises(Exception):
        l2_fix_validator.validate(bad)


def test_l2_cannot_specify_new_target_module(l2_fix_validator):
    schema = _load(SCHEMA_DIR / "L2修复单结构_v2.json")
    reroute = schema["properties"]["重路由请求"]["properties"]
    assert "建议目标模块" not in reroute
    assert reroute["禁止直接指定新目标模块"]["const"] is True


def test_l2_repair_rule_action_product_separated(l2_fix_validator):
    sample = {
        "schema_version": "xcue.l2-fix-form/2.0",
        "L2修复单编号": "L2F-T-002",
        "来源路由决策编号": "L15R-T-001",
        "来源发现引用": {"对象类型": "L1发现项", "对象编号": "L1F-T-001"},
        "接收模块": "L2-02",
        "模块内主问题": "A",
        "模块内次级问题": [],
        "根因": "R",
        "诊断证据引用": [_evidence("EV-2")],
        "修复规则": ["规则1"],
        "修复动作": ["动作1"],
        "修复产物类型": "文风语言修复单",
        "禁止修改范围": [],
        "必须保留内容": [],
        "验收条件": [],
        "回流闸门": {"回流闸门": "L1-01"},
        "重路由请求": {
            "是否请求重路由": False,
            "请求原因": "",
            "建议问题域": "",
            "禁止直接指定新目标模块": True,
        },
        "修复单状态": "READY_FOR_L3",
        "修复方向": "旧含混字段",
    }
    with pytest.raises(Exception):
        l2_fix_validator.validate(sample)


def test_l3_execution_mode_not_equal_status(l3_task_validator):
    task_schema = _load(SCHEMA_DIR / "L3执行任务包结构_v2.json")
    modes = set(task_schema["properties"]["执行模式"]["enum"])
    states = set(task_schema["properties"]["执行状态"]["enum"])
    assert modes != states
    assert "TASK_PLANNING_ONLY" in modes
    assert "PLANNED" in states


def test_l3_candidate_must_reference_fix_form(l3_result_validator):
    sample = {
        "schema_version": "xcue.l3-execution-result/2.0",
        "L3执行结果编号": "L3E-T-001",
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
    }
    l3_result_validator.validate(sample)
    bad = dict(sample)
    bad["候选产物列表"] = [{"产物编号": "X", "相对路径": "p", "产物类型": "t", "是否存在": True, "是否修改正式正文": False}]
    with pytest.raises(Exception):
        l3_result_validator.validate(bad)


def test_l3_prose_modified_flag_required(l3_result_validator):
    bad = {
        "schema_version": "xcue.l3-execution-result/2.0",
        "L3执行结果编号": "L3E-T-002",
        "来源执行任务包编号": "L3T-T-001",
        "执行状态": "COMPLETED",
        "候选产物列表": [],
        "未执行任务": [],
        "错误列表": [],
        "复验入口": {"回流闸门": "L1-01"},
        "回流状态": "COMPLETED",
    }
    with pytest.raises(Exception):
        l3_result_validator.validate(bad)


def test_four_state_machines_not_mixed():
    texts = []
    for name in V2_FILES:
        texts.append(_load(SCHEMA_DIR / name))
    all_props = set()
    for data in texts:
        props = data.get("properties", {})
        all_props.update(props.keys())
    assert "L1顶层状态" in all_props
    assert "路由状态" in all_props
    assert "修复单状态" in all_props
    assert "执行状态" in all_props
    assert "status" not in all_props
    assert "最终状态" not in all_props


def test_evidence_bad_source_rejected(l1_finding_validator):
    bad = _finding()
    bad["证据引用"] = [
        {
            "证据编号": "EV-BAD",
            "来源类型": "INVALID_SOURCE",
            "来源路径": "x",
            "段落编号": 1,
            "行号范围": {"起始行": 1, "结束行": 2},
            "逐字摘句": "x",
            "证据用途": "SCREENING",
        }
    ]
    with pytest.raises(Exception):
        l1_finding_validator.validate(bad)


def test_migration_no_duplicate_unexplained_mapping():
    text = MIGRATION_MD.read_text(encoding="utf-8")
    for old in ("primary_failure", "主失败类型", "修复方向"):
        count = text.count(f"| {old} |") + text.count(f"| {old} |")
        assert count >= 1
    summary_block = text.split("汇总映射")[1]
    assert "L1失败类型 / 模块内主问题" in summary_block


def test_all_sfc_have_resolution():
    text = MIGRATION_MD.read_text(encoding="utf-8")
    for sfc in SFC_IDS:
        assert sfc in text, f"{sfc} missing from migration table"


def test_v1_schemas_unchanged_by_s2a():
    for name, expected_id in V1_SNAPSHOT.items():
        data = _load(V1_DIR / name)
        assert data["$id"] == expected_id
        version = data["properties"]["schema_version"]["const"]
        assert expected_id.endswith("/1.0")
        assert version.endswith("/1.0")


def test_v2_schema_files_exist():
    for name in V2_FILES:
        assert (SCHEMA_DIR / name).exists()


def test_route_rule_source_not_routes_json():
    common = _load(SCHEMA_DIR / "公共引用结构_v1.json")
    const_path = common["$defs"]["route_rule_source"]["properties"]["来源路径"]["const"]
    assert "routes.json" not in const_path
    assert "L1.5_路由规则.json" in const_path


def test_all_schema_ids_absolute_ascii():
    import re

    for name in V2_FILES:
        data = _load(SCHEMA_DIR / name)
        sid = data["$id"]
        assert sid.startswith("xcue://")
        assert not re.search(r"[\u4e00-\u9fff]", sid)


def test_no_chinese_refs_in_schemas():
    import re

    for name in V2_FILES:
        text = json.dumps(_load(SCHEMA_DIR / name), ensure_ascii=False)
        for ref in re.findall(r'"\$ref": "([^"]+)"', text):
            assert ".json" not in ref, f"{name} 含文件名引用：{ref}"
            assert not re.search(r"[\u4e00-\u9fff]", ref), f"{name} 含中文 $ref：{ref}"


def test_all_schemas_pass_check_schema():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    for name in V2_FILES:
        data = _load(SCHEMA_DIR / name)
        Draft202012Validator.check_schema(data)


def test_registry_offline_id_only():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    reg = _registry()
    assert reg.get("http://example.com/bad") is None
    l1 = _load(SCHEMA_DIR / "L1发现项结构_v2.json")
    Draft202012Validator(l1, registry=reg)


def test_illegal_filename_ref_not_in_registry():
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not installed")
    reg = _registry()
    assert reg.get("公共引用结构_v1.json") is None
