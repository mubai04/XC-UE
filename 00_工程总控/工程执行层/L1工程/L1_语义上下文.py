from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from L1模型 import 段落
from L1读取 import 读文本
from 正文切分 import 切段, 清理正文
from 项目加载器 import 项目上下文

CONTEXT_MANIFEST = "MANIFEST"
CONTEXT_INFERRED = "INFERRED"
CONTEXT_NONE = "NONE"


@dataclass
class 语义上下文:
    context_quality: str
    current_title: str
    current_paragraphs: list[段落]
    current_body: str
    prior_title: str = ""
    prior_paragraphs: list[段落] = field(default_factory=list)
    prior_body: str = ""
    prior_chapter_path: Path | None = None

    def current_paragraph_map(self) -> dict[str, str]:
        return {p.段落ID: p.文本 for p in self.current_paragraphs if p.段落ID}

    def prior_paragraph_map(self) -> dict[str, str]:
        return {p.段落ID: p.文本 for p in self.prior_paragraphs if p.段落ID}


def _resolve_chapter_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    return (project_root / raw).resolve()


def _infer_sequence(content_root: Path) -> list[Path]:
    return sorted(p.resolve() for p in content_root.rglob("*.md") if p.is_file())


def 构建语义上下文(
    *,
    chapter_path: Path,
    title: str,
    body: str,
    paragraphs: list[段落],
    project: 项目上下文 | None = None,
) -> 语义上下文:
    prior_paragraphs: list[段落] = []
    prior_title = ""
    prior_body = ""
    prior_path: Path | None = None
    quality = CONTEXT_NONE

    if project is None:
        return 语义上下文(
            context_quality=quality,
            current_title=title,
            current_paragraphs=paragraphs,
            current_body=body,
        )

    sequence: list[Path] = []
    if project.chapter_sequence:
        quality = CONTEXT_MANIFEST
        for raw in project.chapter_sequence:
            sequence.append(_resolve_chapter_path(project.project_root, raw))
    else:
        quality = CONTEXT_INFERRED
        sequence = _infer_sequence(project.content_root)

    resolved_chapter = chapter_path.resolve()
    idx = -1
    for i, candidate in enumerate(sequence):
        if candidate.resolve() == resolved_chapter:
            idx = i
            break

    if idx > 0:
        prior_path = sequence[idx - 1]
        if prior_path.exists():
            raw_prior = 读文本(prior_path)
            prior_title, prior_body = 清理正文(raw_prior)
            prior_paragraphs = 切段(prior_body)

    return 语义上下文(
        context_quality=quality,
        current_title=title,
        current_paragraphs=paragraphs,
        current_body=body,
        prior_title=prior_title,
        prior_paragraphs=prior_paragraphs,
        prior_body=prior_body,
        prior_chapter_path=prior_path,
    )
