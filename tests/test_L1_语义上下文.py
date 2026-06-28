from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"
PUBLIC = EXEC / "公共组件"
L1 = EXEC / "L1工程"
for path in (PUBLIC, L1):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from L1_语义上下文 import CONTEXT_INFERRED, CONTEXT_MANIFEST, CONTEXT_NONE, 构建语义上下文
from 正文切分 import 切段, 清理正文
from 项目加载器 import 项目上下文


def _write_project(tmp_path: Path, *, chapter_sequence: list[str] | None = None) -> Path:
    project_root = tmp_path / "project"
    chapters = project_root / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch01.md").write_text("# ch01\n\n前章钩子仍在。\n", encoding="utf-8")
    (chapters / "ch02.md").write_text("# ch02\n\n当章正文继续。\n", encoding="utf-8")
    manifest = {
        "schema_version": "xcue.project-manifest/1.0",
        "project_id": "ctx-test",
        "content_root": "chapters",
        "default_chapter": "chapters/ch02.md",
        "entrypoint": "chapters/ch02.md",
        "entrypoint_type": "project",
        "required_dirs": [],
    }
    if chapter_sequence is not None:
        manifest["chapter_sequence"] = chapter_sequence
    (project_root / "project.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return project_root


def _project_context(project_root: Path, chapter_sequence: tuple[str, ...] = ()) -> 项目上下文:
    return 项目上下文(
        project_id="ctx-test",
        project_root=project_root,
        relative_project_root=".",
        registry_path=None,
        project_manifest=project_root / "project.json",
        content_root=project_root / "chapters",
        chapter_source=project_root / "chapters" / "ch02.md",
        entrypoint=project_root / "chapters" / "ch02.md",
        entrypoint_type="project",
        source_scope="explicit",
        chapter_sequence=chapter_sequence,
    )


def test_build_context_without_project():
    text = "# t\n\n正文。\n"
    title, body = 清理正文(text)
    paragraphs = 切段(body)
    ctx = 构建语义上下文(
        chapter_path=Path("ch.md"),
        title=title,
        body=body,
        paragraphs=paragraphs,
        project=None,
    )
    assert ctx.context_quality == CONTEXT_NONE
    assert not ctx.prior_paragraphs


def test_manifest_sequence_loads_prior_chapter(tmp_path):
    project_root = _write_project(tmp_path, chapter_sequence=["chapters/ch01.md", "chapters/ch02.md"])
    chapter_path = project_root / "chapters" / "ch02.md"
    raw = chapter_path.read_text(encoding="utf-8")
    title, body = 清理正文(raw)
    paragraphs = 切段(body)
    project = _project_context(project_root, ("chapters/ch01.md", "chapters/ch02.md"))
    ctx = 构建语义上下文(
        chapter_path=chapter_path,
        title=title,
        body=body,
        paragraphs=paragraphs,
        project=project,
    )
    assert ctx.context_quality == CONTEXT_MANIFEST
    assert ctx.prior_body
    assert "前章钩子仍在" in ctx.prior_paragraph_map()["P0002"]


def test_inferred_sequence_when_manifest_missing(tmp_path):
    project_root = _write_project(tmp_path)
    chapter_path = project_root / "chapters" / "ch02.md"
    raw = chapter_path.read_text(encoding="utf-8")
    title, body = 清理正文(raw)
    paragraphs = 切段(body)
    project = _project_context(project_root)
    ctx = 构建语义上下文(
        chapter_path=chapter_path,
        title=title,
        body=body,
        paragraphs=paragraphs,
        project=project,
    )
    assert ctx.context_quality == CONTEXT_INFERRED
    assert ctx.prior_paragraphs
