from __future__ import annotations

# 用于校验模型输出是否回显 fixture 硬编码；不得写入领域提取逻辑。
PRODUCTION_FORBIDDEN_FIXTURE_STRINGS = (
    "生存/达成目标",
    "规则正在收紧",
    "审查/层级规则",
    "触发异常或违规则生效",
    "违规则名单减少或承担后果",
    "名字减少意味着淘汰",
    "林舟想救妹妹",
    "回溯术",
    "左手已经断了",
    "双手完好",
)


def 命中禁止词(text: str) -> list[str]:
    return [s for s in PRODUCTION_FORBIDDEN_FIXTURE_STRINGS if s in text]
