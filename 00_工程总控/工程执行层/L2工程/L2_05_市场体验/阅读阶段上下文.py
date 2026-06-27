from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 体验模型 import 信息重复, 阅读阶段
from 通用证据定位 import 切分段落

_STAGE_NAMES = ("开头", "前段", "中段", "末段")


@dataclass
class 体验上下文:
    章节路径: str
    正文语料: str
    段落列表: list[str]
    阅读阶段表: list[阅读阶段]
    重复信息: list[信息重复]
    failure_evidence: list[dict]


def _阶段切分(段落: list[str]) -> list[阅读阶段]:
    if not 段落:
        return []
    n = len(段落)
    bounds = [0, max(1, n // 4), max(2, n // 2), max(3, (3 * n) // 4), n]
    stages: list[阅读阶段] = []
    for i, name in enumerate(_STAGE_NAMES):
        start = bounds[i] + 1
        end = bounds[i + 1]
        if start > n:
            break
        end = min(end, n)
        excerpt = " ".join(段落[start - 1 : end])[:120]
        stages.append(阅读阶段(name, start, end, excerpt))
    return stages


def 构造阅读阶段上下文(chapter_path: Path, item: 失败输入, *, repo_root: Path | None = None) -> 体验上下文:
    resolved = chapter_path.resolve() if chapter_path.is_absolute() else (
        (repo_root / chapter_path).resolve() if repo_root else chapter_path.resolve()
    )
    raw = resolved.read_text(encoding="utf-8")
    正文 = raw.split("\n", 1)[-1] if raw.startswith("#") else raw
    段落 = 切分段落(正文)
    阶段 = _阶段切分(段落)
    tokens = Counter()
    positions: dict[str, list[int]] = {}
    for idx, para in enumerate(段落, start=1):
        for tok in para.split("，"):
            t = tok.strip()[:8]
            if len(t) >= 4:
                tokens[t] += 1
                positions.setdefault(t, []).append(idx)
    重复: list[信息重复] = []
    for tok, cnt in tokens.items():
        if cnt >= 2 and len(positions.get(tok, [])) >= 2:
            ps = positions[tok]
            重复.append(信息重复(tok, f"段落{ps[0]}", f"段落{ps[1]}"))
    return 体验上下文(
        章节路径=str(resolved),
        正文语料=正文,
        段落列表=段落,
        阅读阶段表=阶段,
        重复信息=重复[:8],
        failure_evidence=[{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句],
    )


def 上下文转诊断输入(ctx: 体验上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-05",
        "failure_type": item.失败类型,
        "reading_stages": [asdict(s) for s in ctx.阅读阶段表],
        "repeat_info": [asdict(r) for r in ctx.重复信息],
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
        "ending_excerpt": ctx.段落列表[-1][:200] if ctx.段落列表 else "",
    }
