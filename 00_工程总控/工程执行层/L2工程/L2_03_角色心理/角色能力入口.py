from __future__ import annotations

from pathlib import Path

from DeepSeek客户端 import DeepSeekClient
from L2模型 import 失败输入, 修复单
from 修复单适配 import 诊断计划转修复单
from 动机链诊断 import 执行动机链诊断
from 角色上下文 import 构造角色上下文
from 角色修复规划 import 模块细节, 规划角色修复
from 角色证据校验 import 校验角色响应
from 通用错误 import 能力诊断错误
from 通用证据定位 import 校验通用证据引用
from 能力标准解析 import 能力规则

MODULE_ID = "L2-03"
FIX_FORM = "L2 角色心理修复单"


def 生成修复单(
    item: 失败输入,
    rules: 能力规则,
    *,
    chapter_path: Path | None = None,
    repo_root: Path | None = None,
    client: DeepSeekClient | None = None,
) -> 修复单:
    form, err = 安全生成修复单(item, rules, chapter_path=chapter_path, repo_root=repo_root, client=client)
    if err or form is None:
        raise RuntimeError(err or f"{MODULE_ID} 未生成修复单")
    return form


def 安全生成修复单(
    item: 失败输入,
    rules: 能力规则,
    *,
    chapter_path: Path | None = None,
    repo_root: Path | None = None,
    client: DeepSeekClient | None = None,
) -> tuple[修复单 | None, str | None]:
    try:
        if chapter_path is None:
            raise 能力诊断错误("缺少章节路径", kind="CHAPTER_PATH_MISSING")
        resolved = chapter_path.resolve() if chapter_path.is_absolute() else (
            (repo_root / chapter_path).resolve() if repo_root else chapter_path.resolve()
        )
        if not resolved.exists():
            raise 能力诊断错误(f"章节不存在：{resolved}", kind="CHAPTER_PATH_MISSING")
        ctx = 构造角色上下文(resolved, item, repo_root=repo_root)
        parsed, diagnosis = 执行动机链诊断(ctx, item, client=client)
        if any(f in str(parsed.get("root_cause", "")) for f in ("增强人物", "加强角色")):
            raise 能力诊断错误("响应命中禁止范围：增强人物", kind="FORBIDDEN_SCOPE")
        validated, base_errors = 校验通用证据引用(parsed, ctx.正文语料)
        errors = base_errors + 校验角色响应(parsed, ctx.正文语料, ctx, diagnosis)
        if errors:
            raise 能力诊断错误("；".join(errors[:6]), kind="EVIDENCE_INVALID")
        plan = 规划角色修复(diagnosis, parsed)
        return (
            诊断计划转修复单(
                item,
                rules,
                module_id=MODULE_ID,
                fix_form_type=FIX_FORM,
                root_cause=diagnosis.root_cause,
                validated_quotes=validated,
                plan=plan,
                module_detail=模块细节(diagnosis),
            ),
            None,
        )
    except 能力诊断错误 as exc:
        return None, f"{MODULE_ID} {exc.kind}: {exc}"
