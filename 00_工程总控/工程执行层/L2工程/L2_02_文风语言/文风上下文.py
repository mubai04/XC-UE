from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 文风模型 import 信息密度问题, 句式问题, 解释腔问题, 重复簇
from 通用证据定位 import 切分段落, 切分句子


@dataclass
class 文风上下文:
    章节路径: str
    段落列表: list[str]
    段落编号: list[int]
    句子索引: list[list[str]]
    句长分布: dict[int, list[int]]
    对话片段: list[dict]
    叙述片段: list[dict]
    重复短语候选: list[重复簇]
    连续解释段候选: list[解释腔问题]
    句式信号: list[句式问题]
    信息密度信号: list[信息密度问题]
    failure_evidence: list[dict]
    必须保留的信息: list[str]
    正文语料: str


def _对话判定(句: str) -> bool:
    return "「" in 句 or "」" in 句 or ("：" in 句 and len(句) < 40)


def _解释腔判定(句: str) -> bool:
    markers = ("因为", "所以", "这意味着", "换句话说", "实际上", "显然")
    return any(m in 句 for m in markers) and len(句) > 18


def 构造文风上下文(
    chapter_path: Path,
    item: 失败输入,
    *,
    repo_root: Path | None = None,
) -> 文风上下文:
    resolved = chapter_path.resolve() if chapter_path.is_absolute() else (repo_root / chapter_path).resolve() if repo_root else chapter_path.resolve()
    raw = resolved.read_text(encoding="utf-8")
    正文 = raw.split("\n", 1)[-1] if raw.startswith("#") else raw
    段落列表 = 切分段落(正文)
    句子索引: list[list[str]] = []
    句长分布: dict[int, list[int]] = {}
    对话片段: list[dict] = []
    叙述片段: list[dict] = []
    句式信号: list[句式问题] = []
    解释候选: list[解释腔问题] = []
    密度信号: list[信息密度问题] = []

    for p_idx, para in enumerate(段落列表, start=1):
        sents = 切分句子(para)
        句子索引.append(sents)
        lengths = [len(s) for s in sents]
        句长分布[p_idx] = lengths
        for s_idx, sent in enumerate(sents, start=1):
            if _对话判定(sent):
                对话片段.append({"paragraph": p_idx, "sentence": s_idx, "text": sent})
            else:
                叙述片段.append({"paragraph": p_idx, "sentence": s_idx, "text": sent})
            if len(sent) > 45:
                句式信号.append(句式问题(p_idx, s_idx, len(sent), "过长句"))
            if len(sent) < 6 and s_idx > 1:
                句式信号.append(句式问题(p_idx, s_idx, len(sent), "连续短句"))
            if _解释腔判定(sent):
                解释候选.append(解释腔问题(p_idx, s_idx, sent[:40]))
        if len(sents) >= 3 and all(_解释腔判定(s) for s in sents[:3]):
            解释候选.append(解释腔问题(p_idx, 1, sents[0][:40]))
        if len(para) > 120 and len(sents) <= 2:
            密度信号.append(信息密度问题(p_idx, "高密度长段"))

    tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", 正文)
    counts = Counter(tokens)
    重复短语: list[重复簇] = []
    for phrase, cnt in counts.items():
        if cnt < 2:
            continue
        positions: list[tuple[int, int]] = []
        for p_idx, para in enumerate(段落列表, start=1):
            if phrase in para:
                for s_idx, sent in enumerate(句子索引[p_idx - 1], start=1):
                    if phrase in sent:
                        positions.append((p_idx, s_idx))
        if positions:
            重复短语.append(重复簇(phrase, positions))

    failure_evidence = [{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句]
    保留 = [e.摘句 for e in item.证据 if e.摘句][:3]
    if item.修复方向:
        保留.append(item.修复方向)

    return 文风上下文(
        章节路径=str(resolved),
        段落列表=段落列表,
        段落编号=list(range(1, len(段落列表) + 1)),
        句子索引=句子索引,
        句长分布=句长分布,
        对话片段=对话片段,
        叙述片段=叙述片段,
        重复短语候选=重复短语,
        连续解释段候选=解释候选,
        句式信号=句式信号,
        信息密度信号=密度信号,
        failure_evidence=failure_evidence,
        必须保留的信息=保留,
        正文语料=正文,
    )


def 上下文转诊断输入(ctx: 文风上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-02",
        "failure_type": item.失败类型,
        "failure_description": item.说明,
        "style_preprocessing": {
            "paragraph_count": len(ctx.段落列表),
            "sentence_lengths": ctx.句长分布,
            "dialogue_segments": ctx.对话片段[:6],
            "narration_segments": ctx.叙述片段[:6],
            "repeat_phrases": [asdict(r) for r in ctx.重复短语候选[:8]],
            "exposition_candidates": [asdict(x) for x in ctx.连续解释段候选[:6]],
            "syntax_signals": [asdict(s) for s in ctx.句式信号[:8]],
            "density_signals": [asdict(d) for d in ctx.信息密度信号[:6]],
        },
        "failure_evidence": ctx.failure_evidence,
        "preserve_required": ctx.必须保留的信息,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
