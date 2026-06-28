from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from 设定模型 import 代价, 限制, 规则

SETTING_RESPONSE_SCHEMA = "xcue.l2-setting-response/2.0"

SOURCE_CHAPTER = "CHAPTER"
SOURCE_IR = "IR"
SOURCE_PROJECT_RULE = "PROJECT_RULE"
SOURCE_FAILURE_EVIDENCE = "FAILURE_EVIDENCE"

ROLE_SETTING_RULE = "SETTING_RULE"
ROLE_CHAPTER_ACTION = "CHAPTER_ACTION"
ROLE_CHAPTER_META = "CHAPTER_META"
ROLE_IR_FACT = "IR_FACT"
ROLE_FAILURE_INPUT = "FAILURE_INPUT"

_META_MARKERS = ("正文未写", "IR 写明", "设定信息存在", "L2-04", "L2P-")


@dataclass
class 证据条目:
    evidence_id: str
    source_type: str
    source_path: str
    paragraph: int
    line_start: int
    line_end: int
    quote: str
    source_role: str


def _路径在案例内(case_root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(case_root.resolve())
        return True
    except ValueError:
        return False


def _相对路径(case_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(case_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _是项目规则文件(name: str) -> bool:
    lower = name.lower()
    return name.startswith("IR-02") or "约束" in name or "规则" in name


def _章节角色(quote: str) -> str:
    if any(m in quote for m in _META_MARKERS):
        return ROLE_CHAPTER_META
    if re.search(r"(不得|不能|禁止|只有|必须|除非|若|一旦|每次)", quote):
        return ROLE_SETTING_RULE
    return ROLE_CHAPTER_ACTION


def _追加证据(
    indexed: list[dict[str, Any]],
    by_id: dict[str, 证据条目],
    *,
    source_type: str,
    source_path: str,
    paragraph: int,
    line_start: int,
    line_end: int,
    quote: str,
    source_role: str,
) -> str | None:
    quote = quote if quote is not None else ""
    if not quote.strip():
        return None
    evidence_id = f"EVID-{len(indexed) + 1:04d}"
    entry = 证据条目(
        evidence_id=evidence_id,
        source_type=source_type,
        source_path=source_path,
        paragraph=paragraph,
        line_start=line_start,
        line_end=line_end,
        quote=quote,
        source_role=source_role,
    )
    indexed.append(
        {
            "evidence_id": evidence_id,
            "source_type": source_type,
            "source_path": source_path,
            "paragraph": paragraph,
            "line_start": line_start,
            "line_end": line_end,
            "quote": quote,
            "source_role": source_role,
        }
    )
    by_id[evidence_id] = entry
    return evidence_id


def 构建证据索引(
    *,
    case_root: Path,
    chapter_rel_path: str,
    paragraph_list: list[str],
    rules: list[规则],
    limits: list[限制],
    costs: list[代价],
    ir_dir: Path | None,
    failure_evidence: list[dict],
) -> tuple[list[dict[str, Any]], dict[str, 证据条目]]:
    case_root = case_root.resolve()
    indexed: list[dict[str, Any]] = []
    by_id: dict[str, 证据条目] = {}

    for p_idx, para in enumerate(paragraph_list, start=1):
        para = para.strip()
        if not para:
            continue
        _追加证据(
            indexed,
            by_id,
            source_type=SOURCE_CHAPTER,
            source_path=chapter_rel_path,
            paragraph=p_idx,
            line_start=0,
            line_end=0,
            quote=para,
            source_role=_章节角色(para),
        )

    for item in rules:
        _追加证据(
            indexed,
            by_id,
            source_type=SOURCE_CHAPTER,
            source_path=chapter_rel_path,
            paragraph=int(item.paragraph or 0),
            line_start=0,
            line_end=0,
            quote=str(item.quote or ""),
            source_role=ROLE_SETTING_RULE,
        )
    for item in limits:
        _追加证据(
            indexed,
            by_id,
            source_type=SOURCE_CHAPTER,
            source_path=chapter_rel_path,
            paragraph=int(item.paragraph or 0),
            line_start=0,
            line_end=0,
            quote=str(item.quote or ""),
            source_role=_章节角色(str(item.quote or "")),
        )
    for item in costs:
        _追加证据(
            indexed,
            by_id,
            source_type=SOURCE_CHAPTER,
            source_path=chapter_rel_path,
            paragraph=int(item.paragraph or 0),
            line_start=0,
            line_end=0,
            quote=str(item.quote or ""),
            source_role=ROLE_SETTING_RULE,
        )

    if ir_dir and ir_dir.is_dir() and _路径在案例内(case_root, ir_dir):
        for path in sorted(ir_dir.glob("IR-*.md")):
            if not _路径在案例内(case_root, path):
                continue
            rel = _相对路径(case_root, path)
            is_project_rule = _是项目规则文件(path.name)
            raw_lines = path.read_text(encoding="utf-8").splitlines()
            for line_no, line in enumerate(raw_lines, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if re.match(r"^[\|\s\-:]+$", stripped):
                    continue
                source_type = SOURCE_PROJECT_RULE if is_project_rule else SOURCE_IR
                role = ROLE_SETTING_RULE if is_project_rule else ROLE_IR_FACT
                _追加证据(
                    indexed,
                    by_id,
                    source_type=source_type,
                    source_path=rel,
                    paragraph=0,
                    line_start=line_no,
                    line_end=line_no,
                    quote=line,
                    source_role=role,
                )

    for fe in failure_evidence:
        if not isinstance(fe, dict):
            continue
        quote = str(fe.get("quote", "")).strip()
        if not quote:
            continue
        _追加证据(
            indexed,
            by_id,
            source_type=SOURCE_FAILURE_EVIDENCE,
            source_path=chapter_rel_path,
            paragraph=int(fe.get("paragraph") or 0),
            line_start=0,
            line_end=0,
            quote=quote,
            source_role=ROLE_FAILURE_INPUT,
        )

    return indexed, by_id


def 读取源文件摘句(case_root: Path | str, entry: 证据条目) -> str | None:
    root = Path(case_root)
    path = (root / entry.source_path).resolve()
    if not _路径在案例内(root, path) or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")
