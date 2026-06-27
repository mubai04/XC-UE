from __future__ import annotations

from pathlib import Path
from typing import Protocol

from DeepSeek客户端 import DeepSeekClient
from L2模型 import 失败输入, 修复单
from 能力标准解析 import 能力规则


class 能力入口协议(Protocol):
    module_id: str

    def 安全生成修复单(
        self,
        item: 失败输入,
        rules: 能力规则,
        *,
        chapter_path: Path | None = None,
        repo_root: Path | None = None,
        client: DeepSeekClient | None = None,
    ) -> tuple[修复单 | None, str | None]: ...
