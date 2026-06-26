from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from 工程异常 import 输入错误


保留名 = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}
ID模式 = re.compile(r"^[0-9A-Za-z_\-\u4e00-\u9fff]+$")
WINDOWS_DRIVE模式 = re.compile(r"^[A-Za-z]:")


def _规范文本(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise 输入错误(f"{field_name} 必须是字符串")
    normalized = unicodedata.normalize("NFKC", value)
    if not normalized:
        raise 输入错误(f"{field_name} 不能为空")
    if "\x00" in normalized or any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise 输入错误(f"{field_name} 包含控制字符")
    return normalized


def _检查Windows歧义(value: str, field_name: str) -> None:
    if value.rstrip(" .") != value:
        raise 输入错误(f"{field_name} 存在尾随点或空格")
    base = value.split(".")[0].upper()
    if base in 保留名:
        raise 输入错误(f"{field_name} 使用 Windows 保留名：{value}")


def _检查Windows路径语法(value: str, field_name: str, *, allow_host_absolute: bool = False) -> None:
    if WINDOWS_DRIVE模式.match(value):
        if allow_host_absolute and os.name == "nt" and Path(value).is_absolute():
            return
        raise 输入错误(f"{field_name} 不允许 Windows 盘符路径：{value}")
    if value.startswith("\\\\") or value.startswith("//"):
        raise 输入错误(f"{field_name} 不允许 UNC 或 Windows 设备路径：{value}")
    if value.startswith("\\?\\") or value.startswith("\\.\\"):
        raise 输入错误(f"{field_name} 不允许 Windows 设备路径：{value}")


def safe_id(value: str, field_name: str) -> str:
    normalized = _规范文本(value, field_name)
    if len(normalized) > 64:
        raise 输入错误(f"{field_name} 长度必须为 1-64")
    if ".." in normalized:
        raise 输入错误(f"{field_name} 不允许包含 ..")
    if "/" in normalized or "\\" in normalized:
        raise 输入错误(f"{field_name} 不允许包含路径分隔符")
    if ":" in normalized or normalized.startswith("\\\\"):
        raise 输入错误(f"{field_name} 不允许包含 Windows 盘符或 UNC 路径")
    _检查Windows歧义(normalized, field_name)
    if not ID模式.fullmatch(normalized):
        raise 输入错误(f"{field_name} 只允许中文、英文字母、数字、下划线和连字符")
    return normalized


def _检查路径片段(part: str, field_name: str) -> None:
    normalized = _规范文本(part, field_name)
    if normalized in {"", ".", ".."} or ".." in normalized:
        raise 输入错误(f"{field_name} 包含非法路径片段：{part}")
    _检查Windows歧义(normalized, field_name)


def _检查父级符号链接(root: Path, path: Path) -> None:
    root_resolved = root.resolve()
    current = path
    parents = [current, *current.parents]
    for parent in parents:
        if parent == parent.parent:
            break
        if not parent.exists():
            continue
        if parent.is_symlink():
            target = parent.resolve()
            try:
                target.relative_to(root_resolved)
            except ValueError as exc:
                raise 输入错误(f"路径包含逃逸根目录的符号链接：{parent}") from exc
        if parent.resolve() == root_resolved:
            break


def assert_inside_root(root: Path, resolved_path: Path) -> Path:
    root_resolved = root.resolve()
    resolved = resolved_path.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise 输入错误(f"路径越出允许根目录：{resolved}") from exc
    return resolved


def resolve_inside_root(root: Path, candidate: str | Path) -> Path:
    raw = _规范文本(str(candidate), "路径")
    _检查Windows路径语法(raw, "路径", allow_host_absolute=True)
    raw_path = Path(raw)
    if raw_path.drive and not raw_path.is_absolute():
        raise 输入错误(f"路径不允许 Windows 相对盘符：{raw}")
    parts = raw_path.parts
    for part in parts:
        if part in {raw_path.anchor, raw_path.drive, "\\", "/"}:
            continue
        _检查路径片段(part, "路径")
    candidate_path = raw_path if raw_path.is_absolute() else root / raw_path
    _检查父级符号链接(root, candidate_path)
    return assert_inside_root(root, candidate_path)


def safe_output_path(root: Path, relative_path: str | Path) -> Path:
    raw = _规范文本(str(relative_path), "输出路径")
    _检查Windows路径语法(raw, "输出路径")
    raw_path = Path(raw)
    if raw_path.is_absolute() or raw_path.drive:
        raise 输入错误(f"输出路径必须是根内相对路径：{raw}")
    for part in raw_path.parts:
        _检查路径片段(part, "输出路径")
    candidate = root / raw_path
    _检查父级符号链接(root, candidate)
    return assert_inside_root(root, candidate)
