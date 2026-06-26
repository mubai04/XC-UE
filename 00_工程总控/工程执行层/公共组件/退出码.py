from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    GATE_REJECTED = 10
    REVIEW_REQUIRED = 11
    INPUT_INVALID = 20
    SCHEMA_INVALID = 21
    LINEAGE_ERROR = 22
    NO_PRODUCTION_RULESET = 24
    RULE_PARSE_FAILED = 25
    PRODUCTION_MODE_NOT_ELIGIBLE = 26
    PROJECT_ERROR = 27
    BLOCKED = 30
    INTERNAL_ERROR = 40


业务失败码 = {
    ExitCode.GATE_REJECTED,
    ExitCode.REVIEW_REQUIRED,
    ExitCode.BLOCKED,
}
