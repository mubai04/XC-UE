from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class 字段映射记录:
    旧字段: str
    新字段: str
    说明: str = ""


@dataclass
class 迁移结果:
    迁移状态: str
    来源对象类型: str
    目标Schema编号: str
    目标对象: dict[str, Any] = field(default_factory=dict)
    旧字段到新字段映射: list[字段映射记录] = field(default_factory=list)
    未迁移字段: list[str] = field(default_factory=list)
    已消费但不保留的旧字段: list[str] = field(default_factory=list)
    迁移警告: list[str] = field(default_factory=list)
    迁移错误: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "迁移状态": self.迁移状态,
            "来源对象类型": self.来源对象类型,
            "目标Schema编号": self.目标Schema编号,
            "目标对象": self.目标对象,
            "旧字段到新字段映射": [
                {"旧字段": m.旧字段, "新字段": m.新字段, "说明": m.说明}
                for m in self.旧字段到新字段映射
            ],
            "未迁移字段": self.未迁移字段,
            "已消费但不保留的旧字段": self.已消费但不保留的旧字段,
            "迁移警告": self.迁移警告,
            "迁移错误": self.迁移错误,
        }


@dataclass
class 迁移上下文:
    pipeline_run_id: str
    project_id: str = ""
    chapter_path: str = ""
    默认证据来源: str = "CHAPTER"
    旧对象编号映射: dict[str, str] = field(default_factory=dict)
    L1发现编号映射: dict[str, str] = field(default_factory=dict)
    路由规则编号映射: dict[str, str] = field(default_factory=dict)
    来源文件映射: dict[str, str] = field(default_factory=dict)
    L1失败包编号: str = ""
    L1_5路由决策编号: str = ""
    L2修复单编号列表: list[str] = field(default_factory=list)
    L2报告编号: str = ""
    L3执行任务包编号: str = ""
    主发现编号: str = ""
    _序号计数: dict[str, int] = field(default_factory=dict)

    def 要求(self, *fields: str) -> None:
        from 迁移错误 import MIGRATION_CONTEXT_REQUIRED, 迁移错误

        missing = [f for f in fields if not getattr(self, f, "")]
        if missing:
            raise 迁移错误(MIGRATION_CONTEXT_REQUIRED, f"缺少上下文：{', '.join(missing)}")

    def 注册发现(self, 键: str, 编号: str) -> None:
        self.L1发现编号映射[键] = 编号

    def 查找发现(self, 键: str) -> str | None:
        return self.L1发现编号映射.get(键)
