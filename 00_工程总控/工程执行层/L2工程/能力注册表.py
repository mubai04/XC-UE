from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from DeepSeek客户端 import DeepSeekClient
from L2模型 import 失败输入, 修复单
from L2路径注册 import 注册L2子路径
from 能力标准解析 import 能力规则

注册L2子路径()

import 文风能力入口  # noqa: E402
import 角色能力入口  # noqa: E402
import 设定能力入口  # noqa: E402
import 市场能力入口  # noqa: E402
import 一致性能力入口  # noqa: E402

SafeGenerator = Callable[..., tuple[修复单 | None, str | None]]

ABILITY_REGISTRY: dict[str, SafeGenerator] = {
    "L2-02": 文风能力入口.安全生成修复单,
    "L2-03": 角色能力入口.安全生成修复单,
    "L2-04": 设定能力入口.安全生成修复单,
    "L2-05": 市场能力入口.安全生成修复单,
    "L2-06": 一致性能力入口.安全生成修复单,
}


def 获取能力入口(module_id: str) -> SafeGenerator | None:
    return ABILITY_REGISTRY.get(module_id)


def 列出已注册模块() -> tuple[str, ...]:
    return tuple(ABILITY_REGISTRY.keys())
