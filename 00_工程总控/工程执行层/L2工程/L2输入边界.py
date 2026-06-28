from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from L2模型 import 失败输入, 接口判断
from 工程异常 import 输入错误

RULES_PATH = Path(__file__).resolve().parent / "L2输入边界规则.json"

_L2_UPSTREAM_PACKAGE_REQUIRED = "L2_UPSTREAM_PACKAGE_REQUIRED"
_INPUT_REQUIRED = "INPUT_REQUIRED"
_RETURN_TO_L1_5 = "RETURN_TO_L1_5"
_LEGACY_EXPLICIT_ONLY = "LEGACY_EXPLICIT_ONLY"

_NAME_IN_EVIDENCE = re.compile(r"[\u4e00-\u9fff]{2,4}")


@dataclass
class 边界校验结果:
    action: str = "OK"
    code: str = ""
    message: str = ""
    missing: list[str] = field(default_factory=list)
    reroute_reason: str = ""
    evidence_gaps: list[str] = field(default_factory=list)
    suggested_domain: str = ""


def 加载输入边界规则(path: Path | None = None) -> dict[str, Any]:
    fp = path or RULES_PATH
    return json.loads(fp.read_text(encoding="utf-8-sig"))


def 规则路径(root: Path) -> Path:
    return root / "00_工程总控" / "工程执行层" / "L2工程" / "L2输入边界规则.json"


def 校验裸章节入口(*, chapter_path: str | Path | None, l15_report_path: str | Path | None) -> None:
    if chapter_path and not l15_report_path:
        raise 输入错误(f"{_L2_UPSTREAM_PACKAGE_REQUIRED}: 章节正文不能单独启动 L2")


def 校验正式入口模式(*, l15_report: bool, failure_packet_only: bool) -> str:
    if l15_report:
        return "FORMAL"
    if failure_packet_only:
        return _LEGACY_EXPLICIT_ONLY
    raise 输入错误("L2 必须提供 --l15-report（正式）或 --failure-packet（LEGACY_EXPLICIT_ONLY）")


def 校验L15路由报告(report: dict[str, Any]) -> tuple[str, list[str]]:
    final_status = str(report.get("final_status", "")).strip()
    blockers = [str(x) for x in report.get("blockers", []) if str(x).strip()]
    if final_status != "ROUTED":
        return final_status, blockers
    target = str(report.get("target_module", "")).strip()
    if not target or not target.startswith("L2-"):
        blockers = blockers or ["L1.5 报告缺少有效 target_module"]
        return "INPUT_REQUIRED", blockers
    return final_status, blockers


def _章节存在(chapter_path: str, repo_root: Path | None) -> bool:
    if not chapter_path.strip():
        return False
    p = Path(chapter_path)
    if p.is_absolute():
        return p.is_file()
    if repo_root is not None:
        return (repo_root / p).is_file()
    return p.is_file()


def _从证据提取角色名(item: 失败输入) -> set[str]:
    names: set[str] = set()
    for ev in item.证据:
        text = f"{ev.摘句 or ''}"
        for m in _NAME_IN_EVIDENCE.findall(text):
            if len(m) >= 2:
                names.add(m)
    blob = f"{item.说明} {item.失败类型} {item.修复方向}"
    for m in _NAME_IN_EVIDENCE.findall(blob):
        if len(m) >= 2:
            names.add(m)
    return names


def 过滤相关角色IR(ir_dir: Path | None, item: 失败输入) -> list[Path]:
    """返回 L2-03 可读取的角色 IR；排除文件名不含角色/心理/人物标签的 IR。"""
    if ir_dir is None or not ir_dir.is_dir():
        return []
    selected: list[Path] = []
    for path in sorted(ir_dir.glob("IR-*.md")):
        name = path.name
        if any(k in name for k in ("角色", "心理", "人物")):
            selected.append(path)
    return selected


def 过滤相关设定IR(ir_dir: Path | None, item: 失败输入) -> list[Path]:
    if ir_dir is None or not ir_dir.is_dir():
        return []
    selected: list[Path] = []
    for path in sorted(ir_dir.glob("IR-*.md")):
        name = path.name
        if any(k in name for k in ("世界", "约束", "规则", "设定", "IR-02")):
            selected.append(path)
    return selected


def _是否工程技术问题(item: 失败输入, rules: dict[str, Any]) -> bool:
    blob = f"{item.失败类型} {item.说明} {item.名称}"
    return any(k in blob for k in rules.get("engineering_failure_types", []))


def _是否外部运营问题(item: 失败输入, rules: dict[str, Any]) -> bool:
    blob = f"{item.失败类型} {item.说明} {item.名称}"
    return any(k in blob for k in rules.get("external_ops_failure_types", []))


def 校验模块输入边界(
    target_module: str,
    item: 失败输入,
    *,
    chapter_path: str = "",
    repo_root: Path | None = None,
    rules: dict[str, Any] | None = None,
) -> 边界校验结果:
    rules = rules or 加载输入边界规则()
    mod_rules = rules.get("modules", {}).get(target_module)
    if not mod_rules:
        return 边界校验结果(
            action=_RETURN_TO_L1_5,
            code=_RETURN_TO_L1_5,
            message=f"未知模块 {target_module}",
            reroute_reason="模块无边界规则",
            suggested_domain="L1.5",
        )

    if mod_rules.get("forbid_engineering_issues") and _是否工程技术问题(item, rules):
        return 边界校验结果(
            action=_RETURN_TO_L1_5,
            code=_RETURN_TO_L1_5,
            message="工程技术阻断不属于 L2-06 创作诊断",
            reroute_reason="failure_type 属于工程技术问题",
            evidence_gaps=[item.失败类型],
            suggested_domain="工程运维",
        )

    if mod_rules.get("forbid_external_ops_metrics") and _是否外部运营问题(item, rules):
        return 边界校验结果(
            action=_RETURN_TO_L1_5,
            code=_RETURN_TO_L1_5,
            message="外部运营指标不是 L2-05 默认输入",
            reroute_reason="failure_type 含外部运营指标",
            evidence_gaps=[item.失败类型],
            suggested_domain="上游明确提供后再路由",
        )

    needs_chapter = bool(mod_rules.get("allow_full_current_chapter"))
    if needs_chapter and not _章节存在(chapter_path, repo_root):
        return 边界校验结果(
            action=rules["actions"]["input_required"],
            code=_INPUT_REQUIRED,
            message=f"{target_module} 需要当前章节完整正文",
            missing=["chapter_path"],
        )

    if target_module == "L2-03":
        ir_dir = None
        if chapter_path and repo_root is not None:
            ir_dir = (repo_root / Path(chapter_path).parent.parent / "IR").resolve()
        if mod_rules.get("allow_ir") == "related_character_only" and ir_dir and ir_dir.is_dir():
            if not 过滤相关角色IR(ir_dir, item) and _从证据提取角色名(item):
                return 边界校验结果(
                    action=rules["actions"]["input_required"],
                    code=_INPUT_REQUIRED,
                    message="L2-03 需要相关角色 IR",
                    missing=["related_character_ir"],
                )

    if target_module == "L2-04":
        ir_dir = None
        if chapter_path and repo_root is not None:
            ir_dir = (repo_root / Path(chapter_path).parent.parent / "IR").resolve()
        if mod_rules.get("allow_ir") and ir_dir and ir_dir.is_dir():
            if not 过滤相关设定IR(ir_dir, item):
                pass  # IR 可选增强，缺失不阻断

    return 边界校验结果(action="OK")


def 构建边界阻断判断(
    item: 失败输入,
    target_module: str,
    boundary: 边界校验结果,
) -> 接口判断:
    if boundary.action == _INPUT_REQUIRED:
        return 接口判断(
            来源闸门=item.来源闸门,
            输入来源模式="L1.5路由报告",
            输入问题=item.说明,
            初步归属=target_module,
            主候选模块=target_module,
            接口失败类型="INPUT_REQUIRED",
            判断依据=boundary.message,
            建议动作=[f"补齐：{', '.join(boundary.missing)}"],
            回流验收位置=item.回流验收位置 or item.来源闸门,
            最终状态="输入不足",
        )
    return 接口判断(
        来源闸门=item.来源闸门,
        输入来源模式="L1.5路由报告",
        输入问题=item.说明,
        初步归属="L1.5",
        主候选模块=target_module,
        接口失败类型="RETURN_TO_L1_5",
        判断依据=boundary.reroute_reason or boundary.message,
        建议动作=["回 L1.5 重路由"],
        回流验收位置=item.回流验收位置 or item.来源闸门,
        最终状态="回L1.5",
    )


def 模块允许完整当前章(target_module: str, rules: dict[str, Any] | None = None) -> bool:
    rules = rules or 加载输入边界规则()
    return bool(rules.get("modules", {}).get(target_module, {}).get("allow_full_current_chapter"))


def L2阶段禁止候选正文() -> bool:
    return True
