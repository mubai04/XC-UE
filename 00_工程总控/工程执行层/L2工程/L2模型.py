from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class 证据:
    段落: int | None
    摘句: str


@dataclass
class 失败输入:
    来源闸门: str
    名称: str
    状态: str
    说明: str
    证据: list[证据]
    严重级别: str
    失败类型: str
    候选模块: str
    回流验收位置: str
    修复方向: str


@dataclass
class 接口判断:
    来源闸门: str
    输入来源模式: str
    输入问题: str
    初步归属: str
    主候选模块: str
    次候选模块: str = ""
    接口失败类型: str = ""
    判断依据: str = ""
    是否混合问题: str = "否"
    是否越界: str = "否"
    建议动作: list[str] = field(default_factory=list)
    回流验收位置: str = ""
    最终状态: str = "接口明确"
    备注: str = ""
    route_rule_id: str = ""
    route_rule_version: str = ""


@dataclass
class 修复单:
    修复单类型: str
    来源闸门: str
    接收模块: str
    输入问题: str
    主失败类型: str
    次失败类型: str
    修复动作: str
    修复产物: str
    验收问题: str
    回流位置: str
    是否需要其他L2辅助: str
    是否需要回L15重路由: str
    最终状态: str
    标准来源: str = ""
    规则编号: str = ""
    规则依据: str = ""
    标准动作: list[str] = field(default_factory=list)
    标准验收: list[str] = field(default_factory=list)
    rule_id: str = ""
    rule_version: str = ""


@dataclass
class L201真实诊断:
    问题类型: str
    证据锚点: list[dict[str, Any]]
    涉及段落: list[int]
    原因诊断: str
    修改目标: str
    候选修改策略: list[str]
    风险: list[str]
    验收条件: list[str]
    确定性候选策略: list[dict[str, Any]]
    置信度: str
    自动修复资格判定: str
    rule_id: str = ""
    rule_version: str = ""


@dataclass
class L2报告:
    run_id: str
    输入文件: str
    输入数量: int
    方法声明: str
    标准校验问题: list[str]
    回流校验问题: list[str]
    接口判断: list[接口判断]
    修复单: list[修复单]
    阻断项: list[接口判断]
    复验目标: list[接口判断] = field(default_factory=list)
    schema_version: str = "xcue.l2-report/1.0"
    pipeline_run_id: str = ""
    stage_run_id: str = ""
    status: str = ""
    状态说明: str = ""
    input_artifacts: list[dict[str, Any]] = field(default_factory=list)
    output_artifacts: list[dict[str, Any]] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
