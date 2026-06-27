from __future__ import annotations

import json
from pathlib import Path

import pytest

from 工程异常 import 项目错误
from 项目加载器 import _校验章节序列


def _write_manifest(project_root: Path, manifest: dict) -> Path:
    path = project_root / "project.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _base_manifest(**overrides) -> dict:
    manifest = {
        "schema_version": "xcue.project-manifest/1.0",
        "project_id": "seq-test",
        "content_root": "chapters",
        "default_chapter": "chapters/a.md",
        "entrypoint": "chapters/a.md",
        "entrypoint_type": "project",
        "required_dirs": [],
        "chapter_sequence": ["chapters/a.md"],
    }
    manifest.update(overrides)
    return manifest


def test_chapter_sequence_valid(tmp_path: Path):
    project_root = tmp_path / "proj"
    content_root = project_root / "chapters"
    content_root.mkdir(parents=True)
    (content_root / "a.md").write_text("# a\n", encoding="utf-8")
    manifest_path = _write_manifest(project_root, _base_manifest())
    result = _校验章节序列(
        project_root=project_root,
        content_root=content_root,
        chapter_sequence_raw=["chapters/a.md"],
        manifest_path=manifest_path,
    )
    assert result == ("chapters/a.md",)


def test_chapter_sequence_rejects_absolute_path(tmp_path: Path):
    project_root = tmp_path / "proj"
    content_root = project_root / "chapters"
    content_root.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("# x\n", encoding="utf-8")
    manifest_path = _write_manifest(project_root, _base_manifest())
    with pytest.raises(项目错误) as exc:
        _校验章节序列(
            project_root=project_root,
            content_root=content_root,
            chapter_sequence_raw=[str(outside)],
            manifest_path=manifest_path,
        )
    assert exc.value.details["reason"] == "PROJECT_CHAPTER_SEQUENCE_INVALID"


def test_chapter_sequence_rejects_parent_escape(tmp_path: Path):
    project_root = tmp_path / "proj"
    content_root = project_root / "chapters"
    content_root.mkdir(parents=True)
    (project_root / "secret.md").write_text("# secret\n", encoding="utf-8")
    manifest_path = _write_manifest(project_root, _base_manifest())
    with pytest.raises(项目错误) as exc:
        _校验章节序列(
            project_root=project_root,
            content_root=content_root,
            chapter_sequence_raw=["../secret.md"],
            manifest_path=manifest_path,
        )
    assert exc.value.details["reason"] == "PROJECT_CHAPTER_SEQUENCE_INVALID"


def test_chapter_sequence_rejects_missing_file(tmp_path: Path):
    project_root = tmp_path / "proj"
    content_root = project_root / "chapters"
    content_root.mkdir(parents=True)
    manifest_path = _write_manifest(project_root, _base_manifest())
    with pytest.raises(项目错误) as exc:
        _校验章节序列(
            project_root=project_root,
            content_root=content_root,
            chapter_sequence_raw=["chapters/missing.md"],
            manifest_path=manifest_path,
        )
    assert exc.value.details["reason"] == "PROJECT_CHAPTER_SEQUENCE_INVALID"


def test_chapter_sequence_rejects_directory(tmp_path: Path):
    project_root = tmp_path / "proj"
    content_root = project_root / "chapters"
    content_root.mkdir(parents=True)
    (content_root / "subdir").mkdir()
    manifest_path = _write_manifest(project_root, _base_manifest())
    with pytest.raises(项目错误) as exc:
        _校验章节序列(
            project_root=project_root,
            content_root=content_root,
            chapter_sequence_raw=["chapters/subdir"],
            manifest_path=manifest_path,
        )
    assert exc.value.details["reason"] == "PROJECT_CHAPTER_SEQUENCE_INVALID"


def test_chapter_sequence_rejects_duplicates(tmp_path: Path):
    project_root = tmp_path / "proj"
    content_root = project_root / "chapters"
    content_root.mkdir(parents=True)
    (content_root / "a.md").write_text("# a\n", encoding="utf-8")
    manifest_path = _write_manifest(project_root, _base_manifest())
    with pytest.raises(项目错误) as exc:
        _校验章节序列(
            project_root=project_root,
            content_root=content_root,
            chapter_sequence_raw=["chapters/a.md", "chapters/a.md"],
            manifest_path=manifest_path,
        )
    assert exc.value.details["reason"] == "PROJECT_CHAPTER_SEQUENCE_INVALID"
