from __future__ import annotations

import uuid
from pathlib import Path

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
from L2_01_叙事结构能力 import 安全生成修复单
from L2_01_证据校验 import 校验诊断响应
from L2_99_接口判断 import 判断
from 修复单生成 import 生成
from 能力规则加载 import 加载能力规则
from tests.conftest import make_mock_transport, repo_root


def _chapter_file(base: Path, seed: str) -> tuple[Path, str]:
    quote = f"{seed} 只有一句无关内容"
    path = base / f"{seed}.md"
    path.write_text(f"# 短章\n\n{quote}。\n", encoding="utf-8")
    return path, f"{quote}。"


def _failure_item(seed: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="有序叙事信号",
        状态="失败",
        说明=f"{seed} 结构链断",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型="叙事失败",
        候选模块="L2-01",
        回流验收位置="L1-01",
        修复方向="压缩主行动线",
    )


def _diagnosis_payload(
    quote: str,
    *,
    root_cause: str | None = None,
    indices: list[int] | None = None,
) -> dict:
    cause = root_cause or "叙事链信号不足，需压缩为单一主行动线"
    return {
        "root_cause": cause,
        "root_cause_evidence_indices": indices if indices is not None else [0],
        "fix_actions": ["只保留一条主行动线", "合并冗余段落"],
        "acceptance_criteria": ["读者能判断当前最重要问题只有一个"],
        "evidence_quotes": [{"paragraph": 1, "quote": quote}],
        "needs_reroute": False,
    }


def _validate(quote: str, payload: dict, item: 失败输入) -> tuple[bool, list[str]]:
    corpus = f"# 短章\n\n{quote}\n"
    _validated, errors = 校验诊断响应(
        payload,
        corpus,
        failure_type=item.失败类型,
        description=item.说明,
        repair_direction=item.修复方向,
    )
    return not errors, errors


def test_l2_01_diagnosis_generates_fix_form_with_evidence(repo_root, tmp_path):
    seed = uuid.uuid4().hex[:8]
    chapter, quote = _chapter_file(tmp_path, seed)
    item = _failure_item(seed, quote)
    rules = 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json")
    ability = rules.能力规则["L2-01"]
    client = create_client("L2", api_key="k", transport=make_mock_transport(_diagnosis_payload(quote)))
    form, err = 安全生成修复单(
        item,
        ability,
        chapter_path=chapter,
        repo_root=repo_root,
        client=client,
    )
    assert form is not None
    assert err is None
    assert form.诊断证据
    assert form.诊断证据[0].摘句 == quote
    assert "主行动线" in form.修复动作


def test_l2_01_summary_root_cause_with_indices_passes(repo_root, tmp_path):
    seed = uuid.uuid4().hex[:8]
    chapter, quote = _chapter_file(tmp_path, seed)
    item = _failure_item(seed, quote)
    payload = _diagnosis_payload(quote, root_cause="叙事链断裂，需压缩为单一主行动线", indices=[0])
    ok, errors = _validate(quote, payload, item)
    assert ok
    assert not errors


def test_l2_01_fictional_evidence_blocks_form(repo_root, tmp_path):
    seed = uuid.uuid4().hex[:8]
    chapter, quote = _chapter_file(tmp_path, seed)
    rules = 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json")
    ability = rules.能力规则["L2-01"]
    client = create_client("L2", api_key="k", transport=make_mock_transport(_diagnosis_payload("完全不存在的虚构摘句")))
    form, err = 安全生成修复单(
        _failure_item(seed, quote),
        ability,
        chapter_path=chapter,
        repo_root=repo_root,
        client=client,
    )
    assert form is None
    assert err and "EVIDENCE_INVALID" in err


def test_l2_01_out_of_range_index_blocks(repo_root, tmp_path):
    seed = uuid.uuid4().hex[:8]
    _, quote = _chapter_file(tmp_path, seed)
    item = _failure_item(seed, quote)
    payload = _diagnosis_payload(quote, indices=[1])
    ok, errors = _validate(quote, payload, item)
    assert not ok
    assert any("越界" in e for e in errors)


def test_l2_01_empty_indices_blocks(repo_root, tmp_path):
    seed = uuid.uuid4().hex[:8]
    _, quote = _chapter_file(tmp_path, seed)
    item = _failure_item(seed, quote)
    payload = _diagnosis_payload(quote, indices=[])
    ok, errors = _validate(quote, payload, item)
    assert not ok
    assert any("root_cause_evidence_indices" in e for e in errors)


def test_l2_01_root_cause_copies_failure_type_blocks(repo_root, tmp_path):
    seed = uuid.uuid4().hex[:8]
    _, quote = _chapter_file(tmp_path, seed)
    item = _failure_item(seed, quote)
    payload = _diagnosis_payload(quote, root_cause="叙事失败", indices=[0])
    ok, errors = _validate(quote, payload, item)
    assert not ok
    assert any("failure_type" in e for e in errors)


def test_l2_01_api_failure_no_fallback_keeps_batch(repo_root, tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    seed = uuid.uuid4().hex[:8]
    chapter, quote = _chapter_file(tmp_path, seed)
    rules = 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json")
    e_quote = quote
    items = [
        _failure_item(seed, quote),
        失败输入(
            来源闸门="L1-02",
            名称="E 即时情绪反馈",
            状态="失败",
            说明=f"{seed} E低",
            证据=[证据(2, e_quote)],
            严重级别="error",
            失败类型="E低：即时情绪反馈弱",
            候选模块="L2-05",
            回流验收位置="L1-02",
            修复方向="增强即时刺激",
        ),
    ]
    judgements = [判断(item, rules) for item in items]

    def factory(stage, **kwargs):
        if stage == "L2":
            return create_client(
                "L2",
                api_key="k",
                transport=make_mock_transport(
                    {
                        "root_cause": "即时收益弱",
                        "experience_risks": [
                            {"risk_type": "弃读", "location_quote": e_quote, "modification_target": "前置冲突"}
                        ],
                        "fix_actions": ["前置冲突"],
                        "acceptance_criteria": ["首段有收益"],
                        "evidence_quotes": [{"paragraph": 2, "quote": e_quote}],
                        "root_cause_evidence_indices": [0],
                        "needs_reroute": False,
                    }
                ),
            )
        raise AssertionError(stage)

    monkeypatch.setattr("DeepSeek客户端.create_client", factory)
    monkeypatch.setattr("模型调用.create_client", factory)

    forms, errors = 生成(
        items,
        judgements,
        rules,
        chapter_path=str(chapter),
        repo_root=repo_root,
    )
    assert len(forms) == 1
    assert forms[0].接收模块 == "L2-05"
    assert any("L2-01" in e for e in errors)
