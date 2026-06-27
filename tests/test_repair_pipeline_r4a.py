from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from DeepSeek客户端 import create_client
from 修复流水线运行入口 import 执行修复流水线
from tests.conftest import ROOT, make_mock_transport, sample_chapter_text


def _setup_harness(workspace: Path, seed: str) -> Path:
    harness = workspace / f"harness-{seed}"
    (harness / "chapters" / "_candidates").mkdir(parents=True)
    (harness / "IR").mkdir(parents=True)
    (harness / "logs").mkdir(parents=True)
    for name in (
        "IR-00_项目索引.md",
        "IR-01_立项卡.md",
        "IR-02_世界约束.md",
        "IR-03_角色动机表.md",
        "IR-04_事件链.md",
        "IR-05_章节目标表.md",
        "IR-06_读者预期表.md",
        "IR-08_状态快照.md",
    ):
        (harness / "IR" / name).write_text(f"# {name}\n", encoding="utf-8")
    formal = harness / "chapters" / "ch01.md"
    formal.write_text(f"# 正式\n\n{seed} 正式正文不得修改。\n", encoding="utf-8")
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


def _packet(chapter: Path, seed: str, failure_type: str, module: str, pipeline_id: str) -> dict:
    text = chapter.read_text(encoding="utf-8")
    quote = "忽然察觉异常，因为规则正在收紧"
    return {
        "schema_version": "xcue.failure-packet/1.0",
        "pipeline_run_id": pipeline_id,
        "stage_run_id": f"{pipeline_id}-L1",
        "status": "SCREENING_REJECT",
        "failure_count": 1,
        "extensions": {"chapter_path": str(chapter)},
        "items": [
            {
                "闸门": "L1-01",
                "名称": "测试",
                "状态": "失败",
                "说明": f"{seed} 失败",
                "证据": [{"段落": 1, "摘句": quote}],
                "严重级别": "error",
                "失败类型": failure_type,
                "候选模块": module,
                "回流验收位置": "L1-01",
                "修复方向": "修复",
                "decision_role": "CONTENT_DECISION",
                "blocking": True,
            }
        ],
    }


def _style_payload(quote: str) -> dict:
    return {
        "root_cause": "解释腔堆叠",
        "style_issues": [{"issue_type": "解释腔", "paragraph": 1, "quote": quote, "constraint": "删旁白"}],
        "fix_actions": ["删旁白"],
        "acceptance_criteria": ["自然"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "forbid_modify_scope": "事件顺序、人物目标",
        "needs_reroute": False,
    }


def _psychology_payload(quote: str) -> dict:
    return {
        "root_cause": "动机断裂",
        "motivation_gaps": [{"character": "主角", "behavior_quote": quote, "missing_link": "缺恐惧来源"}],
        "fix_actions": ["补动机"],
        "acceptance_criteria": ["可理解"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "root_cause_evidence_indices": [0],
        "needs_reroute": False,
    }


@pytest.fixture
def pipeline_workspace(repo_root, external_io_token, tmp_path):
    seed = uuid.uuid4().hex[:8]
    workspace = repo_root / "运行记录" / f"pytest-pipeline-{seed}"
    workspace.mkdir(parents=True, exist_ok=True)
    chapter = workspace / "chapter.md"
    chapter.write_text(sample_chapter_text(seed), encoding="utf-8")
    harness = _setup_harness(workspace, seed)
    return workspace, seed, chapter, harness


def test_repair_pipeline_l2_02_to_candidate(pipeline_workspace, monkeypatch, repo_root):
    workspace, seed, chapter, harness = pipeline_workspace
    pipeline_id = f"R4A-PIPE-{seed}"
    packet_path = workspace / "packet.json"
    quote = "忽然察觉异常，因为规则正在收紧"
    packet_path.write_text(json.dumps(_packet(chapter, seed, "文风失败", "L2-02", pipeline_id), ensure_ascii=False, indent=2), encoding="utf-8")
    formal_before = (harness / "chapters" / "ch01.md").read_text(encoding="utf-8")

    def factory(stage, **kwargs):
        if stage == "L2":
            return create_client("L2", api_key="k", transport=make_mock_transport(_style_payload(quote)))
        if stage == "L3":
            return create_client("L3", api_key="k", transport=make_mock_transport({"title": "候选", "body": f"{seed} 候选正文"}))
        raise AssertionError(stage)

    monkeypatch.setattr("DeepSeek客户端.create_client", factory)
    monkeypatch.setattr("模型调用.create_client", factory)
    monkeypatch.setattr("候选正文生成.create_client", factory)

    code, summary = 执行修复流水线(
        failure_packet=packet_path,
        project_id=f"harness-{seed}",
        project_registry=None,
        run_id=f"R4A-PIPELINE-{seed}",
        pipeline_run_id=pipeline_id,
        workspace=workspace / "run",
        project_harness=harness,
    )
    assert code == 0
    assert summary["pipeline_run_id"] == pipeline_id
    assert summary["final_status"] == "COMPLETED"
    assert len(summary["stages"]) == 3
    l15 = json.loads(Path(summary["l15_report"]).read_text(encoding="utf-8"))
    assert l15["target_module"] == "L2-02"
    assert (harness / "chapters" / "ch01.md").read_text(encoding="utf-8") == formal_before
    candidates = list((harness / "chapters" / "_candidates").glob("*.md"))
    assert candidates


def test_repair_pipeline_stops_when_l15_blocks(pipeline_workspace, repo_root):
    workspace, seed, chapter, _harness = pipeline_workspace
    packet = _packet(chapter, seed, "文风失败", "L2-02", f"R4A-BLOCK-{seed}")
    packet["extensions"] = {}
    packet_path = workspace / "blocked.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    code, summary = 执行修复流水线(
        failure_packet=packet_path,
        project_id="TP-001",
        project_registry=None,
        run_id=f"R4A-BLOCK-{seed}",
        pipeline_run_id=f"R4A-BLOCK-{seed}",
        workspace=workspace / "blocked-run",
    )
    assert code != 0
    assert summary["final_status"] == "STOPPED_AT_L15"
    assert len(summary["stages"]) == 1


def test_repair_pipeline_l2_03_path(pipeline_workspace, monkeypatch, repo_root):
    workspace, seed, chapter, harness = pipeline_workspace
    pipeline_id = f"R4A-P03-{seed}"
    packet_path = workspace / "p03.json"
    quote = "忽然察觉异常，因为规则正在收紧"
    packet_path.write_text(json.dumps(_packet(chapter, seed, "角色失败", "L2-03", pipeline_id), ensure_ascii=False, indent=2), encoding="utf-8")

    def factory(stage, **kwargs):
        if stage == "L2":
            return create_client("L2", api_key="k", transport=make_mock_transport(_psychology_payload(quote)))
        if stage == "L3":
            return create_client("L3", api_key="k", transport=make_mock_transport({"title": "候选", "body": f"{seed} body"}))
        raise AssertionError(stage)

    monkeypatch.setattr("DeepSeek客户端.create_client", factory)
    monkeypatch.setattr("模型调用.create_client", factory)
    monkeypatch.setattr("候选正文生成.create_client", factory)

    code, summary = 执行修复流水线(
        failure_packet=packet_path,
        project_id=f"harness-{seed}",
        project_registry=None,
        run_id=f"R4A-P03-{seed}",
        pipeline_run_id=pipeline_id,
        workspace=workspace / "run03",
        project_harness=harness,
    )
    assert code == 0
    l15 = json.loads(Path(summary["l15_report"]).read_text(encoding="utf-8"))
    assert l15["target_module"] == "L2-03"


def _setting_payload(quote: str) -> dict:
    return {
        "root_cause": "规则压力不足",
        "setting_pressure_points": [{"rule_or_setting": "审查规则", "quote": quote, "choice_pressure": "迫使角色选择隐瞒"}],
        "sustainable_variant": "变体：审查抽查",
        "fix_actions": ["加压"],
        "acceptance_criteria": ["设定推动选择"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }


def _market_payload(quote: str) -> dict:
    return {
        "root_cause": "入口收益不足",
        "experience_risks": [{"risk_type": "弃读", "location_quote": quote, "modification_target": "首段冲突前置"}],
        "fix_actions": ["前置冲突"],
        "acceptance_criteria": ["首段有收益"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }


def _consistency_payload(quote: str, quote_b: str) -> dict:
    return {
        "root_cause": "事实状态冲突",
        "consistency_conflicts": [
            {
                "conflict_type": "事实",
                "entity": "空间层级",
                "attribute": "层级",
                "source_a": {"paragraph": 1, "quote": quote, "source_type": "正文"},
                "source_b": {"paragraph": 1, "quote": quote_b, "source_type": "正文"},
                "classification": "硬冲突",
            }
        ],
        "fix_actions": ["统一事实"],
        "acceptance_criteria": ["无冲突"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }


@pytest.mark.parametrize(
    "failure_type,module,payload_fn,run_suffix",
    [
        ("创意设定失败", "L2-04", lambda q: _setting_payload(q), "p04"),
        ("E低：即时情绪反馈弱", "L2-05", lambda q: _market_payload(q), "p05"),
        ("技术护栏失败", "L2-06", lambda q: _consistency_payload(q, "门后传来不属于这一层的脚步声"), "p06"),
    ],
)
def test_repair_pipeline_independent_module_paths(
    pipeline_workspace, monkeypatch, repo_root, failure_type, module, payload_fn, run_suffix
):
    workspace, seed, chapter, harness = pipeline_workspace
    pipeline_id = f"R4A-{run_suffix}-{seed}"
    packet_path = workspace / f"{run_suffix}.json"
    quote = "忽然察觉异常，因为规则正在收紧"
    packet_path.write_text(
        json.dumps(_packet(chapter, seed, failure_type, module, pipeline_id), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    formal_before = (harness / "chapters" / "ch01.md").read_text(encoding="utf-8")
    payload = payload_fn(quote)

    def factory(stage, **kwargs):
        if stage == "L2":
            return create_client("L2", api_key="k", transport=make_mock_transport(payload))
        if stage == "L3":
            return create_client("L3", api_key="k", transport=make_mock_transport({"title": "候选", "body": f"{seed} body"}))
        raise AssertionError(stage)

    monkeypatch.setattr("DeepSeek客户端.create_client", factory)
    monkeypatch.setattr("模型调用.create_client", factory)
    monkeypatch.setattr("候选正文生成.create_client", factory)

    code, summary = 执行修复流水线(
        failure_packet=packet_path,
        project_id=f"harness-{seed}",
        project_registry=None,
        run_id=f"R4A-{run_suffix.upper()}-{seed}",
        pipeline_run_id=pipeline_id,
        workspace=workspace / run_suffix,
        project_harness=harness,
    )
    assert code == 0
    l15 = json.loads(Path(summary["l15_report"]).read_text(encoding="utf-8"))
    assert l15["target_module"] == module
    assert (harness / "chapters" / "ch01.md").read_text(encoding="utf-8") == formal_before
    from 能力注册表 import 获取能力入口

    assert 获取能力入口(module) is not None
