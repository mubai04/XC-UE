from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from DeepSeek客户端 import DeepSeekClient, create_client
from L3模型 import L3执行任务
from 原子写入 import 原子写文本


@dataclass
class 候选生成结果:
    ok: bool
    path: Path | None = None
    error: str = ""
    error_kind: str = ""
    word_count: int = 0


def _候选路径合法(target_rel: str) -> bool:
    normalized = target_rel.replace("\\", "/")
    if "_candidates" not in normalized:
        return False
    if re.search(r"chapters/ch\d+\.md$", normalized):
        return False
    return True


def _构建生成提示(task: L3执行任务, ir_texts: list[str], source_chapter: str) -> list[dict[str, str]]:
    schema = {"title": "章节标题", "body": "候选正文 Markdown 正文（不含元数据）"}
    return [
        {
            "role": "system",
            "content": (
                "你是小说正文修复执行器。只输出 JSON。"
                "必须基于 IR 约束与修复方向生成新正文。"
                "禁止复制输入大段原文凑字数。"
                "禁止重复段落或循环固定句。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"任务类型：{task.任务类型}\n"
                f"输入问题：{task.输入材料}\n"
                f"修复方向：{task.修复方向}\n"
                f"修复产物要求：{task.修复产物要求}\n\n"
                f"IR 摘要：\n" + "\n".join(ir_texts[:6]) + "\n\n"
                f"参考正式章节（只读，不得整段复制）：\n{source_chapter[:4000]}\n\n"
                f"输出 JSON：\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]


def _重复检测(text: str) -> bool:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) >= 2 and len(set(paragraphs)) < len(paragraphs) * 0.85:
        return True
    sentences = re.split(r"[。！？!?]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]
    if len(sentences) >= 4 and len(set(sentences)) < len(sentences) * 0.75:
        return True
    return False


def _解析正文(parsed: dict) -> tuple[str, str]:
    title = str(parsed.get("title", "候选章节")).strip() or "候选章节"
    body = str(parsed.get("body", "")).strip()
    if not body:
        raise ValueError("body 为空")
    return title, body


def 生成候选正文(
    task: L3执行任务,
    harness_root: Path,
    repo_root: Path,
    *,
    client: DeepSeekClient | None = None,
    source_chapter_path: Path | None = None,
) -> 候选生成结果:
    target_rel = task.目标文件.replace("\\", "/")
    if not _候选路径合法(target_rel):
        return 候选生成结果(ok=False, error="目标路径不在 chapters/_candidates/", error_kind="PATH_FORBIDDEN")

    target = (repo_root / target_rel).resolve()
    try:
        target.relative_to((harness_root / "chapters" / "_candidates").resolve())
    except ValueError:
        return 候选生成结果(ok=False, error="目标路径越界", error_kind="PATH_ESCAPE")

    if target.exists():
        return 候选生成结果(ok=False, error="候选文件已存在，禁止覆盖", error_kind="ALREADY_EXISTS")

    ir_texts: list[str] = []
    for rel in task.IR输入:
        path = (repo_root / rel).resolve()
        if path.exists():
            ir_texts.append(path.read_text(encoding="utf-8")[:1500])

    source = ""
    if source_chapter_path and source_chapter_path.exists():
        source = source_chapter_path.read_text(encoding="utf-8")
    else:
        chapters_dir = harness_root / "chapters"
        for ch in sorted(chapters_dir.glob("ch*.md")):
            source = ch.read_text(encoding="utf-8")
            break

    api = client or create_client("L3")
    result = api.chat_json(_构建生成提示(task, ir_texts, source))
    if not result.ok or not result.parsed:
        return 候选生成结果(ok=False, error=result.error, error_kind=result.error_kind or "API_ERROR")

    try:
        title, body = _解析正文(result.parsed)
    except ValueError as exc:
        return 候选生成结果(ok=False, error=str(exc), error_kind="EMPTY_BODY")

    if _重复检测(body):
        return 候选生成结果(ok=False, error="候选正文重复度过高", error_kind="REPETITION")

    normalized_source = re.sub(r"\s+", "", source)
    normalized_body = re.sub(r"\s+", "", body)
    if source and len(normalized_body) > 100 and normalized_body in normalized_source:
        return 候选生成结果(ok=False, error="候选正文不得整段复制正式章节", error_kind="COPY_SOURCE")

    content = f"# {title}\n\n> L3 候选正文 · {task.执行编号}\n\n{body}\n"
    原子写文本(target, content)
    word_count = len(re.sub(r"[\s，。！？、“”‘’：；,.!?\"'（）()—\-…·#]", "", body))
    return 候选生成结果(ok=True, path=target, word_count=word_count)
