#!/usr/bin/env python3
"""One-shot R4C narrow audit bundle builder. Does not modify source/tests."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).isoformat()

EXCLUDE_DIR_NAMES = {
    ".git",
    ".git_旧目录_无有效提交",
    "运行记录",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "dist",
    "build",
}
EXCLUDE_GLOBS_SUFFIX = {".pyc", ".pyo", ".egg-info"}
EXCLUDE_FILES = {
    "XC-UE_R4C_narrow_audit_bundle.zip",
    "R4C_窄查哈希清单.json",
}

NARROW_TEST_FILES = [
    "tests/test_L2_02_文风语言能力.py",
    "tests/test_L2_03_角色心理能力.py",
    "tests/test_L2_04_创意设定能力.py",
    "tests/test_L2_05_市场体验能力.py",
    "tests/test_L2_06_系统一致性能力.py",
    "tests/test_L2_独立能力结构.py",
    "tests/test_L2_领域泛化.py",
    "tests/test_L2_禁止夹具硬编码.py",
    "tests/test_L2_06_前序与来源.py",
    "tests/test_L2_R4A_模块.py",
    "tests/test_R4A_修复流水线.py",
    "tests/test_L1_5_执行层.py",
]

NARROW_CMD = "python -m pytest " + " ".join(NARROW_TEST_FILES)

FORBIDDEN = [
    "生存/达成目标",
    "规则正在收紧",
    "审查/层级规则",
    "触发异常或违规则生效",
    "违规则名单减少或承担后果",
    "名字减少意味着淘汰",
    "林舟想救妹妹",
    "回溯术",
    "左手已经断了",
    "双手完好",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def should_exclude(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIR_NAMES for p in parts):
        return True
    if any(p.startswith(".venv-") for p in parts):
        return True
    if rel.name in EXCLUDE_FILES:
        return True
    if rel.suffix in (".pyc", ".pyo"):
        return True
    if rel.name.endswith(".egg-info"):
        return True
    return False


def collect_nodeids() -> list[str]:
    proc = subprocess.run(
        NARROW_CMD.split() + ["--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip().startswith("tests/")]


def run_pytest(args: list[str]) -> dict:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout + proc.stderr
    passed = failed = skipped = collected = None
    duration = None
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) skipped", out)
    if m:
        skipped = int(m.group(1))
    m = re.search(r"(\d+) collected", out)
    if m:
        collected = int(m.group(1))
    m = re.search(r"in ([\d.]+)s", out)
    if m:
        duration = float(m.group(1))
    tail = [ln for ln in out.strip().splitlines() if ln.strip()]
    return {
        "command": " ".join(args),
        "exit_code": proc.returncode,
        "collected": collected,
        "passed": passed,
        "failed": failed if failed is not None else 0,
        "skipped": skipped if skipped is not None else 0,
        "duration_seconds": duration,
        "raw_summary": tail[-1] if tail else "",
    }


def scan_hardcoding() -> dict:
    scan_dirs = [
        ROOT / "00_工程总控/工程执行层/L2工程/L2_02_文风语言",
        ROOT / "00_工程总控/工程执行层/L2工程/L2_03_角色心理",
        ROOT / "00_工程总控/工程执行层/L2工程/L2_04_创意设定",
        ROOT / "00_工程总控/工程执行层/L2工程/L2_05_市场体验",
        ROOT / "00_工程总控/工程执行层/L2工程/L2_06_系统一致性",
    ]
    shared_files = [
        ROOT / "00_工程总控/工程执行层/L2工程/公共执行层/正文读取.py",
        ROOT / "00_工程总控/工程执行层/L2工程/公共执行层/前序章节.py",
        ROOT / "00_工程总控/工程执行层/L2工程/公共执行层/领域证据.py",
        ROOT / "00_工程总控/工程执行层/L2工程/公共执行层/验收禁止词.py",
    ]
    hits: list[dict] = []
    for d in scan_dirs:
        for p in sorted(d.glob("*.py")):
            text = p.read_text(encoding="utf-8")
            rel = p.relative_to(ROOT).as_posix()
            for s in FORBIDDEN:
                if s in text:
                    hits.append({"path": rel, "string": s})
    for p in shared_files:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT).as_posix()
        for s in FORBIDDEN:
            if s in text:
                hits.append({"path": rel, "string": s, "role": "shared_layer_or_blocklist"})
    arch = {
        "MODULE_SPECS": [],
        "ModuleSpec": [],
        "module_id_domain_switch": [],
        "fixed_present_value": [],
        "concatenated_corpus_quote_search": [],
    }
    scan_roots = scan_dirs + [ROOT / "00_工程总控/工程执行层/L2工程/公共执行层"]
    for d in scan_roots:
        files = [d] if d.is_file() else list(d.rglob("*.py"))
        for p in files:
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            text = p.read_text(encoding="utf-8", errors="replace")
            if "MODULE_SPECS" in text:
                arch["MODULE_SPECS"].append(rel)
            if "ModuleSpec" in text:
                arch["ModuleSpec"].append(rel)
            if re.search(r"if\s+module_id|match\s+module_id|module_id\s*==", text) and (
                "prompt" in text or "领域" in text
            ):
                arch["module_id_domain_switch"].append(rel)
            if '"present"' in text or "'present'" in text:
                if "事实" in text or "值" in text:
                    arch["fixed_present_value"].append(rel)
            if "all_quotes" in text and "corpus" in text and "+=" in text:
                arch["concatenated_corpus_quote_search"].append(rel)
    module_only = [h for h in hits if h["path"].startswith("00_工程总控/工程执行层/L2工程/L2_")]
    return {
        "forbidden_strings": FORBIDDEN,
        "forbidden_string_hits": hits,
        "forbidden_string_hits_five_modules_only": module_only,
        "five_modules_clean": len(module_only) == 0,
        "architecture_pattern_scan": arch,
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


def main() -> int:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    porcelain = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True, errors="replace"
    )
    dirty_lines = [ln for ln in porcelain.splitlines() if ln.strip()]

    nodeids = collect_nodeids()
    narrow_result = run_pytest(NARROW_CMD.split() + ["-q"])
    narrow_result["collected"] = len(nodeids)
    full_result = run_pytest(["python", "-m", "pytest", "-q"])

    hardcoding = scan_hardcoding()

    scope = {
        "schema_version": "xcue.r4c-narrow-audit/1.0",
        "snapshot_source": "CURRENT_WORKTREE",
        "commit_ref": head,
        "branch": branch,
        "git_dirty": bool(dirty_lines),
        "git_dirty_entries": dirty_lines,
        "git_dirty_count": len(dirty_lines),
        "generated_at": NOW,
        "audit_scope": "R4C_ONLY",
        "explicitly_out_of_scope": [
            "R0 baseline / AUDIT_BASELINE.json",
            "golden v1 / GS-*",
            "L1 semantic calibration",
            "R0-R3 re-audit",
            "real DeepSeek API evaluation",
            "candidate revalidation loop",
            "production eligibility review",
            "new Cursor refactor requests",
        ],
        "narrow_review_targets": {
            "shared_layer": [
                "00_工程总控/工程执行层/L2工程/公共执行层/正文读取.py",
                "00_工程总控/工程执行层/L2工程/公共执行层/前序章节.py",
                "00_工程总控/工程执行层/L2工程/公共执行层/领域证据.py",
                "00_工程总控/工程执行层/L2工程/公共执行层/验收禁止词.py",
            ],
            "five_modules": [
                "00_工程总控/工程执行层/L2工程/L2_02_文风语言/",
                "00_工程总控/工程执行层/L2工程/L2_03_角色心理/",
                "00_工程总控/工程执行层/L2工程/L2_04_创意设定/",
                "00_工程总控/工程执行层/L2工程/L2_05_市场体验/",
                "00_工程总控/工程执行层/L2工程/L2_06_系统一致性/",
            ],
            "pipeline_wiring": [
                "00_工程总控/工程执行层/L2工程/L2_L15执行.py",
                "00_工程总控/工程执行层/L2工程/L2运行入口.py",
                "00_工程总控/工程执行层/L2工程/能力注册表.py",
                "00_工程总控/工程执行层/L2工程/L2路径注册.py",
                "00_工程总控/工程执行层/修复流水线运行入口.py",
                "00_工程总控/工程执行层/统一运行入口.py",
            ],
            "compat_wrappers": [
                "00_工程总控/工程执行层/L2工程/L2_02_文风语言能力.py",
                "00_工程总控/工程执行层/L2工程/L2_03_角色心理能力.py",
                "00_工程总控/工程执行层/L2工程/L2_04_创意设定能力.py",
                "00_工程总控/工程执行层/L2工程/L2_05_市场体验能力.py",
                "00_工程总控/工程执行层/L2工程/L2_06_系统一致性能力.py",
                "00_工程总控/工程执行层/L2工程/L2语义能力执行器.py",
            ],
            "tests": NARROW_TEST_FILES,
        },
        "claimed_acceptance_labels": {
            "L2_02_DOMAIN_CAPABILITY": "PASSED",
            "L2_03_DOMAIN_CAPABILITY": "PASSED",
            "L2_04_DOMAIN_CAPABILITY": "PASSED",
            "L2_05_DOMAIN_CAPABILITY": "PASSED",
            "L2_06_DOMAIN_CAPABILITY": "PASSED",
            "R4B_STRUCTURE_REGRESSION": "PASSED",
            "R4C_DETERMINISTIC_GENERALIZATION": "PASSED",
            "REAL_MODEL_SEMANTIC_EFFECTIVENESS": "NOT_TESTED",
        },
        "claimed_acceptance_note": "实施方声明；非外部审计结论。",
        "pytest_narrow_command": NARROW_CMD + " -q",
        "pytest_narrow_nodeids": nodeids,
        "pytest_narrow_count": len(nodeids),
        "pytest_narrow_result": narrow_result,
        "pytest_full_result": full_result,
        "hardcoding_scan": hardcoding,
        "external_probe_requirements": {
            "L2_02": "未出现在仓库测试中的双来源/单来源语气文本",
            "L2_03": "新人物名、新目标表达、新动作链",
            "L2_04": "新规则句式、新代价、新限制",
            "L2_05": "新开头危险、中段重复、末段选择",
            "L2_06": "新实体、新属性、新状态及时间变化",
        },
    }

    scope_path = ROOT / "审计纠偏_2026-06-26" / "R4C" / "R4C_外部窄查范围.json"
    scope_path.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    bundle_files = iter_bundle_files()
    # ensure JSON in bundle list
    for extra in (scope_path,):
        if extra not in bundle_files:
            bundle_files.append(extra)
    bundle_files = sorted(set(bundle_files), key=lambda x: x.relative_to(ROOT).as_posix())

    file_entries = []
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

    hash_manifest_path = ROOT / "R4C_窄查哈希清单.json"
    scope_sha = sha256_file(scope_path)
    zip_path = ROOT / "XC-UE_R4C_narrow_audit_bundle.zip"
    hm_rel = hash_manifest_path.relative_to(ROOT).as_posix()

    def build_zip(manifest_body: dict) -> None:
        hash_manifest_path.write_text(
            json.dumps(manifest_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        hm_data = hash_manifest_path.read_bytes()
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for entry in file_entries:
                zf.write(ROOT / entry["path"], entry["path"])
            zf.writestr(hm_rel, hm_data)

    manifest = {
        "schema_version": "xcue.r4c-hash-manifest/1.0",
        "generated_at": NOW,
        "snapshot_source": "CURRENT_WORKTREE",
        "commit_ref": head,
        "branch": branch,
        "git_dirty": bool(dirty_lines),
        "bundle_zip_name": zip_path.name,
        "scope_json_path": scope_path.name,
        "scope_json_sha256": scope_sha,
        "total_files": len(file_entries),
        "files": file_entries,
        "excluded_patterns": sorted(EXCLUDE_DIR_NAMES | {".venv-*", "*.pyc", "*.pyo", "*.egg-info/"}),
    }
    build_zip(manifest)
    zip_sha = sha256_file(zip_path)
    manifest["bundle_zip_sha256"] = zip_sha
    manifest["bundle_zip_size_bytes"] = zip_path.stat().st_size
    manifest["bundle_zip_file_count"] = len(file_entries) + 1
    build_zip(manifest)
    zip_sha = sha256_file(zip_path)

    # verify zip
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"corrupt zip member: {bad}")
        names = set(zf.namelist())
    for entry in file_entries:
        if entry["path"] not in names:
            raise RuntimeError(f"missing in zip: {entry['path']}")
    if hm_rel not in names:
        raise RuntimeError(f"missing in zip: {hm_rel}")
    banned_parts = {".git", ".git_旧目录_无有效提交", "运行记录", "__pycache__", ".pytest_cache"}
    for n in names:
        parts = Path(n).parts
        if any(p in banned_parts or p.startswith(".venv") for p in parts):
            raise RuntimeError(f"forbidden path in zip: {n}")

    print(json.dumps({
        "scope_path": str(scope_path.resolve()),
        "hash_manifest_path": str(hash_manifest_path.resolve()),
        "zip_path": str(zip_path.resolve()),
        "commit_ref": head,
        "branch": branch,
        "git_dirty": bool(dirty_lines),
        "git_dirty_count": len(dirty_lines),
        "pytest_narrow_count": len(nodeids),
        "narrow_exit": narrow_result["exit_code"],
        "full_exit": full_result["exit_code"],
        "full_passed": full_result["passed"],
        "scope_sha256": scope_sha,
        "zip_sha256": zip_sha,
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_file_count": manifest["bundle_zip_file_count"],
        "five_modules_clean": hardcoding["five_modules_clean"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
