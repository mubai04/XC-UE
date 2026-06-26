from __future__ import annotations

import re

from 正文切分 import 找证据
from L1模型 import 检测项, 段落, 证据, 闸门结果
from L15交接 import 补路由
from 闸门标准解析 import L101规则, L15路由规则


def _ordered_hits(paragraphs: list[段落], stages: list[tuple[str, list[str]]]) -> tuple[int, list]:
    evidence = []
    last = 0
    for _name, patterns in stages:
        found = None
        for p in paragraphs:
            if p.编号 <= last:
                continue
            if any(re.search(pattern, p.文本) for pattern in patterns):
                found = p
                break
        if found:
            evidence.extend(找证据([found], [".*"], 1))
            last = found.编号
    return len(evidence), evidence


def _首个正文锚点(paragraphs: list[段落]) -> list[证据]:
    return 找证据([p for p in paragraphs if not p.文本.lstrip().startswith("#")], [r".*"], 1)


def 检测(paragraphs: list[段落], rules: L101规则, routes: dict[str, L15路由规则]) -> 闸门结果:
    items: list[检测项] = []

    stages = [
        ("入口异常/目标", [r"忽然|突然|不对|异常|怪|错|不该|不可能|为什么|怎么会|死|血|门|钥匙|信|令|名单|账册|尸|梦"]),
        ("原因或规则压力", [r"因为|原来|规矩|规则|代价|条件|只有|除非|不能|必须|一旦|否则|证据|线索"]),
        ("外部压力靠近", [r"追|逼|查|封|抓|杀|罚|逐|通缉|审|威胁|敌|命令|期限|来不及"]),
        ("事件升级/不可逆变化", [r"塌|碎|裂|消失|爆|燃|倒|醒|变成|打开|关上|失控|暴露|崩|断|升级"]),
        ("角色主动选择", [r"选择|决定|没有再等|抬手|冲|走进|推开|转身|拔|按|赌|宁可|必须去|不能退"]),
        ("章末新问题/反转", [r"没想到|原来|真正|第一次|最后|身后|门后|不是.*而是|竟然|等了.*年|下一|还没结束"]),
    ]
    hit_count, ev = _ordered_hits(paragraphs, stages)
    if hit_count < 4:
        items.append(
            检测项(
                "L1-01",
                "有序叙事信号",
                "失败",
                f"入口异常、规则压力、外部压力、升级、主动选择、章末新问题只识别到 {hit_count}/{len(stages)} 类有序信号；本项不证明真实因果关系。",
                ev or _首个正文锚点(paragraphs),
                "error",
                "叙事失败",
            )
        )
    else:
        items.append(
            检测项(
                "L1-01",
                "有序叙事信号",
                "检测到代理信号",
                "正文存在入口异常、压力、行动与章末新问题的有序信号；本项只作为机器初筛信号。",
                ev,
            )
        )

    agency = 找证据(paragraphs, [r"选择|决定|没有再等|不能退|必须|宁可|赌|抬手|冲|走进|推开|转身"], 4)
    pressure = 找证据(paragraphs, [r"代价|否则|来不及|期限|威胁|追|逼|抓|杀|罚|逐|封|审|暴露|失去"], 4)
    if len(agency) < 2 or len(pressure) < 2:
        items.append(
            检测项(
                "L1-01",
                "主动行动与外部压力信号",
                "风险",
                "主角主动选择或外部代价信号不足；机器未能验证动机与选择的因果关系。",
                agency + pressure,
                "warning",
                "角色失败",
            )
        )
    else:
        items.append(
            检测项(
                "L1-01",
                "主动行动与外部压力信号",
                "检测到代理信号",
                "正文存在行动选择与外部代价信号；是否构成真实角色动机仍需人工判断。",
                agency + pressure,
            )
        )

    setting_ev = 找证据(paragraphs, [r"规则|规矩|设定|能力|境界|血脉|禁忌|代价|只有|除非|不能|不该|钥匙|门票|入口|系统|契约"], 5)
    if len(setting_ev) < 2:
        context_rich = hit_count >= 4 and len(agency) >= 2 and len(pressure) >= 2
        items.append(
            检测项(
                "L1-01",
                "创意设定压力",
                "风险" if context_rich else "失败",
                "未识别到足够规则、禁忌、代价或玩法压力词面证据；若非词面叙事与行动压力已存在，本项降为人工复核，不单独构成硬退回。",
                setting_ev,
                "warning" if context_rich else "error",
                "创意设定待人工复核" if context_rich else "创意设定失败",
            )
        )
    else:
        items.append(
            检测项(
                "L1-01",
                "创意设定压力",
                "检测到代理信号",
                "正文能识别出规则、禁忌、代价或玩法压力的启发式信号；不证明创意设定真实成立。",
                setting_ev,
            )
        )

    explanation_words = ["因为", "所以", "至少", "规则", "规矩", "不是", "不该", "意味着", "也就是说", "换句话说"]
    explanation_paras = [
        p for p in paragraphs if sum(p.文本.count(w) for w in explanation_words) >= 2
    ]
    if len(explanation_paras) >= 7:
        items.append(
            检测项(
                "L1-01",
                "解释腔与AI味风险",
                "风险",
                "按 L1-01“AI味不影响阅读”标准，解释性连接词密集段偏多，可能让正文从现场压力滑向规则说明。",
                找证据(explanation_paras, [r".*"], 5),
                "warning",
                "AI味失败",
            )
        )

    long_paras = [p for p in paragraphs if p.字数 >= 120]
    if len(long_paras) >= 8:
        items.append(
            检测项(
                "L1-01",
                "文风密度",
                "风险",
                "按 L1-01“语言能承载当前场景”标准，长段偏多，若连续出现会抬高阅读负担；需人工判断是否压住节奏。",
                找证据(long_paras, [r".*"], 5),
                "warning",
                "文风失败",
            )
        )

    failures = [补路由(i, routes) for i in items if i.严重级别 in {"error", "warning"}]
    allowed_types = set(rules.失败类型)
    failures = [i for i in failures if not allowed_types or i.失败类型 in allowed_types]
    hard = [i for i in failures if i.严重级别 == "error"]
    result = "SCREENING_REJECT" if hard else ("HUMAN_REVIEW_REQUIRED" if failures else "STRUCTURE_SIGNAL_PRESENT")
    return 闸门结果(
        闸门="L1-01",
        判断结果=result,
        输入材料=["章节正文", "L1-01 Markdown标准", "L1-01失败类型", "L1-01启发式信号标准"],
        失败类型=[i.失败类型 for i in failures if i.失败类型],
        失败位置=[e for i in failures for e in i.证据],
        是否进入L15="是" if failures else "否",
        调用方向=[i.候选模块 for i in failures if i.候选模块],
        回流验收位置="L1-01",
        最终状态=result,
        检测项=items,
        规则摘要={"失败类型": rules.失败类型, "启发式信号标准": rules.通过标准},
    )
