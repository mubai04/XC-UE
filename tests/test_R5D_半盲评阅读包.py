from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
R5D_DIR = PILOT / "results" / "R5D_人工业务评审_20260628"
MANIFEST_PATH = PILOT / "manifest.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def prep_module():
    return _load_module("prep_r5d", ROOT / "脚本" / "准备_R5D_半盲评阅读包.py")


@pytest.fixture(scope="module")
def common_module():
    return _load_module("r5d_common", ROOT / "脚本" / "r5d_半盲评公共.py")


@pytest.fixture(scope="module")
def review_bundle(prep_module, common_module):
    chapter_snapshots: dict[str, str] = {}
    manifest = common_module.load_json(MANIFEST_PATH)
    for entry in manifest["cases"]:
        case_dir = (PILOT / entry["case_dir"]).resolve()
        project = common_module.load_json(case_dir / "project.json")
        resolution = common_module.resolve_chapter_path(case_dir, project)
        assert resolution.chapter_path is not None, resolution.error
        chapter_snapshots[entry["case_id"]] = resolution.chapter_path.read_text(encoding="utf-8")

    info = prep_module.prepare(R5D_DIR)
    assert not info["unresolved"]
    return {"info": info, "chapter_snapshots": chapter_snapshots}


def test_all_chapters_resolved_from_project_json(review_bundle, common_module):
    locator = common_module.load_json(R5D_DIR / "正文位置清单.json")
    assert len(locator["cases"]) == 12
    for row in locator["cases"]:
        assert row["read_complete"] is True
        assert row["error"] is None
        assert row["char_count"] > 0


def test_twelve_reading_packages_exist(review_bundle):
    pkg_dir = R5D_DIR / "半盲评阅读包"
    files = sorted(pkg_dir.glob("评审案例-*_半盲评阅读包.md"))
    assert len(files) == 12


def test_packages_contain_full_chapter_and_path(review_bundle, common_module):
    manifest = common_module.load_json(MANIFEST_PATH)
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        case_dir = (PILOT / entry["case_dir"]).resolve()
        project = common_module.load_json(case_dir / "project.json")
        resolution = common_module.resolve_chapter_path(case_dir, project)
        chapter_text = resolution.chapter_path.read_text(encoding="utf-8")
        order = common_module.load_json(R5D_DIR / "盲评顺序.json")
        row = next(r for r in order["phase_1_order"] if r["case_id"] == case_id)
        pkg_path = R5D_DIR / row["reading_package"]
        content = pkg_path.read_text(encoding="utf-8")
        assert resolution.chapter_rel in content
        assert chapter_text.strip() in content or chapter_text.strip().split("\n\n")[0] in content
        assert "[P0001]" in content


def test_phase1_packages_hide_expected_fields(review_bundle, common_module):
    pkg_dir = R5D_DIR / "半盲评阅读包"
    for path in pkg_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for token in common_module.HIDDEN_PHASE1_TOKENS:
            assert token not in text, f"{path.name} 泄露 {token}"


def test_packages_include_diagnosis_evidence_repair(review_bundle):
    pkg_dir = R5D_DIR / "半盲评阅读包"
    for path in pkg_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "## 4. L2 模型的诊断" in text
        assert "## 5. 模型引用的证据" in text
        assert "## 6. 模型给出的修复单" in text
        assert "repair_form" in text or "修复动作" in text


def test_semi_blind_metadata(review_bundle, common_module):
    order = common_module.load_json(R5D_DIR / "盲评顺序.json")
    summary = common_module.load_json(R5D_DIR / "人工评分汇总.json")
    assert order["review_mode"] == "SEMI_BLIND"
    assert order["strict_blind"] is False
    assert summary["review_mode"] == "SEMI_BLIND"
    guide = (R5D_DIR / "开始评审.md").read_text(encoding="utf-8")
    assert "SEMI_BLIND" in guide or "半盲" in guide


def test_interactive_script_does_not_read_expected():
    source = (ROOT / "脚本" / "启动_R5D_半盲人工评审.py").read_text(encoding="utf-8")
    assert "load_json(EXPECTED" not in source
    assert "案例评审表/对照复核" not in source
    assert "expected" not in source.lower()


def test_interactive_script_does_not_auto_pass():
    source = (ROOT / "脚本" / "启动_R5D_半盲人工评审.py").read_text(encoding="utf-8")
    assert '= "PASS"' not in source
    assert '"PASS"' in source  # only in mapping


def test_source_chapters_unchanged(review_bundle, common_module):
    manifest = common_module.load_json(MANIFEST_PATH)
    snapshots = review_bundle["chapter_snapshots"]
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        case_dir = (PILOT / entry["case_dir"]).resolve()
        project = common_module.load_json(case_dir / "project.json")
        resolution = common_module.resolve_chapter_path(case_dir, project)
        current = resolution.chapter_path.read_text(encoding="utf-8")
        assert current == snapshots[case_id]


def test_start_guide_and_chapter_locator_exist(review_bundle):
    assert (R5D_DIR / "开始评审.md").is_file()
    assert (R5D_DIR / "正文位置清单.md").is_file()
    assert (R5D_DIR / "评分示例说明.md").is_file()


def test_phase2_score_templates_have_extra_fields(review_bundle, common_module):
    for path in sorted((R5D_DIR / "案例评审表").glob("L2P-*_评分.json")):
        row = common_module.load_json(path)
        assert row.get("phase_1_overall") == ""
        assert row.get("phase_2_overall") == ""
        assert row.get("rating_changed") is False
        assert row.get("change_reason") == ""
