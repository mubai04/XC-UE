# L3-07 Project Harness 运行协议 v0.1.2

> 状态：候选真源 / 未定版 / 待测试  
> 定位：规定 XC-UE 项目试验台如何接入 L3 执行。  

---

## 1. Project Harness 定位

Project Harness 是测试项目壳。

它不是 SRN-U。  
它不是 Xuke·Chuangjie。  
它不是 XC-UE 系统真源。  
它不是新的理论系统。  

它只用于承载真实小说项目，压测 XC-UE 全链路。

---

## 2. 推荐结构

Project Harness 放在 `70_测试项目/`，不与 L0–L3 系统层平级：

```text
70_测试项目/
└── TP-001_项目名/
    ├── 00_项目说明.md
    ├── IR/
│   ├── IR-00_项目索引.md
│   ├── IR-01_立项卡.md
│   ├── IR-02_世界约束.md
│   ├── IR-03_角色动机表.md
│   ├── IR-04_事件链.md
│   ├── IR-05_章节目标表.md
│   ├── IR-06_读者预期表.md
│   ├── IR-07_发布状态表.md
│   └── IR-08_状态快照.md
├── runtime/
│   ├── RT-01_价值函数演化表.md
│   ├── RT-02_角色状态迁移表.md
│   ├── RT-03_事件刺激记录.md
│   ├── RT-04_目标变化记录.md
│   └── RT-05_选择结果记录.md
├── chapters/
│   ├── ch01.md
│   ├── ch02.md
│   └── _candidates/
├── tests/
│   ├── L1-01_内部创作测试.md
│   ├── L1-02_读者投入测试.md
│   ├── L1-03_发布锁测试.md
│   ├── L1.5_路由测试.md
│   └── L2_调用记录.md
├── logs/
│   ├── 断点记录.md
│   ├── 修复记录.md
│   └── L3_执行日志.md
└── snapshots/
```

---

## 3. Project Harness 运行顺序

1. 填 IR。
2. 写 ch01。
3. 跑 L1-01。
4. 跑 L1-02。
5. 跑 L1-03。
6. 失败进入 L1.5。
7. 必要时调用 L2。
8. L2 产物进入 L3。
9. L3 输出候选产物到 chapters/_candidates。
10. 记录 logs。
11. 回 L1 / L1.5 复验。
12. 若发现运行时断点，写入 runtime。

---

## 4. Project Harness 权限

可写：

- IR
- runtime
- chapters/_candidates
- tests
- logs
- snapshots

默认只读：

- chapters/ch01.md
- chapters/ch02.md

禁止：

- 反向改 XC-UE 系统真源
- 覆盖 L0-L2
- 从废弃归档恢复旧测试覆盖当前项目
- 候选正文自动覆盖正式正文

---


---

## 4.1 候选目录创建规则

若以下目录不存在，L3 在执行候选正文任务前必须先创建：

```text
chapters/_candidates/
```

创建后必须记录到执行日志：

```yaml
候选目录创建:
  目录: chapters/_candidates/
  创建状态: 已存在 / 已创建 / 创建失败
  记录位置: logs/L3_执行日志.md
```

禁止因 `_candidates/` 不存在而直接写入正式正文目录。


## 5. Runtime 最小槽位

Project Harness 内可先建立最小 Runtime，不升为正式 L4：

```text
runtime/
├── RT-01_价值函数演化表.md
├── RT-02_角色状态迁移表.md
├── RT-03_事件刺激记录.md
├── RT-04_目标变化记录.md
└── RT-05_选择结果记录.md
```

Runtime 当前用途：

- 记录价值函数如何变化
- 记录角色状态如何迁移
- 记录事件刺激造成什么内部变化
- 记录目标如何变化
- 记录选择删除了什么可能性并制造了什么新约束

当前边界：

Runtime 当前只记录状态迁移，不承担自动推演。  
它只服务 TP 项目压测，不作为正式 L4。  
是否上升为正式运行时层或 L4，必须等真实压测断点出现后再判断。

---

## 6. Harness 执行任务单

```yaml
ProjectHarness执行任务:
  项目: TP-001
  当前阶段: 填IR / 写正文 / L1测试 / L1.5路由 / L2修复 / L3执行 / 复验 / 断点记录
  输入文件: []
  输出文件: []
  是否允许改正式正文: 否
  候选输出目录: chapters/_candidates/
  日志位置: logs/
  回流验收位置: ""
```
