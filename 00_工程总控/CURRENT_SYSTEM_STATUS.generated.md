# CURRENT_SYSTEM_STATUS (generated)

> generated_at: 2026-06-27T23:26:42.313450+00:00
> baseline_digest: f0c242529a4dd19c07b0ced5b9bcae2b53304c728aba088b4e54ee36f1c9c9c1
> baseline_ref: 审计纠偏_2026-06-26/AUDIT_BASELINE.json

## 工程状态

```text
XC-UE_CURRENT_STATUS = INTEGRATED_CANDIDATE_WITH_BLOCKERS
PROJECT_RUNTIME = OK
PRODUCTION = NOT_ELIGIBLE
GOLDEN_V1 = FROZEN
L1_5_EXECUTABLE = PASSED
L2_02_TO_06_PROFILE_CONFIGURED = SUPERSEDED
L2_02_INDEPENDENT_CAPABILITY = PASSED
L2_03_INDEPENDENT_CAPABILITY = PASSED
L2_04_INDEPENDENT_CAPABILITY = PASSED
L2_05_INDEPENDENT_CAPABILITY = PASSED
L2_06_INDEPENDENT_CAPABILITY = PASSED
L2_SHARED_EXECUTOR_CONFIG_ONLY = ELIMINATED
FAILURE_PACKET_TO_CANDIDATE_PIPELINE = PASSED
```

## R4A 修复主链（工程执行层）

- L1.5 入口: `00_工程总控/工程执行层/L1.5工程/L1.5运行入口.py`
- L2 正式输入: L1.5 路由报告 (`--l15-report`)
- 修复流水线: `00_工程总控/工程执行层/修复流水线运行入口.py`
- 统一入口 target: `L1.5`, `REPAIR_PIPELINE`（另含 L1/L2/L3/PROJECT）
- L3 候选输出: `chapters/_candidates/`（不覆盖正式章节）

## Git

- commit: `c5f25576e50bcf37f539345804649baa6ecae686`
- dirty: `True`

## Pytest（来自 RUNTIME_SNAPSHOT，默认不主动跑）

- summary: unknown
- r4b_verified: `136 passed`（2026-06-27，`python -m pytest -q`，五模块独立能力 + 流水线回归）

## Golden v1

- frozen: `True`
- baseline_ref: `审计纠偏_2026-06-26/AUDIT_BASELINE.json`

## 运行入口

- unified: `00_工程总控/工程执行层/统一运行入口.py`
- install: `pip install -e ".[dev,runtime]"` → workspace stub only

