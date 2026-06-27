# L1 Semantic Golden v2 — Labeling Protocol (draft)

## 规模

- **最少 10 章**，**推荐 12 章**
- 第 11 章：独立 `clear_fail` 负例（不复用 GS-005）
- 第 12 章：`BORDERLINE` 双盲复核 / 对抗扩展槽位

## 与 v1 隔离

- v1 已 R0 冻结，**不得** retroactive 编辑
- v2 使用新 `chapter_id` 前缀（建议 `GV2-001` …）
- 标签由 ≥2 位独立标注员双盲完成；争议标 `BORDERLINE`

## 场景覆盖

每类 scenario tag 至少 2 样本：

- `clear_pass`
- `clear_fail`（纯叙事不成立，非成稿质量问题）
- `debatable_review`
- `low_lexical_good_narrative`
- `high_lexical_bad_narrative`

## 禁止

- 从 v1 复制粘贴改标签
- 用同一审计流水线输出直接写人工标签
