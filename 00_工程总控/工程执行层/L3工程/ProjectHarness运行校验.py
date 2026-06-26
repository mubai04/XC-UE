from __future__ import annotations

from pathlib import Path

from 安全路径 import resolve_inside_root
from 工程异常 import 输入错误
from L3模型 import L3协议规则
from 项目加载器 import 加载项目


def 发现Harness(root: Path, preferred: str | None = None, project: str | None = None, registry_path: str | None = None) -> Path:
    if preferred:
        candidate = resolve_inside_root(root, preferred)
    else:
        candidate = 加载项目(root, project, registry_path).project_root
    确保Harness目录(candidate)
    return candidate


def 相对(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def 确保Harness目录(harness: Path) -> list[Path]:
    required = [harness / "IR", harness / "chapters", harness / "logs"]
    missing = [item for item in required if not item.exists()]
    if missing:
        raise 输入错误(f"Project Harness 验证失败：{', '.join(str(item) for item in missing)}")
    return required


def 默认候选目标(root: Path, harness: Path, run_id: str, index: int, rules: L3协议规则) -> str:
    relative = rules.候选目标模板.format(run_id=run_id, index=index)
    target = harness / relative
    return 相对(root, target)
