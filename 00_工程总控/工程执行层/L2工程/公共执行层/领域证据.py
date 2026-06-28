from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

STOP_WORDS = frozenset(
    "的 了 在 是 有 和 与 及 而 但 就 也 都 还 又 已 被 把 让 向 从 到 对 为 以 于 这 那 一个 一种 他们 我们 你们 自己".split()
)
PRONOUNS = frozenset({"他", "她", "它", "他们", "她们", "我", "你", "您", "大家", "主角", "有人", "某人"})


@dataclass
class 证据片段:
    source_type: str
    source_path: str
    paragraph: int
    quote: str
    sentence: int | None = None
    entity: str = ""
    attribute: str = ""
    value: str = ""
    time_marker: str = ""
    negated: bool = False
    inferred: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def 标准化文本(text: str) -> str:
    t = re.sub(r"\s+", "", text)
    t = re.sub(r"[，,、；;：:！!？?「」『』\"'（）()【】\[\]]", "", t)
    return t


def 识别说话人(句子: str) -> str | None:
    ev = 识别对话证据(句子)
    return ev.get("speaker")


_SPEECH_VERBS = (
    "说道",
    "问道",
    "答道",
    "喊道",
    "回答",
    "说",
    "问",
    "答",
    "喊",
    "道",
)
_SPEECH_VERB_RE = "|".join(re.escape(v) for v in _SPEECH_VERBS)
_SPEECH_DELIM_RE = re.compile(r'^[：:「"\u201c?？]')
_MANNER_FRAGMENT_RE = re.compile(
    r"^[\u4e00-\u9fff]{0,10}(?:地|着|声|声音)?$"
)


def _looks_like_person_name(name: str) -> bool:
    if not name or name in PRONOUNS:
        return False
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
        return False
    if name.endswith(("外", "内", "上", "下")) and len(name) == 2:
        return False
    return True


def _manner_ok(fragment: str) -> bool:
    if not fragment:
        return True
    if not _MANNER_FRAGMENT_RE.fullmatch(fragment):
        return False
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", fragment) and not fragment.endswith(("地", "着", "声", "音")):
        return False
    if any(tok in fragment for tok in ("看见", "听见", "发现", "似乎", "有人", "问", "守卫")):
        return False
    embedded = [
        x
        for x in re.findall(r"[\u4e00-\u9fff]{2,4}", fragment)
        if not x.endswith(("地", "着", "声", "音"))
    ]
    if sum(1 for x in embedded if _looks_like_person_name(x)) >= 1:
        return False
    return True


def _after_verb_is_speech(after: str) -> bool:
    if not after:
        return True
    if after[0] in "。！？":
        return True
    return bool(_SPEECH_DELIM_RE.match(after))


def _find_speech_in_segment(segment: str) -> dict | None:
    for vm in re.finditer(rf"({_SPEECH_VERB_RE})", segment):
        verb = vm.group(1)
        before = segment[: vm.start()]
        if len(before) < 2:
            continue
        for nlen in (2, 3, 4):
            if len(before) < nlen:
                continue
            name = before[:nlen]
            if not _looks_like_person_name(name):
                continue
            manner = before[nlen:]
            if not _manner_ok(manner):
                continue
            after = segment[vm.end() :]
            if not _after_verb_is_speech(after):
                continue
            return {
                "speaker": name,
                "speaker_confidence": "EXPLICIT",
                "speech_verb": verb,
                "manner_text": manner,
            }
    return None


def _extract_speech_at(sent: str, start: int) -> dict | None:
    return _find_speech_in_segment(sent[start:])


def 识别对话证据(
    句子: str,
    *,
    paragraph: int = 0,
    sentence: int = 0,
) -> dict:
    sent = 句子.strip()
    base = {
        "speaker": None,
        "speaker_confidence": "UNKNOWN",
        "speech_verb": "",
        "manner_text": "",
        "paragraph": paragraph,
        "sentence": sentence,
        "quote": sent,
    }

    leading = _find_speech_in_segment(sent)
    if leading:
        base.update(leading)
        return base

    quote_first = re.search(
        r'[「『"\u201c][^」』"\u201d]{1,80}[」』"\u201d][。！？]?(.+)$',
        sent,
    )
    if quote_first:
        trailing = _find_speech_in_segment(quote_first.group(1))
        if trailing:
            base.update(trailing)
            return base

    plain_name = re.search(r'[。！？!?]["""\u201c]?(.+)$', sent)
    if plain_name:
        trailing = _find_speech_in_segment(plain_name.group(1))
        if trailing:
            base.update(trailing)
            return base

    for m in re.finditer(r"([\u4e00-\u9fff]{2,4})", sent):
        if m.start() > 0 and sent[m.start() - 1] in "，,。！？；;":
            hit = _find_speech_in_segment(sent[m.start() :])
            if hit:
                base.update(hit)
                return base

    return base

def 提取重复短语簇(
    段落列表: list[str],
    句子索引: list[list[str]],
    *,
    source_path: str,
    min_len: int = 4,
    max_len: int = 12,
) -> list[dict[str, Any]]:
    位置表: dict[str, list[dict[str, Any]]] = {}

    def _记录(frag: str, p_idx: int, s_idx: int, quote: str) -> None:
        if len(frag) < min_len or frag in STOP_WORDS:
            return
        位置表.setdefault(frag, []).append(
            {"paragraph": p_idx, "sentence": s_idx, "quote": quote, "source_path": source_path}
        )

    for p_idx, sents in enumerate(句子索引, start=1):
        for s_idx, sent in enumerate(sents, start=1):
            norm = 标准化文本(sent)
            if not norm:
                continue
            for length in range(min_len, min(max_len, len(norm)) + 1):
                seen_at: dict[str, list[int]] = {}
                for i in range(0, len(norm) - length + 1):
                    frag = norm[i : i + length]
                    seen_at.setdefault(frag, []).append(i)
                for frag, offsets in seen_at.items():
                    if len(offsets) >= 2:
                        _记录(frag, p_idx, s_idx, sent)
                    elif len(offsets) == 1 and norm.count(frag) >= 2:
                        _记录(frag, p_idx, s_idx, sent)
                        _记录(frag, p_idx, s_idx, sent)

    for p_idx, sents in enumerate(句子索引, start=1):
        if p_idx >= 2:
            break
        for s_idx, sent in enumerate(sents, start=1):
            norm = 标准化文本(sent)
            for length in range(min_len, min(max_len, len(norm)) + 1):
                for frag_start in range(0, len(norm) - length + 1):
                    frag = norm[frag_start : frag_start + length]
                    if norm.count(frag) >= 2:
                        _记录(frag, p_idx, s_idx, sent)

    clusters: list[dict[str, Any]] = []
    for phrase, locs in 位置表.items():
        unique_positions = {(x["paragraph"], x["sentence"]) for x in locs}
        if len(locs) >= 2 or len(unique_positions) >= 2:
            clusters.append({"phrase": phrase, "occurrences": locs[:6]})
    clusters.sort(key=lambda c: (-len(c["occurrences"]), -len(c["phrase"])))
    return clusters[:12]


def 句内提取候选(句子: str, patterns: list[tuple[re.Pattern[str], str]]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for pat, label in patterns:
        m = pat.search(句子)
        if m:
            hits.append((label, m.group(0)))
    return hits
