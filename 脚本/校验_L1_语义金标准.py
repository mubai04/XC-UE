#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"
PUBLIC = EXEC / "公共组件"
L1 = EXEC / "L1工程"
for path in (PUBLIC, L1):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from L1读取 import 读文本
from 正文切分 import 切段, 清理正文
from 语义证据校验 import REQUIRED_DIMENSIONS, SCOPE_CURRENT, SCOPE_PRIOR, 定位摘句, 段落ID合法

GOLDEN_ROOT = ROOT / "tests" / "fixtures" / "l1_semantic_golden"
REQUIRED_SCENARIO_TAGS = frozenset(
    {
        "clear_pass",
        "clear_fail",
        "debatable_review",
        "low_lexical_good_narrative",
        "high_lexical_bad_narrative",
    }
)


def _scenario_tags(label: dict) -> set[str]:
    tags: set[str] = set()
    primary = str(label.get("scenario_tag", "")).strip()
    if primary:
        tags.add(primary)

    secondary = label.get("secondary_scenario_tags", [])
    if isinstance(secondary, list):
        tags.update(str(tag).strip() for tag in secondary if str(tag).strip())
    return tags


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _paragraph_maps(chapter_path: Path) -> tuple[dict[str, str], str]:
    raw = 读文本(chapter_path)
    title, body = 清理正文(raw)
    paragraphs = 切段(body)
    return {p.段落ID: p.文本 for p in paragraphs if p.段落ID}, title


def validate_label(label: dict, *, chapter_path: Path) -> list[str]:
    errors: list[str] = []
    required_top = (
        "chapter_id",
        "scenario_tag",
        "expected_overall",
        "expected_dimensions",
        "human_evidence",
        "acceptance_range",
        "unacceptable_misjudgments",
    )
    for key in required_top:
        if key not in label:
            errors.append(f"{label.get('chapter_id', chapter_path.stem)}: 缺少字段 {key}")

    expected_overall = str(label.get("expected_overall", "")).upper()
    if expected_overall not in {"PASS", "FAIL", "REVIEW"}:
        errors.append(f"{label.get('chapter_id')}: expected_overall 非法")

    primary_scenario = str(label.get("scenario_tag", "")).strip()
    if primary_scenario not in REQUIRED_SCENARIO_TAGS:
        errors.append(f"{label.get('chapter_id')}: scenario_tag 非法：{primary_scenario}")

    secondary_scenarios = label.get("secondary_scenario_tags", [])
    if secondary_scenarios is not None and not isinstance(secondary_scenarios, list):
        errors.append(f"{label.get('chapter_id')}: secondary_scenario_tags 必须是数组")
    elif isinstance(secondary_scenarios, list):
        invalid_secondary = {
            str(tag).strip()
            for tag in secondary_scenarios
            if str(tag).strip() not in REQUIRED_SCENARIO_TAGS
        }
        if invalid_secondary:
            errors.append(
                f"{label.get('chapter_id')}: secondary_scenario_tags 非法："
                + ", ".join(sorted(invalid_secondary))
            )

    dims = label.get("expected_dimensions")
    if not isinstance(dims, dict) or set(dims.keys()) != set(REQUIRED_DIMENSIONS):
        errors.append(f"{label.get('chapter_id')}: expected_dimensions 必须覆盖 6 个维度")

    paragraph_map, title = _paragraph_maps(chapter_path)
    if not paragraph_map:
        errors.append(f"{chapter_path}: 切段后无有效段落")

    evidence = label.get("human_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{label.get('chapter_id')}: human_evidence 不能为空")
    else:
        for idx, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"{label.get('chapter_id')}: human_evidence[{idx}] 必须是对象")
                continue
            pid = str(item.get("paragraph_id", "")).strip()
            exact = str(item.get("exact_text", ""))
            scope = str(item.get("source_scope", SCOPE_CURRENT)).strip()
            occ = item.get("occurrence_index", 0)
            if not 段落ID合法(pid):
                errors.append(f"{label.get('chapter_id')}: human_evidence[{idx}] paragraph_id 非法")
                continue
            if pid not in paragraph_map:
                errors.append(
                    f"{label.get('chapter_id')}: human_evidence[{idx}] {pid} 不在 L1 切段语料中（title={title}）"
                )
                continue
            if scope not in {SCOPE_CURRENT, SCOPE_PRIOR}:
                errors.append(f"{label.get('chapter_id')}: human_evidence[{idx}] source_scope 非法")
                continue
            if scope == SCOPE_PRIOR:
                errors.append(f"{label.get('chapter_id')}: human_evidence[{idx}] Phase2A 单章验收集不应引用 PRIOR_CHAPTER")
                continue
            if isinstance(occ, bool) or not isinstance(occ, int) or occ < 0:
                errors.append(f"{label.get('chapter_id')}: human_evidence[{idx}] occurrence_index 非法")
                continue
            if 定位摘句(paragraph_map[pid], exact, occ) is None:
                errors.append(
                    f"{label.get('chapter_id')}: human_evidence[{idx}] exact_text 无法在 {pid} 定位"
                )

    acceptance = label.get("acceptance_range")
    if not isinstance(acceptance, dict) or "overall" not in acceptance:
        errors.append(f"{label.get('chapter_id')}: acceptance_range.overall 必填")

    return errors


def validate_manifest(manifest: dict, golden_root: Path) -> list[str]:
    errors: list[str] = []
    chapters = manifest.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return ["manifest.chapters 为空"]
    seen_ids: set[str] = set()
    scenario_tags: set[str] = set()
    for entry in chapters:
        if not isinstance(entry, dict):
            errors.append("manifest.chapters 项必须是对象")
            continue
        chapter_id = entry.get("chapter_id")
        chapter_path = golden_root / str(entry.get("chapter_path", ""))
        label_path = golden_root / str(entry.get("label_path", ""))
        if not chapter_id or chapter_id in seen_ids:
            errors.append(f"chapter_id 重复或缺失：{chapter_id}")
        seen_ids.add(str(chapter_id))
        if not chapter_path.is_file():
            errors.append(f"正文不存在：{chapter_path}")
        if not label_path.is_file():
            errors.append(f"标签不存在：{label_path}")
            continue
        label = _load_json(label_path)
        if str(label.get("chapter_id", "")) != str(chapter_id):
            errors.append(f"{chapter_id}: 标签 chapter_id 与 manifest 不一致")
        scenario_tags.update(_scenario_tags(label))
        errors.extend(validate_label(label, chapter_path=chapter_path))
    missing = REQUIRED_SCENARIO_TAGS - scenario_tags
    if missing and len(chapters) >= 5:
        errors.append(f"五类场景未全覆盖，缺少：{', '.join(sorted(missing))}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate L1 Phase 2A golden corpus")
    parser.add_argument("--golden-root", default=str(GOLDEN_ROOT))
    args = parser.parse_args()
    golden_root = Path(args.golden_root)
    manifest = _load_json(golden_root / "manifest.json")
    errors = validate_manifest(manifest, golden_root)
    if errors:
        print("VALIDATION_FAILED")
        for err in errors:
            print(f"- {err}")
        return 1
    print("VALIDATION_OK")
    print(f"chapters: {len(manifest.get('chapters', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
