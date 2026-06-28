# S1B L1 职责与失败包契约整改结果

日期：2026-06-28  
任务：D-SYS-04｜S1B L1职责、终裁权与失败包契约统一

## 1. L1 正式权力模型

```text
L1-00：总入口、输入完整性、执行编排、状态聚合、失败包输出
L1 前置护栏：无法安全进入语义判断的输入与确定性质量问题
L1-SEM：当前阶段唯一全章内容终裁（CONTENT_DECISION）
L1-01：内部创作成立诊断器（DIAGNOSTIC）
L1-02：内容侧读者投入诊断器（DIAGNOSTIC）
L1-03：发布准备风险诊断器（DIAGNOSTIC，无真实发布权）
L1.5：不重新判断内容，只从 L1 可路由发现中选主处理路径
```

## 2. 四种 decision_role 权限

| decision_role    | 可否影响 L1 终态 | 可否进入路由候选 | 含义 |
| ---------------- | ---------------: | ---------------: | ---- |
| HARD_GUARD       | 是 | 视类型而定 | 确定性输入、工程或最低质量阻断 |
| CONTENT_DECISION | 是 | 是 | L1-SEM 全章内容结论 |
| DIAGNOSTIC       | 否 | 是（routeable=true） | L1-01/02/03 修复线索 |
| AUDIT_BLOCKER    | 是（AUDIT_BLOCKED） | 否 | API/证据/协议无效 |

## 3. L1-SEM 地位

- 当前全章内容终裁组件；输出 `CONTENT_DECISION`。
- 须有证据协议；API/证据失败 → `AUDIT_BLOCKED`。
- 不决定发布（`publish_authority=false`）；不直接写正文；不自行选最终 L2 模块。

## 4. L1-01/02/03 地位

- 工程角色均为 `DIAGNOSTIC`；不单独覆盖顶层 `SCREENING_*` 状态。
- `routeable=true` 且顶层为 `SCREENING_REVIEW`/`SCREENING_REJECT` 时可进入失败包 items。
- L1-03 名义改为「发布准备风险诊断」；文档中的发布/退回/降级为内容风险建议。

## 5. 顶层状态枚举

`SCREENING_PASS` / `SCREENING_REVIEW` / `SCREENING_REJECT` / `AUDIT_BLOCKED`

## 6. routeable 与 blocking

```text
blocking != routeable
```

- 阻断但不可路由：如部分工程技术护栏、`字数不足`（routeable=false）
- 不阻断但可路由：DIAGNOSTIC 代理信号
- 阻断且可路由：CONTENT_DECISION、部分 HARD_GUARD（重复类）
- L1.5 主路由候选：`routeable=true`；`INPUT_REQUIRED`/`BLOCKED_TECHNICAL` 另从全包 items 匹配路由规则

## 7. 失败包 Schema 变化

- item 必填：`decision_role`、`blocking`、`routeable`、`route_reason`、`source_component`
- 顶层必填：`status`、`blocking_count`、`routeable_count`、`items`
- 旧包缺 `routeable`：`L2读取` 明确拒绝，不静默猜测

## 8. L1.5 候选选择规则

1. `AUDIT_BLOCKED` / `SCREENING_PASS`：禁止内容路由
2. 全 items 先匹配 `INPUT_REQUIRED`、`BLOCKED_TECHNICAL`
3. 内容修复主路径：仅 `routeable=true` items，按严重级别、闸门顺序、路由规则排序
4. 同级不同 L2 模块 → `MANUAL_REVIEW`

## 9. 四个 L1-00 未覆盖类型

| 失败类型 | 路由 |
| -------- | ---- |
| 重复窗口过高 | ROUTE_TO_L2 → L2-02 |
| 高重复正文 | ROUTE_TO_L2 → L2-02 |
| 低信息重复正文 | ROUTE_TO_L2 → L2-02 |
| 字数不足 | INPUT_REQUIRED（target_module=null） |

## 10. L1-02 reserved 能力

`RESERVED_NOT_IMPLEMENTED`：传播点弱、付费预期弱及真实传播/付费/投流/ARPPU 等；路由 JSON 已标记；`L1_02_读者投入检测` 不生成对应失败类型。

## 11. L1-03 reserved 能力

`RESERVED_NOT_IMPLEMENTED`：功能锁完整实现、修改轮次自动限制、自动发布/退回/降级、平台规则判定。

## 12. 终态优先级实现说明

文档优先级为 AUDIT_BLOCKER > HARD_GUARD。当**护栏失败与 API 不可用并存**时，顶层状态取 `SCREENING_REJECT`（护栏可行动），`semantic_audit_status` 与 `audit_blockers` 仍记录 `AUDIT_BLOCKED` 信号。

## 13. 测试结果

```text
python 脚本/校验_L1_职责与失败包契约.py → VALIDATION_OK
定向 pytest：56 passed
全量 pytest：301 passed, 3 skipped
```

## 14. 未处理（留 S2）

- L1-01/02/03 检测算法与六维语义标尺调优
- 传播/付费 reserved 能力的正式检测器实现
- L1-03 功能锁与修改轮次自动化
- 真实 API 评测与 R5D 业务评分

## 15. S1 状态判定

```text
S1B_L1_AUTHORITY_MODEL = PASSED
S1B_L1_PACKET_CONTRACT = PASSED
S1B_L1_STATUS_ENUM = PASSED
S1_OVERALL = PASSED
S2_ENTRY = ALLOWED
```
