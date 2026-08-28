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

- [ ] 当前机器 Taxonomy 仍为 7 类：保留可兼容机器值，新增 `industry_professional`，移除当前 Taxonomy 的 `other_organization`。
- [ ] 发声类型中文业务定义与用户本轮提供的七类定义一致。
- [ ] `语义相关性判断标准`、`内容发声类型判断标准`、`情感判断标准`、`一级/二级标签判断标准` 均以表格作为主要定义形式。
- [ ] 每个判断标准表格下均保留或补充适用的高混淆场景和/或示例，帮助模型理解边界，而不是只提供枚举。
- [ ] 现有输出结构 `item_no/relevance/voice_type/sentiment/labels` 不变；RuntimeTaxonomyValidator 继续按 Prompt Taxonomy 校验。
- [ ] Excel 当前合法七类显示新的中文业务名称；历史 `other_organization` 仍可兼容展示，不被重新解释为“行业从业发声”。
- [ ] 其他生产代码、Contract、数据库、API、generated client 经审计无同步修改必要；README/Appendix/Blueprint 不复制具体七类业务定义，除非发现与新实现冲突，否则不机械改文档。
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
- 不改 sentiment 合法值和一级/二级标签合法值集合，除非本轮排版整理发现原 Prompt 自身错误；若发现需另行说明。
- 不执行生产部署或批量重新打标。

# 必须保持不变

- Prompt Markdown 仍是情感、发声类型、一级/二级标签及判断规则唯一业务事实源。
- 机器 Taxonomy 只声明程序需要严格校验的合法值/父子关系；自然语言表格、边界和示例负责告诉模型“怎么判”。
- 历史结果继续由既有 `prompt_sha256/taxonomy_sha256` 追溯当时规则。
- `relevance=relevant` / `irrelevant` 的结构约束不变。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 使用用户提供的七类发声类型定义，包含真实用户、品牌官方、门店经销商、营销推广、行业从业、媒体机构、无法判断 | user:2026-08-28-发声类型分类 | not_satisfied | 待实现 Prompt 表格与机器 Taxonomy |
| R2 | 情感判断、发声类型等判断标准像一级/二级标签一样使用表格，方便展示和修改 | user:2026-08-28-Prompt表格化 | not_satisfied | 待统一 Prompt 结构 |
| R3 | 每个判断标准表格下提供示例或高混淆场景帮助 AI 判断 | user:2026-08-28-示例与高混淆 | not_satisfied | 待补充/整理各节边界和示例 |
| R4 | 检查其他代码和文档是否需要同步，不应假设只有 Prompt 受影响 | user:2026-08-28-影响审计 | not_satisfied | 已确认核心 Contract/DB/API 动态化；仍需完成 Excel/测试和最终 diff 审计 |
| R5 | 修改完成后正常合并到 `main` | user:2026-08-28-合并主分支 | not_satisfied | 待 PR、CI、Review、merge/main 验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Prompt Taxonomy 七类、新表格/示例保留、旧值不再是当前合法值、Excel 新/历史显示兼容 |
| 接口 / Contract | not_applicable | 输出 JSON 字段、Pydantic/HTTP Contract/OpenAPI 不变；只通过现有 Contract regression 证明无漂移 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、Migration、文件持久化或 runtime dependency |
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
- [x] 建立代码/文档影响初步审计：核心 Analysis/Contract/DB/API/generated 无需同步；Excel 展示别名需要最小修改。
- [ ] Red：增加新七类机器 Taxonomy、表格结构和 Excel 展示回归测试并取得有效失败证据。
- [ ] Green：更新 Prompt Taxonomy 与各判断标准表格/示例。
- [ ] Green：更新 Excel 中文展示兼容。
- [ ] 完成其他代码和文档最终影响审计。
- [ ] 运行目标测试与完整永久 CI。
- [ ] 执行 A1/A2 Review、Completion Audit，Change 进入 `ready_for_review`。
- [ ] PR 全绿后 squash merge `main` 并验证 main push CI。
- [ ] 独立归档 Change。

# 文档影响

当前 Analysis README、AI Appendix、Blueprint 已明确 Prompt 为唯一具体业务 Taxonomy 事实源，没有复制当前七类定义，原则上无需随本次业务分类调整同步。Excel Appendix 只描述别名机制而不复制分类值；若实现仍符合该机制则无需修改。最终以 PR diff/全文审计为准。
