from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 体验模型 import 信息重复, 入口承诺, 即时收益, 末段推动力, 认知负担, 阅读阶段
from 正文读取 import 读取章节正文
from 领域证据 import 标准化文本
from 通用证据定位 import 切分句子

_STAGE_NAMES = ("开头", "前段", "中段", "末段")
_PROMISE_HINTS = ("必须", "如果", "一旦", "否则", "留下", "注定", "?", "？")
_BURDEN_HINTS = ("多层", "设定", "意味着", "换句话说", "因为", "认知", "消化", "负荷")
_MOMENTUM_HINTS = ("?", "？", "尚未", "还没", "留下", "到底", "会否", "能否", "新问题")

_ITEM_PAT = re.compile(r"(?:得到|拿到|摸出|找到|获得|掏出|取出)[^。！？]{0,24}")
_INFO_PAT = re.compile(r"(?:得知|发现|看见|听见|察觉|明白)[^。！？]{0,30}")
_LOCAL_PAT = re.compile(r"(?:赢得|解决|击退|挡住|逃过)[^。！？]{0,30}")
_PERM_PAT = re.compile(r"(?:解锁|打开|取得)[^。！？]{0,24}(?:权限|资格|通道|门卡|钥匙)?")
_RELATION_PAT = re.compile(r"(?:反目|结盟|背叛|信任|决裂)")
_DANGER_PAT = re.compile(r"(?:危险|升级|逼近|封锁|围困|追来)")
_CHOICE_PAT = re.compile(r"(?:决定|选择|打算|决心)[^。！？]{0,20}")

_SPEAKER_PREFIX = re.compile(
    r"^(?:广播|公告|系统|提示|守卫|巡逻员|士兵|军官|队长|传令|探子|哨兵|门客|侍从|使者|信使|人|某)"
    r"(?:通知|说|喊道|叫道|宣布|再次说|又说|仍然说|又一次说|称|表示|写|反复提醒|再次强调|强调|提醒)[，,:：]?"
)
_REPEAT_MARKERS = re.compile(r"(?:已经|仍然|又一次|再次|又|还|依旧|仍)")
_STATEMENT_VERBS = ("关闭", "封锁", "爆炸", "开启", "启动", "停止", "修复", "恢复", "打开", "撤离", "封锁")


@dataclass
class 体验上下文:
    章节路径: str
    正文语料: str
    段落列表: list[str]
    句子索引: list[list[str]]
    阅读阶段表: list[阅读阶段]
    入口承诺列表: list[入口承诺]
    即时收益列表: list[即时收益]
    认知负担列表: list[认知负担]
    重复信息列表: list[信息重复]
    末段推动力列表: list[末段推动力]
    failure_evidence: list[dict]

    @property
    def 重复信息(self) -> list[信息重复]:
        return self.重复信息列表

    @property
    def 入口承诺候选(self) -> list[入口承诺]:
        return self.入口承诺列表

    @property
    def 末段推动力(self) -> list[末段推动力]:
        return self.末段推动力列表

    @property
    def 末段推动力候选(self) -> list[末段推动力]:
        return self.末段推动力列表


def _阶段切分(段落: list[str]) -> list[阅读阶段]:
    if not 段落:
        return []
    n = len(段落)
    bounds = [0, max(1, n // 4), max(2, n // 2), max(3, (3 * n) // 4), n]
    stages: list[阅读阶段] = []
    for i, name in enumerate(_STAGE_NAMES):
        start = bounds[i] + 1
        end = bounds[i + 1]
        if start > n:
            break
        end = min(end, n)
        excerpt = " ".join(段落[start - 1 : end])[:120]
        stages.append(阅读阶段(name, start, end, excerpt))
    return stages


def _句匹配(句: str, hints: tuple[str, ...]) -> bool:
    return any(h in 句 for h in hints)


def _提取入口承诺(句子索引: list[list[str]], 阶段: list[阅读阶段]) -> list[入口承诺]:
    if not 阶段:
        return []
    first = 阶段[0]
    out: list[入口承诺] = []
    for p_idx in range(first.起始段落, min(first.结束段落 + 1, len(句子索引) + 1)):
        for s_idx, sent in enumerate(句子索引[p_idx - 1], start=1):
            if _句匹配(sent, _PROMISE_HINTS) or p_idx == first.起始段落:
                out.append(入口承诺(sent.strip(), p_idx, s_idx))
            if len(out) >= 4:
                return out
    return out


def _分类收益(句: str) -> tuple[str, str]:
    if _ITEM_PAT.search(句):
        return "ITEM", _ITEM_PAT.search(句).group(0).strip()
    if _PERM_PAT.search(句):
        return "ITEM", _PERM_PAT.search(句).group(0).strip()
    if _INFO_PAT.search(句):
        return "INFORMATION", _INFO_PAT.search(句).group(0).strip()
    if _LOCAL_PAT.search(句):
        return "LOCAL_RESULT", _LOCAL_PAT.search(句).group(0).strip()
    if _RELATION_PAT.search(句):
        return "RELATION_CHANGE", _RELATION_PAT.search(句).group(0).strip()
    if _DANGER_PAT.search(句):
        return "DANGER_ESCALATION", _DANGER_PAT.search(句).group(0).strip()
    if _CHOICE_PAT.search(句):
        return "KEY_CHOICE", _CHOICE_PAT.search(句).group(0).strip()
    if "发现" in 句 or "获得" in 句 or "突破" in 句 or "局势" in 句:
        return "DISCOVERY", 句[:30]
    return "", ""


def _段落所属阶段(段落: int, 阶段: list[阅读阶段]) -> str:
    for stage in 阶段:
        if stage.起始段落 <= 段落 <= stage.结束段落:
            return stage.名称
    return 阶段[-1].名称 if 阶段 else ""


def _提取即时收益(句子索引: list[list[str]], 阶段: list[阅读阶段]) -> list[即时收益]:
    out: list[即时收益] = []
    total = len(句子索引) or 1
    for p_idx, sents in enumerate(句子索引, start=1):
        stage_name = _段落所属阶段(p_idx, 阶段)
        ratio = round(p_idx / total, 3)
        for s_idx, sent in enumerate(sents, start=1):
            rtype, summary = _分类收益(sent)
            if rtype:
                out.append(
                    即时收益(
                        摘句=sent.strip(),
                        段落=p_idx,
                        sentence=s_idx,
                        reward_type=rtype,
                        summary=summary or sent.strip()[:40],
                        reading_stage=stage_name,
                        position_ratio=ratio,
                    )
                )
            if len(out) >= 12:
                return out
    return out


def _提取认知负担(句子索引: list[list[str]]) -> list[认知负担]:
    out: list[认知负担] = []
    for p_idx, sents in enumerate(句子索引, start=1):
        for s_idx, sent in enumerate(sents, start=1):
            burden_type = ""
            if _句匹配(sent, _BURDEN_HINTS):
                burden_type = "设定解释"
            elif len(sent) > 55 and sent.count("，") >= 2:
                burden_type = "长句信息堆叠"
            if burden_type:
                out.append(认知负担(burden_type, sent.strip(), p_idx, s_idx))
            if len(out) >= 6:
                return out
    return out


def _标准化重复核心(句: str) -> str:
    core = 句.strip()
    core = _SPEAKER_PREFIX.sub("", core)
    core = _REPEAT_MARKERS.sub("", core)
    core = 标准化文本(core)
    return core


def _陈述核心(句: str) -> tuple[str, str]:
    core = _标准化重复核心(句)
    for verb in _STATEMENT_VERBS:
        if verb in core:
            idx = core.index(verb)
            subject = core[:idx]
            predicate = core[idx:]
            if len(subject) >= 2 and len(predicate) >= 2:
                return subject, predicate
    return core, core


def _陈述等价(a: str, b: str) -> bool:
    sa, pa = _陈述核心(a)
    sb, pb = _陈述核心(b)
    if sa != sb:
        return False
    return pa == pb or (pa in pb) or (pb in pa)


def _重复短语候选(句: str) -> str:
    core = _标准化重复核心(句)
    if "：" in core:
        core = core.split("：", 1)[1].strip()
    elif ":" in core:
        core = core.split(":", 1)[1].strip()
    core = re.split(r"[，,]", core)[0].strip()
    return core


def _最长公共片段(a: str, b: str, *, min_len: int = 8) -> str:
    na = _标准化重复核心(a)
    nb = _标准化重复核心(b)
    if len(na) >= min_len and na == nb:
        return na
    if len(na) >= min_len and na in nb:
        return na
    if len(nb) >= min_len and nb in na:
        return nb
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    for size in range(min(len(shorter), 40), min_len - 1, -1):
        for i in range(len(shorter) - size + 1):
            frag = shorter[i : i + size]
            if frag in longer:
                return frag
    return ""


def _提取重复信息(段落列表: list[str], 句子索引: list[list[str]], source_path: str) -> list[信息重复]:
    del 段落列表, source_path
    out: list[信息重复] = []
    seen: set[str] = set()
    entries: list[tuple[int, int, str]] = []

    for p_idx, sents in enumerate(句子索引, start=1):
        for s_idx, sent in enumerate(sents, start=1):
            norm = sent.strip()
            if len(norm) >= 6:
                entries.append((p_idx, s_idx, norm))

    def _append_repeat(phrase: str, pa: int, sa: int, qa: str, pb: int, sb: int, qb: str) -> None:
        text = phrase.strip()
        if len(text) < 4:
            return
        key = f"{text}:{pa}:{pb}"
        if key in seen:
            return
        seen.add(key)
        out.append(信息重复(text, f"P{pa}:S{sa}", f"P{pb}:S{sb}", qa, qb))

    for i, (pa, sa, qa) in enumerate(entries):
        for pb, sb, qb in entries[i + 1 :]:
            if (pa, sa) == (pb, sb):
                continue
            if _陈述等价(qa, qb):
                subj, pred = _陈述核心(qa)
                phrase = f"{subj}{pred}" if subj else _标准化重复核心(qa)
                _append_repeat(phrase, pa, sa, qa, pb, sb, qb)
                continue
            ca = _重复短语候选(qa)
            cb = _重复短语候选(qb)
            if len(ca) >= 6 and len(cb) >= 6 and (ca == cb or ca in cb or cb in ca):
                _append_repeat(max(ca, cb, key=len), pa, sa, qa, pb, sb, qb)
                continue
            frag = _最长公共片段(qa, qb)
            if frag:
                _append_repeat(frag, pa, sa, qa, pb, sb, qb)
            if len(out) >= 8:
                return out
    return out


def _提取末段推动力(句子索引: list[list[str]], 阶段: list[阅读阶段]) -> list[末段推动力]:
    if not 阶段:
        return []
    last = 阶段[-1]
    out: list[末段推动力] = []
    for p_idx in range(last.起始段落, min(last.结束段落 + 1, len(句子索引) + 1)):
        for s_idx, sent in enumerate(句子索引[p_idx - 1], start=1):
            if _句匹配(sent, _MOMENTUM_HINTS):
                out.append(末段推动力(sent.strip(), p_idx, s_idx))
            if len(out) >= 4:
                return out
    if 句子索引 and last.起始段落 <= len(句子索引):
        p_idx = last.结束段落
        if p_idx > len(句子索引):
            p_idx = len(句子索引)
        sents = 句子索引[p_idx - 1]
        if sents:
            out.append(末段推动力(sents[-1].strip(), p_idx, len(sents)))
    return out


def 构造阅读阶段上下文(chapter_path: Path, item: 失败输入, *, repo_root: Path | None = None) -> 体验上下文:
    正文, 段落列表, resolved = 读取章节正文(chapter_path, repo_root=repo_root)
    source_path = str(resolved)
    句子索引 = [切分句子(p) for p in 段落列表]
    阶段 = _阶段切分(段落列表)
    return 体验上下文(
        章节路径=source_path,
        正文语料=正文,
        段落列表=段落列表,
        句子索引=句子索引,
        阅读阶段表=阶段,
        入口承诺列表=_提取入口承诺(句子索引, 阶段),
        即时收益列表=_提取即时收益(句子索引, 阶段),
        认知负担列表=_提取认知负担(句子索引),
        重复信息列表=_提取重复信息(段落列表, 句子索引, source_path),
        末段推动力列表=_提取末段推动力(句子索引, 阶段),
        failure_evidence=[{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句],
    )


def 上下文转诊断输入(ctx: 体验上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-05",
        "failure_type": item.失败类型,
        "reading_stages": [asdict(s) for s in ctx.阅读阶段表],
        "entry_promises": [asdict(p) for p in ctx.入口承诺列表[:6]],
        "immediate_rewards": [asdict(r) for r in ctx.即时收益列表[:6]],
        "cognitive_loads": [asdict(c) for c in ctx.认知负担列表[:6]],
        "repeat_info": [asdict(r) for r in ctx.重复信息列表[:8]],
        "ending_momentum": [asdict(m) for m in ctx.末段推动力列表[:4]],
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
        "ending_excerpt": ctx.段落列表[-1][:200] if ctx.段落列表 else "",
    }
