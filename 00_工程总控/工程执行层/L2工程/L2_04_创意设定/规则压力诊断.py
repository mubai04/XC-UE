from __future__ import annotations

import json
from typing import Any

from DeepSeek客户端 import DeepSeekClient
from JSON响应解析 import 提取JSON字典
from L2模型 import 失败输入
from 模型调用 import 调用模型JSON
from 设定上下文 import 上下文转诊断输入, 构造设定上下文, 设定上下文
from 设定模型 import 角色选择压力, 设定诊断结果


def 执行规则压力诊断(ctx: 设定上下文, item: 失败输入, *, client: DeepSeekClient | None = None) -> tuple[dict[str, Any], 设定诊断结果]:
    payload = 上下文转诊断输入(ctx, item)
    schema = {
        "root_cause": "设定根因",
        "setting_pressure_points": [{"rule_or_setting": "规则", "quote": "逐字摘句", "choice_pressure": "迫使角色放弃X或选择Y"}],
        "differentiation": "与常规方案的实际差别",
        "sustainable_variant": "至少一个可重复变体",
        "fix_actions": ["动作1"],
        "acceptance_criteria": ["验收1"],
        "evidence_quotes": [{"paragraph": 1, "quote": "逐字摘句"}],
        "needs_reroute": False,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 L2-04 创意设定诊断器。只输出 JSON。"
                "必须基于 rules/costs 与 text_facts 判断规则压力、差异性、可持续玩法。"
                "不得只写‘加强设定差异’；不得在此模块宣判一致性硬冲突。"
            ),
        },
        {"role": "user", "content": f"输入：\n{json.dumps(payload, ensure_ascii=False)}\n\nJSON：\n{json.dumps(schema, ensure_ascii=False)}"},
    ]
    parsed = 提取JSON字典(调用模型JSON(messages, client=client))
    points = []
    for raw in parsed.get("setting_pressure_points") or []:
        if isinstance(raw, dict):
            points.append(
                角色选择压力(
                    rule_or_setting=str(raw.get("rule_or_setting", "")),
                    quote=str(raw.get("quote", "")),
                    choice_pressure=str(raw.get("choice_pressure", "")),
                )
            )
    return parsed, 设定诊断结果(
        root_cause=str(parsed.get("root_cause", "")).strip(),
        setting_pressure_points=points,
    )
