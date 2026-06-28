"""构建 R5D v2 语料外部窄查 ZIP（不含 API Key、模型输出与 v1 语料）。"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot_v2"
OUT_ZIP = ROOT / "R5D_v2语料外部窄查包.zip"

INCLUDE_PREFIXES = (
    "tests/fixtures/l2_real_api_pilot_v2/manifest.json",
    "tests/fixtures/l2_real_api_pilot_v2/README.md",
    "tests/fixtures/l2_real_api_pilot_v2/cases/",
    "tests/fixtures/l2_real_api_pilot_v2/expected/",
    "tests/fixtures/l2_real_api_pilot_v2/外部窄查材料/",
    "脚本/校验_L2_业务评测语料.py",
    "脚本/l2_corpus_validate_lib.py",
    "tests/test_L2_业务评测语料质量.py",
)

EXCLUDE_PARTS = (
    ".git",
    "__pycache__",
    ".env",
    "api_key",
    "API_KEY",
    "运行记录",
    "l2_real_api_pilot/",
    "node_modules",
    ".venv",
    "venv",
)


def _should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    for part in EXCLUDE_PARTS:
        if part in rel:
            return False
    for prefix in INCLUDE_PREFIXES:
        if rel == prefix or rel.startswith(prefix):
            return True
    return False


def _verify_zip(zpath: Path) -> list[str]:
    issues: list[str] = []
    with zipfile.ZipFile(zpath, "r") as zf:
        names = zf.namelist()
        case_count = sum(1 for n in names if "/cases/L2V2-" in n and n.endswith("chapter.md"))
        if case_count != 12:
            issues.append(f"chapter.md count={case_count}, expected 12")
        phase1 = [n for n in names if "第一阶段_正文审查包" in n]
        phase2 = [n for n in names if "第二阶段_预期对照包" in n]
        if len(phase1) != 12:
            issues.append(f"phase1 packages={len(phase1)}")
        if len(phase2) != 12:
            issues.append(f"phase2 packages={len(phase2)}")
        for n in names:
            if "API_KEY" in n or n.endswith(".env"):
                issues.append(f"sensitive file in zip: {n}")
        for n in phase1:
            data = zf.read(n).decode("utf-8", errors="replace")
            if '"expected_issue_present"' in data or '"human_notes"' in data:
                issues.append(f"phase1 leak expected fields: {n}")
            if '"acceptable_root_causes"' in data or '"forbidden_diagnoses"' in data:
                issues.append(f"phase1 leak expected fields: {n}")
        if any("l2_real_api_pilot/" in n and "l2_real_api_pilot_v2" not in n for n in names):
            issues.append("v1 pilot included")
        if any("运行记录" in n for n in names):
            issues.append("runtime records included")
    return issues


def build() -> Path:
    if not (V2 / "外部窄查材料").is_dir():
        raise FileNotFoundError("请先运行：python 脚本/生成_R5D_v2外部窄查材料.py")

    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if not _should_include(path):
                continue
            arc = path.relative_to(ROOT).as_posix()
            zf.write(path, arc)

    issues = _verify_zip(OUT_ZIP)
    if issues:
        raise RuntimeError("ZIP verification failed: " + "; ".join(issues))
    return OUT_ZIP


def main() -> int:
    zpath = build()
    print(f"BUILT: {zpath}")
    print(f"SIZE_BYTES: {zpath.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
