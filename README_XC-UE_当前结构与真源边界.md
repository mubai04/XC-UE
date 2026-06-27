# README — XC-UE 当前结构与真源边界 v0.2

> **Cursor 请先读本文件。**
>
> 当前阶段：**R0–R3 基础整改 / Phase 2A 候选集成**  
> 动态状态见：`00_工程总控/CURRENT_SYSTEM_STATUS.generated.md`

---

## 0. 当前阶段声明

```text
已完成：L0–L3 系统层 + Project Harness + L1 Phase 2A 候选评估链
当前做：R0–R3 整改（默认项目闭环 / workspace-only / 评估可信度）
状态：INTEGRATED_CANDIDATE_WITH_BLOCKERS（非生产）
禁止做：第三次全量真实 API / 修改 golden v1 标签追校准 / 进入 R4 扩功能
```

---

## 1. 运行形态（Workspace-Only）

`pip install -e ".[dev,runtime]"` 仅安装 **workspace stub**（`xcue` CLI）与开发/运行时 extras。  
**真实 L1/L2/L3 引擎不在 wheel 内**，必须在仓库根目录执行：

```bash
pip install -e ".[dev,runtime]"
python 00_工程总控/工程执行层/统一运行入口.py --help
python 00_工程总控/工程执行层/统一运行入口.py --target L1 --project TP-001 --chapter 70_测试项目/TP-001_CleanHarness_IR_Runtime/chapters/ch01.md
```

- `xcue` 无参数 → **exit 2**（非成功）
- wheel **不是**产品交付物
- 默认项目 `TP-001` 需存在 [`project.json`](70_测试项目/TP-001_CleanHarness_IR_Runtime/project.json)

---

## 2. Cursor 读取顺序

```text
1. README_XC-UE_当前结构与真源边界.md     ← 本文件
2. INDEX.md
3. 00_工程总控/CURRENT_SYSTEM_STATUS.generated.md   ← 机器生成动态状态
4. 审计纠偏_2026-06-26/AUDIT_BASELINE.json          ← R0 整改前基线（只读）
5. 按任务再读 L1 / L2 / L3 / TP-001
```

---

## 3. 目标根目录

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
│   └── TP-001_CleanHarness_IR_Runtime/
│       └── project.json
├── tests/fixtures/l1_semantic_golden/   ← golden v1（R0 冻结）
└── 审计纠偏_2026-06-26/
```

---

## 4. 三层边界

| 类型 | 路径 | 性质 |
|---|---|---|
| 系统层 | `10_L0` ~ `50_L3` | XC-UE 架构真源（Markdown） |
| 项目运行时 | `70_测试项目/TP-001_*` | Harness + `project.json` |
| 评估语料 | `tests/fixtures/l1_semantic_golden/` | golden v1（冻结）；v2 规划中 |

TP-001 正式输入只认 `IR/`。  
`chapters/_candidates/` **不是**正式输入。

---

## 5. 真源规则

```text
运行真源：00_工程总控/工程执行层/（非 pip 包）
动态状态：CURRENT_SYSTEM_STATUS.generated.md（非手写 CURRENT_SYSTEM_STATUS.md）
golden v1 冻结：FREEZE_RECORD.json + AUDIT_BASELINE.json
```

---

## 6. 相关文档

| 文件 | 用途 |
|---|---|
| `INDEX.md` | 根目录导航 |
| `00_工程总控/CURRENT_SYSTEM_STATUS.generated.md` | 各层动态状态 |
| `00_工程总控/CURRENT_SYSTEM_STATUS.md` | **已废弃**，见 generated |
| `00_工程总控/SOURCE_POLICY_外部资料接入规则.md` | 外部资料规则 |
