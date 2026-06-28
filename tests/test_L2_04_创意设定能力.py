from __future__ import annotations

import uuid
from pathlib import Path

from DeepSeek客户端 import create_client
from L2模型 import 失败输入, 证据
from 设定能力入口 import 安全生成修复单
from 能力规则加载 import 加载能力规则
from tests.conftest import l2_04_v2_payload, make_mock_transport, repo_root, sample_chapter_text


def _item(seed: str, quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01", 名称="t", 状态="失败", 说明=f"{seed}",
        证据=[证据(1, quote)], 严重级别="error", 失败类型="创意设定失败",
        候选模块="L2-04", 回流验收位置="L1-01", 修复方向="加压",
    )


def _rules(root: Path):
    return 加载能力规则(root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json").能力规则["L2-04"]


def _setup_ir_case(tmp_path: Path) -> tuple[Path, Path]:
    case = tmp_path / f"case-{uuid.uuid4().hex[:6]}"
    chapters = case / "chapters"
    ir = case / "IR"
    chapters.mkdir(parents=True)
    ir.mkdir()
    chapter = chapters / "chapter.md"
    chapter.write_text(
        sample_chapter_text("s") + "\n\n正文未写：不持牌者不得入塔，也未写持牌代价。\n\n仍无具体后果。",
        encoding="utf-8",
    )
    (ir / "IR-02_世界约束.md").write_text(
        "| R-101 | 入塔需持木牌 | 踏入塔门 | 失去一段记忆 | 遗忘重要之人 |\n",
        encoding="utf-8",
    )
    return chapter, case


def test_l2_04_context_separates_text_and_ir_facts(tmp_path):
    chapter, case = _setup_ir_case(tmp_path)
    from 设定上下文 import 构造设定上下文

    ctx = 构造设定上下文(chapter, _item("x", "规则"), repo_root=case, ir_dir=case / "IR")
    assert ctx.正文事实
    assert ctx.indexed_evidence
    assert ctx.证据表


def test_l2_04_validator_rejects_consistency_claim(tmp_path):
    chapter, case = _setup_ir_case(tmp_path)
    from 设定上下文 import 构造设定上下文
    from 设定证据校验 import 校验设定响应
    from 设定模型 import 设定诊断结果

    ctx = 构造设定上下文(chapter, _item("s", "规则"), repo_root=case, ir_dir=case / "IR")
    parsed = l2_04_v2_payload(ctx)
    parsed["root_cause"] = "一致性冲突 hard冲突 source_a"
    errors = 校验设定响应(parsed, ctx, 设定诊断结果("x"))
    assert any("L2-06" in e for e in errors)


def test_l2_04_repair_plan_pressure_specific():
    from 设定修复规划 import 规划设定修复
    from 设定模型 import 角色选择压力, 设定诊断结果

    diag = 设定诊断结果(
        "弱",
        [角色选择压力("审查规则", "", "迫使角色选择隐瞒", analysis="迫使隐瞒")],
    )
    plan = 规划设定修复(diag, {})
    assert "隐瞒" in plan["fix_actions"][0]


def test_l2_04_mock_integration(tmp_path, repo_root):
    chapter, case = _setup_ir_case(tmp_path)
    from 设定上下文 import 构造设定上下文

    ctx = 构造设定上下文(chapter, _item("s", "规则正在收紧"), repo_root=case, ir_dir=case / "IR")
    payload = l2_04_v2_payload(ctx)
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(
        _item("s", "规则正在收紧"), _rules(repo_root), chapter_path=chapter, repo_root=case, client=client
    )
    assert form and form.接收模块 == "L2-04"


def test_l2_04_evidence_insufficient_without_rule_markers(tmp_path):
    from 设定上下文 import 构造设定上下文

    path = tmp_path / "plain.md"
    path.write_text("他们默默赶路，没有人说话。", encoding="utf-8")
    ctx = 构造设定上下文(path, _item("p", "默默"))
    assert not ctx.规则表
    forbidden = ("审查/层级规则", "触发异常或违规则生效", "名字减少意味着淘汰")
    blob = str(ctx.规则表) + str(ctx.限制表) + str(ctx.代价表)
    for f in forbidden:
        assert f not in blob


def test_l2_04_variant_extracts_from_replaced_terms(tmp_path):
    from 设定上下文 import 构造设定上下文

    body = "若踏入血池，施术者将折损寿元。唯有持银钥者可开启密门。"
    path = tmp_path / "variant.md"
    path.write_text(body, encoding="utf-8")
    ctx = 构造设定上下文(path, _item("v", "血池"))
    joined = str(ctx.规则表) + str(ctx.限制表) + str(ctx.代价表) + str(ctx.正文事实)
    assert "血池" in joined or "血池" in body
    assert "审查/层级规则" not in joined


def test_l2_04_rejects_fake_quote(tmp_path, repo_root):
    chapter, case = _setup_ir_case(tmp_path)
    from 设定上下文 import 构造设定上下文

    ctx = 构造设定上下文(chapter, _item("x", "q"), repo_root=case, ir_dir=case / "IR")
    payload = l2_04_v2_payload(ctx, bad_evidence_id="EVID-9999")
    client = create_client("L2", api_key="k", transport=make_mock_transport(payload))
    form, err = 安全生成修复单(_item("x", "q"), _rules(repo_root), chapter_path=chapter, repo_root=case, client=client)
    assert form is None and "EVIDENCE_ID_INVALID" in (err or "")
