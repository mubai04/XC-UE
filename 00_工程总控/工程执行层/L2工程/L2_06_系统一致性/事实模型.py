from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

来源类型 = Literal["正文", "IR", "前序章节", "规则"]
冲突分类 = Literal[
    "HARD_CONFLICT",
    "EXPLANATION_INSUFFICIENT",
    "ALLOWED_CHANGE",
    "EVIDENCE_INSUFFICIENT",
]


@dataclass
class 事实声明:
    实体: str
    属性: str
    值: str
    归一化值: str
    时间标记: str = ""
    否定: bool = False
    来源类型: 来源类型 = "正文"
    来源路径: str = ""
    段落: int = 0
    摘句: str = ""


@dataclass
class 来源条目:
    来源路径: str
    段落: int
    文本: str


@dataclass
class 来源索引:
    条目: dict[str, list[来源条目]] = field(default_factory=dict)

    def 注册(self, 来源类型: str, 来源路径: str, 段落: int, 文本: str) -> None:
        self.条目.setdefault(来源类型, []).append(来源条目(来源路径, 段落, 文本))

    def 查找摘句(self, 来源类型: str, quote: str, *, 来源路径: str = "") -> bool:
        if not quote or not quote.strip():
            return False
        for entry in self.条目.get(来源类型, []):
            if 来源路径 and entry.来源路径 != 来源路径:
                continue
            if quote in entry.文本:
                return True
        return False

    def 语料(self, 来源类型: str, *, 来源路径: str = "") -> str:
        parts: list[str] = []
        for entry in self.条目.get(来源类型, []):
            if 来源路径 and entry.来源路径 != 来源路径:
                continue
            parts.append(entry.文本)
        return "\n".join(parts)


@dataclass
class 来源引用:
    来源类型: str
    quote: str
    paragraph: int = 0
    来源路径: str = ""


@dataclass
class 一致性冲突:
    conflict_type: str
    实体: str
    属性: str
    source_a: 来源引用
    source_b: 来源引用
    分类: str = "HARD_CONFLICT"


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
