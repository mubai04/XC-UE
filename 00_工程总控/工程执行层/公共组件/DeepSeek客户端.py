from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Stage = Literal["L1", "L2", "L3"]

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_TIMEOUT = 60.0

STAGE_MODEL_ENV: dict[str, tuple[str, str]] = {
    "L1": ("XCUE_L1_MODEL", "deepseek-v4-flash"),
    "L2": ("XCUE_L2_MODEL", "deepseek-v4-pro"),
    "L3": ("XCUE_L3_MODEL", "deepseek-v4-pro"),
}

FAIL_FINISH_REASONS = frozenset({"length", "content_filter", "tool_calls", "insufficient_system_resource"})


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


def _resolve_model(stage: str, model: str | None) -> str:
    env_key, default = STAGE_MODEL_ENV[stage]
    resolved = (model if model is not None else os.environ.get(env_key, default)).strip()
    if not resolved:
        raise ValueError(f"{stage} 缺少模型配置：{env_key}")
    return resolved


def _stage_payload_options(stage: str) -> dict[str, Any]:
    if stage == "L1":
        return {"thinking": {"type": "disabled"}}
    return {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}


def create_client(
    stage: Stage,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    transport: ChatTransport | None = None,
) -> "DeepSeekClient":
    normalized = stage.upper()
    if normalized not in STAGE_MODEL_ENV:
        raise ValueError(f"未知 stage：{stage}，必须是 L1 / L2 / L3")
    return DeepSeekClient(
        stage=normalized,
        model=_resolve_model(normalized, model),
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        transport=transport,
    )


class DeepSeekClient:
    def __init__(
        self,
        *,
        stage: str,
        model: str,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        transport: ChatTransport | None = None,
    ) -> None:
        normalized = stage.upper()
        if normalized not in STAGE_MODEL_ENV:
            raise ValueError(f"未知 stage：{stage}，必须是 L1 / L2 / L3")
        if not model or not str(model).strip():
            raise ValueError("必须显式提供 stage 对应模型，不得使用共享默认模型")
        self._stage = normalized
        self._api_key = (api_key if api_key is not None else _api_key_from_env()).strip()
        self._base_url = base_url.rstrip("/")
        self._model = str(model).strip()
        self._timeout = timeout
        self._transport = transport or _default_transport

    @property
    def stage(self) -> str:
        return self._stage

    @property
    def model(self) -> str:
        return self._model

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> DeepSeekResult:
        if not self._api_key:
            return DeepSeekResult(ok=False, error="缺少 DEEPSEEK_API_KEY", error_kind="MISSING_API_KEY")
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            **_stage_payload_options(self._stage),
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
            return DeepSeekResult(ok=False, error=str(exc), error_kind="TIMEOUT", meta={"stage": self._stage})
        except OSError as exc:
            return DeepSeekResult(ok=False, error=str(exc), error_kind="NETWORK_ERROR", meta={"stage": self._stage})

        if status < 200 or status >= 300:
            return DeepSeekResult(
                ok=False,
                error=raw or f"HTTP {status}",
                error_kind="HTTP_ERROR",
                status_code=status,
                raw=raw,
                meta={"stage": self._stage},
            )

        try:
            envelope = json.loads(raw)
            choice = envelope["choices"][0]
            content = choice["message"]["content"]
            finish_reason = str(choice.get("finish_reason", "")).strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            return DeepSeekResult(ok=False, error=str(exc), error_kind="INVALID_ENVELOPE", raw=raw, meta={"stage": self._stage})

        if finish_reason != "stop":
            kind = finish_reason.upper() if finish_reason in FAIL_FINISH_REASONS else "FINISH_REASON_REJECTED"
            return DeepSeekResult(
                ok=False,
                error=f"finish_reason={finish_reason}",
                error_kind=kind if finish_reason in FAIL_FINISH_REASONS else "FINISH_REASON_REJECTED",
                raw=raw,
                meta={"stage": self._stage, "finish_reason": finish_reason},
            )

        if not isinstance(content, str) or not content.strip():
            return DeepSeekResult(ok=False, error="空响应内容", error_kind="EMPTY_RESPONSE", raw=raw, meta={"stage": self._stage})

        return DeepSeekResult(ok=True, content=content.strip(), raw=raw, meta={"stage": self._stage, "finish_reason": "stop"})

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
                meta=result.meta,
            )
        if not isinstance(parsed, dict):
            return DeepSeekResult(
                ok=False,
                error="JSON 根节点必须是对象",
                error_kind="INVALID_JSON",
                content=result.content,
                raw=result.raw,
                meta=result.meta,
            )
        result.parsed = parsed
        return result
