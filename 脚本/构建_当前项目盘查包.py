#!/usr/bin/env python3
"""构建 XC-UE 当前项目盘查压缩包（工作区只读快照，不修改源码真源）。"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)
DATE_TAG = NOW.strftime("%Y%m%d")
ZIP_NAME = f"XC-UE_当前项目盘查包_{DATE_TAG}.zip"
HASH_MANIFEST_NAME = "盘查包哈希清单.json"
META_DIR = "盘查包元数据"

EXCLUDE_DIR_NAMES = {
    ".git",
    ".git_旧目录_无有效提交",
    "运行记录",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage_cache",
    ".venv",
    "htmlcov",
    "dist",
    "build",
    "99_归档_不要索引",
    "node_modules",
    "_candidates",
    "_legacy_root_inputs",
    "results",
    "attempt_",
}

EXCLUDE_FILE_NAMES = {
    ZIP_NAME,
    HASH_MANIFEST_NAME,
    "XC-UE_R4C_narrow_audit_bundle.zip",
    "R5D_v2语料外部窄查包.zip",
    "R4C_窄查哈希清单.json",
}

EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".zip", ".docx"}

SENSITIVE_PARTS = {".env", "credential", "secret", "api_key", "API_KEY"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def should_exclude(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIR_NAMES for p in parts):
        return True
    if any(p.startswith(".venv") for p in parts):
        return True
    if any(p.startswith("attempt_") for p in parts):
        return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    if rel.name.endswith(".egg-info"):
        return True
    low = rel.as_posix().lower()
    if any(s in low for s in SENSITIVE_PARTS):
        return True
    # 根目录临时草稿
    if len(parts) == 1 and rel.name.lower().startswith(("_tmp", "tmp_")):
        return True
    if len(parts) == 1 and rel.name.lower() in {"_t.md", "_t2.md", "_tmp_ch.md", "tmp_psy.md"}:
        return True
    return False


def git_meta() -> dict:
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True, encoding="utf-8", errors="replace"
    ).strip()
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8", errors="replace"
    ).strip()
    porcelain = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True, encoding="utf-8", errors="replace"
    )
    dirty_lines = [ln for ln in porcelain.splitlines() if ln.strip()]
    return {
        "branch": branch,
        "commit_ref": head,
        "git_dirty": bool(dirty_lines),
        "git_dirty_count": len(dirty_lines),
    }


def refresh_worktree_inventory() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "脚本" / "盘点_Git工作树.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    summary_path = ROOT / "00_工程总控" / "Git工作树治理_20260628" / "Git工作树盘点结果.json"
    summary: dict = {}
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-3:],
        "stderr_tail": proc.stderr.strip().splitlines()[-5:],
        "inventory_summary": summary,
    }


def iter_bundle_files() -> list[Path]:
    out: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if should_exclude(rel):
            continue
        out.append(p)
    return sorted(out, key=lambda x: x.relative_to(ROOT).as_posix())


def top_dir_label(rel: str) -> str:
    if "/" not in rel:
        return "根目录"
    return rel.split("/")[0]


def build_scope(meta: dict, inventory: dict) -> dict:
    return {
        "schema_version": "xcue.project-inventory-bundle/1.0",
        "generated_at": NOW.isoformat(),
        "snapshot_source": "CURRENT_WORKTREE",
        "bundle_zip_name": ZIP_NAME,
        "purpose": "当前工程盘查快照：治理文档、L0-L3 定义、工程执行层、测试语料与审计证据（排除运行记录与归档）",
        "repository_root": str(ROOT),
        **meta,
        "worktree_inventory_refresh": {
            "exit_code": inventory["exit_code"],
            "stdout_tail": inventory["stdout_tail"],
        },
        "inventory_highlights": inventory.get("inventory_summary") or {},
        "included_roots": [
            "00_工程总控/",
            "10_L0_总图层/",
            "20_L1_闸门层/",
            "30_L1.5_路由矩阵层/",
            "40_L2_正式能力层/",
            "50_L3_执行协议层/",
            "70_测试项目/",
            "tests/",
            "脚本/",
            "scripts/",
            "审计纠偏_2026-06-26/",
            "文档/",
        ],
        "excluded_patterns": sorted(EXCLUDE_DIR_NAMES | {".venv-*", "*.pyc", "*.zip", "*.docx", "99_归档_不要索引/"}),
        "read_order": [
            "XC-UE_项目说明与资源边界.md",
            "00_工程总控/当前工程唯一真源.md",
            "00_工程总控/当前系统状态_自动生成.md",
            "00_工程总控/Git工作树治理_20260628/00_盘点说明.md",
        ],
    }


def build_zip(zip_path: Path, file_entries: list[dict], manifest: dict) -> None:
    hm_rel = f"{META_DIR}/{HASH_MANIFEST_NAME}"
    scope_rel = f"{META_DIR}/盘查包说明.json"
    manifest_body = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    scope_body = json.dumps(manifest.get("scope_snapshot", {}), ensure_ascii=False, indent=2) + "\n"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in file_entries:
            zf.write(ROOT / entry["path"], entry["path"])
        zf.writestr(scope_rel, scope_body.encode("utf-8"))
        zf.writestr(hm_rel, manifest_body.encode("utf-8"))


def verify_zip(zip_path: Path, file_entries: list[dict]) -> list[str]:
    issues: list[str] = []
    hm_rel = f"{META_DIR}/{HASH_MANIFEST_NAME}"
    scope_rel = f"{META_DIR}/盘查包说明.json"
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        if bad:
            issues.append(f"corrupt member: {bad}")
        names = set(zf.namelist())
    for entry in file_entries:
        if entry["path"] not in names:
            issues.append(f"missing: {entry['path']}")
    if hm_rel not in names:
        issues.append(f"missing: {hm_rel}")
    if scope_rel not in names:
        issues.append(f"missing: {scope_rel}")
    banned = {".git", "运行记录", "99_归档_不要索引", "__pycache__"}
    for n in names:
        parts = Path(n).parts
        if any(p in banned or p.startswith(".venv") for p in parts):
            issues.append(f"forbidden path in zip: {n}")
    return issues


def main() -> int:
    inventory = refresh_worktree_inventory()
    if inventory["exit_code"] != 0:
        print("WARN: 工作树盘点脚本未完全成功，仍将打包当前工作区", file=sys.stderr)

    meta = git_meta()
    scope = build_scope(meta, inventory)

    bundle_files = iter_bundle_files()
    file_entries: list[dict] = []
    dir_counter: Counter[str] = Counter()
    for p in bundle_files:
        rel = p.relative_to(ROOT).as_posix()
        data = p.read_bytes()
        file_entries.append(
            {
                "path": rel,
                "size_bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )
        dir_counter[top_dir_label(rel)] += 1

    zip_path = ROOT / ZIP_NAME
    manifest = {
        "schema_version": "xcue.project-inventory-hash-manifest/1.0",
        "generated_at": NOW.isoformat(),
        "bundle_zip_name": ZIP_NAME,
        "commit_ref": meta["commit_ref"],
        "branch": meta["branch"],
        "git_dirty": meta["git_dirty"],
        "git_dirty_count": meta["git_dirty_count"],
        "total_files": len(file_entries),
        "total_bytes": sum(e["size_bytes"] for e in file_entries),
        "top_level_counts": dict(dir_counter),
        "files": file_entries,
        "meta_files": [
            f"{META_DIR}/盘查包说明.json",
            f"{META_DIR}/{HASH_MANIFEST_NAME}",
        ],
    }
    manifest["scope_snapshot"] = scope

    build_zip(zip_path, file_entries, manifest)
    zip_sha = sha256_file(zip_path)
    manifest["bundle_zip_sha256"] = zip_sha
    manifest["bundle_zip_size_bytes"] = zip_path.stat().st_size
    manifest["bundle_zip_file_count"] = len(file_entries) + 2
    build_zip(zip_path, file_entries, manifest)
    zip_sha = sha256_file(zip_path)

    issues = verify_zip(zip_path, file_entries)
    if issues:
        print("ZIP verification failed:", "; ".join(issues), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "zip_path": str(zip_path.resolve()),
                "zip_name": ZIP_NAME,
                "commit_ref": meta["commit_ref"],
                "branch": meta["branch"],
                "git_dirty": meta["git_dirty"],
                "git_dirty_count": meta["git_dirty_count"],
                "source_files": len(file_entries),
                "zip_file_count": manifest["bundle_zip_file_count"],
                "zip_size_bytes": zip_path.stat().st_size,
                "zip_sha256": zip_sha,
                "inventory_exit_code": inventory["exit_code"],
                "top_level_counts": dict(dir_counter),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
