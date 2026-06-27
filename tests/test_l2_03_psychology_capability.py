from __future__ import annotations

import uuid
from pathlib import Path

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
from 角色上下文 import 构造角色上下文
from 角色修复规划 import 规划角色修复
from 角色模型 import 动机缺口, 角色诊断结果
from 角色证据校验 import 校验角色响应
from 角色能力入口 import 安全生成修复单
from 能力规则加载 import 加载能力规则
from tests.conftest import make_mock_transport, repo_root, sample_chapter_text


def _item(seed: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01", 名称="t", 状态="失败", 说明=f"{seed}",
        证据=[证据(1, quote)], 严重级别="error", 失败类型="角色失败",
        候选模块="L2-03", 回流验收位置="L1-01", 修复方向="补动机",
    )


def _rules(root: Path):
    return 加载能力规则(root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json").能力规则["L2-03"]


def test_l2_03_context_builds_goal_stimulus_chain(tmp_path):
    seed = uuid.uuid4().hex[:8]
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text(seed), encoding="utf-8")
    ctx = 构造角色上下文(path, _item(seed, "忽然察觉异常"))
    assert ctx.目标刺激行为链
    assert ctx.行为表
    assert ctx.识别角色


def test_l2_03_validator_rejects_vague_missing_link(tmp_path):
    path = tmp_path / "c.md"
    path.write_text("他必须做出选择，否则代价会落在所有人身上。", encoding="utf-8")
    ctx = 构造角色上下文(path, _item("s", "他必须做出选择"))
    parsed = {
        "root_cause": "动机",
        "motivation_gaps": [{"character": "主角", "behavior_quote": "他必须做出选择", "missing_link": "增强人物"}],
        "fix_actions": ["增强人物"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": "他必须做出选择"}],
    }
    diag = 角色诊断结果("x", [动机缺口("主角", "他必须做出选择", "增强人物")], ctx.目标刺激行为链)
    errors = 校验角色响应(parsed, ctx.正文语料, ctx, diag)
    assert errors


def test_l2_03_repair_plan_links_missing_link():
    diag = 角色诊断结果("断裂", [动机缺口("主角", "他必须做出选择", "缺恐惧来源")])
    plan = 规划角色修复(diag, {})
    assert "缺恐惧来源" in plan["fix_actions"][0]


def test_l2_03_mock_integration(tmp_path, repo_root):
    seed = uuid.uuid4().hex[:8]
    quote = "忽然察觉异常，因为规则正在收紧"
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text(seed), encoding="utf-8")
    payload = {
        "root_cause": "行为与目标断裂",
        "motivation_gaps": [{"character": "主角", "behavior_quote": quote, "missing_link": "未交代恐惧来源"}],
        "fix_actions": ["补动机"],
        "acceptance_criteria": ["可理解"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item(seed, quote), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form and form.接收模块 == "L2-03"


def test_l2_03_forbidden_scope_blocks_enhance_character(tmp_path, repo_root):
    quote = "忽然察觉异常，因为规则正在收紧"
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text("f"), encoding="utf-8")
    payload = {
        "root_cause": "增强人物",
        "motivation_gaps": [{"character": "主角", "behavior_quote": quote, "missing_link": "缺链"}],
        "fix_actions": ["增强人物"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item("f", quote), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form is None and "FORBIDDEN_SCOPE" in (err or "")
