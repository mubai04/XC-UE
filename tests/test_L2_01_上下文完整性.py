from __future__ import annotations

import uuid
from pathlib import Path

from L2_01_诊断上下文 import 构建上下文完整性记录, 构建诊断语料, 检查failure_evidence输入
from L2模型 import 失败输入, 证据
from L2_01_叙事结构能力 import 安全生成修复单
from 能力规则加载 import 加载能力规则


def _item(quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="ctx",
        状态="失败",
        说明="上下文测试",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型="章节结构弱",
        候选模块="L2-01",
        回流验收位置="L1-01",
        修复方向="仅语言润色",
    )


def test_l2_01_full_chapter_coverage_ratio_one(tmp_path, repo_root):
    seed = uuid.uuid4().hex[:8]
    body = "\n\n".join(f"段落{i}：{seed} 内容{i}。" for i in range(1, 9))
    path = tmp_path / "full.md"
    path.write_text(body, encoding="utf-8")
    item = _item(f"{seed} 内容1")
    record = 构建上下文完整性记录(path, item)
    assert record["coverage_ratio"] == 1.0
    assert record["truncated"] is False
    assert record["chapter_paragraph_count"] == record["context_paragraph_count"]


def test_l2_01_truncated_context_detected(tmp_path):
    path = tmp_path / "ch.md"
    path.write_text("段落一：甲。\n\n段落二：乙。\n\n段落三：丙。", encoding="utf-8")
    item = _item("甲")
    incomplete = {
        "chapter_path": str(path),
        "chapter_char_count": 20,
        "chapter_paragraph_count": 3,
        "context_char_count": 5,
        "context_paragraph_count": 1,
        "coverage_ratio": 0.25,
        "truncated": True,
        "failure_evidence_present": True,
        "input_evidence_status": "OK",
        "input_evidence_mismatches": [],
    }
    assert incomplete["truncated"] is True
    assert incomplete["coverage_ratio"] < 1.0


def test_l2_01_failure_evidence_mismatch_detected(tmp_path):
    path = tmp_path / "ch.md"
    path.write_text("纪渊仍把药箱抱紧。", encoding="utf-8")
    item = _item("纪渊把药箱递过去")
    corpus, _ = 构建诊断语料(path, item)
    status = 检查failure_evidence输入(item, corpus)
    assert status["status"] == "MISMATCH"


def test_l2_01_mismatch_returns_reroute_without_api(tmp_path, repo_root):
    path = tmp_path / "ch.md"
    path.write_text("纪渊仍把药箱抱紧。", encoding="utf-8")
    item = _item("纪渊把药箱递过去")
    rules = 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json")
    form, err = 安全生成修复单(
        item,
        rules.能力规则["L2-01"],
        chapter_path=path,
        repo_root=repo_root,
        client=None,
    )
    assert form is not None
    assert err is None
    assert form.是否需要回L15重路由 == "是"
    assert "INPUT_EVIDENCE_MISMATCH" in form.次失败类型 or "证据错位" in form.输入问题
