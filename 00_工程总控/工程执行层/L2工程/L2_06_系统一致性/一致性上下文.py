from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 事实模型 import 事实声明, 来源引用
from 通用证据定位 import 切分段落

_STATE_PATTERNS = (
    (r"名单", "名单状态", "减少"),
    (r"规则", "规则状态", "收紧"),
    (r"门后", "空间层级", "不属于这一层"),
)


@dataclass
class 一致性上下文:
    章节路径: str
    正文语料: str
    段落列表: list[str]
    正文事实: list[事实声明]
    IR事实: list[事实声明]
    规则事实: list[事实声明]
    前序章节事实: list[事实声明]
    事实对候选: list[dict]
    failure_evidence: list[dict]


def _extract_facts(text: str, source: str, paragraphs: list[str] | None = None) -> list[事实声明]:
    facts: list[事实声明] = []
    paras = paragraphs or [text]
    for p_idx, para in enumerate(paras, start=1):
        for pattern, entity, attr in _STATE_PATTERNS:
            if re.search(pattern, para):
                facts.append(事实声明(entity, attr, "present", source, para[:60], p_idx))
    return facts


def _读IR(ir_dir: Path | None) -> list[事实声明]:
    if ir_dir is None or not ir_dir.is_dir():
        return []
    facts = []
    for path in ir_dir.glob("IR-*.md"):
        text = path.read_text(encoding="utf-8")
        facts.extend(_extract_facts(text, "IR"))
    return facts


def 构造一致性上下文(
    chapter_path: Path,
    item: 失败输入,
    *,
    repo_root: Path | None = None,
    ir_dir: Path | None = None,
    prior_chapters: list[Path] | None = None,
) -> 一致性上下文:
    resolved = chapter_path.resolve() if chapter_path.is_absolute() else (
        (repo_root / chapter_path).resolve() if repo_root else chapter_path.resolve()
    )
    raw = resolved.read_text(encoding="utf-8")
    正文 = raw.split("\n", 1)[-1] if raw.startswith("#") else raw
    段落 = 切分段落(正文)
    正文事实 = _extract_facts(正文, "正文", 段落)
    IR事实 = _读IR(ir_dir)
    前序: list[事实声明] = []
    for prior in prior_chapters or []:
        if prior.exists():
            pt = prior.read_text(encoding="utf-8")
            前序.extend(_extract_facts(pt, "前序章节", 切分段落(pt)))
    规则事实 = [f for f in 正文事实 if f.实体 == "规则状态"]
    事实对 = []
    for a in 正文事实:
        for b in IR事实 + 前序:
            if a.实体 == b.实体 and a.属性 == b.属性:
                事实对.append({"entity": a.实体, "attribute": a.属性, "source_a": asdict(a), "source_b": asdict(b)})
    return 一致性上下文(
        章节路径=str(resolved),
        正文语料=正文,
        段落列表=段落,
        正文事实=正文事实,
        IR事实=IR事实,
        规则事实=规则事实,
        前序章节事实=前序,
        事实对候选=事实对[:10],
        failure_evidence=[{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句],
    )


def 上下文转诊断输入(ctx: 一致性上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-06",
        "failure_type": item.失败类型,
        "text_facts": [asdict(f) for f in ctx.正文事实],
        "ir_facts": [asdict(f) for f in ctx.IR事实],
        "rule_facts": [asdict(f) for f in ctx.规则事实],
        "prior_facts": [asdict(f) for f in ctx.前序章节事实[:8]],
        "fact_pairs": ctx.事实对候选,
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
