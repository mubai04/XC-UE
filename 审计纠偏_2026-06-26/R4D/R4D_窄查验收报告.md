# R4D 外部反例窄查验收报告

验收时间：2026-06-28  
验收性质：只读验证（未修改生产代码与测试）

---

## 1. 代码身份

| 项 | 值 |
|---|---|
| HEAD | `7a90a46d809547ff222b49ab86c58ddf51915871` |
| 分支 | `l1-phase2` |
| 工作树 | **dirty**（存在大量未提交修改） |
| R4D 相关修改是否仍在工作树 | **是** — L2-02～L2-06 模块、`公共执行层/前序章节.py`、`公共执行层/领域证据.py`、R4D 测试文件等均处于 modified/untracked 状态 |

---

## 2. 测试收集数量（`--collect-only`，未运行）

| 范围 | 数量 |
|---|---|
| 窄查套件合计 node ID | **103** |
| `test_L2_外部反例.py` | **20** |
| `test_L2_禁止反例硬编码.py` | **6**（6 个参数化目录） |
| 全仓 `pytest --collect-only` | **192** |

**数量矛盾澄清（以 collect 为准）：**

- 「20 passed, 1 skipped」指窄查**运行**结果：103 项收集中 symlink 项在 Windows 上 skip，故 **102 passed + 1 skipped**，不是 20。
- 「防硬编码 6 项」= `test_L2_禁止反例硬编码.py` 的 6 个参数化用例。
- 「新增合计 26 项」= 外部反例 20 + 防硬编码 6；窄查套件还包含原有 L2 能力/流水线/L1.5 回归共 77 项。
- 「全量 191 passed, 1 skipped」= 全仓 192 项收集中 1 项 symlink skip，**191 passed**；不是「从 166 变 191」的独立事实，仅为当前全量快照。

**Skipped 用例（collect 可见）：**

- `tests/test_L2_外部反例.py::test_l2_06_rejects_symlink_escape`
  - `@pytest.mark.skipif(not hasattr(os, "symlink"), reason="平台不支持 symlink")`
  - 运行时若 `link.symlink_to(outside)` 抛 `OSError`，再 `pytest.skip("symlink creation blocked")`

---

## 3. 窄查测试运行结果

```
exit code: 0
passed: 102
failed: 0
skipped: 1
duration: ~2.78s
```

Skipped：`test_l2_06_rejects_symlink_escape`（symlink 创建被阻断或平台无 symlink 能力）。

---

## 4. 全量测试运行结果

```
exit code: 0
passed: 191
failed: 0
skipped: 1
duration: ~17.45s
```

---

## 5. Skip 审查

- Symlink 测试 skip 原因：Windows 环境常见无创建 symlink 权限；测试在 `OSError` 时主动 `pytest.skip("symlink creation blocked")`，属于平台能力限制，**可接受**。
- 非 symlink 路径防护已由其他用例覆盖且通过：
  - `test_l2_06_rejects_prior_path_escape`（`../` 逃逸）
  - `test_l2_06_prior_and_source` 等（合法前序、source_type 绑定）
  - 临时探针：`../outside.md` → `PRIOR_CHAPTER_PATH_OUT_OF_SCOPE`

---

## 6. 五模块静态核验（文件与行号证据）

### L2-02 文风语言

| 检查项 | 结论 | 证据 |
|---|---|---|
| 说话证据含 speaker / speaker_confidence | **成立** | `公共执行层/领域证据.py` 42–78：`识别对话证据` 返回 `speaker`、`speaker_confidence` |
| 语气漂移要求双来源、EXPLICIT、同 speaker、speaker=character | **成立** | `文风证据校验.py` 30–66 |
| 不同人物对话不能通过 | **成立** | 探针 A 交叉校验报错；`文风证据校验.py` 61–62 |
| 同句双填不能通过 | **成立** | `文风证据校验.py` 50–51 |
| 单来源仅 EVIDENCE_INSUFFICIENT | **成立** | `文风证据校验.py` 32–38 |
| 不强行绑定 UNKNOWN 说话人 | **成立** | `文风证据校验.py` 55–56 要求 `conf == "EXPLICIT"` |
| **局限** | 「周砚低声问」类插入副词句式无法识别 EXPLICIT 说话人 | `领域证据.py` 52–58 仅匹配 `说|问|答|喊|道` 直连人名 |

### L2-03 角色心理

| 检查项 | 结论 | 证据 |
|---|---|---|
| 无 `name == name` | **成立** | 全仓 L2 生产代码 grep 无匹配 |
| 结果关联用具体角色字段 | **成立** | `角色模型.py` 34–35 `行为结果.角色`；`角色上下文.py` 结果解析 165–184 |
| `行为结果` 含角色字段 | **成立** | `角色模型.py` 34–35 |
| 誓/誓要/想/想要/准备/决定/受伤 不并入姓名 | **部分成立** | `角色上下文.py` 15–17 `NAME_TRIM_SUFFIXES`；测试 `test_l2_03_guchuan_shi_trim_not_character` 通过 |
| 事件句不进角色名 | **部分成立** | `EVENT_START_MARKERS` 18；但「警铃响起」仍可能被 `_解析刺激` 147–152 误收为实体前缀 |
| 两人物目标/行为/结果不串线 | **仓库反例成立** | `test_l2_03_dual_character_chains_no_crosswire` 通过 |
| 无明确人物时空/不确定 | **部分成立** | `_最近明确角色` 98–106 多命中返回空 |

### L2-04 创意设定

| 检查项 | 结论 | 证据 |
|---|---|---|
| 凡/如果/若/一旦/每当/每次/只有/除非 模式 | **成立** | `设定上下文.py` 13–25 `_RULE_PATTERNS` |
| 代价不限于失去/消耗 | **成立** | 代价模式与 `设定上下文.py` 代价分支 |
| 不依赖特定人物/术法/道具句 | **成立** | 模式为通用正则；`test_l2_04_variant_extracts_from_replaced_terms` 通过 |

### L2-05 市场体验

| 检查项 | 结论 | 证据 |
|---|---|---|
| 即时收益有 reward_type | **成立** | `体验模型.py` 51；`阅读阶段上下文.py` 98–128 |
| ITEM/INFORMATION 等有提取逻辑 | **成立** | `阅读阶段上下文.py` 18–19、98–110 |
| 拿到/摸出/找到/获得 等物品收益 | **逻辑存在** | `_ITEM_PAT` 18；但仅扫描至 `阶段[1].结束段落`（116–119），末段物品不进入即时收益 |
| 重复信息去说话前缀与再次/仍然 | **成立** | `_标准化重复核心` 153–157 |
| 同源不同说话人可成重复候选 | **仓库测试成立** | `test_l2_05_repeat_info_same_core_statement` |
| 仅共享普通词不判重复 | **成立** | `test_l2_05_similar_words_not_repeat` |
| 末段推动力只读最后阅读阶段 | **成立** | 末段阶段切分 `_阶段切分` 63–77；末段为最后四分之一段落 |
| 修复规划按风险分流 | **弱** | `体验修复规划.py` 17–35 按 `risk_type` 与入口/末段拼接，非单一动作，但动作模板仍较同质 |

### L2-06 系统一致性（最高优先级）

| 检查项 | 结论 | 证据 |
|---|---|---|
| 前序章节路径 resolve | **成立** | `前序章节.py` 39 `resolve()` |
| 候选路径同时在 project_root 与 content_root | **成立** | `前序章节.py` 41–42 `assert_inside_root` 两次 |
| 拒绝绝对路径 / ../ / symlink 逃逸 / 缺失 / 目录 | **成立** | `前序章节.py` 35–55 |
| 专用错误 PRIOR_CHAPTER_PATH_OUT_OF_SCOPE | **成立** | `前序章节.py` 36–55 |
| 否定模式优先、span 不重复消费 | **成立** | `一致性上下文.py` 123–129 `used_spans`、223 `_标记` |
| 否定句各只产生一条事实 | **成立** | 探针否定 + `test_l2_06_negation_single_fact` |
| 实体不带否定后缀 | **成立** | `test_l2_06_negation_single_fact` 断言无 `实体.endswith("不")` |
| 来源校验绑定 source_type/path/paragraph/quote/entity/attribute | **成立** | `双来源校验.py` 143–166 |
| 无「quote 在全文即匹配」弱回退（事实绑定） | **部分** | `_匹配事实` 65–78：有摘句匹配事实时严格；**无匹配事实时返回 True**（宽松） |
| `_摘句可定位` 使用 `quote in entry.文本` | **存在** | `双来源校验.py` 96–97（定位用，非 entity 绑定） |
| **`复核冲突分类` 在模型分类后实际执行** | **未成立** | `冲突比对.py` 64–146 `执行冲突比对` 解析模型 JSON 后**未调用** `复核冲突分类`；仅测试与临时探针直接调用 |
| 有时间+移动桥梁时 HARD→ALLOWED_CHANGE | **函数级成立、流水线未接线** | `复核冲突分类` 43–50、52–59；仅覆盖 **城外/城内** 硬编码对，非任意地点 |
| 无桥梁时 EXPLANATION_INSUFFICIENT | **同上局限** | `复核冲突分类` 49–50、58–59 |
| EVIDENCE_INSUFFICIENT 允许 source_b 空 | **成立** | `双来源校验.py` 130–134 |
| ALLOWED_CHANGE 不生成纠错修复 | **成立** | `一致性修复规划.py` 17–18 `continue` |
| EVIDENCE_INSUFFICIENT 只补证据 | **成立** | `一致性修复规划.py` 19–22 |

---

## 7. 五组独立临时探针（系统临时目录一次性脚本，已删除）

探针使用仓库测试未出现的人物/设定/道具/地点。脚本路径已删除：`%TEMP%\xcue_r4d_probe.py`。

### A. L2-02（周砚 / 陆遥）

**输入：**

```text
周砚说：“立刻撤离。”
周砚低声问：“还能再等一刻吗？”
陆遥说：“谁也不准离开。”
```

**实际输出摘要：**

- `dual_source_ready` 周砚：**无**（第二句「周砚低声问」未识别为 EXPLICIT 说话人，周砚仅 1 条对话证据）
- 周砚 vs 陆遥 交叉语气漂移：**校验拒绝**（`style_issues[0] 语气漂移双来源说话人不一致`）
- 周砚单句：`evidence_insufficient` 候选 1 条（符合「仅保留一句时证据不足」）

**判定：** 交叉拒绝与单句不足 **符合**；**同人物双句比较不符合**（第二句格式未覆盖）。

### B. L2-03（程野 / 许棠）

**输入：**

```text
程野决心找回药箱。
警铃响起，程野撞开侧门冲进库房。
许棠准备护送伤员离开。
吊灯坠落，许棠推开伤员，自己被碎片划伤。
```

**实际输出摘要：**

- `confirmed` 角色：程野、许棠
- `目标刺激行为链` 额外出现：**警铃、许棠准备护送、吊灯坠落** 等伪角色键
- 程野行为「撞开侧门冲进库房」未稳定落入 behavior；许棠 goal/behavior 被「许棠准备护送伤员离开。」整句污染

**判定：** **不符合** — 事件句「警铃响起」「吊灯坠落」进入链；人物链串线/污染。

### C. L2-04（青环）

**输入：**

```text
若佩戴青环，伤口就会停止流血。
一旦青环破裂，佩戴者会失去最近一小时的记忆。
只有交出通行牌，守门人才允许进入内城。
```

**实际输出摘要：**

- 规则表：1 条
- 代价表：1 条（「失去最近一小时的记忆」）
- 限制表：**0 条**（「只有交出通行牌…」未入限制表）

**判定：** **部分不符合** — 代价可提取；规则/限制覆盖不全。

### D. L2-05（顾临 / 北梯 / 门卡）

**输入：**

```text
地下仓库突然断电，顾临被锁在冷藏室。

广播通知北梯关闭。

巡逻员又说北梯已经关闭。

顾临在工具箱里找到一张备用门卡。

他准备刷卡时，门外传来妹妹的求救声。
```

**实际输出摘要：**

- ITEM 即时收益：**0 条**（门卡在第 4 段，超出 `阶段[1].结束段落=2` 扫描范围）
- 重复信息：**0 条**（北梯双句未聚类为重复）
- 末段推动力：段落 5「他准备刷卡时，门外传来妹妹的求救声。」
- 阅读阶段末段：段落 4–5

**判定：** **不符合** — ITEM 收益与北梯重复未检出；末段推动力 **符合**。

### E. L2-06

**路径探针：** `chapter_sequence` 含 `../outside.md` →  
`PRIOR_CHAPTER_PATH_OUT_OF_SCOPE:../ 逃逸不允许`；`解析前序章节` 返回空。**符合。**

**否定探针：**「周砚不是医生。」「周砚没有通行证。」→ 2 条否定事实，实体均为「周砚」，无重复 span。**符合。**

**时间变化（北岸/南岸，用户指定文案）：**

| 场景 | 模型输入分类 | `复核冲突分类` 输出 | 期望 |
|---|---|---|---|
| 清晨北岸 → 傍晚乘船抵南岸 | HARD_CONFLICT | **HARD_CONFLICT** | ALLOWED_CHANGE |
| 北岸 → 南岸（无桥梁） | HARD_CONFLICT | **HARD_CONFLICT** | EXPLANATION_INSUFFICIENT |

**判定：** **不符合** — `复核冲突分类` 仅硬编码 **城外/城内**（`冲突比对.py` 44–45），且未接入 `执行冲突比对` 流水线。

---

## 8. 路径逃逸测试

- 仓库：`test_l2_06_rejects_prior_path_escape` **passed**
- 临时探针：`../outside.md` **拒绝** ✓

## 9. 否定事实测试

- 仓库：`test_l2_06_negation_single_fact` **passed**
- 临时探针：每句 1 条否定事实 ✓

## 10. 时间变化分类测试

- 仓库（城外/城内 + 清晨/入夜）：`test_l2_06_allowed_change_with_time_bridge`、`test_l2_06_explanation_insufficient_without_bridge` **passed**
- 用户指定北岸/南岸探针：**失败**（见 §7.E）

## 11. 结构回归

| 检查项 | 结论 |
|---|---|
| 五独立模块目录存在 | **成立** — `test_five_independent_package_directories_exist` passed |
| 公共层无 MODULE_SPECS | **成立** — `test_old_module_spec_eliminated`；grep 生产代码无 `MODULE_SPECS` |
| 注册表只映射能力入口 | **成立** — `能力注册表.py` 22–28 `ABILITY_REGISTRY` |
| 五兼容入口转发 | **成立** — `test_compat_wrappers_delegate_to_independent_entries` passed |
| 流水线未回退统一 module_id prompt 执行器 | **成立** — `test_shared_layer_has_no_module_id_domain_switch` passed |
| 未因 R4D 重新合并领域逻辑 | **成立** — 各模块独立上下文/校验/修复规划 |

`R4B_STRUCTURE_REGRESSION`：**PASSED**（基于结构测试与静态检查）。

---

## 12–15. 过程约束

| 项 | 结果 |
|---|---|
| 是否修改生产代码 | **否** |
| 是否修改测试 | **否** |
| 是否调用真实 DeepSeek API | **否**（全部为 mock / 确定性上下文） |
| 是否生成或索要哈希 | **否** |

---

## 16. 最终标签

```
L2_02_DOMAIN_CAPABILITY = FAILED
L2_03_DOMAIN_CAPABILITY = FAILED
L2_04_DOMAIN_CAPABILITY = FAILED
L2_05_DOMAIN_CAPABILITY = FAILED
L2_06_DOMAIN_CAPABILITY = FAILED

R4B_STRUCTURE_REGRESSION = PASSED
R4D_EXTERNAL_COUNTEREXAMPLES = PASSED
R4D_INDEPENDENT_VERIFICATION = FAILED
REAL_MODEL_SEMANTIC_EFFECTIVENESS = NOT_TESTED
```

**R4D_INDEPENDENT_VERIFICATION 失败摘要：**

| 模块 | 失败输入要点 | 实际输出 | 代码位置 |
|---|---|---|---|
| L2-02 | 周砚两句（第二句含「低声」） | 未形成 `dual_source_ready` | `领域证据.py` 52–58 |
| L2-03 | 警铃/吊灯事件句 | 伪角色「警铃」「吊灯坠落」进入链 | `角色上下文.py` 147–152、206–237 |
| L2-04 | 「只有交出通行牌…」 | 限制表为空 | `设定上下文.py` 规则/限制分支 |
| L2-05 | 第 4 段门卡、北梯重复 | ITEM/重复均为 0 | `阅读阶段上下文.py` 116–119、161–180 |
| L2-06 | 北岸/南岸时间变化 | 复核仍为 HARD_CONFLICT | `冲突比对.py` 24–61（未接线且地点硬编码） |
| L2-06 | 流水线模型输出 | 不自动复核分类 | `冲突比对.py` 113–146 |

说明：窄查与全量 pytest **全部通过**，但独立临时探针与部分静态项（复核接线、地点泛化、副词对话、即时收益段落范围）**未满足验收文案要求**。

---

## 17. 尚未验证

- 真实 DeepSeek 语义效果（`REAL_MODEL_SEMANTIC_EFFECTIVENESS = NOT_TESTED`）
