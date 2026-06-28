"""R5D：生成本地人工业务评审材料（不调用 API，不修改评分）。"""
from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
R5C_RUN = PILOT / "results" / "L2_R5C_全量技术复测_20260628"
R5D_DIR = PILOT / "results" / "R5D_人工业务评审_20260628"
MANIFEST_PATH = PILOT / "manifest.json"
EXPECTED_DIR = PILOT / "expected"

SCORE_FIELDS = (
    "diagnosis_correct",
    "evidence_relevant",
    "root_cause_specific",
    "fix_actions_executable",
    "acceptance_criteria_testable",
    "forbidden_scope_respected",
    "cross_module_overreach",
    "reroute_correct",
    "overall_business_result",
)

RECOMMENDED_ACTIONS = ("ACCEPT", "CALIBRATE", "REROUTE", "REJECT")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_model_json(raw_response: str) -> dict[str, Any] | None:
    if not raw_response:
        return None
    try:
        envelope = json.loads(raw_response)
        content = envelope["choices"][0]["message"]["content"]
        return json.loads(content)
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        return None


def _final_attempt(case_result_dir: Path) -> dict[str, Any]:
    attempts = sorted(case_result_dir.glob("attempt_*.json"), key=lambda p: p.name)
    if not attempts:
        raise FileNotFoundError(f"缺少 attempt 记录：{case_result_dir}")
    return _load_json(attempts[-1])


def _redact_failure_item_for_blind(failure_item: dict[str, Any], blind_label: str) -> dict[str, Any]:
    """盲评展示用：不修改 fixture，仅生成阶段脱敏。"""
    redacted = json.loads(json.dumps(failure_item, ensure_ascii=False))
    if isinstance(redacted.get("名称"), str):
        redacted["名称"] = blind_label
    if isinstance(redacted.get("说明"), str):
        redacted["说明"] = re.sub(r"L2P-\d{3}", blind_label, redacted["说明"])
    return redacted


def _read_supplementary(case_dir: Path) -> dict[str, str]:
    parts: dict[str, str] = {}
    ir_dir = case_dir / "IR"
    if ir_dir.is_dir():
        chunks: list[str] = []
        for path in sorted(ir_dir.glob("*.md")):
            chunks.append(f"### {path.name}\n\n{path.read_text(encoding='utf-8').strip()}")
        if chunks:
            parts["IR材料"] = "\n\n".join(chunks)
    prior = case_dir / "chapters" / "prior.md"
    if prior.is_file():
        parts["前序章节"] = prior.read_text(encoding="utf-8").strip()
    return parts


def _blank_case_score(case_id: str, module_id: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": case_id,
        "module_id": module_id,
        "review_phase": "NOT_STARTED",
    }
    for field in SCORE_FIELDS:
        row[field] = "NOT_REVIEWED"
    row["reviewer_notes"] = ""
    row["decisive_evidence"] = []
    row["major_defects"] = []
    row["recommended_action"] = "NOT_REVIEWED"
    return row


def _blank_phase2_score(case_id: str, module_id: str) -> dict[str, Any]:
    row = _blank_case_score(case_id, module_id)
    row["phase_1_overall"] = ""
    row["phase_2_overall"] = ""
    row["rating_changed"] = False
    row["change_reason"] = ""
    return row


def _format_repair_form(form: dict[str, Any] | None) -> str:
    if not form:
        return "_（未生成修复单）_"
    lines = [
        f"- **接收模块**: {form.get('接收模块', '')}",
        f"- **主失败类型**: {form.get('主失败类型', '')}",
        f"- **是否需要回L15重路由**: {form.get('是否需要回L15重路由', '')}",
        f"- **修复动作**: {form.get('修复动作', '')}",
        f"- **验收问题**: {form.get('验收问题', '')}",
        f"- **规则依据**: {form.get('规则依据', '')}",
    ]
    evidence = form.get("诊断证据") or []
    if evidence:
        lines.append("- **诊断证据**:")
        for ev in evidence:
            if isinstance(ev, dict):
                lines.append(f"  - 段落 {ev.get('段落', '?')}：{ev.get('摘句', '')}")
    actions = form.get("标准动作") or []
    if actions:
        lines.append("- **标准动作**:")
        for action in actions:
            lines.append(f"  - {action}")
    acceptance = form.get("标准验收") or []
    if acceptance:
        lines.append("- **标准验收**:")
        for item in acceptance:
            lines.append(f"  - {item}")
    return "\n".join(lines)


def _format_model_output(parsed: dict[str, Any] | None, attempt: dict[str, Any]) -> str:
    if not parsed:
        err = attempt.get("error_message") or attempt.get("validation_errors")
        return f"_（模型 JSON 未解析；技术信息：{err}）_"
    lines = [f"- **root_cause**: {parsed.get('root_cause', '')}"]
    if parsed.get("needs_reroute") is not None:
        lines.append(f"- **needs_reroute**: {parsed.get('needs_reroute')}")
    for key in (
        "setting_pressure_points",
        "style_issues",
        "motivation_gaps",
        "consistency_conflicts",
        "experience_risks",
    ):
        items = parsed.get(key)
        if isinstance(items, list) and items:
            lines.append(f"- **{key}**:")
            lines.append(f"```json\n{json.dumps(items, ensure_ascii=False, indent=2)}\n```")
    quotes = parsed.get("evidence_quotes")
    if isinstance(quotes, list) and quotes:
        lines.append(f"- **evidence_quotes**:")
        lines.append(f"```json\n{json.dumps(quotes, ensure_ascii=False, indent=2)}\n```")
    for key in ("fix_actions", "acceptance_criteria"):
        items = parsed.get(key)
        if isinstance(items, list) and items:
            lines.append(f"- **{key}**:")
            for item in items:
                lines.append(f"  - {item}")
    return "\n".join(lines)


def _build_blind_md(
    *,
    blind_label: str,
    module_id: str,
    chapter_text: str,
    failure_item: dict[str, Any],
    supplementary: dict[str, str],
    attempt: dict[str, Any],
    tech: dict[str, Any],
    parsed: dict[str, Any] | None,
) -> str:
    parts = [
        f"# 第一阶段盲评 · {blind_label}",
        "",
        "> 本表不含 A/B 类型、expected、human_notes 与负例/边界例标签。",
        "",
        f"- **评审代号**: {blind_label}",
        f"- **目标模块**: {module_id}",
        f"- **技术状态**: {tech.get('final_status', '')}",
        f"- **重试次数**: {tech.get('retry_count', 0)}",
        f"- **attempt 数**: {tech.get('attempts', 1)}",
        "",
        "## failure item",
        "",
        "```json",
        json.dumps(failure_item, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 正文",
        "",
        chapter_text.strip(),
        "",
    ]
    for title, body in supplementary.items():
        parts.extend([f"## {title}", "", body, ""])
    parts.extend(
        [
            "## 模型诊断结果",
            "",
            _format_model_output(parsed, attempt),
            "",
            "## 修复单",
            "",
            _format_repair_form(attempt.get("repair_form")),
            "",
            "## 第一阶段评分",
            "",
            "请填写同目录下对应的 `*_盲评评分.json`，全部字段不得留空后再进入第二阶段。",
            "",
        ]
    )
    return "\n".join(parts)


def _build_reconcile_md(
    *,
    case_id: str,
    module_id: str,
    blind_label: str,
    expected: dict[str, Any],
    attempt: dict[str, Any],
    tech: dict[str, Any],
) -> str:
    form = attempt.get("repair_form") or {}
    return "\n".join(
        [
            f"# 第二阶段对照复核 · {case_id}",
            "",
            f"- **评审代号**: {blind_label}",
            f"- **case_id**: {case_id}",
            f"- **module_id**: {module_id}",
            f"- **技术状态**: {tech.get('final_status', '')}",
            "",
            "## expected（对照真源）",
            "",
            "```json",
            json.dumps(expected, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 模型最终输出摘要",
            "",
            f"- root_cause / 输入问题: {form.get('输入问题', form.get('规则依据', ''))}",
            f"- 修复动作: {form.get('修复动作', '')}",
            f"- 是否需要回L15重路由: {form.get('是否需要回L15重路由', '')}",
            "",
            "## 复核清单",
            "",
            "- [ ] 对比 `expected_issue_present` 与模型诊断方向",
            "- [ ] 检查 `acceptable_root_causes` / `forbidden_diagnoses`",
            "- [ ] 对 REVIEW 项给出保留或改判",
            "- [ ] 确认是否误诊、漏诊、越权",
            "- [ ] 更新 `{case_id}_评分.json` 并同步 `人工评分汇总.json`",
            "",
        ]
    )


def generate(review_dir: Path = R5D_DIR) -> dict[str, Any]:
    if not R5C_RUN.is_dir():
        raise FileNotFoundError(f"缺少 R5C 结果目录：{R5C_RUN}")
    manifest = _load_json(MANIFEST_PATH)
    summary = _load_json(R5C_RUN / "summary.json")
    per_case_tech = summary.get("technical", {}).get("per_case", {})

    blind_dir = review_dir / "案例评审表" / "盲评"
    reconcile_dir = review_dir / "案例评审表" / "对照复核"
    score_dir = review_dir / "案例评审表"
    blind_dir.mkdir(parents=True, exist_ok=True)
    reconcile_dir.mkdir(parents=True, exist_ok=True)

    cases = list(manifest.get("cases") or [])
    rng = random.Random(20260628)
    shuffled = cases[:]
    rng.shuffle(shuffled)
    blind_order = []
    score_rows = []

    for idx, entry in enumerate(shuffled, start=1):
        case_id = str(entry["case_id"])
        module_id = str(entry["target_module"])
        blind_label = f"评审案例-{idx:02d}"
        case_dir = (PILOT / str(entry["case_dir"])).resolve()
        result_dir = R5C_RUN / "cases" / case_id
        expected_path = EXPECTED_DIR / f"{case_id}.expected.json"
        expected = _load_json(expected_path) if expected_path.is_file() else {}

        chapter = (case_dir / "chapters" / "chapter.md").read_text(encoding="utf-8")
        failure_item = _load_json(case_dir / "failure_item.json")
        attempt = _final_attempt(result_dir)
        parsed = _extract_model_json(str(attempt.get("raw_response") or ""))
        supplementary = _read_supplementary(case_dir)
        tech = per_case_tech.get(case_id, {})

        blind_failure = _redact_failure_item_for_blind(failure_item, blind_label)
        blind_md = _build_blind_md(
            blind_label=blind_label,
            module_id=module_id,
            chapter_text=chapter,
            failure_item=blind_failure,
            supplementary=supplementary,
            attempt=attempt,
            tech=tech,
            parsed=parsed,
        )
        (blind_dir / f"{blind_label}.md").write_text(blind_md, encoding="utf-8")

        blind_score = _blank_case_score(case_id, module_id)
        blind_score["blind_label"] = blind_label
        blind_score["review_phase"] = "PHASE_1_BLIND"
        (score_dir / f"{case_id}_盲评评分.json").write_text(
            json.dumps(blind_score, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        reconcile_md = _build_reconcile_md(
            case_id=case_id,
            module_id=module_id,
            blind_label=blind_label,
            expected=expected,
            attempt=attempt,
            tech=tech,
        )
        (reconcile_dir / f"{case_id}_对照复核.md").write_text(reconcile_md, encoding="utf-8")

        final_score = _blank_phase2_score(case_id, module_id)
        final_score["blind_label"] = blind_label
        final_score["review_phase"] = "PHASE_2_PENDING"
        (score_dir / f"{case_id}_评分.json").write_text(
            json.dumps(final_score, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        blind_order.append(
            {
                "order": idx,
                "blind_label": blind_label,
                "case_id": case_id,
                "module_id": module_id,
                "case_type": entry.get("case_type"),
                "score_files": {
                    "phase_1": f"案例评审表/{case_id}_盲评评分.json",
                    "phase_2": f"案例评审表/{case_id}_评分.json",
                },
            }
        )
        score_rows.append(final_score)

    order_payload = {
        "schema_version": "xcue.l2-human-review-order/1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run_id": summary.get("run_id"),
        "review_dir": review_dir.name,
        "note": "第一阶段评审者不应查看 case_id 映射；对照人可在第二阶段使用本文件。",
        "phase_1_order": blind_order,
    }
    (review_dir / "盲评顺序.json").write_text(
        json.dumps(order_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_payload = {
        "schema_version": "xcue.l2-human-review-summary/1.0",
        "phase": "R5D",
        "source_run_id": summary.get("run_id"),
        "status": "AWAITING_HUMAN_REVIEW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": score_rows,
        "statistics": None,
        "gate_result": None,
    }
    (review_dir / "人工评分汇总.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (review_dir / "人工评分汇总.md").write_text(
        "\n".join(
            [
                "# R5D 人工评分汇总（空白）",
                "",
                "请在完成两阶段评审后，将各 `{case_id}_评分.json` 汇总到本文件对应的 `cases` 数组。",
                "",
                "当前状态：`AWAITING_HUMAN_REVIEW`",
                "",
                "## 第一阶段注意",
                "",
                "- 盲评材料位于 `案例评审表/盲评/`，按 `盲评顺序.json` 的 `phase_1_order` 顺序评审。",
                "- 第一阶段评审者**不应**查看 `盲评顺序.json` 中的 `case_id` / `case_type` 映射。",
                "- 对照映射仅在第二阶段由复核人使用。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (review_dir / "争议案例清单.md").write_text(
        "\n".join(
            [
                "# 争议案例清单",
                "",
                "第二阶段复核时，将 REVIEW 项与 expected 冲突的案例记录于此。",
                "",
                "| case_id | blind_label | 争议点 | 最终裁决 | 备注 |",
                "|---|---|---|---|---|",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (review_dir / "R5D_最终业务评审报告.md").write_text(
        "\n".join(
            [
                "# R5D 最终业务评审报告（占位）",
                "",
                "> 人工评分未完成前不得填写最终 PILOT 结论。",
                "",
                "完成评分后运行：",
                "",
                "```powershell",
                f'python "脚本/汇总_L2_人工业务评分.py" --review-dir "{review_dir.as_posix()}"',
                "```",
                "",
                "当前状态：",
                "",
                "```",
                "L2_R5D_BUSINESS_PILOT = AWAITING_HUMAN_REVIEW",
                "L2_REAL_MODEL_EFFECTIVENESS = NOT_TESTED",
                "PRODUCTION_ELIGIBLE = false",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (review_dir / "评审说明.md").write_text(
        "\n".join(
            [
                "# R5D L2 真实模型人工业务评审说明",
                "",
                "## 真源",
                "",
                f"- 试跑结果：`{R5C_RUN.relative_to(ROOT).as_posix()}`",
                f"- 案例与 expected：`tests/fixtures/l2_real_api_pilot/`",
                "",
                "## 两阶段流程",
                "",
                "1. **第一阶段盲评**：按 `盲评顺序.json` 的 `phase_1_order` 顺序，只阅读 `案例评审表/盲评/` 下材料，填写 `{case_id}_盲评评分.json`。",
                "2. **第二阶段对照复核**：阅读 `案例评审表/对照复核/` 与 expected，更新 `{case_id}_评分.json`，必要时记录 `争议案例清单.md`。",
                "3. **汇总**：运行 `脚本/汇总_L2_人工业务评分.py` 生成本地统计与门槛判定（不得由模型代填）。",
                "",
                "## 禁止事项",
                "",
                "- 不调用新的真实 API",
                "- 不修改 12 例正文、IR、expected",
                "- 不把 REVIEW 自动计为 PASS",
                "- 不让模型完成业务评分",
                "",
                "## 评分字段",
                "",
                "见各 `*_评分.json` 模板与任务说明中的 PASS / REVIEW / FAIL 标准。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "review_dir": str(review_dir),
        "case_count": len(cases),
        "blind_order": [row["blind_label"] for row in blind_order],
    }


def main() -> int:
    import shutil

    if R5D_DIR.exists():
        shutil.rmtree(R5D_DIR)
    R5D_DIR.mkdir(parents=True, exist_ok=True)
    info = generate(R5D_DIR)
    print(f"GENERATED: {info['review_dir']}")
    print(f"cases: {info['case_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
