from __future__ import annotations

import json
from pathlib import Path
import sys

from L2模型 import 失败输入, 证据

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 标准加载器 import 加载标准文本, 标准记录, 生产模式


def 读文本(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    return path.read_text(encoding="utf-8-sig")


def L2标准路径(root: Path) -> dict[str, Path]:
    base = root / "40_L2_正式能力层"
    files = {
        "L2-00": base / "L2-00_正式能力层定义_v0.2.md",
        "L2-01": base / "L2-01_叙事结构能力_v0.3.1_边界修正版.md",
        "L2-02": base / "L2-02_文风语言能力_v0.3_真源绑定版.md",
        "L2-03": base / "L2-03_角色心理能力_v0.1.1_自检修正版.md",
        "L2-04": base / "L2-04_创意设定能力_v0.2_根部结构图绑定版.md",
        "L2-05": base / "L2-05_市场体验能力_v0.1.1_自检修正版.md",
        "L2-06": base / "L2-06_系统一致性与状态管理能力_v0.3.1_技术根修正版.md",
        "L2-99": base / "L2-99_能力层接口总表_v0.1.1_自检修正版.md",
    }
    return files


def L2路由规则路径(root: Path) -> Path:
    return root / "00_工程总控" / "工程执行层" / "L2工程" / "routes.json"


def 读L2标准(root: Path, standard_mode: str = 生产模式) -> dict[str, str]:
    texts, _records = 读L2标准与记录(root, standard_mode)
    return texts


def 读L2标准与记录(root: Path, standard_mode: str = 生产模式) -> tuple[dict[str, str], list[标准记录]]:
    return 加载标准文本(root, L2标准路径(root), standard_mode)


def 最新L1失败包(root: Path) -> Path:
    raise RuntimeError("P0 后生产路径禁止按修改时间读取最新 L1 失败包；请显式传入 --failure-packet。")


def 读失败包(path: Path) -> list[失败输入]:
    raw = json.loads(读文本(path))
    if isinstance(raw, dict):
        raw = raw.get("items", [])
    items: list[失败输入] = []
    for item in raw:
        evidence = [证据(e.get("段落"), e.get("摘句", "")) for e in item.get("证据", [])]
        items.append(
            失败输入(
                来源闸门=item.get("闸门", ""),
                名称=item.get("名称", ""),
                状态=item.get("状态", ""),
                说明=item.get("说明", ""),
                证据=evidence,
                严重级别=item.get("严重级别", ""),
                失败类型=item.get("失败类型", ""),
                候选模块=item.get("候选模块", ""),
                回流验收位置=item.get("回流验收位置", ""),
                修复方向=item.get("修复方向", ""),
            )
        )
    return items
