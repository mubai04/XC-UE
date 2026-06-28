from __future__ import annotations

import json
from pathlib import Path

import pytest

from L2模型 import 失败输入, 证据
from 一致性上下文 import 构造一致性上下文
from 双来源校验 import 校验双来源
from 事实模型 import 一致性诊断结果
from tests.conftest import l2_06_v2_payload, repo_root


def _item(quote: str) -> 失败输入:
    return 失败输入(
        来源闸门="L1-01",
        名称="一致性",
        状态="失败",
        说明="R4C wiring",
        证据=[证据(1, quote)],
        严重级别="error",
        失败类型="技术护栏失败",
        候选模块="L2-06",
        回流验收位置="L1-01",
        修复方向="统一事实",
    )


def _setup_ir(base: Path) -> tuple[Path, Path]:
    ir_dir = base / "IR"
    ir_dir.mkdir()
    (ir_dir / "IR-08_状态快照.md").write_text("角色甲双臂健全。", encoding="utf-8")
    chapter = base / "ch.md"
    chapter.write_text("角色甲的左臂无法动弹。", encoding="utf-8")
    return chapter, ir_dir


def test_l2_06_prior_chapter_resolved_from_manifest(tmp_path):
    harness = tmp_path / "harness"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    ch00 = chapters / "ch00.md"
    ch01 = chapters / "ch01.md"
    ch00.write_text("前章：甲在河东。", encoding="utf-8")
    ch01.write_text("本章：甲已到河西。", encoding="utf-8")
    manifest = {
        "schema_version": "xcue.project-manifest/1.0",
        "chapter_sequence": ["chapters/ch00.md", "chapters/ch01.md"],
    }
    (harness / "project.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    from 前序章节 import 解析前序章节

    priors = 解析前序章节(ch01)
    assert len(priors) == 1
    assert priors[0].resolve() == ch00.resolve()

    ctx = 构造一致性上下文(ch01, _item("河西"), prior_chapters=priors)
    assert ctx.前序章节事实, "构造一致性上下文应加载前序章节事实"
    prior_quotes = [getattr(f, "quote", f.摘句) for f in ctx.前序章节事实]
    assert any("河东" in q for q in prior_quotes)


def test_l2_06_entry_passes_prior_chapters(tmp_path, monkeypatch, repo_root):
    harness = tmp_path / "entry"
    chapters = harness / "chapters"
    chapters.mkdir(parents=True)
    ch00 = chapters / "ch00.md"
    ch01 = chapters / "ch01.md"
    ch00.write_text("前章事实。", encoding="utf-8")
    ch01.write_text("本章事实。", encoding="utf-8")
    (harness / "project.json").write_text(
        json.dumps({"chapter_sequence": ["chapters/ch00.md", "chapters/ch01.md"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    captured: dict = {}

    def _capture_construct(chapter_path, item, **kwargs):
        captured.update(kwargs)
        return 构造一致性上下文(chapter_path, item, **kwargs)

    def _fake_compare(ctx, item, **kwargs):
        return (
            {
                "root_cause": "reroute",
                "consistency_conflicts": [
                    {
                        "conflict_type": "事实",
                        "entity": "甲",
                        "attribute": "位置",
                        "source_a": {"paragraph": 1, "quote": "前章事实。", "source_type": "前序章节"},
                        "source_b": {"paragraph": 1, "quote": "本章事实。", "source_type": "正文"},
                        "classification": "ALLOWED_CHANGE",
                    }
                ],
                "fix_actions": ["说明变化"],
                "acceptance_criteria": ["可解释"],
                "evidence_quotes": [{"paragraph": 1, "quote": "本章事实。"}],
                "needs_reroute": False,
            },
            一致性诊断结果("变化", []),
        )

    monkeypatch.setattr("一致性能力入口.构造一致性上下文", _capture_construct)
    monkeypatch.setattr("一致性能力入口.执行冲突比对", _fake_compare)
    monkeypatch.setattr("一致性能力入口.校验通用证据引用", lambda parsed, corpus: ([], []))

    from 一致性能力入口 import 安全生成修复单
    from 能力规则加载 import 加载能力规则

    rules = 加载能力规则(repo_root / "00_工程总控" / "工程执行层" / "L2工程" / "ability_rules.json").能力规则["L2-06"]
    form, err = 安全生成修复单(_item("本章"), rules, chapter_path=ch01, repo_root=repo_root)
    assert captured.get("prior_chapters") is not None, "正式入口必须把 prior_chapters 传入构造一致性上下文"
    assert len(captured["prior_chapters"]) >= 1
    assert form or err


def test_l2_06_source_type_must_match_indexed_source(tmp_path):
    chapter, ir_dir = _setup_ir(tmp_path)
    ctx = 构造一致性上下文(chapter, _item("左臂"), ir_dir=ir_dir)
    if not ctx.indexed_fact_pairs:
        pytest.skip("未生成事实对")
    parsed = l2_06_v2_payload(ctx, swap_ids=True)
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("x", []))
    assert errors
    assert any("不匹配" in e for e in errors)


def test_l2_06_evidence_insufficient_classification(tmp_path):
    chapter = tmp_path / "solo.md"
    chapter.write_text("只有一句孤立陈述。", encoding="utf-8")
    ctx = 构造一致性上下文(chapter, _item("孤立"))
    parsed = l2_06_v2_payload(
        ctx,
        classification="EVIDENCE_INSUFFICIENT",
        reason="缺少IR来源对照",
    )
    errors = 校验双来源(parsed, ctx.正文语料, ctx, 一致性诊断结果("x", []))
    assert not errors
