from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from DeepSeek客户端 import create_client
from L1_语义审计 import 审计
from 工程异常 import 项目错误
from 退出码 import ExitCode
from 项目加载器 import 加载项目
from tests.conftest import ROOT, find_chapter_evidence, make_mock_transport, make_semantic_context, sample_chapter_text, semantic_audit_payload
from tests.test_e2e_pipeline import (
    _e2e_workspace,
    _failure_chapter,
    _patch_create_client,
    _run_entry,
    _setup_harness,
    _write_minimal_project,
)


TP001_ROOT = ROOT / "70_测试项目" / "TP-001_CleanHarness_IR_Runtime"
TP001_CHAPTER = TP001_ROOT / "chapters" / "ch01.md"
UNIFIED_ENTRY = ROOT / "00_工程总控" / "工程执行层" / "统一运行入口.py"


def test_tp001_loader_resolves(repo_root: Path):
    project = 加载项目(repo_root, "TP-001")
    assert project.project_id == "TP-001"
    assert project.chapter_sequence == ("chapters/ch01.md", "chapters/ch02.md")
    assert project.content_root.name == "chapters"
    assert project.chapter_source.name == "ch01.md"


def test_tp001_unified_entry_smoke_without_api_key(repo_root: Path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    result = subprocess.run(
        [
            sys.executable,
            str(UNIFIED_ENTRY),
            "--target",
            "L1",
            "--project",
            "TP-001",
            "--chapter",
            "70_测试项目/TP-001_CleanHarness_IR_Runtime/chapters/ch01.md",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode != int(ExitCode.PROJECT_ERROR)
    combined = f"{result.stdout}\n{result.stderr}"
    assert "PROJECT_RESOLUTION_FAILED" not in combined
    if result.returncode == int(ExitCode.BLOCKED):
        assert "API_UNAVAILABLE" in combined or "AUDIT_BLOCKED" in combined


def test_tp001_l1_inprocess_mock_no_api_block(monkeypatch, repo_root: Path):
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    quote = f"{seed} 忽然察觉异常"
    paragraph_id, _ = find_chapter_evidence(text, quote)
    chapter = repo_root / "运行记录" / f"tp001-mock-{seed}.md"
    chapter.parent.mkdir(parents=True, exist_ok=True)
    chapter.write_text(text, encoding="utf-8")

    加载项目(repo_root, "TP-001")
    context = make_semantic_context(text)
    client = create_client(
        "L1",
        api_key="k",
        transport=make_mock_transport(
            semantic_audit_payload(
                quote, target_overall="PASS", paragraph_id=paragraph_id, chapter_text=text
            )
        ),
    )
    result = 审计(context, client=client)
    assert result.可用
    assert result.整体结论 == "PASS"


def test_tp001_l1_l2_l3_inprocess_mock(monkeypatch, repo_root: Path):
    加载项目(repo_root, "TP-001")
    seed = uuid.uuid4().hex[:8]
    workspace = _e2e_workspace(repo_root, f"tp001-{seed}")
    project_root = workspace / "project"
    _write_minimal_project(project_root)
    chapter = project_root / "chapters" / f"{seed}.md"
    chapter.write_text(_failure_chapter(seed), encoding="utf-8")
    chapter_text = chapter.read_text(encoding="utf-8")
    l2_quote = f"{seed} 只有一句无关内容"
    l1_paragraph_id, _ = find_chapter_evidence(chapter_text, l2_quote)
    l3_body = f"{seed} 候选段落一。\n\n{seed} 候选段落二，冲突继续升级。\n"
    _patch_create_client(
        monkeypatch,
        l1_quote=l2_quote,
        l1_paragraph_id=l1_paragraph_id,
        l1_chapter_text=chapter_text,
        l2_quote=l2_quote,
        l3_body=l3_body,
    )

    harness = _setup_harness(workspace, seed)
    formal_path = harness / "chapters" / "ch01.md"
    formal_before = formal_path.read_text(encoding="utf-8")

    l1_out = workspace / "l1"
    l1_run = f"TP001-{seed}-L1"
    import L1运行入口

    l1_code, l1_payload = _run_entry(
        L1运行入口.main,
        [
            "L1运行入口.py",
            "--run-id",
            l1_run,
            "--chapter",
            str(chapter.resolve()),
            "--out-dir",
            str(l1_out),
            "--project-root",
            str(project_root),
            "--project",
            "pytest-mini",
            "--pipeline-run-id",
            l1_run,
        ],
    )
    assert l1_code != 0
    packet_path = Path(l1_payload["failure_packet"])
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    focused = [item for item in packet.get("items", []) if item.get("候选模块") == "L2-01"]
    assert focused
    packet["items"] = focused[:1]
    packet["failure_count"] = len(packet["items"])
    filtered_packet_path = workspace / f"{seed}_l2_input.json"
    filtered_packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    from tests.test_e2e_pipeline import _import_l15_main, _run_entry as e2e_run_entry, _run_l15_on_packet

    l15_code, l15_payload = _run_l15_on_packet(filtered_packet_path, workspace, l1_run)
    assert l15_code == 0, l15_payload

    import L2运行入口

    l2_code, l2_payload = e2e_run_entry(
        L2运行入口.main,
        [
            "L2运行入口.py",
            "--l15-report",
            l15_payload["report_json"],
            "--run-id",
            f"TP001-{seed}-L2",
            "--out-dir",
            str(workspace / "l2"),
            "--pipeline-run-id",
            l1_run,
        ],
    )
    assert l2_code == 0, l2_payload

    import L3运行入口

    l3_code, l3_payload = _run_entry(
        L3运行入口.main,
        [
            "L3运行入口.py",
            "--l2-report",
            l2_payload["report_json"],
            "--run-id",
            f"TP001-{seed}-L3",
            "--out-dir",
            str(workspace / "l3"),
            "--project-harness",
            harness.relative_to(repo_root).as_posix(),
            "--pipeline-run-id",
            l1_run,
        ],
    )
    assert l3_code == 0, l3_payload
    assert formal_path.read_text(encoding="utf-8") == formal_before
