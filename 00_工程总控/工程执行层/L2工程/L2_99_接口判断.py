from __future__ import annotations

from L2模型 import 失败输入, 接口判断
from 能力标准解析 import L2规则


NON_L2 = {
    "L3": "L3",
    "外部运营层": "外部运营层",
}

DERIVED_RECHECK = {
    "回L1": "L1",
    "回 L1": "L1",
    "回L1-01": "L1-01",
    "回 L1-01": "L1-01",
    "回L1-02": "L1-02",
    "回 L1-02": "L1-02",
    "回L1-03": "L1-03",
    "回 L1-03": "L1-03",
}


def _标准归属(item: 失败输入, rules: L2规则 | None) -> tuple[str, str, str]:
    if not rules or not rules.路由规则集:
        return "", "", ""
    haystack = " ".join([item.失败类型, item.名称, item.说明, item.修复方向])
    matched: list[tuple[int, str, str, str]] = []
    for rule in rules.路由规则集.rules:
        for keyword in rule.keywords:
            if keyword and keyword in haystack:
                matched.append((len(keyword), rule.target, rule.rule_id, rule.version))
    if matched:
        _, target, rule_id, version = max(matched, key=lambda item: item[0])
        return target, rule_id, version
    return "", "", ""


def _规则集版本(rules: L2规则 | None) -> str:
    if not rules or not rules.路由规则集:
        return ""
    return rules.路由规则集.version


def _命中禁止项(item: 失败输入, rules: L2规则 | None, module: str) -> str:
    if not rules:
        return ""
    ability = rules.能力规则.get(module)
    if not ability:
        return ""
    haystack = " ".join([item.失败类型, item.名称, item.说明, item.修复方向])
    for forbidden in ability.禁止项:
        if forbidden and forbidden in haystack:
            return forbidden
    return ""


def 判断(item: 失败输入, rules: L2规则 | None = None) -> 接口判断:
    route_set_version = _规则集版本(rules)
    candidate = item.候选模块
    if candidate in DERIVED_RECHECK:
        target = DERIVED_RECHECK[candidate]
        return 接口判断(
            来源闸门=item.来源闸门,
            输入来源模式="派生复验项",
            输入问题=item.说明,
            初步归属=target,
            主候选模块="",
            接口失败类型="IF-R1",
            判断依据="该项来自上游闸门的复验前置条件，只记录复验目标，不生成 L2 修复单。",
            是否越界="否",
            建议动作=[f"回 {target} 复验"],
            回流验收位置=item.回流验收位置 or target,
            最终状态="派生复验",
            备注="不转换为回 L1.5，不阻断同批其他 L2 修复单。",
            route_rule_id="DERIVED_RECHECK",
            route_rule_version=route_set_version,
        )
    if candidate in NON_L2:
        target = NON_L2[candidate]
        return 接口判断(
            来源闸门=item.来源闸门,
            输入来源模式="直接闸门输入",
            输入问题=item.说明,
            初步归属=target,
            主候选模块=target,
            接口失败类型="IF-P2" if target == "回L1.5" else "IF-P4",
            判断依据="L1 failure packet 给出的候选模块不是 L2 能力模块。",
            是否越界="是",
            建议动作=["回 L1.5 重路由"] if target == "回L1.5" else ["进入 L3"],
            回流验收位置=item.回流验收位置 or item.来源闸门,
            最终状态="回L1.5" if target == "回L1.5" else "进入L3",
            route_rule_id="NON_L2_TARGET",
            route_rule_version=route_set_version,
        )

    expected, route_rule_id, route_rule_version = _标准归属(item, rules)
    if not candidate and not expected:
        return 接口判断(
            来源闸门=item.来源闸门,
            输入来源模式="直接闸门输入",
            输入问题=item.说明,
            初步归属="L1.5",
            主候选模块="",
            接口失败类型="ROUTE_NOT_FOUND",
            判断依据="结构化路由规则未命中，且 failure packet 无候选模块。",
            是否混合问题="是",
            建议动作=["回 L1.5 重路由"],
            回流验收位置=item.来源闸门,
            最终状态="回L1.5",
            route_rule_id="ROUTE_NOT_FOUND",
            route_rule_version=route_set_version,
        )

    module = candidate or expected
    if expected and candidate and expected != candidate:
        return 接口判断(
            来源闸门=item.来源闸门,
            输入来源模式="直接闸门输入",
            输入问题=item.说明,
            初步归属=expected,
            主候选模块=expected,
            次候选模块=candidate,
            接口失败类型="IF-P3",
            判断依据=f"结构化路由规则 {route_rule_id} 映射为 {expected}，但输入候选模块为 {candidate}。",
            是否混合问题="是",
            建议动作=["回 L1.5 重路由"],
            回流验收位置=item.回流验收位置 or item.来源闸门,
            最终状态="回L1.5",
            route_rule_id=route_rule_id or "CANDIDATE_MODULE",
            route_rule_version=route_rule_version or route_set_version,
        )

    forbidden = _命中禁止项(item, rules, module)
    if forbidden:
        return 接口判断(
            来源闸门=item.来源闸门,
            输入来源模式="直接闸门输入",
            输入问题=item.说明,
            初步归属=module,
            主候选模块="回L1.5",
            次候选模块=module,
            接口失败类型="L2_FORBIDDEN",
            判断依据=f"{module} 禁止项命中：{forbidden}",
            是否越界="是",
            建议动作=["回 L1.5 重路由"],
            回流验收位置=item.回流验收位置 or item.来源闸门,
            最终状态="回L1.5",
            route_rule_id=route_rule_id,
            route_rule_version=route_rule_version,
        )

    return 接口判断(
        来源闸门=item.来源闸门,
        输入来源模式="直接闸门输入",
        输入问题=item.说明,
        初步归属=module,
        主候选模块=module,
        判断依据=f"结构化路由规则 {route_rule_id or 'CANDIDATE_MODULE'} 将“{item.失败类型}”匹配到 {module}。",
        建议动作=["进入对应 L2"],
        回流验收位置=item.回流验收位置 or item.来源闸门,
        最终状态="接口明确",
        route_rule_id=route_rule_id or "CANDIDATE_MODULE",
        route_rule_version=route_rule_version or route_set_version,
    )
