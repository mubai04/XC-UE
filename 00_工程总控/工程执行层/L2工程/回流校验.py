from __future__ import annotations

from L2模型 import 修复单


def 校验(forms: list[修复单]) -> list[str]:
    errors: list[str] = []
    for form in forms:
        if not form.回流位置:
            errors.append(f"{form.接收模块} 缺少回流位置")
        if form.回流位置 not in {"L1-00", "L1-01", "L1-02", "L1-03", "L1.5"}:
            errors.append(f"{form.接收模块} 回流位置异常：{form.回流位置}")
    return errors
