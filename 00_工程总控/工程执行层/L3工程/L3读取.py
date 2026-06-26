from __future__ import annotations

import json
from pathlib import Path
import sys

from L3模型 import L2修复单

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 标准加载器 import 加载标准文本, 标准记录, 生产模式


def 读文本(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    return path.read_text(encoding="utf-8-sig")


def L3标准路径(root: Path) -> dict[str, Path]:
    base = root / "50_L3_执行协议层"
    files = {
        "L3-00": base / "L3-00_执行协议总表_v0.1.2.md",
        "L3-01": base / "L3-01_Cursor文件操作协议_v0.1.2.md",
        "L3-02": base / "L3-02_正文生成与改写任务协议_v0.1.2.md",
        "L3-03": base / "L3-03_验收回填协议_v0.1.2.md",
        "L3-04": base / "L3-04_版本与回滚协议_v0.1.2.md",
        "L3-05": base / "L3-05_日志记录协议_v0.1.2.md",
        "L3-06": base / "L3-06_IR输入映射协议_v0.1.2.md",
        "L3-07": base / "L3-07_ProjectHarness运行协议_v0.1.2.md",
        "L3-99": base / "L3-99_执行禁止项_v0.1.2.md",
    }
    return files


def 读L3标准(root: Path, standard_mode: str = 生产模式) -> dict[str, str]:
    texts, _records = 读L3标准与记录(root, standard_mode)
    return texts


def 读L3标准与记录(root: Path, standard_mode: str = 生产模式) -> tuple[dict[str, str], list[标准记录]]:
    return 加载标准文本(root, L3标准路径(root), standard_mode)


def 最新L2报告(root: Path) -> Path:
    raise RuntimeError("P0 后生产路径禁止按修改时间读取最新 L2 报告；请显式传入 --l2-report。")


def 读L2修复单(path: Path) -> list[L2修复单]:
    data = json.loads(读文本(path))
    if data.get("status") == "BLOCKED":
        raise ValueError(f"L2 报告已阻断，L3 不得继续生成任务包：{path}")
    forms = data.get("修复单", [])
    result: list[L2修复单] = []
    for form in forms:
        result.append(
            L2修复单(
                修复单类型=form.get("修复单类型", ""),
                来源闸门=form.get("来源闸门", ""),
                接收模块=form.get("接收模块", ""),
                输入问题=form.get("输入问题", ""),
                主失败类型=form.get("主失败类型", ""),
                次失败类型=form.get("次失败类型", ""),
                修复动作=form.get("修复动作", ""),
                修复产物=form.get("修复产物", ""),
                验收问题=form.get("验收问题", ""),
                回流位置=form.get("回流位置", ""),
                是否需要其他L2辅助=form.get("是否需要其他L2辅助", ""),
                是否需要回L15重路由=form.get("是否需要回L15重路由", ""),
                最终状态=form.get("最终状态", ""),
            )
        )
    return result
