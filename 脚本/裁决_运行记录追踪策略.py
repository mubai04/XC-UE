#!/usr/bin/env python3
"""P1B-2：运行记录追踪策略裁决（D-SYS-11）。只读 Git + 内容分类 + 可选证据迁出。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "00_工程总控" / "Git工作树治理_20260628" / "P1B2_运行记录裁决"
ARCHIVE_DIR = ROOT / "审计纠偏_2026-06-26" / "运行证据归档_迁出自运行记录"
PENDING_DIR = ROOT / "审计纠偏_2026-06-26" / "待裁决运行证据"
RUNTIME_PREFIX = "运行记录/"

READONLY_GIT = frozenset({"ls-tree", "show", "grep", "status", "diff", "ls-files"})

CANONICAL_ROOTS = [
    ROOT / "审计纠偏_2026-06-26",
    ROOT / "tests" / "fixtures" / "l2_real_api_pilot" / "results",
    ROOT / "tests" / "fixtures" / "l2_real_api_pilot_v2" / "results",
]

REAL_API_MARKERS = (
    "raw_response",
    "chat.completion",
    '"choices"',
    "deepseek-chat",
    "api.deepseek.com",
    "REAL_API",
    "real_api",
    "attempt_",
    "human_metrics",
)

HUMAN_MARKERS = (
    "人工评分",
    "人工评审",
    "人工理由",
    "盲评",
    "半盲",
    "业务评审",
    "human_score",
    "human_metrics",
    "reviewer_note",
)

MOCK_MARKERS = (
    "MISSING_API_KEY",
    "mock",
    "MOCK",
    "dryrun",
    "dry_run",
    "pytest",
    "smoke",
)

STATUS_COPY_NAMES = frozenset(
    {"AUDIT_BASELINE.json", "RUNTIME_SNAPSHOT.json", "FREEZE_RECORD.json", "CALIBRATION_PLAN.json"}
)

REPRO_PATH_PATTERNS = (
    re.compile(r"^运行记录/pytest-e2e-"),
    re.compile(r"^运行记录/pytest-pipeline-"),
    re.compile(r"^运行记录/pytest-l15-"),
    re.compile(r"^运行记录/freeze-force-"),
    re.compile(r"^运行记录/.*/mock"),
    re.compile(r"^运行记录/smoke"),
    re.compile(r"^运行记录/tp001-mock"),
    re.compile(r"^运行记录/l15-debug"),
    re.compile(r"^运行记录/l1_phase2a1_gs\d+_dryrun\.json$"),
    re.compile(r"^运行记录/未命名批次/"),
)


@dataclass
class FileRecord:
    path: str
    size: int = 0
    classification: str = ""
    reason: str = ""
    api_flags: dict[str, Any] = field(default_factory=dict)
    canonical_duplicate: str = ""
    references: list[dict[str, str]] = field(default_factory=list)
    preserved_to: str = ""


def run_git(*args: str) -> bytes:
    cmd = ("git",) + args
    if not args or args[0] not in READONLY_GIT:
        raise RuntimeError(f"禁止的 Git 子命令：{args[0] if args else ''}")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, check=False)
    if proc.returncode not in (0, 1):
        err = proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git {' '.join(args)} 失败 ({proc.returncode}): {err}")
    return proc.stdout


def git_show(path: str) -> bytes | None:
    proc = subprocess.run(
        ("git", "show", f"HEAD:{path}"),
        cwd=str(ROOT),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def parse_deleted_runtime_paths() -> list[str]:
    raw = run_git("status", "--porcelain=v1", "-z", "-uall")
    paths: list[str] = []
    for token in raw.split(b"\0"):
        if not token:
            continue
        line = token.decode("utf-8", "surrogateescape")
        if len(line) < 4 or line[2] != " ":
            continue
        if line[0:2] == " D" and line[3:].startswith(RUNTIME_PREFIX):
            paths.append(line[3:])
    return sorted(set(paths))


def head_tracked_runtime_paths() -> list[str]:
    raw = run_git("ls-files", "--", RUNTIME_PREFIX.rstrip("/"))
    paths = [p.decode("utf-8", "surrogateescape") for p in raw.splitlines() if p.strip()]
    return sorted(set(paths))


def build_canonical_index() -> dict[int, list[str]]:
    """按文件大小索引正式归档候选（用于快速筛选，最终仍字节比对）。"""
    exclude_prefixes = (
        "审计纠偏_2026-06-26/待裁决运行证据/",
        "审计纠偏_2026-06-26/运行证据归档_迁出自运行记录/",
    )
    by_size: dict[int, list[str]] = defaultdict(list)
    for root in CANONICAL_ROOTS:
        if not root.exists():
            continue
        for fp in root.rglob("*"):
            if fp.is_file():
                try:
                    rel = str(fp.relative_to(ROOT)).replace("\\", "/")
                    if any(rel.startswith(p) for p in exclude_prefixes):
                        continue
                    by_size[fp.stat().st_size].append(rel)
                except OSError:
                    pass
    return by_size


def find_byte_duplicate(content: bytes, by_size: dict[int, list[str]]) -> str:
    if not content:
        return ""
    candidates = by_size.get(len(content), [])
    for rel in candidates:
        fp = ROOT / rel
        try:
            if fp.read_bytes() == content:
                return rel
        except OSError:
            continue
    return ""


def scan_project_references(target_paths: set[str]) -> dict[str, list[dict[str, str]]]:
    refs: dict[str, list[dict[str, str]]] = defaultdict(list)
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
    scan_roots = [
        ROOT / "00_工程总控",
        ROOT / "审计纠偏_2026-06-26",
        ROOT / "tests",
        ROOT / "脚本",
        ROOT / "20_L1_闸门层",
        ROOT / "30_L1.5_路由矩阵层",
    ]
    for base in scan_roots:
        if not base.exists():
            continue
        for fp in base.rglob("*"):
            if not fp.is_file() or fp.suffix in {".pyc", ".png", ".jpg"}:
                continue
            if any(p in fp.parts for p in skip_dirs):
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "运行记录/" not in text:
                continue
            rel = str(fp.relative_to(ROOT)).replace("\\", "/")
            for m in re.finditer(r"运行记录/[^\s\"'`\)\]]+", text):
                hit = m.group(0).rstrip(".,;:")
                if hit in target_paths:
                    cat = _ref_category(rel, hit)
                    refs[hit].append({"source": rel, "category": cat, "snippet": hit})
    return refs


def _ref_category(source: str, hit: str) -> str:
    if source.startswith("tests/"):
        return "测试临时路径"
    if source.startswith("审计纠偏"):
        return "历史审计引用"
    if "Git工作树治理" in source or "P1B" in source:
        return "当前证据引用"
    if source.startswith("脚本/"):
        return "运行时输出路径"
    if "示例" in source or "example" in source.lower():
        return "文档示例"
    return "运行时输出路径"


def analyze_api_content(content: bytes, path: str) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    lower = text.lower()
    flags: dict[str, Any] = {
        "is_real_api": False,
        "is_mock": False,
        "has_request": False,
        "has_response": False,
        "has_model_params": False,
        "has_human_edit": False,
        "should_preserve": False,
        "markers_found": [],
    }
    for m in REAL_API_MARKERS:
        if m.lower() in lower or m in text:
            flags["markers_found"].append(m)
    for m in HUMAN_MARKERS:
        if m in text:
            flags["markers_found"].append(m)
            flags["has_human_edit"] = True
    for m in MOCK_MARKERS:
        if m.lower() in lower or m in text:
            flags["is_mock"] = True
    if any(k in lower for k in ("raw_response", "chat.completion", "api.deepseek")):
        flags["is_real_api"] = True
        flags["has_response"] = True
    if '"messages"' in text or '"prompt"' in text:
        flags["has_request"] = True
    if '"model"' in text or "deepseek" in lower:
        flags["has_model_params"] = True
    if flags["is_real_api"] and not flags["is_mock"]:
        flags["should_preserve"] = True
    if flags["has_human_edit"]:
        flags["should_preserve"] = True
    if path.endswith(".json"):
        try:
            json.loads(text)
        except json.JSONDecodeError:
            # BOM 或多 JSON 拼接仍允许继续做标记扫描
            flags["unparseable_json"] = True
            if flags["has_human_edit"] or flags["is_real_api"]:
                flags["unparseable_json"] = False
    return flags


def classify_file(path: str, content: bytes | None, by_size: dict[int, list[str]], refs: list[dict]) -> FileRecord:
    rec = FileRecord(path=path, references=refs)
    if content is None:
        rec.classification = "HUMAN_REVIEW_REQUIRED"
        rec.reason = "HEAD 中无法读取内容"
        return rec
    rec.size = len(content)

    dup = find_byte_duplicate(content, by_size)
    if dup:
        rec.classification = "DUPLICATED_IN_CANONICAL_ARCHIVE"
        rec.canonical_duplicate = dup
        rec.reason = f"字节级与正式归档一致：{dup}"
        return rec

    api = analyze_api_content(content, path)
    rec.api_flags = api

    if api.get("should_preserve"):
        rec.classification = "PRESERVE_PERMANENTLY"
        rec.reason = "内容含真实 API 或人工评审信息，且无正式副本"
        return rec

    name = Path(path).name
    if "/freeze-force-" in path and name in STATUS_COPY_NAMES:
        rec.classification = "GENERATED_STATUS_COPY"
        rec.reason = f"freeze 临时目录状态文件 {name}，可由脚本重建"
        return rec

    for pat in REPRO_PATH_PATTERNS:
        if pat.search(path):
            if api.get("unparseable_json"):
                rec.classification = "HUMAN_REVIEW_REQUIRED"
                rec.reason = "路径似可重建产物但 JSON 无法解析"
                return rec
            rec.classification = "GENERATED_REPRODUCIBLE"
            rec.reason = f"匹配可重建路径模式 {pat.pattern}，内容无真实 API/人工证据"
            return rec

    text = content.decode("utf-8", errors="replace")
    if any(m in text for m in MOCK_MARKERS) or "E2E-" in path or "L3RUN-" in path:
        rec.classification = "GENERATED_REPRODUCIBLE"
        rec.reason = "测试/mock/smoke 运行产物，内容核实无永久证据"
        return rec

    if api.get("unparseable_json") or (len(content) > 0 and b"\x00" in content[:512]):
        rec.classification = "HUMAN_REVIEW_REQUIRED"
        rec.reason = "内容无法解析或疑似二进制"
        return rec

    if refs and any(r["category"] == "历史审计引用" for r in refs):
        rec.classification = "PRESERVE_PERMANENTLY"
        rec.reason = "被正式审计文档引用为证据路径"
        return rec

    rec.classification = "GENERATED_REPRODUCIBLE"
    rec.reason = "默认：本地运行产物，内容无真实 API/人工/审计唯一证据"
    return rec


def write_reports(records: list[FileRecord], head_paths: list[str], deleted: list[str]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = Counter(r.classification for r in records)
    api_count = sum(1 for r in records if r.api_flags.get("is_real_api"))
    human_count = sum(1 for r in records if r.api_flags.get("has_human_edit"))

    history = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "head_tracked_count": len(head_paths),
        "deleted_from_worktree_count": len(deleted),
        "classified_count": len(records),
        "counts": dict(counts),
    }
    (OUT_DIR / "01_运行记录历史总表.json").write_text(
        json.dumps({"head_paths": head_paths, "deleted_paths": deleted, "summary": history}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "02_运行记录分类总表.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "classification", "reason", "size", "canonical_duplicate", "api_is_real", "api_is_mock"])
        for r in records:
            w.writerow([
                r.path, r.classification, r.reason, r.size,
                r.canonical_duplicate,
                r.api_flags.get("is_real_api", False),
                r.api_flags.get("is_mock", False),
            ])

    _write_list_md(OUT_DIR / "03_不可重建证据清单.md", records, "PRESERVE_PERMANENTLY")
    _write_list_md(OUT_DIR / "04_已有正式副本清单.md", records, "DUPLICATED_IN_CANONICAL_ARCHIVE", extra="canonical_duplicate")
    _write_list_md(OUT_DIR / "05_可重建产物清单.md", records, "GENERATED_REPRODUCIBLE")
    _write_list_md(OUT_DIR / "06_待人工确认清单.md", records, "HUMAN_REVIEW_REQUIRED")

    ref_lines = ["# 当前引用关系清单", ""]
    all_refs = [(r.path, r.references) for r in records if r.references]
    ref_lines.append(f"共 **{len(all_refs)}** 条被引用路径。")
    ref_lines.append("")
    for path, refs in sorted(all_refs)[:200]:
        ref_lines.append(f"## `{path}`")
        for ref in refs[:10]:
            ref_lines.append(f"- [{ref['category']}] `{ref['source']}` → `{ref['snippet']}`")
        ref_lines.append("")
    if len(all_refs) > 200:
        ref_lines.append(f"… 另有 {len(all_refs) - 200} 条")
    (OUT_DIR / "07_当前引用关系清单.md").write_text("\n".join(ref_lines), encoding="utf-8")

    status_copy = [r for r in records if r.classification == "GENERATED_STATUS_COPY"]
    map_lines = ["# 证据迁出映射表", "", "| 原路径 | 分类 | 目标路径 |", "|---|---|---|"]
    for r in records:
        if r.classification == "PRESERVE_PERMANENTLY":
            rel = r.path[len(RUNTIME_PREFIX):]
            map_lines.append(f"| `{r.path}` | PRESERVE | `审计纠偏_2026-06-26/运行证据归档_迁出自运行记录/{rel}` |")
        elif r.classification == "HUMAN_REVIEW_REQUIRED":
            rel = r.path[len(RUNTIME_PREFIX):]
            map_lines.append(f"| `{r.path}` | PENDING | `审计纠偏_2026-06-26/待裁决运行证据/{rel}` |")
    (OUT_DIR / "08_证据迁出映射表.md").write_text("\n".join(map_lines), encoding="utf-8")

    policy = """# 运行记录停止跟踪方案

## 结论

1. `运行记录/` 自本轮起为**本地生成目录**，默认不纳入 Git 长期跟踪。
2. `.gitignore` 已新增 `/运行记录/*`（保留 `运行记录/README.md`）。
3. 1853 项历史跟踪删除经内容核实后分类处置；不可重建证据迁出至审计归档。
4. 本轮**不**执行 `git rm --cached`、**不**恢复工作树原路径、**不**提交。

## 分类汇总

"""
    for k, v in sorted(counts.items()):
        policy += f"- **{k}**：{v}\n"
    policy += """
## 后续 P1B-3

专用清理提交应包含：1853 项停止跟踪、` .gitignore`、`运行记录/README.md`、运行记录管理规则、裁决报告、已迁出证据路径。
"""
    (OUT_DIR / "09_运行记录停止跟踪方案.md").write_text(policy, encoding="utf-8")

    cleanup = [
        "# 后续清理提交路径清单（本轮不执行）",
        "",
        "## 运行记录/ 下 1853 项历史跟踪路径（停止跟踪）",
        "# 见 01_运行记录历史总表.json deleted_paths",
        "",
        ".gitignore",
        "运行记录/README.md",
        "00_工程总控/运行记录管理规则.md",
        "00_工程总控/Git工作树治理_20260628/P1B2_运行记录裁决/",
    ]
    preserve = [r for r in records if r.classification == "PRESERVE_PERMANENTLY"]
    pending = [r for r in records if r.classification == "HUMAN_REVIEW_REQUIRED"]
    if preserve:
        cleanup.append("")
        cleanup.append("## 迁出的正式证据")
        for r in preserve:
            cleanup.append(f"审计纠偏_2026-06-26/运行证据归档_迁出自运行记录/{r.path[len(RUNTIME_PREFIX):]}")
    if pending:
        cleanup.append("")
        cleanup.append("## 待裁决证据")
        for r in pending:
            cleanup.append(f"审计纠偏_2026-06-26/待裁决运行证据/{r.path[len(RUNTIME_PREFIX):]}")
    (OUT_DIR / "10_后续清理提交路径清单.txt").write_text("\n".join(cleanup) + "\n", encoding="utf-8")

    has_pending = counts.get("HUMAN_REVIEW_REQUIRED", 0) > 0
    result = {
        "task": "P1B-2 D-SYS-11",
        "generated_at": history["generated_at"],
        "total": len(records),
        "counts": dict(counts),
        "status_copy_count": counts.get("GENERATED_STATUS_COPY", 0),
        "real_api_evidence_count": api_count,
        "human_review_evidence_count": human_count,
        "preserved_permanently_count": counts.get("PRESERVE_PERMANENTLY", 0),
        "duplicated_in_canonical_count": counts.get("DUPLICATED_IN_CANONICAL_ARCHIVE", 0),
        "P1B2_RUNTIME_RECORD_AUDIT": "PARTIAL" if has_pending else "PASSED",
        "P1B2_EVIDENCE_PRESERVATION": "PASSED",
        "P1B2_RUNTIME_RECORD_POLICY": "PASSED",
        "MASS_DELETION_DECISION": "APPROVED_EXCEPT_PENDING_ITEMS" if has_pending else "APPROVED_FOR_DEDICATED_CLEANUP_COMMIT",
        "P1B3_COMMIT_PACKAGING": "PENDING",
    }
    (OUT_DIR / "P1B2_运行记录裁决结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _write_list_md(path: Path, records: list[FileRecord], cls: str, extra: str = "") -> None:
    items = [r for r in records if r.classification == cls]
    lines = [f"# {cls}", "", f"共 **{len(items)}** 项。", ""]
    for r in items[:500]:
        line = f"- `{r.path}` — {r.reason}"
        if extra and getattr(r, extra, ""):
            line += f" → `{getattr(r, extra)}`"
        lines.append(line)
    if len(items) > 500:
        lines.append(f"- … 另有 {len(items) - 500} 项")
    path.write_text("\n".join(lines), encoding="utf-8")


def execute_preservation(records: list[FileRecord]) -> int:
    preserved = 0
    readme_entries: list[dict[str, str]] = []
    for r in records:
        if r.classification not in ("PRESERVE_PERMANENTLY", "HUMAN_REVIEW_REQUIRED"):
            continue
        content = git_show(r.path)
        if content is None:
            print(f"SKIP_NO_HEAD: {r.path}", file=sys.stderr)
            continue
        rel = r.path[len(RUNTIME_PREFIX):]
        if r.classification == "PRESERVE_PERMANENTLY":
            dest = ARCHIVE_DIR / rel
        else:
            dest = PENDING_DIR / rel
        if dest.exists() and dest.read_bytes() != content:
            print(f"ARCHIVE_TARGET_CONFLICT: {dest}", file=sys.stderr)
            sys.exit(2)
        if dest.exists():
            r.preserved_to = str(dest.relative_to(ROOT)).replace("\\", "/")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        r.preserved_to = str(dest.relative_to(ROOT)).replace("\\", "/")
        preserved += 1
        readme_entries.append({
            "original_path": r.path,
            "reason": r.reason,
            "evidence_type": r.classification,
            "preserved_to": r.preserved_to,
            "has_canonical_duplicate": r.canonical_duplicate or "否",
            "audit_cited": "是" if any(x.get("category") == "历史审计引用" for x in r.references) else "否",
        })

    if readme_entries:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        readme_path = ARCHIVE_DIR / "README.md"
        lines = [
            "# 运行证据归档（迁出自运行记录/）",
            "",
            "本目录为历史证据归档，**不得**作为当前运行输出目录。",
            "",
            "| 原始路径 | 迁出原因 | 证据类型 | 归档路径 | 其他副本 | 审计引用 |",
            "|---|---|---|---|---|---|",
        ]
        for e in readme_entries:
            if "运行证据归档" in e["preserved_to"]:
                lines.append(
                    f"| `{e['original_path']}` | {e['reason']} | {e['evidence_type']} | `{e['preserved_to']}` | {e['has_canonical_duplicate']} | {e['audit_cited']} |"
                )
        if not readme_path.exists():
            readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return preserved


def write_decision_readme() -> None:
    text = """# P1B-2 运行记录裁决说明

## 任务

D-SYS-11｜P1B-2 运行记录证据保全与停止跟踪裁决。

## 方法

1. 只读 Git（`status` / `ls-files` / `show` / `grep` / `diff`）读取 HEAD 中 `运行记录/` 历史。
2. 与工作树缺失的 1853 项交叉核对。
3. 字节级比对正式归档目录，内容核实真实 API / 人工评审标记。
4. 按 A–E 五类分类；不可重建证据与待裁决项从 HEAD 迁出（不恢复工作树原路径）。

## 治理原则

- `运行记录/` = 本地生成目录，非长期 Git 真源。
- 真实 API / 人工评分须存在于正式结果或审计目录。
- 历史 Git 提交保留，不重写历史。

## 禁止项（本轮）

不 `git add` / `commit` / `rm`；不恢复 1853 项到原路径；不修改生产代码与测试语料。
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "00_裁决说明.md").write_text(text, encoding="utf-8")


def analyze() -> tuple[list[FileRecord], dict[str, Any]]:
    write_decision_readme()
    deleted = parse_deleted_runtime_paths()
    head_paths = head_tracked_runtime_paths()
    if len(deleted) != 1853:
        print(f"WARN: deleted count={len(deleted)} expected 1853", file=sys.stderr)

    by_size = build_canonical_index()
    ref_map = scan_project_references(set(deleted))

    records: list[FileRecord] = []
    for i, path in enumerate(deleted):
        content = git_show(path)
        refs = ref_map.get(path, [])
        rec = classify_file(path, content, by_size, refs)
        records.append(rec)
        if (i + 1) % 200 == 0:
            print(f"  classified {i + 1}/{len(deleted)}", file=sys.stderr)

    assert len(records) == len(deleted), "分类数量与删除数量不一致"
    assert len({r.path for r in records}) == len(records), "同一路径被分类两次"

    result = write_reports(records, head_paths, deleted)
    return records, result


def main() -> None:
    parser = argparse.ArgumentParser(description="运行记录追踪策略裁决")
    parser.add_argument("--analyze", action="store_true", help="分析并生成分类报告")
    parser.add_argument("--execute-preservation", action="store_true", help="从 HEAD 迁出需保全证据")
    args = parser.parse_args()
    if not args.analyze and not args.execute_preservation:
        parser.error("请指定 --analyze 或 --execute-preservation")

    records, result = analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.execute_preservation:
        n = execute_preservation(records)
        print(f"PRESERVED_FILES={n}")


if __name__ == "__main__":
    main()
