from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class 句式问题:
    段落编号: int
    句子编号: int
    句长: int
    信号: str


@dataclass
class 重复簇:
    短语: str
    出现位置: list[tuple[int, int]]


@dataclass
class 解释腔问题:
    段落编号: int
    句子编号: int
    摘句: str


@dataclass
class 信息密度问题:
    段落编号: int
    信号: str


@dataclass
class 人物语气漂移:
    人物: str
    来源A: str
    来源B: str
    证据不足: bool = False


@dataclass
class 文风问题:
    issue_type: str
    paragraph: int
    sentence: int | None
    quote: str
    constraint: str


@dataclass
class 文风修改动作:
    目标位置: str
    动作: str
    保留范围: str
    禁止范围: str
    验收标准: str


@dataclass
class 文风诊断结果:
    root_cause: str
    style_issues: list[文风问题] = field(default_factory=list)
    预处理信号: dict = field(default_factory=dict)
