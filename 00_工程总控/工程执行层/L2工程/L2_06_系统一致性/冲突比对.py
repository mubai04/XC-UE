from __future__ import annotations

import json
from typing import Any

from DeepSeek客户端 import DeepSeekClient
from JSON响应解析 import 提取JSON字典
from L2模型 import 失败输入
from 一致性上下文 import 上下文转诊断输入, 一致性上下文
from 事实模型 import 一致性冲突, 一致性诊断结果, 来源引用
from 模型调用 import 调用模型JSON


def 执行冲突比对(ctx: 一致性上下文, item: 失败输入, *, client: DeepSeekClient | None = None) -> tuple[dict[str, Any], 一致性诊断结果]:
    payload = 上下文转诊断输入(ctx, item)
    schema = {
        "root_cause": "一致性根因",
        "consistency_conflicts": [
            {
                "conflict_type": "事实",
                "entity": "实体",
                "attribute": "属性",
                "source_a": {"paragraph": 1, "quote": "摘句A", "source_type": "正文"},
                "source_b": {"paragraph": 2, "quote": "摘句B", "source_type": "IR"},
                "classification": "硬冲突",
            }
        ],
        "fix_actions": ["动作1"],
        "acceptance_criteria": ["验收1"],
        "evidence_quotes": [{"paragraph": 1, "quote": "摘句A"}],
        "needs_reroute": False,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 L2-06 系统一致性诊断器。只输出 JSON。"
                "每个 consistency_conflicts 必须同时给出 source_a 与 source_b。"
                "无法双来源核对时不得宣称硬冲突；不得把文风差异判为系统冲突。"
            ),
        },
        {"role": "user", "content": f"输入：\n{json.dumps(payload, ensure_ascii=False)}\n\nJSON：\n{json.dumps(schema, ensure_ascii=False)}"},
    ]
    parsed = 提取JSON字典(调用模型JSON(messages, client=client))
    conflicts = []
    for raw in parsed.get("consistency_conflicts") or []:
        if not isinstance(raw, dict):
            continue
        sa = raw.get("source_a") or {}
        sb = raw.get("source_b") or {}
        conflicts.append(
            一致性冲突(
                conflict_type=str(raw.get("conflict_type", "")),
                实体=str(raw.get("entity", "")),
                属性=str(raw.get("attribute", "")),
                source_a=来源引用(str(sa.get("source_type", "正文")), str(sa.get("quote", "")), int(sa.get("paragraph") or 0)),
                source_b=来源引用(str(sb.get("source_type", "IR")), str(sb.get("quote", "")), int(sb.get("paragraph") or 0)),
                分类=str(raw.get("classification", "硬冲突")),
            )
        )
    return parsed, 一致性诊断结果(root_cause=str(parsed.get("root_cause", "")).strip(), consistency_conflicts=conflicts)
