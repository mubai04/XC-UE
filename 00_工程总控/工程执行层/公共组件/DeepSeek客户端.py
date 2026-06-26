from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 60.0


class ChatTransport(Protocol):
    def __call__(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]: ...


@dataclass
class DeepSeekResult:
    ok: bool
    content: str = ""
    parsed: dict[str, Any] | None = None
    error: str = ""
    error_kind: str = ""
    status_code: int | None = None
    raw: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def _default_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise TimeoutError(str(exc.reason)) from exc


def _api_key_from_env() -> str:
    return os.environ.get("DEEPSEEK_API_KEY", "").strip()


class DeepSeekClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
        transport: ChatTransport | None = None,
    ) -> None:
        self._api_key = (api_key if api_key is not None else _api_key_from_env()).strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport or _default_transport

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> DeepSeekResult:
        if not self._api_key:
            return DeepSeekResult(ok=False, error="缺少 DEEPSEEK_API_KEY", error_kind="MISSING_API_KEY")
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        url = f"{self._base_url}/chat/completions"
        try:
            status, raw = self._transport(url, headers, body, self._timeout)
        except TimeoutError as exc:
            return DeepSeekResult(ok=False, error=str(exc), error_kind="TIMEOUT")
        except OSError as exc:
            return DeepSeekResult(ok=False, error=str(exc), error_kind="NETWORK_ERROR")

        if status < 200 or status >= 300:
            return DeepSeekResult(
                ok=False,
                error=raw or f"HTTP {status}",
                error_kind="HTTP_ERROR",
                status_code=status,
                raw=raw,
            )

        try:
            envelope = json.loads(raw)
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            return DeepSeekResult(ok=False, error=str(exc), error_kind="INVALID_ENVELOPE", raw=raw)

        if not isinstance(content, str) or not content.strip():
            return DeepSeekResult(ok=False, error="空响应内容", error_kind="EMPTY_RESPONSE", raw=raw)

        return DeepSeekResult(ok=True, content=content.strip(), raw=raw)

    def chat_json(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> DeepSeekResult:
        result = self.chat(messages, temperature=temperature)
        if not result.ok:
            return result
        try:
            parsed = json.loads(result.content)
        except json.JSONDecodeError as exc:
            return DeepSeekResult(
                ok=False,
                error=str(exc),
                error_kind="INVALID_JSON",
                content=result.content,
                raw=result.raw,
            )
        if not isinstance(parsed, dict):
            return DeepSeekResult(
                ok=False,
                error="JSON 根节点必须是对象",
                error_kind="INVALID_JSON",
                content=result.content,
                raw=result.raw,
            )
        result.parsed = parsed
        return result


def default_client() -> DeepSeekClient:
    return DeepSeekClient()
