from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class 设定实体:
    名称: str
    来源: str


@dataclass
class 规则:
    名称: str
    触发条件: str
    来源: str


@dataclass
class 限制:
    描述: str
    来源: str


@dataclass
class 代价:
    描述: str
    来源: str


@dataclass
class 角色选择压力:
    rule_or_setting: str
    quote: str
    choice_pressure: str


@dataclass
class 差异点:
    描述: str
    与普通方案差别: str


@dataclass
class 可持续玩法:
    变体: str
    可重复机制: str


@dataclass
class 设定诊断结果:
    root_cause: str
    setting_pressure_points: list[角色选择压力] = field(default_factory=list)
    差异点列表: list[差异点] = field(default_factory=list)
    可持续玩法列表: list[可持续玩法] = field(default_factory=list)
