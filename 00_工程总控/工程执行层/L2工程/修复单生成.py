from __future__ import annotations

from L2模型 import 失败输入, 接口判断, 修复单
from 能力标准解析 import L2规则
import L2_01_叙事结构能力
import L2_02_文风语言能力
import L2_03_角色心理能力
import L2_04_创意设定能力
import L2_05_市场体验能力
import L2_06_系统一致性能力


GENERATORS = {
    "L2-01": L2_01_叙事结构能力.安全生成修复单,
    "L2-02": L2_02_文风语言能力.生成修复单,
    "L2-03": L2_03_角色心理能力.生成修复单,
    "L2-04": L2_04_创意设定能力.生成修复单,
    "L2-05": L2_05_市场体验能力.生成修复单,
    "L2-06": L2_06_系统一致性能力.生成修复单,
}


def 生成(items: list[失败输入], judgements: list[接口判断], rules: L2规则) -> tuple[list[修复单], list[str]]:
    forms: list[修复单] = []
    errors: list[str] = []
    for source, judgement in zip(items, judgements):
        if judgement.最终状态 != "接口明确":
            continue
        generator = GENERATORS.get(judgement.主候选模块)
        if not generator:
            continue
        ability_rules = rules.能力规则.get(judgement.主候选模块)
        if not ability_rules:
            errors.append(f"{judgement.主候选模块}: 缺少能力规则")
            continue
        try:
            if judgement.主候选模块 == "L2-01":
                form, warn = generator(source, ability_rules)
                if warn:
                    errors.append(warn)
                if form:
                    forms.append(form)
                elif not warn:
                    errors.append(f"L2-01: 未生成修复单（{source.失败类型}）")
            else:
                forms.append(generator(source, ability_rules))
        except Exception as exc:
            errors.append(f"{judgement.主候选模块}: {exc}")
    return forms, errors
