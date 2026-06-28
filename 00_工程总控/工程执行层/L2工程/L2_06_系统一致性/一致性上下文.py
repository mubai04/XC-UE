from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from L2模型 import 失败输入
from 事实模型 import 事实声明, 来源索引
from 属性归一 import 归一化值, 归一化属性
from 正文读取 import 读取章节正文
from 通用证据定位 import 切分段落

_TIME_MARKERS = ("清晨", "入夜", "入夜后", "次日", "几天后", "几年后", "后来", "此前", "此前夜", "昨夜")
_CHANGE_MARKERS = ("已经", "仍然", "不再", "从未", "还在", "变成", "变为", "恢复", "治愈", "进入", "离开")
_RULE_MARKERS = ("必须", "不得", "不能", "只能", "规则", "规定", "禁止", "除非", "一旦", "凡是")
_NEGATION_PREFIX = ("不是", "没有", "不再", "从未", "并非", "并无")

_ENTITY = r"[\u4e00-\u9fffA-Za-z0-9·]{1,6}"

_FACT_PATTERNS: tuple[tuple[str, str], ...] = (
    (rf"(?P<entity>{_ENTITY})(?:已经|仍然|不再|从未)?(?P<neg>不是)(?P<value>[^。，；\n]{{1,40}})", "是否定"),
    (rf"(?P<entity>{_ENTITY})(?:已经|仍然|不再|从未)?(?P<neg>没有)(?P<value>[^。，；\n]{{1,40}})", "有无"),
    (rf"(?P<entity>{_ENTITY})从未(?P<value>[^。，；\n]{{1,40}})", "从未"),
    (rf"(?P<entity>{_ENTITY})不在(?P<value>[^。，；\n]{{1,40}})", "不在"),
    (rf"(?P<entity>{_ENTITY})(?:已经|仍然|不再|从未)?(?P<neg>并非)(?P<value>[^。，；\n]{{1,40}})", "并非"),
    (rf"(?P<entity>{_ENTITY})的(?P<attr>[\u4e00-\u9fff]{{1,10}})[是为](?P<value>[^。，；\n]{{1,40}})", "的属值为"),
    (rf"(?P<entity>{_ENTITY})的(?P<attr>[\u4e00-\u9fff]{{1,10}})(?:已经|仍然|不再|从未)?(?:变成|变为|仍是|还是)(?P<value>[^。，；\n]{{1,40}})", "的属变化"),
    (rf"(?P<entity>{_ENTITY})(?<![不没])是(?P<value>[^。，；\n]{{1,40}})", "是"),
    (rf"(?P<entity>{_ENTITY})有(?P<value>[^。，；\n]{{1,40}})", "有"),
    (rf"(?P<entity>{_ENTITY})的(?P<limb>左手|右手|双手)(?:已经|仍然|不再|从未)?(?P<value>断了|断掉|完好|健全|受伤|残废|失去)", "肢体"),
    (rf"(?P<entity>{_ENTITY})(?P<limb>左手|右手|双手)(?:已经|仍然|不再|从未)?(?P<value>断了|断掉|完好|健全|受伤|残废|失去)", "肢体简"),
    (rf"(?P<entity>{_ENTITY})(?:仍在|还在)(?P<value>[^。，；\n]{{1,20}})", "仍在"),
    (rf"(?P<entity>{_ENTITY})(?:乘船|乘车)(?:抵达|到达|前往)(?P<value>[^。，；\n]{{1,20}})", "抵达"),
    (rf"(?P<entity>{_ENTITY})(?:抵达|到达|前往)(?P<value>[^。，；\n]{{1,20}})", "直抵"),
    (rf"(?P<time>清晨|入夜后|入夜|次日|几天后|几年后|后来|傍晚|数日后)[，,]?(?P<entity>{_ENTITY})(?:乘船|乘车)(?:抵达|到达|前往)(?P<value>[^。，；\n]{{1,20}})", "时抵达"),
    (rf"(?P<time>清晨|入夜后|次日|几天后|几年后|后来|傍晚|数日后)[，,]?(?P<entity>{_ENTITY})(?:还在|已经)(?P<value>[^。，；\n]{{1,20}})", "时还在"),
    (rf"(?P<time>清晨|入夜后|次日|几天后|几年后|后来)[，,]?(?P<entity>{_ENTITY})(?:已经|仍然|不再|从未|还在)?(?P<action>进入|离开|位于)(?P<value>[^。，；\n]{{1,20}})", "时位"),
    (rf"(?P<entity>{_ENTITY})(?:已经|仍然|不再|从未)?(?:位于|进入|离开)(?P<value>[^。，；\n]{{1,20}})", "位置动"),
    (rf"(?P<entity>规则)(?:正在|已经)(?P<value>[^。，；\n]{{1,20}})", "规则状态"),
    (rf"不属于(?P<value>[^。，；\n]{{1,12}})的", "层级否定"),
    (rf"(?P<entity>{_ENTITY})(?<![正])在(?P<value>[^。，；\n]{{1,20}})", "位于简"),
    (rf"(?P<entity>{_ENTITY})已到(?P<value>[^。，；\n]{{1,20}})", "已到"),
    (rf"(?P<entity>{_ENTITY})的(?P<limb>左臂|右臂|双臂)(?:无法|不能)(?P<value>[^。，；\n]{{1,20}})", "肢臂"),
    (rf"(?P<entity>{_ENTITY})(?:已经|仍然|不再|从未|还在)(?P<value>[^。，；\n]{{1,30}})", "状态"),
)


@dataclass
class 一致性上下文:
    章节路径: str
    正文语料: str
    段落列表: list[str]
    正文事实: list[事实声明]
    IR事实: list[事实声明]
    规则事实: list[事实声明]
    前序章节事实: list[事实声明]
    事实对候选: list[dict]
    来源索引表: 来源索引
    failure_evidence: list[dict]
    索引事实表: dict = field(default_factory=dict)
    索引事实对表: dict = field(default_factory=dict)
    indexed_facts: list = field(default_factory=list)
    indexed_fact_pairs: list = field(default_factory=list)
    response_schema_version: str = ""


def _提取时间标记(句: str) -> str:
    found = [m for m in _TIME_MARKERS if m in 句]
    for m in _CHANGE_MARKERS:
        if m in 句 and m not in found:
            found.append(m)
    return "/".join(found[:4])


def _是否否定(句: str, *, 显式否定: str = "") -> bool:
    if 显式否定:
        return True
    return any(句.startswith(p) or f"{p}" in 句[:12] for p in _NEGATION_PREFIX)


_BAD_ENTITY_PREFIX = ("因为", "所以", "如果", "虽然", "而且", "然后", "因此", "忽然", "段落", "而")
_BAD_ENTITY_SUFFIX = ("正在", "已经", "仍然", "察觉", "异常")


_BAD_ENTITY_CONTAINS = ("表明", "读数", "回报", "察觉", "异常")


def _像事实实体(实体: str) -> bool:
    name = 实体.strip()
    if not name or len(name) > 8:
        return False
    if any(name.startswith(p) for p in _BAD_ENTITY_PREFIX):
        return False
    if any(name.endswith(s) for s in _BAD_ENTITY_SUFFIX):
        return False
    if any(x in name for x in _BAD_ENTITY_CONTAINS):
        return False
    return True


def _层级实体自关键词前(句: str, 关键词: str) -> str:
    pos = 句.find(关键词)
    if pos < 4:
        return ""
    before = 句[:pos]
    for plen in range(2, 5):
        if len(before) < plen + 2:
            continue
        cand = before[-(plen + 2) :]
        if not cand.endswith("层级"):
            continue
        if _像事实实体(cand):
            return cand
    return ""


def _提取层级事实(
    sent: str,
    *,
    关键词: str,
    来源类型: str,
    来源路径: str,
    段落: int,
    value_tail: str = r"[^。，；\n]{1,20}",
) -> 事实声明 | None:
    if 关键词 not in sent:
        return None
    entity = _层级实体自关键词前(sent, 关键词)
    m = re.search(rf"{re.escape(关键词)}(?P<value>{value_tail})", sent)
    if not entity or not m:
        return None
    return _构造事实(
        实体=entity, 属性="层级", 值=m.group("value"),
        来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
    )


def _清理实体(实体: str) -> str:
    name = 实体.strip().rstrip("的")
    for suffix in ("已经", "还在", "曾经", "仍然", "不再", "不", "没", "没有", "并非", "不是"):
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[: -len(suffix)]
    return name


def _构造事实(
    *,
    实体: str,
    属性: str,
    值: str,
    来源类型: str,
    来源路径: str,
    段落: int,
    摘句: str,
    否定: bool = False,
) -> 事实声明 | None:
    entity = _清理实体(实体)
    attr = 属性.strip()
    value = 值.strip().rstrip("，,。；;")
    if not entity or not value or not _像事实实体(entity):
        return None
    if not attr:
        attr = "状态"
    norm_attr = 归一化属性(attr)
    norm_val = 归一化值(norm_attr, value)
    return 事实声明(
        实体=entity,
        属性=attr,
        值=value,
        归一化值=norm_val,
        时间标记=_提取时间标记(摘句),
        否定=否定,
        来源类型=来源类型,  # type: ignore[arg-type]
        来源路径=来源路径,
        段落=段落,
        摘句=摘句[:120],
    )


def _从句提取事实(
    句: str,
    *,
    来源类型: str,
    来源路径: str,
    段落: int,
) -> list[事实声明]:
    facts: list[事实声明] = []
    sent = 句.strip()
    if not sent:
        return facts
    used_spans: list[tuple[int, int]] = []

    def _重叠(start: int, end: int) -> bool:
        return any(start < ue and end > us for us, ue in used_spans)

    def _标记(start: int, end: int) -> None:
        used_spans.append((start, end))

    for pattern, kind in _FACT_PATTERNS:
        for match in re.finditer(pattern, sent):
            if _重叠(match.start(), match.end()):
                continue
            groups = match.groupdict()
            entity = groups.get("entity") or ""
            if kind == "的属值为":
                fact = _构造事实(
                    实体=entity, 属性=groups.get("attr", ""), 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind == "的属变化":
                fact = _构造事实(
                    实体=entity, 属性=groups.get("attr", ""), 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind in ("是", "是否定", "并非"):
                neg = bool(groups.get("neg")) or kind in ("是否定", "并非")
                fact = _构造事实(
                    实体=entity, 属性="身份", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent, 否定=neg,
                )
            elif kind == "从未":
                fact = _构造事实(
                    实体=entity, 属性="状态", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent, 否定=True,
                )
            elif kind == "不在":
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent, 否定=True,
                )
            elif kind in ("有", "有无"):
                neg = groups.get("neg") == "没有"
                fact = _构造事实(
                    实体=entity, 属性="持有", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent, 否定=neg,
                )
            elif kind in ("肢体", "肢体简"):
                limb = groups.get("limb", "肢体")
                fact = _构造事实(
                    实体=entity, 属性=f"{limb}状态", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind == "位置动":
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind in ("仍在", "抵达", "直抵"):
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind == "时抵达":
                entity = groups.get("entity") or entity
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
                if fact:
                    fact.时间标记 = groups.get("time", "") or fact.时间标记
            elif kind == "时还在":
                entity = groups.get("entity") or entity
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
                if fact:
                    fact.时间标记 = groups.get("time", "") or fact.时间标记
            elif kind == "时位":
                entity = groups.get("entity") or entity
                action = groups.get("action", "位于")
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
                if fact:
                    fact.时间标记 = groups.get("time", "") or fact.时间标记
                    if action == "离开":
                        fact.否定 = False
            elif kind == "规则状态":
                fact = _构造事实(
                    实体=entity, 属性="状态", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind == "层级否定":
                value = groups.get("value", "").strip()
                fact = _构造事实(
                    实体=value or "对象", 属性="层级", 值="不属于",
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent, 否定=True,
                )
            elif kind == "位于简":
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind == "已到":
                fact = _构造事实(
                    实体=entity, 属性="位置", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind == "肢臂":
                fact = _构造事实(
                    实体=entity, 属性="肢体状态", 值=f"{groups.get('limb', '')}{groups.get('value', '')}",
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            elif kind == "状态":
                fact = _构造事实(
                    实体=entity, 属性="状态", 值=groups.get("value", ""),
                    来源类型=来源类型, 来源路径=来源路径, 段落=段落, 摘句=sent,
                )
            else:
                fact = None
            if fact:
                facts.append(fact)
                _标记(match.start(), match.end())

    for keyword in ("仍标记为", "仍被标记为"):
        fact = _提取层级事实(
            sent, 关键词=keyword, 来源类型=来源类型, 来源路径=来源路径, 段落=段落,
        )
        if fact:
            facts.append(fact)
            break
    for keyword in ("已经进入", "已经变成", "已经变为"):
        fact = _提取层级事实(
            sent, 关键词=keyword, 来源类型=来源类型, 来源路径=来源路径, 段落=段落,
        )
        if fact:
            facts.append(fact)
            break
    return facts


def _从段落提取事实(
    paragraphs: list[str],
    *,
    来源类型: str,
    来源路径: str,
    规则句: bool = False,
) -> list[事实声明]:
    facts: list[事实声明] = []
    for p_idx, para in enumerate(paragraphs, start=1):
        if 规则句 and not any(m in para for m in _RULE_MARKERS):
            continue
        for sent in re.split(r"(?<=[。！？!?])", para):
            facts.extend(
                _从句提取事实(sent, 来源类型=来源类型, 来源路径=来源路径, 段落=p_idx)
            )
    return facts


def _去重事实(facts: list[事实声明]) -> list[事实声明]:
    seen: set[tuple] = set()
    out: list[事实声明] = []
    for fact in facts:
        key = (
            fact.实体,
            归一化属性(fact.属性),
            fact.归一化值,
            fact.否定,
            fact.来源类型,
            fact.来源路径,
            fact.段落,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(fact)
    return out


def _构建来源索引(
    正文路径: str,
    段落: list[str],
    IR事实: list[事实声明],
    前序事实: list[事实声明],
    规则事实: list[事实声明],
) -> 来源索引:
    index = 来源索引()
    for p_idx, para in enumerate(段落, start=1):
        index.注册("正文", 正文路径, p_idx, para)
    for fact in IR事实:
        index.注册("IR", fact.来源路径, fact.段落, fact.摘句 or "")
    for fact in 前序事实:
        index.注册("前序章节", fact.来源路径, fact.段落, fact.摘句 or "")
    for fact in 规则事实:
        index.注册("规则", fact.来源路径, fact.段落, fact.摘句 or "")
    return index


def _读IR(ir_dir: Path | None) -> list[事实声明]:
    if ir_dir is None or not ir_dir.is_dir():
        return []
    facts: list[事实声明] = []
    for path in sorted(ir_dir.glob("IR-*.md")):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip("- ").strip()
            if not line or line.startswith("#"):
                continue
            for fact in _从句提取事实(
                line, 来源类型="IR", 来源路径=str(path.resolve()), 段落=line_no
            ):
                facts.append(fact)
    return facts


def _读前序章节(paths: list[Path]) -> list[事实声明]:
    facts: list[事实声明] = []
    for prior in paths:
        if not prior.exists():
            continue
        body, paragraphs, resolved = 读取章节正文(prior)
        for fact in _从段落提取事实(
            paragraphs, 来源类型="前序章节", 来源路径=str(resolved), 规则句=False
        ):
            facts.append(fact)
        if not facts and body.strip():
            for p_idx, para in enumerate(paragraphs, start=1):
                for fact in _从句提取事实(
                    para, 来源类型="前序章节", 来源路径=str(resolved), 段落=p_idx
                ):
                    facts.append(fact)
    return facts


def _配对事实(正文事实: list[事实声明], 对照: list[事实声明]) -> list[dict]:
    pairs: list[dict] = []
    for a in 正文事实:
        norm_a = 归一化属性(a.属性)
        for b in 对照:
            if a.实体 != b.实体:
                continue
            if 归一化属性(b.属性) != norm_a:
                continue
            if a.归一化值 == b.归一化值 and not (a.否定 ^ b.否定):
                continue
            pairs.append(
                {
                    "entity": a.实体,
                    "attribute": a.属性,
                    "normalized_attribute": norm_a,
                    "source_a": asdict(a),
                    "source_b": asdict(b),
                    "value_a": a.归一化值,
                    "value_b": b.归一化值,
                    "time_a": a.时间标记,
                    "time_b": b.时间标记,
                }
            )
    return pairs


def _配对正文内部事实(正文事实: list[事实声明]) -> list[dict]:
    pairs: list[dict] = []
    for i, a in enumerate(正文事实):
        norm_a = 归一化属性(a.属性)
        for b in 正文事实[i + 1 :]:
            if a.实体 != b.实体:
                continue
            if 归一化属性(b.属性) != norm_a:
                continue
            if a.归一化值 == b.归一化值 and not (a.否定 ^ b.否定):
                continue
            pairs.append(
                {
                    "entity": a.实体,
                    "attribute": a.属性,
                    "normalized_attribute": norm_a,
                    "source_a": asdict(a),
                    "source_b": asdict(b),
                    "value_a": a.归一化值,
                    "value_b": b.归一化值,
                    "time_a": a.时间标记,
                    "time_b": b.时间标记,
                    "candidate_relation": "POSSIBLE_CONFLICT",
                }
            )
    return pairs


def 构造一致性上下文(
    chapter_path: Path,
    item: 失败输入,
    *,
    repo_root: Path | None = None,
    ir_dir: Path | None = None,
    prior_chapters: list[Path] | None = None,
) -> 一致性上下文:
    正文, 段落, resolved = 读取章节正文(chapter_path, repo_root=repo_root)
    source_path = str(resolved)
    正文事实 = _去重事实(_从段落提取事实(段落, 来源类型="正文", 来源路径=source_path))
    IR事实 = _去重事实(_读IR(ir_dir))
    前序 = _去重事实(_读前序章节(prior_chapters or []))
    规则事实 = _去重事实(_从段落提取事实(段落, 来源类型="规则", 来源路径=source_path, 规则句=True))
    索引 = _构建来源索引(source_path, 段落, IR事实, 前序, 规则事实)

    事实对: list[dict] = []
    事实对.extend(_配对正文内部事实(正文事实))
    for group in (IR事实, 前序, 规则事实):
        事实对.extend(_配对事实(正文事实, group))

    from 事实索引 import CONSISTENCY_RESPONSE_SCHEMA, 构建索引包

    ctx = 一致性上下文(
        章节路径=source_path,
        正文语料=正文,
        段落列表=段落,
        正文事实=正文事实,
        IR事实=IR事实,
        规则事实=规则事实,
        前序章节事实=前序,
        事实对候选=事实对[:40],
        来源索引表=索引,
        failure_evidence=[{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句],
        response_schema_version=CONSISTENCY_RESPONSE_SCHEMA,
    )
    indexed_facts, indexed_pairs, fact_by_id, pair_by_id = 构建索引包(ctx)
    ctx.indexed_facts = indexed_facts
    ctx.indexed_fact_pairs = indexed_pairs
    ctx.索引事实表 = fact_by_id
    ctx.索引事实对表 = pair_by_id
    return ctx


def 上下文转诊断输入(ctx: 一致性上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-06",
        "response_schema_version": ctx.response_schema_version,
        "failure_type": item.失败类型,
        "indexed_facts": ctx.indexed_facts,
        "indexed_fact_pairs": ctx.indexed_fact_pairs,
        "source_index_types": sorted(ctx.来源索引表.条目.keys()),
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
