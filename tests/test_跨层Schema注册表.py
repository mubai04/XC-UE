from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "结构定义" / "跨层契约"
RUNLIB = ROOT / "00_工程总控" / "工程执行层" / "公共组件" / "跨层契约运行库"
PUBLIC = ROOT / "00_工程总控" / "工程执行层" / "公共组件"
for path in (PUBLIC, RUNLIB):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from Schema注册表 import (  # noqa: E402
    SCHEMA_FILES,
    SCHEMA_IDS,
    获取Schema注册表,
    校验对象,
    预检Schema,
)
from 迁移错误 import CROSS_LAYER_SCHEMA_ID_DUPLICATED, 迁移错误  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8-sig"))


def test_eight_schemas_registered():
    errors = 预检Schema()
    assert errors == []
    registry = 获取Schema注册表()
    assert registry is not None
    assert len(SCHEMA_FILES) == 8


def test_all_check_schema():
    for name in SCHEMA_FILES:
        Draft202012Validator.check_schema(_load(name))


def test_all_ids_absolute_ascii():
    for name in SCHEMA_FILES:
        sid = _load(name)["$id"]
        assert sid.startswith("xcue://")
        assert not re.search(r"[\u4e00-\u9fff]", sid)


def test_no_chinese_refs():
    for name in SCHEMA_FILES:
        text = json.dumps(_load(name), ensure_ascii=False)
        for ref in re.findall(r'"\$ref": "([^"]+)"', text):
            assert ".json" not in ref
            assert not re.search(r"[\u4e00-\u9fff]", ref)


def test_anchors_ascii():
    for name in SCHEMA_FILES:
        text = json.dumps(_load(name), ensure_ascii=False)
        for anchor in re.findall(r'"\$anchor": "([^"]+)"', text):
            assert re.fullmatch(r"[-A-Za-z0-9_.:]+", anchor)


def test_no_network_schema_resolution():
    registry = 获取Schema注册表()
    assert registry.get("http://example.com/bad") is None
    assert registry.get("公共引用结构_v1.json") is None


def test_registry_offline_resolves_all_refs():
    registry = 获取Schema注册表()
    for name in SCHEMA_FILES:
        data = _load(name)
        Draft202012Validator(data, registry=registry)


def test_no_duplicate_id():
    assert CROSS_LAYER_SCHEMA_ID_DUPLICATED == "CROSS_LAYER_SCHEMA_ID_DUPLICATED"
    ids = [_load(n)["$id"] for n in SCHEMA_FILES]
    assert len(ids) == len(set(ids))


def test_validate_object_roundtrip():
    sample = {
        "schema_version": "xcue.l1-finding/2.0",
        "L1发现编号": "L1F-T-0001",
        "来源闸门": "L1-01",
        "来源组件": "L1-01",
        "发现名称": "t",
        "发现状态": "失败",
        "L1问题域": "文风",
        "L1失败类型": "文风失败",
        "说明": "t",
        "证据引用": [],
        "严重级别": "warning",
        "decision_role": "DIAGNOSTIC",
        "blocking": False,
        "routeable": True,
        "route_reason": "r",
        "候选模块提示": "",
        "修复提示": "",
        "回流闸门": {"回流闸门": "L1-01"},
    }
    校验对象(SCHEMA_IDS["l1-finding/v2"], sample)


def test_missing_required_rejected():
    bad = {
        "schema_version": "xcue.l1-finding/2.0",
        "L1发现编号": "L1F-T-0001",
    }
    with pytest.raises(迁移错误):
        校验对象(SCHEMA_IDS["l1-finding/v2"], bad)


def test_extra_field_rejected():
    sample = {
        "schema_version": "xcue.l1-finding/2.0",
        "L1发现编号": "L1F-T-0001",
        "来源闸门": "L1-01",
        "来源组件": "L1-01",
        "发现名称": "t",
        "发现状态": "失败",
        "L1问题域": "文风",
        "L1失败类型": "文风失败",
        "说明": "t",
        "证据引用": [],
        "严重级别": "warning",
        "decision_role": "DIAGNOSTIC",
        "blocking": False,
        "routeable": True,
        "route_reason": "r",
        "候选模块提示": "",
        "修复提示": "",
        "回流闸门": {"回流闸门": "L1-01"},
        "失败类型": "旧字段",
    }
    with pytest.raises(迁移错误):
        校验对象(SCHEMA_IDS["l1-finding/v2"], sample)


def test_illegal_chinese_anchor_fails_check_schema():
    broken = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "xcue://schemas/cross-layer/test-broken/v0",
        "type": "object",
        "$defs": {
            "bad": {
                "$anchor": "证据引用",
                "type": "string",
            }
        },
    }
    with pytest.raises(SchemaError):
        Draft202012Validator.check_schema(broken)


def test_validator_script_reports_schema_check():
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(ROOT / "脚本" / "校验_L0至L3跨层接口契约.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SCHEMA_CHECK = PASSED" in proc.stdout
    assert "VALIDATION_OK" in proc.stdout
    assert "ERROR:" not in proc.stdout
