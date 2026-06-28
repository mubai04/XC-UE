#!/usr/bin/env python3
"""L2-01 单章节真实修复：案例资格检查（L2-01-REAL-01）。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "00_工程总控" / "工程执行层" / "项目注册表.json"

EXCLUDED_PROJECT_IDS = frozenset({"TP-001"})
EXCLUDED_PATH_PARTS = (
    "tests/fixtures",
    "tests\\fixtures",
    "l2_real_api_pilot",
    "l2_real_api_pilot_v2",
    "l1_semantic_golden",
    "跨层契约迁移",
    "TP-001_CleanHarness",
)
EVAL_HINT_MARKERS = (
    "本章问题是",
    "L2-01",
    "因果不收束",
    "评测提示",
    "标准答案",
    "expected",
    "pilot",
    "L2P-",
    "L2V2-",
    "GS-00",
)
MIN_BODY_CHARS = 800


@dataclass
class 案例候选:
    project_id: str
    chapter_path: str
    chapter_sequence_index: int | None = None
    project_root: str = ""
    reasons: list[str] = field(default_factory=list)


@dataclass
class 资格结果:
    ok: bool
    stop_code: str = ""
    message: str = ""
    candidate: 案例候选 | None = None
    scanned: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _normalize(path: str | Path) -> str:
    return str(Path(path).as_posix())


def _读注册表() -> dict[str, Any]:
    if not REGISTRY.is_file():
        return {"projects": {}}
    return json.loads(REGISTRY.read_text(encoding="utf-8-sig"))


def _路径禁用(rel: str) -> list[str]:
    reasons: list[str] = []
    lower = rel.lower()
    for part in EXCLUDED_PATH_PARTS:
        if part.lower().replace("\\", "/") in lower:
            reasons.append(f"路径命中禁用前缀：{part}")
    return reasons


def _正文禁用(text: str) -> list[str]:
    reasons: list[str] = []
    for m in EVAL_HINT_MARKERS:
        if m in text:
            reasons.append(f"正文含评测提示：{m}")
    placeholder = ("在这里写", "测试正文", "最低建议", "跑 L1-01")
    hits = sum(1 for p in placeholder if p in text)
    if hits >= 2 and len(text.strip()) < MIN_BODY_CHARS:
        reasons.append("正文为占位/测试模板且字数不足")
    body = re.sub(r"^#.*$", "", text, flags=re.M).strip()
    if len(body) < MIN_BODY_CHARS:
        reasons.append(f"有效正文字数不足 {MIN_BODY_CHARS}")
    return reasons


def _扫描项目章节(project_id: str, project_root: Path) -> list[案例候选]:
    manifest = project_root / "project.json"
    if not manifest.is_file():
        return []
    meta = json.loads(manifest.read_text(encoding="utf-8-sig"))
    content_root = project_root / str(meta.get("content_root", "chapters"))
    if not content_root.is_dir():
        return []
    seq = meta.get("chapter_sequence") or []
    seq_map = {name: idx for idx, name in enumerate(seq)}
    out: list[案例候选] = []
    for fp in sorted(content_root.glob("*.md")):
        if fp.name.startswith("_"):
            continue
        rel = _normalize(fp.relative_to(ROOT))
        reasons = _路径禁用(rel)
        if project_id in EXCLUDED_PROJECT_IDS:
            reasons.append("project_id 为 TP-001 占位项目")
        try:
            text = fp.read_text(encoding="utf-8-sig")
        except OSError as exc:
            reasons.append(f"无法读取：{exc}")
            text = ""
        reasons.extend(_正文禁用(text))
        out.append(
            案例候选(
                project_id=project_id,
                chapter_path=rel,
                chapter_sequence_index=seq_map.get(fp.name),
                project_root=_normalize(project_root.relative_to(ROOT)),
                reasons=reasons,
            )
        )
    return out


def 扫描全部案例(root: Path | None = None) -> 资格结果:
    root = root or ROOT
    registry = _读注册表()
    projects = registry.get("projects") or {}
    scanned: list[dict[str, Any]] = []
    qualified: list[案例候选] = []

    if not projects:
        return 资格结果(
            ok=False,
            stop_code="REAL_L2_01_CASE_REQUIRED",
            message="项目注册表为空",
            missing=["非 TP-001 的真实小说项目", "已写入正文的章节"],
        )

    for project_id, spec in projects.items():
        rel_root = str(spec.get("project_root", "")).strip()
        if not rel_root:
            scanned.append({"project_id": project_id, "error": "缺少 project_root"})
            continue
        project_root = (root / rel_root).resolve()
        for cand in _扫描项目章节(project_id, project_root):
            scanned.append(asdict(cand))
            if not cand.reasons:
                qualified.append(cand)

    if not qualified:
        missing = [
            "当前注册表仅含 TP-001 或全部章节为占位/语料/fixture",
            "需要：真实小说 Project Harness（非 TP-001）+ 完整作者正文",
            "需要：正文不含评测提示，且有效字数≥800",
            "需要：章节可在 L1 自然产生 routeable 结构发现并由 L1.5 路由至 L2-01",
        ]
        return 资格结果(
            ok=False,
            stop_code="REAL_L2_01_CASE_REQUIRED",
            message="未找到合格真实章节",
            scanned=scanned,
            missing=missing,
        )

    return 资格结果(ok=True, candidate=qualified[0], scanned=scanned)


def 校验指定案例(project_id: str, chapter_path: str | Path, root: Path | None = None) -> 资格结果:
    root = root or ROOT
    registry = _读注册表()
    spec = (registry.get("projects") or {}).get(project_id) or {}
    rel_root = str(spec.get("project_root", "")).strip()
    chapter = Path(chapter_path)
    if not chapter.is_absolute():
        if rel_root and not str(chapter_path).startswith(rel_root):
            chapter = (root / rel_root / chapter).resolve()
        else:
            chapter = (root / chapter).resolve()
    rel = _normalize(chapter.relative_to(root))
    reasons = _路径禁用(rel)
    if project_id in EXCLUDED_PROJECT_IDS:
        reasons.append("project_id 为 TP-001 占位项目")
    if not chapter.is_file():
        reasons.append("章节文件不存在")
    else:
        try:
            reasons.extend(_正文禁用(chapter.read_text(encoding="utf-8-sig")))
        except OSError as exc:
            reasons.append(f"无法读取：{exc}")
    cand = 案例候选(project_id=project_id, chapter_path=rel, reasons=reasons)
    if reasons:
        return 资格结果(
            ok=False,
            stop_code="REAL_L2_01_CASE_REQUIRED",
            message="指定章节不符合真实案例条件",
            candidate=cand,
            scanned=[asdict(cand)],
            missing=reasons,
        )
    return 资格结果(ok=True, candidate=cand, scanned=[asdict(cand)])
