from __future__ import annotations

import json
from typing import Any

from DeepSeek客户端 import DeepSeekClient, create_client
from L2模型 import 失败输入, 修复单
from 能力标准解析 import 能力规则
from 能力修复单 import 选择失败规则


class 叙事结构诊断错误(Exception):
    def __init__(self, message: str, *, kind: str = "DIAGNOSIS_FAILED") -> None:
        super().__init__(message)
        self.kind = kind


def _构建诊断提示(item: 失败输入, rules: 能力规则) -> list[dict[str, str]]:
    rule = 选择失败规则(item, rules)
    context = {
        "failure_type": item.失败类型,
        "description": item.说明,
        "repair_direction": item.修复方向,
        "matched_rule": rule.编号 if rule else "",
        "ability_scope": rules.输入关键词[:3] if rules.输入关键词 else [],
    }
    schema = {
        "root_cause": "一句话根因",
        "fix_actions": ["可执行修复动作1", "可执行修复动作2"],
        "acceptance_criteria": ["验收标准1"],
        "evidence_quotes": [{"quote": "若引用失败包说明中的原文片段则必须逐字匹配"}],
        "needs_reroute": False,
    }
    return [
        {
            "role": "system",
            "content": "你是 L2-01 叙事结构诊断器。只输出 JSON。修复动作必须可执行且具体。",
        },
        {
            "role": "user",
            "content": (
                f"失败包上下文：\n{json.dumps(context, ensure_ascii=False)}\n\n"
                f"输出 JSON：\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]


def _诊断转修复单(item: 失败输入, rules: 能力规则, parsed: dict[str, Any]) -> 修复单:
    rule = 选择失败规则(item, rules)
    actions = parsed.get("fix_actions") or []
    acceptance = parsed.get("acceptance_criteria") or []
    if not isinstance(actions, list) or not actions:
        raise 叙事结构诊断错误("fix_actions 为空", kind="INVALID_JSON")
    if not isinstance(acceptance, list) or not acceptance:
        raise 叙事结构诊断错误("acceptance_criteria 为空", kind="INVALID_JSON")
    actions = [str(a).strip() for a in actions if str(a).strip()][:4]
    acceptance = [str(a).strip() for a in acceptance if str(a).strip()][:4]
    if not actions:
        raise 叙事结构诊断错误("fix_actions 无有效项", kind="INVALID_JSON")
    root_cause = str(parsed.get("root_cause", "")).strip() or item.说明
    reroute = "是" if parsed.get("needs_reroute") else "否"
    return 修复单(
        修复单类型="L2 叙事结构修复单",
        来源闸门=item.来源闸门,
        接收模块=rules.模块,
        输入问题=f"{item.说明} | 根因：{root_cause}",
        主失败类型=item.失败类型,
        次失败类型=rule.编号 if rule else "",
        修复动作=" / ".join(actions),
        修复产物=item.修复方向 or rules.输出产物 or "叙事结构修复单",
        验收问题="；".join(acceptance),
        回流位置=item.回流验收位置 or item.来源闸门,
        是否需要其他L2辅助="否",
        是否需要回L15重路由=reroute,
        最终状态="回原闸门复验",
        标准来源=rules.标准来源,
        规则编号=rule.编号 if rule else "",
        规则依据=root_cause,
        标准动作=actions,
        标准验收=acceptance,
        rule_id=f"{rules.模块}:{rule.编号}" if rule else f"{rules.模块}:semantic",
        rule_version=rule.规则版本 if rule else rules.规则版本,
    )


def 生成修复单(
    item: 失败输入,
    rules: 能力规则,
    *,
    client: DeepSeekClient | None = None,
) -> 修复单:
    api = client or create_client("L2")
    result = api.chat_json(_构建诊断提示(item, rules))
    if not result.ok or not result.parsed:
        raise 叙事结构诊断错误(result.error or "API 失败", kind=result.error_kind or "API_ERROR")
    try:
        return _诊断转修复单(item, rules, result.parsed)
    except 叙事结构诊断错误:
        raise
    except Exception as exc:
        raise 叙事结构诊断错误(str(exc)) from exc


def 安全生成修复单(
    item: 失败输入,
    rules: 能力规则,
    *,
    client: DeepSeekClient | None = None,
) -> tuple[修复单 | None, str | None]:
    try:
        return 生成修复单(item, rules, client=client), None
    except 叙事结构诊断错误 as exc:
        return None, f"L2-01 {exc.kind}: {exc}"
