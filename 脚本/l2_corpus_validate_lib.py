"""L2 业务评测语料：切段与校验辅助（纯本地）。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

LEAKAGE_PATTERNS = [
    r"没有过渡",
    r"无任何过渡",
    r"因果不收束",
    r"因果链完整",
    r"因果链闭合",
    r"动机不足",
    r"文风重复",
    r"设定没有推动",
    r"选择压力未落地",
    r"设定未逼迫",
    r"入口弱",
    r"认知负担",
    r"硬冲突",
    r"HARD_CONFLICT",
    r"ALLOWED_CHANGE",
    r"合法变化",
    r"正文未给出",
    r"叙事未收束",
    r"未收束",
    r"供模型诊断",
    r"标准答案",
    r"模块标签",
    r"本案例",
    r"测试样本",
    r"便于\s*L2",
    r"L2-\d{2}\s*[AB]\s*类",
    r"对\s*L2-\d{2}\s*而言",
    r"不应判",
    r"不应误判",
    r"边界样本",
    r"技术护栏",
    r"真实\s*API\s*试跑",
    r"延长章节篇幅",
    r"延长可读上下文",
    r"段落补充",
    r"段落再续",
    r"段落延拓",
    r"保持本案例",
    r"模块诊断",
    r"不新增模块",
]

META_PATTERNS = [
    r"供模型",
    r"供真实",
    r"真实模型",
    r"评测",
    r"试跑",
    r"诊断器",
    r"标准答案",
    r"模块标签",
    r"本案例",
    r"延长篇幅",
    r"延长章节",
    r"连载段落长度",
]

EXPECTED_FIELD_NAMES = (
    "expected_issue_present",
    "acceptable_root_causes",
    "forbidden_diagnoses",
    "human_notes",
    "minimum_action_requirements",
)


@dataclass
class Paragraph:
    number: int
    text: str


def clean_body(raw: str) -> str:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        body.append(line)
    return "\n".join(body).strip()


def segment_paragraphs(text: str) -> list[Paragraph]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    return [Paragraph(i, block) for i, block in enumerate(blocks, start=1)]


def find_quote_in_body(body: str, quote: str) -> bool:
    return quote in body


def paragraph_for_quote(paragraphs: list[Paragraph], quote: str) -> int | None:
    for p in paragraphs:
        if quote in p.text:
            return p.number
    return None


def scan_patterns(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            snippet = text[max(0, match.start() - 20): match.end() + 20].replace("\n", " ")
            hits.append(f"{pattern}: …{snippet}…")
    return hits


def load_manifest(dataset_root: Path) -> dict[str, Any]:
    return json.loads((dataset_root / "manifest.json").read_text(encoding="utf-8"))


def case_paths(dataset_root: Path, case_dir_rel: str) -> dict[str, Path]:
    case_dir = (dataset_root / case_dir_rel).resolve()
    return {
        "case_dir": case_dir,
        "chapter": case_dir / "chapters" / "chapter.md",
        "failure_item": case_dir / "failure_item.json",
        "project": case_dir / "project.json",
        "expected": dataset_root / "expected" / f"{case_dir.name}.expected.json",
    }


def resolve_chapter(case_dir: Path, project: dict[str, Any]) -> Path:
    for key in ("default_chapter", "entrypoint"):
        rel = project.get(key)
        if isinstance(rel, str) and rel.strip():
            path = (case_dir / rel).resolve()
            if path.is_file():
                return path
    raise FileNotFoundError(f"CASE_CHAPTER_NOT_RESOLVED: {case_dir}")


def check_expected_not_in_chapter(chapter_text: str, expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in EXPECTED_FIELD_NAMES:
        if key in chapter_text:
            errors.append(f"正文含 expected 字段名 {key}")
    for key in ("acceptable_root_causes", "forbidden_diagnoses", "minimum_action_requirements"):
        for item in expected.get(key) or []:
            if isinstance(item, str) and len(item) >= 8 and item in chapter_text:
                errors.append(f"正文复现 expected 值：{item}")
    notes = str(expected.get("human_notes", ""))
    if len(notes) >= 12 and notes in chapter_text:
        errors.append("正文复现 human_notes")
    return errors


def validate_case(dataset_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    paths = case_paths(dataset_root, entry["case_dir"])
    case_id = entry["case_id"]
    project = json.loads(paths["project"].read_text(encoding="utf-8"))
    chapter_path = resolve_chapter(paths["case_dir"], project)
    raw = chapter_path.read_text(encoding="utf-8")
    body = clean_body(raw)
    paragraphs = segment_paragraphs(body)
    failure_item = json.loads(paths["failure_item"].read_text(encoding="utf-8"))
    expected_path = paths["expected"]
    expected = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.is_file() else {}

    errors: list[str] = []
    leakage_hits = scan_patterns(body, LEAKAGE_PATTERNS)
    meta_hits = scan_patterns(body, META_PATTERNS)
    filler_hits = scan_patterns(body, [r"段落补充", r"段落再续", r"段落延拓", r"夜色渐沉，远处人声与风声交错"])

    if leakage_hits:
        errors.append(f"疑似答案泄露 {len(leakage_hits)} 处")
    if meta_hits:
        errors.append(f"疑似元叙述 {len(meta_hits)} 处")
    if filler_hits:
        errors.append(f"疑似填充段 {len(filler_hits)} 处")

    errors.extend(check_expected_not_in_chapter(body, expected))

    evidence_results: list[dict[str, Any]] = []
    for ev in failure_item.get("证据") or []:
        quote = str(ev.get("摘句", ""))
        declared = ev.get("段落")
        found_para = paragraph_for_quote(paragraphs, quote) if quote else None
        quote_ok = find_quote_in_body(body, quote) if quote else False
        para_ok = found_para == declared if quote_ok and declared is not None else False
        if not quote_ok:
            errors.append(f"failure evidence 摘句不存在：{quote[:40]}")
        elif declared is not None and found_para != declared:
            errors.append(
                f"failure evidence 段落错误：声明 {declared}，实际 {found_para}，摘句={quote[:30]}"
            )
        evidence_results.append(
            {
                "段落": declared,
                "摘句": quote,
                "quote_found": quote_ok,
                "actual_paragraph": found_para,
                "paragraph_match": para_ok,
            }
        )

    return {
        "case_id": case_id,
        "module_id": entry.get("target_module"),
        "case_type": entry.get("case_type"),
        "chapter_path": str(chapter_path),
        "paragraph_count": len(paragraphs),
        "char_count": len(body),
        "errors": errors,
        "leakage_hits": leakage_hits,
        "meta_hits": meta_hits,
        "filler_hits": filler_hits,
        "evidence_results": evidence_results,
        "validation_ok": not errors,
    }


def validate_dataset(dataset_root: Path) -> dict[str, Any]:
    manifest = load_manifest(dataset_root)
    cases = []
    all_ok = True
    for entry in manifest.get("cases") or []:
        result = validate_case(dataset_root, entry)
        cases.append(result)
        if not result["validation_ok"]:
            all_ok = False
    return {
        "dataset_root": str(dataset_root),
        "schema_version": manifest.get("schema_version"),
        "validation_ok": all_ok,
        "cases": cases,
    }
