from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from tests.conftest import ROOT, failure_packet_item, failure_packet_payload, sample_chapter_text

L2_DIR = ROOT / "00_工程总控" / "工程执行层" / "L2工程"
for p in (L2_DIR, ROOT / "00_工程总控" / "工程执行层" / "公共组件"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from L2输入边界 import (
    L2阶段禁止候选正文,
    加载输入边界规则,
    校验模块输入边界,
    校验裸章节入口,
    过滤相关角色IR,
    过滤相关设定IR,
    模块允许完整当前章,
)
from L2模型 import 失败输入, 证据
from 工程异常 import 输入错误
from 修复单生成 import 执行L15分配模块
from 能力标准解析 import L2规则

DOMAIN_ALGORITHM_FILES = [
    L2_DIR / "L2_01_叙事结构能力.py",
    L2_DIR / "L2_02_文风语言" / "文风上下文.py",
    L2_DIR / "L2_03_角色心理" / "角色上下文.py",
    L2_DIR / "L2_04_创意设定" / "设定上下文.py",
    L2_DIR / "L2_05_市场体验" / "阅读阶段上下文.py",
    L2_DIR / "L2_06_系统一致性" / "一致性上下文.py",
]


def _item(failure_type: str = "叙事结构失败", quote: str = "测试摘句") -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="测试",
        状态="失败",
        说明="测试说明",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型=failure_type,
        候选模块="L2-01",
        回流验收位置="L1-01",
        修复方向="测试",
    )


def _import_l2_main():
    spec = importlib.util.spec_from_file_location("L2运行入口", L2_DIR / "L2运行入口.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.main


def test_raw_chapter_only_rejected():
    with pytest.raises(输入错误, match="L2_UPSTREAM_PACKAGE_REQUIRED"):
        校验裸章节入口(chapter_path="chapters/x.md", l15_report_path=None)


def test_valid_l15_and_chapter_boundary_ok(tmp_path):
    chapter = tmp_path / "chapter.md"
    chapter.write_text(sample_chapter_text("bnd"), encoding="utf-8")
    item = _item()
    result = 校验模块输入边界("L2-01", item, chapter_path=str(chapter), repo_root=tmp_path)
    assert result.action == "OK"


def test_missing_chapter_input_required(tmp_path):
    item = _item()
    result = 校验模块输入边界("L2-01", item, chapter_path="", repo_root=tmp_path)
    assert result.code == "INPUT_REQUIRED"
    assert "chapter_path" in result.missing


def test_l2_01_allows_full_chapter():
    rules = 加载输入边界规则()
    assert 模块允许完整当前章("L2-01", rules)


def test_l2_03_filters_character_ir(tmp_path):
    ir = tmp_path / "IR"
    ir.mkdir()
    (ir / "IR-03_角色心理.md").write_text("# 角色\n\n林远的目标", encoding="utf-8")
    (ir / "IR-99_无关.md").write_text("# 无关\n\n其他内容", encoding="utf-8")
    item = 失败输入(
        "L1-01", "测试", "失败", "林远动机弱", [证据(1, "林远必须做出选择")],
        "error", "角色动机弱", "L2-03", "L1-01", "测试",
    )
    selected = 过滤相关角色IR(ir, item)
    names = [p.name for p in selected]
    assert "IR-03_角色心理.md" in names
    assert "IR-99_无关.md" not in names


def test_l2_04_allows_setting_ir(tmp_path):
    ir = tmp_path / "IR"
    ir.mkdir()
    (ir / "IR-02_世界约束.md").write_text("# 规则\n\n不得越界", encoding="utf-8")
    selected = 过滤相关设定IR(ir, _item("设定失败"))
    assert any("IR-02" in p.name for p in selected)


def test_l2_05_rejects_external_ops():
    item = _item("投流转化率低")
    result = 校验模块输入边界("L2-05", item, chapter_path="x.md", repo_root=ROOT)
    assert result.code == "RETURN_TO_L1_5"


def test_l2_06_allows_prior_and_runtime_config():
    rules = 加载输入边界规则()
    mod = rules["modules"]["L2-06"]
    assert mod["allow_prior_chapters"] == "related_only"
    assert mod["allow_runtime_state"] is True


def test_l2_06_rejects_engineering_issue():
    item = _item("Schema错误")
    result = 校验模块输入边界("L2-06", item, chapter_path="c.md", repo_root=ROOT)
    assert result.code == "RETURN_TO_L1_5"


def test_misroute_returns_l1_5(tmp_path):
    item = _item()
    item.候选模块 = "L2-02"
    rules = L2规则(能力规则={}, 路由规则集={})
    forms, errors, judgement, blocked = 执行L15分配模块(
        item, "L2-01", rules, chapter_path=str(tmp_path / "missing.md"), repo_root=tmp_path,
    )
    assert not forms
    assert blocked
    assert blocked[0].最终状态 == "回L1.5"


def test_l2_cannot_direct_assign_new_module():
    fix_schema = json.loads(
        (ROOT / "00_工程总控/工程执行层/公共组件/结构定义/跨层契约/L2修复单结构_v2.json").read_text(encoding="utf-8-sig")
    )
    props = fix_schema["properties"]["重路由请求"]["properties"]
    assert "建议目标模块" not in props
    assert props["禁止直接指定新目标模块"]["const"] is True


def test_l2_stage_no_candidate_text():
    assert L2阶段禁止候选正文() is True


def test_formal_pipeline_uses_l15_report_only():
    text = (ROOT / "00_工程总控/工程执行层/修复流水线运行入口.py").read_text(encoding="utf-8")
    assert '"--l15-report"' in text
    l2_section = text.split("L2运行入口.main", 1)[1][:600]
    assert "--failure-packet" not in l2_section


def test_domain_algorithm_files_unchanged_by_boundary_imports():
    for fp in DOMAIN_ALGORITHM_FILES:
        assert fp.is_file(), f"缺少 {fp}"
        src = fp.read_text(encoding="utf-8")
        assert "L2输入边界" not in src, f"{fp.name} 不应引入边界模块"


def test_l2_entry_rejects_chapter_only_flag(external_io_token, tmp_path):
    chapter = tmp_path / "ch.md"
    chapter.write_text("# t\n\nbody", encoding="utf-8")
    buf_err = StringIO()
    old = sys.argv
    sys.argv = ["L2运行入口.py", "--chapter", str(chapter)]
    try:
        with redirect_stderr(buf_err):
            code = _import_l2_main()()
    finally:
        sys.argv = old
    assert code != 0


def test_legacy_failure_packet_marked(external_io_token, tmp_path):
    seed = uuid.uuid4().hex[:8]
    ws = tmp_path / f"legacy-{seed}"
    ws.mkdir()
    chapter = ws / "chapter.md"
    chapter.write_text(sample_chapter_text(seed), encoding="utf-8")
    packet = failure_packet_payload(chapter, [failure_packet_item("L1-01", "叙事结构失败", quote="测试")])
    packet_path = ws / "packet.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    buf_err = StringIO()
    old = sys.argv
    sys.argv = [
        "L2运行入口.py",
        "--failure-packet", str(packet_path),
        "--out-dir", str(ws / "out"),
        "--run-id", f"L2-LEG-{seed}",
    ]
    try:
        with redirect_stderr(buf_err):
            _import_l2_main()()
    finally:
        sys.argv = old
    assert "LEGACY_EXPLICIT_ONLY" in buf_err.getvalue()
