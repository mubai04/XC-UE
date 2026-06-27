from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
from 文风上下文 import 构造文风上下文
from 文风修复规划 import 规划文风修复
from 文风模型 import 文风诊断结果, 文风问题
from 文风证据校验 import 校验文风响应
from 文风能力入口 import 安全生成修复单
from 能力规则加载 import 加载能力规则
from tests.conftest import make_mock_transport, repo_root, sample_chapter_text


def _item(seed: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01", 名称="t", 状态="失败", 说明=f"{seed} 文风",
        证据=[证据(1, quote)], 严重级别="error", 失败类型="文风失败",
        候选模块="L2-02", 回流验收位置="L1-01", 修复方向="压缩解释腔",
    )


def _rules(root: Path):
    return 加载能力规则(root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json").能力规则["L2-02"]


def test_l2_02_context_extracts_repeats_and_sentences(tmp_path, repo_root):
    seed = uuid.uuid4().hex[:8]
    text = f"段落一：{seed} 规则正在收紧，规则正在收紧。\n\n段落二：因为所以这意味着实际上显然很长的一句解释腔堆叠。"
    path = tmp_path / "ch.md"
    path.write_text(text, encoding="utf-8")
    ctx = 构造文风上下文(path, _item(seed, "规则正在收紧"))
    assert len(ctx.段落列表) >= 2
    assert ctx.句长分布
    assert any(r.短语 == "规则正在收紧" for r in ctx.重复短语候选)
    assert ctx.句式信号 or ctx.连续解释段候选


def test_l2_02_validator_rejects_vague_constraint(tmp_path, repo_root):
    seed = "v"
    path = tmp_path / "c.md"
    path.write_text(sample_chapter_text(seed), encoding="utf-8")
    ctx = 构造文风上下文(path, _item(seed, "忽然察觉异常"))
    parsed = {
        "root_cause": "解释腔",
        "style_issues": [{"issue_type": "解释腔", "paragraph": 1, "quote": "忽然察觉异常", "constraint": "优化语言"}],
        "fix_actions": ["优化语言"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": "忽然察觉异常"}],
    }
    diag = 文风诊断结果("解释腔", [文风问题("解释腔", 1, 1, "忽然察觉异常", "优化语言")])
    errors = 校验文风响应(parsed, ctx.正文语料, diag)
    assert any("空泛" in e for e in errors)


def test_l2_02_repair_plan_has_location_and_scope():
    diag = 文风诊断结果(
        "重复",
        [文风问题("重复", 2, 1, "规则正在收紧", "合并重复短语")],
    )
    plan = 规划文风修复(diag, {"forbid_modify_scope": "事件顺序、人物目标、世界规则"})
    assert plan["fix_actions"]
    assert plan["forbid_modify_scope"]
    assert plan["style_actions"][0]["位置"].startswith("段落")


def test_l2_02_mock_integration_produces_fix_form(tmp_path, repo_root):
    seed = uuid.uuid4().hex[:8]
    quote = "忽然察觉异常，因为规则正在收紧"
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text(seed), encoding="utf-8")
    payload = {
        "root_cause": "解释腔堆叠",
        "style_issues": [{"issue_type": "解释腔", "paragraph": 1, "quote": quote, "constraint": "删除旁白解释"}],
        "fix_actions": ["压缩解释句"],
        "acceptance_criteria": ["语气更自然"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "forbid_modify_scope": "事件顺序、人物目标",
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item(seed, quote), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form and not err
    assert form.接收模块 == "L2-02"


def test_l2_02_rejects_fictional_quote(tmp_path, repo_root):
    seed = uuid.uuid4().hex[:8]
    path = tmp_path / "ch.md"
    path.write_text(sample_chapter_text(seed), encoding="utf-8")
    payload = {
        "root_cause": "解释腔",
        "style_issues": [{"issue_type": "解释腔", "paragraph": 1, "quote": "不存在", "constraint": "删旁白"}],
        "fix_actions": ["删"],
        "acceptance_criteria": ["好"],
        "evidence_quotes": [{"paragraph": 1, "quote": "不存在"}],
        "forbid_modify_scope": "事件顺序",
        "needs_reroute": False,
    }
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item(seed, "x"), _rules(repo_root), chapter_path=path, repo_root=repo_root, client=client)
    assert form is None and err and "EVIDENCE_INVALID" in err
