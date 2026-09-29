---
schema: coding-change/v1
id: CHG-20260929-112600-content-labeling-v4-6
title: 将首次正式 AI 打标基线升级为 Prompt V4.6
level: L2
status: active
owner: codex
branch: feature/656-content-labeling-v4-6
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - administration
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v4.6.md
  - backend/src/aima_ugc/modules/analysis/prompts/content_labeling_bootstrap.txt
  - backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py
  - backend/src/aima_ugc/modules/analysis/schemes.py
  - backend/src/aima_ugc/modules/analysis/content_labeling.py
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/adapters/llm/openai_compatible.py
  - backend/src/aima_ugc/modules/analysis/offline_labeling.py
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - tests/unit/analysis/
contracts:
  - Analysis Scheme definition semantics
  - ContentLabeling model payload/input hash
  - content-labeling.v4.6 output protocol
data_changes: []
---

# 变更摘要

- **Requirement Source**：#656。
- **问题**：首次正式 AI 打标已经确定使用用户提供的 Prompt V4.6，但当前 main 仍以 V4 bootstrap，且 Scheme/Validator/模型输入/离线链存在 V4.6 未闭环点。
- **目标**：让 V4.6 成为第一次正式打标基线；仓库 Prompt 资产与用户上传原文完全一致；正式/离线共用同一 V4.6 语义。
- **非目标**：不新增前端回归，不改前端 Taxonomy 展示机制，不做历史重打，不做 DB Schema/Migration，不 Release/Deploy。

# 已确认事实

| ID | 事实 | 来源 |
| --- | --- | --- |
| E1 | 用户确认尚未开始任何正式打标，V4.6 是第一次正式打标 Prompt | #656 / 当前任务 |
| E2 | 当前 bootstrap pointer 仍为 `content_labeling_v4.md` | `content_labeling_bootstrap.txt` |
| E3 | Parser 已声明支持 `content-labeling.v4.6`，但仓库缺少正式 V4.6 Prompt 文件 | `prompt_taxonomy.py` / prompts 目录 |
| E4 | Scheme Contract 仍硬要求“无法判断 / 无法分类” | `contracts/administration.py` |
| E5 | V4.6 上传原文没有旧版 AIMA_TAXONOMY marker；现有 Scheme bootstrap/compiler 依赖 marker | `schemes.py` + 用户原文件 |
| E6 | 模型 payload 当前未发送 platform，但 Canonical 已有 platform | `content_labeling.py` / Canonical Contract |
| E7 | V4.6 要求三类 voice_type、voice_evidence 非空、irrelevant 固定空结构、全空输入允许 `[EMPTY_INPUT]` | 用户 V4.6 原文件 |
| E8 | 离线 Excel 现有补充指令会把 irrelevant 强制为 relevant | `openai_compatible.py` / `content_labeling.py` |

# 目标与成功标准

- [ ] AC1 Prompt 文件与用户上传原文文本完全一致；上传原文件 CRLF 字节 SHA-256=`44e584274fd2bd5b5d5bf81143f29068c84d44d97c6d723af51c24a29887a1a5`，Git LF 规范化文本 SHA-256=`9a8fa7e98680ee707871f0303d4154dfbae4e900c0be90535edd8b5793ab02cb`。
- [ ] AC2 bootstrap pointer 指向 V4.6。
- [ ] AC3 V4.6 Parser 正确得到 3 voice types、4 sentiments、5 source types、8 content intents、9 个一级标签及正确二级标签。
- [ ] AC4 Scheme bootstrap/compiler 支持 V4.6，首次编译后的 Prompt 与原始 V4.6 完全一致；结构化 Taxonomy 与 Prompt 原文一致。
- [ ] AC5 Scheme Contract 删除旧“无法判断/无法分类”硬要求，但保留通用结构约束。
- [ ] AC6 模型 payload/input hash 包含 platform；evidence 仍只来自 title/text/author 五文本字段。
- [ ] AC7 V4.6 Validator 锁定 voice_evidence、irrelevant、EMPTY_INPUT、clear 终态。
- [ ] AC8 V4.6 离线链不强制 irrelevant→relevant，也不以本地伪造业务结果掩盖失败。
- [ ] AC9 不新增前端回归；现有动态 Taxonomy 前端契约保持不变。
- [ ] AC10 后端专项、静态检查、治理/文档、PR required CI 与独立 Review 通过。

# 必须保持不变

- `ContentLabelAnalysisV3` 持久化结构不变。
- Analysis Scheme 继续作为运行时唯一 active 业务事实源，Run 继续冻结 Prompt/Taxonomy/Model 身份。
- 前端继续通过 active Scheme / Filter Options 动态读取 Taxonomy。
- 不新增依赖、Migration、Release/Deploy 行为。

# 实施方案

1. **Prompt/Parser**
   - 原样新增 V4.6 文件并切 bootstrap pointer；
   - 修正 V4.6 Markdown Taxonomy 解析边界，避免“标签规则”混入最后一级标签。

2. **Scheme**
   - V4.6 bootstrap 仍生成一个受控 `{{AIMA_TAXONOMY_JSON}}` 模板标记；
   - V4.6 compiler 将该标记移除并按结构化 definition 精确重建 Markdown 闭集，初始编译结果必须逐字等于原文件；
   - 旧 V3/V4 JSON-marker Scheme 路径保持不变。

3. **Model Input / Validator**
   - platform 加入模型 payload 和 input hash；
   - V4.6 三类 voice_type 都要求 voice_evidence；
   - irrelevant 固定结构；
   - 五文本字段全空时只允许 `[EMPTY_INPUT]`；
   - final decision_status 仍只能收敛到 clear。

4. **Offline**
   - V4.6 不注入“irrelevant 必须改 relevant”的 Excel 覆盖规则；
   - V4.6 validation/provider 失败不走本地业务分类 fallback。

5. **Docs/Tests**
   - 只补后端/Contract/Analysis tests，不增加前端回归；
   - 同步 Analysis README 与 AI 打标 Appendix。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | V4.6 Prompt 与上传文件一致 | #656 AC1 | not_satisfied | 待实现/验证 |
| R2 | 首次 bootstrap 使用 V4.6 | #656 AC2 | not_satisfied | 待实现/验证 |
| R3 | V4.6 Parser/Scheme 可完整编译 | #656 AC3-AC5 | not_satisfied | 待实现/验证 |
| R4 | platform/Validator 与 V4.6 一致 | #656 AC6-AC7 | not_satisfied | 待实现/验证 |
| R5 | 离线链不覆盖 V4.6 | #656 AC8 | not_satisfied | 待实现/验证 |
| R6 | 不增加前端回归且前端 Contract 不破坏 | #656 AC9 | not_satisfied | 待 diff/Contract 复核 |
| R7 | 验证/Review/CI/merge 闭环 | #656 AC10 | not_satisfied | 待验证 |

# Validation Matrix

| 验证层 | 状态 | 计划 |
| --- | --- | --- |
| 行为 / Unit | required | Prompt Parser、Scheme compiler、Validator、payload/hash、offline |
| Contract | required | Administration Scheme definition + V4.6 output shape |
| Integration / Persistence | required | 现有 Analysis Scheme/Run 相关集成；无 Schema 变化 |
| User / Browser | not_applicable | 用户明确不增加前端回归；本次不改前端交互/Contract 形状 |
| External Provider Probe | not_applicable | Prompt 协议升级不需要付费 Provider 作为 PR CI |
| Build / Static | required | Ruff、mypy |
| Docs / Governance | required | README/Appendix、Change completion、docs/governance checks |

# 风险与回滚

- **Prompt 一致性**：任何业务文本自动格式化/改写均禁止；以 LF 规范化后的全文与固定 SHA-256 门禁验证，CRLF/LF 仅作为换行编码差异记录。
- **兼容性**：旧 V3/V4 Scheme 编译路径必须继续工作；无历史正式打标结果，不涉及结果迁移。
- **部署事实**：当前生产/测试数据库是否已提前 bootstrap 旧 V4 仍需部署时读取环境确认；本 PR 不写生产数据。
- **回滚**：源码回滚即可；无 Schema/数据迁移。

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 交付状态

- 实现：进行中
- PR：待创建
- CI：待执行
- Review：待执行
- Merge：用户已授权，但仅在 required gates 全部通过后执行
- Release / Deploy：不适用
