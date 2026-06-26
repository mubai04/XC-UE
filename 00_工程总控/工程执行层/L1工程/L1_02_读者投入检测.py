from __future__ import annotations

import re

from 正文切分 import 找证据
from L1模型 import 检测项, 段落, 闸门结果
from L15交接 import 补路由
from 闸门标准解析 import L102规则, L15路由规则


E_PATTERNS = [
    r"惊|愣|怔|笑|怒|疼|痛|冷|怕|汗|颤|血|死|杀|追|逃|炸|塌|碎|裂|燃",
    r"压迫|威胁|反差|紧张|爽|不可能|怎么会|来不及|不能退|没有退路",
    r"冲突|逼近|抓住|撞|推开|拔|砸|跪|吼|哭|喘",
]

V_PATTERNS = [
    r"下一|以后|还会|到底|为什么|真相|秘密|背后|真正|原来|门后|等着",
    r"伏笔|线索|主线|敌人|反扑|升级|收益|兑现|代价|答案|问题",
    r"没结束|还没完|第一次|第二次|最后|身后|看见了.*新|发现.*不是",
]

C_PATTERNS = [
    r"规则|设定|体系|境界|等级|机构|名册|流程|条款|分类|概念|术语",
    r"因为|所以|也就是说|换句话说|意味着|简单来说|按照|根据|首先|其次",
]

ENTRANCE_PATTERNS = [r"不对|异常|怪|死|血|追|杀|抓|问题|为什么|门|钥匙|信|令|醒来|突然|忽然"]
HOOK_PATTERNS = [r"下一|为什么|到底|真相|秘密|背后|门后|不是.*而是|竟然|没结束|第一次|最后|等着"]


def _score_hits(paragraphs: list[段落], patterns: list[str], cap: int = 5) -> tuple[int, list]:
    ev = 找证据(paragraphs, patterns, cap)
    return min(5, len(ev)), ev


def _score_e(paragraphs: list[段落]) -> tuple[int, list]:
    score, ev = _score_hits(paragraphs, E_PATTERNS)
    first_third = paragraphs[: max(1, len(paragraphs) // 3)]
    early_ev = 找证据(first_third, E_PATTERNS, 2)
    if early_ev and score < 5:
        score += 1
        ev = (early_ev + ev)[:5]
    return min(5, score), ev


def _score_v(paragraphs: list[段落]) -> tuple[int, list]:
    tail = paragraphs[-max(8, len(paragraphs) // 4) :]
    score, ev = _score_hits(tail, V_PATTERNS, 5)
    whole_ev = 找证据(paragraphs, V_PATTERNS, 3)
    if whole_ev and score < 5:
        score += 1
        ev = (ev + whole_ev)[:5]
    return min(5, score), ev


def _score_c(paragraphs: list[段落]) -> tuple[int, list, str]:
    first_half = paragraphs[: max(1, len(paragraphs) // 2)]
    dense: list[段落] = []
    term_like_tokens: set[str] = set()
    for p in first_half:
        concept_hits = sum(len(re.findall(pattern, p.文本)) for pattern in C_PATTERNS)
        long_cn_terms = re.findall(r"[\u4e00-\u9fff]{2,8}(?:堂|院|宗|门|令|境|诀|法|司|阁|殿|局|会|族|城|府|山|书|册|簿)", p.文本)
        term_like_tokens.update(long_cn_terms)
        if concept_hits >= 2 or len(long_cn_terms) >= 3 or p.字数 >= 140:
            dense.append(p)

    if len(dense) >= 8 or len(term_like_tokens) >= 12:
        score = 5
    elif len(dense) >= 5 or len(term_like_tokens) >= 8:
        score = 4
    elif len(dense) >= 3 or len(term_like_tokens) >= 5:
        score = 3
    elif dense or term_like_tokens:
        score = 2
    else:
        score = 1
    desc = f"前半章疑似概念/专名 {len(term_like_tokens)} 个，密集说明段 {len(dense)} 个。"
    return score, dense[:5], desc


def _投入项(e_score: int, v_score: int, c_score: int, rules: L102规则, ev_e: list, ev_v: list, ev_c: list, c_desc: str) -> list[检测项]:
    thresholds = rules.通过阈值
    i_score = e_score * v_score - c_score
    items: list[检测项] = []

    e_threshold = thresholds["E"]
    if e_score < e_threshold:
        items.append(
            检测项(
                "L1-02",
                "E 即时情绪反馈",
                "失败",
                f"按标准变量 E 评分 {e_score}/5，低于阈值 {e_threshold}；即时刺激、压力或情绪变化不足。",
                ev_e,
                "error",
                "E低：即时情绪反馈弱",
            )
        )
    else:
        items.append(检测项("L1-02", "E 即时情绪代理信号", "检测到代理信号", f"E={e_score}/5，达到启发式阈值 {e_threshold}；不等同真实读者情绪。", ev_e))

    v_threshold = thresholds["V"]
    if v_score < v_threshold:
        items.append(
            检测项(
                "L1-02",
                "V 未来价值预期",
                "失败",
                f"按标准变量 V 评分 {v_score}/5，低于阈值 {v_threshold}；章末或主线没有形成足够下一步期待。",
                ev_v,
                "error",
                "V低：未来价值预期弱",
            )
        )
    else:
        items.append(检测项("L1-02", "V 未来价值代理信号", "检测到代理信号", f"V={v_score}/5，达到启发式阈值 {v_threshold}；不等同真实追读价值。", ev_v))

    c_max = thresholds["C_max"]
    if c_score > c_max:
        items.append(
            检测项(
                "L1-02",
                "C 认知成本",
                "风险",
                f"C={c_score}/5，高于可控阈值 {c_max}。{c_desc}",
                ev_c,
                "warning",
                "C高：认知成本过高",
            )
        )
    else:
        items.append(检测项("L1-02", "C 认知成本代理信号", "检测到代理信号", f"C={c_score}/5，未超过阈值 {c_max}。{c_desc}", ev_c))

    i_min = thresholds["I_min"]
    if e_score * v_score <= c_score or i_score < i_min:
        formula_failure = "E低：即时情绪反馈弱" if e_score < thresholds["E"] else "V低：未来价值预期弱"
        if c_score > thresholds["C_max"]:
            formula_failure = "C高：认知成本过高"
        items.append(
            检测项(
                "L1-02",
                "启发式 I = E × V - C",
                "失败",
                f"{rules.公式}；当前启发式 I={e_score}×{v_score}-{c_score}={i_score}，阈值 I≥{i_min}，且标准不足条件为 {rules.不足条件}。",
                ev_e[:2] + ev_v[:2] + ev_c[:1],
                "error",
                formula_failure,
            )
        )
    else:
        items.append(
            检测项(
                "L1-02",
                "启发式 I = E × V - C",
                "检测到代理信号",
                f"{rules.公式}；当前启发式 I={e_score}×{v_score}-{c_score}={i_score}，达到 I≥{i_min}；只代表机器初筛特征，不等同读者投入意愿。",
                ev_e[:2] + ev_v[:2] + ev_c[:1],
            )
        )
    return items


def 检测(paragraphs: list[段落], rules: L102规则, l101_passed: bool, routes: dict[str, L15路由规则]) -> 闸门结果:
    items: list[检测项] = []

    entrance_ev = 找证据(paragraphs[:8], ENTRANCE_PATTERNS, 4)
    if len(entrance_ev) < 2:
        items.append(
            检测项(
                "L1-02",
                "入口抓手",
                "风险",
                "按 L1-02 入口标准，前八段未给出足够异常、压力、问题或可追对象。",
                entrance_ev,
                "warning",
                "入口弱",
            )
        )
    else:
        items.append(检测项("L1-02", "入口抓手代理信号", "检测到代理信号", "前八段识别到异常、压力、问题或可追对象的启发式信号。", entrance_ev))

    e_score, e_ev = _score_e(paragraphs)
    v_score, v_ev = _score_v(paragraphs)
    c_score, dense_paras, c_desc = _score_c(paragraphs)
    c_ev = 找证据(dense_paras, [r".*"], 5)
    items.extend(_投入项(e_score, v_score, c_score, rules, e_ev, v_ev, c_ev, c_desc))

    hook_ev = 找证据(paragraphs[-12:], HOOK_PATTERNS, 4)
    if len(hook_ev) < 2:
        items.append(检测项("L1-02", "章末追读", "风险", "章末未形成足够明确的新问题、真相压力或下一章理由。", hook_ev, "warning", "章末弱"))
    else:
        items.append(检测项("L1-02", "章末追读代理信号", "检测到代理信号", "章末识别到下一章理由或新问题的代理信号；不等同真实追读。", hook_ev))

    abandon = []
    for i in range(0, len(paragraphs) - 2):
        window = paragraphs[i : i + 3]
        if sum(p.字数 for p in window) >= 330 and sum(1 for p in window if "“" in p.文本 or '"' in p.文本) <= 1:
            abandon.extend(window)
            break
    if abandon:
        items.append(
            检测项(
                "L1-02",
                "弃读点窗口",
                "风险",
                "检测到连续长说明/低互动窗口，可能是阅读断流点，需人工复核。",
                找证据(abandon, [r".*"], 3),
                "warning",
                "弃读点明显",
            )
        )

    failures = [补路由(i, routes) for i in items if i.严重级别 in {"error", "warning"}]
    if not l101_passed:
        failures.insert(
            0,
            补路由(
                检测项(
                    "L1-02",
                    "前置闸门",
                    "阻断",
                    "L1-01 未检测到足够结构代理信号时，L1-02 不允许提升自动结论。",
                    [],
                    "warning",
                    "L1-01未通过",
                    候选模块="回L1-01",
                    回流验收位置="L1-01",
                    修复方向="先处理内部创作信号检测问题",
                ),
                routes,
            ),
        )

    allowed_types = set(rules.失败类型)
    failures = [i for i in failures if not allowed_types or i.失败类型 in allowed_types]
    hard = [i for i in failures if i.严重级别 == "error"]
    result = "SCREENING_REJECT" if hard else ("HUMAN_REVIEW_REQUIRED" if failures else "STRUCTURE_SIGNAL_PRESENT")
    return 闸门结果(
        闸门="L1-02",
        判断结果=result,
        输入材料=["章节正文", "L1-02 Markdown标准", "L1-01输出结果", "E/V/C公式与阈值"],
        失败类型=[i.失败类型 for i in failures if i.失败类型],
        失败位置=[e for i in failures for e in i.证据],
        是否进入L15="是" if failures else "否",
        调用方向=[i.候选模块 for i in failures if i.候选模块],
        回流验收位置="L1-02",
        最终状态=result,
        检测项=items,
        规则摘要={
            "公式": rules.公式,
            "不足条件": rules.不足条件,
            "阈值": rules.通过阈值,
            "E": e_score,
            "V": v_score,
            "C": c_score,
            "I": e_score * v_score - c_score,
            "失败类型": rules.失败类型,
            "启发式信号标准": rules.通过标准,
        },
    )
