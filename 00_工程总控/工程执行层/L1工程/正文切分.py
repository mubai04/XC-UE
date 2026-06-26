from __future__ import annotations

import re

from L1模型 import 段落


def 清理正文(raw: str) -> tuple[str, str]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body: list[str] = []
    title = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if stripped.startswith("# "):
            title = stripped.lstrip("#").strip()
            if "候选正文" in title:
                continue
            body.append(stripped)
            continue
        body.append(line)
    text = "\n".join(body).strip()
    if not title:
        title = "未识别章节标题"
    return title, text


def 切段(text: str) -> list[段落]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    paragraphs: list[段落] = []
    for i, block in enumerate(blocks, start=1):
        clean = re.sub(r"\s+", "", block)
        paragraphs.append(段落(i, block, len(clean)))
    return paragraphs


def 正文字数(paragraphs: list[段落]) -> int:
    count = 0
    for p in paragraphs:
        if p.文本.startswith("#"):
            continue
        count += len(re.sub(r"[\s，。！？、“”‘’：；,.!?\"'（）()—\-…·#]", "", p.文本))
    return count


def 摘句(text: str, limit: int = 42) -> str:
    clean = re.sub(r"\s+", "", text)
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "..."


def 找证据(paragraphs: list[段落], patterns: list[str], limit: int = 3):
    from L1模型 import 证据

    evidence: list[证据] = []
    for p in paragraphs:
        if any(re.search(pattern, p.文本) for pattern in patterns):
            evidence.append(证据(p.编号, 摘句(p.文本)))
            if len(evidence) >= limit:
                break
    return evidence
