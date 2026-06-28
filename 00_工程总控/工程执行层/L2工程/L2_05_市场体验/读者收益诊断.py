from __future__ import annotations



import json

from typing import Any



from DeepSeek客户端 import DeepSeekClient

from JSON响应解析 import 提取JSON字典

from L2模型 import 失败输入

from 模型调用 import 调用模型JSON

from 体验模型 import 体验诊断结果, 弃读风险

from 阅读阶段上下文 import 上下文转诊断输入, 体验上下文





def 执行读者收益诊断(ctx: 体验上下文, item: 失败输入, *, client: DeepSeekClient | None = None) -> tuple[dict[str, Any], 体验诊断结果]:

    payload = 上下文转诊断输入(ctx, item)

    schema = {

        "root_cause": "体验根因",

        "experience_risks": [{"risk_type": "弃读", "location_quote": "逐字摘句", "modification_target": "改哪一处达到什么读者效果"}],

        "fix_actions": ["动作1"],

        "acceptance_criteria": ["验收1"],

        "evidence_quotes": [{"paragraph": 1, "quote": "逐字摘句"}],

        "needs_reroute": False,

    }

    messages = [

        {

            "role": "system",

            "content": (

                "你是 L2-05 市场体验诊断器。只输出 JSON。"

                "必须基于 reading_stages、entry_promises、immediate_rewards、cognitive_loads、repeat_info、ending_momentum 判断体验风险。"

                "不得复述 SCREENING_PASS/REJECT 或 L1 状态；不得写‘提高爽点’。"

            ),

        },

        {"role": "user", "content": f"输入：\n{json.dumps(payload, ensure_ascii=False)}\n\nJSON：\n{json.dumps(schema, ensure_ascii=False)}"},

    ]

    parsed = 提取JSON字典(调用模型JSON(messages, client=client))

    risks = []

    for raw in parsed.get("experience_risks") or []:

        if isinstance(raw, dict):

            risks.append(

                弃读风险(

                    risk_type=str(raw.get("risk_type", "")),

                    location_quote=str(raw.get("location_quote", "")),

                    modification_target=str(raw.get("modification_target", "")),

                )

            )

    return parsed, 体验诊断结果(

        root_cause=str(parsed.get("root_cause", "")).strip(),

        experience_risks=risks,

        阅读阶段表=ctx.阅读阶段表,

        入口承诺列表=ctx.入口承诺列表,

        即时收益列表=ctx.即时收益列表,

        认知负担列表=ctx.认知负担列表,

        重复信息列表=ctx.重复信息列表,

        末段推动力列表=ctx.末段推动力列表,

    )

