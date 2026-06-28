# P0｜v2 Schema 合法性与环境复现修复结果

日期：2026-06-28  
分支：`l1-phase2`（未提交）  
前置：独立盘查发现 S2A 假通过与 Schema 非法 `$ref`

## 状态修正（任务开始）

```text
S2A_SCHEMA_V2 = DEFECT_FOUND
S2B1_INDEPENDENT_VERIFICATION = FAILED
S2B2_RUNTIME_CUTOVER = BLOCKED
PRODUCTION_RUNTIME = v1
```

## 独立盘查发现

1. 8 个 v2 Schema 在 **jsonschema 4.26.0** 下，`$ref` 含中文文件名与中文 JSON Pointer，Registry 离线解析不可靠。
2. `公共引用结构_v1.json` 的 `$defs` 键名含中文（如 `证据引用`），内部 `$ref` 为 `#/$defs/证据引用` 等形式。
3. `脚本/校验_L0至L3跨层接口契约.py` **未**对每个 Schema 调用 `Draft202012Validator.check_schema()`，仅实例化 Validator，产生假通过。
4. `pyproject.toml` 依赖无版本范围，环境不可复现。

## 原始错误规模（修复前）

| 类别 | 数量（约） |
|------|-----------|
| 中文 `$defs` 键 | 12 |
| 中文 JSON Pointer `$ref` | 40+ |
| 文件名相对 `$ref`（`公共引用结构_v1.json#...`） | 90+ |
| 跨 Schema 文件名 `$ref`（如 `L1发现项结构_v2.json`） | 2 |
| S2A 校验器未执行 `check_schema()` | 8 次遗漏 |

## `$id` 调整

8 个 Schema 均保持绝对 ASCII URI（未改语义）：

| 文件 | `$id` |
|------|-------|
| 公共引用结构_v1.json | `xcue://schemas/cross-layer/common-reference/v1` |
| L1发现项结构_v2.json | `xcue://schemas/cross-layer/l1-finding/v2` |
| L1失败包结构_v2.json | `xcue://schemas/cross-layer/l1-failure-packet/v2` |
| L1_5路由决策结构_v2.json | `xcue://schemas/cross-layer/l15-route-decision/v2` |
| L2修复单结构_v2.json | `xcue://schemas/cross-layer/l2-fix-form/v2` |
| L2报告结构_v2.json | `xcue://schemas/cross-layer/l2-report/v2` |
| L3执行任务包结构_v2.json | `xcue://schemas/cross-layer/l3-task-bundle/v2` |
| L3执行结果结构_v2.json | `xcue://schemas/cross-layer/l3-execution-result/v2` |

## `$ref` 与 anchor 修复

1. `$defs` 键改为 ASCII snake_case（如 `evidence_reference`）。
2. 每个 def 增加 `$anchor`（kebab-case，如 `evidence-reference`）。
3. 内部引用：`#object-id`、`#evidence-reference` 等。
4. 跨 Schema 引用：`xcue://schemas/cross-layer/common-reference/v1#object-id`。
5. 跨层完整 Schema：`xcue://schemas/cross-layer/l1-finding/v2` 等。
6. **禁止**文件名相对引用与中文 Pointer。

实例对象中的中文业务字段名（如 `证据引用`、`L1发现编号`）**未改**。

## 校验器假通过根因与修复

**根因**：`_build_registry()` 后仅 `Draft202012Validator(schema, registry=registry)`，无 `check_schema()`；异常被宽泛捕获后继续输出 `VALIDATION_OK`。

**修复**（`脚本/校验_L0至L3跨层接口契约.py`）：

- 注册前对每个 Schema 执行 `Draft202012Validator.check_schema()`。
- Registry 仅按 `$id` 注册，不注册文件名别名。
- 静态检查 `$ref` / `$anchor` ASCII 合法性。
- 5 组正向 + 3 组负向样例校验。
- 失败时输出具体 Schema 与路径，**不**输出 `VALIDATION_OK`。

## Registry 修复

`Schema注册表.py`：

- `Resource.from_contents()` + `$id` 键。
- 注册前 `check_schema()`。
- 无网络 retrieve，无文件名权威键。
- 重复 `$id` / 非法 Schema 明确失败。

## 迁移模型调整

L1.5 四个 v1 专有键（`primary_failure` 等）改为 **`已消费但不保留的旧字段`**，不再计入 `未迁移字段`。合法链：**未迁移字段 = 0**。

## 依赖版本

| 包 | pyproject 范围 | 干净环境实测 |
|----|----------------|-------------|
| jsonschema | >=4.23.0,<5 | 4.26.0 |
| referencing | >=0.35.0,<1 | 0.37.0 |
| PyYAML | >=6.0.2,<7 | 6.0.3 |
| pytest | >=8.0,<9 | 8.4.2 |

锁定文件：`依赖锁定_开发运行.txt`  
说明文档：`文档/项目治理层/开发环境复现说明.md`

## 干净环境复验

临时环境：`.venv-schema-verify`（Python 3.13.13，已删除）

| 步骤 | 结果 |
|------|------|
| `校验_L0至L3跨层接口契约.py` | SCHEMA_CHECK / REFERENCE / POSITIVE / NEGATIVE = PASSED；VALIDATION_OK |
| `回放_v1到v2跨层迁移.py --validate-only` | VALIDATION_OK；MIGRATION_CHAIN_READY |
| 定向 pytest（54） | 54 passed |
| 全量 pytest | 355 passed, 3 skipped |

## S2B-1 复验

- 离线迁移链引用闭合：OK
- 未迁移字段：0
- 已消费但不保留的旧字段：4（L1.5，预期）

## 未修改项

- L1/L1.5/L2/L3 领域算法与生产入口：**否**
- v1 Schema / 评测语料 / R0 基线：**否**
- 真实 API：**否**
- 生产运行时：**仍为 v1**
- S2B-2：**继续暂缓**

## 最终状态

```text
S2A_SCHEMA_V2 = REPAIRED_AND_VERIFIED
S2A_VALIDATOR_FALSE_PASS = ELIMINATED
DEPENDENCY_ENVIRONMENT = REPRODUCIBLE
S2B1_CLEAN_ENV_VERIFICATION = PASSED
S2B1_OFFLINE_REPLAY = PASSED
PRODUCTION_RUNTIME = v1
S2B2_RUNTIME_CUTOVER = DEFERRED
```
