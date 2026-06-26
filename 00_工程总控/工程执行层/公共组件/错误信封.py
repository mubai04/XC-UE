from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from 工程异常 import 工程错误
from 退出码 import ExitCode


错误码 = {
    ExitCode.INPUT_INVALID: "INPUT_INVALID",
    ExitCode.SCHEMA_INVALID: "INPUT_SCHEMA_INVALID",
    ExitCode.LINEAGE_ERROR: "INPUT_LINEAGE_INVALID",
    ExitCode.NO_PRODUCTION_RULESET: "NO_PRODUCTION_RULESET",
    ExitCode.RULE_PARSE_FAILED: "RULE_PARSE_FAILED",
    ExitCode.PRODUCTION_MODE_NOT_ELIGIBLE: "PRODUCTION_MODE_NOT_ELIGIBLE",
    ExitCode.PROJECT_ERROR: "PROJECT_ERROR",
    ExitCode.BLOCKED: "STAGE_BLOCKED",
    ExitCode.INTERNAL_ERROR: "INTERNAL_ERROR",
}



def 错误信封(
    exc: 工程错误,
    *,
    stage: str,
    run_id: str = "",
    path: str | Path = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code = 错误码.get(exc.exit_code, "INTERNAL_ERROR")
    message = str(exc)
    payload_details = {**(getattr(exc, "details", {}) or {}), **(details or {})}
    if exc.exit_code == ExitCode.PROJECT_ERROR and isinstance(payload_details.get("reason"), str):
        code = payload_details["reason"]
    envelope = {
        "ok": False,
        "error_code": code,
        "message": message,
        "stage": stage,
        "error": {
            "code": code,
            "message": message,
            "stage": stage,
            "run_id": run_id,
            "path": str(path) if path else "",
            "details": payload_details,
            "retryable": False,
        },
        "exit_code": int(exc.exit_code),
    }
    for key in [
        "rule_source",
        "reason",
        "location",
        "detail",
        "requested_mode",
        "effective_mode",
        "eligible",
        "entrypoint",
    ]:
        if key in payload_details:
            envelope[key] = payload_details[key]
    return envelope


def 打印错误信封(
    exc: 工程错误,
    *,
    stage: str,
    run_id: str = "",
    path: str | Path = "",
    details: dict[str, Any] | None = None,
) -> None:
    import sys

    print(
        json.dumps(
            错误信封(exc, stage=stage, run_id=run_id, path=path, details=details),
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
