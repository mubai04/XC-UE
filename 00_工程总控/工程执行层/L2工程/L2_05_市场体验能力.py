from __future__ import annotations

from L2模型 import 失败输入, 修复单
from 能力标准解析 import 能力规则
from 能力修复单 import 生成标准修复单


def 生成修复单(item: 失败输入, rules: 能力规则) -> 修复单:
    return 生成标准修复单(item, rules)
