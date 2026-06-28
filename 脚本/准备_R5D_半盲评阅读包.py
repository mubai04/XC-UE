"""R5D-1：生成半盲评阅读包与评审导航（纯本地，不调用 API）。"""
from __future__ import annotations

import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from r5d_半盲评公共 import (
    HIDDEN_PHASE1_TOKENS,
    PILOT,
    R5C_RUN,
    R5D_DIR,
    SEMI_BLIND_METADATA,
    blank_phase1_score,
    blank_phase2_score,
    collect_supplementary,
    extract_model_json,
    final_attempt,
    load_json,
    number_paragraphs,
    parse_repair_scope,
    resolve_chapter_path,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PILOT / "manifest.json"

SCORE_QUESTIONS: list[tuple[str, str, str, str]] = [
    (
        "diagnosis_correct",
        "① 问题判断对不对？",
        "正文里是否真的存在模型说的问题？模型有没有把别的问题说成本模块问题？正常内容是否被强行判病？",
        "对应字段：`diagnosis_correct`",
    ),
    (
        "evidence_relevant",
        "② 引用的证据能证明这个问题吗？",
        "摘句存在，不等于摘句能证明结论。看完摘句后，你是否自然得到模型的判断？",
        "对应字段：`evidence_relevant`",
    ),
    (
        "root_cause_specific",
        "③ 根因说得具体吗？",
        "具体例：「角色没有从得知危险过渡到冒险开门的理由。」空泛例：「人物动机不足。」",
        "对应字段：`root_cause_specific`",
    ),
    (
        "fix_actions_executable",
        "④ 修复动作能直接照着做吗？",
        "具体例：「在第6段开门前补一处角色确认妹妹仍在门后的信息。」空泛例：「增强人物动机。」",
        "对应字段：`fix_actions_executable`",
    ),
    (
        "acceptance_criteria_testable",
        "⑤ 修完后能检查是否成功吗？",
        "验收标准是否能通过重新阅读正文判断，而不是「更精彩」「更有吸引力」一类主观口号。",
        "对应字段：`acceptance_criteria_testable`",
    ),
    (
        "forbidden_scope_respected",
        "⑥ 有没有改动不该由本模块改的内容？",
        "文风模块不得改世界规则；市场模块不得重写人物核心目标；角色模块不得凭空新增设定；一致性模块不得删除合法状态变化。没有越界填 PASS，有明显越界填 FAIL。",
        "对应字段：`forbidden_scope_respected`",
    ),
    (
        "cross_module_overreach",
        "⑦ 有没有抢其他模块的工作？",
        "没有跨模块越权填 PASS，明显把别的模块问题当自己问题填 FAIL。",
        "对应字段：`cross_module_overreach`",
    ),
    (
        "reroute_correct",
        "⑧ 该转交其他模块时，转交对了吗？",
        "若本例不需要转交，模型留在本模块处理合理，可填 PASS。",
        "对应字段：`reroute_correct`",
    ),
]


def _format_failure_item_plain(failure_item: dict[str, Any]) -> str:
    evidence_lines = []
    for ev in failure_item.get("证据") or []:
        if isinstance(ev, dict):
            evidence_lines.append(f"- 段落 {ev.get('段落', '?')}：{ev.get('摘句', '')}")
    return "\n".join(
        [
            f"- **检测到的问题**：{failure_item.get('名称', '')} — {failure_item.get('说明', '')}",
            f"- **失败类型**：{failure_item.get('失败类型', '')}",
            f"- **严重级别**：{failure_item.get('严重级别', '')}",
            f"- **建议模块**：{failure_item.get('候选模块', '')}",
            f"- **修复方向**：{failure_item.get('修复方向', '')}",
            "",
            "**L1/L1.5 给出的证据**：",
            *(evidence_lines or ["- （无）"]),
            "",
            "**原始 failure_item.json**：",
            "",
            "```json",
            json.dumps(failure_item, ensure_ascii=False, indent=2),
            "```",
        ]
    )


def _format_model_diagnosis(parsed: dict[str, Any] | None, attempt: dict[str, Any]) -> str:
    if not parsed:
        return f"_模型 JSON 未能解析。技术状态：{attempt.get('transport_status', '')}_"
    lines = [f"- **root cause**：{parsed.get('root_cause', '')}"]
    if parsed.get("needs_reroute") is not None:
        lines.append(f"- **是否建议 reroute**：{parsed.get('needs_reroute')}")
    for key in (
        "style_issues",
        "motivation_gaps",
        "setting_pressure_points",
        "consistency_conflicts",
        "experience_risks",
    ):
        items = parsed.get(key)
        if isinstance(items, list) and items:
            lines.append(f"- **{key}**：")
            lines.append("```json")
            lines.append(json.dumps(items, ensure_ascii=False, indent=2))
            lines.append("```")
    for key in ("fix_actions", "acceptance_criteria"):
        items = parsed.get(key)
        if isinstance(items, list) and items:
            lines.append(f"- **{key}**：")
            for item in items:
                lines.append(f"  - {item}")
    return "\n".join(lines)


def _format_evidence_list(
    *,
    parsed: dict[str, Any] | None,
    repair_form: dict[str, Any] | None,
    root_cause: str,
) -> str:
    rows: list[str] = []
    idx = 1
    form = repair_form or {}
    for ev in form.get("诊断证据") or []:
        if not isinstance(ev, dict):
            continue
        rows.extend(
            [
                f"### 证据 {idx}",
                f"- **来源类型**：修复单诊断证据",
                f"- **来源文件**：R5C 最终 attempt / repair_form",
                f"- **段落**：{ev.get('段落', '—')}",
                f"- **摘句**：{ev.get('摘句', '')}",
                f"- **模型用来证明什么**：{root_cause or form.get('规则依据', '')}",
                "",
            ]
        )
        idx += 1
    if parsed:
        for ev in parsed.get("evidence_quotes") or []:
            if not isinstance(ev, dict):
                continue
            if ev.get("evidence_id"):
                rows.extend(
                    [
                        f"### 证据 {idx}",
                        f"- **来源类型**：模型 evidence_id 引用",
                        f"- **来源文件**：indexed_evidence（R5C 请求上下文）",
                        f"- **证据 ID**：{ev.get('evidence_id')}",
                        f"- **段落**：—",
                        f"- **摘句**：见 indexed_evidence 索引",
                        f"- **模型用来证明什么**：见 setting_pressure_points / 根因分析",
                        "",
                    ]
                )
            elif ev.get("quote"):
                rows.extend(
                    [
                        f"### 证据 {idx}",
                        f"- **来源类型**：模型 evidence_quotes",
                        f"- **来源文件**：正文",
                        f"- **段落**：{ev.get('paragraph', '—')}",
                        f"- **摘句**：{ev.get('quote', '')}",
                        f"- **模型用来证明什么**：{root_cause}",
                        "",
                    ]
                )
            idx += 1
    return "\n".join(rows) if rows else "_（无结构化证据条目）_"


def _format_repair_form_section(form: dict[str, Any] | None) -> str:
    if not form:
        return "_（未生成修复单）_"
    scope = parse_repair_scope(str(form.get("规则依据", "")))
    lines = [
        f"- **修复动作**：{form.get('修复动作', '')}",
        f"- **修改范围**：{scope.get('修改范围') or '（见规则依据）'}",
        f"- **禁止修改范围**：{scope.get('禁止修改范围') or '（见规则依据）'}",
        f"- **必须保留内容**：{form.get('修复产物', '') or '（修复单未单列，请结合禁止范围理解）'}",
        f"- **验收标准**：{form.get('验收问题', '')}",
        f"- **回流位置**：{form.get('回流位置', '')}",
        "",
        "**标准动作**：",
    ]
    for action in form.get("标准动作") or []:
        lines.append(f"- {action}")
    lines.extend(["", "**标准验收**："])
    for item in form.get("标准验收") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "**原始 repair_form**：",
            "",
            "```json",
            json.dumps(form, ensure_ascii=False, indent=2),
            "```",
        ]
    )
    return "\n".join(lines)


def _format_scoring_section(score_rel: str) -> str:
    lines = [
        "请填写评分文件：`" + score_rel + "`",
        "",
        "评分选项：",
        "- **PASS**：基本正确，可以直接采用",
        "- **REVIEW**：方向有用，但需要人工修正",
        "- **FAIL**：判断错误、证据不支持、动作无法执行或发生越权",
        "- **NOT_REVIEWED**：尚未评价",
        "",
    ]
    for field, title, hint, mapping in SCORE_QUESTIONS:
        lines.extend([f"### {title}", "", hint, "", mapping, ""])
    lines.extend(
        [
            "## 8. 总体结论",
            "",
            "- **PASS**：这张修复单基本可直接交给 L3",
            "- **REVIEW**：修复单有价值，但必须先由人修改",
            "- **FAIL**：不应把这张修复单交给 L3",
            "",
            "请填写：",
            "- `overall_business_result`",
            "- `reviewer_notes`",
            "- `decisive_evidence`（数组，可写段落编号如 P0006）",
            "- `major_defects`（数组）",
            "- `recommended_action`：`ACCEPT` / `CALIBRATE` / `REROUTE` / `REJECT`",
            "",
            "也可运行交互工具：`python 脚本/启动_R5D_半盲人工评审.py --case 01`",
        ]
    )
    return "\n".join(lines)


def build_reading_package(
    *,
    blind_label: str,
    case_id: str,
    module_id: str,
    resolution,
    supplementary: list[dict[str, str]],
    failure_item: dict[str, Any],
    attempt: dict[str, Any],
    parsed: dict[str, Any] | None,
    tech: dict[str, Any],
    score_rel: str,
) -> str:
    chapter_text = resolution.chapter_path.read_text(encoding="utf-8") if resolution.chapter_path else ""
    sup_paths = ", ".join(item["路径"] for item in supplementary) if supplementary else "本例无额外材料"
    tech_ok = tech.get("final_status") == "SUCCESS"
    retry = tech.get("retry_count", 0)
    parts = [
        f"# {blind_label}",
        "",
        "> 评审模式：**半盲独立评审（SEMI_BLIND）**。可见 case_id 与模块；不可见 A/B 类型与 expected。",
        "",
        "## 0. 本例信息",
        "",
        f"- **case_id**：{case_id}",
        f"- **评审代号**：{blind_label}",
        f"- **目标模块**：{module_id}",
        f"- **正文来源路径**：`{resolution.chapter_rel}`（案例目录内 `{resolution.case_dir.name}/`）",
        f"- **IR/前序/规则材料路径**：{sup_paths}",
        f"- **模型调用技术成功**：{'是' if tech_ok else '否'}（final_status={tech.get('final_status', '')}）",
        f"- **是否经过重试**：{'是' if retry else '否'}（retry_count={retry}，attempts={tech.get('attempts', 1)}）",
        "",
        "## 1. 完整正文",
        "",
        f"文件：`{resolution.chapter_rel}` | 字数：{resolution.char_count} | 段落数：{resolution.paragraph_count}",
        "",
        number_paragraphs(chapter_text),
        "",
        "## 2. 辅助材料",
        "",
    ]
    if supplementary:
        for item in supplementary:
            parts.extend(
                [
                    f"### {item['类型']}（`{item['路径']}`）",
                    "",
                    item["内容"],
                    "",
                ]
            )
    else:
        parts.append("本例无额外材料。")
        parts.append("")
    root_cause = (parsed or {}).get("root_cause") or (attempt.get("repair_form") or {}).get("规则依据", "")
    parts.extend(
        [
            "## 3. L1/L1.5 交给 L2 的问题",
            "",
            _format_failure_item_plain(failure_item),
            "",
            "## 4. L2 模型的诊断",
            "",
            _format_model_diagnosis(parsed, attempt),
            "",
            "## 5. 模型引用的证据",
            "",
            _format_evidence_list(
                parsed=parsed,
                repair_form=attempt.get("repair_form"),
                root_cause=str(root_cause),
            ),
            "",
            "## 6. 模型给出的修复单",
            "",
            _format_repair_form_section(attempt.get("repair_form")),
            "",
            "## 7. 通俗人工评分区",
            "",
            _format_scoring_section(score_rel),
        ]
    )
    return "\n".join(parts)


def _update_metadata_files(review_dir: Path, blind_order: list[dict[str, Any]], score_rows: list[dict[str, Any]]) -> None:
    order_path = review_dir / "盲评顺序.json"
    order_payload = load_json(order_path) if order_path.is_file() else {}
    order_payload.update(SEMI_BLIND_METADATA)
    order_payload["phase_1_name"] = "半盲独立评审"
    order_payload["phase_2_name"] = "对照复核"
    order_payload["note"] = (
        "历史文件名保留「盲评」字样，实际模式为 SEMI_BLIND。"
        "第一阶段仍隐藏 A/B 类型与 expected。"
    )
    order_payload["phase_1_order"] = blind_order
    order_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    order_path.write_text(json.dumps(order_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_payload = {
        "schema_version": "xcue.l2-human-review-summary/1.0",
        "phase": "R5D",
        "source_run_id": load_json(R5C_RUN / "summary.json").get("run_id"),
        "status": "AWAITING_HUMAN_REVIEW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **SEMI_BLIND_METADATA,
        "cases": score_rows,
        "statistics": None,
        "gate_result": None,
        "labels": {
            "L2_R5D_BUSINESS_PILOT": "AWAITING_HUMAN_REVIEW",
            "L2_REAL_MODEL_EFFECTIVENESS": "NOT_TESTED",
            "PRODUCTION_ELIGIBLE": False,
        },
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
                "评审模式：**SEMI_BLIND（半盲评）**",
                "",
                "当前状态：`AWAITING_HUMAN_REVIEW`",
                "",
                "## 如何开始",
                "",
                "请打开 [`开始评审.md`](开始评审.md)，按 01→12 顺序阅读 `半盲评阅读包/` 并填写评分。",
                "",
                "## 两阶段说明",
                "",
                "1. **半盲独立评审**：阅读包 + `{case_id}_盲评评分.json`",
                "2. **对照复核**：全部第一阶段评分不再是 NOT_REVIEWED 后，再打开 `案例评审表/对照复核/`",
                "",
                "第一阶段评分不得删除；第二阶段写入 `{case_id}_评分.json` 并记录变更原因。",
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
                "## 评审模式",
                "",
                "```json",
                json.dumps(SEMI_BLIND_METADATA, ensure_ascii=False, indent=2),
                "```",
                "",
                "- **第一阶段：半盲独立评审** — 阅读 `半盲评阅读包/`，填写 `{case_id}_盲评评分.json`",
                "- **第二阶段：对照复核** — 阅读 `案例评审表/对照复核/` 与 expected，更新 `{case_id}_评分.json`",
                "",
                "历史目录名「盲评」保留，文档内统一称 **SEMI_BLIND**，不宣称严格盲评。",
                "",
                "## 真源",
                "",
                f"- 试跑结果：`{R5C_RUN.relative_to(ROOT).as_posix()}`",
                f"- 正文定位：见 `正文位置清单.md`",
                "",
                "## 禁止事项",
                "",
                "- 不调用新的真实 API",
                "- 不修改 12 例正文、IR、expected",
                "- 不把 REVIEW 自动计为 PASS",
                "- 不让模型或脚本替人完成业务评分",
                "- 不得用 expected 自动覆盖人工评分",
                "",
                "## 第二阶段额外字段",
                "",
                "```json",
                json.dumps(
                    {
                        "phase_1_overall": "",
                        "phase_2_overall": "",
                        "rating_changed": False,
                        "change_reason": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
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
                "评审模式：**SEMI_BLIND**",
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
                "review_mode = SEMI_BLIND",
                "L2_R5D_BUSINESS_PILOT = AWAITING_HUMAN_REVIEW",
                "L2_REAL_MODEL_EFFECTIVENESS = NOT_TESTED",
                "PRODUCTION_ELIGIBLE = false",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_start_guide(review_dir: Path, blind_order: list[dict[str, Any]]) -> None:
    lines = [
        "# 开始评审",
        "",
        "评审模式：**半盲独立评审（SEMI_BLIND）**",
        "",
        "```text",
        "第一步：",
        "打开“半盲评阅读包/评审案例-01_半盲评阅读包.md”。",
        "",
        "第二步：",
        "从上到下阅读：",
        "正文 → 模型诊断 → 证据 → 修复动作。",
        "",
        "第三步：",
        "填写对应评分文件。",
        "拿不准就填 REVIEW，不要勉强填 PASS。",
        "",
        "第四步：",
        "完成案例01后再打开案例02。",
        "",
        "第五步：",
        "12例第一阶段全部完成前，不打开“对照复核”目录。",
        "```",
        "",
        "## 12 个阅读包与评分文件",
        "",
    ]
    for row in blind_order:
        label = row["blind_label"]
        num = label.replace("评审案例-", "")
        pkg = f"半盲评阅读包/{label}_半盲评阅读包.md"
        score = row["score_files"]["phase_1"]
        lines.append(f"- [{label}]({pkg}) → 评分：[{row['case_id']} 第一阶段]({score})")
    lines.extend(
        [
            "",
            "## 交互式填写（可选）",
            "",
            "```powershell",
            'python "脚本/启动_R5D_半盲人工评审.py" --case 01',
            'python "脚本/启动_R5D_半盲人工评审.py" --resume',
            'python "脚本/启动_R5D_半盲人工评审.py" --list',
            "```",
            "",
            "示例说明：[`评分示例说明.md`](评分示例说明.md)",
            "",
        ]
    )
    (review_dir / "开始评审.md").write_text("\n".join(lines), encoding="utf-8")


def _write_score_examples(review_dir: Path) -> None:
    (review_dir / "评分示例说明.md").write_text(
        "\n".join(
            [
                "# 评分示例说明（虚构短例）",
                "",
                "> 以下例子与 12 个真实 pilot 案例无关，不含 expected 信息。",
                "",
                "## ① 问题判断对不对（diagnosis_correct）",
                "",
                "- **PASS**：正文第 3 段角色突然 teleport，模型正确指出缺少移动过程。",
                "- **FAIL**：正文因果完整，模型仍判「结构断裂」。",
                "",
                "## ② 证据是否相关（evidence_relevant）",
                "",
                "- **PASS**：摘句「他不记得如何到达山顶」直接支持「缺少过渡」。",
                "- **FAIL**：摘句只写「天气很冷」，却被用来证明「动机不足」。",
                "",
                "## ③ 根因是否具体（root_cause_specific）",
                "",
                "- **PASS**：「角色得知危险后没有解释为何仍选择开门。」",
                "- **FAIL**：「人物动机不足。」",
                "",
                "## ④ 修复动作可执行（fix_actions_executable）",
                "",
                "- **PASS**：「在第 6 段开门前补一句：他确认妹妹仍在门后。」",
                "- **FAIL**：「增强人物动机。」",
                "",
                "## ⑤ 验收可检查（acceptance_criteria_testable）",
                "",
                "- **PASS**：「读者能说出角色为何从仓库到达山顶。」",
                "- **FAIL**：「文笔更精炼、更有吸引力。」",
                "",
                "## ⑥ 模块范围（forbidden_scope_respected）",
                "",
                "- **PASS**：文风模块只改句式，未改世界规则。",
                "- **FAIL**：文风模块要求删除「魔法规则」条目。",
                "",
                "## ⑦ 跨模块越权（cross_module_overreach）",
                "",
                "- **PASS**：市场模块只谈阅读收益，未重写人物核心目标。",
                "- **FAIL**：一致性模块把「文风重复」当硬冲突处理。",
                "",
                "## PASS / REVIEW / FAIL 差异",
                "",
                "- **PASS**：可直接交给 L3 执行。",
                "- **REVIEW**：方向对，但动作或验收需人工改一版。",
                "- **FAIL**：诊断或修复单不应进入 L3。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def prepare(review_dir: Path = R5D_DIR) -> dict[str, Any]:
    if not R5C_RUN.is_dir():
        raise FileNotFoundError(f"缺少 R5C 结果：{R5C_RUN}")
    manifest = load_json(MANIFEST_PATH)
    summary = load_json(R5C_RUN / "summary.json")
    per_case_tech = summary.get("technical", {}).get("per_case", {})

    pkg_dir = review_dir / "半盲评阅读包"
    score_dir = review_dir / "案例评审表"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    score_dir.mkdir(parents=True, exist_ok=True)

    cases = list(manifest.get("cases") or [])
    rng = random.Random(20260628)
    shuffled = cases[:]
    rng.shuffle(shuffled)

    chapter_rows: list[dict[str, Any]] = []
    blind_order: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    unresolved: list[str] = []

    for idx, entry in enumerate(shuffled, start=1):
        case_id = str(entry["case_id"])
        module_id = str(entry["target_module"])
        blind_label = f"评审案例-{idx:02d}"
        case_dir = (PILOT / str(entry["case_dir"])).resolve()
        project = load_json(case_dir / "project.json")
        resolution = resolve_chapter_path(case_dir, project)
        if resolution.error:
            unresolved.append(case_id)

        supplementary = collect_supplementary(case_dir)
        failure_item = load_json(case_dir / "failure_item.json")
        attempt = final_attempt(R5C_RUN / "cases" / case_id)
        parsed = extract_model_json(str(attempt.get("raw_response") or ""))
        tech = per_case_tech.get(case_id, {})
        score_rel = f"案例评审表/{case_id}_盲评评分.json"

        pkg_text = build_reading_package(
            blind_label=blind_label,
            case_id=case_id,
            module_id=module_id,
            resolution=resolution,
            supplementary=supplementary,
            failure_item=failure_item,
            attempt=attempt,
            parsed=parsed,
            tech=tech,
            score_rel=score_rel,
        )
        (pkg_dir / f"{blind_label}_半盲评阅读包.md").write_text(pkg_text, encoding="utf-8")

        phase1 = blank_phase1_score(case_id, module_id, blind_label)
        (score_dir / f"{case_id}_盲评评分.json").write_text(
            json.dumps(phase1, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        phase2 = blank_phase2_score(case_id, module_id, blind_label)
        (score_dir / f"{case_id}_评分.json").write_text(
            json.dumps(phase2, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        sup_desc = ", ".join(item["路径"] for item in supplementary) or "—"
        chapter_rows.append(
            {
                "blind_label": blind_label,
                "case_id": case_id,
                "module_id": module_id,
                "chapter_rel": resolution.chapter_rel,
                "chapter_abs": str(resolution.chapter_path) if resolution.chapter_path else None,
                "supplementary_paths": sup_desc,
                "char_count": resolution.char_count,
                "read_complete": resolution.read_complete,
                "error": resolution.error,
            }
        )
        blind_order.append(
            {
                "order": idx,
                "blind_label": blind_label,
                "case_id": case_id,
                "module_id": module_id,
                "reading_package": f"半盲评阅读包/{blind_label}_半盲评阅读包.md",
                "score_files": {
                    "phase_1": f"案例评审表/{case_id}_盲评评分.json",
                    "phase_2": f"案例评审表/{case_id}_评分.json",
                },
            }
        )
        score_rows.append(phase2)

    order_payload = {
        "schema_version": "xcue.l2-human-review-order/1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run_id": summary.get("run_id"),
        "review_dir": review_dir.name,
        **SEMI_BLIND_METADATA,
        "phase_1_name": "半盲独立评审",
        "phase_2_name": "对照复核",
        "phase_1_order": blind_order,
    }
    (review_dir / "盲评顺序.json").write_text(
        json.dumps(order_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    table_lines = [
        "# 正文位置清单",
        "",
        "| 评审代号 | case_id | 目标模块 | 正文文件 | IR/前序材料 | 字数 | 是否完整 |",
        "| ---- | ------- | ---- | ---- | ------- | -: | ---- |",
    ]
    for row in chapter_rows:
        chapter_rel = row["chapter_rel"] or "CASE_CHAPTER_NOT_RESOLVED"
        complete = "是" if row["read_complete"] else f"否（{row['error']}）"
        table_lines.append(
            f"| {row['blind_label']} | {row['case_id']} | {row['module_id']} | `{chapter_rel}` | {row['supplementary_paths']} | {row['char_count']} | {complete} |"
        )
    (review_dir / "正文位置清单.md").write_text("\n".join(table_lines), encoding="utf-8")
    (review_dir / "正文位置清单.json").write_text(
        json.dumps(
            {
                "schema_version": "xcue.l2-chapter-locator/1.0",
                **SEMI_BLIND_METADATA,
                "cases": chapter_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _update_metadata_files(review_dir, blind_order, score_rows)
    _write_start_guide(review_dir, blind_order)
    _write_score_examples(review_dir)

    return {
        "review_dir": str(review_dir),
        "case_count": len(cases),
        "unresolved": unresolved,
        "packages": [f"{row['blind_label']}_半盲评阅读包.md" for row in chapter_rows],
    }


def main() -> int:
    if not R5D_DIR.is_dir():
        R5D_DIR.mkdir(parents=True, exist_ok=True)
    info = prepare(R5D_DIR)
    print(f"PREPARED: {info['review_dir']}")
    print(f"packages: {info['case_count']}")
    if info["unresolved"]:
        for case_id in info["unresolved"]:
            print(f"CASE_CHAPTER_NOT_RESOLVED: {case_id}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
