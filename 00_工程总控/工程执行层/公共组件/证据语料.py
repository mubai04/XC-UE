"""L1-SEM 只读证据语料：prompt 与校验器共用同一份规范化段落文本。"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any

SCOPE_CURRENT = "CURRENT_CHAPTER"
SCOPE_PRIOR = "PRIOR_CHAPTER"


def 规范化证据文本(text: str) -> str:
    """仅允许：去 BOM、统一换行、Unicode NFC。不改标点、不折叠空格。"""
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


@dataclass(frozen=True)
class 证据段落:
    paragraph_id: str
    text: str


@dataclass
class 证据语料:
    source_scope: str
    paragraphs: list[证据段落] = field(default_factory=list)

    def paragraph_map(self) -> dict[str, str]:
        return {p.paragraph_id: p.text for p in self.paragraphs}

    def format_for_prompt(self) -> str:
        lines = [f"[{p.paragraph_id}|{self.source_scope}] {p.text}" for p in self.paragraphs]
        return "\n\n".join(lines)

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "source_scope": self.source_scope,
            "paragraph_count": len(self.paragraphs),
            "paragraphs": [
                {"paragraph_id": p.paragraph_id, "text_length": len(p.text), "text": p.text}
                for p in self.paragraphs
            ],
        }

    @classmethod
    def from_paragraph_objects(cls, paragraphs: list[Any], *, source_scope: str) -> 证据语料:
        items: list[证据段落] = []
        for p in paragraphs:
            pid = getattr(p, "段落ID", None) or ""
            raw = getattr(p, "文本", "")
            if not pid:
                continue
            items.append(证据段落(paragraph_id=pid, text=规范化证据文本(str(raw))))
        return cls(source_scope=source_scope, paragraphs=items)


def 构建章节证据语料(
    *,
    current_paragraphs: list[Any],
    prior_paragraphs: list[Any] | None = None,
) -> tuple[证据语料, 证据语料 | None]:
    current = 证据语料.from_paragraph_objects(current_paragraphs, source_scope=SCOPE_CURRENT)
    prior = None
    if prior_paragraphs:
        prior = 证据语料.from_paragraph_objects(prior_paragraphs, source_scope=SCOPE_PRIOR)
    return current, prior
