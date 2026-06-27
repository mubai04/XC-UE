# XC-UE 工程索引 v0.2

> **Cursor 请先读：** `README_XC-UE_当前结构与真源边界.md`  
> 动态状态：`00_工程总控/CURRENT_SYSTEM_STATUS.generated.md`

---

## 1. 该读什么

| 优先级 | 路径 | 用途 |
|---|---|---|
| 1 | `README_XC-UE_当前结构与真源边界.md` | 阶段、运行形态、边界 |
| 2 | `00_工程总控/CURRENT_SYSTEM_STATUS.generated.md` | L0–L3 / Harness 动态状态 |
| 3 | `审计纠偏_2026-06-26/AUDIT_BASELINE.json` | R0 整改前基线 |
| 4 | `10_L0_总图层/L0_XC-UE_终极工程总图.md` | 系统总图 |
| 5 | `20_L1_闸门层/` ~ `50_L3_执行协议层/` | 各层 Markdown 真源 |
| 6 | `70_测试项目/TP-001_*/project.json` | 默认项目清单 |
| 7 | `tests/fixtures/l1_semantic_golden/` | golden v1（冻结） |

---

## 2. 不该读什么（默认禁止索引）

| 路径 | 原因 |
|---|---|
| `**/chapters/_candidates/` | 候选正文 |
| `*.zip` / `*.docx` | 压缩包与外部原文 |
| 历史 API 归档（除非做评估审计） | 只读证据 |

以上部分已在 `.cursorignore` 中排除。

---

## 3. 根目录结构

```text
XC-UE/
├── README_XC-UE_当前结构与真源边界.md
├── INDEX.md
├── pyproject.toml
├── 00_工程总控/
├── 10_L0_总图层/
├── 20_L1_闸门层/
├── 30_L1.5_路由矩阵层/
├── 40_L2_正式能力层/
├── 50_L3_执行协议层/
├── 70_测试项目/
├── tests/
└── 审计纠偏_2026-06-26/
```

---

## 4. 当前阶段

```text
R0  证据冻结（AUDIT_BASELINE.json）
R1  默认项目 TP-001 可加载
R2  workspace-only 运行形态
R3  评估可信度 / golden v2 脚手架
```

---

## 5. 相关文档

- `00_工程总控/CURRENT_SYSTEM_STATUS.generated.md`
- `00_工程总控/SOURCE_POLICY_外部资料接入规则.md`
