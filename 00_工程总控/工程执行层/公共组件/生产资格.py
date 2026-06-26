from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from 工程异常 import 工程错误
from 标准加载器 import 候选试验模式, 生产模式
from 退出码 import ExitCode


生产资格错误码 = "PRODUCTION_MODE_NOT_ELIGIBLE"


@dataclass(frozen=True)
class 生产资格判定:
    requested_mode: str
    effective_mode: str | None
    eligible: bool
    reason: str
    rule_source: str
    entrypoint: str
    rules_status: str
    schema_version: str
    production_eligible: bool
    experimental_standard: bool
    project_identity: str

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "eligible": self.eligible,
            "reason": self.reason,
            "rule_source": self.rule_source,
            "entrypoint": self.entrypoint,
            "rules_status": self.rules_status,
            "schema_version": self.schema_version,
            "production_eligible": self.production_eligible,
            "experimental_standard": self.experimental_standard,
            "project_identity": self.project_identity,
        }
        if not self.eligible:
            payload["error_code"] = 生产资格错误码
        return payload


class 生产资格错误(工程错误):
    def __init__(self, decision: 生产资格判定) -> None:
        super().__init__(生产资格错误码, ExitCode.PRODUCTION_MODE_NOT_ELIGIBLE)
        self.decision = decision
        self.details = decision.to_dict()


def _读规则摘要(path: Path) -> tuple[str, str, bool]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "", "", False
    if not isinstance(data, dict):
        return "", "", False
    schema_version = data.get("schema_version", "")
    status = str(data.get("status", "")).lower()
    production_eligible = data.get("production_eligible") is True
    return str(schema_version), status, production_eligible


def _规则源列表(rule_source: Path | str | Iterable[Path | str] | None) -> list[Path]:
    if rule_source is None:
        return []
    if isinstance(rule_source, (str, Path)):
        return [Path(rule_source)]
    return [Path(item) for item in rule_source]


def 判定生产资格(
    *,
    requested_mode: str,
    rule_source: Path | str | Iterable[Path | str] | None,
    entrypoint: str,
    project_identity: str = "",
) -> 生产资格判定:
    experimental_standard = requested_mode != 生产模式
    if requested_mode != 生产模式:
        return 生产资格判定(
            requested_mode=requested_mode,
            effective_mode=requested_mode,
            eligible=True,
            reason="NON_PRODUCTION_MODE",
            rule_source=";".join(str(path) for path in _规则源列表(rule_source)),
            entrypoint=entrypoint,
            rules_status="",
            schema_version="",
            production_eligible=False,
            experimental_standard=experimental_standard,
            project_identity=project_identity,
        )

    rule_sources = _规则源列表(rule_source)
    if not rule_sources:
        return 生产资格判定(
            requested_mode=requested_mode,
            effective_mode=None,
            eligible=False,
            reason="MISSING_ELIGIBILITY_CONTEXT",
            rule_source="",
            entrypoint=entrypoint,
            rules_status="",
            schema_version="",
            production_eligible=False,
            experimental_standard=False,
            project_identity=project_identity,
        )

    summaries = [_读规则摘要(path) for path in rule_sources]
    schema_version = ";".join(item[0] for item in summaries)
    rules_status = ";".join(item[1] for item in summaries)
    production_eligible = all(item[1] == "production" and item[2] for item in summaries)
    joined_sources = ";".join(str(path) for path in rule_sources)
    if production_eligible:
        return 生产资格判定(
            requested_mode=requested_mode,
            effective_mode=生产模式,
            eligible=True,
            reason="PRODUCTION_ELIGIBLE",
            rule_source=joined_sources,
            entrypoint=entrypoint,
            rules_status=rules_status,
            schema_version=schema_version,
            production_eligible=production_eligible,
            experimental_standard=False,
            project_identity=project_identity,
        )

    statuses = {item[1] for item in summaries}
    reason = "CANDIDATE_RULES_ONLY" if statuses & {"active", "candidate", ""} else "RULES_NOT_PRODUCTION_ELIGIBLE"
    return 生产资格判定(
        requested_mode=requested_mode,
        effective_mode=None,
        eligible=False,
        reason=reason,
        rule_source=joined_sources,
        entrypoint=entrypoint,
        rules_status=rules_status,
        schema_version=schema_version,
        production_eligible=production_eligible,
        experimental_standard=False,
        project_identity=project_identity,
    )


def 要求生产资格(
    *,
    requested_mode: str,
    rule_source: Path | str | Iterable[Path | str] | None,
    entrypoint: str,
    project_identity: str = "",
) -> 生产资格判定:
    decision = 判定生产资格(
        requested_mode=requested_mode,
        rule_source=rule_source,
        entrypoint=entrypoint,
        project_identity=project_identity,
    )
    if requested_mode == 生产模式 and not decision.eligible:
        raise 生产资格错误(decision)
    return decision


def 判定结果转标准字段(decision: 生产资格判定) -> dict[str, Any]:
    effective = decision.effective_mode or decision.requested_mode
    return {
        "standard_mode": effective,
        "experimental_standard": effective == 候选试验模式,
        "production_eligibility": decision.to_dict(),
    }
