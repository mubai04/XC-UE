# MANIFEST 文件权限与真源表 v0.1

> 状态：Project Harness 本地权限真源  
> 适用范围：TP-002《修士死后，都会变成秘境》，不覆盖 XC-UE 系统层。

---

## 1. 真源优先级

```text
IR/
↓
chapters/chxx.md 正式正文事实
↓
tests/ 测试记录
↓
logs/ 执行与断点记录
↓
runtime/ 状态变化记录
```

---

## 2. 文件权限矩阵

| 路径 | 作用 | 默认权限 | 是否真源 |
|---|---|---:|---:|
| `IR/` | 当前项目正式输入 | 读 / 条件写 | 是 |
| `chapters/chxx.md` | 正式正文 | 读 / 默认不写 | 是 |
| `chapters/_candidates/` | 候选正文 | 读 / 写 | 否 |
| `runtime/` | 状态变化记录 | 读 / 追加写 | 否 |
| `tests/` | 测试记录 | 读 / 追加写 | 是 |
| `logs/` | 日志记录 | 读 / 追加写 | 是 |
| `snapshots/` | 快照 | 读 / 写 | 否 |

---

## 3. 默认读取规则

L1 / L1.5 / L2 / L3 默认读取：`IR/`、`chapters/`、`tests/`、`logs/`、`runtime/`、本 MANIFEST。
