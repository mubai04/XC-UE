# L1-SEM-ANCHOR-01 最终报告

## 1. 根因是否已证明

**是（高置信度）** — 通过 `--capture-semantic-evidence-debug` 保存的 `RR02-ZDXB-ANCHOR-R1-L1_semantic_evidence_debug.json` 可复现。

## 2. 实际根因

| # | 故障点 | 机制 |
|---|---|---|
| A | **弯引号 vs 直引号** | 模型对 P0054 返回 Unicode 弯引号 `"…"`，语料为 ASCII 直引号 `"…"`，首响 `冲突` 锚定失败 |
| B | **代码块内换行被合并** | P0079 语料为 `` `备案。\n一次都没有。` ``，模型返回 `备案。一次都没有。`（无 `\n`），非连续子串 → `章末追读` 锚定失败 |
| C | （次要，非锚定） | `因果` PASS 时 `final_reason` 缺字面 `行动`，触发语义校验，与 EVIDENCE_INVALID 并列导致 `AUDIT_BLOCKED` |

**不是** prompt/validator 语料不一致（修复后二者共用 `证据语料`）；**不是** BOM/CRLF/NFC 主因（首响大部分维度引文已可锚定）。

## 3. 故障链路位置

```text
API 原始响应 → exact_text 提取 → 定位摘句
  ├─ A: 字符级引号不一致（模型输出层）
  └─ B: 代码块多行合并（模型输出层，校验器正确拒绝）
→ 校验语义审计响应 → EVIDENCE_INVALID → AUDIT_BLOCKED
```

## 4. 模型 original exact_text 是否为逐字引文

**否。** 调试记录显示首响 `冲突` 使用弯引号；`章末追读` 合并了代码块两行。

## 5. prompt 语料与 validator 语料是否一致

**是（修复后）。** 均来自 `构建章节证据语料()` → 同一 `paragraph_map()`。

## 6. 换行 / Unicode 差异

- 语料内 `\n` 在代码块段落中保留（见 P0079）。
- 模型未复制 `\n`，而是句号拼接 — **非规范化差异，是引文错误**。
- 弯引号为 **标点替换**，非 NFC 等价。

## 7–10. 未修改项

| 项 | 修改？ |
|---|---|
| 业务评价标准 | **否** |
| L1 阈值 | **否** |
| 路由 | **否** |
| 模糊匹配放行 | **否** |

## 11. 新增/修改文件

| 文件 | 变更 |
|---|---|
| `公共组件/证据语料.py` | **新增** 统一语料 |
| `公共组件/语义证据校验.py` | NFC/CRLF 锚定、省略号拒绝、锚定诊断 |
| `L1工程/L1_语义审计.py` | 共用语料、证据协议 prompt、锚定纠错重试、debug 捕获 |
| `L1工程/L1运行入口.py` | `--capture-semantic-evidence-debug` |
| `tests/test_证据语料锚定.py` | **新增** 16 项离线测试 |
| `脚本/运行_REAL_REPAIR_02.py` | L1 调用启用 debug |

## 12. 离线测试结果

`tests/test_证据语料锚定.py` + `tests/test_语义证据.py`：**34 passed**

## 13–14. 真实 API

| 项 | 值 |
|---|---|
| 调用次数 | **1**（`RR02-ZDXB-ANCHOR-R1`） |
| 协议纠错重试 | **1**（`evidence_anchor_retry_count=1`） |
| 运输/格式重试 | 0 |

## 15–19. L1 复验

| 项 | 值 |
|---|---|
| L1 最终状态 | `AUDIT_BLOCKED` |
| semantic_audit_status | `AUDIT_BLOCKED` |
| audit_reason_type | `EVIDENCE_INVALID`（+ 语义字段校验） |
| failure_packet.items | **0** |
| routeable_count | **0** |
| 进入 L1.5 | **否** |
| 进入 L2/L3 | **否** |

复验较修复前：**冲突/读者收益** 经锚定重试后引文已可定位；**章末追读** 仍因代码块换行合并失败。

## 20–22. 保护项

| 项 | 状态 |
|---|---|
| 正式正文修改 | **否** |
| 外部参考稿读取 | **否** |
| 哈希 | **未生成/未索要** |

## 23. 跑偏检查

未改 Git/运行记录/S2B-2/Schema 扩建/L2/L3/路由/业务阈值；未绕过 L1-SEM。

## 24. 状态码

```text
L1_SEM_ANCHOR_REPAIR = PARTIAL
REAL_REPAIR_02 = PAUSED
PRIMARY_BLOCKER = 章末追读代码块换行合并 + 因果final_reason语义校验
```

## 后续（不在本任务范围）

1. 人工或下一轮在**不放宽校验**前提下再跑 1 次 API，观察强化后的代码块/引号协议是否足够；
2. 若模型仍合并代码块行，可考虑在 prompt 中展示 P0079 级示例（仍不改业务阈值）；
3. `因果` PASS 缺 `行动` 属语义合同校验，非锚定器 bug。

## 调试产物

`审计纠偏_2026-06-26/REAL_REPAIR_02_准点下班怎么了/runs/RR02-ZDXB-ANCHOR-R1/l1/RR02-ZDXB-ANCHOR-R1-L1_semantic_evidence_debug.json`
