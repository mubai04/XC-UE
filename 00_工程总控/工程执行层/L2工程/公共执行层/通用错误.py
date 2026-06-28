from __future__ import annotations


class 能力诊断错误(Exception):
    def __init__(self, message: str, *, kind: str = "DIAGNOSIS_FAILED") -> None:
        super().__init__(message)
        self.kind = kind
