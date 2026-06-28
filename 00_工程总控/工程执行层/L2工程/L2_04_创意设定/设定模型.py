from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class 设定实体:
    名称: str
    source_type: str = ""
    source_path: str = ""
    paragraph: int = 0
    quote: str = ""


@dataclass
class 规则:
    名称: str
    触发条件: str
    source_type: str = ""
    source_path: str = ""
    paragraph: int = 0
    quote: str = ""
    sentence: int | None = None
    subject: str | None = None
    condition: str = ""
    effect: str = ""


@dataclass
class 限制:
    描述: str
    source_type: str = ""
    source_path: str = ""
    paragraph: int = 0
    quote: str = ""
    sentence: int | None = None
    前置条件: str = ""
    限制结果: str = ""
    subject: str = ""
    condition: str = ""
    effect_or_permission: str = ""
    constraint_type: str = ""


@dataclass
class 代价:
    描述: str
    source_type: str = ""
    source_path: str = ""
    paragraph: int = 0
    quote: str = ""
    sentence: int | None = None
    触发条件: str = ""
    承受者: str = ""


@dataclass
class 角色选择压力:
    rule_or_setting: str
    quote: str
    choice_pressure: str
    problem_type: str = ""
    analysis: str = ""
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class 差异点:
    描述: str
    与普通方案差别: str
    quote: str = ""
    paragraph: int = 0
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class 可持续变体:
    变体: str
    可重复机制: str
    quote: str = ""
    paragraph: int = 0
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class 设定诊断结果:
    root_cause: str
    setting_pressure_points: list[角色选择压力] = field(default_factory=list)
    differentiation_points: list[差异点] = field(default_factory=list)
    sustainable_variants: list[可持续变体] = field(default_factory=list)
