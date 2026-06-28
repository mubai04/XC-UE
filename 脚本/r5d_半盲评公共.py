"""R5D 半盲评：共享常量与材料解析（纯本地，不调用 API）。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
R5C_RUN = PILOT / "results" / "L2_R5C_全量技术复测_20260628"
R5D_DIR = PILOT / "results" / "R5D_人工业务评审_20260628"
MANIFEST_PATH = PILOT / "manifest.json"

SEMI_BLIND_METADATA: dict[str, Any] = {
    "review_mode": "SEMI_BLIND",
    "strict_blind": False,
    "known_information": [
        "目标L2模块",
        "评审案例代号",
        "case_id映射此前已被用户看到",
    ],
    "hidden_information_during_phase_1": [
        "A/B案例类型",
        "expected_issue_present",
        "acceptable_root_causes",
        "forbidden_diagnoses",
        "human_notes",
        "预设业务结论",
    ],
    "disclosure_note": "评审者已经看过案例与模块映射，因此本轮不宣称严格盲评。第一阶段仍隐藏案例类型和expected。",
}

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

PHASE2_EXTRA_FIELDS = (
    "phase_1_overall",
    "phase_2_overall",
    "rating_changed",
    "change_reason",
)

HIDDEN_PHASE1_TOKENS = (
    "expected_issue_present",
    "acceptable_root_causes",
    "forbidden_diagnoses",
    "human_notes",
    "A类",
    "B类",
    '"case_type": "A"',
    '"case_type": "B"',
)


@dataclass
class ChapterResolution:
    case_id: str
    case_dir: Path
    project_path: Path
    chapter_path: Path | None
    chapter_rel: str | None
    char_count: int
    paragraph_count: int
    read_complete: bool
    error: str | None = None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_model_json(raw_response: str) -> dict[str, Any] | None:
    if not raw_response:
        return None
    try:
        envelope = json.loads(raw_response)
        content = envelope["choices"][0]["message"]["content"]
        return json.loads(content)
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        return None


def final_attempt(case_result_dir: Path) -> dict[str, Any]:
    attempts = sorted(case_result_dir.glob("attempt_*.json"), key=lambda p: p.name)
    if not attempts:
        raise FileNotFoundError(f"缺少 attempt 记录：{case_result_dir}")
    return load_json(attempts[-1])


def _path_inside_case(case_dir: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(case_dir.resolve())
        return True
    except ValueError:
        return False


def resolve_chapter_path(case_dir: Path, project: dict[str, Any]) -> ChapterResolution:
    case_id = str(project.get("project_id") or case_dir.name)
    project_path = case_dir / "project.json"
    candidates: list[str] = []
    for key in ("default_chapter", "entrypoint"):
        value = project.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for rel in candidates:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)

    for rel in ordered:
        path = (case_dir / rel).resolve()
        if path.is_file() and _path_inside_case(case_dir, path):
            text = path.read_text(encoding="utf-8")
            return ChapterResolution(
                case_id=case_id,
                case_dir=case_dir,
                project_path=project_path,
                chapter_path=path,
                chapter_rel=rel.replace("\\", "/"),
                char_count=len(text),
                paragraph_count=_count_paragraphs(text),
                read_complete=True,
            )
    return ChapterResolution(
        case_id=case_id,
        case_dir=case_dir,
        project_path=project_path,
        chapter_path=None,
        chapter_rel=None,
        char_count=0,
        paragraph_count=0,
        read_complete=False,
        error="CASE_CHAPTER_NOT_RESOLVED",
    )


def _count_paragraphs(text: str) -> int:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    return len(blocks) if blocks else (1 if text.strip() else 0)


def number_paragraphs(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if not blocks:
        return text
    numbered: list[str] = []
    for idx, block in enumerate(blocks, start=1):
        numbered.append(f"[P{idx:04d}]\n\n{block}")
    return "\n\n".join(numbered)


def parse_repair_scope(rule_basis: str) -> dict[str, str]:
    text = rule_basis or ""
    scope = ""
    forbidden = ""
    m_scope = re.search(r"修改范围：([^|]+)", text)
    m_forbid = re.search(r"禁止：([^|]+)", text)
    if m_scope:
        scope = m_scope.group(1).strip()
    if m_forbid:
        forbidden = m_forbid.group(1).strip()
    return {"修改范围": scope, "禁止修改范围": forbidden}


def collect_supplementary(case_dir: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    ir_dir = case_dir / "IR"
    if ir_dir.is_dir():
        for path in sorted(ir_dir.glob("*.md")):
            rel = path.relative_to(case_dir).as_posix()
            items.append(
                {
                    "类型": "IR设定",
                    "路径": rel,
                    "内容": path.read_text(encoding="utf-8").strip(),
                }
            )
    prior = case_dir / "chapters" / "prior.md"
    if prior.is_file():
        items.append(
            {
                "类型": "前序章节",
                "路径": prior.relative_to(case_dir).as_posix(),
                "内容": prior.read_text(encoding="utf-8").strip(),
            }
        )
    rules = case_dir / "project_rules.json"
    if rules.is_file():
        items.append(
            {
                "类型": "项目规则",
                "路径": rules.relative_to(case_dir).as_posix(),
                "内容": rules.read_text(encoding="utf-8").strip(),
            }
        )
    return items


def blank_phase1_score(case_id: str, module_id: str, blind_label: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": case_id,
        "module_id": module_id,
        "blind_label": blind_label,
        "review_mode": "SEMI_BLIND",
        "review_phase": "PHASE_1_SEMI_BLIND",
    }
    for field in SCORE_FIELDS:
        row[field] = "NOT_REVIEWED"
    row["reviewer_notes"] = ""
    row["decisive_evidence"] = []
    row["major_defects"] = []
    row["recommended_action"] = "NOT_REVIEWED"
    return row


def blank_phase2_score(case_id: str, module_id: str, blind_label: str) -> dict[str, Any]:
    row = blank_phase1_score(case_id, module_id, blind_label)
    row["review_phase"] = "PHASE_2_PENDING"
    row["phase_1_overall"] = ""
    row["phase_2_overall"] = ""
    row["rating_changed"] = False
    row["change_reason"] = ""
    return row
