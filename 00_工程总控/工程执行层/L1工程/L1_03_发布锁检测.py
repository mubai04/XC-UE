from __future__ import annotations

from 正文切分 import 找证据
from L1模型 import 检测项, 段落, 闸门结果
from L15交接 import 补路由
from 闸门标准解析 import L103规则, L15路由规则


BENEFIT_PATTERNS = [
    r"爽|反差|压迫|惊|怒|笑|紧张|释放",
    r"线索|真相|秘密|发现|原来|信息|推进",
    r"变化|升级|新问题|新期待|代价|收益|兑现",
    r"冲突|追|杀|抓|逼|塌|碎|裂|死|血",
]

HOOK_PATTERNS = [r"下一|为什么|到底|真相|秘密|背后|门后|不是.*而是|竟然|没结束|第一次|最后|等着"]


def 检测(
    paragraphs: list[段落],
    word_count: int,
    rules: L103规则,
    l102_passed: bool,
    routes: dict[str, L15路由规则],
) -> 闸门结果:
    items: list[检测项] = []

    if word_count < rules.功能稿下限:
        items.append(
            检测项(
                "L1-03",
                "字数体量",
                "失败",
                f"当前正文约 {word_count} 字，低于 L1-03 标准功能稿下限 {rules.功能稿下限}，默认降级为功能稿。",
                [],
                "error",
                "字数不足",
            )
        )
    elif word_count < rules.字数下限:
        items.append(
            检测项(
                "L1-03",
                "字数体量",
                "风险",
                f"当前正文约 {word_count} 字，低于 L1-03 启发式体量 {rules.字数下限}-{rules.字数上限}，但未低于功能稿下限；需人工判断扩写或降级。",
                [],
                "warning",
                "字数不足",
            )
        )
    elif word_count > rules.字数上限:
        items.append(
            检测项(
                "L1-03",
                "字数体量",
                "风险",
                f"当前正文约 {word_count} 字，高于 L1-03 启发式体量 {rules.字数下限}-{rules.字数上限}，可能需要压缩或拆章人工判断。",
                [],
                "warning",
                "字数超出默认发布体量",
            )
        )
    else:
        items.append(检测项("L1-03", "字数体量代理信号", "检测到代理信号", f"当前正文约 {word_count} 字落在 L1-03 初筛体量 {rules.字数下限}-{rules.字数上限}；不构成发布授权。"))

    payoff_ev = 找证据(paragraphs, BENEFIT_PATTERNS, 5)
    if len(payoff_ev) < 2:
        items.append(
            检测项("L1-03", "当章收益", "失败", "当章没有足够明确的惊讶、压迫、信息推进或新问题。", payoff_ev, "error", "当章收益不足")
        )
    else:
        items.append(检测项("L1-03", "当章收益代理信号", "检测到代理信号", "当章识别到情绪反馈、信息推进、冲突升级或新问题的启发式信号。", payoff_ev))

    hook_ev = 找证据(paragraphs[-12:], HOOK_PATTERNS, 4)
    if len(hook_ev) < 2:
        items.append(检测项("L1-03", "章末追读", "失败", "章末没有制造下一章新变量。", hook_ev, "error", "章末追读弱"))
    else:
        items.append(检测项("L1-03", "章末追读代理信号", "检测到代理信号", "章末识别到下一章理由或新变量的代理信号；不等同真实追读。", hook_ev))

    if not l102_passed:
        items.append(
            检测项(
                "L1-03",
                "投入意愿前置",
                "风险",
                "L1-02 存在需要派单修复项，L1-03 不能提升为发布前启发式检查未发现指定风险。",
                [],
                "warning",
                "投入意愿不足",
                候选模块="回L1-02",
                回流验收位置="L1-02",
                修复方向="先回 L1-02 处理读者投入风险",
            )
        )

    failures = [补路由(i, routes) for i in items if i.严重级别 in {"error", "warning"}]
    hard = [i for i in failures if i.严重级别 == "error"]
    if hard:
        result = "SCREENING_REJECT"
    elif failures:
        result = "HUMAN_REVIEW_REQUIRED"
    else:
        result = "SCREENING_PASS"
    return 闸门结果(
        闸门="L1-03",
        判断结果=result,
        输入材料=["章节正文", "当前字数", "L1-03 Markdown标准", "L1-02输出结果"],
        失败类型=[i.失败类型 for i in failures if i.失败类型],
        失败位置=[e for i in failures for e in i.证据],
        是否进入L15="是" if failures else "否",
        调用方向=[i.候选模块 for i in failures if i.候选模块],
        回流验收位置="L1-03",
        最终状态=result,
        检测项=items,
        规则摘要={
            "字数下限": rules.字数下限,
            "字数上限": rules.字数上限,
            "功能稿下限": rules.功能稿下限,
            "发布前启发式检查表": rules.发布判定表,
            "当章收益项": rules.当章收益项,
        },
    )
