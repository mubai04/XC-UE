from __future__ import annotations

import re
from collections import Counter

from L1模型 import 检测项, 段落, 证据


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


def _证据(名称: str, value: float, severity: str, failure_type: str, description: str) -> 检测项:
    return 检测项(
        "L1-00",
        名称,
        "风险" if severity == "warning" else "失败",
        f"{description} 当前值：{value:.3f}。",
        [证据(None, f"{名称}={value:.3f}")],
        severity,
        failure_type,
        候选模块="人工复核" if severity == "warning" else "回L1",
        回流验收位置="L1-00",
        修复方向="先处理文本重复、低信息或触发词堆砌风险，再进入 L1 初筛。",
    )


def 检测(paragraphs: list[段落]) -> list[检测项]:
    items: list[检测项] = []
    body_paragraphs = [p for p in paragraphs if not p.文本.startswith("#")]
    total_chars = sum(p.字数 for p in body_paragraphs)
    if total_chars < 300:
        items.append(_证据("TOO_SHORT_INPUT", float(total_chars), "error", "极短输入", "正文有效字数低于 P0 阻断阈值 300。"))
    if total_chars > 20000:
        items.append(_证据("TOO_LONG_INPUT", float(total_chars), "warning", "超长输入", "正文有效字数超过 P0 人工复核阈值 20000。"))

    repeat_ratio = _重复段落比例(paragraphs)
    if repeat_ratio > 0.15:
        items.append(_证据("HIGH_REPETITION", repeat_ratio, "error", "高重复正文", "重复段落比例超过 P0 阻断阈值 0.15。"))

    unique_ratio = _句子唯一率(paragraphs)
    if unique_ratio < 0.70:
        items.append(_证据("LOW_SENTENCE_UNIQUENESS", unique_ratio, "error", "低信息重复正文", "句子唯一率低于 P0 阻断阈值 0.70。"))

    ngram_ratio = _重复窗口比例(paragraphs)
    if ngram_ratio > 0.40:
        items.append(_证据("REPEATED_NGRAM", ngram_ratio, "error", "重复窗口过高", "四字窗口重复比例超过 P0 阻断阈值 0.40。"))
    elif ngram_ratio > 0.25:
        items.append(_证据("REPEATED_NGRAM", ngram_ratio, "warning", "重复窗口风险", "四字窗口重复比例超过 P0 人工复核阈值 0.25。"))

    trigger_concentration = _触发词集中度(paragraphs)
    if trigger_concentration > 0.65:
        items.append(_证据("TRIGGER_CONCENTRATION", trigger_concentration, "warning", "触发词集中风险", "命中触发词集中在少数段落。"))

    trigger_span = _触发词段落跨度(paragraphs)
    if trigger_span and trigger_span < 0.35:
        items.append(_证据("INSUFFICIENT_EVIDENCE_INDEPENDENCE", trigger_span, "warning", "证据独立性不足", "触发词证据分布跨度低于 P0 人工复核阈值 0.35。"))

    trigger_dependency = _触发词依赖度(paragraphs)
    dependency_context_risky = trigger_concentration > 0.45 or unique_ratio < 0.75 or repeat_ratio > 0.10 or total_chars < 1200
    if trigger_dependency > 0.80 and dependency_context_risky:
        items.append(_证据("TRIGGER_DEPENDENCY", trigger_dependency, "warning", "触发词依赖风险", "删除监控触发词后，剩余基础结构信号明显不足。"))

    return items
