from __future__ import annotations

from L2模型 import 接口判断


def 检查(judgements: list[接口判断]) -> list[接口判断]:
    blocked = []
    for item in judgements:
        if item.最终状态 == "派生复验":
            continue
        if item.主候选模块 in {"L3", "外部运营层", "回L1.5"}:
            blocked.append(item)
        if item.是否越界 == "是":
            blocked.append(item)
    unique = []
    seen = set()
    for item in blocked:
        key = (item.来源闸门, item.输入问题, item.主候选模块)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
