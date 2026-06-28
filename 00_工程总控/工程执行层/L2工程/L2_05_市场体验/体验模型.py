from __future__ import annotations



from dataclasses import dataclass, field





@dataclass

class 阅读阶段:

    名称: str

    起始段落: int

    结束段落: int

    文本摘要: str





@dataclass

class 入口承诺:

    摘句: str

    段落: int

    sentence: int = 0





@dataclass

class 即时收益:

    摘句: str

    段落: int

    sentence: int = 0

    reward_type: str = ""

    summary: str = ""

    reading_stage: str = ""

    position_ratio: float = 0.0





@dataclass

class 弃读风险:

    risk_type: str

    location_quote: str

    modification_target: str

    段落: int = 0





@dataclass

class 信息重复:

    短语: str

    位置A: str

    位置B: str

    摘句A: str = ""

    摘句B: str = ""





@dataclass

class 认知负担:

    类型: str

    摘句: str

    段落: int = 0

    sentence: int = 0





@dataclass

class 末段推动力:

    摘句: str

    段落: int

    sentence: int = 0





@dataclass

class 体验诊断结果:

    root_cause: str

    experience_risks: list[弃读风险] = field(default_factory=list)

    阅读阶段表: list[阅读阶段] = field(default_factory=list)

    入口承诺列表: list[入口承诺] = field(default_factory=list)

    即时收益列表: list[即时收益] = field(default_factory=list)

    认知负担列表: list[认知负担] = field(default_factory=list)

    重复信息列表: list[信息重复] = field(default_factory=list)

    末段推动力列表: list[末段推动力] = field(default_factory=list)

