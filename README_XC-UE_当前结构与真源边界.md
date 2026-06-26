# README — XC-UE 当前结构与真源边界 v0.1

> **Cursor 请先读本文件。**
>
> 当前阶段：**不是重建系统**，而是 **目录治理 + 真实项目压测准备**。  
> 状态：目录治理 v0.1 / 2026-06-16

---

## 0. 当前阶段声明

```text
已完成：L0 / L1 / L1.5 / L2 / L3 系统层 + Project Harness 壳
当前做：目录治理（DG-01 ~ DG-09）
下一步：填 70_测试项目/TP-001_CleanHarness_IR_Runtime/IR/
禁止做：重建 L0-L3 / 建 L4 / 画 SRN-U / 写 ch01 / 跑 L1
```

---

## 1. Cursor 读取顺序

```text
1. README_XC-UE_当前结构与真源边界.md     ← 本文件
2. INDEX.md                               ← 该读什么、不该读什么
3. 00_工程总控/CURRENT_SYSTEM_STATUS.md   ← 防误判「L2/L3 未建」
4. 00_工程总控/DIRECTORY_GOVERNANCE_TASKS.md
5. 10_L0_总图层/L0_XC-UE_终极工程总图.md
6. 按任务再读 L1 / L1.5 / L2 / L3 / TP-001
```

**禁止**在未读边界声明前，读取归档区或旧输入并写入系统层。

---

## 2. 目标根目录

```text
XC-UE/
├── README_XC-UE_当前结构与真源边界.md
├── INDEX.md
├── .cursorignore
├── 00_工程总控/
├── 10_L0_总图层/
├── 20_L1_闸门层/
├── 30_L1.5_路由矩阵层/
├── 40_L2_正式能力层/
│   └── _images/
├── 50_L3_执行协议层/
├── 70_测试项目/
│   └── TP-001_CleanHarness_IR_Runtime/
├── 90_日志/
└── 99_归档_不要索引/
    └── 旧工程/
```

---

## 3. 三层边界

| 类型 | 路径 | 性质 |
|---|---|---|
| 系统层 | `10_L0` ~ `50_L3` | XC-UE 架构真源（Markdown） |
| 项目运行时 | `70_测试项目/TP-001_*` | 压测壳，非系统真源 |
| 归档区 | `99_归档_不要索引/` | 禁止索引、禁止反向写入 |

TP-001 正式输入只认 `IR/`。  
`_legacy_root_inputs/`、`chapters/_candidates/` **不是**正式输入。

---

## 4. 真源规则

```text
Markdown > 图片
活跃工程 > 99_归档_不要索引/
系统层 > 测试项目层
```

图片在各层 `_images/` 子目录，是表达层，不是规则真源。

---

## 5. 当前禁止

```text
不填真实小说 IR（DG 完成后、人工确认后才开始）
不写 ch01 / 不跑 L1
不建 L4 / 不画新图 / 不扩 L2 内容
不做 SRN-U / Xuke·Chuangjie
不从归档区反向覆盖活跃工程
```

---

## 6. 动作序列

```text
DG-01 ~ DG-09  目录治理     ← 见 DIRECTORY_GOVERNANCE_TASKS.md
P4             填 TP-001 IR  ← DG 完成后
P5             写 ch01
P6             跑 L1-01/02/03
```

---

## 7. 相关文档

| 文件 | 用途 |
|---|---|
| `INDEX.md` | 根目录导航 |
| `00_工程总控/CURRENT_SYSTEM_STATUS.md` | 各层状态 |
| `00_工程总控/DIRECTORY_GOVERNANCE_TASKS.md` | DG 任务单 |
| `00_工程总控/SOURCE_POLICY_外部资料接入规则.md` | 外部资料规则 |
