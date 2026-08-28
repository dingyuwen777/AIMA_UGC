---
schema: rvc-change/v1
id: "CHG-20260828-voice-type-prompt-table"
title: "更新发声类型定义并统一 Prompt 判断标准表格"
level: L2
status: in_progress
owner: "chatgpt"
branch: "feature/voice-type-prompt-table"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "analysis"
  - "export"
  - "tests"
affected_paths:
  - "backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md"
  - "backend/src/aima_ugc/platform/export/excel.py"
  - "tests/unit/analysis/test_voice_type_taxonomy.py"
  - "tests/unit/platform/test_excel_voice_type_taxonomy.py"
contracts: []
data_changes: []
---

# 目标

按用户本轮确认的七类发声类型重新定义当前 Prompt，并把语义相关性、发声类型、情感、一级/二级标签等判断标准统一整理为“表格定义 + 表格下高混淆场景/示例”的可维护结构。

本次只改变 Prompt Taxonomy/判断语义与 Excel 中文展示别名，不改变输出 JSON 字段、Python Contract、数据库 Schema、HTTP API 或 generated client；历史 Analysis Result 不改写。

# 成功标准

- [x] 当前机器 Taxonomy 仍为 7 类：保留可兼容机器值，新增 `industry_professional`，移除当前 Taxonomy 的 `other_organization`。
- [x] 发声类型中文业务定义与用户本轮提供的七类定义一致。
- [x] `语义相关性判断标准`、`内容发声类型判断标准`、`情感判断标准`、`一级/二级标签判断标准` 均以表格作为主要定义形式。
- [x] 每个判断标准表格下均保留或补充适用的高混淆场景和示例，帮助模型理解边界，而不是只提供枚举。
- [x] 现有输出结构 `item_no/relevance/voice_type/sentiment/labels` 不变；RuntimeTaxonomyValidator 继续按 Prompt Taxonomy 校验。
- [x] Excel 当前合法七类显示新的中文业务名称；历史 `other_organization` 仍可兼容展示，不被重新解释为“行业从业发声”。
- [x] 其他生产代码、Contract、数据库、API、generated client 经审计无同步修改必要；README/Appendix/Blueprint 不复制具体七类业务定义，无需机械同步。
- [ ] 目标 Unit、仓库质量门禁和完整 PR CI 通过后正常合并 `main`，并验证 main push CI。

# 范围

- 修改 `content_labeling_v3.md` 的机器 Taxonomy、发声类型定义、判断表格、高混淆场景和示例。
- 把语义相关性和情感判断从列表整理为表格，并在表格后保留/补充示例或混淆边界。
- 保持一级/二级标签表格，整理其后示例/边界结构，使各判断维度风格一致。
- 更新 Excel 发声类型中文展示别名。
- 更新直接锁定 Prompt/Excel 行为的 Unit 测试。
- 审计其他代码和文档影响。

# 非目标

- 不修改 `ContentVoiceType`、HTTP Contract、OpenAPI、generated client。
- 不修改 PostgreSQL Schema/Migration。
- 不回写或重分类历史 Analysis Result。
- 不新增 Taxonomy API、配置中心、数据库 Taxonomy 表或前端页面。
- 不改 sentiment 合法值和一级/二级标签合法值集合。
- 不执行生产部署或批量重新打标。

# 必须保持不变

- Prompt Markdown 仍是情感、发声类型、一级/二级标签及判断规则唯一业务事实源。
- 机器 Taxonomy 只声明程序需要严格校验的合法值/父子关系；自然语言表格、边界和示例负责告诉模型“怎么判”。
- 历史结果继续由既有 `prompt_sha256/taxonomy_sha256` 追溯当时规则。
- `relevance=relevant` / `irrelevant` 的结构约束不变。
- 历史 `other_organization` 结果不改写、不映射为 `industry_professional`；仅在 Excel 展示别名中继续兼容旧值。

# 已确认实现决定

当前七类业务名称与机器值：

```text
真实用户发声     -> user_voice
品牌官方发声     -> brand_official
门店经销商发声   -> dealer_promotion
营销推广发声     -> creator_marketing
行业从业发声     -> industry_professional
媒体机构发声     -> media_information
无法判断         -> unknown
```

其中 `creator_marketing` 与 `media_information` 保留稳定机器值，但业务定义按本轮用户确认规则扩展；`other_organization` 从当前机器 Taxonomy 移除，仅保留历史结果读取/Excel 展示兼容。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 使用用户提供的七类发声类型定义，包含真实用户、品牌官方、门店经销商、营销推广、行业从业、媒体机构、无法判断 | user:2026-08-28-发声类型分类 | not_satisfied | Prompt 已完成七类表格和机器 Taxonomy 实现；等待新 HEAD Unit/CI Green 后转 satisfied |
| R2 | 情感判断、发声类型等判断标准像一级/二级标签一样使用表格，方便展示和修改 | user:2026-08-28-Prompt表格化 | not_satisfied | 相关性、发声类型、情感、一级/二级标签均已形成表格；等待新 HEAD Unit/CI Green |
| R3 | 每个判断标准表格下提供示例或高混淆场景帮助 AI 判断 | user:2026-08-28-示例与高混淆 | not_satisfied | 四个判断维度均已保留/补充高混淆场景和示例；等待新 HEAD Unit/CI Green |
| R4 | 检查其他代码和文档是否需要同步，不应假设只有 Prompt 受影响 | user:2026-08-28-影响审计 | not_satisfied | 核心 Analysis/Contract/DB/API/generated 无固定枚举依赖；Excel 是唯一生产代码同步项；README/AI Appendix/Blueprint/Excel Appendix 不复制七类具体业务定义；等待最终 CI/diff Review 后转 satisfied |
| R5 | 修改完成后正常合并到 `main` | user:2026-08-28-合并主分支 | not_satisfied | Draft PR #258 已创建；等待 Green、Review、Ready、merge 和 main push CI |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Prompt Taxonomy 七类、新表格/示例保留、旧值不再是当前合法值、Excel 新/历史显示兼容；Red 已准确覆盖这些失败边界 |
| 接口 / Contract | not_applicable | 输出 JSON 字段、Pydantic/HTTP Contract/OpenAPI 不变；正式 generated drift 在 Red run 已通过，最终 HEAD 继续复验 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、Migration、文件持久化或 runtime dependency；永久 CI 仍会提供回归证据，但不把它写成独立需求 |
| 用户 / Workflow Acceptance | not_applicable | 不新增或改变前端/用户操作入口；Prompt/Excel 行为由 Unit 和既有完整 CI 回归 |
| 跨组件 Golden Path | not_applicable | 不修改 API/Job/Worker 装配或跨进程链 |
| 外部依赖 Probe | not_applicable | 不修改 LLM HTTP 协议或外部 Provider 字段；无需付费 Probe |
| Build / Package / Runtime | required | 使用仓库永久 CI 的 Repository Quality / build regression |
| Docs / Governance / Other | required | Change Ready/Completion Gate、Prompt Markdown 一致性、代码/文档影响审计 |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

- [x] 从最新 `main` 恢复 AGENTS/Coding Skill、当前 Prompt、Analysis README、AI/Excel Appendix、Excel exporter 和现有回归测试事实。
- [x] 建立代码/文档影响审计：核心 Analysis/Contract/DB/API/generated 无需同步；Excel 展示别名是唯一生产代码同步项；业务定义文档无需复制更新。
- [x] Red：增加新七类机器 Taxonomy、表格结构和 Excel 展示回归测试并取得有效失败证据。
- [x] Green 实现：更新 Prompt Taxonomy 与相关性/发声类型/情感/标签表格、边界和示例。
- [x] Green 实现：更新 Excel 当前七类中文展示，并保留历史 `other_organization` 展示兼容。
- [x] 清理一次性补丁 Workflow；PR changed files 已确认只剩 5 个正式文件。
- [ ] 运行最终 HEAD 目标测试与完整永久 CI。
- [ ] 执行 A1/A2 Review、Completion Audit，Change 进入 `ready_for_review`。
- [ ] PR 全绿后 squash merge `main` 并验证 main push CI。
- [ ] 独立归档 Change。

# Red 证据

- Red HEAD：`c6f87f3b7e4e14a65f88e806013ba99e7772dcbc`；PR #258 CI run `33155008319`，Repository Quality job `98795613709`。
- generated Contract/Orval drift 在 Unit 前已通过；Ruff `529 files already formatted`、`All checks passed!`，mypy `Success: no issues found in 254 source files`，说明 Red 不是格式/类型/生成物噪声。
- Unit：`8 failed, 695 passed`。8 个失败恰好来自：旧七类 Taxonomy、缺少统一表格/新业务名称、Excel 仍使用旧中文别名或缺少 `industry_professional` 别名。
- Secret/docs gate 同轮成功；没有删除或跳过失败测试制造 Green。

# 实现事实

- 当前 Prompt Taxonomy：`user_voice / brand_official / dealer_promotion / creator_marketing / industry_professional / media_information / unknown`。
- `语义相关性判断标准`：表格 + 高混淆场景 + 示例。
- `内容发声类型判断标准`：七类业务定义表格 + 两层证据 + 高混淆场景 + 示例。
- `情感判断标准`：表格 + 高混淆场景 + 示例。
- `一级/二级标签判断标准`：原 9 个一级/39 个二级标签表格不改变；表格后的边界与示例统一命名为 `一级/二级标签高混淆场景` / `一级/二级标签示例`。
- Excel 当前七类使用新中文业务名称；历史 `other_organization` 仍显示 `其他机构传播`，未来未知机器值仍通过既有 fallback 原样展示。
- 一次性 `.github/workflows/temp-voice-type-prompt-patch.yml` 已由同一工具提交删除，最终 PR diff 无该文件。

# 代码与文档影响审计

- `ContentVoiceType` 已是结构字符串，合法值由 Prompt Runtime Taxonomy 校验，本次无需 Contract 修改。
- PostgreSQL 自 `20260828_0030` 起只约束 `voice_type` 非空结构，不复制业务枚举，本次无需 Migration。
- HTTP/OpenAPI/generated client 不维护具体 voice type enum，本次无需生成物变更。
- Analysis README、AI Appendix 与 Blueprint 只声明“Prompt 是唯一 Taxonomy 事实源”，没有复制当前七类定义；同步修改会重新制造第二份业务事实，因此不改。
- Excel Appendix 只描述“中文别名不是合法值白名单、未知新值原样输出”的机制；本次实现仍符合该机制，因此无需修改。

# 文档影响

业务判断文档只修改唯一事实源 `content_labeling_v3.md`。其他 README/Appendix/Blueprint 经审计不需要同步具体七类定义；Change 记录本轮变更原因和验证证据。
