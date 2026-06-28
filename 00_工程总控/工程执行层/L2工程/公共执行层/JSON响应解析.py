from __future__ import annotations

from typing import Any

from 通用错误 import 能力诊断错误


def 提取JSON字典(result: Any) -> dict[str, Any]:
    if not getattr(result, "ok", False) or not getattr(result, "parsed", None):
        kind = getattr(result, "error_kind", None) or "API_ERROR"
        msg = getattr(result, "error", None) or "API 失败"
        if kind in {"API_UNAVAILABLE", "API_KEY_MISSING"}:
            raise 能力诊断错误(msg, kind=kind)
        raise 能力诊断错误(msg, kind=kind)
    parsed = result.parsed
    if not isinstance(parsed, dict):
        raise 能力诊断错误("模型响应不是 JSON 对象", kind="INVALID_JSON")
    return parsed
