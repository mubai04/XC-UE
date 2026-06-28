# S2A 跨层接口契约冻结结果

日期：2026-06-28  
任务：D-SYS-05｜S2A 跨层字段语义与接口契约冻结

## 1. 新契约目录

`00_工程总控/跨层接口契约/`

| 文档 | 内容 |
|------|------|
| 00_跨层契约说明.md | 总览与引用原则 |
| 01_字段命名与语义规范.md | 各层字段语义 |
| 02_旧字段迁移映射表.md | SFC-01～15 迁移决议 |
| 03_状态机边界.md | 四套状态机 |
| 04_证据与引用规范.md | 证据引用与规则来源拆分 |
| 05_L1到L3数据流示例.md | 完整编号引用链示例 |
| 06_契约版本与兼容策略.md | v1/v2 边界 |

## 2. 八个 v2 Schema（冻结候选）

路径：`00_工程总控/工程执行层/公共组件/结构定义/跨层契约/`

1. `公共引用结构_v1.json`
2. `L1发现项结构_v2.json`
3. `L1失败包结构_v2.json`
4. `L1_5路由决策结构_v2.json`
5. `L2修复单结构_v2.json`
6. `L2报告结构_v2.json`
7. `L3执行任务包结构_v2.json`
8. `L3执行结果结构_v2.json`

## 3. 十五项碰撞处理（SFC-01～15）

全部在 `02_旧字段迁移映射表.md` 逐项记录，处置类型含 KEEP / RENAME / SPLIT / DEPRECATE。

| ID | 摘要 | 处置 |
|----|------|------|
| SFC-01 | primary_failure vs 主失败类型 | RENAME → 主发现引用 / 模块内主问题 |
| SFC-02 | 失败类型跨层 | RENAME/SPLIT → L1失败类型 / 模块内主问题 |
| SFC-03 | C高认知成本闸门歧义 | SPLIT + 来源闸门 |
| SFC-04 | 认知成本路由 vs ability | SPLIT → 路由/能力规则来源 |
| SFC-05 | 候选模块 vs target_module | RENAME → 候选模块提示 / 目标模块 |
| SFC-06 | 修复方向 L1 vs L1.5 | RENAME → 修复提示 / 修复产物类型 |
| SFC-07 | 修复方向 L1.5 vs L2 | SPLIT → 修复产物类型 / 修复动作 |
| SFC-08 | final_status vs L2终态 | RENAME → 路由状态 / 修复单状态 |
| SFC-09 | L2终态 vs L3 execution_mode | SPLIT → 修复单状态 / 执行模式+执行状态 |
| SFC-10 | status L1 vs L1-03发布 | RENAME / DEPRECATE 文档语义 |
| SFC-11 | 回流验收位置 vs return_gate | RENAME → 回流闸门引用 |
| SFC-12 | 证据 L1 vs L2 | RENAME → 证据引用 |
| SFC-13 | AI味失败 | SPLIT → L1问题域+模块内问题 |
| SFC-14 | 章末弱/章末追读弱 | SPLIT + 路由规则编号 |
| SFC-15 | decision_role Schema 分裂 | KEEP（S1B 已对齐 v1） |

## 4. 四套状态机

- **L1顶层状态**：SCREENING_PASS / REVIEW / REJECT / AUDIT_BLOCKED
- **路由状态**：ROUTED / RETURN_TO_L1 / INPUT_REQUIRED / MANUAL_REVIEW / BLOCKED_TECHNICAL
- **修复单状态**：READY_FOR_L3 / INPUT_REQUIRED / RETURN_TO_L1_5 / MANUAL_REVIEW / AUDIT_BLOCKED
- **执行状态**：PLANNED / EXECUTING / CANDIDATE_WRITTEN / BLOCKED / FAILED / COMPLETED

执行模式（TASK_PLANNING_ONLY / CANDIDATE_GENERATION）与执行状态分离。

## 5. 证据引用规范

统一 `证据引用`（证据编号、来源类型、来源路径、段落编号、行号范围、逐字摘句、证据用途）。  
来源类型：CHAPTER / PRIOR_CHAPTER / IR / PROJECT_RULE / FAILURE_EVIDENCE / RUNTIME_STATE。

## 6. rule_source 拆分

| 新字段 | 允许来源 |
|--------|----------|
| 路由规则来源 | 仅 `30_L1.5_路由矩阵层/L1.5_路由规则.json` |
| 能力规则来源 | `40_L2_正式能力层/**/ability_rules.json` |
| 执行协议来源 | L3 protocol 规则 |
| 证据规则来源 | 证据协议文件 |

L2 旧 `routes.json` 不得出现在路由规则来源。

## 7. 测试结果

```text
python 脚本/校验_L0至L3跨层接口契约.py → VALIDATION_OK
tests/test_L0至L3跨层接口契约.py → 19 passed
全量 pytest → 320 passed, 3 skipped
```

## 8. 运行时状态

- **v1 Schema 仍为生产运行契约**；S2A 未修改 v1 文件内容（仅新增 `跨层契约/` 子目录）。
- **v2 为冻结候选**；生产代码未接入；**运行时尚未迁移**。

## 9. S2B 状态

```text
S2A_CROSS_LAYER_CONTRACT = PASSED
S2A_SCHEMA_V2 = FROZEN_CANDIDATE
S2B_RUNTIME_MIGRATION = PENDING
S2_OVERALL = PARTIAL
S3_ENTRY = BLOCKED
```

S2B 尚未开始：需迁移器、生产代码消费 v2、显式迁移边界。
