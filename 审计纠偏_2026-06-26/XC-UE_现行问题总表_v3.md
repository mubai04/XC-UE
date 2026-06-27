# XC-UE 现行问题总表 v3（Phase 1 冻结更新）

**更新日期：** 2026-06-27  
**L1 Phase 1 基线：** `9f13877` · tag `l1-phase1-freeze-20260627`  
**CSV 真源：** [`XC-UE_现行问题总表_v3.csv`](XC-UE_现行问题总表_v3.csv)

## Phase 1 正式判定

```text
L1 Phase 1：ACCEPTED_FOR_FREEZE
提交基线：9f13877
置信度：97%
```

**决策架构已修复 ≠ DeepSeek 对小说的判断已被证明准确。**

## Phase 1 关闭项（VERIFIED_CLOSED）

| issue_id | 标题 | 新状态 | 验证 |
|---|---|---|---|
| V3-P1-001 | 词面规则参与最终裁决 | VERIFIED_CLOSED | 词面仅 DIAGNOSTIC；`聚合终态()` 不由词面决定 |
| V3-P1-002 | API 失败被当成正文失败 | VERIFIED_CLOSED | `AUDIT_BLOCKED` + `audit_blockers` |
| V3-P1-003 | AUDIT_BLOCKER 进入正文失败包 | VERIFIED_CLOSED | `分拆阻断项()` 分离产物 |
| V3-P1-004 | HARD_GUARD 被 API 阻断遮蔽 | VERIFIED_CLOSED | 硬护栏优先 + `semantic_audit_status` |
| V3-003 | 乱码样本词面/语义分裂 | VERIFIED_CLOSED | 全链语义 FAIL → REJECT |
| V3-043 | L1-03 SCREENING_PASS 误读 | VERIFIED_CLOSED | 子闸改为 HEURISTIC_DIAGNOSTIC |

## Phase 1 部分关闭 / 仍开放

| issue_id | 标题 | 状态 | 说明 |
|---|---|---|---|
| V3-013 | L1 状态枚举漂移 | MODIFIED | 已增 AUDIT_BLOCKED；其余枚举仍待统一 |
| V3-014 | validate-before-write | MODIFIED | L1 已写前校验；L2/L3 仍缺 |
| V3-042 | L1-SEM 失败路由 | MODIFIED | CONTENT_DECISION 可路由；AUDIT_BLOCKER 禁止路由 |

## Phase 2 入口项（不删除历史，仅标记）

| issue_id | 标题 | 状态 | 说明 |
|---|---|---|---|
| V3-P1-005 | L1-SEM 证据协议质量 | PHASE2_OPEN | exact_text / analysis_summary 分离、offset 强校验 |
| V3-P1-006 | L1 语义诊断真实准确率 | NEEDS_REAL_DATA | 需真实章节集 + 误杀/漏检/人工一致率 |
| V3-019 | 测试正文迎合关键词 | CONFIRMED | Phase 2 替换为冻结真实语料 |
| V3-026 | 无真实项目样章 | CONFIRMED | Phase 2 建立验收集 |
| V3-029 | DeepSeek 客户端重试 | NEEDS_MORE_EVIDENCE | Phase 2 纳入超时/重试/成本 |

## 统计（v3 全表 50 行含 Phase 1 增补）

| 状态 | 数量 |
|---|---|
| VERIFIED_CLOSED | 6 |
| PHASE2_OPEN | 1 |
| NEEDS_REAL_DATA | 1 |
| CONFIRMED | 18 |
| MODIFIED | 12 |
| NEEDS_MORE_EVIDENCE | 12 |

历史问题均保留于 CSV，不删除 `original_issue_id` 与旧结论列。
