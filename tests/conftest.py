from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "00_工程总控" / "工程执行层"
PUBLIC = EXEC / "公共组件"
L1 = EXEC / "L1工程"
L2 = EXEC / "L2工程"
L3 = EXEC / "L3工程"

for path in (PUBLIC, L1, L2, L3):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


@pytest.fixture
def repo_root() -> Path:
    return ROOT


def make_mock_transport(response_body: dict, *, status: int = 200) -> callable:
    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        envelope = {
            "choices": [{"message": {"content": json.dumps(response_body, ensure_ascii=False)}}],
        }
        return status, json.dumps(envelope, ensure_ascii=False)

    return transport


def make_error_transport(*, status: int = 500, message: str = "server error") -> callable:
    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        return status, message

    return transport


def make_timeout_transport() -> callable:
    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str]:
        raise TimeoutError("timed out")

    return transport


def sample_chapter_text(seed: str) -> str:
    blocks = [
        f"段落一：{seed} 忽然察觉异常，因为规则正在收紧，门后传来不属于这一层的脚步声。",
        f"段落二：他必须做出选择，否则代价会落在所有人身上，而名单上的名字已经开始减少。",
        f"段落三：追兵逼近，冲突升级，真相尚未揭晓，旧日承诺像刀背一样压在他的肩胛。",
        f"段落四：读者收益在于局势反转，但认知成本来自多层设定，每条规则都绑定着不同的惩罚。",
        f"段落五：章末留下新问题——{seed} 到底看见了什么，而那个答案似乎早在多年前就被写进账册。",
        f"段落六：风从裂开的窗缝里灌进来，带着铁锈、雨和未燃尽的符纸，提醒他时间不多。",
        f"段落七：同伴想退，他却知道一旦退后，整条因果链都会断在昨夜那个未被记录的决定上。",
        f"段落八：远处钟声敲响，意味着审查即将开始，而他还没有准备好面对真正的提问者。",
    ]
    return f"# 测试章节 {seed}\n\n" + "\n\n".join(blocks) + "\n"
