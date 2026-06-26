# DIRECTORY_GOVERNANCE — 目录治理 v1

执行时间：2026-06-16

## 目的

将 XC-UE 从「可建系统」收束为「系统层 + 执行层 + 项目运行时」的稳定目录结构，防止根目录漂移、真源混放、Cursor 误索引。

## 已执行项

### 1. L3 顶层目录去版本号

```text
50_L3_执行协议层_v0.1.2/  →  50_L3_执行协议层/
```

版本号保留在文件名内（如 `L3-00_执行协议总表_v0.1.2.md`）。

### 2. Project Harness 移入测试项目区

```text
XC-UE_Project_Harness_TP-001_v0.2.1_CleanHarness_IR_Runtime/
  →  70_测试项目/TP-001_CleanHarness_IR_Runtime/
```

### 3. 旧工程移入归档区

```text
旧工程/  →  99_归档_不要索引/旧工程/
```

受 `SOURCE_POLICY_外部资料接入规则.md` 约束，禁止作为活跃工程真源。

### 4. L2 图片移入 _images/

```text
40_L2_正式能力层/*.png  →  40_L2_正式能力层/_images/
```

与 L0 / L1 / L1.5 的 `_images/` 惯例统一。

### 5. 修正 L2-04 图片文件名

```text
L2-04_创意设定能力_正式正式架构图_v0.2.1_精确重生成版.png
  →  L2-04_创意设定能力_正式版式架构图_v0.2.1_精确重生成版.png
```

### 6. 新增根目录 INDEX

- `README_XC-UE_当前结构与真源边界.md` — Cursor 首读边界声明
- `INDEX.md` — 工程速查索引
- `00_工程总控/CURRENT_SYSTEM_STATUS.md` — 各层当前状态
- `00_工程总控/STRUCTURE_CHECK_v1.md` — P3 目录结构自检
- `.cursorignore` — 排除 `99_归档_不要索引/`

## 治理后根目录

```text
XC-UE/
├── INDEX.md
├── 00_工程总控/
├── 10_L0_总图层/
├── 20_L1_闸门层/
├── 30_L1.5_路由矩阵层/
├── 40_L2_正式能力层/
├── 50_L3_执行协议层/
├── 70_测试项目/
│   └── TP-001_CleanHarness_IR_Runtime/
├── 90_日志/
└── 99_归档_不要索引/
    └── 旧工程/
```

## 未执行项（按判断保留）

- 不新建 L4
- 不重建 SRN-U / Xuke·Chuangjie
- 不扩新 L2 能力文件

## 下一步

1. 人工确认后启动 P4：填充 `70_测试项目/TP-001_CleanHarness_IR_Runtime/IR/`
2. L2 图文一致性审计（并行，不阻塞 P4）
3. P5 写 ch01 → P6 跑 L1 压测
