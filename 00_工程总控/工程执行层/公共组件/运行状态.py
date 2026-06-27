from __future__ import annotations


运行中 = "RUNNING"
已完成 = "COMPLETED"
机器初筛通过 = "SCREENING_PASS"
机器初筛退回 = "SCREENING_REJECT"
需要人工复核 = "REVIEW_REQUIRED"
审计阻断 = "AUDIT_BLOCKED"
已阻断 = "BLOCKED"
输入无效 = "INPUT_INVALID"
结构无效 = "SCHEMA_INVALID"
任务规划模式 = "TASK_PLANNING_ONLY"
等待执行器 = "AWAITING_EXECUTOR"
部分阻断 = "PARTIAL_BLOCKED"
模型阻断 = "MODEL_BLOCKED"
候选失败 = "CANDIDATE_FAILED"

L3可执行L2状态 = frozenset({已完成})
L3禁止L2状态 = frozenset({已阻断, 结构无效, 部分阻断, 模型阻断})


状态说明 = {
    运行中: "运行中",
    已完成: "已完成",
    机器初筛通过: "发布前启发式检查未发现指定硬风险，仍需人工复核",
    机器初筛退回: "命中已配置的启发式硬风险",
    需要人工复核: "需要人工复核",
    审计阻断: "语义审计或输入上下文阻断，未对正文作通过/拒绝裁决",
    已阻断: "阻断",
    输入无效: "输入无效",
    结构无效: "结构无效",
    任务规划模式: "任务规划模式",
    等待执行器: "等待执行器",
    部分阻断: "部分修复单生成成功，但存在模型/API 阻断项",
    模型阻断: "模型/API 阻断，未生成任何修复单",
    候选失败: "候选正文生成失败",
}
