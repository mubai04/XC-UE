from __future__ import annotations

from pathlib import Path

from L3模型 import L2修复单, L3协议规则
from ProjectHarness运行校验 import 相对


def 映射IR(form: L2修复单, root: Path, harness: Path, rules: L3协议规则) -> list[str]:
    base = harness / "IR"
    mapped = rules.IR映射.get(form.接收模块, rules.IR映射.get("*", []))
    files = [base / name for name in mapped]
    return [相对(root, path) for path in files]


def 校验IR存在(task, root: Path) -> list[str]:
    errors: list[str] = []
    for item in task.IR输入:
        path = root / item
        if not path.exists():
            errors.append(f"IR 输入不存在：{item}")
        elif path.stat().st_size == 0:
            errors.append(f"IR 输入为空：{item}")
    return errors
