from __future__ import annotations

import json
import os
from pathlib import Path

from 安全路径 import assert_inside_root


def _manifest_roots(chapter_path: Path) -> tuple[Path, Path] | None:
    resolved = chapter_path.resolve()
    harness_root = resolved.parent.parent
    manifest_path = harness_root / "project.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    content_root_raw = manifest.get("content_root")
    if not isinstance(content_root_raw, str) or not content_root_raw:
        content_root_raw = "chapters"
    project_root = harness_root.resolve()
    content_root = (project_root / content_root_raw).resolve()
    return project_root, content_root


def _resolve_sequence_path(
    raw: str,
    *,
    project_root: Path,
    content_root: Path,
) -> tuple[Path | None, str | None]:
    raw_path = Path(raw)
    if raw_path.is_absolute():
        return None, "PRIOR_CHAPTER_PATH_OUT_OF_SCOPE:绝对路径不允许"
    if ".." in raw_path.parts:
        return None, "PRIOR_CHAPTER_PATH_OUT_OF_SCOPE:../ 逃逸不允许"
    candidate = (project_root / raw).resolve()
    try:
        candidate = assert_inside_root(project_root, candidate)
        candidate = assert_inside_root(content_root, candidate)
    except Exception:
        return None, "PRIOR_CHAPTER_PATH_OUT_OF_SCOPE:路径超出项目或正文根"
    if not candidate.exists():
        return None, "PRIOR_CHAPTER_PATH_OUT_OF_SCOPE:文件不存在"
    if not candidate.is_file():
        return None, "PRIOR_CHAPTER_PATH_OUT_OF_SCOPE:必须是文件而非目录"
    # 符号链接 / 目录联接指向项目外时拒绝
    real = Path(os.path.realpath(candidate))
    try:
        real.relative_to(project_root)
        real.relative_to(content_root)
    except ValueError:
        return None, "PRIOR_CHAPTER_PATH_OUT_OF_SCOPE:符号链接逃逸"
    return candidate, None


def _current_sequence_index(sequence: list[str], resolved: Path, harness_root: Path) -> int | None:
    current = str(resolved.relative_to(harness_root)).replace("\\", "/")
    normalized = [str(s).replace("\\", "/") for s in sequence]
    try:
        return normalized.index(current)
    except ValueError:
        alt = f"chapters/{resolved.name}"
        try:
            return normalized.index(alt)
        except ValueError:
            return None


def 解析前序章节错误(chapter_path: Path) -> list[str]:
    resolved = chapter_path.resolve()
    roots = _manifest_roots(resolved)
    if roots is None:
        return []
    project_root, content_root = roots
    harness_root = project_root
    manifest_path = harness_root / "project.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    sequence = manifest.get("chapter_sequence") or []
    if not isinstance(sequence, list):
        return []
    idx = _current_sequence_index(sequence, resolved, harness_root)
    if idx is None:
        return []
    errors: list[str] = []
    for rel in sequence[:idx]:
        _, err = _resolve_sequence_path(
            str(rel), project_root=project_root, content_root=content_root
        )
        if err:
            errors.append(err)
    return errors


def 解析前序章节(chapter_path: Path) -> list[Path]:
    resolved = chapter_path.resolve()
    roots = _manifest_roots(resolved)
    if roots is None:
        return []
    project_root, content_root = roots
    harness_root = project_root
    manifest_path = harness_root / "project.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    sequence = manifest.get("chapter_sequence") or []
    if not isinstance(sequence, list):
        return []
    idx = _current_sequence_index(sequence, resolved, harness_root)
    if idx is None:
        return []
    priors: list[Path] = []
    for rel in sequence[:idx]:
        candidate, err = _resolve_sequence_path(
            str(rel), project_root=project_root, content_root=content_root
        )
        if err or candidate is None:
            continue
        priors.append(candidate)
    return priors
