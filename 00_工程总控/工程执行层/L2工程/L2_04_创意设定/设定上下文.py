from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from L2模型 import 失败输入
from 证据索引 import SETTING_RESPONSE_SCHEMA, 构建证据索引
from 正文读取 import 读取章节正文
from 设定模型 import 代价, 规则, 设定实体, 限制
from 通用证据定位 import 切分句子

_RULE_STRUCT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"凡([^，。！？]+)者[，,](.+)"), "凡者"),
    (re.compile(r"如果([^，。！？]+)[，,]?就(.+)"), "如果就"),
    (re.compile(r"若([^，。！？]+)[，,]?则(.+)"), "若则"),
    (re.compile(r"一旦([^，。！？]+)[，,].*?(?:就|会)(.+)"), "一旦"),
    (re.compile(r"每当([^，。！？]+)[，,].*?(?:就|会)(.+)"), "每当"),
    (re.compile(r"每次([^，。！？]+)[，,].*?(?:都)?(?:会|就)(.+)"), "每次"),
    (re.compile(r"只要([^，。！？]+)[，,]?就(.+)"), "只要"),
    (re.compile(r"当([^，。！？]+)时[，,](.+)"), "当时"),
    (re.compile(r"(触发[^，。！？]+后)[，,](.+)"), "触发后"),
)
_LIMIT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"只有([^，。！？]+?)，([^，。！？]+?)才(.+)"), "只有才主体"),
    (re.compile(r"只有([^，。！？]+?)才(.+)"), "只有才"),
    (re.compile(r"必须([^，。！？]+?)才能(.+)"), "必须才能"),
    (re.compile(r"未经([^，。！？]+?)不得(.+)"), "未经不得"),
    (re.compile(r"若无([^，。！？]+?)，?不能(.+)"), "若无不能"),
    (re.compile(r"除非([^，。！？]+)[，,]?否则(.+)"), "除非否则"),
    (re.compile(r"(唯有[^。！？]+)"), "唯有"),
    (re.compile(r"(不得[^。！？]+)"), "不得"),
    (re.compile(r"(不能[^。！？]+)"), "不能"),
    (re.compile(r"(禁止[^。！？]+)"), "禁止"),
    (re.compile(r"(只能[^。！？]+)"), "只能"),
    (re.compile(r"(仅限[^。！？]+)"), "仅限"),
    (re.compile(r"(?:最多|至少)[^。！？]+"), "数量限"),
)
_QUANTITY_ONLY = re.compile(r"只有(?:一|两|三|四|五|几|数|个|位|名|人|条|把|张)")
_COST_KEYWORDS = (
    "忘记", "缩短", "扣除", "损伤", "受伤", "付出", "耗尽", "减少", "丧失",
    "献出", "燃烧", "折损", "反噬", "失去", "消耗",
)
_NARRATION_ONLY = re.compile(r"^[^，。！？]{0,8}(?:他|她|众人|人群)(?:走|看|望|站|坐)")


@dataclass
class 设定上下文:
    章节路径: str
    正文语料: str
    段落列表: list[str]
    正文事实: list[str]
    IR事实: list[str]
    模型推断: list[str]
    尚无证据: list[str]
    设定实体表: list[设定实体]
    规则表: list[规则]
    限制表: list[限制]
    代价表: list[代价]
    failure_evidence: list[dict]
    案例根目录: str = ""
    chapter_rel_path: str = ""
    response_schema_version: str = SETTING_RESPONSE_SCHEMA
    indexed_evidence: list[dict] = field(default_factory=list)
    证据表: dict = field(default_factory=dict)


def _读IR片段(ir_dir: Path | None) -> list[str]:
    if ir_dir is None or not ir_dir.is_dir():
        return []
    facts: list[str] = []
    for path in sorted(ir_dir.glob("IR-*.md")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            cleaned = line.strip("- ").strip()
            if cleaned and not cleaned.startswith("#"):
                facts.append(f"[IR:{path.name}:L{line_no}] {cleaned[:100]}")
    return facts[:20]


def _代价描述(effect: str, full: str) -> str | None:
    for kw in _COST_KEYWORDS:
        if kw in effect or kw in full:
            idx = full.find(kw)
            return full[idx:].strip().rstrip("。！？") if idx >= 0 else effect.strip()
    return None


def _提取规则限制代价(
    段落列表: list[str],
    source_path: str,
) -> tuple[list[规则], list[限制], list[代价], list[设定实体], list[str]]:
    规则表: list[规则] = []
    限制表: list[限制] = []
    代价表: list[代价] = []
    实体表: list[设定实体] = []
    事实: list[str] = []
    seen: set[str] = set()

    for p_idx, para in enumerate(段落列表, start=1):
        for s_idx, sent in enumerate(切分句子(para), start=1):
            sent = sent.strip()
            if not sent or _NARRATION_ONLY.match(sent):
                continue
            ev = {
                "source_type": "正文",
                "source_path": source_path,
                "paragraph": p_idx,
                "quote": sent,
                "sentence": s_idx,
            }
            matched_struct = False
            for pat, kind in _RULE_STRUCT_PATTERNS:
                m = pat.search(sent)
                if not m:
                    continue
                if kind in ("凡者", "如果就", "若则", "一旦", "每当", "每次", "只要", "当时", "触发后"):
                    condition = m.group(1).strip()
                    effect = m.group(2).strip().rstrip("。！？")
                else:
                    continue
                key = f"rule:{condition[:16]}:{effect[:16]}"
                if key in seen:
                    matched_struct = True
                    break
                seen.add(key)
                规则表.append(
                    规则(
                        名称=effect[:40],
                        触发条件=condition,
                        subject=None,
                        condition=condition,
                        effect=effect,
                        **ev,
                    )
                )
                实体表.append(
                    设定实体(
                        名称=condition[:12],
                        source_type=ev["source_type"],
                        source_path=ev["source_path"],
                        paragraph=ev["paragraph"],
                        quote=ev["quote"],
                    )
                )
                事实.append(f"[P{p_idx}:S{s_idx}] {sent[:100]}")
                cost_desc = _代价描述(effect, sent)
                bearer_m = re.search(r"([\u4e00-\u9fff]{2,6})(?:都会|会)", effect)
                bearer = bearer_m.group(1) if bearer_m else ""
                if cost_desc:
                    代价表.append(
                        代价(
                            描述=cost_desc,
                            触发条件=condition,
                            承受者=bearer,
                            **ev,
                        )
                    )
                matched_struct = True
                break
            if matched_struct:
                continue
            for pat, kind in _LIMIT_PATTERNS:
                m = pat.search(sent)
                if not m:
                    continue
                if kind in ("只有才", "只有才主体", "必须才能", "未经不得", "若无不能"):
                    if _QUANTITY_ONLY.search(sent):
                        continue
                subject = ""
                precondition = ""
                result = ""
                if kind == "只有才主体":
                    precondition = m.group(1).strip()
                    subject = m.group(2).strip()
                    result = m.group(3).strip().rstrip("。！？")
                    desc = f"只有{precondition}，{subject}才{result}"
                elif kind == "只有才":
                    precondition = m.group(1).strip()
                    result = m.group(2).strip().rstrip("。！？")
                    desc = f"只有{precondition}才{result}"
                elif kind == "必须才能":
                    precondition = m.group(1).strip()
                    result = m.group(2).strip().rstrip("。！？")
                    desc = f"必须{precondition}才能{result}"
                elif kind == "未经不得":
                    precondition = m.group(1).strip()
                    result = m.group(2).strip().rstrip("。！？")
                    desc = f"未经{precondition}不得{result}"
                elif kind == "若无不能":
                    precondition = m.group(1).strip()
                    result = m.group(2).strip().rstrip("。！？")
                    desc = f"若无{precondition}不能{result}"
                elif kind == "除非否则":
                    precondition = m.group(1).strip()
                    result = m.group(2).strip().rstrip("。！？")
                    desc = f"除非{precondition}，否则{result}"
                else:
                    desc = m.group(0).strip().rstrip("。！？")
                    precondition = ""
                    result = desc
                key = f"limit:{desc[:24]}"
                if key in seen:
                    break
                seen.add(key)
                限制表.append(
                    限制(
                        描述=desc,
                        前置条件=precondition,
                        限制结果=result,
                        subject=subject,
                        condition=precondition,
                        effect_or_permission=result,
                        constraint_type="REQUIRED_CONDITION" if kind in (
                            "只有才", "只有才主体", "必须才能", "未经不得", "若无不能", "除非否则"
                        ) else "",
                        **ev,
                    )
                )
                实体表.append(
                    设定实体(
                        名称=desc[:12],
                        source_type=ev["source_type"],
                        source_path=ev["source_path"],
                        paragraph=ev["paragraph"],
                        quote=ev["quote"],
                    )
                )
                事实.append(f"[P{p_idx}:S{s_idx}] {sent[:100]}")
                break

    return 规则表, 限制表, 代价表, 实体表, 事实


def 构造设定上下文(
    chapter_path: Path,
    item: 失败输入,
    *,
    repo_root: Path | None = None,
    ir_dir: Path | None = None,
) -> 设定上下文:
    正文, 段落列表, resolved = 读取章节正文(chapter_path, repo_root=repo_root)
    source_path = str(resolved)
    规则表, 限制表, 代价表, 实体表, 正文事实 = _提取规则限制代价(段落列表, source_path)
    IR事实 = _读IR片段(ir_dir)
    尚无证据: list[str] = []
    if not 规则表 and not 限制表 and not 代价表:
        尚无证据.append("正文未提取到带证据的规则/限制/代价句")
    if ir_dir and not IR事实:
        尚无证据.append("IR 目录存在但未读到可用事实行")
    case_root = repo_root.resolve() if repo_root else (
        resolved.parent.parent if resolved.parent.name == "chapters" else resolved.parent
    )
    chapter_rel = "chapters/chapter.md"
    try:
        chapter_rel = chapter_path.resolve().relative_to(case_root).as_posix()
    except ValueError:
        chapter_rel = chapter_path.name
    failure_ev = [{"paragraph": e.段落, "quote": e.摘句} for e in item.证据 if e.摘句]
    indexed, by_id = 构建证据索引(
        case_root=case_root,
        chapter_rel_path=chapter_rel,
        paragraph_list=段落列表,
        rules=规则表,
        limits=限制表,
        costs=代价表,
        ir_dir=ir_dir,
        failure_evidence=failure_ev,
    )
    return 设定上下文(
        章节路径=source_path,
        正文语料=正文,
        段落列表=段落列表,
        正文事实=正文事实[:16],
        IR事实=IR事实,
        模型推断=[],
        尚无证据=尚无证据,
        设定实体表=实体表[:12],
        规则表=规则表,
        限制表=限制表,
        代价表=代价表,
        failure_evidence=failure_ev,
        案例根目录=str(case_root),
        chapter_rel_path=chapter_rel,
        response_schema_version=SETTING_RESPONSE_SCHEMA,
        indexed_evidence=indexed,
        证据表=by_id,
    )


def 上下文转诊断输入(ctx: 设定上下文, item: 失败输入) -> dict:
    return {
        "module": "L2-04",
        "response_schema_version": ctx.response_schema_version,
        "failure_type": item.失败类型,
        "indexed_evidence": ctx.indexed_evidence,
        "text_facts": ctx.正文事实,
        "ir_facts": ctx.IR事实,
        "inferred": ctx.模型推断,
        "unverified": ctx.尚无证据,
        "entities": [asdict(e) for e in ctx.设定实体表],
        "rules": [asdict(r) for r in ctx.规则表],
        "limits": [asdict(l) for l in ctx.限制表],
        "costs": [asdict(c) for c in ctx.代价表],
        "failure_evidence": ctx.failure_evidence,
        "chapter_excerpt": ctx.正文语料[:2000],
    }
