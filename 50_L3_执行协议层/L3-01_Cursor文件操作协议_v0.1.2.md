# L3-01 Cursor 文件操作协议 v0.1.2

> 状态：候选真源 / 未定版 / 待测试  
> 定位：规定 Cursor 或人工执行时如何读取、修改、创建、备份、diff 文件。  

---

## 1. 基本原则

Cursor 文件操作必须遵守：

1. 先读后改。
2. 先备份后覆盖。
3. 默认输出候选文件，不直接覆盖正式正文。
4. 只改任务单指定文件。
5. 不跨目录搜索后擅自修改。
6. 不从废弃归档反向覆盖当前工程。
7. 不让图片、对话、临时说明覆盖 Markdown 真源。
8. 不修改 L0-L2 / L1.5 真源，除非任务单明确允许且人工确认。
9. 每次执行必须生成 diff / 变更摘要。

---

## 2. 文件权限矩阵

| 区域 | 读 | 写 | 覆盖 | 备注 |
|---|---|---|---|---|
| L0-L2 / L1.5 | 是 | 默认否 | 否 | 系统真源区 |
| L3 | 是 | 条件写 | 需备份 | 仅版本升级 |
| Project Harness | 是 | 是 | 需备份 | 测试项目壳 |
| IR | 是 | 条件写 | 需备份 | 项目中间表示 |
| runtime | 是 | 是 | 需备份 | 状态演化记录 |
| chapters/chxx.md | 是 | 默认否 | 人工确认 | 正式正文 |
| chapters/_candidates | 是 | 是 | 可新建 | 候选正文输出区 |
| tests | 是 | 追加 | 否 | 测试记录 |
| logs | 是 | 追加 | 否 | 执行 / 断点 / 修复 |
| snapshots | 是 | 是 | 否 | 快照 |
| 废弃归档 | 是 | 否 | 否 | 只读参考 |

---

## 3. 文件操作类型

允许操作：

- read：读取文件
- create：新建文件
- update：修改文件
- append：追加记录
- copy：复制备份
- rename：重命名
- rollback：回滚
- diff：生成差异说明

禁止默认操作：

- delete：删除文件
- overwrite：无备份覆盖
- recursive_edit：递归批量修改
- archive_restore：从归档恢复覆盖当前工程
- image_to_truth：图片反向定义 Markdown

---

## 4. 标准文件操作任务单

```yaml
文件操作任务:
  操作类型: read / create / update / append / copy / rename / rollback / diff
  任务来源: L1 / L1.5 / L2 / L3 / ProjectHarness
  目标文件: ""
  参考文件: []
  禁止文件: []
  备份策略: 必须备份 / 可不备份
  输出文件: ""
  diff摘要文件: ""
  操作说明: ""
  验收位置: ""
```

---

## 5. 候选输出规则

正文相关执行默认输出到：

```text
chapters/_candidates/
```

示例：

```text
chapters/_candidates/ch01_candidate_v01.md
```

正式正文文件：

```text
chapters/ch01.md
```

默认只读，不直接覆盖。

只有满足以下条件才可合并正式正文：

1. 候选产物已生成。
2. diff 摘要已生成。
3. L1 / L1.5 复验通过。
4. 人工确认合并。
5. 合并前备份正式正文。

---

## 6. 命名规则

新增文件命名：

```text
层级-编号_功能名_v版本_状态.md
```

执行日志命名：

```text
L3RUN-YYYYMMDD-HHMM_任务名.md
```

备份文件命名：

```text
原文件名.bak_YYYYMMDD_HHMM
```

diff 摘要命名：

```text
DIFF-YYYYMMDD-HHMM_任务名.md
```

---

## 7. 操作后必须记录

每次操作后必须记录：

- 读取了哪些文件
- 修改了哪些文件
- 新增了哪些文件
- 备份在哪里
- diff 摘要在哪里
- 输出产物在哪里
- 是否需要回 L1 / L1.5 复验
