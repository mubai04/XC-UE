from __future__ import annotations

from L2模型 import 失败输入, 接口判断, 修复单
from 能力标准解析 import L2规则
import L2_02_文风语言能力
import L2_03_角色心理能力
import L2_04_创意设定能力
import L2_05_市场体验能力
import L2_06_系统一致性能力


GENERATORS = {
    "L2-02": L2_02_文风语言能力.生成修复单,
    "L2-03": L2_03_角色心理能力.生成修复单,
    "L2-04": L2_04_创意设定能力.生成修复单,
    "L2-05": L2_05_市场体验能力.生成修复单,
    "L2-06": L2_06_系统一致性能力.生成修复单,
}


def 生成(items: list[失败输入], judgements: list[接口判断], rules: L2规则) -> list[修复单]:
    forms: list[修复单] = []
    for source, judgement in zip(items, judgements):
        if judgement.最终状态 != "接口明确":
            continue
        generator = GENERATORS.get(judgement.主候选模块)
        if not generator:
            continue
        ability_rules = rules.能力规则.get(judgement.主候选模块)
        if not ability_rules:
            continue
        forms.append(generator(source, ability_rules))
    return forms
