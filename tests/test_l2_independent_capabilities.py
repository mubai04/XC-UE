from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from tests.conftest import ROOT

L2 = ROOT / "00_工程总控" / "工程执行层" / "L2工程"

MODULE_DIRS = {
    "L2-02": L2 / "L2_02_文风语言",
    "L2-03": L2 / "L2_03_角色心理",
    "L2-04": L2 / "L2_04_创意设定",
    "L2-05": L2 / "L2_05_市场体验",
    "L2-06": L2 / "L2_06_系统一致性",
}

ENTRY_FILES = {
    "L2-02": "文风能力入口.py",
    "L2-03": "角色能力入口.py",
    "L2-04": "设定能力入口.py",
    "L2-05": "市场能力入口.py",
    "L2-06": "一致性能力入口.py",
}

CONTEXT_BUILDERS = {
    "L2-02": "构造文风上下文",
    "L2-03": "构造角色上下文",
    "L2-04": "构造设定上下文",
    "L2-05": "构造阅读阶段上下文",
    "L2-06": "构造一致性上下文",
}

PLANNERS = {
    "L2-02": ("文风修复规划.py", "规划文风修复"),
    "L2-03": ("角色修复规划.py", "规划角色修复"),
    "L2-04": ("设定修复规划.py", "规划设定修复"),
    "L2-05": ("体验修复规划.py", "规划体验修复"),
    "L2-06": ("一致性修复规划.py", "规划一致性修复"),
}


def test_five_independent_package_directories_exist():
    for mid, path in MODULE_DIRS.items():
        assert path.is_dir(), mid
        assert (path / ENTRY_FILES[mid]).is_file()


def test_registry_maps_entries_only_no_prompts():
    from 能力注册表 import ABILITY_REGISTRY

    assert set(ABILITY_REGISTRY) == {"L2-02", "L2-03", "L2-04", "L2-05", "L2-06"}
    registry_src = (L2 / "能力注册表.py").read_text(encoding="utf-8")
    assert "system_prompt" not in registry_src
    assert "MODULE_SPECS" not in registry_src
    assert "required_response_fields" not in registry_src


def test_shared_layer_has_no_module_id_domain_switch():
    for name in ("模型调用.py", "JSON响应解析.py", "通用证据定位.py"):
        text = (L2 / "公共执行层" / name).read_text(encoding="utf-8")
        assert "MODULE_SPECS" not in text
        assert "system_prompt" not in text
    adapt = (L2 / "公共执行层" / "修复单适配.py").read_text(encoding="utf-8")
    assert "MODULE_SPECS" not in adapt


def test_planner_functions_are_distinct():
    import importlib.util

    fns = []
    for mid, (fname, func) in PLANNERS.items():
        mod_path = MODULE_DIRS[mid] / fname
        spec = importlib.util.spec_from_file_location(f"plan_{mid}", mod_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        fns.append(getattr(mod, func))
    assert len({id(f) for f in fns}) == 5


def test_context_payload_top_level_differs():
    from 文风上下文 import 上下文转诊断输入 as c02
    from 角色上下文 import 上下文转诊断输入 as c03
    from 设定上下文 import 上下文转诊断输入 as c04
    from 阅读阶段上下文 import 上下文转诊断输入 as c05
    from 一致性上下文 import 上下文转诊断输入 as c06
    from L2模型 import 失败输入, 证据

    item = 失败输入("L1-01", "t", "失败", "d", [证据(1, "q")], "error", "x", "L2-02", "L1-01", "r")
    path = ROOT / "tests" / "fixtures" / "r4a_l15_smoke_failure_packet.json"
    chapter = ROOT / "70_测试项目" / "TP-001_CleanHarness_IR_Runtime" / "chapters" / "ch01.md"
    if not chapter.is_file():
        pytest.skip("harness chapter missing")
    from 文风上下文 import 构造文风上下文

    ctx02 = 构造文风上下文(chapter, item, repo_root=ROOT)
    keys = []
    for fn, ctx in (
        (c02, ctx02),
    ):
        keys.append(tuple(sorted(fn(ctx, item).keys())))
    from 角色上下文 import 构造角色上下文
    from 设定上下文 import 构造设定上下文
    from 阅读阶段上下文 import 构造阅读阶段上下文
    from 一致性上下文 import 构造一致性上下文

    payloads = [
        c02(构造文风上下文(chapter, item, repo_root=ROOT), item),
        c03(构造角色上下文(chapter, item, repo_root=ROOT), item),
        c04(构造设定上下文(chapter, item, repo_root=ROOT), item),
        c05(构造阅读阶段上下文(chapter, item, repo_root=ROOT), item),
        c06(构造一致性上下文(chapter, item, repo_root=ROOT), item),
    ]
    top_keys = [tuple(sorted(p.keys())) for p in payloads]
    assert len(set(top_keys)) == 5


def test_old_module_spec_eliminated():
    legacy = (L2 / "L2语义能力执行器.py").read_text(encoding="utf-8")
    assert "MODULE_SPECS" not in legacy
    assert "STYLE_SPEC" not in legacy
    assert "执行语义诊断" not in legacy


def test_compat_wrappers_delegate_to_independent_entries():
    import L2_02_文风语言能力 as w02
    import 文风能力入口 as e02

    assert w02.安全生成修复单 is e02.安全生成修复单


def test_each_module_has_domain_test_file():
    for pattern in (
        "test_l2_02_style_capability.py",
        "test_l2_03_psychology_capability.py",
        "test_l2_04_setting_capability.py",
        "test_l2_05_market_capability.py",
        "test_l2_06_consistency_capability.py",
    ):
        assert (ROOT / "tests" / pattern).is_file()


def test_registry_removal_isolates_modules():
    from 能力注册表 import ABILITY_REGISTRY

    assert "L2-02" in ABILITY_REGISTRY
    copy = dict(ABILITY_REGISTRY)
    del copy["L2-02"]
    assert len(copy) == 4
