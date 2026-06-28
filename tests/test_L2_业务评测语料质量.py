from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
V2 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot_v2"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lib():
    return _load("l2_lib", ROOT / "脚本" / "l2_corpus_validate_lib.py")


def _tmp_case(tmp_path: Path, chapter: str, failure_evidence: list, expected: dict | None = None) -> Path:
    case_dir = tmp_path / "cases" / "TMP-001"
    (case_dir / "chapters").mkdir(parents=True)
    (case_dir / "chapters" / "chapter.md").write_text(chapter, encoding="utf-8")
    (case_dir / "failure_item.json").write_text(
        json.dumps(
            {
                "来源闸门": "L1-01",
                "名称": "TMP-001",
                "状态": "失败",
                "证据": failure_evidence,
                "失败类型": "测试",
                "候选模块": "L2-01",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (case_dir / "project.json").write_text(
        json.dumps(
            {
                "project_id": "TMP-001",
                "default_chapter": "chapters/chapter.md",
                "entrypoint": "chapters/chapter.md",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "expected").mkdir(exist_ok=True)
    if expected:
        (tmp_path / "expected" / "TMP-001.expected.json").write_text(
            json.dumps(expected, ensure_ascii=False), encoding="utf-8"
        )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "TMP-001",
                        "target_module": "L2-01",
                        "case_type": "A",
                        "case_dir": "cases/TMP-001",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_reject_meta_diagnosis_phrase(lib, tmp_path):
    root = _tmp_case(
        tmp_path,
        "# 段落一\n\n便于 L2 模块提取证据与规划修复。\n",
        [{"段落": 1, "摘句": "便于"}],
    )
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = lib.validate_case(root, data["cases"][0])
    assert not result["validation_ok"]


def test_reject_no_transition_phrase(lib, tmp_path):
    root = _tmp_case(
        tmp_path,
        "# 段落一\n\n没有任何过渡说明他如何抵达。\n",
        [{"段落": 1, "摘句": "没有任何过渡"}],
    )
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = lib.validate_case(root, data["cases"][0])
    assert not result["validation_ok"]


def test_reject_wrong_evidence_paragraph(lib, tmp_path):
    root = _tmp_case(
        tmp_path,
        "# 段落一\n\n甲在仓库。\n\n# 段落二\n\n乙在山顶。\n",
        [{"段落": 1, "摘句": "乙在山顶"}],
    )
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = lib.validate_case(root, data["cases"][0])
    assert not result["validation_ok"]


def test_reject_missing_quote(lib, tmp_path):
    root = _tmp_case(tmp_path, "# 段落一\n\n甲在仓库。\n", [{"段落": 1, "摘句": "不存在"}])
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = lib.validate_case(root, data["cases"][0])
    assert not result["validation_ok"]


def test_reject_expected_in_chapter(lib, tmp_path):
    root = _tmp_case(
        tmp_path,
        "# 段落一\n\nhuman_notes 写在正文里。\n",
        [{"段落": 1, "摘句": "human_notes"}],
        expected={"human_notes": "human_notes 写在正文里"},
    )
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = lib.validate_case(root, data["cases"][0])
    assert not result["validation_ok"]


def test_accept_natural_problem_without_answer(lib, tmp_path):
    chapter = """# 段落一

陈渡在旧仓。他推门，冷风扑面，发现自己站在灯塔山上。

# 段落二

他不记得如何离开旧仓。"""
    root = _tmp_case(
        tmp_path,
        chapter,
        [{"段落": 2, "摘句": "发现自己站在灯塔山上"}],
    )
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = lib.validate_case(root, data["cases"][0])
    assert result["validation_ok"]


def test_b_class_no_explicit_no_problem(lib, tmp_path):
    chapter = """# 段落一

裴青封渡改道，追上少年，涵洞交接，活着复命。"""
    root = _tmp_case(tmp_path, chapter, [{"段落": 2, "摘句": "封渡改道"}])
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = lib.validate_case(root, data["cases"][0])
    assert result["validation_ok"]


def test_v1_not_modified(lib):
    v1_chapter = (V1 / "cases" / "L2P-001" / "chapters" / "chapter.md").read_text(encoding="utf-8")
    assert "供真实模型诊断" in v1_chapter


def test_v2_directory_independent(lib):
    assert V2.is_dir()
    manifest = json.loads((V2 / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"].endswith("/2.0")
    assert len(manifest["cases"]) == 12


def test_v2_dataset_passes_validator(lib):
    report = lib.validate_dataset(V2)
    assert report["validation_ok"]
