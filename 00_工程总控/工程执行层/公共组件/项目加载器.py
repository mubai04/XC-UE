from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from 安全路径 import assert_inside_root, resolve_inside_root, safe_id
from 工程异常 import 输入错误, 项目错误


注册表版本 = "xcue.project-registry/1.0"
项目清单版本 = "xcue.project-manifest/1.0"


@dataclass(frozen=True)
class 项目上下文:
    project_id: str
    project_root: Path
    relative_project_root: str
    registry_path: Path | None
    project_manifest: Path
    content_root: Path
    chapter_source: Path
    entrypoint: Path
    entrypoint_type: str
    source_scope: str
    resolved: bool = True


def 默认注册表路径(root: Path) -> Path:
    return root / "00_工程总控" / "工程执行层" / "项目注册表.json"


def _注册表路径(root: Path, registry_path: str | Path | None) -> Path:
    if registry_path is None:
        return 默认注册表路径(root)
    path = Path(registry_path)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _项目错误(reason: str, message: str, **details: object) -> 项目错误:
    return 项目错误(message, reason, **details)


def _读JSON(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"{label}不存在：{path}", path=str(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"{label}解析失败：{path}: {exc}", path=str(path)) from exc
    if not isinstance(data, dict):
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"{label}必须是 JSON object：{path}", path=str(path))
    return data


def _读注册表(path: Path) -> dict[str, Any]:
    data = _读JSON(path, "项目注册表")
    if data.get("schema_version") != 注册表版本:
        raise 输入错误("项目注册表 schema_version 不支持")
    if not isinstance(data.get("default_project"), str) or not data["default_project"]:
        raise 输入错误("项目注册表缺少 default_project")
    if not isinstance(data.get("projects"), dict):
        raise 输入错误("项目注册表缺少 projects")
    return data


def _相对路径(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _解析任意项目根(root: Path, raw_root: str | Path, reason: str = "PROJECT_RESOLUTION_FAILED") -> Path:
    raw_path = Path(raw_root)
    if raw_path.is_absolute():
        return raw_path.resolve()
    try:
        return resolve_inside_root(root, raw_path)
    except 输入错误 as exc:
        raise _项目错误(reason, str(exc), project_root=str(raw_root)) from exc


def _解析项目内路径(project_root: Path, raw: str | Path, reason: str = "PROJECT_PATH_OUT_OF_SCOPE") -> Path:
    try:
        return assert_inside_root(project_root, (project_root / Path(raw)).resolve())
    except 输入错误 as exc:
        raise _项目错误(reason, str(exc), path=str(raw), project_root=str(project_root)) from exc


def _校验目录(path: Path, reason: str, label: str) -> None:
    if not path.exists() or not path.is_dir():
        raise _项目错误(reason, f"{label}不存在：{path}", path=str(path))


def _读项目清单(path: Path) -> dict[str, Any]:
    data = _读JSON(path, "项目清单")
    if data.get("schema_version") != 项目清单版本:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"项目清单 schema_version 不支持：{path}", path=str(path))
    return data


def _由清单构造上下文(
    *,
    root: Path,
    project_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    expected_project_id: str | None,
    registry_path: Path | None,
    source_scope: str,
) -> 项目上下文:
    manifest_project_id = manifest.get("project_id")
    if not isinstance(manifest_project_id, str) or not manifest_project_id:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", "项目清单缺少 project_id", path=str(manifest_path))
    manifest_project_id = safe_id(manifest_project_id, "project_id")
    if expected_project_id and manifest_project_id != expected_project_id:
        raise _项目错误(
            "PROJECT_ID_MISMATCH",
            f"项目 ID 与清单不一致：{expected_project_id} != {manifest_project_id}",
            requested_project=expected_project_id,
            manifest_project=manifest_project_id,
        )

    content_root_raw = manifest.get("content_root")
    default_chapter_raw = manifest.get("default_chapter")
    entrypoint_raw = manifest.get("entrypoint")
    entrypoint_type = manifest.get("entrypoint_type", "project")
    required_dirs = manifest.get("required_dirs", [])
    if not isinstance(content_root_raw, str) or not content_root_raw:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", "项目清单缺少 content_root", path=str(manifest_path))
    if not isinstance(default_chapter_raw, str) or not default_chapter_raw:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", "项目清单缺少 default_chapter", path=str(manifest_path))
    if not isinstance(entrypoint_raw, str) or not entrypoint_raw:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", "项目清单缺少 entrypoint", path=str(manifest_path))
    if entrypoint_type not in {"project", "shared"}:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"entrypoint_type 不支持：{entrypoint_type}", path=str(manifest_path))
    if not isinstance(required_dirs, list) or any(not isinstance(item, str) or not item for item in required_dirs):
        raise _项目错误("PROJECT_RESOLUTION_FAILED", "required_dirs 必须是字符串数组", path=str(manifest_path))

    content_root = _解析项目内路径(project_root, content_root_raw)
    chapter_source = _解析项目内路径(project_root, default_chapter_raw)
    entrypoint = _解析项目内路径(project_root, entrypoint_raw)
    _校验目录(content_root, "PROJECT_CONTENT_NOT_FOUND", "项目正文目录")
    try:
        chapter_source.relative_to(content_root)
    except ValueError as exc:
        raise _项目错误(
            "PROJECT_PATH_OUT_OF_SCOPE",
            f"默认章节不在 content_root 内：{chapter_source}",
            chapter_source=str(chapter_source),
            content_root=str(content_root),
        ) from exc
    if not chapter_source.exists() or not chapter_source.is_file():
        raise _项目错误("PROJECT_CONTENT_NOT_FOUND", f"项目正文不存在：{chapter_source}", path=str(chapter_source))
    if not entrypoint.exists() or not entrypoint.is_file():
        raise _项目错误("PROJECT_ENTRYPOINT_NOT_FOUND", f"项目入口不存在：{entrypoint}", path=str(entrypoint))
    for dirname in required_dirs:
        _校验目录(_解析项目内路径(project_root, dirname), "PROJECT_RESOLUTION_FAILED", f"项目必需目录 {dirname}")

    return 项目上下文(
        project_id=manifest_project_id,
        project_root=project_root,
        relative_project_root=_相对路径(root, project_root),
        registry_path=registry_path,
        project_manifest=manifest_path,
        content_root=content_root,
        chapter_source=chapter_source,
        entrypoint=entrypoint,
        entrypoint_type=str(entrypoint_type),
        source_scope=source_scope,
    )


def _加载项目根(
    *,
    root: Path,
    project_root: Path,
    expected_project_id: str | None,
    registry_path: Path | None,
    source_scope: str,
) -> 项目上下文:
    if not project_root.exists():
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"项目根目录不存在：{project_root}", project_root=str(project_root))
    if not project_root.is_dir():
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"项目根路径不是目录：{project_root}", project_root=str(project_root))
    manifest_path = (project_root / "project.json").resolve()
    manifest = _读项目清单(manifest_path)
    return _由清单构造上下文(
        root=root,
        project_root=project_root,
        manifest_path=manifest_path,
        manifest=manifest,
        expected_project_id=expected_project_id,
        registry_path=registry_path,
        source_scope=source_scope,
    )


def 加载项目(
    root: Path,
    project_id: str | None = None,
    registry_path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
    project_manifest: str | Path | None = None,
    allow_default: bool = True,
) -> 项目上下文:
    root = root.resolve()
    if project_manifest is not None:
        manifest_path = _解析任意项目根(root, project_manifest).resolve()
        project_root_path = manifest_path.parent
        manifest = _读项目清单(manifest_path)
        return _由清单构造上下文(
            root=root,
            project_root=project_root_path,
            manifest_path=manifest_path,
            manifest=manifest,
            expected_project_id=safe_id(project_id, "project") if project_id else None,
            registry_path=None,
            source_scope="external" if _相对路径(root, project_root_path) == str(project_root_path) else "repository",
        )

    if project_root is not None:
        project_root_path = _解析任意项目根(root, project_root)
        return _加载项目根(
            root=root,
            project_root=project_root_path,
            expected_project_id=safe_id(project_id, "project") if project_id else None,
            registry_path=None,
            source_scope="external" if _相对路径(root, project_root_path) == str(project_root_path) else "explicit_path",
        )

    registry = _注册表路径(root, registry_path)
    try:
        data = _读注册表(registry)
    except 输入错误:
        raise
    except 项目错误 as exc:
        raise exc
    if project_id is None:
        if not allow_default:
            raise _项目错误("PROJECT_RESOLUTION_FAILED", "未提供项目 ID 且不允许默认项目")
        selected = safe_id(data["default_project"], "default_project")
    else:
        selected = safe_id(project_id, "project")
    projects = data["projects"]
    if selected not in projects:
        raise _项目错误("PROJECT_RESOLUTION_FAILED", f"未知项目：{selected}", project=selected)
    entry = projects[selected]
    if not isinstance(entry, dict):
        raise 输入错误(f"项目注册项必须是 object：{selected}")
    raw_root = entry.get("project_root")
    if not isinstance(raw_root, str) or not raw_root:
        raise 输入错误(f"项目缺少 project_root：{selected}")
    expected_project_id = entry.get("project_id", selected)
    if not isinstance(expected_project_id, str) or not expected_project_id:
        raise 输入错误(f"项目 project_id 必须是非空字符串：{selected}")
    project_root_path = _解析任意项目根(root, raw_root)
    return _加载项目根(
        root=root,
        project_root=project_root_path,
        expected_project_id=safe_id(expected_project_id, "project_id"),
        registry_path=registry,
        source_scope="external" if _相对路径(root, project_root_path) == str(project_root_path) else "repository",
    )


def 读取默认项目ID(root: Path, registry_path: str | Path | None = None) -> str:
    registry = _注册表路径(root.resolve(), registry_path)
    data = _读注册表(registry)
    return safe_id(data["default_project"], "default_project")


def 校验项目正文路径(project: 项目上下文, chapter: str | Path) -> Path:
    raw = Path(chapter)
    candidate = raw.resolve() if raw.is_absolute() else (project.project_root / raw).resolve()
    try:
        candidate = assert_inside_root(project.content_root, candidate)
    except 输入错误 as exc:
        raise _项目错误(
            "PROJECT_PATH_OUT_OF_SCOPE",
            str(exc),
            chapter_source=str(candidate),
            content_root=str(project.content_root),
            project_id=project.project_id,
        ) from exc
    if not candidate.exists() or not candidate.is_file():
        raise _项目错误("PROJECT_CONTENT_NOT_FOUND", f"项目正文不存在：{candidate}", path=str(candidate))
    return candidate
