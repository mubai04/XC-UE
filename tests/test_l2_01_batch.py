from __future__ import annotations

import uuid

from DeepSeek客户端 import DeepSeekClient
from L2模型 import 失败输入, 证据
from L2_01_叙事结构能力 import 安全生成修复单
from L2_99_接口判断 import 判断
from 修复单生成 import 生成
from 能力规则加载 import 加载能力规则
from tests.conftest import make_mock_transport, repo_root


def _failure_item(seed: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="有序叙事信号",
        状态="失败",
        说明=f"{seed} 结构链断",
        证据=[证据(1, seed)],
        严重级别="error",
        失败类型="叙事失败",
        候选模块="L2-01",
        回流验收位置="L1-01",
        修复方向="压缩主行动线",
    )


def test_l2_01_diagnosis_generates_fix_form(repo_root):
    seed = uuid.uuid4().hex[:8]
    rules = 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json")
    ability = rules.能力规则["L2-01"]
    payload = {
        "root_cause": f"{seed} 多路径未剪枝",
        "fix_actions": ["只保留一条主行动线", "删除并行支线"],
        "acceptance_criteria": ["读者能判断当前最重要问题只有一个"],
        "needs_reroute": False,
    }
    client = DeepSeekClient(api_key="k", transport=make_mock_transport(payload))
    form, warn = 安全生成修复单(_failure_item(seed), ability, client=client)
    assert form is not None
    assert "主行动线" in form.修复动作
    assert warn is None


def test_l2_01_api_failure_falls_back_without_clearing_batch(repo_root):
    seed = uuid.uuid4().hex[:8]
    rules = 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json")
    items = [
        _failure_item(seed),
        失败输入(
            来源闸门="L1-02",
            名称="E 即时情绪反馈",
            状态="失败",
            说明=f"{seed} E低",
            证据=[证据(2, seed)],
            严重级别="error",
            失败类型="E低：即时情绪反馈弱",
            候选模块="L2-05",
            回流验收位置="L1-02",
            修复方向="增强即时刺激",
        ),
    ]
    judgements = [判断(item, rules) for item in items]
    forms, errors = 生成(items, judgements, rules)
    assert len(forms) == 2
    assert len(errors) >= 0
