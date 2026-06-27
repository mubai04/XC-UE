# L2工程

本目录把 `40_L2_正式能力层/` 的 Markdown 能力标准转换为 **独立领域模块** 的可运行诊断与修复单工程。

## 结构状态（R4B）

| 状态 | 说明 |
|---|---|
| 路由已接入 | L1.5 → 能力注册表 → 独立入口 |
| 结构独立 | L2-02～L2-06 各为独立包，含模型/上下文/诊断/校验/修复规划/入口 |
| mock 集成通过 | 各模块 mock 集成测试与流水线回归通过 |
| 确定性领域逻辑通过 | 各模块不依赖 mock 的上下文/校验/规划测试通过 |
| 真实模型效果 | **尚未独立评估** |

```text
L2_02_INDEPENDENT_CAPABILITY = PASSED
L2_03_INDEPENDENT_CAPABILITY = PASSED
L2_04_INDEPENDENT_CAPABILITY = PASSED
L2_05_INDEPENDENT_CAPABILITY = PASSED
L2_06_INDEPENDENT_CAPABILITY = PASSED
L2_SHARED_EXECUTOR_CONFIG_ONLY = ELIMINATED
```

禁止写「L2-02～L2-06 语义能力已完全验证」；允许写「已形成独立领域模块，结构与 mock 集成测试通过；真实模型语义效果仍待独立评估。」

## 目录

```text
L2工程/
├─ 公共执行层/          # 仅基础设施（模型调用、JSON 解析、通用 quote、修复单适配）
├─ L2_02_文风语言/      # 文风独立能力
├─ L2_03_角色心理/
├─ L2_04_创意设定/
├─ L2_05_市场体验/
├─ L2_06_系统一致性/
├─ 能力注册表.py        # 仅入口映射，不含 prompt/字段定义
└─ L2_02_文风语言能力.py … L2_06_*.py  # 兼容转发
```

`L2语义能力执行器.py` 已淘汰 `MODULE_SPECS` 统一领域执行路径。

## 正式输入

- **L1.5 路由报告**（`--l15-report`）
- L2 只执行 `target_module`；`--failure-packet` 为 deprecated 兼容

## 运行

```powershell
python "00_工程总控\工程执行层\统一运行入口.py" --target REPAIR_PIPELINE `
  --failure-packet "tests\fixtures\r4a_l15_smoke_failure_packet.json" `
  --project TP-001 --run-id R4A-PIPELINE-SMOKE
```

## 边界

- 不写正式正文（L3 写 `_candidates/`）
- 不替 L1.5 派单
- L2-01 路由命中仍阻断
