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
from 退出码 import ExitCode
from L1_语义审计 import 审计
from 正文切分 import 切段, 清理正文
from tests.conftest import ROOT, find_chapter_evidence, make_mock_transport, make_semantic_context, sample_chapter_text, semantic_audit_payload


@pytest.fixture
def external_io_token(tmp_path, monkeypatch):
    token_file = tmp_path / "io.token"
    token_file.write_text("XCUE_TEST_EXTERNAL_IO_TOKEN_V1", encoding="utf-8")
    monkeypatch.setenv("XCUE_TEST_ALLOW_EXTERNAL_IO", "1")
    monkeypatch.setenv("XCUE_TEST_IO_TOKEN_FILE", str(token_file))
    return token_file


def _load_subprocess_json(result: subprocess.CompletedProcess) -> dict:
    for stream in (result.stdout, result.stderr):
        text = (stream or "").strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            for line in reversed(text.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
    raise AssertionError(f"no JSON payload: stdout={result.stdout!r} stderr={result.stderr!r}")


def _load_entry_json(stdout: str, stderr: str = "") -> dict:
    for stream in (stdout, stderr):
        text = (stream or "").strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            for line in reversed(text.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
    raise AssertionError(f"no JSON payload: stdout={stdout!r} stderr={stderr!r}")


def _import_l15_main():
    import importlib.util

    entry = ROOT / "00_工程总控" / "工程执行层" / "L1.5工程" / "L1.5运行入口.py"
    spec = importlib.util.spec_from_file_location("L15运行入口", entry)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.main


def _run_l15_on_packet(packet_path: Path, workspace: Path, pipeline_run_id: str) -> tuple[int, dict]:
    l15_out = workspace / "l15"
    l15_run = f"{pipeline_run_id}-L15"
    return _run_entry(
        _import_l15_main(),
        [
            "L1.5运行入口.py",
            "--failure-packet",
            str(packet_path),
            "--run-id",
            l15_run,
            "--out-dir",
            str(l15_out),
            "--pipeline-run-id",
            pipeline_run_id,
        ],
    )


def _run_entry(main_fn, argv: list[str]) -> tuple[int, dict]:
    buffer = StringIO()
    error_buffer = StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with redirect_stdout(buffer), redirect_stderr(error_buffer):
            code = main_fn()
    finally:
        sys.argv = old_argv
    payload = _load_entry_json(buffer.getvalue(), error_buffer.getvalue())
    return code, payload


def _e2e_workspace(repo_root: Path, seed: str) -> Path:
    workspace = repo_root / "运行记录" / f"pytest-e2e-{seed}"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _write_minimal_project(project_root: Path) -> None:
    (project_root / "chapters").mkdir(parents=True, exist_ok=True)
    (project_root / "IR").mkdir(parents=True, exist_ok=True)
    default_chapter = project_root / "chapters" / "default.md"
    default_chapter.write_text("# default\n\nplaceholder\n", encoding="utf-8")
    manifest = {
        "schema_version": "xcue.project-manifest/1.0",
        "project_id": "pytest-mini",
        "content_root": "chapters",
        "default_chapter": "chapters/default.md",
        "entrypoint": "chapters/default.md",
        "entrypoint_type": "project",
        "required_dirs": [],
    }
    (project_root / "project.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _setup_harness(root: Path, seed: str) -> Path:
    harness = root / f"harness-{seed}"
    (harness / "IR").mkdir(parents=True)
    (harness / "chapters" / "_candidates").mkdir(parents=True)
    (harness / "logs").mkdir()
    formal = harness / "chapters" / "ch01.md"
    formal.write_text(f"# 正式章\n\n{seed} 正式正文不得被覆盖。\n", encoding="utf-8")
    for name in (
        "IR-00_项目索引.md",
        "IR-04_事件链.md",
        "IR-05_章节目标表.md",
    ):
        (harness / "IR" / name).write_text(f"# {name}\n", encoding="utf-8")
    manifest = {
        "schema_version": "xcue.project-manifest/1.0",
        "project_id": f"harness-{seed}",
        "content_root": "chapters",
        "default_chapter": "chapters/ch01.md",
        "entrypoint": "chapters/ch01.md",
        "entrypoint_type": "project",
        "required_dirs": ["IR"],
    }
    (harness / "project.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return harness


def _failure_chapter(seed: str) -> str:
    return f"# 短章 {seed}\n\n{seed} 只有一句无关内容。\n"


def _l2_payload(quote: str, *, root_cause: str | None = None) -> dict:
    cause = root_cause or f"{quote} 导致结构链无法识别"
    return {
        "root_cause": cause,
        "root_cause_evidence_indices": [0],
        "fix_actions": ["只保留一条主行动线", "合并冗余段落"],
        "acceptance_criteria": ["读者能判断当前最重要问题只有一个"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }


def _patch_create_client(
    monkeypatch,
    *,
    l1_quote: str,
    l1_paragraph_id: str,
    l1_chapter_text: str,
    l2_quote: str,
    l3_body: str,
):
    def factory(stage, **kwargs):
        if stage == "L1":
            return create_client(
                "L1",
                api_key="k",
                transport=make_mock_transport(
                    semantic_audit_payload(
                        l1_quote,
                        target_overall="PASS",
                        paragraph_id=l1_paragraph_id,
                        chapter_text=l1_chapter_text,
                    )
                ),
                **{k: v for k, v in kwargs.items() if k != "api_key"},
            )
        if stage == "L2":
            return create_client(
                "L2",
                api_key="k",
                transport=make_mock_transport(_l2_payload(l2_quote)),
                **{k: v for k, v in kwargs.items() if k != "api_key"},
            )
        if stage == "L3":
            return create_client(
                "L3",
                api_key="k",
                transport=make_mock_transport({"title": "候选", "body": l3_body}),
                **{k: v for k, v in kwargs.items() if k != "api_key"},
            )
        raise AssertionError(f"unexpected stage {stage}")

    monkeypatch.setattr("DeepSeek客户端.create_client", factory)
    monkeypatch.setattr("L1_语义审计.create_client", factory)
    monkeypatch.setattr("L2_01_叙事结构能力.create_client", factory)
    monkeypatch.setattr("模型调用.create_client", factory)
    monkeypatch.setattr("候选正文生成.create_client", factory)


def test_l1_entry_semantic_unavailable_rejects(external_io_token, tmp_path, repo_root):
    seed = uuid.uuid4().hex[:8]
    workspace = _e2e_workspace(repo_root, seed)
    project_root = workspace / "project"
    _write_minimal_project(project_root)
    chapter = tmp_path / f"{seed}.md"
    chapter.write_text(
        "\n\n".join(
            f"第{i}段：{seed} 在仓库{i}核对批次，记录线索{i}，推进冲突{i}，焦点问题{i}。"
            for i in range(1, 80)
        ),
        encoding="utf-8",
    )
    run_id = f"E2E-L1-{seed}"
    out_dir = tmp_path / "l1-blocked"
    import L1运行入口

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("L1_前置质量护栏.检测", lambda paragraphs, l103=None: [])
    monkeypatch.setattr(
        "L1_语义审计.create_client",
        lambda stage, **kwargs: create_client(stage, api_key="", **{k: v for k, v in kwargs.items() if k != "api_key"}),
    )
    try:
        code, payload = _run_entry(
            L1运行入口.main,
            [
                "L1运行入口.py",
                "--run-id",
                run_id,
                "--chapter",
                str(chapter),
                "--out-dir",
                str(out_dir),
                "--project-root",
                str(project_root),
                "--project",
                "pytest-mini",
            ],
        )
    finally:
        monkeypatch.undo()
    assert code == int(ExitCode.BLOCKED)
    assert payload.get("status") == "AUDIT_BLOCKED"
    assert payload.get("audit_reason_type") == "API_UNAVAILABLE"
    assert payload.get("audit_blocker_count", 0) >= 1
    assert payload.get("failure_count", 0) == 0


def test_l1_inprocess_semantic_mock_passes():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    context = make_semantic_context(text)
    quote = f"{seed} 忽然察觉异常"
    paragraph_id, _ = find_chapter_evidence(text, quote)
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


def test_l1_l2_l3_entry_mock_pipeline(monkeypatch, repo_root):
    seed = uuid.uuid4().hex[:8]
    workspace = _e2e_workspace(repo_root, seed)
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
    l1_run = f"E2E-{seed}-L1"
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
    assert packet_path.exists()
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet.get("extensions", {}).get("chapter_path") == str(chapter.resolve())
    assert packet.get("failure_count", 0) > 0
    focused_items = [
        item
        for item in packet.get("items", [])
        if item.get("候选模块") == "L2-01"
    ]
    assert focused_items, "L1 未产出 L2-01 可路由失败项"
    packet["items"] = focused_items[:1]
    packet["failure_count"] = len(packet["items"])
    filtered_packet_path = workspace / f"{seed}_l2_input.json"
    filtered_packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    l15_code, l15_payload = _run_l15_on_packet(filtered_packet_path, workspace, l1_run)
    assert l15_code == 0, l15_payload
    assert l15_payload.get("final_status") == "ROUTED"

    l2_out = workspace / "l2"
    l2_run = f"E2E-{seed}-L2"
    import L2运行入口

    l2_code, l2_payload = _run_entry(
        L2运行入口.main,
        [
            "L2运行入口.py",
            "--l15-report",
            l15_payload["report_json"],
            "--run-id",
            l2_run,
            "--out-dir",
            str(l2_out),
            "--pipeline-run-id",
            l1_run,
        ],
    )
    assert l2_code == 0, l2_payload
    assert l2_payload["status"] == "COMPLETED"
    l2_report = json.loads(Path(l2_payload["report_json"]).read_text(encoding="utf-8"))
    assert l2_report["修复单"]
    assert l2_report["修复单"][0].get("诊断证据")

    l3_out = workspace / "l3"
    l3_run = f"E2E-{seed}-L3"
    import L3运行入口

    l3_code, l3_payload = _run_entry(
        L3运行入口.main,
        [
            "L3运行入口.py",
            "--l2-report",
            l2_payload["report_json"],
            "--run-id",
            l3_run,
            "--out-dir",
            str(l3_out),
            "--project-harness",
            harness.relative_to(repo_root).as_posix(),
            "--pipeline-run-id",
            l1_run,
        ],
    )
    assert l3_code == 0, l3_payload
    assert l3_payload["candidate_created_count"] >= 1
    assert l3_payload["candidate_created_count"] >= 1
    assert formal_path.read_text(encoding="utf-8") == formal_before
    candidates = list((harness / "chapters" / "_candidates").glob("*.md"))
    assert candidates
    assert all("_candidates" in str(path) for path in candidates)
    assert not any(path.name == "ch01.md" for path in candidates)


def test_l2_fictional_evidence_blocks_l3_entry(monkeypatch, repo_root):
    seed = uuid.uuid4().hex[:8]
    workspace = _e2e_workspace(repo_root, seed)
    chapter = workspace / f"{seed}.md"
    quote = f"{seed} 只有一句无关内容"
    chapter.write_text(_failure_chapter(seed), encoding="utf-8")

    def factory(stage, **kwargs):
        if stage == "L2":
            payload = _l2_payload("完全不存在的虚构摘句")
            return create_client("L2", api_key="k", transport=make_mock_transport(payload))
        return create_client(stage, api_key="k", **{k: v for k, v in kwargs.items() if k != "api_key"})

    monkeypatch.setattr("DeepSeek客户端.create_client", factory)
    monkeypatch.setattr("L2_01_叙事结构能力.create_client", factory)
    monkeypatch.setattr("模型调用.create_client", factory)

    packet = {
        "schema_version": "xcue.failure-packet/1.0",
        "pipeline_run_id": f"E2E-{seed}",
        "stage_run_id": f"E2E-{seed}-L1",
        "status": "SCREENING_REJECT",
        "failure_count": 1,
        "extensions": {"chapter_path": str(chapter)},
        "items": [
            {
                "闸门": "L1-01",
                "名称": "有序叙事信号",
                "状态": "失败",
                "说明": f"{seed} 结构链断",
                "证据": [{"段落": 1, "摘句": quote}],
                "严重级别": "error",
                "失败类型": "叙事失败",
                "候选模块": "L2-01",
                "回流验收位置": "L1-01",
                "修复方向": "压缩主行动线",
                "decision_role": "CONTENT_DECISION",
                "blocking": True,
                "reason_type": "",
            }
        ],
    }
    packet_path = workspace / f"{seed}_failure_packet.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    pipeline_id = f"E2E-{seed}"
    l15_code, l15_payload = _run_l15_on_packet(packet_path, workspace, pipeline_id)
    assert l15_code == 0, l15_payload

    import L2运行入口

    l2_code, l2_payload = _run_entry(
        L2运行入口.main,
        [
            "L2运行入口.py",
            "--l15-report",
            l15_payload["report_json"],
            "--run-id",
            f"E2E-{seed}-L2",
            "--out-dir",
            str(workspace / "l2"),
            "--pipeline-run-id",
            pipeline_id,
        ],
    )
    assert l2_code != 0
    assert l2_payload["status"] == "MODEL_BLOCKED"
    assert l2_payload["fix_count"] == 0

    import L3运行入口

    l3_code, _payload = _run_entry(
        L3运行入口.main,
        [
            "L3运行入口.py",
            "--l2-report",
            l2_payload["report_json"],
            "--run-id",
            f"E2E-{seed}-L3",
            "--out-dir",
            str(workspace / "l3"),
            "--project-harness",
            _setup_harness(workspace, seed).relative_to(repo_root).as_posix(),
            "--pipeline-run-id",
            pipeline_id,
        ],
    )
    assert l3_code != 0


def test_l3_api_failure_nonzero_exit(repo_root):
    seed = uuid.uuid4().hex[:8]
    workspace = _e2e_workspace(repo_root, seed)
    harness = _setup_harness(workspace, seed)
    l2_report = {
        "schema_version": "xcue.l2-report/1.0",
        "pipeline_run_id": f"E2E-{seed}",
        "stage_run_id": f"E2E-{seed}-L2",
        "status": "COMPLETED",
        "run_id": f"E2E-{seed}-L2",
        "输入文件": "mock.json",
        "输入数量": 1,
        "方法声明": "test",
        "标准校验问题": [],
        "回流校验问题": [],
        "接口判断": [],
        "修复单": [
            {
                "修复单类型": "L2 叙事结构修复单",
                "来源闸门": "L1-01",
                "接收模块": "L2-01",
                "输入问题": "test",
                "主失败类型": "叙事失败",
                "次失败类型": "F01",
                "修复动作": "压缩主行动线",
                "修复产物": "叙事结构修复单",
                "验收问题": "读者能判断",
                "回流位置": "L1-01",
                "是否需要其他L2辅助": "否",
                "是否需要回L15重路由": "否",
                "最终状态": "回原闸门复验",
                "rule_id": "L2-01:F01",
                "rule_version": "test",
                "诊断证据": [{"段落": 1, "摘句": f"{seed} 正式正文不得被覆盖"}],
            }
        ],
        "阻断项": [],
    }
    report_path = workspace / "l2_completed.json"
    report_path.write_text(json.dumps(l2_report, ensure_ascii=False, indent=2), encoding="utf-8")

    import L3运行入口

    old_key = os.environ.get("DEEPSEEK_API_KEY")
    os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        l3_code, l3_payload = _run_entry(
            L3运行入口.main,
            [
                "L3运行入口.py",
                "--l2-report",
                str(report_path),
                "--run-id",
                f"E2E-{seed}-L3",
                "--out-dir",
                str(workspace / "l3"),
                "--project-harness",
                harness.relative_to(repo_root).as_posix(),
                "--pipeline-run-id",
                f"E2E-{seed}",
            ],
        )
    finally:
        if old_key is not None:
            os.environ["DEEPSEEK_API_KEY"] = old_key

    assert l3_code != 0
    assert l3_payload.get("exit_code", l3_code) != 0
