from __future__ import annotations

import json
import sys
import uuid
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from DeepSeek客户端 import create_client
from L1决策角色 import 聚合终态, 理由_API不可用
from L1模型 import 检测项, 闸门结果
from L1_语义审计 import 审计, 语义审计结果
from L1_00_闸门接口校验 import 检测 as 接口校验
from 失败包生成 import 分拆阻断项, 生成失败包
from 正文切分 import 切段, 正文字数, 清理正文
from 退出码 import ExitCode
from 运行状态 import 审计阻断, 机器初筛通过, 机器初筛退回, 需要人工复核
from tests.conftest import ROOT, make_mock_transport, make_semantic_context, sample_chapter_text, semantic_audit_payload


def _padded_chapter(seed: str, *, min_chars: int = 2100) -> str:
    title, body = 清理正文(sample_chapter_text(seed))
    paragraphs = 切段(body)
    idx = 0
    while 正文字数(paragraphs) < min_chars:
        idx += 1
        body += (
            f"\n\n第{idx}段：{seed} 在{idx}号仓库存档，核对来源与批次，"
            f"记录尚未验证的线索，并继续推进因果与冲突。"
        )
        paragraphs = 切段(body)
    return f"# 测试章节 {seed}\n\n{body}\n"


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


def _run_l1_entry(
    *,
    chapter_path: Path,
    out_dir: Path,
    project_root: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
    semantic_overall: str = "PASS",
    skip_guard: bool = False,
    api_key: str = "k",
) -> tuple[int, dict]:
    title, body = 清理正文(chapter_path.read_text(encoding="utf-8"))
    paragraphs = 切段(body)
    quote_para = next((p for p in reversed(paragraphs) if not p.文本.startswith("#")), paragraphs[-1])
    quote = quote_para.文本[: min(20, len(quote_para.文本))]
    paragraph_id = quote_para.段落ID

    def factory(stage, **kwargs):
        if api_key:
            return create_client(
                stage,
                api_key=api_key,
                transport=make_mock_transport(
                    semantic_audit_payload(
                        quote,
                        target_overall=semantic_overall,
                        paragraph_id=paragraph_id,
                        chapter_text=chapter_path.read_text(encoding="utf-8"),
                    )
                ),
                **{k: v for k, v in kwargs.items() if k != "api_key"},
            )
        return create_client(stage, api_key="", **{k: v for k, v in kwargs.items() if k != "api_key"})

    monkeypatch.setattr("L1_语义审计.create_client", factory)
    if skip_guard:
        monkeypatch.setattr("L1_前置质量护栏.检测", lambda paragraphs, l103=None: [])

    import L1运行入口

    argv = [
        "L1运行入口.py",
        "--run-id",
        run_id,
        "--chapter",
        str(chapter_path),
        "--out-dir",
        str(out_dir),
        "--project-root",
        str(project_root),
        "--project",
        "pytest-mini",
    ]
    buffer = StringIO()
    error_buffer = StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with redirect_stdout(buffer), redirect_stderr(error_buffer):
            code = L1运行入口.main()
    finally:
        sys.argv = old_argv
    payload = _load_entry_json(buffer.getvalue(), error_buffer.getvalue())
    return code, payload


def _read_artifacts(out_dir: Path, run_id: str) -> tuple[dict, dict, dict]:
    report = json.loads((out_dir / f"{run_id}.json").read_text(encoding="utf-8"))
    packet = json.loads((out_dir / f"{run_id}_failure_packet.json").read_text(encoding="utf-8"))
    audit = json.loads((out_dir / f"{run_id}_audit_blockers.json").read_text(encoding="utf-8"))
    return report, packet, audit


@pytest.fixture
def external_io_token(tmp_path, monkeypatch):
    token_file = tmp_path / "io.token"
    token_file.write_text("XCUE_TEST_EXTERNAL_IO_TOKEN_V1", encoding="utf-8")
    monkeypatch.setenv("XCUE_TEST_ALLOW_EXTERNAL_IO", "1")
    monkeypatch.setenv("XCUE_TEST_IO_TOKEN_FILE", str(token_file))
    return token_file


@pytest.fixture
def mini_project(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "chapters").mkdir(parents=True)
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
    return project_root


@pytest.mark.parametrize(
    ("semantic_overall", "skip_guard", "api_key", "chapter_builder", "expect_status", "expect_semantic", "expect_audit_items"),
    [
        ("PASS", False, "k", lambda s: f"# 短章\n\n{s} 只有一句。\n", 机器初筛退回, "PASS", False),
        ("PASS", False, "", lambda s: f"# 短章\n\n{s} 只有一句。\n", 机器初筛退回, 审计阻断, True),
        ("PASS", True, "", lambda s: _padded_chapter(s), 审计阻断, 审计阻断, True),
        ("FAIL", True, "k", lambda s: _padded_chapter(s), 机器初筛退回, "FAIL", False),
        ("REVIEW", True, "k", lambda s: _padded_chapter(s), 需要人工复核, "REVIEW", False),
        ("PASS", True, "k", lambda s: _padded_chapter(s), 机器初筛通过, "PASS", False),
    ],
    ids=[
        "guard_fail_semantic_pass",
        "guard_fail_semantic_blocked",
        "guard_pass_semantic_blocked",
        "guard_pass_semantic_fail",
        "guard_pass_semantic_review",
        "guard_pass_semantic_pass",
    ],
)
def test_terminal_state_matrix(
    external_io_token,
    monkeypatch,
    mini_project,
    tmp_path,
    semantic_overall,
    skip_guard,
    api_key,
    chapter_builder,
    expect_status,
    expect_semantic,
    expect_audit_items,
):
    seed = uuid.uuid4().hex[:8]
    run_id = f"L1-MAT-{seed}"
    chapter = tmp_path / f"{seed}.md"
    chapter.write_text(chapter_builder(seed), encoding="utf-8")
    out_dir = tmp_path / run_id
    code, payload = _run_l1_entry(
        chapter_path=chapter,
        out_dir=out_dir,
        project_root=mini_project,
        run_id=run_id,
        monkeypatch=monkeypatch,
        semantic_overall=semantic_overall,
        skip_guard=skip_guard,
        api_key=api_key,
    )
    if expect_status == 机器初筛通过:
        assert code == int(ExitCode.OK)
    elif expect_status == 需要人工复核:
        assert code == int(ExitCode.REVIEW_REQUIRED)
    elif expect_status == 审计阻断:
        assert code == int(ExitCode.BLOCKED)
    else:
        assert code == int(ExitCode.GATE_REJECTED)
    assert payload["status"] == expect_status
    report, packet, audit = _read_artifacts(out_dir, run_id)
    assert report["semantic_audit_status"] == expect_semantic
    assert report["validation_status"] == "VALIDATED"
    if expect_audit_items:
        assert audit["blocker_count"] > 0
        assert payload["audit_blocker_count"] > 0
    else:
        assert audit["blocker_count"] == 0
    assert all(item.get("decision_role") != "AUDIT_BLOCKER" for item in packet["items"])
    assert all(item.get("decision_role") != "DIAGNOSTIC" for item in packet["items"])


def test_guard_fail_and_api_blocked_prefers_reject_with_semantic_flag(external_io_token, monkeypatch, mini_project, tmp_path):
    seed = uuid.uuid4().hex[:8]
    run_id = f"L1-COMB-{seed}"
    chapter = tmp_path / f"{seed}.md"
    chapter.write_text(f"# 短章\n\n{seed} 只有一句。\n", encoding="utf-8")
    out_dir = tmp_path / run_id
    _, payload = _run_l1_entry(
        chapter_path=chapter,
        out_dir=out_dir,
        project_root=mini_project,
        run_id=run_id,
        monkeypatch=monkeypatch,
        semantic_overall="PASS",
        skip_guard=False,
        api_key="",
    )
    assert payload["status"] == 机器初筛退回
    report, packet, audit = _read_artifacts(out_dir, run_id)
    assert report["semantic_audit_status"] == 审计阻断
    assert report["audit_reason_type"] == "API_UNAVAILABLE"
    assert packet["failure_count"] >= 1
    assert audit["blocker_count"] >= 1
    assert payload["failure_count"] >= 1
    assert payload["audit_blocker_count"] >= 1


def test_api_unavailable_audit_blocked(external_io_token, monkeypatch, mini_project, tmp_path):
    seed = uuid.uuid4().hex[:8]
    run_id = f"L1-BLK-{seed}"
    chapter = tmp_path / f"{seed}.md"
    chapter.write_text(_padded_chapter(seed), encoding="utf-8")
    out_dir = tmp_path / "l1-blocked"
    _, payload = _run_l1_entry(
        chapter_path=chapter,
        out_dir=out_dir,
        project_root=mini_project,
        run_id=run_id,
        monkeypatch=monkeypatch,
        semantic_overall="PASS",
        skip_guard=True,
        api_key="",
    )
    report, packet, audit = _read_artifacts(out_dir, run_id)
    assert report["status"] == 审计阻断
    assert payload["status"] == 审计阻断
    assert report["audit_reason_type"] == "API_UNAVAILABLE"
    assert report["semantic_audit_status"] == 审计阻断
    assert packet["failure_count"] == 0
    assert audit["blocker_count"] == 1
    assert all(item["decision_role"] == "AUDIT_BLOCKER" for item in audit["items"])


def test_l100_invalid_input_audit_blocked():
    bad_gate = 闸门结果(
        闸门="L1-01",
        判断结果="STRUCTURE_SIGNAL_PRESENT",
        输入材料=[],
        失败类型=[],
        失败位置=[],
        是否进入L15="否",
        调用方向=[],
        回流验收位置="L1-01",
        最终状态="STRUCTURE_SIGNAL_PRESENT",
        检测项=[],
    )
    del bad_gate.判断结果  # type: ignore[attr-defined]
    l100 = 接口校验([bad_gate])
    split = 分拆阻断项([l100])
    semantic = 语义审计结果(检测项列表=[], 可用=True, 整体结论="PASS")
    final = 聚合终态(semantic, split.失败包, split.审计阻断项)
    assert final.status == 审计阻断
    assert final.audit_reason_type == "INPUT_INVALID"
    assert len(split.失败包) == 0
    assert len(split.审计阻断项) == 1


def _garbled_chapter(seed: str) -> str:
    lines = [
        f"# 乱码章 {seed}",
        "",
        "忽然门后有血怎么会制玄赖号驹癸白始辰衣出戎被巨鸣洪平珍洪羽归冬木冈王芥化师爱成水果河始阙淡水乃咸羽余成。",
        "因为规则只有一个代价不能省在云己草岁裳被有光霜鸟潜潜宾虞夜平律为调宇壬潜赖庚拱坐化列夜殷臣暑结张木壬陶岁罪水冬朝。",
        "敌人追来期限将到否则会被抓金日夜丁结凤珠重育方虞宾臣地壬庚驹裳迩李地鸣冬道云淡为周金地戊玉王坐草归生在赖丁白光爱盈。",
    ]
    return "\n\n".join(lines) + "\n"


def test_diagnostics_and_audit_blockers_not_in_failure_packet(external_io_token, monkeypatch, mini_project, tmp_path):
    seed = uuid.uuid4().hex[:8]
    run_id = f"L1-GAR-{seed}"
    chapter = tmp_path / "garbled.md"
    chapter.write_text(_garbled_chapter(seed), encoding="utf-8")
    out_dir = tmp_path / "l1-garbled"
    _, payload = _run_l1_entry(
        chapter_path=chapter,
        out_dir=out_dir,
        project_root=mini_project,
        run_id=run_id,
        monkeypatch=monkeypatch,
        semantic_overall="FAIL",
    )
    report, packet, audit = _read_artifacts(out_dir, run_id)
    assert all(item.get("decision_role") != "DIAGNOSTIC" for item in packet["items"])
    assert all(item.get("decision_role") != "AUDIT_BLOCKER" for item in packet["items"])
    assert payload["status"] == 机器初筛退回
    assert report["semantic_audit_status"] == "FAIL"


def test_garbled_heuristic_hits_still_rejected_by_semantic_fail(external_io_token, monkeypatch, mini_project, tmp_path):
    seed = uuid.uuid4().hex[:8]
    run_id = f"L1-GAR2-{seed}"
    chapter = tmp_path / "garbled2.md"
    chapter.write_text(_garbled_chapter(seed), encoding="utf-8")
    out_dir = tmp_path / run_id
    _, payload = _run_l1_entry(
        chapter_path=chapter,
        out_dir=out_dir,
        project_root=mini_project,
        run_id=run_id,
        monkeypatch=monkeypatch,
        semantic_overall="FAIL",
        skip_guard=True,
    )
    assert payload["status"] == 机器初筛退回
    report, _, _ = _read_artifacts(out_dir, run_id)
    assert report["semantic_audit_status"] == "FAIL"


def test_split_failure_packet_excludes_audit_blockers():
    item_guard = 检测项("L1-00", "字数", "失败", "", [], "error", "字数不足", decision_role="HARD_GUARD", blocking=True)
    item_audit = 检测项(
        "L1-SEM",
        "语义审计服务",
        "失败",
        "",
        [],
        "error",
        "语义审计不可用",
        decision_role="AUDIT_BLOCKER",
        blocking=True,
        reason_type=理由_API不可用,
    )
    gate = 闸门结果("L1-00", "x", [], [], [], "否", [], "L1-00", "x", [item_guard, item_audit])
    split = 分拆阻断项([gate])
    assert split.失败包 == [item_guard]
    assert split.审计阻断项 == [item_audit]
    assert 生成失败包([gate]) == [item_guard]


def test_semantic_api_failure_tags_audit_blocker():
    seed = uuid.uuid4().hex[:8]
    context = make_semantic_context(sample_chapter_text(seed))
    result = 审计(context, client=create_client("L1", api_key=""))
    assert not result.可用
    assert result.检测项列表[0].decision_role == "AUDIT_BLOCKER"


def test_aggregate_semantic_fail_rejects():
    semantic = 语义审计结果(
        检测项列表=[
            检测项(
                "L1-SEM",
                "语义审计·因果",
                "失败",
                "不足",
                [],
                "error",
                "语义审计-因果不足",
                decision_role="CONTENT_DECISION",
                blocking=True,
            )
        ],
        可用=True,
        整体结论="FAIL",
    )
    final = 聚合终态(semantic, semantic.检测项列表, [])
    assert final.status == 机器初筛退回
    assert final.semantic_audit_status == "FAIL"


def test_all_terminal_status_reports_validate(external_io_token, monkeypatch, mini_project, tmp_path):
    cases = [
        ("PASS", True, "k", 机器初筛通过),
        ("REVIEW", True, "k", 需要人工复核),
        ("FAIL", True, "k", 机器初筛退回),
        ("PASS", True, "", 审计阻断),
    ]
    for idx, (overall, skip_guard, api_key, expected_status) in enumerate(cases):
        seed = uuid.uuid4().hex[:8]
        run_id = f"L1-SCH-{idx}-{seed}"
        chapter = tmp_path / f"{seed}.md"
        chapter.write_text(_padded_chapter(seed), encoding="utf-8")
        out_dir = tmp_path / run_id
        _, payload = _run_l1_entry(
            chapter_path=chapter,
            out_dir=out_dir,
            project_root=mini_project,
            run_id=run_id,
            monkeypatch=monkeypatch,
            semantic_overall=overall,
            skip_guard=skip_guard,
            api_key=api_key,
        )
        assert payload["status"] == expected_status
        report, packet, audit = _read_artifacts(out_dir, run_id)
        assert report["validation_status"] == "VALIDATED"
        assert packet["schema_version"] == "xcue.failure-packet/1.0"
        assert audit["schema_version"] == "xcue.audit-blockers/1.0"


def test_l1_entry_writes_only_to_out_dir(external_io_token, monkeypatch, mini_project, tmp_path):
    seed = uuid.uuid4().hex[:8]
    run_id = f"L1-ISO-{seed}"
    chapter = tmp_path / f"{seed}.md"
    chapter.write_text(_padded_chapter(seed), encoding="utf-8")
    out_dir = tmp_path / "l1-isolated"
    before = {p for p in (ROOT / "运行记录").rglob("*") if p.is_file()} if (ROOT / "运行记录").exists() else set()
    _run_l1_entry(
        chapter_path=chapter,
        out_dir=out_dir,
        project_root=mini_project,
        run_id=run_id,
        monkeypatch=monkeypatch,
        semantic_overall="PASS",
        skip_guard=True,
    )
    after = {p for p in (ROOT / "运行记录").rglob("*") if p.is_file()} if (ROOT / "运行记录").exists() else set()
    assert before == after
    assert list(out_dir.glob("*.json"))
