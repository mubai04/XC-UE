from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
import L2_02_文风语言能力 as m02
import L2_03_角色心理能力 as m03
import L2_04_创意设定能力 as m04
import L2_05_市场体验能力 as m05
import L2_06_系统一致性能力 as m06
from 能力注册表 import ABILITY_REGISTRY, 获取能力入口
from 能力规则加载 import 加载能力规则
from tests.conftest import make_mock_transport, sample_chapter_text, repo_root


def _chapter(base: Path, seed: str) -> tuple[Path, str]:
    text = sample_chapter_text(seed)
    path = base / f"{seed}.md"
    path.write_text(text, encoding="utf-8")
    quote = "忽然察觉异常，因为规则正在收紧"
    return path, quote


def _item(seed: str, failure_type: str, module: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="测试",
        状态="失败",
        说明=f"{seed} 说明",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型=failure_type,
        候选模块=module,
        回流验收位置="L1-01",
        修复方向="测试修复",
    )


def _rules(repo_root: Path):
    return 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json")


def test_registry_resolves_all_five_modules():
    for mid in ("L2-02", "L2-03", "L2-04", "L2-05", "L2-06"):
        assert 获取能力入口(mid) is ABILITY_REGISTRY[mid]


def test_compat_wrappers_not_identical_functions():
    assert m02.安全生成修复单 is not m03.安全生成修复单
    assert m04.安全生成修复单 is not m05.安全生成修复单


def test_l2_02_registry_integration(repo_root, tmp_path):
    seed = uuid.uuid4().hex[:8]
    chapter, quote = _chapter(tmp_path, seed)
    rules = _rules(repo_root).能力规则["L2-02"]
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
    gen = 获取能力入口("L2-02")
    form, err = gen(_item(seed, "文风失败", "L2-02", quote), rules, chapter_path=chapter, repo_root=repo_root, client=client)
    assert form and not err
