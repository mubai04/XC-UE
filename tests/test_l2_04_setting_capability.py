from __future__ import annotations

import uuid
from pathlib import Path

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
from 设定上下文 import 构造设定上下文
from 设定修复规划 import 规划设定修复
from 设定模型 import 角色选择压力, 设定诊断结果
from 设定证据校验 import 校验设定响应
from 设定能力入口 import 安全生成修复单
from 能力规则加载 import 加载能力规则
from tests.conftest import make_mock_transport, repo_root, sample_chapter_text


def _item(seed: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01", 名称="t", 状态="失败", 说明=f"{seed}",
        证据=[证据(1, quote)], 严重级别="error", 失败类型="创意设定失败",
        候选模块="L2-04", 回流验收位置="L1-01", 修复方向="加压",
    )


def _rules(root: Path):
    return 加载能力规则(root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json").能力规则["L2-04"]


def test_l2_04_context_separates_text_and_ir_facts(tmp_path):
    seed = uuid.uuid4().hex[:8]
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text(seed), encoding="utf-8")
    ctx = 构造设定上下文(path, _item(seed, "规则"))
    assert ctx.正文事实
    assert isinstance(ctx.IR事实, list)
    assert isinstance(ctx.尚无证据, list)


def test_l2_04_validator_rejects_consistency_claim(tmp_path):
    path = tmp_path / "c.md"
    path.write_text("每条规则都绑定着不同的惩罚。", encoding="utf-8")
    ctx = 构造设定上下文(path, _item("s", "规则"))
    parsed = {
        "root_cause": "设定",
        "setting_pressure_points": [{"rule_or_setting": "规则", "quote": "每条规则都绑定着不同的惩罚", "choice_pressure": "迫使角色选择隐瞒"}],
        "sustainable_variant": "变体A：审查升级",
        "fix_actions": ["压"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": "每条规则都绑定着不同的惩罚"}],
        "consistency_conflicts": [],
    }
    parsed_bad = {**parsed, "root_cause": "一致性冲突 hard冲突 source_a"}
    diag = 设定诊断结果("x", [角色选择压力("规则", "每条规则都绑定着不同的惩罚", "迫使角色选择隐瞒")])
    errors = 校验设定响应(parsed_bad, ctx.正文语料, diag)
    assert any("L2-06" in e for e in errors)


def test_l2_04_repair_plan_pressure_specific():
    diag = 设定诊断结果("弱", [角色选择压力("审查规则", "规则正在收紧", "迫使角色选择隐瞒")])
    plan = 规划设定修复(diag, {})
    assert "隐瞒" in plan["fix_actions"][0]


def test_l2_04_mock_integration(tmp_path, repo_root):
    quote = "忽然察觉异常，因为规则正在收紧"
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text("s"), encoding="utf-8")
    payload = {
        "root_cause": "规则压力不足",
        "setting_pressure_points": [{"rule_or_setting": "审查规则", "quote": quote, "choice_pressure": "迫使角色选择隐瞒"}],
        "sustainable_variant": "变体：审查随机抽查",
        "fix_actions": ["加压"],
        "acceptance_criteria": ["设定推动选择"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item("s", quote), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form and form.接收模块 == "L2-04"


def test_l2_04_rejects_fake_quote(tmp_path, repo_root):
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text("x"), encoding="utf-8")
    payload = {
        "root_cause": "设定",
        "setting_pressure_points": [{"rule_or_setting": "规则", "quote": "杜撰", "choice_pressure": "迫使角色放弃安全"}],
        "sustainable_variant": "变体A",
        "fix_actions": ["压"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": "杜撰"}],
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item("x", "q"), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form is None and "EVIDENCE_INVALID" in (err or "")
