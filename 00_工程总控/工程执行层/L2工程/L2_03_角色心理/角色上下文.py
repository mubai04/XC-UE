from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 角色模型 import 行为, 角色状态, 触发事件, 选择
from 通用证据定位 import 切分段落, 切分句子

_ROLE_HINTS = ("他", "她", "主角", "我")


@dataclass
class 角色上下文:
    章节路径: str
    正文语料: str
    段落列表: list[str]
    识别角色: list[str]
    角色状态表: list[角色状态]
    触发事件表: list[触发事件]
    行为表: list[行为]
    选择表: list[选择]
    目标刺激行为链: list[dict]
    failure_evidence: list[dict]
    必须保留的信息: list[str]


def _识别角色(正文: str) -> list[str]:
    found = []
    for name in ("主角", "他", "她"):
        if name in 正文 and name not in found:
            found.append(name)
    if not found:
        found.append("主角")
    return found


def _含行为动词(句: str) -> bool:
    return any(v in 句 for v in ("选择", "决定", "必须", "转向", "逼近", "察觉", "减少"))


def 构造角色上下文(chapter_path: Path, item: 失败输入, *, repo_root: Path | None = None) -> 角色上下文:
    resolved = chapter_path.resolve() if chapter_path.is_absolute() else (
        (repo_root / chapter_path).resolve() if repo_root else chapter_path.resolve()
    )
    raw = resolved.read_text(encoding="utf-8")
    正文 = raw.split("\n", 1)[-1] if raw.startswith("#") else raw
    段落列表 = 切分段落(正文)
    角色们 = _识别角色(正文)
    状态表 = [角色状态(名称=r, 当前目标="生存/达成目标", 已知信息=["规则正在收紧"]) for r in 角色们]
    触发: list[触发事件] = []
    行为表: list[行为] = []
    选择表: list[选择] = []
    链条: list[dict] = []

    for p_idx, para in enumerate(段落列表, start=1):
        for sent in 切分句子(para):
            if any(k in sent for k in ("察觉", "传来", "规则", "异常")):
                触发.append(触发事件(p_idx, sent[:60]))
            if _含行为动词(sent):
                role = 角色们[0]
                行为表.append(行为(role, p_idx, sent[:60]))
                if "选择" in sent or "必须" in sent:
                    选择表.append(选择(role, p_idx, sent[:60]))
        if 行为表:
            链条.append(
                {
                    "character": 角色们[0],
                    "goal": 状态表[0].当前目标,
                    "stimulus": 触发[-1].摘句 if 触发 else "",
                    "behavior": 行为表[-1].摘句 if 行为表 else "",
                    "choice": 选择表[-1].摘句 if 选择表 else "",
                    "paragraph": p_idx,
                }
            )

    failure_evidence = [{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句]
    保留 = [e.摘句 for e in item.证据 if e.摘句][:3]

    return 角色上下文(
        章节路径=str(resolved),
        正文语料=正文,
        段落列表=段落列表,
        识别角色=角色们,
        角色状态表=状态表,
        触发事件表=触发,
        行为表=行为表,
        选择表=选择表,
        目标刺激行为链=链条,
        failure_evidence=failure_evidence,
        必须保留的信息=保留,
    )


def 上下文转诊断输入(ctx: 角色上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-03",
        "failure_type": item.失败类型,
        "character_chains": ctx.目标刺激行为链,
        "character_states": [asdict(s) for s in ctx.角色状态表],
        "triggers": [asdict(t) for t in ctx.触发事件表[:6]],
        "behaviors": [asdict(b) for b in ctx.行为表[:8]],
        "choices": [asdict(c) for c in ctx.选择表[:6]],
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
