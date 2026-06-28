from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from DeepSeek客户端 import DeepSeekClient, create_client
from L2_01_诊断上下文 import 格式化诊断输入, 构建上下文完整性记录, 构建诊断语料, 检查failure_evidence输入, 诊断输入摘要
from L2_01_证据校验 import 校验诊断响应
from L2模型 import 失败输入, 修复单, 证据
from 能力标准解析 import 能力规则
from 能力修复单 import 选择失败规则


class 叙事结构诊断错误(Exception):
    def __init__(self, message: str, *, kind: str = "DIAGNOSIS_FAILED") -> None:
        super().__init__(message)
        self.kind = kind


def _构建诊断提示(
    item: 失败输入,
    rules: 能力规则,
    *,
    chapter_path: Path,
    repo_root: Path | None = None,
) -> tuple[str, list[dict[str, str]]]:
    matched = 选择失败规则(item, rules)
    corpus, payload = 诊断输入摘要(item, rules, matched, chapter_path, repo_root=repo_root)
    schema = {
        "root_cause": "基于 chapter_context 与 failure_evidence 的一句话根因（可概括，不必逐字包含摘句）",
        "root_cause_evidence_indices": [0],
        "fix_actions": ["可执行修复动作1", "可执行修复动作2"],
        "acceptance_criteria": ["验收标准1"],
        "evidence_quotes": [{"paragraph": 1, "quote": "必须逐字存在于 chapter_context 或 failure_evidence"}],
        "needs_reroute": False,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 L2-01 叙事结构诊断器。只输出 JSON。"
                "根因必须来自输入中的 chapter_context 与 failure_evidence，不得只重复 failure_type 或 repair_direction。"
                "evidence_quotes 必须非空，且每条 quote 必须能在输入正文中逐字找到。"
                "root_cause_evidence_indices 必须列出 root_cause 所依据的 evidence_quotes 下标（从 0 开始）。"
                "fix_actions 与 acceptance_criteria 必须具体可执行。"
                "若 input_evidence_status 为 MISMATCH，必须设置 needs_reroute=true，"
                "不得把输入证据错位当成叙事结构故障；fix_actions 应指向回 L1 修正证据或重路由。"
            ),
        },
        {
            "role": "user",
            "content": (
                "诊断输入：\n"
                f"{格式化诊断输入(payload)}\n\n"
                f"输出 JSON 结构：\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]
    return corpus, messages


def _诊断转修复单(
    item: 失败输入,
    rules: 能力规则,
    parsed: dict[str, Any],
    validated_quotes: list[dict[str, Any]],
) -> 修复单:
    rule = 选择失败规则(item, rules)
    actions = [str(a).strip() for a in parsed.get("fix_actions") or [] if str(a).strip()][:4]
    acceptance = [str(a).strip() for a in parsed.get("acceptance_criteria") or [] if str(a).strip()][:4]
    root_cause = str(parsed.get("root_cause", "")).strip()
    reroute = "是" if parsed.get("needs_reroute") else "否"
    diagnostic_evidence = [
        证据(
            int(entry["paragraph"]) if isinstance(entry.get("paragraph"), int) else None,
            str(entry["quote"]),
        )
        for entry in validated_quotes
    ]
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
        诊断证据=diagnostic_evidence,
    )


def _证据错位修复单(item: 失败输入, rules: 能力规则, mismatches: list) -> 修复单:
    detail = "；".join(str(m.get("quote", "")) for m in mismatches[:3])
    return 修复单(
        修复单类型="L2 叙事结构修复单",
        来源闸门=item.来源闸门,
        接收模块=rules.模块,
        输入问题=f"{item.说明} | 输入证据错位，非结构故障",
        主失败类型=item.失败类型,
        次失败类型="INPUT_EVIDENCE_MISMATCH",
        修复动作="回 L1 修正 failure_evidence 摘句，使其逐字存在于章节正文后再路由",
        修复产物="证据校正",
        验收问题="failure_evidence 摘句与章节正文一致后再进入 L2-01",
        回流位置=item.回流验收位置 or item.来源闸门,
        是否需要其他L2辅助="否",
        是否需要回L15重路由="是",
        最终状态="回L1.5",
        标准来源=rules.标准来源,
        规则编号="",
        规则依据=f"输入证据不在正文：{detail}",
        标准动作=["回 L1 修正 failure_evidence 摘句"],
        标准验收=["failure_evidence 与章节正文逐字一致"],
        rule_id=f"{rules.模块}:input_evidence_mismatch",
        rule_version=rules.规则版本,
        诊断证据=[证据(m.get("paragraph"), str(m.get("quote", ""))) for m in mismatches if m.get("quote")],
    )


def 生成修复单(
    item: 失败输入,
    rules: 能力规则,
    *,
    chapter_path: Path | None = None,
    repo_root: Path | None = None,
    client: DeepSeekClient | None = None,
) -> 修复单:
    if chapter_path is None:
        raise 叙事结构诊断错误("缺少章节路径，无法读取正文上下文", kind="CHAPTER_PATH_MISSING")
    resolved = chapter_path if chapter_path.is_absolute() else (repo_root / chapter_path if repo_root else chapter_path)
    if not Path(resolved).exists():
        raise 叙事结构诊断错误(f"章节正文不存在：{resolved}", kind="CHAPTER_PATH_MISSING")

    completeness = 构建上下文完整性记录(
        Path(resolved), item, repo_root=repo_root
    )
    if completeness.get("truncated"):
        raise 叙事结构诊断错误(
            f"章节上下文未完整发送：coverage_ratio={completeness.get('coverage_ratio')}",
            kind="CONTEXT_INCOMPLETE",
        )

    corpus_pre, _ = 构建诊断语料(Path(resolved), item, repo_root=repo_root)
    evidence_status = 检查failure_evidence输入(item, corpus_pre)
    if evidence_status["status"] == "MISMATCH":
        return _证据错位修复单(item, rules, evidence_status["mismatches"])

    api = client or create_client("L2")
    corpus, messages = _构建诊断提示(item, rules, chapter_path=Path(resolved), repo_root=repo_root)
    result = api.chat_json(messages)
    if not result.ok or not result.parsed:
        raise 叙事结构诊断错误(result.error or "API 失败", kind=result.error_kind or "API_ERROR")

    validated_quotes, errors = 校验诊断响应(
        result.parsed,
        corpus,
        failure_type=item.失败类型,
        description=item.说明,
        repair_direction=item.修复方向,
    )
    if errors:
        raise 叙事结构诊断错误("；".join(errors[:5]), kind="EVIDENCE_INVALID")

    try:
        return _诊断转修复单(item, rules, result.parsed, validated_quotes)
    except 叙事结构诊断错误:
        raise
    except Exception as exc:
        raise 叙事结构诊断错误(str(exc)) from exc


def 安全生成修复单(
    item: 失败输入,
    rules: 能力规则,
    *,
    chapter_path: Path | None = None,
    repo_root: Path | None = None,
    client: DeepSeekClient | None = None,
) -> tuple[修复单 | None, str | None]:
    try:
        return (
            生成修复单(
                item,
                rules,
                chapter_path=chapter_path,
                repo_root=repo_root,
                client=client,
            ),
            None,
        )
    except 叙事结构诊断错误 as exc:
        return None, f"L2-01 {exc.kind}: {exc}"
