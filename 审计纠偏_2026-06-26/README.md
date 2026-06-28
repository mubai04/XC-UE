# 审计纠偏_2026-06-26

本目录存放 R0–R4 审计、冻结与验收产物。根目录仅保留系统脚本直接引用的基线文件。

## 根目录（勿随意移动）

| 文件 | 用途 |
|---|---|
| `AUDIT_BASELINE.json` | golden v1 / 冻结基线快照（`脚本/冻结审计基线.py`） |
| `RUNTIME_SNAPSHOT.json` | 运行时快照（`脚本/生成当前系统状态.py`） |

## 子目录

| 目录 | 内容 |
|---|---|
| [`L1_Phase1/`](L1_Phase1/) | Phase 1 冻结报告、pytest 回归记录 |
| [`L1_Phase2/`](L1_Phase2/) | Phase 2 范围说明、Phase 2A eval 摘要、首次真实 API 评估归档 |
| [`问题追踪/`](问题追踪/) | 现行问题总表 v3（CSV 真源 + MD 摘要）、R0–R3 整改结果 |
| [`R4D/`](R4D/) | R4D 外部反例窄查验收报告 |

## 清理说明（2026-06-28）

- 删除已被 rerun 取代的 `L1_Phase1_pytest_regression_2026-06-26.txt`
- 按阶段归入子目录；`AUDIT_BASELINE.json` 内历史路径未改写（冻结快照）
