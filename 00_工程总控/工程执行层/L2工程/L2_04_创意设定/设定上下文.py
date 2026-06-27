from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 设定模型 import 代价, 规则, 设定实体, 限制
from 通用证据定位 import 切分段落

_RULE_MARKERS = ("规则", "审查", "惩罚", "名单", "代价", "设定")


@dataclass
class 设定上下文:
    章节路径: str
    正文语料: str
    正文事实: list[str]
    IR事实: list[str]
    模型推断: list[str]
    尚无证据: list[str]
    设定实体表: list[设定实体]
    规则表: list[规则]
    限制表: list[限制]
    代价表: list[代价]
    failure_evidence: list[dict]


def _读IR片段(ir_dir: Path | None) -> list[str]:
    if ir_dir is None or not ir_dir.is_dir():
        return []
    facts = []
    for path in sorted(ir_dir.glob("IR-*.md")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip("- ").strip()
            if line and not line.startswith("#"):
                facts.append(f"[IR:{path.name}] {line[:80]}")
    return facts[:12]


def 构造设定上下文(
    chapter_path: Path,
    item: 失败输入,
    *,
    repo_root: Path | None = None,
    ir_dir: Path | None = None,
) -> 设定上下文:
    resolved = chapter_path.resolve() if chapter_path.is_absolute() else (
        (repo_root / chapter_path).resolve() if repo_root else chapter_path.resolve()
    )
    raw = resolved.read_text(encoding="utf-8")
    正文 = raw.split("\n", 1)[-1] if raw.startswith("#") else raw
    段落 = 切分段落(正文)
    正文事实 = [p[:100] for p in 段落 if any(m in p for m in _RULE_MARKERS)]
    IR事实 = _读IR片段(ir_dir)
    实体: list[设定实体] = []
    规则表: list[规则] = []
    限制表: list[限制] = []
    代价表: list[代价] = []
    for p in 段落:
        if "规则" in p:
            规则表.append(规则("审查/层级规则", "触发异常或违规则生效", "正文"))
            实体.append(设定实体("层级规则", "正文"))
        if "惩罚" in p or "代价" in p:
            代价表.append(代价("违规则名单减少或承担后果", "正文"))
        if "名单" in p:
            限制表.append(限制("名字减少意味着淘汰", "正文"))
    return 设定上下文(
        章节路径=str(resolved),
        正文语料=正文,
        正文事实=正文事实,
        IR事实=IR事实,
        模型推断=[],
        尚无证据=["未在正文或IR出现的硬规则"] if not 规则表 else [],
        设定实体表=实体,
        规则表=规则表,
        限制表=限制表,
        代价表=代价表,
        failure_evidence=[{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句],
    )


def 上下文转诊断输入(ctx: 设定上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-04",
        "failure_type": item.失败类型,
        "text_facts": ctx.正文事实,
        "ir_facts": ctx.IR事实,
        "inferred": ctx.模型推断,
        "unverified": ctx.尚无证据,
        "entities": [asdict(e) for e in ctx.设定实体表],
        "rules": [asdict(r) for r in ctx.规则表],
        "limits": [asdict(l) for l in ctx.限制表],
        "costs": [asdict(c) for c in ctx.代价表],
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
