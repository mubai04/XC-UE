# L1-SEM-ANCHOR-02 最终报告

## 跑偏门禁（已完成）

```text
当前主里程碑：解除同一真实案例的 L1-SEM 证据锚定阻断。
本任务直接产物：单行证据协议、最小合同修复、一次真实复验。
阻断已经发生：是（前三次 EVIDENCE_INVALID；本次锚定已解除）。
下一步直接使用者：REAL-REPAIR-02 现有流水线。
停止条件：一次真实复验完成 → 已执行。
```

## 1. 代码块换行根因是否已封堵

**是。** 复验中 P0079 使用单行 `这座大楼的建筑设计图，在规划局没有备案。`，`anchor_diagnostics=[]`，首响即锚定成功，无需证据纠错重试。

## 2. 弯引号问题是否仍严格拒绝

**是。** 离线 `test_弯引号替换拒绝` 通过；首响 `冲突` 证据为直引号 `@所有人 今晚加个班…`（P0020）。

## 3–4. Prompt 协议与 JSON 示例

**已加入**：不得跨换行符、代码块单行规则、正确/错误 JSON 示例（含禁止原因）。

## 5. final_reason 阻断根因

| 问题 | 结论 |
|---|---|
| 是否存在 `"行动" not in final_reason` | **是**（`_因果链条完整` 原实现） |
| 合同要求 | 原为 **自由文本固定汉字**；标尺文档要求「起因→行动→结果」 |
| 模型是否已表达行动语义 | **是**（`→`、事件链；缺字面「行动」） |
| 失败类型 | **自由文本关键词误阻断** |

**最小修复**：改为在 `final_reason` **或** `analysis_summary` 中检查起因/行动/结果**语义槽位**（含 `→`、`选择`、`随后` 等），不再要求字面「行动」。

## 6–9. 未修改项

业务评价标准、L1 阈值、路由、模糊匹配 — **均未修改**。

## 10. 修改文件

- `公共组件/语义证据校验.py` — `\n` 禁止、多 evidence、因果语义槽位
- `L1工程/L1_语义审计.py` — 单行协议 + JSON 示例 + 纠错提示
- `结构定义/L1语义审计响应结构.json` — evidence maxItems 1→3
- `tests/test_L1_SEM_ANCHOR_02.py` — 新增
- `tests/test_证据语料锚定.py`、`tests/test_语义证据.py` — 更新

## 11–12. 测试

| 套件 | 结果 |
|---|---|
| 定向（ANCHOR-02 + 语料 + 语义） | **49 passed** |
| 全量 pytest | **413 passed**, 3 skipped |

## 13–14. 真实 API

| 项 | 值 |
|---|---|
| REAL_API_CALLS_USED | **1** |
| run_id | `RR02-ANCHOR-R2` |
| 证据纠错重试 | **0** |

## 15. 各语义字段锚定（首响全部成功）

| 维度 | paragraph_id | 锚定 |
|---|---|---|
| 因果 | P0002 | ✓ |
| 动机 | P0009 | ✓ |
| 冲突 | P0020 | ✓ |
| 读者收益 | P0011/P0039/P0079 | ✓（3 条单行） |
| 认知成本 | P0002/P0010/P0049 | ✓ |
| 章末追读 | P0079/P0084 | ✓（含代码块单行） |

## 16–18. L1 状态

| 项 | 值 |
|---|---|
| L1 最终状态 | `AUDIT_BLOCKED` |
| 锚定层 | **通过**（非 EVIDENCE_INVALID 锚定失败） |
| 剩余阻断 | `动机: final_reason 过于空泛`（语义合同，非引文） |
| failure_packet.items | **0** |
| routeable_count | **0** |
| 进入 L1.5 | **否** |

## 19–22. 后续链

L2/L3 — **未进入**。

## 23–25. 保护项

正式正文 **未修改**；外部参考 **未读取**；哈希 **未生成**。

## 26–27. 最终状态

```text
L1_SEM_ANCHOR_REPAIR = PASSED        # 证据锚定目标达成
L1_RESULT = AUDIT_BLOCKED            # 动机 final_reason 空泛（非锚定）
REAL_REPAIR_02 = PAUSED
REAL_API_CALLS_USED = 1
FURTHER_API_RETRY = FORBIDDEN
```

## 说明

锚定任务（代码块换行、弯引号、统一语料）**已解除**；L1 仍因 **动机维度 final_reason 未命中 PHENOMENON_KEYWORDS** 被合同层阻断。该问题属 L1-SEM 语义合同校验，不在本任务「证据锚定」范围内，且不得为通过而降低 `_final_reason_specific` 业务门槛。

Debug：`runs/RR02-ANCHOR-R2/l1/RR02-ANCHOR-R2-L1_semantic_evidence_debug.json`
