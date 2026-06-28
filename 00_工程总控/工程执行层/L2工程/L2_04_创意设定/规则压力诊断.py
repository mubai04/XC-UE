from __future__ import annotations

import json
from typing import Any

from DeepSeek客户端 import DeepSeekClient
from JSON响应解析 import 提取JSON字典
from L2模型 import 失败输入
from 模型调用 import 调用模型JSON
from 证据索引 import SETTING_RESPONSE_SCHEMA
from 设定上下文 import 上下文转诊断输入, 设定上下文
from 设定模型 import 差异点, 可持续变体, 角色选择压力, 设定诊断结果


def _response_schema() -> dict[str, Any]:
    return {
        "response_schema_version": SETTING_RESPONSE_SCHEMA,
        "root_cause": "设定根因",
        "setting_pressure_points": [
            {
                "setting": "设定名",
                "problem_type": "RULE_DOES_NOT_PRESS_CHOICE",
                "evidence_ids": ["EVID-0001", "EVID-0008"],
                "analysis": "规则存在但章节未迫使取舍",
                "repair_direction": "让角色在保留记忆与取牌之间作出选择",
            }
        ],
        "differentiation_points": [
            {
                "description": "差异描述",
                "contrast_with_convention": "与常规方案差别",
                "evidence_ids": ["EVID-0003"],
            }
        ],
        "sustainable_variants": [
            {
                "variant": "变体名",
                "repeatable_mechanism": "可重复机制",
                "evidence_ids": ["EVID-0004"],
            }
        ],
        "fix_actions": ["动作1"],
        "acceptance_criteria": ["验收1"],
        "evidence_quotes": [{"evidence_id": "EVID-0001"}],
        "needs_reroute": False,
    }


def 执行规则压力诊断(
    ctx: 设定上下文,
    item: 失败输入,
    *,
    client: DeepSeekClient | None = None,
) -> tuple[dict[str, Any], 设定诊断结果]:
    payload = 上下文转诊断输入(ctx, item)
    schema = _response_schema()
    messages = [
        {
            "role": "system",
            "content": (
                "你是 L2-04 创意设定诊断器。只输出 JSON。"
                f"必须使用 {SETTING_RESPONSE_SCHEMA}："
                "所有诊断项通过 evidence_ids 引用 indexed_evidence，不得用自由 quote 作为主绑定键。"
                "IR/PROJECT_RULE 摘句只能引用对应文件的 evidence_id。"
                "RULE_DOES_NOT_PRESS_CHOICE 必须同时引用规则来源与章节行为来源。"
                "不得在此模块宣判一致性硬冲突；若发现正文与规则硬冲突，设置 needs_reroute=true。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"输入：\n{json.dumps(payload, ensure_ascii=False)}\n\n"
                f"JSON：\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]
    parsed = 提取JSON字典(调用模型JSON(messages, client=client))
    parsed.setdefault("response_schema_version", SETTING_RESPONSE_SCHEMA)

    points: list[角色选择压力] = []
    for raw in parsed.get("setting_pressure_points") or []:
        if not isinstance(raw, dict):
            continue
        ids = [str(x) for x in raw.get("evidence_ids") or [] if str(x).strip()]
        points.append(
            角色选择压力(
                rule_or_setting=str(raw.get("setting", raw.get("rule_or_setting", ""))),
                quote="",
                choice_pressure=str(raw.get("repair_direction", raw.get("choice_pressure", ""))),
                problem_type=str(raw.get("problem_type", "")),
                analysis=str(raw.get("analysis", "")),
                evidence_ids=ids,
            )
        )

    diff_points: list[差异点] = []
    for raw in parsed.get("differentiation_points") or []:
        if not isinstance(raw, dict):
            continue
        ids = [str(x) for x in raw.get("evidence_ids") or [] if str(x).strip()]
        diff_points.append(
            差异点(
                描述=str(raw.get("description", "")),
                与普通方案差别=str(raw.get("contrast_with_convention", "")),
                quote="",
                evidence_ids=ids,
            )
        )

    variants: list[可持续变体] = []
    for raw in parsed.get("sustainable_variants") or []:
        if not isinstance(raw, dict):
            continue
        ids = [str(x) for x in raw.get("evidence_ids") or [] if str(x).strip()]
        variants.append(
            可持续变体(
                变体=str(raw.get("variant", "")),
                可重复机制=str(raw.get("repeatable_mechanism", "")),
                quote="",
                evidence_ids=ids,
            )
        )

    return parsed, 设定诊断结果(
        root_cause=str(parsed.get("root_cause", "")).strip(),
        setting_pressure_points=points,
        differentiation_points=diff_points,
        sustainable_variants=variants,
    )
