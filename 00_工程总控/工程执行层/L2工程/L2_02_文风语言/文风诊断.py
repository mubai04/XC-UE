from __future__ import annotations

import json
from typing import Any

from DeepSeek客户端 import DeepSeekClient
from JSON响应解析 import 提取JSON字典
from L2模型 import 失败输入
from 文风上下文 import 上下文转诊断输入, 文风上下文
from 文风模型 import 文风诊断结果, 文风问题
from 模型调用 import 调用模型JSON


def _系统提示() -> str:
    return (
        "你是 L2-02 文风语言诊断器。只输出 JSON。"
        "必须结合 style_preprocessing 与 chapter_excerpt 判断句式、解释腔、重复、信息密度、人物语气。"
        "style_issues 必须给出 issue_type、paragraph、quote、constraint。"
        "不得输出‘优化语言’‘增强文风’等空泛动作。"
    )


def _响应结构() -> dict[str, Any]:
    return {
        "root_cause": "文风根因",
        "style_issues": [
            {"issue_type": "解释腔", "paragraph": 1, "sentence": 1, "quote": "逐字摘句", "constraint": "具体修改约束"}
        ],
        "fix_actions": ["动作1"],
        "acceptance_criteria": ["验收1"],
        "evidence_quotes": [{"paragraph": 1, "quote": "逐字摘句"}],
        "modify_scope": "段落级",
        "forbid_modify_scope": "事件顺序与人物目标",
        "needs_reroute": False,
    }


def 执行文风诊断(
    ctx: 文风上下文,
    item: 失败输入,
    *,
    client: DeepSeekClient | None = None,
) -> tuple[dict[str, Any], 文风诊断结果]:
    payload = 上下文转诊断输入(ctx, item)
    messages = [
        {"role": "system", "content": _系统提示()},
        {
            "role": "user",
            "content": f"诊断输入：\n{json.dumps(payload, ensure_ascii=False)}\n\n输出 JSON：\n{json.dumps(_响应结构(), ensure_ascii=False)}",
        },
    ]
    parsed = 提取JSON字典(调用模型JSON(messages, client=client))
    issues = []
    for raw in parsed.get("style_issues") or []:
        if isinstance(raw, dict):
            issues.append(
                文风问题(
                    issue_type=str(raw.get("issue_type", "")),
                    paragraph=int(raw.get("paragraph") or 0),
                    sentence=int(raw["sentence"]) if raw.get("sentence") is not None else None,
                    quote=str(raw.get("quote", "")),
                    constraint=str(raw.get("constraint", "")),
                )
            )
    result = 文风诊断结果(
        root_cause=str(parsed.get("root_cause", "")).strip(),
        style_issues=issues,
        预处理信号=payload.get("style_preprocessing", {}),
    )
    return parsed, result
