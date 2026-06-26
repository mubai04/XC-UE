from __future__ import annotations

from 工程异常 import 工程错误
from 退出码 import ExitCode

class 生产规则集缺失(工程错误):
    def __init__(self, message: str = "NO_PRODUCTION_RULESET: 生产模式没有 ACTIVE/FROZEN 规则集") -> None:
        super().__init__(message, ExitCode.NO_PRODUCTION_RULESET)
