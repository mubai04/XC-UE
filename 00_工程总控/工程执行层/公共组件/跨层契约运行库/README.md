# 跨层契约运行库

S2B-1 离线 v1→v2 显式迁移库，**不接入** L1/L1.5/L2/L3 生产入口。

## 模块

| 文件 | 职责 |
|------|------|
| Schema注册表.py | 内存 Schema 注册与校验 |
| 契约校验.py | 各层 v2 对象校验入口 |
| 对象编号.py | 确定性对象编号 |
| 迁移模型.py | 迁移上下文与结果 |
| 迁移错误.py | 错误码 |
| v1到v2迁移.py | 各层迁移规则 |
| 引用完整性校验.py | 编号引用链闭合检查 |

## 使用

```python
from 迁移模型 import 迁移上下文
from v1到v2迁移 import 迁移完整链路

ctx = 迁移上下文(
    pipeline_run_id="PIPE-DEMO",
    chapter_path="chapters/demo.md",
)
results = 迁移完整链路(
    l1_packet=...,
    l15_report=...,
    l2_report=...,
    l3_task=...,
    l3_result=...,
    ctx=ctx,
)
```

离线回放：`脚本/回放_v1到v2跨层迁移.py`
