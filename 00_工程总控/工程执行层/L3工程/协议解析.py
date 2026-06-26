from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
import sys

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 工程异常 import 工程错误
from 退出码 import ExitCode


REQUIRED_SECTIONS = {
    "L3-00": ["L3 定位", "L3 输入", "L3 输出", "L3 执行顺序", "文件权限矩阵"],
    "L3-01": ["文件", "权限"],
    "L3-02": ["正文", "候选"],
    "L3-03": ["验收", "回填"],
    "L3-04": ["版本", "回滚"],
    "L3-05": ["日志", "记录"],
    "L3-06": ["IR", "映射"],
    "L3-07": ["Project", "Harness"],
    "L3-99": ["总禁止", "阻断条件"],
}


@dataclass
class L3协议规则:
    状态机: list[str] = field(default_factory=list)
    异常状态: list[str] = field(default_factory=list)
    权限矩阵: dict[str, dict[str, str]] = field(default_factory=dict)
    任务字段: list[str] = field(default_factory=list)
    输出字段: list[str] = field(default_factory=list)
    执行顺序: list[str] = field(default_factory=list)
    IR推荐文件: list[str] = field(default_factory=list)
    候选必备目录: list[str] = field(default_factory=list)
    禁止项: list[str] = field(default_factory=list)


class 规则解析失败(工程错误):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("RULE_PARSE_FAILED: " + "；".join(errors), ExitCode.RULE_PARSE_FAILED)
        self.errors = errors


def 标准完整性(standards: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for name, sections in REQUIRED_SECTIONS.items():
        text = standards.get(name, "")
        lost = [section for section in sections if section not in text]
        if lost:
            errors.append(f"{name} 缺少：{'、'.join(lost)}")
    return errors


def _章节(text: str, title: str, level: int = 2) -> str:
    marker = "#" * level
    pattern = rf"(?ms)^{marker}\s+{re.escape(title)}.*?(?=^{marker}\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def _标题区块(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(rf"(?ms)^##\s+.*{pattern}.*?(?=^##\s+|\Z)", text)
        if match:
            return match.group(0)
    return ""


def _标记区块(text: str, block_id: str) -> str:
    pattern = rf"(?ms)<!--\s*XCUE:{re.escape(block_id)}:START\s*-->(.*?)<!--\s*XCUE:{re.escape(block_id)}:END\s*-->"
    matches = re.findall(pattern, text)
    if len(matches) > 1:
        raise 规则解析失败([f"L3-00#{block_id} 存在重复机器区块"])
    return matches[0].strip() if matches else ""


def _区块(text: str, block_id: str, title_patterns: list[str]) -> str:
    marked = _标记区块(text, block_id)
    if marked:
        return marked
    return _标题区块(text, title_patterns)


def _行号(text: str, fragment: str) -> int | None:
    if not fragment:
        return None
    index = text.find(fragment)
    if index < 0:
        return None
    return text[:index].count("\n") + 1


def _代码块(text: str) -> str:
    match = re.search(r"```(?:text|yaml)?\s*(.*?)```", text, re.S)
    return match.group(1).strip() if match else ""


def _表格(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] not in {"区域 / 文件类型", "区域"}:
            rows.append(cells)
    return rows


def _表头(text: str) -> list[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "---" not in stripped:
            return [cell.strip() for cell in stripped.strip("|").split("|")]
    return []


def _编号列表(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            items.append(re.sub(r"^\d+\.\s+", "", stripped).strip("。 "))
        elif stripped.startswith("- "):
            items.append(stripped[2:].strip("。 "))
    return items


def 解析规则(standards: dict[str, str]) -> L3协议规则:
    l300 = standards.get("L3-00", "")
    l306 = standards.get("L3-06", "")
    l307 = standards.get("L3-07", "")
    l399 = standards.get("L3-99", "")

    errors: list[str] = []

    state_section = _区块(l300, "L3_STATE_MACHINE", ["状态机"])
    state_block = _代码块(state_section)
    states = [line.strip() for line in state_block.splitlines() if line.strip() and line.strip() != "↓"]
    normal_states = [line for line in states if "/" not in line]
    abnormal_block = state_section.split("异常状态：", 1)[-1]
    abnormal_states = _代码块(abnormal_block).splitlines() if "异常状态：" in state_section else []
    if not normal_states:
        errors.append(f"L3-00#L3_STATE_MACHINE 缺少状态机步骤，line={_行号(l300, state_section)}")
    required_states = {
        "TASK_PACKAGE_CREATED",
        "AWAITING_EXECUTOR",
        "EXECUTION_STARTED",
        "EXECUTION_FAILED",
        "EXECUTION_COMPLETED",
        "ACCEPTANCE_PENDING",
        "ACCEPTED",
        "ROLLED_BACK",
    }
    missing_states = sorted(required_states - set(normal_states) - set(abnormal_states))
    if missing_states:
        errors.append(f"L3-00#L3_STATE_MACHINE 缺少必需状态：{'、'.join(missing_states)}")
    duplicated = sorted({state for state in normal_states if normal_states.count(state) > 1})
    if duplicated:
        errors.append(f"L3-00#L3_STATE_MACHINE 存在重复状态：{'、'.join(duplicated)}")

    permissions: dict[str, dict[str, str]] = {}
    permission_section = _区块(l300, "L3_PERMISSION_MATRIX", ["权限矩阵"])
    headers = _表头(permission_section)
    if not {"区域 / 文件类型", "默认权限", "说明"}.issubset(set(headers)):
        errors.append(f"L3-00#L3_PERMISSION_MATRIX 缺少权限矩阵必填列，line={_行号(l300, permission_section)}")
    for cells in _表格(permission_section):
        if len(cells) >= 3:
            permissions[cells[0]] = {"默认权限": cells[1], "说明": cells[2]}
    if not permissions:
        errors.append(f"L3-00#L3_PERMISSION_MATRIX 缺少权限矩阵内容，line={_行号(l300, permission_section)}")

    input_section = _区块(l300, "L3_TASK_INPUT_FIELDS", ["L3 输入", "任务输入"])
    output_section = _区块(l300, "L3_TASK_OUTPUT_FIELDS", ["L3 输出", "任务输出"])
    input_block = _代码块(input_section)
    output_block = _代码块(output_section)
    input_fields = [line.split(":", 1)[0].strip() for line in input_block.splitlines() if ":" in line and not line.startswith("L3_")]
    output_fields = [line.split(":", 1)[0].strip() for line in output_block.splitlines() if ":" in line and not line.startswith("L3_")]
    required_input = {"来源层", "来源文件", "任务类型", "输入材料", "IR输入", "目标文件", "禁止修改文件", "修复方向", "修复产物要求", "回流验收位置", "是否允许改正式正文", "是否需要备份"}
    required_output = {"执行编号", "执行状态", "实际读取文件", "任务包文件", "分项任务文件", "任务依赖", "约束", "目标文件引用", "修复产物", "复验入口", "待复验问题", "断点记录"}
    missing_input = sorted(required_input - set(input_fields))
    missing_output = sorted(required_output - set(output_fields))
    if missing_input:
        errors.append(f"L3-00#L3_TASK_INPUT_FIELDS 缺少字段：{'、'.join(missing_input)}，line={_行号(l300, input_section)}")
    if missing_output:
        errors.append(f"L3-00#L3_TASK_OUTPUT_FIELDS 缺少字段：{'、'.join(missing_output)}，line={_行号(l300, output_section)}")

    ir_files = re.findall(r"IR-\d+_[^\s│├└]+\.md", _章节(l306, "2. 推荐 IR 文件组"))
    candidate_dirs = _代码块(_章节(l307, "4.1 候选目录创建规则")).splitlines()
    candidate_dirs = [line.strip() for line in candidate_dirs if line.strip() and not line.strip().endswith(":")]
    execution_order = _编号列表(_区块(l300, "L3_EXECUTION_ORDER", ["执行顺序"]))
    forbidden = _编号列表(_区块(l399, "L3_FORBIDDEN", ["总禁止"]))
    if not execution_order:
        errors.append("L3-00#L3_EXECUTION_ORDER 缺少执行顺序")
    if not forbidden:
        errors.append("L3-99#L3_FORBIDDEN 缺少禁止项")
    if errors:
        raise 规则解析失败(errors)

    return L3协议规则(
        状态机=normal_states,
        异常状态=[line.strip() for line in abnormal_states if line.strip()],
        权限矩阵=permissions,
        任务字段=input_fields,
        输出字段=output_fields,
        执行顺序=execution_order,
        IR推荐文件=ir_files,
        候选必备目录=candidate_dirs,
        禁止项=forbidden,
    )
