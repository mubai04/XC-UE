# L1-SEM-ANCHOR-02-F 工程冻结验收报告

## 跑偏门禁（已完成）

```text
当前主里程碑：完成 L1-SEM-ANCHOR-02 严格证据位置合同补正与离线冻结。
本任务直接产物：移除位置自动修复、严格校验 paragraph_id 与 occurrence_index、修正测试假阳性、离线重放。
阻断已经发生：是。
下一步直接使用者：L1-SEM-ANCHOR-02 冻结基线。
停止条件：定向测试与离线重放完成 → 已执行。未调用 API，未处理动机具体性问题。
```

---

## 1. 是否存在 `PARAGRAPH_ID_REPAIRED`

**原存在，现已删除。** 原 `_resolve_evidence` 在指定段落未命中时调用 `_collect_scope_matches` 全章搜索，唯一命中则自动修复 `paragraph_id` 并写入 warning。

## 2. 是否删除或停用自动段落修复

**是。** `_resolve_evidence` 仅在指定 `paragraph_id` 段内查找；`_collect_scope_matches` 仅保留于 `收集锚定诊断` 诊断用途，不再参与放行。

## 3. 错误 `paragraph_id` 是否硬拒绝

**是。** 返回 `PARAGRAPH_NOT_FOUND {id} 不在 {scope} 语料中`。

## 4. 文本存在于其他段落时是否仍拒绝

**是。** 返回 `EXACT_TEXT_NOT_IN_PARAGRAPH {paragraph_id}`，不跨段搜索。

## 5. 错误 `occurrence_index` 是否硬拒绝

**是。** 文本存在但序号越界时返回 `OCCURRENCE_INDEX_INVALID occurrence_index={n} 在 {pid} 中越界`；负数为 schema 层拒绝。

## 6. `occurrence_index` 是否按指定段落内部计算

**是。** 通过 `定位摘句(para_text, exact_text, occurrence_index)` 在单段内从 0 起计非重叠匹配。

## 7. 是否修正 prompt 测试假阳性

**是。** 删除 `assert needle in text or generic_rule in text`；改为 6 项独立断言。

## 8. 是否修改冲突旧测试

**是。** `test_10_wrong_paragraph_id_repaired_when_unique` → 拒绝；`test_paragraph_id_repaired_when_exact_text_unique_in_scope` → 拒绝。

## 9. 修改文件

| 文件 | 变更 |
|---|---|
| `公共组件/语义证据校验.py` | 严格 `_resolve_evidence`；移除 `PARAGRAPH_ID_REPAIRED` 放行 |
| `tests/test_L1_SEM_ANCHOR_02.py` | 位置合同测试 + 独立 prompt 断言 + RR02 离线重放 |
| `tests/test_证据语料锚定.py` | 自动修复测试改为拒绝 |
| `tests/test_语义证据.py` | 自动修复测试改为拒绝 |

## 10. 定向测试结果

**65 passed**（`test_L1_SEM_ANCHOR_02` + `test_证据语料锚定` + `test_语义证据` 相关子集）

## 11. L1-SEM 相关测试结果

同上 **65 passed**

## 12. 全量测试结果

**429 passed, 3 skipped**（24.17s）

## 13. 全量失败是否属于既有缺失产物

**否。** 全量通过，无 R5C 缺失产物导致的失败。

## 14. 离线重放运行 ID

`RR02-ANCHOR-R2`（`parsed_final`，未修改模型响应）

## 15. 离线重放六维锚定结果

| 维度 | paragraph_id | exact_text（摘要） | occurrence_index | anchor_result |
|---|---|---|---|---|
| 因果 | P0002 | 下午六点整。陈敛关掉IDE… | 0 | PASS |
| 动机 | P0009 | 原因有两个。第一… | 0 | PASS |
| 冲突 | P0020 | @所有人 今晚加个班… | 0 | PASS |
| 读者收益 | P0011 | 【今日收割简报】 | 0 | PASS |
| 读者收益 | P0039 | 你的工位位置… | 0 | PASS |
| 读者收益 | P0079 | 这座大楼的建筑设计图，在规划局没有备案。 | 0 | PASS |
| 认知成本 | P0002 | 下午六点整… | 0 | PASS |
| 认知成本 | P0010 | 电梯门关上… | 0 | PASS |
| 认知成本 | P0049 | 赵总监办公室… | 0 | PASS |
| 章末追读 | P0079 | 这座大楼的建筑设计图，在规划局没有备案。 | 0 | PASS |
| 章末追读 | P0084 | 他掏出手机——翻到那条推送，截了个图。 | 0 | PASS |

**11 条 evidence 全部锚定通过。**

## 16. `anchor_diagnostics`

`[]`

## 17. `location_failed_dimensions`

`[]`

## 18. L1 最终状态（离线重放）

`AUDIT_BLOCKED` — 仅因 `动机: final_reason 过于空泛`（语义合同，非位置合同）

## 19. `failure_packet.items` 数量

**0**（与 RR02-ANCHOR-R2 一致，未进入 routeable）

## 20–22. L1.5 / L2 / L3

**均未进入**

## 23. 真实 API 调用次数

**0**

## 24–27. 禁止项确认

| 项 | 是否修改 |
|---|---|
| 业务评价标准 | 否 |
| L1 阈值 | 否 |
| 路由 | 否 |
| `_final_reason_specific()` | 否 |
| 正式正文 | 否 |
| 模糊匹配 | 否 |

## 28. 是否生成或索要哈希

否

## 29. 是否满足工程冻结条件

**是。** 全部验收项满足。

## 30. 未解决但发现的新问题

`动机: final_reason 过于空泛` 仍阻断 L1 整体通过 — **有意不在本任务范围**，需另立任务评估。

---

## 反向压力测试

1. **重复文本 occurrence_index 遗漏？** 离线重放全部 `occurrence_index=0`；已新增段内重复文本 0/1/越界测试，但不能保证所有多出现场景在生产语料中覆盖。**置信度：中。**

2. **其他入口绕过严格位置校验？** `校验语义审计响应` 为唯一证据锚定入口；`摘句在正文中` 仅辅助。未发现并行放行路径。**置信度：高。**

3. **离线重放能否证明未来模型永不返回错误位置？** **不能。** 仅证明 RR02-ANCHOR-R2 的 `parsed_final` 在严格合同下可锚定；未来错误 `paragraph_id`/`occurrence_index` 将被硬拒绝。

---

## 是否跑偏检查

```text
当前主里程碑：L1-SEM-ANCHOR-02 严格证据位置合同补正与离线冻结。
本次实际解决的问题：删除 PARAGRAPH_ID_REPAIRED 自动修复；严格 paragraph_id / occurrence_index；修正测试假阳性；RR02 离线重放通过。
未解决但发现的新问题：动机 final_reason 具体性阻断（不在本任务范围）。
是否触碰禁止范围：否。
是否超过停止条件：否。
是否调用真实 API：否。
是否处理动机具体性问题：否。
是否跑偏：否。
跑偏依据：任务范围内最小修改，未扩展至 L1 重构或 API 复验。
纠正动作：无。
```

---

## 最终状态

```text
L1_SEM_ANCHOR_02_CORE = PASSED
L1_SEM_ANCHOR_02_ENGINEERING_ACCEPTANCE = PASSED
L1_SEM_ANCHOR_02_FREEZE = ALLOWED
REAL_REPAIR_02 = PAUSED
REAL_API_CALLS_USED = 0
FURTHER_API_RETRY = FORBIDDEN
```
