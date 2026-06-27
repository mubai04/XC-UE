from __future__ import annotations

import uuid
from pathlib import Path

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
from 体验修复规划 import 规划体验修复
from 体验模型 import 体验诊断结果, 弃读风险
from 体验证据校验 import 校验体验响应
from 市场能力入口 import 安全生成修复单
from 阅读阶段上下文 import 构造阅读阶段上下文
from 能力规则加载 import 加载能力规则
from tests.conftest import make_mock_transport, repo_root, sample_chapter_text


def _item(seed: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-02", 名称="t", 状态="失败", 说明=f"{seed}",
        证据=[证据(1, quote)], 严重级别="error", 失败类型="E低：即时情绪反馈弱",
        候选模块="L2-05", 回流验收位置="L1-02", 修复方向="前置冲突",
    )


def _rules(root: Path):
    return 加载能力规则(root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json").能力规则["L2-05"]


def test_l2_05_context_splits_reading_stages(tmp_path):
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text("m"), encoding="utf-8")
    ctx = 构造阅读阶段上下文(path, _item("m", "x"))
    assert len(ctx.阅读阶段表) >= 2
    names = {s.名称 for s in ctx.阅读阶段表}
    assert "开头" in names or "前段" in names


def test_l2_05_validator_rejects_screening_echo(tmp_path):
    path = tmp_path / "c.md"
    path.write_text(sample_chapter_text("s"), encoding="utf-8")
    ctx = 构造阅读阶段上下文(path, _item("s", "忽然察觉异常"))
    parsed = {
        "root_cause": "SCREENING_REJECT",
        "experience_risks": [{"risk_type": "弃读", "location_quote": "忽然察觉异常", "modification_target": "首段加强冲突"}],
        "fix_actions": ["改"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": "忽然察觉异常"}],
    }
    diag = 体验诊断结果("x", [弃读风险("弃读", "忽然察觉异常", "首段加强冲突")], ctx.阅读阶段表)
    errors = 校验体验响应(parsed, ctx.正文语料, diag)
    assert any("L1" in e for e in errors)


def test_l2_05_repair_plan_targets_reader_effect():
    diag = 体验诊断结果("弱", [弃读风险("弃读", "忽然察觉异常", "首段冲突前置")])
    plan = 规划体验修复(diag, {})
    assert "首段冲突前置" in plan["fix_actions"][0]


def test_l2_05_mock_integration(tmp_path, repo_root):
    quote = "忽然察觉异常，因为规则正在收紧"
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text("k"), encoding="utf-8")
    payload = {
        "root_cause": "入口收益不足",
        "experience_risks": [{"risk_type": "弃读", "location_quote": quote, "modification_target": "首段冲突前置"}],
        "fix_actions": ["前置冲突"],
        "acceptance_criteria": ["首段有收益"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item("k", quote), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form and form.接收模块 == "L2-05"


def test_l2_05_rejects_vague_hook_action(tmp_path, repo_root):
    quote = "忽然察觉异常，因为规则正在收紧"
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text("h"), encoding="utf-8")
    payload = {
        "root_cause": "入口弱",
        "experience_risks": [{"risk_type": "弃读", "location_quote": quote, "modification_target": "加强钩子让读者继续"}],
        "fix_actions": ["加强钩子"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item("h", quote), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form is None and "EVIDENCE_INVALID" in (err or "")
