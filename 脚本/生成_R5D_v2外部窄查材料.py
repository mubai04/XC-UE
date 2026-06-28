"""R5D v2 外部窄查材料生成与机械预检（只读，不修改语料）。"""
from __future__ import annotations

import json
import random
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from l2_corpus_validate_lib import (
    clean_body,
    LEAKAGE_PATTERNS,
    META_PATTERNS,
    paragraph_for_quote,
    resolve_chapter,
    scan_patterns,
    segment_paragraphs,
    validate_case,
    validate_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot_v2"
OUT = V2 / "外部窄查材料"
V1_AUDIT = ROOT / "tests" / "fixtures" / "l2_real_api_pilot" / "results" / "R5D_语料质量审计_20260628"

EXT_LEAKAGE_PATTERNS = LEAKAGE_PATTERNS + [
    r"模型",
    r"模块",
    r"案例",
    r"测试样本",
    r"供诊断",
    r"便于识别",
    r"A类",
    r"B类",
    r"\bPASS\b",
    r"\bFAIL\b",
    r"\bREVIEW\b",
    r"文风问题",
    r"本文没有过渡",
    r"保持本案例特征",
    r"不应误判",
]

FILLER_PATTERNS = [
    r"段落补充",
    r"段落再续",
    r"段落延拓",
    r"夜色渐沉，远处人声与风声交错",
    r"延长篇幅",
    r"保持本案例",
    r"供真实",
    r"供模型",
]

BOUNDARY_HINTS: dict[str, str] = {
    "L2-01": "核对叙事结构/因果链，勿将文风或市场体验当主故障。",
    "L2-02": "核对文风与对话信息密度，勿将结构断裂或事实冲突当文风病。",
    "L2-03": "核对动机链是否完整，勿将市场入口弱当心理断裂。",
    "L2-04": "核对设定是否逼迫选择，勿将平淡完备判为压力不足，亦勿宣判硬冲突。",
    "L2-05": "核对阅读收益与章末推动力，勿将文风粗糙当市场体验主故障。",
    "L2-06": "核对事实冲突与合法状态变化，勿混淆 HARD_CONFLICT 与 ALLOWED_CHANGE。",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def number_paragraphs(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if not blocks:
        return text
    return "\n\n".join(f"[P{p:04d}]\n\n{b}" for p, b in enumerate(blocks, start=1))


def collect_supplementary(case_dir: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    ir_dir = case_dir / "IR"
    if ir_dir.is_dir():
        for path in sorted(ir_dir.glob("*.md")):
            items.append(
                {
                    "类型": "IR",
                    "路径": path.relative_to(V2).as_posix(),
                    "内容": path.read_text(encoding="utf-8").strip(),
                }
            )
    prior = case_dir / "chapters" / "prior.md"
    if prior.is_file():
        items.append(
            {
                "类型": "前序章节",
                "路径": prior.relative_to(V2).as_posix(),
                "内容": prior.read_text(encoding="utf-8").strip(),
            }
        )
    rules = case_dir / "project_rules.json"
    if rules.is_file():
        items.append(
            {
                "类型": "项目规则",
                "路径": rules.relative_to(V2).as_posix(),
                "内容": rules.read_text(encoding="utf-8").strip(),
            }
        )
    return items


def _scan_with_positions(text: str, patterns: list[str]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            hits.append(
                {
                    "pattern": pattern,
                    "match": match.group(0),
                    "context": text[start:end].replace("\n", " "),
                }
            )
    return hits


def _paragraph_blocks(case_dir: Path, project: dict[str, Any]) -> list[str]:
    chapter_path = resolve_chapter(case_dir, project)
    body = clean_body(chapter_path.read_text(encoding="utf-8"))
    return [p.text for p in segment_paragraphs(body)]


def cross_case_similarity(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    blocks_by_case: dict[str, list[str]] = {}
    for entry in manifest["cases"]:
        case_dir = (V2 / entry["case_dir"]).resolve()
        project = _load_json(case_dir / "project.json")
        blocks_by_case[entry["case_id"]] = _paragraph_blocks(case_dir, project)

    pairs: list[dict[str, Any]] = []
    ids = list(blocks_by_case.keys())
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            for ba in blocks_by_case[a]:
                if len(ba) < 40:
                    continue
                for bb in blocks_by_case[b]:
                    if len(bb) < 40:
                        continue
                    if ba == bb:
                        pairs.append(
                            {
                                "type": "identical_paragraph",
                                "case_a": a,
                                "case_b": b,
                                "snippet": ba[:120],
                            }
                        )
                    ratio = SequenceMatcher(None, ba, bb).ratio()
                    if ratio >= 0.85 and ba != bb:
                        pairs.append(
                            {
                                "type": "high_similarity",
                                "case_a": a,
                                "case_b": b,
                                "ratio": round(ratio, 3),
                                "snippet_a": ba[:80],
                                "snippet_b": bb[:80],
                            }
                        )
    failure_texts: dict[str, str] = {}
    for entry in manifest["cases"]:
        fi = _load_json((V2 / entry["case_dir"]) / "failure_item.json")
        failure_texts[entry["case_id"]] = json.dumps(fi, ensure_ascii=False)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if failure_texts[a] == failure_texts[b]:
                pairs.append({"type": "identical_failure_item", "case_a": a, "case_b": b})
    return pairs


def mechanical_precheck(manifest: dict[str, Any]) -> dict[str, Any]:
    dataset_report = validate_dataset(V2)
    per_case: list[dict[str, Any]] = []
    leakage_total = 0
    meta_total = 0
    filler_total = 0

    for entry in manifest["cases"]:
        auto = validate_case(V2, entry)
        case_dir = (V2 / entry["case_dir"]).resolve()
        project = _load_json(case_dir / "project.json")
        chapter_path = resolve_chapter(case_dir, project)
        raw = chapter_path.read_text(encoding="utf-8")
        body = clean_body(raw)
        leakage_hits = _scan_with_positions(body, EXT_LEAKAGE_PATTERNS)
        meta_hits = _scan_with_positions(body, META_PATTERNS)
        filler_hits = _scan_with_positions(body, FILLER_PATTERNS)
        leakage_total += len(leakage_hits)
        meta_total += len(meta_hits)
        filler_total += len(filler_hits)

        failure_item = _load_json(case_dir / "failure_item.json")
        fi_text = json.dumps(failure_item, ensure_ascii=False)
        fi_leakage = _scan_with_positions(fi_text, EXT_LEAKAGE_PATTERNS)

        purity_hints = [
            "人工核查：A类是否只呈现一个主缺陷，而非堆叠多模块严重问题。",
            "人工核查：B类正文是否自然成立，而非旁白声明无问题。",
            "人工核查：目标缺陷是否通过事件表现，而非作者解释。",
            "人工核查：failure_item 是否仅描述 L1 观测，未完整泄露 L2 根因与修复答案。",
        ]

        per_case.append(
            {
                "case_id": entry["case_id"],
                "module_id": entry["target_module"],
                "case_type": entry["case_type"],
                "file_integrity_ok": not auto["errors"],
                "file_errors": auto["errors"],
                "evidence_results": auto["evidence_results"],
                "leakage_hit_count": len(leakage_hits),
                "meta_hit_count": len(meta_hits),
                "filler_hit_count": len(filler_hits),
                "failure_item_scan_hits": len(fi_leakage),
                "leakage_hits": leakage_hits[:20],
                "meta_hits": meta_hits[:20],
                "filler_hits": filler_hits[:20],
                "purity_review_hints": purity_hints,
                "mechanical_status": "SCAN_COMPLETE",
            }
        )

    similarity = cross_case_similarity(manifest)
    mechanical_passed = dataset_report["validation_ok"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_validation_ok": dataset_report["validation_ok"],
        "mechanical_validation": "PASSED" if mechanical_passed else "FAILED",
        "leakage_scan_total": leakage_total,
        "meta_scan_total": meta_total,
        "filler_scan_total": filler_total,
        "cross_case_similarity_pairs": len(similarity),
        "similarity_details": similarity[:50],
        "per_case": per_case,
        "dataset_validation": dataset_report,
    }


def blank_review_form(review_label: str) -> dict[str, Any]:
    return {
        "review_case": review_label,
        "case_id": "",
        "module_id": "",
        "natural_fiction_text": "NOT_REVIEWED",
        "answer_leakage": "NOT_REVIEWED",
        "meta_text_contamination": "NOT_REVIEWED",
        "filler_contamination": "NOT_REVIEWED",
        "failure_evidence_valid": "NOT_REVIEWED",
        "target_defect_present": "NOT_REVIEWED",
        "single_primary_defect": "NOT_REVIEWED",
        "case_boundary_valid": "NOT_REVIEWED",
        "expected_separated_from_input": "NOT_REVIEWED",
        "overall_corpus_result": "NOT_REVIEWED",
        "decisive_findings": [],
        "required_action": "NOT_REVIEWED",
    }


def build_phase1_md(
    *,
    review_label: str,
    module_id: str,
    chapter_rel: str,
    chapter_numbered: str,
    supplementary: list[dict[str, str]],
    failure_item: dict[str, Any],
    char_count: int,
    paragraph_count: int,
    scan_summary: dict[str, Any],
) -> str:
    sup_lines = (
        "\n".join(f"- `{s['类型']}`：`{s['路径']}`" for s in supplementary)
        if supplementary
        else "- 无额外辅助材料"
    )
    scan_lines = [
        f"- 答案泄露模式命中：**{scan_summary['leakage_hit_count']}**（仅记录，不作最终结论）",
        f"- 元叙述模式命中：**{scan_summary['meta_hit_count']}**",
        f"- 填充文本模式命中：**{scan_summary['filler_hit_count']}**",
        f"- 文件完整性机械检查：{'通过' if scan_summary['file_integrity_ok'] else '有告警'}",
    ]
    if scan_summary.get("leakage_hits"):
        scan_lines.append("")
        scan_lines.append("命中示例（节选）：")
        for h in scan_summary["leakage_hits"][:5]:
            scan_lines.append(f"- `{h['pattern']}` → {h['context']}")

    return "\n".join(
        [
            f"# {review_label} · 正文审查包（第一阶段）",
            "",
            "> 本包不含 A/B 类型、expected、human_notes 与任何标准答案。",
            "",
            f"- **审查代号**：{review_label}",
            f"- **目标 L2 模块**：{module_id}",
            f"- **正文路径**：`{chapter_rel}`",
            f"- **字数**：{char_count}",
            f"- **段落数（正式切段）**：{paragraph_count}",
            "",
            "## 机械扫描发现（非最终结论）",
            "",
            *scan_lines,
            "",
            "## 完整正文",
            "",
            chapter_numbered,
            "",
            "## 辅助材料",
            "",
            sup_lines,
            "",
        ]
        + [
            f"### {s['类型']}（`{s['路径']}`）\n\n{s['内容']}\n"
            for s in supplementary
        ]
        + [
            "## failure_item.json",
            "",
            "```json",
            json.dumps(failure_item, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 人工填写",
            "",
            f"请填写 `案例审查表/{review_label}_审查表.json`。完成 12 例后再进入第二阶段。",
            "",
        ]
    )


def build_phase2_md(case_id: str, module_id: str, case_type: str, expected: dict[str, Any]) -> str:
    boundary = BOUNDARY_HINTS.get(module_id, "")
    return "\n".join(
        [
            f"# {case_id} · 预期对照（第二阶段）",
            "",
            f"- **case_id**：{case_id}",
            f"- **模块**：{module_id}",
            f"- **A/B 类型**：{case_type}",
            "",
            "## expected",
            "",
            "```json",
            json.dumps(expected, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 第一阶段应重点核对的能力边界",
            "",
            boundary,
            "",
            "对照时检查：acceptable_root_causes / forbidden_diagnoses 是否与正文独立判断一致。",
            "",
        ]
    )


def generate() -> dict[str, Any]:
    manifest = _load_json(V2 / "manifest.json")
    precheck = mechanical_precheck(manifest)

    phase1_dir = OUT / "第一阶段_正文审查包"
    phase2_dir = OUT / "第二阶段_预期对照包"
    forms_dir = OUT / "案例审查表"
    for d in (OUT, phase1_dir, phase2_dir, forms_dir):
        d.mkdir(parents=True, exist_ok=True)

    entries = list(manifest["cases"])
    rng = random.Random(20260628)
    shuffled = entries[:]
    rng.shuffle(shuffled)

    order_rows: list[dict[str, Any]] = []
    path_rows: list[str] = [
        "# v2 案例路径清单",
        "",
        "| 审查代号 | case_id | 模块 | 正文 | failure_item | expected | IR/前序/规则 | 字数 | 段落 | 机械扫描 |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]

    for idx, entry in enumerate(shuffled, start=1):
        review_label = f"审查案例-{idx:02d}"
        case_id = entry["case_id"]
        module_id = entry["target_module"]
        case_dir = (V2 / entry["case_dir"]).resolve()
        project = _load_json(case_dir / "project.json")
        chapter_path = resolve_chapter(case_dir, project)
        chapter_rel = chapter_path.relative_to(V2).as_posix()
        raw = chapter_path.read_text(encoding="utf-8")
        body = clean_body(raw)
        paragraphs = segment_paragraphs(body)
        supplementary = collect_supplementary(case_dir)
        failure_item = _load_json(case_dir / "failure_item.json")
        expected = _load_json(V2 / "expected" / f"{case_id}.expected.json")
        scan_row = next(c for c in precheck["per_case"] if c["case_id"] == case_id)

        phase1_md = build_phase1_md(
            review_label=review_label,
            module_id=module_id,
            chapter_rel=chapter_rel,
            chapter_numbered=number_paragraphs(raw),
            supplementary=supplementary,
            failure_item=failure_item,
            char_count=len(body),
            paragraph_count=len(paragraphs),
            scan_summary=scan_row,
        )
        (phase1_dir / f"{review_label}_正文审查包.md").write_text(phase1_md, encoding="utf-8")
        (phase2_dir / f"{case_id}_预期对照.md").write_text(
            build_phase2_md(case_id, module_id, entry["case_type"], expected),
            encoding="utf-8",
        )
        (forms_dir / f"{review_label}_审查表.json").write_text(
            json.dumps(blank_review_form(review_label), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        sup_desc = ", ".join(s["路径"] for s in supplementary) or "—"
        mech = "完整性OK" if scan_row["file_integrity_ok"] else "有告警"
        path_rows.append(
            f"| {review_label} | {case_id} | {module_id} | `{chapter_rel}` | "
            f"`{case_dir.relative_to(V2).as_posix()}/failure_item.json` | "
            f"`expected/{case_id}.expected.json` | {sup_desc} | {len(body)} | {len(paragraphs)} | {mech} |"
        )
        order_rows.append(
            {
                "order": idx,
                "review_label": review_label,
                "case_id": case_id,
                "module_id": module_id,
                "phase1_package": f"第一阶段_正文审查包/{review_label}_正文审查包.md",
                "phase2_package": f"第二阶段_预期对照包/{case_id}_预期对照.md",
                "review_form": f"案例审查表/{review_label}_审查表.json",
            }
        )

    (OUT / "v2案例路径清单.md").write_text("\n".join(path_rows), encoding="utf-8")

    precheck_payload = {
        "schema_version": "xcue.l2-v2-mechanical-precheck/1.0",
        **precheck,
        "status": {
            "R5D_V2_MECHANICAL_VALIDATION": precheck["mechanical_validation"],
            "R5D_V2_EXTERNAL_AUDIT_PACKAGE": "READY" if precheck["mechanical_validation"] == "PASSED" else "FAILED",
            "R5D_V2_CORPUS_PACKAGE": "READY" if precheck["mechanical_validation"] == "PASSED" else "FAILED",
            "R5D_V2_EXTERNAL_AUDIT": "PENDING",
            "L2_REAL_MODEL_EFFECTIVENESS": "NOT_TESTED",
        },
        "note": "扫描命中仅记录位置，不自动判定语料无效。最终有效性需外部人工审查。",
    }
    (OUT / "v2语料机械预检报告.json").write_text(
        json.dumps(precheck_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_lines = [
        "# v2 语料机械预检报告",
        "",
        f"- 生成时间：{precheck_payload['generated_at']}",
        f"- 语料校验器：`{'PASSED' if precheck['dataset_validation_ok'] else 'FAILED'}`",
        f"- `R5D_V2_MECHANICAL_VALIDATION = {precheck['mechanical_validation']}`",
        f"- 泄露扫描命中总数：{precheck['leakage_scan_total']}",
        f"- 元叙述扫描命中总数：{precheck['meta_scan_total']}",
        f"- 填充文本扫描命中总数：{precheck['filler_scan_total']}",
        f"- 跨案例相似片段对：{precheck['cross_case_similarity_pairs']}",
        "",
        "> 命中仅记录，不自动判无效。不得据此宣布 `R5D_V2_CORPUS = PASSED`。",
        "",
        "## 逐例摘要",
        "",
    ]
    for row in precheck["per_case"]:
        md_lines.append(
            f"- **{row['case_id']}**：泄露 {row['leakage_hit_count']} | 元叙述 {row['meta_hit_count']} | "
            f"填充 {row['filler_hit_count']} | 完整性 {'OK' if row['file_integrity_ok'] else 'FAIL'}"
        )
    (OUT / "v2语料机械预检报告.md").write_text("\n".join(md_lines), encoding="utf-8")

    scope = {
        "schema_version": "xcue.l2-v2-external-audit-scope/1.0",
        "included": [
            "v2 manifest 与 12 案例正文/failure_item/project",
            "必要 IR、前序章节、项目规则",
            "expected（仅第二阶段）",
            "机械预检报告与空白审查表",
        ],
        "excluded": [
            "v1 模型回答",
            "R5A/R5B/R5C 模型输出",
            "旧 R5D 人工评分",
            "L2 生产代码与提示词",
        ],
        "phase_1_order": order_rows,
        "historical_reference_only": str(V1_AUDIT.relative_to(ROOT).as_posix()) if V1_AUDIT.is_dir() else None,
    }
    (OUT / "外部窄查范围.json").write_text(json.dumps(scope, ensure_ascii=False, indent=2), encoding="utf-8")

    phase1_links = "\n".join(
        f"- [{r['review_label']}](第一阶段_正文审查包/{r['review_label']}_正文审查包.md) → "
        f"审查表：[{r['review_label']}](案例审查表/{r['review_label']}_审查表.json)"
        for r in order_rows
    )
    (OUT / "开始审查.md").write_text(
        "\n".join(
            [
                "# 开始审查 · v2 语料外部窄查",
                "",
                "```text",
                "第一步：打开「第一阶段_正文审查包/审查案例-01_正文审查包.md」。",
                "第二步：阅读完整正文 → 辅助材料 → failure_item。",
                "第三步：填写对应「案例审查表/审查案例-01_审查表.json」。",
                "第四步：完成案例 01 后再打开案例 02。",
                "第五步：12 例第一阶段全部完成前，不打开「第二阶段_预期对照包」。",
                "```",
                "",
                "## 案例可接受（须同时满足）",
                "",
                "1. 正文像自然小说片段",
                "2. 不直接说出诊断答案",
                "3. 不含评测和模型元叙述",
                "4. 不含机械填充",
                "5. failure evidence 真实且位置正确",
                "6. A 类目标缺陷真实存在",
                "7. B 类目标缺陷不成立或应正确转交",
                "8. 主要问题集中，不堆多个严重模块缺陷",
                "9. expected 未进入模型输入",
                "10. 更换人物名地点道具后逻辑仍成立",
                "",
                "## 整体 v2 通过条件",
                "",
                "- 12 例均完成外部人工审查",
                "- FAIL 案例为 0",
                "- REVIEW 案例修订后重新审查",
                "- 六模块均有有效 A/B",
                "- 无跨案例统一填充模板",
                "- failure evidence 错误为 0",
                "- 答案泄露为 0",
                "",
                "## 第一阶段阅读顺序",
                "",
                phase1_links,
                "",
                "第二阶段材料位于 `第二阶段_预期对照包/`（第一阶段完成后方可打开）。",
                "",
                f"机械预检：[`v2语料机械预检报告.md`](v2语料机械预检报告.md)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (OUT / "外部窄查结论模板.md").write_text(
        "\n".join(
            [
                "# 外部窄查结论模板（人工填写）",
                "",
                "## 整体结论（审查完成后填写）",
                "",
                "- 审查完成日期：",
                "- 审查人：",
                "- FAIL 案例数：",
                "- REVIEW 案例数：",
                "- 是否建议进入 v2 真实 API 试跑：",
                "",
                "## 声明",
                "",
                "- 本结论不由机械扫描自动生成",
                "- 不得在未完成 12 例审查时宣布 `R5D_V2_CORPUS = PASSED`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return precheck_payload


def main() -> int:
    info = generate()
    print(f"GENERATED: {OUT}")
    print(f"MECHANICAL: {info['status']['R5D_V2_MECHANICAL_VALIDATION']}")
    print(f"PACKAGE: {info['status']['R5D_V2_EXTERNAL_AUDIT_PACKAGE']}")
    return 0 if info["mechanical_validation"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
