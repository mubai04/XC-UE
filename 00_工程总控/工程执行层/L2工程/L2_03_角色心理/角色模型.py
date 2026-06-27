from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class 角色状态:
    名称: str
    当前目标: str = ""
    已知信息: list[str] = field(default_factory=list)


@dataclass
class 触发事件:
    段落: int
    摘句: str


@dataclass
class 行为:
    角色: str
    段落: int
    摘句: str


@dataclass
class 选择:
    角色: str
    段落: int
    摘句: str


@dataclass
class 行为结果:
    段落: int
    摘句: str


@dataclass
class 动机缺口:
    character: str
    behavior_quote: str
    missing_link: str
    触发事件: str = ""
    关系对象: str = ""


@dataclass
class 情绪跳跃:
    角色: str
    跳跃前: str
    跳跃后: str


@dataclass
class 关系压力:
    角色: str
    关系对象: str
    压力来源: str
    摘句: str


@dataclass
class 选择代价:
    角色: str
    代价: str
    摘句: str


@dataclass
class 角色诊断结果:
    root_cause: str
    motivation_gaps: list[动机缺口] = field(default_factory=list)
    角色链条: list[dict] = field(default_factory=list)
