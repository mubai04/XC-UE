# 70_测试项目

本目录存放 **Project Harness** 项目运行时，不是 XC-UE 系统层。

## 当前项目

```text
TP-001_CleanHarness_IR_Runtime/     # 引擎测试壳（空 IR）
TP-002_修士死后都会变成秘境/        # 真实小说生产项目
```

入口：

- 测试壳：`TP-001_CleanHarness_IR_Runtime/00_项目说明.md`
- 生产项目：`TP-002_修士死后都会变成秘境/00_项目说明.md`

## 规则

- 测试项目不得反向覆盖 L0 / L1 / L1.5 / L2 / L3 真源
- 正式项目输入只认各项目内的 `IR/`
- 详见根目录 `INDEX.md` 与 `50_L3_执行协议层/L3-07_ProjectHarness运行协议_v0.1.2.md`
