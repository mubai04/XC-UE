from __future__ import annotations

import hashlib
import importlib.util
import json
import uuid
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from DeepSeek客户端 import create_client
from tests.conftest import ROOT, make_mock_transport, sample_chapter_text


def _load_entry(main_fn, argv: list[str]) -> tuple[int, dict]:
    buffer = StringIO()
    error_buffer = StringIO()
    old_argv = __import__("sys").argv
    __import__("sys").argv = argv
    try:
        with redirect_stdout(buffer), redirect_stderr(error_buffer):
            code = main_fn()
    finally:
        __import__("sys").argv = old_argv
    text = (buffer.getvalue() or error_buffer.getvalue() or "").strip()
    return code, json.loads(text)


def _failure_packet(chapter: Path, seed: str, failure_type: str, module: str, *, secondary: dict | None = None) -> dict:
    _, body = __import__("正文切分", fromlist=["清理正文"]).清理正文(chapter.read_text(encoding="utf-8"))
    quote = body.split("\n\n")[1][:20] if "\n\n" in body else body[:20]
    items = [
        {
            "闸门": "L1-01" if module != "L2-05" else "L1-02",
            "名称": "测试项",
            "状态": "失败",
            "说明": f"{seed} 主失败 {failure_type}",
            "证据": [{"段落": 1, "摘句": quote}],
            "严重级别": "error",
            "失败类型": failure_type,
            "候选模块": module,
            "回流验收位置": "L1-01",
            "修复方向": "测试修复方向",
            "decision_role": "CONTENT_DECISION",
            "blocking": True,
        }
    ]
    if secondary:
        items.append(secondary)
    return {
        "schema_version": "xcue.failure-packet/1.0",
        "pipeline_run_id": f"R4A-{seed}",
        "stage_run_id": f"R4A-{seed}-L1",
        "status": "SCREENING_REJECT",
        "failure_count": len(items),
        "extensions": {"chapter_path": str(chapter)},
        "items": items,
    }


def _import_l15_main():
    entry = ROOT / "00_工程总控" / "工程执行层" / "L1.5工程" / "L1.5运行入口.py"
    spec = importlib.util.spec_from_file_location("L15运行入口", entry)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.main


@pytest.fixture
def l15_workspace(tmp_path, repo_root, external_io_token):
    seed = uuid.uuid4().hex[:8]
    workspace = repo_root / "运行记录" / f"pytest-l15-{seed}"
    workspace.mkdir(parents=True, exist_ok=True)
    chapter = workspace / "chapter.md"
    chapter.write_text(sample_chapter_text(seed), encoding="utf-8")
    return workspace, seed, chapter


def test_l15_routes_single_primary_failure(l15_workspace):
    workspace, seed, chapter = l15_workspace
    packet = _failure_packet(chapter, seed, "文风失败", "L2-02")
    packet["items"].append(
        {
            "闸门": "L1-02",
            "名称": "次要",
            "状态": "失败",
            "说明": f"{seed} 次要 E低",
            "证据": [{"段落": 2, "摘句": "段落二"}],
            "严重级别": "warning",
            "失败类型": "E低：即时情绪反馈弱",
            "候选模块": "L2-05",
            "回流验收位置": "L1-02",
            "修复方向": "次要",
            "decision_role": "CONTENT_DECISION",
            "blocking": False,
        }
    )
    packet_path = workspace / "packet.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    code, payload = _load_entry(
        _import_l15_main(),
        [
            "L1.5运行入口.py",
            "--failure-packet",
            str(packet_path),
            "--run-id",
            f"L15-{seed}",
            "--out-dir",
            str(workspace / "out"),
            "--pipeline-run-id",
            f"R4A-{seed}",
        ],
    )
    report = json.loads((workspace / "out" / f"L15-{seed}.json").read_text(encoding="utf-8"))
    assert code == 0
    assert report["final_status"] == "ROUTED"
    assert report["target_module"] == "L2-02"
    assert len(report["secondary_failures"]) == 1
    assert payload["target_module"] == "L2-02"


def test_l15_manual_review_on_route_conflict(l15_workspace):
    workspace, seed, chapter = l15_workspace
    packet = _failure_packet(chapter, seed, "文风失败", "L2-02")
    packet["items"].append(
        {
            "闸门": "L1-01",
            "名称": "同级",
            "状态": "失败",
            "说明": f"{seed} 角色",
            "证据": [{"段落": 3, "摘句": "段落三"}],
            "严重级别": "error",
            "失败类型": "角色失败",
            "候选模块": "L2-03",
            "回流验收位置": "L1-01",
                "修复方向": "角色",
                "decision_role": "CONTENT_DECISION",
                "blocking": True,
            }
    )
    packet_path = workspace / "conflict.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    code, payload = _load_entry(
        _import_l15_main(),
        [
            "L1.5运行入口.py",
            "--failure-packet",
            str(packet_path),
            "--run-id",
            f"L15C-{seed}",
            "--out-dir",
            str(workspace / "out2"),
            "--pipeline-run-id",
            f"R4A-{seed}",
        ],
    )
    assert payload["final_status"] == "MANUAL_REVIEW"
    assert code != 0


def test_l15_rejects_overwrite(l15_workspace):
    workspace, seed, chapter = l15_workspace
    packet_path = workspace / "one.json"
    packet_path.write_text(json.dumps(_failure_packet(chapter, seed, "文风失败", "L2-02"), ensure_ascii=False), encoding="utf-8")
    out_dir = workspace / "out3"
    argv = [
        "L1.5运行入口.py",
        "--failure-packet",
        str(packet_path),
        "--run-id",
        f"L15D-{seed}",
        "--out-dir",
        str(out_dir),
        "--pipeline-run-id",
        f"R4A-{seed}",
    ]
    code1, _ = _load_entry(_import_l15_main(), argv)
    assert code1 == 0
    code2, _ = _load_entry(_import_l15_main(), argv)
    assert code2 != 0


def test_unified_entry_l15_smoke(l15_workspace):
    workspace, seed, chapter = l15_workspace
    packet_path = workspace / "unified.json"
    packet_path.write_text(json.dumps(_failure_packet(chapter, seed, "文风失败", "L2-02"), ensure_ascii=False), encoding="utf-8")
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "00_工程总控" / "工程执行层" / "统一运行入口.py"),
            "--target",
            "L1.5",
            "--failure-packet",
            str(packet_path),
            "--run-id",
            f"R4A-L15-SMOKE-{seed}",
            "--out-dir",
            str(workspace / "unified-out"),
            "--pipeline-run-id",
            f"R4A-{seed}",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(result.stdout or result.stderr)
    assert result.returncode == 0
    assert payload["returncode"] == 0
