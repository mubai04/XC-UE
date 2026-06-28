from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 文风模型 import 信息密度问题, 句式问题, 解释腔问题, 重复簇
from 正文读取 import 读取章节正文
from 领域证据 import STOP_WORDS, 提取重复短语簇, 识别对话证据
from 通用证据定位 import 切分句子


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
    语气比较候选: list[dict]
    failure_evidence: list[dict]
    必须保留的信息: list[str]
    正文语料: str


def _解释腔判定(句: str) -> bool:
    markers = ("因为", "所以", "这意味着", "换句话说", "实际上", "显然")
    return any(m in 句 for m in markers) and len(句) > 18


def _提取语气比较候选(句子索引: list[list[str]], source_path: str) -> list[dict]:
    speaker_quotes: dict[str, list[dict]] = {}
    for p_idx, sents in enumerate(句子索引, start=1):
        for s_idx, sent in enumerate(sents, start=1):
            ev = 识别对话证据(sent, paragraph=p_idx, sentence=s_idx)
            speaker = ev.get("speaker")
            if not speaker or ev.get("speaker_confidence") != "EXPLICIT":
                continue
            entry = {
                "paragraph": p_idx,
                "sentence": s_idx,
                "quote": sent,
                "source_path": source_path,
                "speaker": speaker,
                "speaker_confidence": ev.get("speaker_confidence"),
            }
            speaker_quotes.setdefault(speaker, []).append(entry)
    candidates: list[dict] = []
    for speaker, quotes in speaker_quotes.items():
        if len(quotes) >= 2:
            candidates.append(
                {
                    "character": speaker,
                    "source_a": quotes[0],
                    "source_b": quotes[1],
                    "status": "dual_source_ready",
                }
            )
        elif len(quotes) == 1:
            candidates.append(
                {"character": speaker, "source_a": quotes[0], "source_b": None, "status": "evidence_insufficient"}
            )
    return candidates


def 构造文风上下文(
    chapter_path: Path,
    item: 失败输入,
    *,
    repo_root: Path | None = None,
) -> 文风上下文:
    正文, 段落列表, resolved = 读取章节正文(chapter_path, repo_root=repo_root)
    source_path = str(resolved)
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
        句长分布[p_idx] = [len(s) for s in sents]
        for s_idx, sent in enumerate(sents, start=1):
            ev = 识别对话证据(sent, paragraph=p_idx, sentence=s_idx)
            speaker = ev.get("speaker")
            is_dialogue = speaker is not None or "「" in sent or "」" in sent or ("：" in sent and len(sent) < 40)
            seg = {
                "paragraph": p_idx,
                "sentence": s_idx,
                "text": sent,
                "speaker": speaker,
                "speaker_confidence": ev.get("speaker_confidence"),
                "source_path": source_path,
                "quote": sent,
            }
            if is_dialogue:
                对话片段.append(seg)
            else:
                叙述片段.append(seg)
            if len(sent) > 45:
                句式信号.append(句式问题(p_idx, s_idx, len(sent), "过长句"))
            if len(sent) < 6 and s_idx > 1:
                句式信号.append(句式问题(p_idx, s_idx, len(sent), "连续短句"))
            if _解释腔判定(sent):
                解释候选.append(解释腔问题(p_idx, s_idx, sent[:60]))
        if len(sents) >= 3 and all(_解释腔判定(s) for s in sents[:3]):
            解释候选.append(解释腔问题(p_idx, 1, sents[0][:60]))
        if len(para) > 120 and len(sents) <= 2:
            密度信号.append(信息密度问题(p_idx, "高密度长段"))

    raw_clusters = 提取重复短语簇(段落列表, 句子索引, source_path=source_path)
    重复短语: list[重复簇] = []
    for c in raw_clusters:
        positions = [(o["paragraph"], o["sentence"]) for o in c["occurrences"]]
        重复短语.append(重复簇(c["phrase"], positions))

    failure_evidence = [{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句]
    保留 = [e.摘句 for e in item.证据 if e.摘句][:3]

    return 文风上下文(
        章节路径=source_path,
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
        语气比较候选=_提取语气比较候选(句子索引, source_path),
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
            "dialogue_segments": ctx.对话片段[:8],
            "narration_segments": ctx.叙述片段[:8],
            "repeat_phrases": [asdict(r) for r in ctx.重复短语候选[:8]],
            "exposition_candidates": [asdict(x) for x in ctx.连续解释段候选[:6]],
            "syntax_signals": [asdict(s) for s in ctx.句式信号[:8]],
            "density_signals": [asdict(d) for d in ctx.信息密度信号[:6]],
            "tone_comparison_candidates": ctx.语气比较候选[:6],
        },
        "failure_evidence": ctx.failure_evidence,
        "preserve_required": ctx.必须保留的信息,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
