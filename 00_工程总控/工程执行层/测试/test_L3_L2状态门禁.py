from __future__ import annotations

from 运行状态 import L3可执行L2状态, L3禁止L2状态, 已完成, 已阻断, 模型阻断, 结构无效, 部分阻断


def test_l3_only_accepts_completed_l2():
    assert 已完成 in L3可执行L2状态
    assert 已阻断 in L3禁止L2状态
    assert 结构无效 in L3禁止L2状态
    assert 部分阻断 in L3禁止L2状态
    assert 模型阻断 in L3禁止L2状态


def test_l3_rejects_partial_blocked():
    assert "PARTIAL_BLOCKED" == 部分阻断
