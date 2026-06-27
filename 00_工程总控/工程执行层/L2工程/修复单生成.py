from __future__ import annotations



from pathlib import Path



from L2_L15执行 import 构建L15分配判断

from L2模型 import 失败输入, 接口判断, 修复单

from 能力注册表 import 获取能力入口

from 能力标准解析 import L2规则

import L2_01_叙事结构能力





GENERATORS = {

    "L2-01": L2_01_叙事结构能力.安全生成修复单,

}

for _mid in ("L2-02", "L2-03", "L2-04", "L2-05", "L2-06"):
    _gen = 获取能力入口(_mid)
    if _gen:
        GENERATORS[_mid] = _gen





def _调用生成器(

    module: str,

    source: 失败输入,

    ability_rules,

    *,

    chapter_path: Path | None,

    repo_root: Path | None,

    client,

) -> tuple[修复单 | None, str | None]:

    generator = GENERATORS.get(module)

    if not generator:

        return None, f"{module}: 未注册生成器"

    return generator(

        source,

        ability_rules,

        chapter_path=chapter_path,

        repo_root=repo_root,

        client=client,

    )





def 生成(

    items: list[失败输入],

    judgements: list[接口判断],

    rules: L2规则,

    *,

    chapter_path: str = "",

    repo_root: Path | None = None,

    client=None,

) -> tuple[list[修复单], list[str]]:

    forms: list[修复单] = []

    errors: list[str] = []

    resolved_chapter = Path(chapter_path) if chapter_path else None

    for source, judgement in zip(items, judgements):

        if judgement.最终状态 != "接口明确":

            continue

        ability_rules = rules.能力规则.get(judgement.主候选模块)

        if not ability_rules:

            errors.append(f"{judgement.主候选模块}: 缺少能力规则")

            continue

        form, warn = _调用生成器(

            judgement.主候选模块,

            source,

            ability_rules,

            chapter_path=resolved_chapter,

            repo_root=repo_root,

            client=client,

        )

        if warn:

            errors.append(warn)

        if form:

            forms.append(form)

        elif not warn:

            errors.append(f"{judgement.主候选模块}: 未生成修复单（{source.失败类型}）")

    return forms, errors





def 执行L15分配模块(

    item: 失败输入,

    target_module: str,

    rules: L2规则,

    *,

    chapter_path: str = "",

    repo_root: Path | None = None,

    client=None,

    route_rule_id: str = "",

    route_rule_version: str = "",

) -> tuple[list[修复单], list[str], 接口判断, list[接口判断]]:

    judgement = 构建L15分配判断(item, target_module, route_rule_id, route_rule_version)

    ability_rules = rules.能力规则.get(target_module)

    errors: list[str] = []

    blocked: list[接口判断] = []

    if not ability_rules:

        errors.append(f"{target_module}: 缺少能力规则")

        blocked.append(

            接口判断(

                来源闸门=item.来源闸门,

                输入来源模式="L1.5路由报告",

                输入问题=item.说明,

                初步归属="L1.5",

                主候选模块="",

                接口失败类型="MODULE_MISSING",

                判断依据=f"L1.5 分配模块 {target_module} 无能力规则",

                建议动作=["回 L1.5 重路由"],

                回流验收位置=item.回流验收位置 or item.来源闸门,

                最终状态="回L1.5",

            )

        )

        return [], errors, judgement, blocked



    if item.候选模块 and item.候选模块 != target_module:

        blocked.append(

            接口判断(

                来源闸门=item.来源闸门,

                输入来源模式="L1.5路由报告",

                输入问题=item.说明,

                初步归属=target_module,

                主候选模块=item.候选模块,

                接口失败类型="L2_BOUNDARY",

                判断依据=f"L2 不得改派：L1.5={target_module}，输入候选={item.候选模块}",

                是否越界="是",

                建议动作=["回 L1.5 重路由"],

                回流验收位置=item.回流验收位置 or item.来源闸门,

                最终状态="回L1.5",

            )

        )

        return [], [f"L2 越界改派：{item.候选模块} != {target_module}"], judgement, blocked



    resolved_chapter = Path(chapter_path) if chapter_path else None

    form, warn = _调用生成器(

        target_module,

        item,

        ability_rules,

        chapter_path=resolved_chapter,

        repo_root=repo_root,

        client=client,

    )

    if warn:

        errors.append(warn)

    forms = [form] if form else []

    return forms, errors, judgement, blocked

