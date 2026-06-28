from __future__ import annotations

import re
from collections import Counter

from L1决策角色 import 标记诊断项, 硬护栏角色
from L1模型 import 检测项, 段落, 证据
from 闸门标准解析 import L103规则


触发词 = [
    "惊",
    "怒",
    "疼",
    "痛",
    "血",
    "死",
    "杀",
    "追",
    "逃",
    "塌",
    "碎",
    "规则",
    "代价",
    "选择",
    "决定",
    "不能",
    "必须",
    "真相",
    "秘密",
    "下一",
    "门后",
    "第一次",
    "最后",
]


def _规范句子(text: str) -> list[str]:
    raw = re.split(r"[。！？!?；;]\s*", text)
    sentences = []
    for sentence in raw:
        clean = re.sub(r"[\s，。！？、“”‘’：；,.!?\"'（）()—\-…·#]", "", sentence)
        if clean:
            sentences.append(clean)
    return sentences


def _重复段落比例(paragraphs: list[段落]) -> float:
    texts = [re.sub(r"\s+", "", p.文本) for p in paragraphs if not p.文本.startswith("#")]
    if not texts:
        return 1.0
    counts = Counter(texts)
    repeated = sum(count for count in counts.values() if count > 1)
    return repeated / len(texts)


def _句子唯一率(paragraphs: list[段落]) -> float:
    sentences = _规范句子("\n".join(p.文本 for p in paragraphs))
    if not sentences:
        return 0.0
    return len(set(sentences)) / len(sentences)


def _重复窗口比例(paragraphs: list[段落], size: int = 4) -> float:
    text = re.sub(r"[\s，。！？、“”‘’：；,.!?\"'（）()—\-…·#]", "", "\n".join(p.文本 for p in paragraphs))
    if len(text) < size:
        return 0.0
    windows = [text[i : i + size] for i in range(0, len(text) - size + 1)]
    counts = Counter(windows)
    repeated = sum(count for count in counts.values() if count > 1)
    return repeated / len(windows)


def _触发词集中度(paragraphs: list[段落]) -> float:
    counts = []
    for p in paragraphs:
        count = sum(p.文本.count(word) for word in 触发词)
        if count:
            counts.append(count)
    total = sum(counts)
    if total == 0:
        return 0.0
    return sum(sorted(counts, reverse=True)[:3]) / total


def _触发词段落跨度(paragraphs: list[段落]) -> float:
    hit_numbers = []
    for p in paragraphs:
        if any(word in p.文本 for word in 触发词):
            hit_numbers.append(p.编号)
    if len(hit_numbers) < 2 or not paragraphs:
        return 0.0
    return (max(hit_numbers) - min(hit_numbers) + 1) / len(paragraphs)


def _触发词依赖度(paragraphs: list[段落]) -> float:
    text = "\n".join(p.文本 for p in paragraphs)
    original_hits = sum(text.count(word) for word in 触发词)
    if original_hits == 0:
        return 0.0
    removed = text
    for word in 触发词:
        removed = removed.replace(word, "")
    remaining_signal = sum(1 for word in ["因为", "所以", "但是", "转身", "抬手", "看见", "听见", "发现"] if word in removed)
    return 1.0 if remaining_signal == 0 else max(0.0, 1.0 - remaining_signal / max(1, original_hits))


def _硬护栏(名称: str, value: float, failure_type: str, description: str) -> 检测项:
    return 检测项(
        "L1-00",
        名称,
        "失败",
        f"{description} 当前值：{value:.3f}。",
        [证据(None, f"{名称}={value:.3f}")],
        "error",
        failure_type,
        候选模块="回L1",
        回流验收位置="L1-00",
        修复方向="先处理文本重复、低信息或字数硬阈风险，再进入 L1 语义审计。",
        heuristic=False,
        decision_role=硬护栏角色,
        blocking=True,
        routeable=False,
        route_reason="",
        source_component="L1-00",
        reason_type="",
    )


def _诊断(名称: str, value: float, description: str) -> 检测项:
    return 标记诊断项(
        检测项(
            "L1-00",
            名称,
            "风险",
            f"{description} 当前值：{value:.3f}。",
            [证据(None, f"{名称}={value:.3f}")],
            "info",
            "",
        )
    )


def 检测(paragraphs: list[段落], *, l103: L103规则 | None = None) -> list[检测项]:
    items: list[检测项] = []
    body_paragraphs = [p for p in paragraphs if not p.文本.startswith("#")]
    total_chars = sum(p.字数 for p in body_paragraphs)
    function_floor = l103.功能稿下限 if l103 else 2000

    if total_chars < function_floor:
        items.append(
            _硬护栏(
                "WORD_COUNT_BELOW_FUNCTION_FLOOR",
                float(total_chars),
                "字数不足",
                f"正文有效字数低于 gate_rules 功能稿下限 {function_floor}。",
            )
        )
    if total_chars > 20000:
        items.append(_诊断("TOO_LONG_INPUT", float(total_chars), "正文有效字数超过人工复核阈值 20000。"))

    repeat_ratio = _重复段落比例(paragraphs)
    if repeat_ratio > 0.15:
        items.append(_硬护栏("HIGH_REPETITION", repeat_ratio, "高重复正文", "重复段落比例超过阻断阈值 0.15。"))

    unique_ratio = _句子唯一率(paragraphs)
    if unique_ratio < 0.70:
        items.append(_硬护栏("LOW_SENTENCE_UNIQUENESS", unique_ratio, "低信息重复正文", "句子唯一率低于阻断阈值 0.70。"))

    ngram_ratio = _重复窗口比例(paragraphs)
    if ngram_ratio > 0.40:
        items.append(_硬护栏("REPEATED_NGRAM", ngram_ratio, "重复窗口过高", "四字窗口重复比例超过阻断阈值 0.40。"))
    elif ngram_ratio > 0.25:
        items.append(_诊断("REPEATED_NGRAM", ngram_ratio, "四字窗口重复比例超过人工复核阈值 0.25。"))

    trigger_concentration = _触发词集中度(paragraphs)
    if trigger_concentration > 0.65:
        items.append(_诊断("TRIGGER_CONCENTRATION", trigger_concentration, "命中触发词集中在少数段落。"))

    trigger_span = _触发词段落跨度(paragraphs)
    if trigger_span and trigger_span < 0.35:
        items.append(_诊断("INSUFFICIENT_EVIDENCE_INDEPENDENCE", trigger_span, "触发词证据分布跨度偏低。"))

    trigger_dependency = _触发词依赖度(paragraphs)
    dependency_context_risky = trigger_concentration > 0.45 or unique_ratio < 0.75 or repeat_ratio > 0.10 or total_chars < function_floor
    if trigger_dependency > 0.80 and dependency_context_risky:
        items.append(_诊断("TRIGGER_DEPENDENCY", trigger_dependency, "删除监控触发词后，剩余基础结构信号明显不足。"))

    return items
