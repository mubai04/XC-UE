# 13 测试与 API 证据有效性清单

---

## 1. 证据分类（15 类）

| 类 | 代表 | 有效性 |
|----|------|--------|
| 1 基础设施 | conftest, 加载器 | VALID |
| 2 路径安全 | 输入校验测试 | VALID |
| 3 Schema | 结构定义校验 | VALID |
| 4 API 协议 | R5B/R5C 评估器 | VALID（L2 技术） |
| 5 路由 | test_L1_5, gate_rules | VALID（实现 SSOT） |
| 6 确定性提取 | R4C 泛化探针 | VALID |
| 7 模块内诊断 | test_L2_0x_* mock | PARTIAL（无真实语义） |
| 8 修复单规划 | R4A mock | VALID（结构） |
| 9 L3 执行 | R4A mock L3 | PARTIAL（非真实 API） |
| 10 L1 问题发现 | L1 semantic golden | PARTIAL（Phase 2A） |
| 11 L1.5 路由 | R4A + test_L1_5 | VALID |
| 12 跨层流水线 | test_R4A_修复流水线 | VALID（mock only） |
| 13 业务效果 | R5D | INVALID（v1 语料）/ PENDING（v2） |
| 14 层级混杂 | DOMAIN_CAPABILITY=PASSED 无定义符合 | INVALID 扩张 |
| 15 无效评测 | v1 R5D 盲评 | INVALID（语料污染） |

---

## 2. R4A—R5C 分别证明

| 轮次 | 证明 | 不能证明 |
|------|------|----------|
| **R4A** | mock 下 L1.5→L2→L3 结构可达；正式章节不被改 | 真实模型、业务质量 |
| **R4B** | L2-02~06 独立模块结构（status 标志；无独立 test_R4B 文件名） | 运行时行为 |
| **R4C** | 确定性逻辑泛化、防夹具硬编码 | LLM 输出 |
| **R4D** | 外部窄查反例回归锁定 | 全覆盖 |
| **R4E** | 独立探针变体、防样本硬编码 | 业务 |
| **R5A** | 首次真实 API 暴露协议问题 | 稳定通过 |
| **R5B** | 超时/重试/定向复测改进 | 全量 12/12（当时） |
| **R5C** | **v1 12/12 技术协议 PASS** | 修复语义、L1/L3、业务 |
| **R5D** | 语料审计工具 + 半盲评脚手架 | 模型业务有效性（v1 暂停） |

---

## 3. 可保留结论

```text
L1_5_EXECUTABLE = PASSED          → L1.5 路由代码+测试通过
R4B/R4C/R4D/R4E = PASSED          → L2 结构/确定性/反例（mock/synthetic）
FAILURE_PACKET_TO_CANDIDATE_PIPELINE = PASSED → mock 跨层
L2_R5C_TECHNICAL_PROTOCOL = PASSED  → 仅：真实 API + Schema + 证据绑定 + 技术链路
```

**不可保留：**

- DOMAIN_CAPABILITY=PASSED → 业务能力通过
- R5C → L2 修复有效
- R4A → 生产就绪
- v1 pilot → R5D 业务结论

---

## 4. DOMAIN_CAPABILITY=PASSED 缺乏定义符合性

generated 中 L2_02~06_DOMAIN_CAPABILITY=PASSED **不满足**八链标准（缺正式定版、缺语义有效性测试）。应解读为 **工程实现候选通过**，非正式能力认证。

```text
EVALUATION_CONSTRUCT_VALIDITY = PARTIAL
```
