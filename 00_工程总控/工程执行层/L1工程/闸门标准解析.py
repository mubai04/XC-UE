from __future__ import annotations

import re
from dataclasses import dataclass, field


REQUIRED_SECTIONS = {
    "L1-00": ["闸门接口总表", "统一输出格式", "流转规则", "禁止项"],
    "L1-01": ["定位", "失败类型", "统一输出格式", "通过标准", "禁止项"],
    "L1-02": ["核心公式", "失败类型", "统一输出格式", "通过标准", "禁止项"],
    "L1-03": ["功能锁", "发布锁", "投入意愿", "发布判定表", "每章验收输出格式"],
}


@dataclass
class L101规则:
    失败类型: list[str] = field(default_factory=list)
    通过标准: list[str] = field(default_factory=list)
    表现词: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class L102规则:
    公式: str = "I = E × V - C"
    不足条件: str = "E × V ≤ C"
    失败类型: list[str] = field(default_factory=list)
    通过标准: list[str] = field(default_factory=list)
    变量词: dict[str, list[str]] = field(default_factory=dict)
    低表现词: dict[str, list[str]] = field(default_factory=dict)
    通过阈值: dict[str, int] = field(default_factory=lambda: {"E": 3, "V": 3, "C_max": 3, "I_min": 6})


@dataclass
class L103规则:
    字数下限: int = 2200
    字数上限: int = 3000
    功能稿下限: int = 2000
    发布判定表: dict[str, str] = field(default_factory=dict)
    当章收益项: list[str] = field(default_factory=list)


@dataclass
class L15路由规则:
    目标模块: str
    修复产物: str
    回流闸门: str


@dataclass
class L1规则:
    L101: L101规则
    L102: L102规则
    L103: L103规则
    L15路由: dict[str, L15路由规则] = field(default_factory=dict)


class 规则解析错误(ValueError):
    pass


def 标准完整性(standards: dict[str, str]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for name, sections in REQUIRED_SECTIONS.items():
        text = standards.get(name, "")
        lost = [section for section in sections if section not in text]
        if lost:
            missing[name] = lost
    return missing


def _章节(text: str, title: str) -> str:
    pattern = rf"(?ms)^##+\s+{re.escape(title)}.*?(?=^##+\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def _子章节(text: str, title: str) -> str:
    pattern = rf"(?ms)^###+\s+{re.escape(title)}.*?(?=^###+\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def _代码块列表(text: str) -> list[str]:
    match = re.search(r"```text\s*(.*?)```", text, re.S)
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def _项目符号列表(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("* ", "- ")):
            items.append(stripped[2:].strip())
    return items


def _解析L101(text: str) -> L101规则:
    failure_types = _代码块列表(_章节(text, "7. 失败类型"))
    pass_rules = _代码块列表(_章节(text, "14. 通过标准"))
    signals: dict[str, list[str]] = {}
    for failure_type in failure_types:
        section_no = {
            "文风失败": "8.1 文风失败",
            "叙事失败": "8.2 叙事失败",
            "角色失败": "8.3 角色失败",
            "创意设定失败": "8.4 创意设定失败",
            "AI味失败": "8.5 AI味失败",
            "技术护栏失败": "8.6 技术护栏失败",
            "输入不足": "8.7 输入不足",
        }.get(failure_type)
        if section_no:
            signals[failure_type] = _代码块列表(_子章节(text, section_no))
    return L101规则(failure_types, pass_rules, signals)


def _解析L102(text: str) -> L102规则:
    failure_types = _代码块列表(_章节(text, "7. 失败类型"))
    pass_rules = _代码块列表(_章节(text, "14. 通过标准"))
    formula_match = re.search(r"I\s*=\s*E\s*[×x*]\s*V\s*-\s*C", text)
    insufficient_match = re.search(r"E\s*[×x*]\s*V\s*≤\s*C", text)
    if not formula_match:
        raise 规则解析错误("L1-02 缺少机器可解析公式：I = E × V - C")
    if not insufficient_match:
        raise 规则解析错误("L1-02 缺少机器可解析不足条件：E × V ≤ C")
    variables = {
        "E": _代码块列表(_子章节(text, "4.1 E：即时情绪反馈")),
        "V": _代码块列表(_子章节(text, "4.2 V：未来价值预期")),
        "C": _代码块列表(_子章节(text, "4.3 C：认知成本")),
    }
    low_signals = {
        "E低：即时情绪反馈弱": _代码块列表(_子章节(text, "8.1 E 低")),
        "V低：未来价值预期弱": _代码块列表(_子章节(text, "8.2 V 低")),
        "C高：认知成本过高": _代码块列表(_子章节(text, "8.3 C 高")),
        "入口弱": _代码块列表(_子章节(text, "8.4 入口弱")),
        "章末弱": _代码块列表(_子章节(text, "8.5 章末弱")),
        "弃读点明显": _代码块列表(_子章节(text, "8.6 弃读点明显")),
    }
    missing_variables = [key for key, values in variables.items() if not values]
    if missing_variables:
        raise 规则解析错误(f"L1-02 缺少变量词表：{', '.join(missing_variables)}")
    return L102规则(
        公式=formula_match.group(0),
        不足条件=insufficient_match.group(0),
        失败类型=failure_types,
        通过标准=pass_rules,
        变量词=variables,
        低表现词=low_signals,
    )


def _解析L103(text: str) -> L103规则:
    ranges = re.findall(r"(\d{4})\s*[–-]\s*(\d{4})\s*字", text)
    if not ranges:
        raise 规则解析错误("L1-03 缺少机器可解析字数范围")
    lower, upper = (int(ranges[0][0]), int(ranges[0][1]))
    low_match = re.search(r"低于\s*(\d{4})\s*字", text)
    if not low_match:
        raise 规则解析错误("L1-03 缺少机器可解析功能稿下限")
    function_floor = int(low_match.group(1))

    judgement: dict[str, str] = {}
    for line in _章节(text, "发布判定表").splitlines():
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] != "检查项":
            judgement[cells[0]] = cells[1]

    benefit_section = re.search(r"(?ms)当章收益至少有一项：\s*(.*?)(?=\n\n章末追读必须回答：)", text)
    benefits = _项目符号列表(benefit_section.group(1)) if benefit_section else []
    if not judgement:
        raise 规则解析错误("L1-03 缺少发布判定表")
    if not benefits:
        raise 规则解析错误("L1-03 缺少当章收益项")
    return L103规则(lower, upper, function_floor, judgement, benefits)


def 解析规则(standards: dict[str, str]) -> L1规则:
    return L1规则(
        L101=_解析L101(standards.get("L1-01", "")),
        L102=_解析L102(standards.get("L1-02", "")),
        L103=_解析L103(standards.get("L1-03", "")),
    )
