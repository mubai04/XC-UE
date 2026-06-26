from __future__ import annotations

from L2模型 import 失败输入, 修复单
from 能力标准解析 import 能力规则, 失败规则


def _score_rule(item: 失败输入, rule: 失败规则) -> int:
    haystack = " ".join([item.失败类型, item.名称, item.说明, item.修复方向])
    keywords = rule.匹配关键词 or [rule.编号, rule.名称, rule.定义, *rule.表现, *rule.修复规则]
    return sum(1 for keyword in keywords if keyword and keyword in haystack)


def 选择失败规则(item: 失败输入, ability: 能力规则) -> 失败规则 | None:
    if not ability.失败类型库:
        return None
    scored = sorted(((_score_rule(item, rule), rule) for rule in ability.失败类型库), key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return None


def _选择动作(item: 失败输入, ability: 能力规则, rule: 失败规则 | None) -> list[str]:
    actions = rule.修复规则[:] if rule and rule.修复规则 else []
    if not actions:
        for action in ability.修复动作库:
            if item.失败类型 and item.失败类型 in action:
                actions.append(action)
    if not actions:
        actions = ability.默认动作.get(item.失败类型, [])[:]
    if not actions:
        actions = ability.默认动作.get("*", [])[:]
    if not actions:
        actions = ability.修复动作库[:3]
    return actions[:4]


def _选择验收(ability: 能力规则, rule: 失败规则 | None) -> list[str]:
    acceptance = rule.验收标准[:] if rule and rule.验收标准 else []
    if not acceptance:
        acceptance = ability.回流验收问题[:3]
    return acceptance[:4]


def 生成标准修复单(item: 失败输入, ability: 能力规则) -> 修复单:
    rule = 选择失败规则(item, ability)
    actions = _选择动作(item, ability, rule)
    acceptance = _选择验收(ability, rule)
    product = item.修复方向 or ability.输出产物 or f"{ability.模块} 修复单"
    needs_l2 = "是" if ability.模块 == "L2-05" and item.失败类型.startswith("C高") else "否"
    reroute = "是" if rule and "越界" in rule.名称 else "否"
    return 修复单(
        修复单类型="L2 能力修复单",
        来源闸门=item.来源闸门,
        接收模块=ability.模块,
        输入问题=item.说明,
        主失败类型=item.失败类型,
        次失败类型=rule.编号 if rule else "",
        修复动作=" / ".join(actions),
        修复产物=product,
        验收问题="；".join(acceptance) if acceptance else "修复后是否回到原闸门复验并消除该失败类型。",
        回流位置=item.回流验收位置 or item.来源闸门,
        是否需要其他L2辅助=needs_l2,
        是否需要回L15重路由=reroute,
        最终状态="回原闸门复验",
        标准来源=ability.标准来源,
        规则编号=rule.编号 if rule else "",
        规则依据=rule.名称 if rule else "按能力接口表生成",
        标准动作=actions,
        标准验收=acceptance,
        rule_id=f"{ability.模块}:{rule.编号}" if rule else f"{ability.模块}:interface",
        rule_version=(rule.规则版本 if rule else ability.规则版本),
    )
