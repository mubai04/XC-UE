from __future__ import annotations

import re
from pathlib import Path

from 通用证据定位 import 切分段落


def 读取章节正文(chapter_path: Path, *, repo_root: Path | None = None) -> tuple[str, list[str], Path]:
    resolved = chapter_path.resolve() if chapter_path.is_absolute() else (
        (repo_root / chapter_path).resolve() if repo_root else chapter_path.resolve()
    )
    raw = resolved.read_text(encoding="utf-8")
    body = raw.split("\n", 1)[-1] if raw.startswith("#") else raw
    return body, 切分段落(body), resolved
