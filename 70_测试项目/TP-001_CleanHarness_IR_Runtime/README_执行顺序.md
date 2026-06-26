# TP-001 执行顺序 v0.2.1

## 0. 当前真源规则

正式项目输入只认：

```text
IR/
```

根目录旧输入文件已移动到：

```text
_legacy_root_inputs/
```

旧输入只作人工参考，不进入默认执行链路。

## 1. 先读权限表

执行前必须先读：

```text
MANIFEST_文件权限与真源表.md
```

## 2. 再填 IR

1. `IR/IR-00_项目索引.md`
2. `IR/IR-01_立项卡.md`
3. `IR/IR-02_世界约束.md`
4. `IR/IR-03_角色动机表.md`
5. `IR/IR-04_事件链.md`
6. `IR/IR-05_章节目标表.md`
7. `IR/IR-06_读者预期表.md`
8. `IR/IR-07_发布状态表.md`
9. `IR/IR-08_状态快照.md`
10. `IR/IR-99_输入完整性检查.md`

## 3. 再写正文

1. `chapters/ch01.md`
2. `chapters/ch02.md`

候选正文只允许写入：

```text
chapters/_candidates/
```

## 4. 跑测试

1. `tests/L1-01_内部创作测试.md`
2. `tests/L1-02_读者投入测试.md`
3. `tests/L1-03_发布锁测试.md`
4. `tests/L1.5_路由测试.md`
5. `tests/L2_调用记录.md`

## 5. L3 执行

L3 本地执行入口：

```text
tests/L3_执行任务单.md
```

L3 执行必须输出：

- 候选产物
- diff 摘要
- 执行日志
- 回流验收位置
- 复验结果回写

## 6. Runtime 记录

runtime 当前只记录：

- 价值函数变化
- 角色状态迁移
- 事件刺激
- 目标变化
- 选择结果

runtime 当前不自动推演，不升 L4。  
runtime 变化必须通过 `RT-00_运行时索引.md` 回写 IR。

## 当前禁止

- 不重写 XC-UE 系统层
- 不从归档反向覆盖当前工程
- 不画新图
- 不让候选正文覆盖正式正文
- 不把 `_legacy_root_inputs/` 当正式输入
