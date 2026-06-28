"""R5B L2 真实 API 试跑入口（与 脚本/评估_L2_真实API试跑.py 同步）。"""
from __future__ import annotations

import runpy
from pathlib import Path

_TARGET = Path(__file__).resolve().parents[1] / "脚本" / "评估_L2_真实API试跑.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
