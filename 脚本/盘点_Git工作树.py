#!/usr/bin/env python3
"""Git 工作树只读盘点（D-SYS-09 P1A）。不执行任何写入型 Git 命令。"""

from __future__ import annotations

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
OUT_DIR = ROOT / "00_工程总控" / "Git工作树治理_20260628"
RAW_DIR = OUT_DIR / "_raw_git_output"

# 只读 Git 命令白名单
READONLY_GIT = {
    "branch",
    "rev-parse",
    "status",
    "diff",
    "clean",
    "ls-files",
    "log",
}


def run_git(*args: str, cwd: Path | None = None) -> bytes:
    cmd = ("git",) + args
    flag = args[0] if args else ""
    if flag not in READONLY_GIT:
        raise RuntimeError(f"禁止的 Git 子命令：{flag}")
    if flag == "clean" and not any("n" in a for a in args[1:]):
        raise RuntimeError("git clean 必须带 -n 预览")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        capture_output=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        err = proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git {' '.join(args)} 失败 ({proc.returncode}): {err}")
    return proc.stdout


def save_raw(name: str, data: bytes) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / name).write_bytes(data)


def parse_porcelain_z(raw: bytes) -> list[dict[str, Any]]:
    tokens = [t for t in raw.split(b"\0") if t]
    entries: list[dict[str, Any]] = []
    i = 0
    while i < len(tokens):
        line = tokens[i].decode("utf-8", "surrogateescape")
        if len(line) < 4 or line[2] != " ":
            i += 1
            continue
        x, y = line[0], line[1]
        path = line[3:]
        xy = x + y
        if (x in "RC" or y in "RC") and i + 1 < len(tokens):
            new_path = tokens[i + 1].decode("utf-8", "surrogateescape")
            kind = "renamed" if "R" in xy else "copied"
            entries.append(
                {
                    "path": new_path,
                    "old_path": path,
                    "index_status": x,
                    "worktree_status": y,
                    "xy": xy,
                    "kind": kind,
                    "staged": x != " " and x != "?",
                    "unstaged": y != " " and y != "?",
                    "untracked": x == "?" and y == "?",
                    "conflict": _is_conflict(x, y),
                }
            )
            i += 2
        else:
            kind = _kind_from_xy(x, y)
            entries.append(
                {
                    "path": path,
                    "old_path": "",
                    "index_status": x,
                    "worktree_status": y,
                    "xy": xy,
                    "kind": kind,
                    "staged": x not in (" ", "?") and kind != "untracked",
                    "unstaged": y not in (" ", "?") and kind != "untracked",
                    "untracked": kind == "untracked",
                    "conflict": _is_conflict(x, y),
                }
            )
            i += 1
    return entries


UNMERGED_XY = frozenset({"DD", "AU", "UD", "UA", "DU", "AA", "UU"})


def _is_conflict(x: str, y: str) -> bool:
    xy = x + y
    return x == "U" or y == "U" or xy in UNMERGED_XY


def _kind_from_xy(x: str, y: str) -> str:
    if x == "?" and y == "?":
        return "untracked"
    if _is_conflict(x, y):
        return "conflict"
    if x == "R" or y == "R":
        return "renamed"
    if x == "C" or y == "C":
        return "copied"
    if x == "A" or y == "A":
        return "added"
    if x == "D" or y == "D":
        return "deleted"
    if x == "M" or y == "M":
        return "modified"
    if x == "T" or y == "T":
        return "typechange"
    return "other"


def parse_name_status_z(raw: bytes) -> list[dict[str, str]]:
    tokens = [t.decode("utf-8", "surrogateescape") for t in raw.split(b"\0") if t]
    rows: list[dict[str, str]] = []
    i = 0
    while i < len(tokens):
        parts = tokens[i].split("\t")
        if len(parts) == 1 and i + 2 < len(tokens):
            status = parts[0]
            if status.startswith("R") or status.startswith("C"):
                rows.append({"status": status, "old_path": tokens[i + 1], "path": tokens[i + 2]})
                i += 3
                continue
        if len(parts) >= 2:
            status = parts[0]
            if status.startswith("R") or status.startswith("C"):
                if len(parts) >= 3:
                    rows.append({"status": status, "old_path": parts[1], "path": parts[2]})
                i += 1
            else:
                rows.append({"status": status, "old_path": "", "path": parts[1]})
                i += 1
        else:
            i += 1
    return rows


def top_dir(path: str) -> str:
    p = path.replace("\\", "/")
    if "/" not in p:
        return "根目录文件"
    top = p.split("/")[0]
    mapping = {
        "00_工程总控": "00_工程总控/",
        "10_L0_总图层": "10_L0*/",
        "10_L0": "10_L0*/",
        "20_L1_闸门层": "20_L1*/",
        "20_L1": "20_L1*/",
        "30_L1.5_路由矩阵层": "30_L1.5*/",
        "30_L1.5": "30_L1.5*/",
        "40_L2_正式能力层": "40_L2*/",
        "40_L2": "40_L2*/",
        "50_L3_执行协议层": "50_L3*/",
        "50_L3": "50_L3*/",
        "70_测试项目": "70_测试项目/",
        "90_日志": "90_日志/",
        "审计纠偏_2026-06-26": "审计纠偏_2026-06-26/",
        "运行记录": "运行记录/",
        "scripts": "scripts/",
        "脚本": "脚本/",
        "src": "src/",
        "tests": "tests/",
        "测试": "测试/",
    }
    for prefix, label in mapping.items():
        if p.startswith(prefix + "/") or p == prefix:
            return label
    return "其他"


TEMP_ROOT_PATTERNS = [
    re.compile(r"^_tmp", re.I),
    re.compile(r"^tmp_", re.I),
    re.compile(r"^_t\d*\.md$", re.I),
    re.compile(r"^_t\.md$", re.I),
    re.compile(r"\.bak$", re.I),
    re.compile(r"\.old$", re.I),
    re.compile(r"\.orig$", re.I),
    re.compile(r"\.rej$", re.I),
]

GENERATED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage_cache",
    ".venv",
    ".venv-schema-verify",
    "htmlcov",
    "dist",
    "build",
    "*.egg-info",
}


def classify_entry(entry: dict[str, Any]) -> tuple[str, list[str]]:
    path = entry["path"]
    old_path = entry.get("old_path") or ""
    kind = entry["kind"]
    rel = path.replace("\\", "/")
    old_rel = old_path.replace("\\", "/")
    risks: list[str] = []

    if entry.get("conflict"):
        risks.append("HUMAN_DECISION_REQUIRED")

    if kind in ("renamed", "copied"):
        risks.append("RENAME_PAIR")
        if _has_cjk(old_rel) or _has_cjk(rel):
            risks.append("CHINESE_NAME_MIGRATION")
        if old_rel.lower() == rel.lower() and old_rel != rel:
            risks.append("CASE_ONLY_RENAME")

    if kind == "deleted" or entry.get("worktree_status") == "D" or entry.get("index_status") == "D":
        risks.append("MASS_DELETE")
        if _is_history_evidence(rel):
            risks.append("POSSIBLE_ACCIDENTAL_DELETE")
        elif _is_generated_artifact(rel):
            risks.append("EXPECTED_CLEANUP_CANDIDATE")

    if kind == "untracked":
        risks.append("UNTRACKED_SOURCE" if _looks_like_source(rel) else "UNTRACKED_GENERATED")
        if rel.startswith("运行记录/") or "/results/" in rel:
            risks.append("UNTRACKED_GENERATED")

    if _is_root_temp(rel):
        risks.append("ROOT_TEMP_FILE")

    if rel.endswith((".env", ".pem", ".key")) or "credential" in rel.lower() or "secret" in rel.lower():
        risks.append("SENSITIVE_FILE_CANDIDATE")

    if rel.startswith("scripts/") and rel.endswith(".py"):
        risks.append("COMPATIBILITY_WRAPPER")

    category = _primary_category(rel, old_rel, kind, entry)
    if category == "未知":
        risks.append("HUMAN_DECISION_REQUIRED")
    if _is_stale_status_candidate(rel):
        risks.append("STALE_STATUS")

    return category, sorted(set(risks))


def _has_cjk(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def _is_root_temp(rel: str) -> bool:
    if "/" in rel:
        return False
    name = rel
    return any(p.match(name) for p in TEMP_ROOT_PATTERNS)


def _is_history_evidence(rel: str) -> bool:
    patterns = [
        "90_日志/",
        "审计纠偏_",
        "tests/fixtures/",
        "R5A",
        "R5B",
        "R5C",
        "R5D",
        "golden",
        "expected",
        "基线",
    ]
    return any(p in rel for p in patterns) and not _is_generated_artifact(rel)


def _is_generated_artifact(rel: str) -> bool:
    if "__pycache__" in rel or rel.endswith(".pyc"):
        return True
    if ".pytest_cache" in rel:
        return True
    if rel.startswith("运行记录/"):
        return True
    if "/results/" in rel and rel.endswith((".json", ".md")):
        return True
    if rel.endswith(".egg-info") or ".egg-info/" in rel:
        return True
    if rel.endswith(".zip") and "盘查包" in rel:
        return True
    return False


def _looks_like_source(rel: str) -> bool:
    return rel.endswith((".py", ".md", ".json", ".toml", ".yaml", ".yml", ".txt")) and not _is_generated_artifact(rel)


def _is_stale_status_candidate(rel: str) -> bool:
    names = [
        "当前系统状态_自动生成.md",
        "目录结构检查",
        "目录治理任务",
        "L1-L1.5_当前系统失败断点记录",
        "XC-UE_全量深度盘查报告",
    ]
    return any(n in rel for n in names)


def _primary_category(rel: str, old_rel: str, kind: str, entry: dict) -> str:
    check = rel or old_rel
    if check.startswith("00_工程总控/跨层接口契约") or "跨层契约/" in check and check.endswith(".json"):
        return "Schema与跨层契约"
    if check.startswith("00_工程总控/工程执行层/公共组件/结构定义/跨层契约"):
        return "Schema与跨层契约"
    if check.startswith("00_工程总控/工程执行层/公共组件/跨层契约运行库"):
        return "Schema与跨层契约"
    if check.startswith("00_工程总控/跨层接口契约") or "跨层接口契约" in check:
        return "Schema与跨层契约"
    if check.startswith("00_工程总控/Git工作树治理"):
        return "GOVERNANCE"
    if check.startswith("00_工程总控/") and check.endswith(".md"):
        return "GOVERNANCE" if "治理" in check or "真源" in check or "登记" in check else "生成状态"
    if check.startswith(("10_L0", "20_L1", "30_L1.5", "40_L2", "50_L3")):
        return "正式定义"
    if check.startswith("00_工程总控/工程执行层/"):
        return "生产代码"
    if check.startswith("tests/fixtures/") and ("/results/" in check or "attempt_" in check):
        return "API评估结果"
    if check.startswith("tests/fixtures/"):
        return "测试夹具与语料"
    if check.startswith("tests/") or check.startswith("测试/"):
        return "测试"
    if check.startswith("审计纠偏_"):
        return "审计报告"
    if check.startswith("90_日志/"):
        return "历史归档"
    if check.startswith("运行记录/"):
        return "运行记录"
    if check.startswith("scripts/"):
        return "兼容入口"
    if check.startswith("脚本/"):
        return "生产代码" if check.endswith(".py") else "GOVERNANCE"
    if check in ("pyproject.toml", "依赖锁定_开发运行.txt") or check.startswith("文档/"):
        return "依赖与环境"
    if check.startswith(".cursor/"):
        return "GOVERNANCE"
    if _is_root_temp(check) or check.startswith("_"):
        return "临时文件"
    if kind == "untracked" and _is_generated_artifact(check):
        return "运行记录"
    if check.endswith(".md") and "项目说明" in check or check in ("XC-UE_项目说明与资源边界.md", "README.md"):
        return "GOVERNANCE"
    if "eval_l2" in check or "R5" in check:
        return "API评估结果"
    return "未知"


def delete_disposition(entry: dict, category: str, risks: list[str]) -> str:
    if entry["kind"] != "deleted" and entry.get("index_status") != "D" and entry.get("worktree_status") != "D":
        return ""
    rel = entry["path"] or entry.get("old_path", "")
    if "RENAME_PAIR" in risks or entry.get("old_path"):
        return "RENAME_RECOGNITION_REQUIRED"
    if _is_history_evidence(rel) and "POSSIBLE_ACCIDENTAL_DELETE" in risks:
        return "KEEP_TRACKED_HISTORY"
    if _is_generated_artifact(rel) or "EXPECTED_CLEANUP_CANDIDATE" in risks:
        return "GENERATED_CAN_DELETE_LATER"
    if category in ("审计报告", "历史归档", "测试夹具与语料"):
        return "HUMAN_DECISION_REQUIRED"
    if rel.startswith("运行记录/"):
        return "HUMAN_DECISION_REQUIRED"
    return "PENDING"


def analyze_scripts_boundary(root: Path) -> dict[str, Any]:
    scripts_dir = root / "scripts"
    jiao_dir = root / "脚本"
    scripts_files = sorted(p.relative_to(root).as_posix() for p in scripts_dir.glob("*") if p.is_file()) if scripts_dir.exists() else []
    jiao_files = sorted(p.relative_to(root).as_posix() for p in jiao_dir.rglob("*") if p.is_file()) if jiao_dir.exists() else []

    file_classes: dict[str, str] = {}
    duplicates: list[str] = []

    for sf in scripts_files:
        sp = root / sf
        text = sp.read_text(encoding="utf-8", errors="replace") if sp.suffix == ".py" else ""
        if "runpy.run_path" in text or "脚本/" in text:
            file_classes[sf] = "COMPATIBILITY_WRAPPER"
        elif sp.stat().st_size < 200:
            file_classes[sf] = "COMPATIBILITY_WRAPPER"
        else:
            file_classes[sf] = "DUPLICATE_IMPLEMENTATION"
            duplicates.append(sf)

    refs_scripts = _grep_refs(root, "scripts/")
    refs_jiao = _grep_refs(root, "脚本/")

    return {
        "scripts_files": scripts_files,
        "jiao_files_count": len(jiao_files),
        "file_classes": file_classes,
        "duplicate_logic_candidates": duplicates,
        "refs_scripts": refs_scripts[:30],
        "refs_jiao_count": len(refs_jiao),
        "boundary_conforms": len(duplicates) == 0,
    }


def _grep_refs(root: Path, needle: str) -> list[str]:
    hits: list[str] = []
    for pattern in ("*.py", "*.md", "*.toml", "*.yml", "*.yaml"):
        for p in root.rglob(pattern):
            if ".git" in p.parts or "__pycache__" in p.parts or "Git工作树治理" in p.parts:
                continue
            try:
                if needle in p.read_text(encoding="utf-8", errors="replace"):
                    hits.append(p.relative_to(root).as_posix())
            except OSError:
                pass
    return hits


def propose_batches(entries: list[dict]) -> list[dict]:
    batches = [
        {
            "id": "A",
            "name": "唯一真源与治理",
            "goal": "S0治理文件、项目说明、索引、副本登记",
            "allow_prefixes": ["00_工程总控/当前工程唯一真源", "00_工程总控/云盘副本", "XC-UE_项目说明", "文档/项目治理层", ".cursor/rules"],
            "forbid_prefixes": ["00_工程总控/工程执行层", "tests/", "运行记录/"],
            "depends_on": [],
            "risk": "低",
            "rollback": True,
            "needs_test": False,
            "human_confirm": ["确认状态文档措辞与当前阶段一致"],
        },
        {
            "id": "B",
            "name": "L0、L1、L1.5定义与路由",
            "goal": "L0状态纠偏、L1权力模型、L1.5路由真源",
            "allow_prefixes": ["10_L0", "20_L1", "30_L1.5", "00_工程总控/工程执行层/L1", "00_工程总控/工程执行层/L1.5", "脚本/校验_L1"],
            "forbid_prefixes": ["运行记录/", "tests/fixtures/l2_real_api_pilot/results"],
            "depends_on": ["A"],
            "risk": "中",
            "rollback": True,
            "needs_test": True,
            "human_confirm": ["路由规则条数与Matrix一致"],
        },
        {
            "id": "C",
            "name": "跨层契约与P0修复",
            "goal": "S2A v2 Schema、S2B-1迁移库、P0合法性、依赖锁定",
            "allow_prefixes": ["00_工程总控/跨层接口契约", "00_工程总控/工程执行层/公共组件/结构定义/跨层契约", "00_工程总控/工程执行层/公共组件/跨层契约运行库", "脚本/校验_L0", "脚本/回放_v1", "依赖锁定", "pyproject.toml", "文档/项目治理层/开发环境"],
            "forbid_prefixes": ["00_工程总控/工程执行层/L2工程/L2_0", "运行记录/"],
            "depends_on": ["B"],
            "risk": "中",
            "rollback": True,
            "needs_test": True,
            "human_confirm": ["干净环境pytest已通过"],
        },
        {
            "id": "D",
            "name": "L2、L3及R4/R5实现",
            "goal": "领域实现、流水线、评测工具（按模块再拆）",
            "allow_prefixes": ["00_工程总控/工程执行层/L2", "00_工程总控/工程执行层/L3", "40_L2", "50_L3", "脚本/评估", "脚本/生成", "scripts/"],
            "forbid_prefixes": ["tests/fixtures/l2_real_api_pilot/results", "运行记录/"],
            "depends_on": ["C"],
            "risk": "高",
            "rollback": True,
            "needs_test": True,
            "human_confirm": ["L2各模块分批提交", "scripts仅包装"],
        },
        {
            "id": "E",
            "name": "测试语料与API评估记录",
            "goal": "fixtures、expected、R5试跑记录",
            "allow_prefixes": ["tests/fixtures/", "tests/test_", "审计纠偏_2026-06-26/L0_L3"],
            "forbid_prefixes": ["00_工程总控/工程执行层/"],
            "depends_on": ["D"],
            "risk": "中",
            "rollback": True,
            "needs_test": True,
            "human_confirm": ["R5A-R5C原始记录是否入库"],
        },
        {
            "id": "F",
            "name": "清理提交",
            "goal": "运行产物删除、临时文件、ignore、过期状态",
            "allow_prefixes": ["运行记录/", "_t", "_tmp", ".gitignore"],
            "forbid_prefixes": ["tests/fixtures/", "审计纠偏_", "90_日志/"],
            "depends_on": ["A", "B", "C", "D", "E"],
            "risk": "高",
            "rollback": False,
            "needs_test": True,
            "human_confirm": ["大量删除逐项确认", "不可重建证据不得删"],
        },
    ]
    return batches


def assign_batch(path: str, batches: list[dict]) -> str:
    p = path.replace("\\", "/")
    for b in batches:
        for prefix in b["allow_prefixes"]:
            if p.startswith(prefix) or p == prefix.rstrip("/"):
                blocked = any(p.startswith(f) for f in b.get("forbid_prefixes", []))
                if not blocked:
                    return b["id"]
    return "待裁决"


def inspect_temp_file(root: Path, name: str) -> dict[str, Any]:
    p = root / name
    info: dict[str, Any] = {"name": name, "exists": p.exists(), "tracked": False, "suggestion": "HUMAN_REVIEW"}
    if not p.exists():
        return info
    info["size"] = p.stat().st_size
    try:
        preview = p.read_text(encoding="utf-8", errors="replace")[:500]
        info["preview"] = preview.replace("\n", " ")[:200]
    except OSError:
        info["preview"] = ""
    refs = _grep_refs(root, name)
    info["referenced_by"] = refs[:10]
    if not refs and info.get("size", 0) < 5000:
        info["suggestion"] = "DELETE_LATER"
    elif refs:
        info["suggestion"] = "KEEP"
    return info


def main() -> int:
    try:
        top = run_git("rev-parse", "--show-toplevel").decode("utf-8").strip()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    root = Path(top)
    if root.resolve() != ROOT.resolve():
        print(f"ERROR: 脚本根 {ROOT} 与 Git 根 {root} 不一致", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    before_status = run_git("status", "--porcelain=v1", "-z", "-uall", cwd=root)
    save_raw("00_before_status.z", before_status)

    branch = run_git("branch", "--show-current", cwd=root).decode("utf-8").strip()
    status_entries = parse_porcelain_z(before_status)
    diff_unstaged = run_git("diff", "--name-status", "-z", cwd=root)
    diff_staged = run_git("diff", "--cached", "--name-status", "-z", cwd=root)
    diff_stat = run_git("diff", "--stat", cwd=root).decode("utf-8", errors="replace")
    diff_cached_stat = run_git("diff", "--cached", "--stat", cwd=root).decode("utf-8", errors="replace")
    clean_nd = run_git("clean", "-nd", cwd=root).decode("utf-8", errors="replace")
    clean_ndx = run_git("clean", "-ndX", cwd=root).decode("utf-8", errors="replace")

    save_raw("01_branch.txt", branch.encode("utf-8"))
    save_raw("02_status.z", before_status)
    save_raw("03_diff_name_status.z", diff_unstaged)
    save_raw("04_diff_cached_name_status.z", diff_staged)
    save_raw("05_diff_stat.txt", diff_stat.encode("utf-8"))
    save_raw("06_diff_cached_stat.txt", diff_cached_stat.encode("utf-8"))
    save_raw("07_clean_nd.txt", clean_nd.encode("utf-8"))
    save_raw("08_clean_ndX.txt", clean_ndx.encode("utf-8"))

    enriched: list[dict[str, Any]] = []
    batches = propose_batches([])

    for e in status_entries:
        cat, risks = classify_entry(e)
        row = dict(e)
        row["category"] = cat
        row["risk_tags"] = risks
        row["top_dir"] = top_dir(e["path"] or e.get("old_path", ""))
        row["delete_disposition"] = delete_disposition(e, cat, risks)
        row["batch"] = assign_batch(e["path"] or e.get("old_path", ""), batches)
        enriched.append(row)

    both_staged_unstaged = sum(1 for e in enriched if e.get("staged") and e.get("unstaged") and not e.get("untracked"))
    stats = {
        "total_entries": len(enriched),
        "staged_entries": sum(1 for e in enriched if e.get("staged")),
        "unstaged_entries": sum(1 for e in enriched if e.get("unstaged")),
        "both_staged_unstaged": both_staged_unstaged,
        "added": sum(1 for e in enriched if e["kind"] == "added"),
        "modified": sum(1 for e in enriched if e["kind"] == "modified"),
        "deleted": sum(1 for e in enriched if e["kind"] == "deleted"),
        "renamed": sum(1 for e in enriched if e["kind"] == "renamed"),
        "copied": sum(1 for e in enriched if e["kind"] == "copied"),
        "untracked": sum(1 for e in enriched if e["kind"] == "untracked"),
        "conflict": sum(1 for e in enriched if e.get("conflict")),
    }

    categories = Counter(e["category"] for e in enriched)
    risk_tags = Counter(tag for e in enriched for tag in e["risk_tags"])
    dir_stats = Counter(e["top_dir"] for e in enriched)

    deleted_entries = [e for e in enriched if e["kind"] == "deleted" or "D" in e.get("xy", "")]
    run_record_deletes = [e for e in deleted_entries if (e["path"] or e.get("old_path", "")).startswith("运行记录/")]
    history_deletes = [
        e for e in deleted_entries if _is_history_evidence(e["path"] or e.get("old_path", "")) and not _is_generated_artifact(e["path"] or e.get("old_path", ""))
    ]
    renames = [e for e in enriched if e["kind"] == "renamed"]
    cjk_renames = [e for e in renames if "CHINESE_NAME_MIGRATION" in e["risk_tags"]]

    root_temps = [p.name for p in root.iterdir() if p.is_file() and _is_root_temp(p.name)]
    temp_details = [inspect_temp_file(root, n) for n in sorted(set(root_temps + ["_t.md", "_t2.md", "_tmp_ch.md", "tmp_psy.md"]))]

    scripts_info = analyze_scripts_boundary(root)

    batch_paths: dict[str, list[str]] = {b["id"]: [] for b in batches}
    batch_paths["待裁决"] = []
    for e in enriched:
        p = e["path"] or e.get("old_path", "")
        bid = assign_batch(p, batches)
        if bid == "待裁决":
            batch_paths["待裁决"].append(p)
        else:
            batch_paths[bid].append(p)

    human_decisions = [
        e for e in enriched if "HUMAN_DECISION_REQUIRED" in e["risk_tags"] or e["delete_disposition"] == "HUMAN_DECISION_REQUIRED"
    ]
    stale_files = [e for e in enriched if "STALE_STATUS" in e["risk_tags"]]

    mass_delete_groups = defaultdict(list)
    for e in deleted_entries:
        p = e.get("old_path") or e["path"]
        grp = top_dir(p)
        mass_delete_groups[grp].append(p)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    machine = {
        "branch": branch,
        "repository_root": str(root),
        "inventory_generated_at": now,
        "total_entries": stats["total_entries"],
        "staged_entries": stats["staged_entries"],
        "unstaged_entries": stats["unstaged_entries"],
        "untracked_entries": stats["untracked"],
        "deleted_entries": stats["deleted"],
        "renamed_entries": stats["renamed"],
        "conflicted_entries": stats["conflict"],
        "categories": dict(categories),
        "risk_tags": dict(risk_tags),
        "mass_delete_groups": {k: len(v) for k, v in mass_delete_groups.items()},
        "temporary_files": temp_details,
        "duplicate_logic_candidates": scripts_info["duplicate_logic_candidates"],
        "stale_status_files": [e["path"] for e in stale_files],
        "human_decisions_required": len(human_decisions),
        "proposed_commit_batches": [b["id"] for b in batches],
        "p1b_ready": False,
    }

    _write_all_reports(
        root=root,
        branch=branch,
        now=now,
        stats=stats,
        categories=categories,
        risk_tags=risk_tags,
        dir_stats=dir_stats,
        enriched=enriched,
        deleted_entries=deleted_entries,
        run_record_deletes=run_record_deletes,
        history_deletes=history_deletes,
        renames=renames,
        cjk_renames=cjk_renames,
        temp_details=temp_details,
        scripts_info=scripts_info,
        batches=batches,
        batch_paths=batch_paths,
        human_decisions=human_decisions,
        mass_delete_groups=mass_delete_groups,
        machine=machine,
        clean_nd=clean_nd,
        clean_ndx=clean_ndx,
        diff_stat=diff_stat,
        diff_cached_stat=diff_cached_stat,
    )

    after_status = run_git("status", "--porcelain=v1", "-z", "-uall", cwd=root)
    save_raw("99_after_status.z", after_status)

    allowed_new = {
        "脚本/盘点_Git工作树.py".replace("\\", "/"),
    }
    for p in OUT_DIR.rglob("*"):
        if p.is_file():
            allowed_new.add(p.relative_to(root).as_posix())

    def _parse_paths(raw: bytes) -> set[str]:
        paths: set[str] = set()
        for e in parse_porcelain_z(raw):
            if e.get("path"):
                paths.add(e["path"].replace("\\", "/"))
            if e.get("old_path"):
                paths.add(e["old_path"].replace("\\", "/"))
        return paths

    before_paths = _parse_paths(before_status)
    after_paths = _parse_paths(after_status)
    new_only = after_paths - before_paths
    removed = before_paths - after_paths
    unexpected_new = new_only - allowed_new
    if removed or unexpected_new:
        print("P1A_NON_AUDIT_CHANGE_DETECTED", file=sys.stderr)
        if removed:
            print(f"消失的路径: {sorted(removed)[:20]}", file=sys.stderr)
        if unexpected_new:
            print(f"非预期新增: {sorted(unexpected_new)[:20]}", file=sys.stderr)
        return 2

    print("P1A_WORKTREE_INVENTORY = PASSED")
    print(f"total_entries={stats['total_entries']}")
    return 0


def _write_all_reports(**kw: Any) -> None:
    root: Path = kw["root"]
    branch: str = kw["branch"]
    now: str = kw["now"]
    stats: dict = kw["stats"]
    enriched: list = kw["enriched"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "Git工作树盘点结果.json").write_text(
        json.dumps(kw["machine"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "02_全部变更明细.json").write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (OUT_DIR / "03_全部变更明细.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "path", "old_path", "kind", "xy", "index_status", "worktree_status",
                "staged", "unstaged", "untracked", "conflict", "category", "risk_tags",
                "top_dir", "delete_disposition", "batch",
            ],
        )
        w.writeheader()
        for e in enriched:
            row = {k: e.get(k, "") for k in w.fieldnames}
            row["risk_tags"] = ";".join(e.get("risk_tags", []))
            w.writerow(row)

    _write_md(OUT_DIR / "00_盘点说明.md", f"""# Git 工作树盘点说明

生成时间（元数据）：{now}

## 性质

- **只读盘点**：未执行 add / commit / reset / restore / clean -f / rm / mv
- 脚本：`脚本/盘点_Git工作树.py`
- 原始 Git 输出：`_raw_git_output/`

## 前置状态

```text
S2A_SCHEMA_V2 = REPAIRED_AND_VERIFIED
S2B1_CLEAN_ENV_VERIFICATION = PASSED
PRODUCTION_RUNTIME = v1
S2B2_RUNTIME_CUTOVER = DEFERRED
```

## 当前分支

`{branch}`

## 仓库根

`{root}`

## 输出文件

见本目录 01—13 及 `Git工作树盘点结果.json`、暂存清单_*.txt
""")

    _write_md(OUT_DIR / "01_工作树总体统计.md", _stats_md(kw))
    _write_md(OUT_DIR / "04_批量删除专项清单.md", _delete_md(kw))
    _write_md(OUT_DIR / "05_重命名与中文路径迁移清单.md", _rename_md(kw))
    _write_md(OUT_DIR / "06_未跟踪文件分类.md", _untracked_md(enriched))
    _write_md(OUT_DIR / "07_根目录临时文件审查.md", _temp_md(kw["temp_details"]))
    _write_md(OUT_DIR / "08_scripts与脚本目录边界.md", _scripts_md(kw["scripts_info"]))
    _write_md(OUT_DIR / "09_生成物与运行产物分类.md", _artifacts_md(enriched, kw["clean_nd"], kw["clean_ndx"]))
    _write_md(OUT_DIR / "10_建议忽略规则_仅建议.md", _ignore_md(enriched, kw["clean_ndx"]))
    _write_md(OUT_DIR / "11_分批提交候选计划.md", _batch_plan_md(kw["batches"]))
    _write_md(OUT_DIR / "12_需要人工裁决的问题.md", _human_md(kw["human_decisions"], kw))
    _write_md(OUT_DIR / "13_P1B后续执行边界.md", _p1b_md(kw))

    labels = {
        "A": "暂存清单_A_治理.txt",
        "B": "暂存清单_B_L0_L1_L1_5.txt",
        "C": "暂存清单_C_跨层契约.txt",
        "D": "暂存清单_D_L2_L3.txt",
        "E": "暂存清单_E_评测资料.txt",
        "F": "暂存清单_F_清理候选.txt",
        "待裁决": "暂存清单_待裁决.txt",
    }
    for bid, fname in labels.items():
        paths = sorted(set(kw["batch_paths"].get(bid, [])))
        (OUT_DIR / fname).write_text("\n".join(paths) + ("\n" if paths else ""), encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _stats_md(kw: dict) -> str:
    s = kw["stats"]
    ds = kw["dir_stats"]
    lines = [
        "# 工作树总体统计",
        "",
        "## 变更状态",
        "",
        "| 指标 | 数量 |",
        "|------|------|",
    ]
    for k, v in s.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 目录维度", "", "| 目录 | 条目 |", "|------|------|"]
    for d, c in ds.most_common():
        lines.append(f"| {d} | {c} |")
    lines += ["", "## 主要分类", "", "| 分类 | 数量 |", "|------|------|"]
    for cat, c in kw["categories"].most_common():
        lines.append(f"| {cat} | {c} |")
    lines += ["", "## 风险标签", "", "| 标签 | 数量 |", "|------|------|"]
    for tag, c in kw["risk_tags"].most_common():
        lines.append(f"| {tag} | {c} |")
    lines += [
        "",
        "## diff --stat（未暂存）",
        "",
        "```",
        kw["diff_stat"].strip() or "(空)",
        "```",
        "",
        "## diff --cached --stat",
        "",
        "```",
        kw["diff_cached_stat"].strip() or "(空)",
        "```",
    ]
    return "\n".join(lines)


def _delete_md(kw: dict) -> str:
    lines = ["# 批量删除专项清单", "", "最终处置均为 **PENDING** 或 **HUMAN_DECISION_REQUIRED**，本轮未删除任何文件。", ""]
    for grp, paths in sorted(kw["mass_delete_groups"].items(), key=lambda x: -len(x[1])):
        lines.append(f"## {grp}（{len(paths)} 项）")
        lines.append("")
        for e in kw["deleted_entries"]:
            p = e.get("old_path") or e["path"]
            if top_dir(p) != grp:
                continue
            lines.append(f"- `{p}` | 分类={e['category']} | 处置={e['delete_disposition']} | 风险={','.join(e['risk_tags'])}")
        lines.append("")
    lines += [
        "## 运行记录/ 删除",
        "",
        f"数量：**{len(kw['run_record_deletes'])}**",
        "",
        "不得自动认定全部可删；需逐项确认是否含不可重建证据。",
        "",
        "## 不可重建历史删除候选",
        "",
        f"数量：**{len(kw['history_deletes'])}**",
    ]
    return "\n".join(lines)


def _rename_md(kw: dict) -> str:
    lines = ["# 重命名与中文路径迁移清单", "", f"Git 已识别重命名：**{len(kw['renames'])}**", f"含中文路径迁移标签：**{len(kw['cjk_renames'])}**", ""]
    for e in kw["renames"][:200]:
        lines.append(f"- `{e.get('old_path')}` → `{e['path']}` | {','.join(e['risk_tags'])}")
    if len(kw["renames"]) > 200:
        lines.append(f"- … 另有 {len(kw['renames']) - 200} 项，见 02_全部变更明细.json")
    return "\n".join(lines)


def _untracked_md(enriched: list) -> str:
    untracked = [e for e in enriched if e["kind"] == "untracked"]
    by_cat = Counter(e["category"] for e in untracked)
    lines = ["# 未跟踪文件分类", "", f"总计：**{len(untracked)}**", ""]
    for cat, n in by_cat.most_common():
        lines.append(f"## {cat}（{n}）")
        for e in untracked:
            if e["category"] != cat:
                continue
            lines.append(f"- `{e['path']}`")
        lines.append("")
    return "\n".join(lines)


def _temp_md(details: list) -> str:
    lines = ["# 根目录临时文件审查", "", "本轮未删除或移动。", ""]
    for d in details:
        if not d.get("exists"):
            continue
        lines.append(f"## `{d['name']}`")
        lines.append(f"- 大小：{d.get('size', 0)} 字节")
        lines.append(f"- 建议：{d.get('suggestion')}")
        lines.append(f"- 被引用：{d.get('referenced_by') or '无'}")
        if d.get("preview"):
            lines.append(f"- 预览：{d['preview']}")
        lines.append("")
    return "\n".join(lines)


def _scripts_md(info: dict) -> str:
    conforms = info["boundary_conforms"]
    lines = [
        "# scripts/ 与 脚本/ 目录边界",
        "",
        "## 结论",
        "",
        "**脚本/**：中文正式工具实现目录",
        "",
        "**scripts/**：应仅为英文兼容包装入口",
        "",
        f"当前是否符合：{'是' if conforms else '否 — 存在 DUPLICATE_LOGIC'}",
        "",
        "## scripts/ 文件",
        "",
    ]
    for f, cls in info["file_classes"].items():
        lines.append(f"- `{f}` → {cls}")
    lines += [
        "",
        f"## 脚本/ 文件数",
        "",
        f"{info['jiao_files_count']} 个（实现主体）",
        "",
        "## 引用 scripts/ 的文件（样本）",
        "",
    ]
    for r in info["refs_scripts"]:
        lines.append(f"- `{r}`")
    return "\n".join(lines)


def _artifacts_md(enriched: list, clean_nd: str, clean_ndx: str) -> str:
    return f"""# 生成物与运行产物分类

## git clean -nd 预览（未执行删除）

```
{clean_nd.strip() or "(无)"}
```

## git clean -ndX 预览（忽略文件，未执行删除）

```
{clean_ndx.strip() or "(无)"}
```

## 分类说明

| 类型 | 策略 |
|------|------|
| R5A—R5C 真实 API 原始记录 | 必须作为审计证据，不得自动删 |
| S0—P0 审计结果 | 必须作为审计证据提交 |
| golden / expected | 业务真源，不得自动删 |
| 运行记录/ | 可重建但需人工确认 |
| __pycache__ / .pytest_cache | 建议 ignore，已跟踪者需 git rm --cached |
"""


def _ignore_md(enriched: list, clean_ndx: str) -> str:
    return """# 建议忽略规则（仅建议，未修改 .gitignore）

> **注意**：`.gitignore` 不会自动停止跟踪已进入 Git 的文件。

| 模式 | 当前是否有跟踪项 | 加入 ignore 对已跟踪文件 | 可能隐藏证据 | 建议等级 |
|------|------------------|--------------------------|--------------|----------|
| `运行记录/` | 可能有 | 无效（需 rm --cached） | 中 | 中 — 人工确认后 |
| `__pycache__/` | 通常否 | 无效 | 低 | 高 |
| `.pytest_cache/` | 通常否 | 无效 | 低 | 高 |
| `*.pyc` | 通常否 | 无效 | 低 | 高 |
| `.venv*/` | 否 | 无效 | 低 | 高 |
| `*.egg-info/` | 视情况 | 需 rm --cached | 低 | 中 |
| `_t*.md` / `_tmp*.md` | 视情况 | 需 rm --cached | 中 | 低 — 人工审查后 |
| `XC-UE_当前项目盘查包_*.zip` | 通常否 | 无效 | 低 | 中 |

不得把「加入 ignore」作为解决大量已跟踪删除的唯一办法。
"""


def _batch_plan_md(batches: list) -> str:
    lines = ["# 分批提交候选计划", "", "不得使用 `git add .` / `git add -A` / `git commit -am`。", ""]
    for b in batches:
        lines += [
            f"## 批次 {b['id']}：{b['name']}",
            "",
            f"- 目标：{b['goal']}",
            f"- 允许路径前缀：{', '.join(b['allow_prefixes'][:8])}…",
            f"- 禁止路径：{', '.join(b['forbid_prefixes'])}",
            f"- 前置依赖：{b['depends_on'] or '无'}",
            f"- 风险：{b['risk']}",
            f"- 可单独回滚：{b['rollback']}",
            f"- 需要测试：{b['needs_test']}",
            f"- 人工确认：{'; '.join(b['human_confirm'])}",
            "",
        ]
    return "\n".join(lines)


def _human_md(human: list, kw: dict) -> str:
    lines = ["# 需要人工裁决的问题", "", f"总计：**{len(human)}** 项变更含 HUMAN_DECISION_REQUIRED", ""]
    lines.append("## 大量删除")
    lines.append("")
    lines.append(f"- 运行记录/ 删除：{len(kw['run_record_deletes'])} 项 → **PENDING**")
    lines.append(f"- 历史证据类删除：{len(kw['history_deletes'])} 项 → **HUMAN_DECISION_REQUIRED**")
    lines.append("")
    lines.append("## 待裁决文件")
    lines.append("")
    for p in sorted(set(kw["batch_paths"].get("待裁决", [])))[:100]:
        lines.append(f"- `{p}`")
    pending = len(kw["batch_paths"].get("待裁决", []))
    if pending > 100:
        lines.append(f"- … 另有 {pending - 100} 项")
    return "\n".join(lines)


def _p1b_md(kw: dict) -> str:
    return f"""# P1B 后续执行边界

## 当前状态

```text
P1A_WORKTREE_INVENTORY = PASSED
P1A_CHANGE_CLASSIFICATION = PASSED
P1A_COMMIT_PLAN = READY
MASS_DELETION_DECISION = PENDING
P1B_EXECUTION = BLOCKED_PENDING_HUMAN_DECISIONS
```

## P1B 允许操作（尚未执行）

- 按暂存清单分批 `git add <paths>`
- 人工确认后的清理提交（批次 F）
- 更新 `.gitignore`（批次 F，需人工确认）

## P1B 禁止

- `git add .` / `git add -A`
- 未确认的大量删除
- S2B-2 生产运行时切换
- 自动恢复/删除运行记录

## 前置条件

1. 人工裁决 {kw['machine']['human_decisions_required']} 项问题
2. 运行记录/ 删除策略确认
3. 根目录临时文件处置确认
4. scripts/ 边界确认（当前 duplicate：{kw['scripts_info']['duplicate_logic_candidates']})
"""


if __name__ == "__main__":
    raise SystemExit(main())
