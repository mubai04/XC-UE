from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class 段落:
    编号: int
    文本: str
    字数: int


@dataclass
class 证据:
    段落: int | None
    摘句: str


@dataclass
class 检测项:
    闸门: str
    名称: str
    状态: str
    说明: str
    证据: list[证据] = field(default_factory=list)
    严重级别: str = "info"
    失败类型: str = ""
    候选模块: str = ""
    回流验收位置: str = ""
    修复方向: str = ""
    heuristic: bool = True
    signal_strength: str = "UNRANKED_HEURISTIC_SIGNAL"
    confidence: str = "UNVALIDATED"


@dataclass
class 闸门结果:
    闸门: str
    判断结果: str
    输入材料: list[str]
    失败类型: list[str]
    失败位置: list[证据]
    是否进入L15: str
    调用方向: list[str]
    回流验收位置: str
    最终状态: str
    检测项: list[检测项]
    规则摘要: dict[str, Any] = field(default_factory=dict)


@dataclass
class 正文检测结果:
    run_id: str
    项目: str
    章节路径: str
    章节标题: str
    当前字数: int
    段落数: int
    方法声明: str
    闸门结果: list[闸门结果]
    失败包: list[检测项]
    路由建议: list[dict[str, Any]]
    schema_version: str = "xcue.l1-report/1.0"
    pipeline_run_id: str = ""
    stage_run_id: str = ""
    status: str = ""
    状态说明: str = ""
    heuristic: bool = True
    publish_authority: bool = False
    human_review_required: bool = True
    validation_status: str = "UNVALIDATED"
    decision_scope: str = "HEURISTIC_SCREENING"
    rule_version: str = "L1-CANDIDATE-UNVALIDATED"
    signal_strength: str = "HEURISTIC_ONLY"
    confidence: str = "LOW_UNCALIBRATED"
    known_limitations: list[str] = field(
        default_factory=lambda: [
            "仅基于已配置的启发式规则和正文表面证据。",
            "不能证明真实读者投入、文学质量或商业表现。",
            "未经过生产数据校准，不具备发布授权能力。",
        ]
    )
    human_review_reasons: list[str] = field(
        default_factory=lambda: [
            "L1 自动结果只做发布前启发式风险筛查。",
            "所有通过、退回或复核状态均需要人工确认后才能进入后续发布决策。",
        ]
    )
    forbidden_extrapolations: list[str] = field(
        default_factory=lambda: [
            "不得据此宣称内部创作成立。",
            "不得据此宣称读者愿意追读或投入。",
            "不得据此宣称质量通过、发布锁通过或可发布。",
        ]
    )
    input_artifacts: list[dict[str, Any]] = field(default_factory=list)
    output_artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
