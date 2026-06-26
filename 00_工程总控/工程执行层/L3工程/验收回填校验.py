from __future__ import annotations

from L3模型 import L3执行任务, L3协议规则


VALID_RETURNS = {"L1-00", "L1-01", "L1-02", "L1-03", "L1.5"}


def 校验(task: L3执行任务, rules: L3协议规则 | None = None) -> list[str]:
    valid_returns = rules.合法回流位置 if rules is not None else VALID_RETURNS
    if task.回流验收位置 not in valid_returns:
        return [f"回流验收位置异常：{task.回流验收位置}"]
    return []
