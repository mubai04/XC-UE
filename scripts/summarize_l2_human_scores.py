"""英文路径入口：调用 脚本/汇总_L2_人工业务评分.py"""
from __future__ import annotations

import runpy
from pathlib import Path

_TARGET = Path(__file__).resolve().parents[1] / "脚本" / "汇总_L2_人工业务评分.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
