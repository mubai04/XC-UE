from __future__ import annotations

属性别名表: dict[str, str] = {
    "左手状态": "肢体状态",
    "右手状态": "肢体状态",
    "双手状态": "肢体状态",
    "肢体": "肢体状态",
    "所在地": "位置",
    "地点": "位置",
    "所处位置": "位置",
    "存活": "生命状态",
    "死亡": "生命状态",
    "生命": "生命状态",
}

值别名表: dict[str, dict[str, str]] = {
    "肢体状态": {
        "断了": "受损",
        "断掉": "受损",
        "失去": "受损",
        "残废": "受损",
        "受伤": "受损",
        "完好": "完好",
        "健全": "完好",
    },
    "位置": {
        "城内": "城内",
        "城外": "城外",
    },
}


def 归一化属性(属性: str) -> str:
    key = 属性.strip()
    return 属性别名表.get(key, key)


def 归一化值(属性: str, 值: str) -> str:
    norm_attr = 归一化属性(属性)
    raw = 值.strip()
    mapping = 值别名表.get(norm_attr, {})
    return mapping.get(raw, raw)


def 属性可比对(属性_a: str, 属性_b: str) -> bool:
    return 归一化属性(属性_a) == 归一化属性(属性_b)
