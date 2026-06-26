from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"
for path in (EXEC / "公共组件", EXEC / "L1工程", EXEC / "L2工程", EXEC / "L3工程"):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
