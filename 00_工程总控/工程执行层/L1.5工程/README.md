# L1.5 工程（路由执行层）

本目录实现 **L1 failure packet → 唯一主路由报告** 的可运行工程层，对应 Markdown 真源 `30_L1.5_路由矩阵层/`。

L1.5 **不写正文、不调用模型、不判断章节质量**；只校验失败包、读取 `gate_rules.json` 的 `l15_routes`、确定唯一主失败项并输出目标 L2 模块。

## 入口

```powershell
python "00_工程总控\工程执行层\统一运行入口.py" --target L1.5 `
  --failure-packet "tests\fixtures\r4a_l15_smoke_failure_packet.json" `
  --run-id R4A-L15-SMOKE `
  --pipeline-run-id R4A-L15-SMOKE `
  --stage-run-id R4A-L15-SMOKE-L1
```

或直接调用：

```powershell
python "00_工程总控\工程执行层\L1.5工程\L1.5运行入口.py" --help
```

## 参数

| 参数 | 说明 |
|---|---|
| `--failure-packet` | L1 failure packet JSON（必填） |
| `--run-id` | 本阶段运行编号 |
| `--out-dir` | 报告输出目录（默认 `L1.5工程/reports/`） |
| `--pipeline-run-id` | 流水线血缘 ID（须与 packet 一致） |
| `--stage-run-id` | 阶段血缘 ID |
| `--standard-mode` | 标准模式（默认 production） |

## 输出

- `L1.5路由报告结构.json` 合规的 JSON 报告
- 同名 Markdown 摘要
- `final_status` 仅允许：`ROUTED` / `INPUT_REQUIRED` / `MANUAL_REVIEW` / `RETURN_TO_L1` / `BLOCKED`
- 同 `run-id` 已有报告时拒绝覆盖

## 内部模块

| 文件 | 职责 |
|---|---|
| `L1.5运行入口.py` | CLI 与主流程 |
| `L15路由.py` | 从 `l15_routes` 解析主/次级失败与目标模块 |
| `L15报告.py` | JSON/Markdown 报告写入 |
| `L15模型.py` | 路由报告数据模型 |
| `L1工程/L15交接.py` | 遗留辅助函数（兼容导入） |

## 下游

正式修复流水线中，L2 **只接受** L1.5 路由报告（`--l15-report`），不得绕过 L1.5 自行改派模块。
