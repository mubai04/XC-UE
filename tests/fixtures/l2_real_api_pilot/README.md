# L2 真实 API 小样本试跑集（R5A）

本目录为 **R5A｜L2真实模型小样本试跑** 专用夹具，不进入模型提示，不包含标准答案正文。

## 结构

- `manifest.json` — 12 例索引（L2P-001～L2P-012）
- `cases/L2P-xxx/` — 每例独立 mini-harness（`project.json`、`chapters/`、可选 `IR/`）
- `expected/L2P-xxx.expected.json` — 人工预期（仅运行后对比）
- `results/` — 试跑输出（按 `run_id` 子目录）

## 校验（不调 API）

```powershell
python 脚本/评估_L2_真实API试跑.py --validate-only
```

## 真实试跑

需配置 `DEEPSEEK_API_KEY`。不得覆盖已有 run：

```powershell
python 脚本/评估_L2_真实API试跑.py --run-id L2_R5A_REAL_API_PILOT_20260628 --force-new-run
```

## 约束

- 不修改 golden v1、R0 基线、正式章节
- 不进入 L3、不生成候选正文
- 每例每类错误最多重试一次
