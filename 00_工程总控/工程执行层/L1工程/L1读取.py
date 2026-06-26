from __future__ import annotations

from pathlib import Path

import sys

公共组件 = Path(__file__).resolve().parents[1] / "公共组件"
if str(公共组件) not in sys.path:
    sys.path.insert(0, str(公共组件))

from 标准加载器 import 候选试验模式, 加载标准文本, 标准记录, 生产模式


def 读文本(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    return path.read_text(encoding="utf-8-sig")


def 标准路径(root: Path) -> dict[str, Path]:
    files = {
        "L1-00": root / "20_L1_闸门层" / "L1-00_闸门接口表.md",
        "L1-01": root / "20_L1_闸门层" / "L1-01_五大创作问题_技术护栏闭环图.md",
        "L1-02": root / "20_L1_闸门层" / "L1-02_读者投入意愿工程图.md",
        "L1-03": root / "20_L1_闸门层" / "L1-03_发布锁验收工程图.md",
        "L1.5": root / "30_L1.5_路由矩阵层" / "L1.5_Routing_Matrix.md",
        "L2-99": root / "40_L2_正式能力层" / "L2-99_能力层接口总表_v0.1.1_自检修正版.md",
    }
    return files


def 读标准(root: Path, standard_mode: str = 生产模式) -> dict[str, str]:
    texts, _records = 读标准与记录(root, standard_mode)
    return texts


def 读标准与记录(root: Path, standard_mode: str = 生产模式) -> tuple[dict[str, str], list[标准记录]]:
    return 加载标准文本(root, 标准路径(root), standard_mode)
