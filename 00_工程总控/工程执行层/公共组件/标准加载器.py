from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from 工程异常 import 结构错误
from 系统状态 import 生产规则集缺失


生产模式 = "PRODUCTION"
候选试验模式 = "CANDIDATE_TEST"


@dataclass(frozen=True)
class 标准记录:
    名称: str
    文档编号: str
    路径: str
    状态: str
    版本: str
    模式: str


class 标准加载错误(结构错误):
    pass


def _提取FrontMatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    normalized = text.lstrip("\ufeff")
    if not normalized.startswith("---\n"):
        raise 标准加载错误(f"规则缺少 Front Matter：{path}")
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise 标准加载错误(f"规则 Front Matter 缺少结束分隔符：{path}")
    loaded = yaml.safe_load(normalized[4:end]) or {}
    if not isinstance(loaded, dict):
        raise 标准加载错误(f"规则 Front Matter 必须是映射对象：{path}")
    return loaded


def _校验资格(root: Path, rel_path: str, entry: dict[str, Any], mode: str) -> None:
    path = root / rel_path
    if not path.exists():
        raise 标准加载错误(f"规则文件不存在：{rel_path}")
    if not entry.get("允许机器调用"):
        raise 标准加载错误(f"规则不允许机器调用：{rel_path}")

    status = entry.get("文档状态")
    source_allowed = entry.get("允许作为真源")
    if mode == 生产模式:
        if status not in {"ACTIVE", "FROZEN"} or source_allowed is not True:
            raise 标准加载错误(f"生产模式拒绝无真源资格规则：{rel_path} ({status})")
    elif mode == 候选试验模式:
        if status not in {"CANDIDATE", "ACTIVE", "FROZEN"}:
            raise 标准加载错误(f"候选试验模式拒绝非法状态规则：{rel_path} ({status})")
    else:
        raise 标准加载错误(f"未知标准加载模式：{mode}")


def _生产资格预检(specs: dict[str, Path], mode: str) -> None:
    if mode != 生产模式:
        return
    eligible = []
    for path in specs.values():
        if not path.exists():
            continue
        entry = _提取FrontMatter(path)
        if entry.get("文档状态") in {"ACTIVE", "FROZEN"} and entry.get("允许作为真源") is True:
            eligible.append(path)
    if not eligible:
        raise 生产规则集缺失()


def 加载标准文本(root: Path, specs: dict[str, Path], mode: str = 生产模式) -> tuple[dict[str, str], list[标准记录]]:
    _生产资格预检(specs, mode)
    texts: dict[str, str] = {}
    records: list[标准记录] = []
    for name, path in specs.items():
        rel_path = path.resolve().relative_to(root.resolve()).as_posix()
        entry = _提取FrontMatter(path)
        _校验资格(root, rel_path, entry, mode)
        texts[name] = path.read_text(encoding="utf-8-sig")
        records.append(
            标准记录(
                名称=name,
                文档编号=entry.get("文档编号", ""),
                路径=rel_path,
                状态=entry.get("文档状态", ""),
                版本=entry.get("当前版本", ""),
                模式=mode,
            )
        )
    return texts, records


def 标准记录转字典(records: Iterable[标准记录]) -> list[dict[str, str]]:
    return [record.__dict__.copy() for record in records]
