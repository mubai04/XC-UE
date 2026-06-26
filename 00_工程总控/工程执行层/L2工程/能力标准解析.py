from __future__ import annotations

import re
from dataclasses import dataclass, field

from 路由规则加载 import 路由规则集


REQUIRED_SECTIONS = {
    "L2-00": ["定位", "能力", "边界"],
    "L2-01": ["输入边界", "输出边界", "回流验收"],
    "L2-02": ["输入边界", "输出边界", "回流验收"],
    "L2-03": ["输入边界", "输出边界", "回流验收"],
    "L2-04": ["输入边界", "输出边界", "回流验收"],
    "L2-05": ["输出格式", "回流验收位置", "与其他 L2 的边界"],
    "L2-06": ["标准输入", "标准输出", "回流验收"],
    "L2-99": ["接口层四不原则", "快速路由表", "统一输出接口", "标准输出格式"],
}


@dataclass
class 失败规则:
    编号: str
    名称: str
    定义: str = ""
    表现: list[str] = field(default_factory=list)
    修复规则: list[str] = field(default_factory=list)
    验收标准: list[str] = field(default_factory=list)
    匹配关键词: list[str] = field(default_factory=list)
    规则版本: str = ""


@dataclass
class 能力规则:
    模块: str
    标准来源: str
    输入关键词: list[str] = field(default_factory=list)
    输出产物: str = ""
    默认回流: list[str] = field(default_factory=list)
    失败类型库: list[失败规则] = field(default_factory=list)
    修复动作库: list[str] = field(default_factory=list)
    回流验收问题: list[str] = field(default_factory=list)
    禁止项: list[str] = field(default_factory=list)
    默认动作: dict[str, list[str]] = field(default_factory=dict)
    规则版本: str = ""


@dataclass
class L2规则:
    路由表: list[tuple[list[str], str]] = field(default_factory=list)
    能力接口表: dict[str, 能力规则] = field(default_factory=dict)
    能力规则: dict[str, 能力规则] = field(default_factory=dict)
    接口失败类型: dict[str, str] = field(default_factory=dict)
    路由规则集: 路由规则集 | None = None


def 标准完整性(standards: dict[str, str]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for name, sections in REQUIRED_SECTIONS.items():
        text = standards.get(name, "")
        lost = [section for section in sections if section not in text]
        if lost:
            missing[name] = lost
    return missing


def _章节(text: str, title: str) -> str:
    pattern = rf"(?ms)^##\s+{re.escape(title)}.*?(?=^##\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def _任意级标题章节(text: str, title_keyword: str) -> str:
    pattern = rf"(?ms)^#+\s+[^\n]*{re.escape(title_keyword)}[^\n]*\n.*?(?=^#+\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def _代码块列表(text: str) -> list[str]:
    match = re.search(r"```(?:text)?\s*(.*?)```", text, re.S)
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def _列表行(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            items.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
        elif stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
    return items


def _禁止边界句(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "|", "```")):
            continue
        if any(word in stripped for word in ("不得", "不能", "禁止")):
            items.append(stripped)
    return items


def _解析禁止项(text: str) -> list[str]:
    sections = [
        _任意级标题章节(text, "禁止输入"),
        _任意级标题章节(text, "禁止项"),
    ]
    items: list[str] = []
    for section in sections:
        items.extend(_代码块列表(section))
        items.extend(_列表行(section))
    if not items:
        items = _禁止边界句(text)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _表格(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] not in {"问题表现", "模块", "编号", "检查项"}:
            rows.append(cells)
    return rows


def _拆关键词(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"、|/|，|,|\s+", text) if part.strip()]


def _解析路由表(text: str) -> list[tuple[list[str], str]]:
    routes: list[tuple[list[str], str]] = []
    for cells in _表格(_章节(text, "10. 快速路由表")):
        if len(cells) >= 2:
            routes.append((_拆关键词(cells[0]), cells[1].replace(" ", "")))
    return routes


def _解析能力接口(text: str) -> dict[str, 能力规则]:
    result: dict[str, 能力规则] = {}
    for cells in _表格(_章节(text, "13. 六大能力接口表")):
        if len(cells) >= 4 and cells[0].startswith("L2-"):
            module = cells[0]
            result[module] = 能力规则(
                模块=module,
                标准来源="L2-99",
                输入关键词=_拆关键词(cells[1]),
                输出产物=cells[2],
                默认回流=[part.strip() for part in re.split(r"/|、", cells[3]) if part.strip()],
            )
    return result


def _解析接口失败类型(text: str) -> dict[str, str]:
    items: dict[str, str] = {}
    for cells in _表格(_章节(text, "14. 接口失败类型 IF-P1 至 IF-P10")):
        if len(cells) >= 3 and cells[0].startswith("IF-"):
            items[cells[0]] = f"{cells[1]}：{cells[2]}"
    return items


def _解析动作库(section: str) -> list[str]:
    block_items = _代码块列表(section)
    if block_items:
        actions = []
        for line in block_items:
            cleaned = line.rstrip("：:")
            if cleaned and not cleaned.startswith(("将", "删除", "当", "窗口", "当前", "输出", "修复")):
                actions.append(cleaned)
        if actions:
            return actions
    headings = re.findall(r"(?m)^###\s+(A\d+)\s+(.+)$", section)
    if headings:
        return [f"{code} {name.strip()}" for code, name in headings]
    return _列表行(section)


def _解析失败规则(text: str, section_title: str) -> list[失败规则]:
    section = _章节(text, section_title)
    rules: list[失败规则] = []
    matches = list(re.finditer(r"(?m)^###\s+((?:F|P)\d+)\s+(.+)$", section))
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section)
        body = section[start:end]
        definition = ""
        signals: list[str] = []
        define_match = re.search(r"定义：\s*(?:```text\s*(.*?)```|([^\n]+))", body, re.S)
        if define_match:
            definition = (define_match.group(1) or define_match.group(2) or "").strip()
        else:
            p_match = re.search(r"表现：([^\n]+)", body)
            if p_match:
                definition = p_match.group(1).strip()
                signals = [definition]
            else:
                plain = [line.strip() for line in body.splitlines() if line.strip() and not line.strip().endswith("：")]
                definition = plain[0] if plain else ""
        if "表现：" in body and not signals:
            signals = _代码块列表(body[body.find("表现：") :])
            if not signals:
                signal_match = re.search(r"表现：([^\n]+)", body)
                signals = [signal_match.group(1).strip()] if signal_match else []
        repair = _代码块列表(body[body.find("修复规则：") :]) if "修复规则：" in body else []
        if not repair:
            repair_match = re.search(r"修复：([^\n]+)", body)
            if repair_match:
                repair = [repair_match.group(1).strip("。")]
        acceptance = _代码块列表(body[body.find("验收标准：") :]) if "验收标准：" in body else []
        rules.append(
            失败规则(
                编号=match.group(1),
                名称=match.group(2).strip(),
                定义=definition,
                表现=signals,
                修复规则=repair,
                验收标准=acceptance,
            )
        )
    return rules


def _解析能力(module: str, text: str, interface: 能力规则 | None = None) -> 能力规则:
    titles = {
        "L2-01": "12. 叙事结构失败类型",
        "L2-02": "12. 文风语言失败类型",
        "L2-03": "12. 角色心理失败类型",
        "L2-04": "12. 创意设定失败类型",
        "L2-05": "11. 主失败类型（P1-P12）",
        "L2-06": "13. 失败类型库",
    }
    action_titles = {
        "L2-01": "14. 修复动作库",
        "L2-02": "15. 修复动作库",
        "L2-03": "13. 修复动作库",
        "L2-04": "13. 修复动作库",
        "L2-05": "12. 修复动作库",
        "L2-06": "14. 修复动作库",
    }
    acceptance_titles = {
        "L2-01": "15. 回流验收",
        "L2-02": "16. 回流验收",
        "L2-03": "14. 回流验收",
        "L2-04": "14. 回流验收",
        "L2-05": "14. 验收十四问",
        "L2-06": "15. 回流验收",
    }
    base = interface or 能力规则(module, module)
    base.标准来源 = module
    base.失败类型库 = _解析失败规则(text, titles[module])
    base.修复动作库 = _解析动作库(_章节(text, action_titles[module]))
    acceptance_section = _章节(text, acceptance_titles[module])
    acceptance_source = acceptance_section
    if "验收问题：" in acceptance_section:
        acceptance_source = acceptance_section[acceptance_section.find("验收问题：") :]
    base.回流验收问题 = _代码块列表(acceptance_source) or _列表行(acceptance_source)
    base.禁止项 = _解析禁止项(text)
    return base


def 解析规则(standards: dict[str, str]) -> L2规则:
    l299 = standards.get("L2-99", "")
    interface = _解析能力接口(l299)
    abilities: dict[str, 能力规则] = {}
    for module in ["L2-01", "L2-02", "L2-03", "L2-04", "L2-05", "L2-06"]:
        abilities[module] = _解析能力(module, standards.get(module, ""), interface.get(module))
    return L2规则(
        路由表=_解析路由表(l299),
        能力接口表=interface,
        能力规则=abilities,
        接口失败类型=_解析接口失败类型(l299),
    )
