# README — XC-UE 当前结构与真源边界 v0.2

> **Cursor 请先读：** `00_工程总控/当前工程唯一真源.md`，再读本文件。  
> 当前阶段：**R0–R3 基础整改 / Phase 2A 候选集成**  
> 动态状态见：`00_工程总控/当前系统状态_自动生成.md`

---

## 0. 唯一工程真源

```text
当前唯一真源：
C:\Users\慕白\OneDrive\桌面\XC-UE

运行实现真源：
00_工程总控/工程执行层/

架构候选定义：
10_L0_总图层/ 至 50_L3_执行协议层/

动态状态：
00_工程总控/当前系统状态_自动生成.md

云盘小说目录中的 XC-UE：
非当前副本，不参与默认读取和运行。
```

详见：`00_工程总控/当前工程唯一真源.md`、`00_工程总控/云盘副本登记表.md`

---

## 1. 当前阶段声明

```text
已完成：L0–L3 系统层 + Project Harness + L1 Phase 2A 候选评估链
当前做：R0–R3 整改（默认项目闭环 / workspace-only / 评估可信度）
状态：INTEGRATED_CANDIDATE_WITH_BLOCKERS（非生产）
禁止做：第三次全量真实 API / 修改 golden v1 标签追校准 / 进入 R4 扩功能
```

---

## 2. 运行形态（Workspace-Only）

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

## 3. Cursor 读取顺序

```text
1. 00_工程总控/当前工程唯一真源.md
2. XC-UE_项目说明与资源边界.md     ← 本文件
3. 项目索引.md
4. 00_工程总控/当前系统状态_自动生成.md   ← 机器生成动态状态
5. L0—L3 候选定义（10_L0 至 50_L3）
6. 工程执行层（00_工程总控/工程执行层/）
7. 审计纠偏_2026-06-26/AUDIT_BASELINE.json          ← R0 整改前基线（只读）
8. 按任务再读 L1 / L2 / L3 / TP-001
```

---

## 4. 目标根目录

```text
XC-UE/
├── XC-UE_项目说明与资源边界.md
├── 项目索引.md
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

## 5. 三层边界

| 类型 | 路径 | 性质 |
|---|---|---|
| 系统层 | `10_L0` ~ `50_L3` | XC-UE 架构真源（Markdown） |
| 项目运行时 | `70_测试项目/TP-001_*` | Harness + `project.json` |
| 评估语料 | `tests/fixtures/l1_semantic_golden/` | golden v1（冻结）；v2 规划中 |

TP-001 正式输入只认 `IR/`。  
`chapters/_candidates/` **不是**正式输入。

---

## 6. 真源规则

```text
运行真源：00_工程总控/工程执行层/（非 pip 包）
动态状态：当前系统状态_自动生成.md（非手写 当前系统状态_旧版.md）
golden v1 冻结：FREEZE_RECORD.json + AUDIT_BASELINE.json
```

---

## 7. 相关文档

| 文件 | 用途 |
|---|---|
| `00_工程总控/当前工程唯一真源.md` | S0 唯一工程真源裁决 |
| `00_工程总控/云盘副本登记表.md` | 云盘副本身份登记 |
| `项目索引.md` | 根目录导航 |
| `00_工程总控/当前系统状态_自动生成.md` | 各层动态状态 |
| `文档/项目治理层/历史/当前系统状态_旧版.md` | **已废弃**，见 generated |
| `00_工程总控/外部材料接入规则.md` | 外部资料规则 |
