# Project Harness v0.2 升级说明

> 状态：测试项目壳 / 非系统真源

## 本次升级

在 TP-001 原测试项目壳基础上新增：

1. IR 文件组
2. runtime 最小槽位
3. chapters/_candidates 候选正文目录
4. logs/L3_执行日志.md
5. v0.2 执行顺序说明

## 核心边界

Project Harness 只作为真实小说项目压测载体。  
IR 是项目中间表示，不是系统真源。  
runtime 是测试组件，不是 L4。  
候选正文不得自动覆盖正式正文。

## 当前路线

L3 v0.1.2  
↓  
Project Harness + IR + 最小 Runtime  
↓  
真实项目输入  
↓  
L1 → L1.5 → L2 → L3  
↓  
复验与断点记录
