"""R4E：禁止将独立探针完整句写入生产 L2 实现。"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import ROOT

L2 = ROOT / "00_工程总控" / "工程执行层" / "L2工程"

MODULE_DIRS = (
    L2 / "L2_02_文风语言",
    L2 / "L2_03_角色心理",
    L2 / "L2_04_创意设定",
    L2 / "L2_05_市场体验",
    L2 / "L2_06_系统一致性",
    L2 / "公共执行层",
)

FORBIDDEN_R4E_STRINGS = (
    "周砚低声问还能再等一刻吗",
    "周砚低声问",
    "警铃响起程野撞开侧门",
    "警铃响起，程野撞开侧门",
    "吊灯坠落许棠推开伤员",
    "吊灯坠落，许棠推开伤员",
    "只有交出通行牌守门人才允许进入内城",
    "只有交出通行牌，守门人才允许进入内城",
    "广播通知北梯关闭",
    "巡逻员又说北梯已经关闭",
    "工具箱里找到一张备用门卡",
    "清晨周砚仍在北岸",
    "清晨，周砚仍在北岸",
    "傍晚周砚乘船抵达南岸",
    "傍晚，周砚乘船抵达南岸",
)


@pytest.mark.parametrize("module_dir", MODULE_DIRS, ids=[p.name for p in MODULE_DIRS])
def test_production_py_files_contain_no_r4e_probe_strings(module_dir: Path):
    assert module_dir.is_dir(), f"missing module dir: {module_dir}"
    offenders: list[str] = []
    for path in sorted(module_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_R4E_STRINGS:
            if needle in text:
                offenders.append(f"{path.relative_to(ROOT)}: {needle}")
    assert not offenders, "生产代码不得硬编码 R4E 探针字符串:\n" + "\n".join(offenders)
