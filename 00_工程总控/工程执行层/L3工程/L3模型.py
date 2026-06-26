from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from 工程异常 import 工程错误
from 退出码 import ExitCode


默认允许状态跳转 = {
    "RECEIVED": {"INPUT_VALIDATED", "VALIDATION_FAILED"},
    "INPUT_VALIDATED": {"TASK_PLANNED"},
    "TASK_PLANNED": {"TASK_PACKAGE_CREATED", "BLOCKED"},
    "TASK_PACKAGE_CREATED": {"AWAITING_EXECUTOR"},
    "AWAITING_EXECUTOR": {"EXECUTION_STARTED"},
    "EXECUTION_STARTED": {"EXECUTION_FAILED", "EXECUTION_COMPLETED"},
    "EXECUTION_FAILED": {"ROLLED_BACK"},
    "EXECUTION_COMPLETED": {"ACCEPTANCE_PENDING"},
    "ACCEPTANCE_PENDING": {"ACCEPTED", "ROLLED_BACK"},
    "VALIDATION_FAILED": {"BLOCKED"},
    "BLOCKED": set(),
    "ACCEPTED": set(),
    "ROLLED_BACK": set(),
}

允许状态跳转 = 默认允许状态跳转


@dataclass
class L3协议规则:
    规则版本: str
    状态机: list[str] = field(default_factory=list)
    异常状态: list[str] = field(default_factory=list)
    状态跳转: dict[str, set[str]] = field(default_factory=dict)
    权限矩阵: dict[str, dict[str, str]] = field(default_factory=dict)
    任务字段: list[str] = field(default_factory=list)
    输出字段: list[str] = field(default_factory=list)
    执行顺序: list[str] = field(default_factory=list)
    IR推荐文件: list[str] = field(default_factory=list)
    候选必备目录: list[str] = field(default_factory=list)
    IR映射: dict[str, list[str]] = field(default_factory=dict)
    任务类型规则: list[dict[str, Any]] = field(default_factory=list)
    正文章节Glob: str = "ch*.md"
    候选目标模板: str = "chapters/_candidates/{run_id}_TASK-{index:03d}.md"
    默认禁止目标: list[str] = field(default_factory=list)
    是否允许改正式正文: str = "否"
    是否需要备份: str = "不适用"
    合法回流位置: set[str] = field(default_factory=set)
    禁止项: list[str] = field(default_factory=list)
    补丁执行规则: dict[str, Any] = field(default_factory=dict)


def 状态变更(前状态: str, 后状态: str, 触发事件: str, 执行组件: str, 证据文件: str = "") -> dict[str, str]:
    if 前状态 and 后状态 not in 允许状态跳转.get(前状态, set()):
        raise 工程错误(f"非法状态跳转：{前状态} -> {后状态}", ExitCode.RULE_PARSE_FAILED)
    return {
        "前状态": 前状态,
        "后状态": 后状态,
        "触发事件": 触发事件,
        "时间": datetime.now().astimezone().isoformat(timespec="seconds"),
        "执行组件": 执行组件,
        "证据文件": 证据文件,
    }


def 追加状态(task: "L3执行任务", 后状态: str, 触发事件: str, 执行组件: str, 证据文件: str = "") -> None:
    前状态 = task.执行状态
    if 前状态 == 后状态:
        return
    change = 状态变更(前状态, 后状态, 触发事件, 执行组件, 证据文件)
    task.状态历史.append(change)
    task.执行状态 = 后状态


@dataclass
class L2修复单:
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


@dataclass
class L3执行任务:
    执行编号: str
    来源层: str
    来源文件: str
    ProjectHarness根: str
    任务类型: str
    输入材料: str
    IR输入: list[str]
    目标文件: str
    禁止修改文件: list[str]
    修复方向: str
    修复产物要求: str
    回流验收位置: str
    是否允许改正式正文: str
    是否需要备份: str
    执行状态: str = "RECEIVED"
    校验问题: list[str] = field(default_factory=list)
    状态历史: list[dict[str, str]] = field(default_factory=list)


@dataclass
class L3执行输出:
    执行编号: str
    执行状态: str
    实际读取文件: list[str]
    任务包文件: str
    分项任务文件: str
    任务依赖: list[str]
    约束: list[str]
    目标文件引用: str
    修复产物: str
    复验入口: str
    待复验问题: str
    断点记录: str
    execution_mode: str = "TASK_PLANNING_ONLY"
    prose_modified: bool = False
    task_package_created: bool = False
    awaiting_executor: bool = True


@dataclass
class L3报告:
    run_id: str
    输入文件: str
    输入修复单数量: int
    方法声明: str
    标准校验问题: list[str]
    协议规则摘要: dict[str, Any]
    任务单: list[L3执行任务]
    执行输出: list[L3执行输出]
    阻断任务: list[L3执行任务]
    protocol_rule_version: str
    schema_version: str = "xcue.l3-task-bundle/1.0"
    pipeline_run_id: str = ""
    stage_run_id: str = ""
    status: str = ""
    状态说明: str = ""
    execution_mode: str = "TASK_PLANNING_ONLY"
    prose_modified: bool = False
    task_package_created: bool = False
    awaiting_executor: bool = True
    input_artifacts: list[dict[str, Any]] = field(default_factory=list)
    output_artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
