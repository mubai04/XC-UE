from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class 事实声明:
    实体: str
    属性: str
    值: str
    来源类型: Literal["正文", "IR", "规则"]
    摘句: str
    段落: int = 0


@dataclass
class 来源引用:
    来源类型: str
    quote: str
    paragraph: int = 0


@dataclass
class 一致性冲突:
    conflict_type: str
    实体: str
    属性: str
    source_a: 来源引用
    source_b: 来源引用
    分类: str = "硬冲突"


@dataclass
class 允许变化:
    实体: str
    属性: str
    说明: str


@dataclass
class 一致性诊断结果:
    root_cause: str
    consistency_conflicts: list[一致性冲突] = field(default_factory=list)
    解释不足: list[str] = field(default_factory=list)
