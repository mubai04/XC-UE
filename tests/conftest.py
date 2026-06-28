from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"
PUBLIC = EXEC / "公共组件"
L1 = EXEC / "L1工程"
L2 = EXEC / "L2工程"
L3 = EXEC / "L3工程"
L15 = EXEC / "L1.5工程"
RUNLIB = PUBLIC / "跨层契约运行库"

for path in (EXEC, PUBLIC, L1, L2, L3, L15, RUNLIB):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

try:
    from L2路径注册 import 注册L2子路径

    注册L2子路径()
except ImportError:
    pass


@pytest.fixture
def external_io_token(tmp_path, monkeypatch):
    token_file = tmp_path / "io.token"
    token_file.write_text("XCUE_TEST_EXTERNAL_IO_TOKEN_V1", encoding="utf-8")
    monkeypatch.setenv("XCUE_TEST_ALLOW_EXTERNAL_IO", "1")
    monkeypatch.setenv("XCUE_TEST_IO_TOKEN_FILE", str(token_file))
    return token_file


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def external_io_token(tmp_path, monkeypatch):
    token_file = tmp_path / "io.token"
    token_file.write_text("XCUE_TEST_EXTERNAL_IO_TOKEN_V1", encoding="utf-8")
    monkeypatch.setenv("XCUE_TEST_ALLOW_EXTERNAL_IO", "1")
    monkeypatch.setenv("XCUE_TEST_IO_TOKEN_FILE", str(token_file))
    return token_file


def make_mock_transport(response_body: dict, *, status: int = 200, finish_reason: str = "stop") -> callable:
    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        envelope = {
            "choices": [
                {
                    "message": {"content": json.dumps(response_body, ensure_ascii=False)},
                    "finish_reason": finish_reason,
                }
            ],
        }
        return status, json.dumps(envelope, ensure_ascii=False)

    return transport


def make_error_transport(*, status: int = 500, message: str = "server error") -> callable:
    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        return status, message

    return transport


def make_timeout_transport() -> callable:
    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        raise TimeoutError("timed out")

    return transport


def sample_chapter_text(seed: str) -> str:
    blocks = [
        f"段落一：{seed} 忽然察觉异常，因为规则正在收紧，门后传来不属于这一层的脚步声。",
        f"段落二：他必须做出选择，否则代价会落在所有人身上，而名单上的名字已经开始减少。",
        f"段落三：追兵逼近，冲突升级，真相尚未揭晓，旧日承诺像刀背一样压在他的肩胛。",
        f"段落四：读者收益在于局势反转，但认知成本来自多层设定，每条规则都绑定着不同的惩罚。",
        f"段落五：章末留下新问题——{seed} 到底看见了什么，而那个答案似乎早在多年前就被写进账册。",
        f"段落六：风从裂开的窗缝里灌进来，带着铁锈、雨和未燃尽的符纸，提醒他时间不多。",
        f"段落七：同伴想退，他却知道一旦退后，整条因果链都会断在昨夜那个未被记录的决定上。",
        f"段落八：远处钟声敲响，意味着审查即将开始，而他还没有准备好面对真正的提问者。",
    ]
    return f"# 测试章节 {seed}\n\n" + "\n\n".join(blocks) + "\n"


def find_chapter_evidence(text: str, needle: str) -> tuple[str, str]:
    from 正文切分 import 切段, 清理正文

    _, body = 清理正文(text)
    paragraphs = 切段(body)
    for paragraph in paragraphs:
        if needle in paragraph.文本:
            return paragraph.段落ID, needle
    first = paragraphs[0]
    excerpt = first.文本[: min(20, len(first.文本))]
    return first.段落ID, excerpt


def last_twenty_percent_evidence(text: str) -> tuple[str, str]:
    from 正文切分 import 切段, 清理正文

    _, body = 清理正文(text)
    paragraphs = 切段(body)
    start_idx = max(0, int(len(paragraphs) * 0.8))
    paragraph = paragraphs[min(start_idx, len(paragraphs) - 1)]
    paragraph_id = paragraph.段落ID or f"P{paragraph.编号:04d}"
    excerpt = paragraph.文本[: min(24, len(paragraph.文本))]
    return paragraph_id, excerpt


def dimension_semantic_fields(name: str, verdict: str) -> dict[str, str]:
    analysis_summary = (
        f"优点：全章{name}主线可追踪；风险：中段存在轻微重复但尚未持续破坏理解；"
        f"最终选择{verdict}因为正反权衡后该维度仍符合标尺。"
    )
    strength_summary = f"全章{name}层面存在清晰的事件增量与有效承接。"
    risk_summary = (
        "未发现足以降级的全章性风险"
        if verdict == "PASS"
        else f"全章存在与{name}相关的重复或信息增量下降风险。"
    )
    if name == "因果" and verdict == "PASS":
        final_reason = "起因：异常被察觉；行动：人物做出选择；结果：冲突升级并留下悬念，故判PASS。"
    else:
        final_reason = (
            f"比较正反依据，全章在{name}维度存在"
            f"{'重复与章末承接' if verdict != 'PASS' else '事件增量与章末承接'}"
            f"现象，故判{verdict}。"
        )
    return {
        "analysis_summary": analysis_summary,
        "strength_summary": strength_summary,
        "risk_summary": risk_summary,
        "final_reason": final_reason,
    }


def semantic_audit_payload(
    quote: str,
    *,
    paragraph_id: str = "P0001",
    target_overall: str = "REVIEW",
    source_scope: str = "CURRENT_CHAPTER",
    chapter_text: str | None = None,
) -> dict:
    dims = ("因果", "动机", "冲突", "读者收益", "认知成本", "章末追读")
    ending_paragraph_id = paragraph_id
    ending_quote = quote
    if chapter_text:
        ending_paragraph_id, ending_quote = last_twenty_percent_evidence(chapter_text)

    dimensions = []
    for name in dims:
        if target_overall == "PASS":
            verdict = "PASS"
        elif target_overall == "FAIL":
            verdict = "FAIL"
        else:
            verdict = "REVIEW" if name != "因果" else "PASS"
        if name == "章末追读":
            dim_paragraph_id = ending_paragraph_id
            dim_quote = ending_quote
            dim_scope = "CURRENT_CHAPTER"
        else:
            dim_paragraph_id = paragraph_id
            dim_quote = quote
            dim_scope = source_scope
        fields = dimension_semantic_fields(name, verdict)
        dimensions.append(
            {
                "name": name,
                "verdict": verdict,
                **fields,
                "evidence": [
                    {
                        "paragraph_id": dim_paragraph_id,
                        "exact_text": dim_quote,
                        "source_scope": dim_scope,
                        "occurrence_index": 0,
                        "evidence_rationale": (
                            f"该摘句作为{name}维度的代表性锚点，支持 strength_summary 中的主线描述，"
                            "不等同于单条摘句证明整章。"
                        ),
                    }
                ],
            }
        )
    return {"dimensions": dimensions}


def l2_06_v2_payload(
    ctx,
    *,
    classification: str = "HARD_CONFLICT",
    pair_index: int = 0,
    swap_ids: bool = False,
    reason: str = "测试冲突",
    repair_direction: str = "对齐事实",
    source_a_fact_id: str | None = None,
    source_b_fact_id: str | None = None,
    fact_pair_id: str | None = None,
) -> dict:
    from 事实索引 import CONSISTENCY_RESPONSE_SCHEMA

    if not ctx.indexed_fact_pairs and classification != "EVIDENCE_INSUFFICIENT":
        raise AssertionError("缺少 indexed_fact_pairs")
    if classification == "EVIDENCE_INSUFFICIENT":
        fact_id = source_a_fact_id or next(iter(ctx.索引事实表), "")
        return {
            "response_schema_version": CONSISTENCY_RESPONSE_SCHEMA,
            "root_cause": "证据不足",
            "consistency_conflicts": [
                {
                    "source_a_fact_id": fact_id,
                    "classification": "EVIDENCE_INSUFFICIENT",
                    "reason": reason,
                }
            ],
            "fix_actions": ["补证据"],
            "acceptance_criteria": ["双来源"],
            "evidence_quotes": [],
            "needs_reroute": False,
        }
    pair = ctx.indexed_fact_pairs[pair_index]
    sa = source_a_fact_id or pair["source_a_fact_id"]
    sb = source_b_fact_id or pair["source_b_fact_id"]
    if swap_ids:
        sa, sb = sb, sa
    fa = ctx.索引事实表[sa]
    return {
        "response_schema_version": CONSISTENCY_RESPONSE_SCHEMA,
        "root_cause": "事实状态冲突",
        "consistency_conflicts": [
            {
                "fact_pair_id": fact_pair_id or pair["fact_pair_id"],
                "source_a_fact_id": sa,
                "source_b_fact_id": sb,
                "classification": classification,
                "reason": reason,
                "repair_direction": repair_direction,
            }
        ],
        "fix_actions": ["统一事实"],
        "acceptance_criteria": ["无冲突"],
        "evidence_quotes": [{"paragraph": fa.段落 or 1, "quote": fa.摘句}],
        "needs_reroute": False,
    }


def l2_04_v2_payload(
    ctx,
    *,
    problem_type: str = "RULE_DOES_NOT_PRESS_CHOICE",
    wrong_source_type: str | None = None,
    bad_evidence_id: str | None = None,
) -> dict:
    from 证据索引 import (
        ROLE_CHAPTER_ACTION,
        ROLE_CHAPTER_META,
        SETTING_RESPONSE_SCHEMA,
        SOURCE_CHAPTER,
        SOURCE_IR,
        SOURCE_PROJECT_RULE,
    )

    rule_ids = [
        eid
        for eid, e in ctx.证据表.items()
        if e.source_type in (SOURCE_PROJECT_RULE, SOURCE_IR)
    ]
    action_ids = [
        eid
        for eid, e in ctx.证据表.items()
        if e.source_type == SOURCE_CHAPTER and e.source_role in (ROLE_CHAPTER_ACTION, ROLE_CHAPTER_META)
    ]
    if not rule_ids or not action_ids:
        raise AssertionError("缺少规则或章节行为证据索引")
    rule_id = rule_ids[0]
    action_id = action_ids[0]
    if bad_evidence_id:
        rule_id = bad_evidence_id
    pressure_ids = [rule_id, action_id]
    if wrong_source_type == SOURCE_CHAPTER and rule_id in ctx.证据表:
        pressure_ids = [action_id, action_id]
    ev_quote = action_id
    return {
        "response_schema_version": SETTING_RESPONSE_SCHEMA,
        "root_cause": "设定未逼迫当下选择",
        "setting_pressure_points": [
            {
                "setting": "木牌规则",
                "problem_type": problem_type,
                "evidence_ids": pressure_ids,
                "analysis": "规则存在但章节未迫使人物承担取舍",
                "repair_direction": "迫使角色在保留记忆与取牌之间作出选择",
            }
        ],
        "differentiation_points": [
            {
                "description": "代价仅停留在设定层",
                "contrast_with_convention": "常规会在现场激活代价",
                "evidence_ids": [action_id],
            }
        ],
        "sustainable_variants": [
            {
                "variant": "记忆代价反复兑现",
                "repeatable_mechanism": "每次触及阈限即流失记忆",
                "evidence_ids": [rule_id],
            }
        ],
        "fix_actions": ["在取牌时描写记忆流失"],
        "acceptance_criteria": ["读者感知选择压力"],
        "evidence_quotes": [{"evidence_id": ev_quote}],
        "needs_reroute": False,
    }


def make_semantic_context(text: str):
    from L1_语义上下文 import CONTEXT_NONE, 语义上下文
    from 正文切分 import 切段, 清理正文

    title, body = 清理正文(text)
    paragraphs = 切段(body)
    return 语义上下文(
        context_quality=CONTEXT_NONE,
        current_title=title,
        current_paragraphs=paragraphs,
        current_body=body,
    )


def failure_packet_item(
    gate: str,
    failure_type: str,
    *,
    routeable: bool = True,
    blocking: bool = False,
    decision_role: str = "DIAGNOSTIC",
    source_component: str | None = None,
    severity: str = "error",
    quote: str = "测试摘句",
) -> dict:
    return {
        "闸门": gate,
        "名称": "测试项",
        "状态": "失败",
        "说明": f"测试 {failure_type}",
        "证据": [{"段落": 1, "摘句": quote}],
        "严重级别": severity,
        "失败类型": failure_type,
        "候选模块": "",
        "回流验收位置": gate,
        "修复方向": "测试修复方向",
        "decision_role": decision_role,
        "blocking": blocking,
        "routeable": routeable,
        "route_reason": "为L1.5提供领域路由线索" if routeable else "",
        "source_component": source_component or gate,
        "reason_type": "",
    }


def failure_packet_payload(
    chapter_path: str | Path,
    items: list[dict],
    *,
    status: str = "SCREENING_REJECT",
    pipeline_run_id: str = "TEST-PIPE",
    stage_run_id: str = "TEST-STAGE",
) -> dict:
    blocking_count = sum(1 for item in items if item.get("blocking"))
    routeable_count = sum(1 for item in items if item.get("routeable"))
    return {
        "schema_version": "xcue.failure-packet/1.0",
        "pipeline_run_id": pipeline_run_id,
        "stage_run_id": stage_run_id,
        "status": status,
        "failure_count": len(items),
        "blocking_count": blocking_count,
        "routeable_count": routeable_count,
        "items": items,
        "extensions": {"chapter_path": str(chapter_path), "publish_authority": False},
    }
