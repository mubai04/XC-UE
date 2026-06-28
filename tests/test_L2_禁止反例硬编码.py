"""禁止在外部反例测试句写入生产 L2 实现。"""

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

FORBIDDEN_COUNTEREXAMPLE_STRINGS = (
    "李四说：今晚就走",
    "王五说：我绝不离开",
    "叶青想夺回账本",
    "苏晚想逃出地牢",
    "顾川誓要带弟弟离开矿城",
    "凡触碰银镜者",
    "一旦点燃黑烛",
    "每次借用镜术",
    "献上一枚旧币",
    "广播说东门封锁",
    "守卫再次说东门封锁",
    "摸出一把黄铜钥匙",
    "顾川不是守门人",
    "清晨，顾川还在城外",
    "入夜后，顾川已经进入城内",
)


@pytest.mark.parametrize("module_dir", MODULE_DIRS, ids=[p.name for p in MODULE_DIRS])
def test_production_py_files_contain_no_counterexample_strings(module_dir: Path):
    assert module_dir.is_dir(), f"missing module dir: {module_dir}"
    offenders: list[str] = []
    for path in sorted(module_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_COUNTEREXAMPLE_STRINGS:
            if needle in text:
                offenders.append(f"{path.relative_to(ROOT)}: {needle}")
    assert not offenders, "生产代码不得硬编码外部反例字符串:\n" + "\n".join(offenders)
