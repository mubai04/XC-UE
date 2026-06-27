from __future__ import annotations

from typing import Any

from DeepSeek客户端 import DeepSeekClient, create_client


def 调用模型JSON(
    messages: list[dict[str, str]],
    *,
    client: DeepSeekClient | None = None,
    stage: str = "L2",
) -> Any:
    api = client or create_client(stage)
    return api.chat_json(messages)
