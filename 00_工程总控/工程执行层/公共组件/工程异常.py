from __future__ import annotations

from 退出码 import ExitCode


class 工程错误(Exception):
    def __init__(self, message: str, exit_code: ExitCode = ExitCode.INTERNAL_ERROR) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class 输入错误(工程错误):
    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.INPUT_INVALID)


class 项目错误(工程错误):
    def __init__(self, message: str, reason: str, **details: object) -> None:
        super().__init__(message, ExitCode.PROJECT_ERROR)
        self.details = {"reason": reason, **details}


class 结构错误(工程错误):
    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.SCHEMA_INVALID)


class 血缘错误(工程错误):
    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.LINEAGE_ERROR)
