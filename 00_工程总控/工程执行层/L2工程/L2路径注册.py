from __future__ import annotations

import sys
from pathlib import Path

L2_ROOT = Path(__file__).resolve().parent

_SUBDIRS = (
    "公共执行层",
    "L2_02_文风语言",
    "L2_03_角色心理",
    "L2_04_创意设定",
    "L2_05_市场体验",
    "L2_06_系统一致性",
)


def 注册L2子路径() -> None:
    root_text = str(L2_ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    for name in _SUBDIRS:
        path = L2_ROOT / name
        if path.is_dir():
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)
