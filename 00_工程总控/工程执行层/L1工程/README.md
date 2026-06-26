# L1工程

本目录把 `20_L1_闸门层/` 的 Markdown 闸门标准转换为可运行的正文检测工程。

L1工程检测的是章节正文是否能过 L1 闸门，不检测文件壳是否存在，也不直接写正文。

## 文件对应关系

| 标准文件 | 工程文件 | 职责 |
|---|---|---|
| L1-00_闸门接口表.md | L1_00_闸门接口校验.py | 校验 L1 输出字段、L1.5 交接条件、接口流转 |
| L1-01_五大创作问题_技术护栏闭环图.md | L1_01_内部创作检测.py | 检测内部创作代理信号 |
| L1-02_读者投入意愿工程图.md | L1_02_读者投入检测.py | 检测 E / V / C、入口、章末、弃读代理风险 |
| L1-03_发布锁验收工程图.md | L1_03_发布锁检测.py | 检测字数体量、当章收益、章末代理信号和发布前启发式风险 |
| L1.5_Routing_Matrix.md | L15交接.py | 生成失败后的路由建议，不直接修正文 |

## 运行

```powershell
python "00_工程总控\工程执行层\统一运行入口.py" --target L1 --run-id L1_RUN-手动编号
```

指定候选正文：

```powershell
python "00_工程总控\工程执行层\统一运行入口.py" --target L1 --chapter "70_测试项目\TP-001_CleanHarness_IR_Runtime\chapters\_candidates\ch01_candidate_RUN-20260621-002.md"
```

## 输出

报告输出到：

```text
00_工程总控/工程执行层/L1工程/reports/
```

输出内容包括：

- L1-00 / L1-01 / L1-02 / L1-03 闸门结论
- 正文段落证据
- failure packet
- L1.5 路由建议

批次 05 起，L1 自动输出固定为未验证启发式结果：

- `heuristic=true`
- `publish_authority=false`
- `human_review_required=true`
- `validation_status=UNVALIDATED`

## 边界

- 自动检测只做工程化初筛，不冒充最终文学判断。
- “检测到代理信号”只表示当前规则未发现指定硬风险，不等于内部创作成立、读者愿意追读或发布质量通过。
- 图片不是规则真源；Markdown 是当前标准来源。
- 本工程不会自动覆盖正式正文。
