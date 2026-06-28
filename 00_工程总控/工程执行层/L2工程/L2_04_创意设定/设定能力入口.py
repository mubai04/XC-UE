from __future__ import annotations

from pathlib import Path

from DeepSeek客户端 import DeepSeekClient
from L2模型 import 失败输入, 修复单
from 修复单适配 import 诊断计划转修复单
from 规则压力诊断 import 执行规则压力诊断
from 设定上下文 import 构造设定上下文
from 设定修复规划 import 模块细节, 规划设定修复
from 设定证据校验 import 提取校验错误类型, 校验设定响应, 校验设定证据引用
from 通用错误 import 能力诊断错误
from 能力标准解析 import 能力规则

MODULE_ID = "L2-04"
FIX_FORM = "L2 创意设定修复单"


def _resolve_ir(chapter_path: Path, repo_root: Path | None) -> Path | None:
    parent = chapter_path.parent.parent
    ir = parent / "IR"
    return ir if ir.is_dir() else None


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
        ctx = 构造设定上下文(resolved, item, repo_root=repo_root, ir_dir=_resolve_ir(resolved, repo_root))
        parsed, diagnosis = 执行规则压力诊断(ctx, item, client=client)
        validated, base_errors = 校验设定证据引用(parsed, ctx)
        errors = base_errors + 校验设定响应(parsed, ctx, diagnosis)
        if errors:
            kind = 提取校验错误类型(errors)
            raise 能力诊断错误("；".join(errors[:6]), kind=kind)
        plan = 规划设定修复(diagnosis, parsed)
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
