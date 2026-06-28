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
)

FORBIDDEN_STRINGS = (
    "生存/达成目标",
    "规则正在收紧",
    "审查/层级规则",
    "触发异常或违规则生效",
    "违规则名单减少或承担后果",
    "名字减少意味着淘汰",
    "林舟想救妹妹",
    "回溯术",
    "左手已经断了",
    "双手完好",
)


@pytest.mark.parametrize("module_dir", MODULE_DIRS, ids=[p.name for p in MODULE_DIRS])
def test_production_py_files_contain_no_fixture_strings(module_dir: Path):
    assert module_dir.is_dir(), f"missing module dir: {module_dir}"
    offenders: list[str] = []
    for path in sorted(module_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_STRINGS:
            if needle in text:
                offenders.append(f"{path.relative_to(ROOT)}: {needle}")
    assert not offenders, "生产代码不得硬编码验收/fixture 字符串:\n" + "\n".join(offenders)
