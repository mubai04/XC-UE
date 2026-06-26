from __future__ import annotations

import json
import sys
from pathlib import Path

from L2模型 import 失败输入, 证据
from 能力标准解析 import 失败规则, 能力规则

L1工程 = Path(__file__).resolve().parents[1] / "L1工程"
if str(L1工程) not in sys.path:
    sys.path.insert(0, str(L1工程))

from 正文切分 import 切段, 清理正文

CONTEXT_WINDOW = 1


def _resolve_chapter(chapter_path: Path, repo_root: Path | None) -> Path:
    if chapter_path.is_absolute():
        return chapter_path.resolve()
    if repo_root is not None:
        return (repo_root / chapter_path).resolve()
    return chapter_path.resolve()


def 构建诊断语料(
    chapter_path: Path,
    item: 失败输入,
    *,
    repo_root: Path | None = None,
) -> tuple[str, dict[str, object]]:
    resolved = _resolve_chapter(chapter_path, repo_root)
    if not resolved.exists():
        raise FileNotFoundError(f"章节正文不存在：{resolved}")
    raw = resolved.read_text(encoding="utf-8-sig")
    title, body = 清理正文(raw)
    paragraphs = 切段(body)
    if not paragraphs:
        raise ValueError(f"章节正文无有效段落：{resolved}")
    para_map = {p.编号: p.文本 for p in paragraphs}

    focus = {e.段落 for e in item.证据 if isinstance(e.段落, int) and e.段落 in para_map}
    if not focus:
        focus = {paragraphs[0].编号}

    included: set[int] = set()
    for number in focus:
        for offset in range(-CONTEXT_WINDOW, CONTEXT_WINDOW + 1):
            candidate = number + offset
            if candidate in para_map:
                included.add(candidate)

    context_paragraphs = [{"paragraph": number, "text": para_map[number]} for number in sorted(included)]
    item_quotes = [e.摘句 for e in item.证据 if e.摘句]
    corpus_parts = [body, *item_quotes]
    corpus = "\n".join(part for part in corpus_parts if part)

    context = {
        "chapter_path": str(resolved),
        "title": title,
        "paragraphs": context_paragraphs,
    }
    return corpus, context


def 失败证据条目(item: 失败输入) -> list[dict[str, object]]:
    return [{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句]


def 能力规则摘要(rules: 能力规则, matched: 失败规则 | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "module": rules.模块,
        "scope_keywords": rules.输入关键词,
        "output_product": rules.输出产物,
        "forbidden_inputs": rules.禁止项,
        "default_returns": rules.默认回流,
    }
    if matched:
        payload["matched_failure_rule"] = {
            "id": matched.编号,
            "name": matched.名称,
            "definition": matched.定义,
            "signals": matched.表现,
            "repair_rules": matched.修复规则,
            "acceptance": matched.验收标准,
        }
    return payload


def 诊断输入摘要(
    item: 失败输入,
    rules: 能力规则,
    matched: 失败规则 | None,
    chapter_path: Path,
    *,
    repo_root: Path | None = None,
) -> tuple[str, dict[str, object]]:
    corpus, chapter_context = 构建诊断语料(chapter_path, item, repo_root=repo_root)
    payload = {
        "failure_type": item.失败类型,
        "description": item.说明,
        "repair_direction": item.修复方向,
        "failure_evidence": 失败证据条目(item),
        "chapter_context": chapter_context,
        "ability_rules": 能力规则摘要(rules, matched),
        "forbidden_modifications": rules.禁止项,
    }
    return corpus, payload


def 格式化诊断输入(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
