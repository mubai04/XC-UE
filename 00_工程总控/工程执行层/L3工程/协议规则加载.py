from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from 工程异常 import 工程错误
from L3模型 import L3协议规则
from 退出码 import ExitCode


REQUIRED_SCHEMA = "xcue.l3-protocol-rules/1.0"
REQUIRED_MODULES = {"L2-01", "L2-02", "L2-03", "L2-04", "L2-05", "L2-06", "*"}
REQUIRED_TASK_FIELDS = {
    "来源层",
    "来源文件",
    "ProjectHarness根",
    "任务类型",
    "输入材料",
    "IR输入",
    "目标文件",
    "禁止修改文件",
    "修复方向",
    "修复产物要求",
    "回流验收位置",
    "是否允许改正式正文",
    "是否需要备份",
}
REQUIRED_OUTPUT_FIELDS = {
    "执行编号",
    "执行状态",
    "实际读取文件",
    "任务包文件",
    "分项任务文件",
    "任务依赖",
    "约束",
    "目标文件引用",
    "修复产物",
    "复验入口",
    "待复验问题",
    "断点记录",
}
REQUIRED_STATES = {
    "TASK_PACKAGE_CREATED",
    "AWAITING_EXECUTOR",
    "EXECUTION_STARTED",
    "EXECUTION_FAILED",
    "EXECUTION_COMPLETED",
    "ACCEPTANCE_PENDING",
    "ACCEPTED",
    "ROLLED_BACK",
}


class 协议规则加载错误(工程错误):
    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.RULE_PARSE_FAILED)


def L3协议规则路径(root: Path) -> Path:
    return root / "00_工程总控" / "工程执行层" / "L3工程" / "protocol_rules.json"


def 加载协议规则(path: Path) -> L3协议规则:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise 协议规则加载错误(f"L3 结构化协议规则不可读：{path}") from exc
    try:
        raw = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise 协议规则加载错误(f"L3 结构化协议规则解析失败：{path}") from exc

    _校验根结构(raw)
    return L3协议规则(
        规则版本=_非空字符串(raw["version"], "version"),
        状态机=_字符串列表(raw["state_machine"], "state_machine"),
        异常状态=_字符串列表(raw["abnormal_states"], "abnormal_states"),
        状态跳转=_状态跳转(raw["state_transitions"]),
        权限矩阵=_权限矩阵(raw["permission_matrix"]),
        任务字段=_字符串列表(raw["task_fields"], "task_fields"),
        输出字段=_字符串列表(raw["output_fields"], "output_fields"),
        执行顺序=_字符串列表(raw["execution_order"], "execution_order"),
        IR推荐文件=_字符串列表(raw["ir_recommended_files"], "ir_recommended_files"),
        候选必备目录=_字符串列表(raw["candidate_required_dirs"], "candidate_required_dirs"),
        IR映射=_字符串列表字典(raw["ir_mapping"], "ir_mapping"),
        任务类型规则=_对象列表(raw["task_type_rules"], "task_type_rules"),
        正文章节Glob=_非空字符串(raw["formal_chapter_glob"], "formal_chapter_glob"),
        候选目标模板=_非空字符串(raw["candidate_target_pattern"], "candidate_target_pattern"),
        默认禁止目标=_字符串列表(raw["default_forbidden_targets"], "default_forbidden_targets"),
        是否允许改正式正文=_是否值(raw["formal_prose_modification"], "formal_prose_modification"),
        是否需要备份=_备份值(raw["backup_requirement"], "backup_requirement"),
        合法回流位置=set(_字符串列表(raw["valid_return_positions"], "valid_return_positions")),
        禁止项=_字符串列表(raw["forbidden"], "forbidden"),
    )


def _校验根结构(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise 协议规则加载错误("L3 结构化协议规则根节点必须是对象")
    required = [
        "schema_version",
        "version",
        "status",
        "scope",
        "state_machine",
        "abnormal_states",
        "state_transitions",
        "permission_matrix",
        "task_fields",
        "output_fields",
        "execution_order",
        "ir_recommended_files",
        "candidate_required_dirs",
        "ir_mapping",
        "task_type_rules",
        "formal_chapter_glob",
        "candidate_target_pattern",
        "default_forbidden_targets",
        "formal_prose_modification",
        "backup_requirement",
        "valid_return_positions",
        "forbidden",
    ]
    for key in required:
        if key not in raw:
            raise 协议规则加载错误(f"L3 结构化协议规则缺少字段：{key}")
    if raw["schema_version"] != REQUIRED_SCHEMA:
        raise 协议规则加载错误("L3 结构化协议规则 schema_version 不匹配")
    if raw["status"] != "active":
        raise 协议规则加载错误("L3 结构化协议规则 status 必须为 active")
    _非空字符串(raw["version"], "version")
    _非空字符串(raw["scope"], "scope")
    states = _字符串列表(raw["state_machine"], "state_machine")
    abnormal = _字符串列表(raw["abnormal_states"], "abnormal_states")
    missing_states = sorted(REQUIRED_STATES - set(states) - set(abnormal))
    if missing_states:
        raise 协议规则加载错误(f"L3 结构化协议规则缺少状态：{'、'.join(missing_states)}")
    duplicates = sorted({state for state in states if states.count(state) > 1})
    if duplicates:
        raise 协议规则加载错误(f"L3 结构化协议规则状态重复：{'、'.join(duplicates)}")
    task_fields = set(_字符串列表(raw["task_fields"], "task_fields"))
    output_fields = set(_字符串列表(raw["output_fields"], "output_fields"))
    missing_task_fields = sorted(REQUIRED_TASK_FIELDS - task_fields)
    missing_output_fields = sorted(REQUIRED_OUTPUT_FIELDS - output_fields)
    if missing_task_fields:
        raise 协议规则加载错误(f"L3 结构化协议规则缺少任务字段：{'、'.join(missing_task_fields)}")
    if missing_output_fields:
        raise 协议规则加载错误(f"L3 结构化协议规则缺少输出字段：{'、'.join(missing_output_fields)}")
    missing_modules = sorted(REQUIRED_MODULES - set(_字符串列表字典(raw["ir_mapping"], "ir_mapping")))
    if missing_modules:
        raise 协议规则加载错误(f"L3 结构化协议规则缺少 IR 映射：{'、'.join(missing_modules)}")
    if not _对象列表(raw["task_type_rules"], "task_type_rules"):
        raise 协议规则加载错误("L3 结构化协议规则 task_type_rules 不能为空")
    if not _权限矩阵(raw["permission_matrix"]):
        raise 协议规则加载错误("L3 结构化协议规则 permission_matrix 不能为空")
    if not _字符串列表(raw["execution_order"], "execution_order"):
        raise 协议规则加载错误("L3 结构化协议规则 execution_order 不能为空")
    if not _字符串列表(raw["forbidden"], "forbidden"):
        raise 协议规则加载错误("L3 结构化协议规则 forbidden 不能为空")


def _状态跳转(value: Any) -> dict[str, set[str]]:
    raw = _字符串列表字典(value, "state_transitions")
    if "RECEIVED" not in raw:
        raise 协议规则加载错误("L3 结构化协议规则 state_transitions 缺少 RECEIVED")
    return {state: set(targets) for state, targets in raw.items()}


def _权限矩阵(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        raise 协议规则加载错误("permission_matrix 必须是对象")
    result: dict[str, dict[str, str]] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise 协议规则加载错误("permission_matrix 必须是对象字典")
        result[key] = _字符串字典(item, f"permission_matrix.{key}")
    return result


def _对象列表(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise 协议规则加载错误(f"{label} 必须是对象数组")
    return value


def _字符串列表(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise 协议规则加载错误(f"{label} 必须是字符串数组")
    return [item for item in value if item]


def _字符串字典(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise 协议规则加载错误(f"{label} 必须是字符串字典")
    return dict(value)


def _字符串列表字典(value: Any, label: str) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise 协议规则加载错误(f"{label} 必须是字符串数组字典")
    result: dict[str, list[str]] = {}
    for key, items in value.items():
        if not isinstance(key, str):
            raise 协议规则加载错误(f"{label} 键必须是字符串")
        result[key] = _字符串列表(items, f"{label}.{key}")
    return result


def _非空字符串(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise 协议规则加载错误(f"{label} 必须是非空字符串")
    return value.strip()


def _是否值(value: Any, label: str) -> str:
    text = _非空字符串(value, label)
    if text not in {"是", "否"}:
        raise 协议规则加载错误(f"{label} 必须为 是 或 否")
    return text


def _备份值(value: Any, label: str) -> str:
    text = _非空字符串(value, label)
    if text not in {"是", "否", "不适用"}:
        raise 协议规则加载错误(f"{label} 必须为 是、否 或 不适用")
    return text
