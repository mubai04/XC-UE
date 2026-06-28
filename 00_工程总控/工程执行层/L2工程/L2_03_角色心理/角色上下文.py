from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from L2模型 import 失败输入
from 正文读取 import 读取章节正文
from 角色模型 import (
    行为,
    环境事件,
    角色动作记录,
    角色状态,
    角色结果记录,
    触发事件,
    行为结果,
    选择,
)
from 领域证据 import PRONOUNS, 识别对话证据
from 通用证据定位 import 切分句子

_NAME_BASE = r"[\u4e00-\u9fffA-Za-z0-9·]{2,6}"
_NAME_HEAD = r"[\u4e00-\u9fff]{2,4}"
GOAL_VERBS = ("想", "要", "想要", "打算", "准备", "决定", "决心", "誓要", "必须", "不能让")
NAME_TRIM_SUFFIXES = (
    "誓要", "想要", "打算", "准备", "决定", "决心", "必须", "不能", "试图", "誓", "想", "要", "受伤", "受", "伤",
)
NON_PERSON = frozenset({"守卫", "敌哨", "门客", "士兵", "队长", "广播", "钟声", "号炮", "巡逻员", "守门人"})
STOP_FILTER = frozenset({"这时", "随后", "因此", "但是", "然而", "于是", "突然", "终于", "一个", "什么", "段落"})
_ENV_VERBS = ("响起", "坠落", "关闭", "蔓延", "爆炸", "熄灭", "坍塌", "断裂", "爆发", "倾倒", "炸开")
_ENV_SUBJECT_HINT = ("铃", "灯", "门", "火", "烟", "声", "风", "墙", "顶", "梁", "炮", "钟", "梯", "闸", "警报", "横梁")
_OBSTACLE_PAT = re.compile(
    r"(守卫|敌哨|追兵|敌兵|审查|巡逻)([^。！？]{0,12}?(?:逼近|拦住|围堵|压来|追来|升级))"
)
_TEMPORAL_STIM_PAT = re.compile(
    r"^(.{2,12}?(?:响起|齐响|炸开|关闭|震响|熄灭|断裂|爆发|倾倒))(?:后|时)?"
)
_ACTION_HINTS = ("撞", "冲", "推", "翻", "跑", "奔", "躲", "进", "开", "交", "夺", "拉", "杀", "攻", "退", "离开", "护送", "选择", "做出", "奔向", "翻窗", "躲开", "撞开")
_PRONOUN_BEH_PAT = re.compile(r"^(?:他|她)(?:必须|不得不|只能|仍|还)?")


@dataclass
class 角色上下文:
    章节路径: str
    正文语料: str
    段落列表: list[str]
    识别角色: list[dict]
    角色状态表: list[角色状态]
    环境事件表: list[环境事件]
    触发事件表: list[触发事件]
    行为表: list[行为]
    角色动作表: list[角色动作记录]
    选择表: list[选择]
    结果表: list[行为结果]
    角色结果表: list[角色结果记录]
    目标刺激行为链: list[dict]
    failure_evidence: list[dict]
    必须保留的信息: list[str]


def _trim_name(raw: str) -> str:
    name = raw.strip()
    for suffix in sorted(NAME_TRIM_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def _is_likely_person_name(chunk: str) -> bool:
    if not chunk or chunk in PRONOUNS or chunk in STOP_FILTER:
        return False
    if chunk in NON_PERSON:
        return False
    if len(chunk) < 2 or len(chunk) > 6:
        return False
    if any(chunk.endswith(s) for s in _ENV_SUBJECT_HINT):
        return False
    if chunk.endswith("逼近"):
        return False
    return True


def _读IR03角色(ir_dir: Path | None) -> set[str]:
    names: set[str] = set()
    if ir_dir is None:
        return names
    path = ir_dir / "IR-03_角色动机表.md"
    if path.is_file():
        for m in re.finditer(r"([\u4e00-\u9fff]{2,4})", path.read_text(encoding="utf-8")):
            n = _trim_name(m.group(1))
            if _is_likely_person_name(n):
                names.add(n)
    return names


def _collect_mentions(正文: str, ir_names: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in ir_names:
        counts[n] = counts.get(n, 0) + 3
    verb_alt = "|".join(GOAL_VERBS)
    patterns = [
        re.compile(rf"({_NAME_BASE})(?:说|问|答|喊|道)[：:\"\"「]"),
        re.compile(rf"({_NAME_BASE})(?:{verb_alt})"),
        re.compile(rf"({_NAME_BASE})(?:翻|奔|跑|冲|躲|退|拿|摸|找|夺|推|拉|杀|攻|守|撞|开|护|送)"),
    ]
    for pat in patterns:
        for m in pat.finditer(正文):
            n = _trim_name(m.group(1))
            if _is_likely_person_name(n):
                counts[n] = counts.get(n, 0) + 1
    for sent in re.split(r"(?<=[。！？!?])", 正文):
        ev = 识别对话证据(sent)
        if ev.get("speaker_confidence") == "EXPLICIT" and ev.get("speaker"):
            sp = _trim_name(str(ev["speaker"]))
            if _is_likely_person_name(sp):
                counts[sp] = counts.get(sp, 0) + 2
    return counts


def _confirm_characters(counts: dict[str, int], ir_names: set[str]) -> list[str]:
    confirmed: list[str] = []
    for name, c in counts.items():
        if name in ir_names or c >= 2:
            if _is_likely_person_name(name) and name not in confirmed:
                confirmed.append(name)
    return confirmed


def _split_clauses(sent: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[，,]", sent) if p.strip()]
    return parts or [sent.strip()]


def _is_env_subject(subj: str) -> bool:
    if _is_likely_person_name(subj):
        return False
    if any(h in subj for h in _ENV_SUBJECT_HINT):
        return True
    if subj in ("火焰", "钟声", "号炮", "审查", "广播"):
        return True
    return False


def _parse_env_event(clause: str, paragraph: int, full_sent: str) -> 环境事件 | None:
    verb_alt = "|".join(_ENV_VERBS)
    m = re.match(rf"^(.{{2,12}}?)({verb_alt})", clause.strip())
    if not m:
        return None
    subj = m.group(1).strip()
    if not _is_env_subject(subj):
        return None
    return 环境事件(
        event_type=m.group(2),
        paragraph=paragraph,
        quote=full_sent.strip(),
        affected_characters=[],
    )


def _split_name_head(clause: str) -> tuple[str, str] | None:
    text = clause.strip()
    candidates: list[tuple[int, int, str, str]] = []
    for nlen in range(2, min(7, len(text))):
        name = _trim_name(text[:nlen])
        if not _is_likely_person_name(name):
            continue
        rest = text[nlen:].strip()
        if not rest:
            continue
        score = 0
        if any(rest.startswith(v) for v in GOAL_VERBS):
            score += 3
        if any(h in rest[:8] for h in _ACTION_HINTS):
            score += 2
        candidates.append((score, nlen, name, rest))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    _, _, name, rest = candidates[0]
    return name, rest


def _parse_goal(clause: str, confirmed: set[str]) -> tuple[str, str] | None:
    verb_alt = "|".join(GOAL_VERBS)
    split = _split_name_head(clause.strip())
    if not split:
        return None
    char, rest = split
    m = re.match(rf"^({verb_alt})(.+)$", rest)
    if not m:
        return None
    if char not in confirmed and not _is_likely_person_name(char):
        return None
    action = m.group(2).strip().rstrip("。！？")
    return char, action


def _parse_behavior(clause: str, confirmed: set[str]) -> tuple[str, str] | None:
    split = _split_name_head(clause.strip())
    if not split:
        return None
    char, tail = split
    if char not in confirmed:
        return None
    if not any(h in tail for h in _ACTION_HINTS):
        return None
    action = tail.rstrip("。！？")
    if action.startswith(("准备", "打算", "想要", "决定", "决心")):
        return None
    return char, action


def _parse_result(clause: str, confirmed: set[str], recent: str) -> tuple[str, str] | None:
    if "自己" in clause and recent in confirmed:
        if any(k in clause for k in ("受伤", "倒地", "成功", "失败", "逃脱", "获得", "失去", "划伤")):
            frag = clause.split("自己", 1)[-1].strip().rstrip("。！？")
            return recent, f"自己{frag}" if frag else "自己受影响"
    m = re.search(
        rf"^({_NAME_BASE})(?:[^。！？]{{0,16}}?(?:受伤[^。！？]*倒地|受伤倒地|倒地|受伤|成功|失败|逃脱|获得|失去|划伤))",
        clause,
    )
    if m:
        char = _trim_name(m.group(1))
        if char in confirmed:
            return char, clause.strip().rstrip("。！？")
    return None


def _recent_char_in_sentence(sent: str, confirmed: set[str]) -> str:
    hits = [n for n in confirmed if n in sent]
    if len(hits) == 1:
        return hits[0]
    return ""


def _resolve_pronoun_char(clause: str, sent: str, confirmed: set[str], recent: str) -> str:
    if recent in confirmed:
        return recent
    hits = [n for n in confirmed if n in sent]
    if len(hits) == 1:
        return hits[0]
    if len(confirmed) == 1:
        return next(iter(confirmed))
    return ""


def _parse_temporal_stimulus(clause: str) -> str:
    m = _TEMPORAL_STIM_PAT.match(clause.strip())
    if not m:
        return ""
    head = m.group(1).strip()
    if _is_likely_person_name(_trim_name(head[: min(4, len(head))])):
        return ""
    return clause.strip().rstrip("。！？")


def _parse_obstacle_stimulus(clause: str, sent: str, confirmed: set[str]) -> tuple[str, str] | None:
    m = _OBSTACLE_PAT.search(clause)
    if not m:
        return None
    stim = m.group(0).strip()
    if len(stim) < 4:
        stim = clause.strip().rstrip("。！？")
    targets = [n for n in confirmed if n in sent]
    if len(targets) == 1:
        return targets[0], stim
    if "他" in clause or "她" in clause:
        char = _resolve_pronoun_char(clause, sent, confirmed, _recent_char_in_sentence(sent, confirmed))
        if char:
            return char, stim
    for n in confirmed:
        if n in clause:
            return n, stim
    return None


def _parse_pronoun_behavior(
    clause: str, sent: str, confirmed: set[str], recent: str
) -> tuple[str, str] | None:
    if not _PRONOUN_BEH_PAT.match(clause.strip()):
        return None
    char = _resolve_pronoun_char(clause, sent, confirmed, recent)
    if not char:
        return None
    if not any(h in clause for h in _ACTION_HINTS):
        return None
    return char, clause.strip().rstrip("。！？")


def 构造角色上下文(chapter_path: Path, item: 失败输入, *, repo_root: Path | None = None) -> 角色上下文:
    正文, 段落列表, resolved = 读取章节正文(chapter_path, repo_root=repo_root)
    source_path = str(resolved)
    ir_dir = resolved.parent.parent / "IR"
    ir_names = _读IR03角色(ir_dir if ir_dir.is_dir() else None)
    counts = _collect_mentions(正文, ir_names)
    角色候选 = [{"name": n, "mentions": c, "confirmed": False} for n, c in counts.items()]
    confirmed_list = _confirm_characters(counts, ir_names)
    confirmed = set(confirmed_list)
    for r in 角色候选:
        if r["name"] in confirmed:
            r["confirmed"] = True

    目标证据: dict[str, str] = {}
    目标摘句: dict[str, str] = {}
    行为证据: dict[str, str] = {}
    行为摘句: dict[str, str] = {}
    结果证据: dict[str, str] = {}
    刺激证据: dict[str, str] = {}
    环境事件表: list[环境事件] = []
    触发: list[触发事件] = []
    行为表: list[行为] = []
    角色动作表: list[角色动作记录] = []
    选择表: list[选择] = []
    结果表: list[行为结果] = []
    角色结果表: list[角色结果记录] = []

    for p_idx, para in enumerate(段落列表, start=1):
        for sent in 切分句子(para):
            clauses = _split_clauses(sent)
            recent = _recent_char_in_sentence(sent, confirmed)
            pending_stim = ""
            for clause in clauses:
                env = _parse_env_event(clause, p_idx, sent)
                if env:
                    env.affected_characters = [n for n in confirmed if n in sent]
                    环境事件表.append(env)
                    触发.append(触发事件(p_idx, sent.strip()))
                    stim_clause = clause.strip().rstrip("。！？")
                    for n in env.affected_characters:
                        刺激证据[n] = stim_clause
                    continue
                temporal = _parse_temporal_stimulus(clause)
                if temporal:
                    pending_stim = temporal
                    触发.append(触发事件(p_idx, sent.strip()))
                    continue
                obstacle = _parse_obstacle_stimulus(clause, sent, confirmed)
                if obstacle:
                    char, stim = obstacle
                    confirmed.add(char)
                    刺激证据[char] = stim
                    触发.append(触发事件(p_idx, sent.strip()))
                goal = _parse_goal(clause, confirmed)
                if goal:
                    char, action = goal
                    confirmed.add(char)
                    目标证据[char] = action
                    目标摘句[char] = clause.strip().rstrip("。！？")
                    if pending_stim:
                        刺激证据[char] = pending_stim
                    continue
                beh = _parse_behavior(clause, confirmed)
                if beh:
                    char, action = beh
                    confirmed.add(char)
                    行为证据[char] = action
                    行为摘句[char] = clause.strip().rstrip("。！？")
                    行为表.append(行为(char, p_idx, sent.strip()))
                    角色动作表.append(角色动作记录(char, action, p_idx, sent.strip()))
                    if pending_stim and char not in 刺激证据:
                        刺激证据[char] = pending_stim
                    continue
                pron = _parse_pronoun_behavior(clause, sent, confirmed, recent)
                if pron:
                    char, action = pron
                    confirmed.add(char)
                    行为证据[char] = action
                    行为摘句[char] = clause.strip().rstrip("。！？")
                    行为表.append(行为(char, p_idx, sent.strip()))
                    角色动作表.append(角色动作记录(char, action, p_idx, sent.strip()))
                    if pending_stim and char not in 刺激证据:
                        刺激证据[char] = pending_stim
                    continue
                res = _parse_result(clause, confirmed, recent)
                if res:
                    char, result = res
                    confirmed.add(char)
                    结果证据[char] = result
                    结果表.append(行为结果(char, p_idx, sent.strip()))
                    角色结果表.append(角色结果记录(char, result, p_idx, sent.strip()))
            pending_stim = ""

            ev = 识别对话证据(sent)
            if ev.get("speaker_confidence") == "EXPLICIT" and ev.get("speaker"):
                sp = _trim_name(str(ev["speaker"]))
                if _is_likely_person_name(sp):
                    counts[sp] = counts.get(sp, 0) + 1
                    if counts[sp] >= 2 or sp in ir_names:
                        confirmed.add(sp)

    confirmed_list = sorted(confirmed)
    for r in 角色候选:
        r["confirmed"] = r["name"] in confirmed
    if not 角色候选:
        角色候选 = [{"name": n, "mentions": c, "confirmed": n in confirmed} for n, c in counts.items()]

    状态表 = [角色状态(名称=n, 当前目标=目标证据.get(n, ""), 已知信息=[]) for n in confirmed_list]
    链条: list[dict] = []
    for name in confirmed_list:
        goal_q = 目标证据.get(name, "")
        goal_ev = 目标摘句.get(name, goal_q)
        beh_q = 行为证据.get(name, "")
        beh_ev = 行为摘句.get(name, beh_q)
        res_q = 结果证据.get(name, "")
        stim = 刺激证据.get(name, "")
        if not stim:
            stim = next(
                (e.quote for e in reversed(环境事件表) if name in e.affected_characters),
                "",
            )
        if not stim:
            stim = next((t.摘句 for t in reversed(触发) if name in t.摘句), "")
        链条.append(
            {
                "character": name,
                "goal": goal_q,
                "goal_evidence": goal_ev,
                "stimulus": stim,
                "stimulus_evidence": stim,
                "behavior": beh_q,
                "behavior_evidence": beh_ev,
                "choice": "",
                "choice_evidence": "",
                "result": res_q,
                "result_evidence": res_q,
                "unresolved_links": [x for x, v in (
                    ("缺少目标", goal_q), ("缺少行为", beh_q), ("缺少行为结果", res_q)
                ) if not v],
            }
        )

    return 角色上下文(
        章节路径=source_path,
        正文语料=正文,
        段落列表=段落列表,
        识别角色=角色候选,
        角色状态表=状态表,
        环境事件表=环境事件表,
        触发事件表=触发,
        行为表=行为表,
        角色动作表=角色动作表,
        选择表=选择表,
        结果表=结果表,
        角色结果表=角色结果表,
        目标刺激行为链=链条,
        failure_evidence=[{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句],
        必须保留的信息=[e.摘句 for e in item.证据 if e.摘句][:3],
    )


def 上下文转诊断输入(ctx: 角色上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-03",
        "failure_type": item.失败类型,
        "character_chains": ctx.目标刺激行为链,
        "character_states": [asdict(s) for s in ctx.角色状态表],
        "environment_events": [asdict(e) for e in ctx.环境事件表[:8]],
        "character_actions": [asdict(a) for a in ctx.角色动作表[:8]],
        "character_results": [asdict(r) for r in ctx.角色结果表[:8]],
        "triggers": [asdict(t) for t in ctx.触发事件表[:8]],
        "behaviors": [asdict(b) for b in ctx.行为表[:8]],
        "choices": [asdict(c) for c in ctx.选择表[:6]],
        "results": [asdict(r) for r in ctx.结果表[:6]],
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
