from __future__ import annotations

import json
from typing import Any

from DeepSeek客户端 import DeepSeekClient
from JSON响应解析 import 提取JSON字典
from L2模型 import 失败输入
from 模型调用 import 调用模型JSON
from 角色上下文 import 上下文转诊断输入, 角色上下文
from 角色模型 import 动机缺口, 角色诊断结果


def 执行动机链诊断(ctx: 角色上下文, item: 失败输入, *, client: DeepSeekClient | None = None) -> tuple[dict[str, Any], 角色诊断结果]:
    payload = 上下文转诊断输入(ctx, item)
    schema = {
        "root_cause": "动机根因",
        "motivation_gaps": [{"character": "主角", "behavior_quote": "逐字摘句", "missing_link": "缺哪一环", "relation_target": ""}],
        "fix_actions": ["动作1"],
        "acceptance_criteria": ["验收1"],
        "evidence_quotes": [{"paragraph": 1, "quote": "逐字摘句"}],
        "needs_reroute": False,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 L2-03 角色心理诊断器。只输出 JSON。"
                "必须基于 character_chains 与 behaviors 判断动机缺口、情绪跳跃、关系压力。"
                "motivation_gaps 必须引用 behavior_quote。"
                "不得输出‘增强人物’‘补充心理描写’。"
            ),
        },
        {"role": "user", "content": f"输入：\n{json.dumps(payload, ensure_ascii=False)}\n\nJSON：\n{json.dumps(schema, ensure_ascii=False)}"},
    ]
    parsed = 提取JSON字典(调用模型JSON(messages, client=client))
    gaps = []
    for raw in parsed.get("motivation_gaps") or []:
        if isinstance(raw, dict):
            gaps.append(
                动机缺口(
                    character=str(raw.get("character", "")),
                    behavior_quote=str(raw.get("behavior_quote", "")),
                    missing_link=str(raw.get("missing_link", "")),
                    关系对象=str(raw.get("relation_target", "")),
                )
            )
    return parsed, 角色诊断结果(
        root_cause=str(parsed.get("root_cause", "")).strip(),
        motivation_gaps=gaps,
        角色链条=ctx.目标刺激行为链,
    )
