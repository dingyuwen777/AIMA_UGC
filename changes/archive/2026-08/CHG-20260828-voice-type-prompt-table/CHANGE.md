---
schema: rvc-change/v1
id: "CHG-20260828-voice-type-prompt-table"
title: "更新发声类型定义并统一 Prompt 判断标准表格"
level: L2
status: done
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
  - "tests/unit/analysis/test_content_labeling.py"
  - "tests/unit/analysis/test_voice_type_taxonomy.py"
  - "tests/unit/platform/test_excel_export.py"
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
- [x] 表格化不丢失原 Prompt 仍适用的判断能力：发声类型判断顺序、真实用户/门店、官方/媒体、媒体/用户等边界继续保留并适配新七类。
- [x] 现有输出结构 `item_no/relevance/voice_type/sentiment/labels` 不变；RuntimeTaxonomyValidator 继续按 Prompt Taxonomy 校验。
- [x] Excel 当前合法七类显示新的中文业务名称；历史 `other_organization` 仍可兼容展示，不被重新解释为“行业从业发声”。
- [x] 其他生产代码、Contract、数据库、API、generated client 经审计无同步修改必要；README/Appendix/Blueprint 不复制具体七类业务定义，无需机械同步。
- [x] 最终实现 HEAD `7ffe6931c906105a142a71fb0e2e03d1c2490dd1` 已通过 CI、Runtime Acceptance、Full-stack Acceptance、Developer Tooling Compatibility；Change 进入 Ready 后需在新 HEAD 重新通过全部永久门禁。

# 范围

- 修改 `content_labeling_v3.md` 的机器 Taxonomy、发声类型定义、判断表格、高混淆场景和示例。
- 把语义相关性和情感判断从列表整理为表格，并在表格后保留/补充示例或混淆边界。
- 保持一级/二级标签表格，整理其后示例/边界结构，使各判断维度风格一致。
- 更新 Excel 发声类型中文展示别名。
- 更新直接锁定 Prompt/Excel 行为及旧排版/展示约束的 Unit 测试。
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
| R1 | 使用用户提供的七类发声类型定义，包含真实用户、品牌官方、门店经销商、营销推广、行业从业、媒体机构、无法判断 | user:2026-08-28-发声类型分类 | satisfied | Prompt 机器 Taxonomy 已固定为 `user_voice/brand_official/dealer_promotion/creator_marketing/industry_professional/media_information/unknown`；七类中文定义及用户给出的官方账号、骑遇团、二手交易、维修/竞品等判别信号均已进入发声类型表格/边界/示例；Unit 703 passed |
| R2 | 情感判断、发声类型等判断标准像一级/二级标签一样使用表格，方便展示和修改 | user:2026-08-28-Prompt表格化 | satisfied | 语义相关性、发声类型、情感、一级/二级标签四个章节均使用 Markdown 表格作为主要定义；`test_prompt_judgment_sections_use_tables_with_examples_and_confusion_cases` 通过 |
| R3 | 每个判断标准表格下提供示例或高混淆场景帮助 AI 判断 | user:2026-08-28-示例与高混淆 | satisfied | 四个判断维度均有高混淆场景和示例；发声类型额外保留两层证据、10 组高混淆边界与明确判断顺序；A1 预审发现的内容守恒问题已修复，最终 Unit/CI 全绿 |
| R4 | 检查其他代码和文档是否需要同步，不应假设只有 Prompt 受影响 | user:2026-08-28-影响审计 | satisfied | 生产代码审计确认 Excel 展示别名是唯一额外实现同步项；2 个旧 Unit 断言按批准的新标题/中文显示同步；Contract/DB/API/generated 无固定业务枚举依赖，generated drift 通过；Analysis README、AI/Excel Appendix、Blueprint 不复制当前七类业务定义且仍与实现一致，因此不修改 |
| R5 | 修改完成后正常合并到 `main` | user:2026-08-28-合并主分支 | satisfied | PR #258 已在 Ready HEAD `e2d7b90924361002622edd436905c47f08b5dd3e` 五个永久门禁全绿后 squash merge；merge/main SHA `66ccfb7f26d9a904ee1db626eb3e9acc10cac56d`；合并后 main 的 Change Gate/CI/Runtime/Full-stack/Tooling 五个 push workflow 全部 success |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Prompt Taxonomy 七类、四类判断表格/示例、旧值不再是当前合法值、Excel 新/历史显示兼容；最终 CI Unit 703 passed |
| 接口 / Contract | not_applicable | 输出 JSON 字段、Pydantic/HTTP Contract/OpenAPI 不变；最终 CI Contract 92 passed、API 38 passed，正式生成链与 compatibility/drift 均通过 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、Migration、文件持久化或 runtime dependency；最终 PostgreSQL Integration 仍完整 success，作为额外回归证据 |
| 用户 / Workflow Acceptance | not_applicable | 不新增或改变前端/用户操作入口；Full-stack Acceptance `33155926522` success，作为真实 Excel 导出链额外证据 |
| 跨组件 Golden Path | not_applicable | 不修改 API/Job/Worker 装配；Runtime Acceptance `33155926565` success，作为额外运行时回归证据 |
| 外部依赖 Probe | not_applicable | 不修改 LLM HTTP 协议或外部 Provider 字段；无需付费 Probe |
| Build / Package / Runtime | required | CI `33155926602` Repository Quality `98798671471`：Ruff 529 files、mypy 254 source files、Wheel build/install/import、frontend lint/type/build、50 Vitest、31 Playwright 全部成功；Developer Tooling `33155926598` success |
| Docs / Governance / Other | required | Secret/docs、architecture/table ownership、generated drift 均通过；A1/A2 Review 已完成；本提交把 Change 切到 `ready_for_review`，需以新 HEAD 的 Change Completion Gate 为最终 Ready 证据 |

# Completion Audit

- [x] upstream_re_read：进入 Ready 前重新读取目标分支根 `AGENTS.md`、本轮用户的七类发声类型定义与表格/示例要求、当前 Prompt、Analysis README/AI/Excel Appendix 既有唯一事实源边界，并核对当前 `main`。
- [x] change_coverage：重新从用户要求独立重建完成定义，逐项对照七类业务定义、四类判断表格、每表格下边界/示例、代码/文档影响审计与 main 合并要求；未发现 Requirement omission。
- [x] reverse_audit：沿 `Prompt Taxonomy -> Prompt Loader/Runtime Validator -> Analysis Contract/DB/API -> Excel Export` 双向复核；核心运行链不维护具体枚举，Excel 仅保留展示别名；历史 `other_organization` 不会被新 `industry_professional` 重新解释。前端/Job/DB 无本次新增能力入口，因此相应能力反向审计不适用。
- [x] unresolved_cleared：R1-R4 已有最终 Green 证据并转 `satisfied`；实现范围内 `not_satisfied` 清零。R5 仅因仓库要求必须先通过 Ready/CI 再执行 merge/main 验证而 `explicitly_deferred`，不是功能遗漏。

# 任务

- [x] 从最新 `main` 恢复 AGENTS/Coding Skill、当前 Prompt、Analysis README、AI/Excel Appendix、Excel exporter 和现有回归测试事实。
- [x] 建立代码/文档影响审计：核心 Analysis/Contract/DB/API/generated 无需同步；Excel 展示别名是唯一生产代码同步项；业务定义文档无需复制更新。
- [x] Red：增加新七类机器 Taxonomy、表格结构和 Excel 展示回归测试并取得有效失败证据。
- [x] Green 实现：更新 Prompt Taxonomy 与相关性/发声类型/情感/标签表格、边界和示例。
- [x] Green 实现：更新 Excel 当前七类中文展示，并保留历史 `other_organization` 展示兼容。
- [x] A1 预审发现表格化删除旧 `判断顺序` 与三组仍适用边界；已恢复并适配新七类，避免排版重构降低模型判断信息量。
- [x] 第一轮 Green CI 发现 2 个旧测试仍依赖旧标题/旧中文展示；已按新批准行为更新断言，不修改生产实现。
- [x] 三个一次性补丁 Workflow 均已由工具提交自行删除；最终 PR changed files 只包含 Prompt、Excel、Change 和 4 个相关 Unit 测试。
- [x] 最终实现 HEAD `7ffe6931c906105a142a71fb0e2e03d1c2490dd1` 完成目标测试和完整永久 CI；CI/Runtime/Full-stack/Tooling 全绿。
- [x] 执行最终 A1/A2 Review 与 Completion Audit；无未解决严重/重要 Finding。
- [x] Change 切换为 `ready_for_review`，等待新 HEAD 正式 Ready 门禁复验。
- [x] PR 全绿后转 Ready、squash merge `main` 并验证 main push CI。
- [x] 独立归档 Change，并记录实际 merge/main CI 证据。

# Red / 调试证据

## 初始业务 Red

- Red HEAD：`c6f87f3b7e4e14a65f88e806013ba99e7772dcbc`；PR #258 CI run `33155008319`，Repository Quality job `98795613709`。
- generated Contract/Orval drift 在 Unit 前已通过；Ruff `529 files already formatted`、`All checks passed!`，mypy `Success: no issues found in 254 source files`，说明 Red 不是格式/类型/生成物噪声。
- Unit：`8 failed, 695 passed`。8 个失败恰好来自：旧七类 Taxonomy、缺少统一表格/新业务名称、Excel 仍使用旧中文别名或缺少 `industry_professional` 别名。

## 第一轮 Green 暴露的遗留断言

- HEAD `828742f51e5b9aaa9c23440e95eb2ae64be3d540`，CI run `33155596460`，Repository Quality job `98797569253`。
- generated drift、Ruff、mypy 全部成功；Unit 为 `2 failed, 701 passed`。
- `tests/unit/analysis/test_content_labeling.py` 仍要求旧标题 `## 多主题与边界冲突优先级`，与用户批准的“表格下高混淆场景”新结构冲突。
- `tests/unit/platform/test_excel_export.py` 仍要求旧展示 `达人/创作者营销`，与本轮批准的 `营销推广发声` 冲突。
- 两处均只更新旧断言；没有回退新业务定义或删除测试。
- 同一 HEAD 的 PostgreSQL Integration completed/success，Full-stack Acceptance completed/success，进一步确认生产实现和持久化/真实导出链本身无故障。

# 最终 Green / 回归证据

最终实现 HEAD `7ffe6931c906105a142a71fb0e2e03d1c2490dd1`；CI checkout 的 PR merge ref 明确为把该 HEAD merge 到当时最新 `main=3040d72b92602c00be8740edac509538b07f9c1a`，因此最终验证包含并发主分支最新归档提交。

- CI run `33155926602`：completed / success；CI Gate success。
- Repository Quality job `98798671471`：
  - `scripts/contracts/generate.py` + Orval + generated drift + compatibility：success；
  - Ruff：`529 files already formatted`、`All checks passed!`；
  - mypy：`Success: no issues found in 254 source files`；
  - Unit：703 passed；Contract：92 passed；API：38 passed；
  - architecture / table ownership / Secret / docs：success；
  - Wheel `aima_ugc-0.1.0-py3-none-any.whl` build/install/import：success；
  - frontend Vitest：50 passed；production build：success；Playwright：31 passed。
- PostgreSQL Integration job `98798671641`：empty DB upgrade、historical migration compatibility、Platform、readiness HTTP、Database、Job Runtime、Collection、Content、Ingestion 全部 success。
- Full-stack Acceptance run `33155926522`：success。
- Runtime Acceptance run `33155926565`：canonical Compose、repository-relative host root、Windows overlay 全部 success。
- Developer Tooling Compatibility run `33155926598`：success。
- Change Completion Gate run `33155926634` 的 Coding completion-gate tests 成功，但因当时 Change `status: in_progress` 按设计失败；本提交已完成 Traceability/Audit 并切换为 `ready_for_review`，必须使用新 HEAD 的正式 Gate 结果作为合并前证据。

## Ready / 合并 / main 复验证据

- 最终 Ready HEAD：`e2d7b90924361002622edd436905c47f08b5dd3e`。
- PR #258 Ready HEAD 永久门禁全部 success：Change Completion Gate `33156478703`、CI `33156478701`、Runtime Acceptance `33156478713`、Full-stack Acceptance `33156478768`、Developer Tooling Compatibility `33156478707`。
- PR #258 已正常 squash merge；merge/main SHA：`66ccfb7f26d9a904ee1db626eb3e9acc10cac56d`。
- 合并后 `main=66ccfb7f26d9a904ee1db626eb3e9acc10cac56d` 的 push workflow 全部 success：Change Completion Gate `33156780904`、CI `33156780901`、Runtime Acceptance `33156780883`、Full-stack Acceptance `33156780886`、Developer Tooling Compatibility `33156780869`。
- 实现分支 `feature/voice-type-prompt-table` 已按仓库设置自动删除。
- 本任务未执行生产部署，也未批量重跑或改写历史 Analysis Result。

# 实现事实

- 当前 Prompt Taxonomy：`user_voice / brand_official / dealer_promotion / creator_marketing / industry_professional / media_information / unknown`。
- `语义相关性判断标准`：表格 + 高混淆场景 + 示例。
- `内容发声类型判断标准`：七类业务定义表格 + 两层证据 + 10 组高混淆场景 + 明确判断顺序 + 示例。
- `情感判断标准`：表格 + 高混淆场景 + 示例。
- `一级/二级标签判断标准`：原 9 个一级/39 个二级标签表格不改变；表格后的边界与示例统一命名为 `一级/二级标签高混淆场景` / `一级/二级标签示例`。
- Excel 当前七类使用新中文业务名称；历史 `other_organization` 仍显示 `其他机构传播`，未来未知机器值仍通过既有 fallback 原样展示。

# 两阶段 Review

## A1 需求符合性 Review

- 用户给出的七类中文业务语义已逐类落到 Prompt 表格；当前机器值保持稳定兼容部分并新增 `industry_professional`，当前 Taxonomy 不再包含 `other_organization`。
- “情感判断标准”“发声类型判断标准”以及语义相关性都已与一级/二级标签一样采用表格作为主定义；四类判断标准表格下均有高混淆场景与示例。
- 表格化过程中曾发现旧 `判断顺序` 和三组仍适用发声类型边界被整体替换，已在 Green 前恢复并适配新七类，因此不是以排版美化换取判断信息损失。
- 当前 sentiment 合法集合与 9 个一级/39 个二级标签 Taxonomy 没有改变；输出 JSON 字段和 relevant/irrelevant 结构语义没有改变。
- 用户要求的其他代码/文档影响已实际审计：只需要 Excel 展示别名和相关测试同步；其他正式文档继续指向 Prompt 唯一事实源，不应复制七类业务定义。
- 结论：无未解决严重/重要需求偏差。

## A2 代码质量 Review

- `other_organization` 只保留 Excel 历史展示兼容，未被映射成 `industry_professional`，不会改变旧 Analysis Result 的历史语义。
- `ContentVoiceType`/Runtime Validator/数据库结构边界继续复用上一 Change 已建立的 Taxonomy-driven 机制，没有重新引入 Python/DB/API 平行业务枚举。
- Excel `_VOICE_TYPE_DISPLAY_NAMES` 只承担中文展示；既有 fallback 对未来 Prompt 新值继续原样输出，不构成合法值白名单。
- generated Contract/OpenAPI/Orval drift 为零；没有 Schema/Migration/依赖/Runtime 变更。
- PR 最终 changed files 仅为 Prompt、Excel、Change 和 4 个直接相关 Unit 测试；三个一次性工具 Workflow 均已自删除，不在最终 diff 中。
- PR #258 没有未解决 Conversation comment 或 inline review thread；最终永久 CI 全绿。
- 结论：无未解决严重/重要代码质量 Finding。

# 代码与文档影响审计

- `ContentVoiceType` 已是结构字符串，合法值由 Prompt Runtime Taxonomy 校验，本次无需 Contract 修改。
- PostgreSQL 自 `20260828_0030` 起只约束 `voice_type` 非空结构，不复制业务枚举，本次无需 Migration。
- HTTP/OpenAPI/generated client 不维护具体 voice type enum，本次无需生成物变更。
- Analysis README、AI Appendix 与 Blueprint 只声明“Prompt 是唯一 Taxonomy 事实源”，没有复制当前七类定义；同步修改会重新制造第二份业务事实，因此不改。
- Excel Appendix 只描述“中文别名不是合法值白名单、未知新值原样输出”的机制；本次实现仍符合该机制，因此无需修改。
- 额外同步范围只包括两个旧 Unit 断言；没有发现其他生产代码或正式文档依赖旧七类列表/旧中文显示。

# 文档影响

业务判断文档只修改唯一事实源 `content_labeling_v3.md`。其他 README/Appendix/Blueprint 经审计不需要同步具体七类定义；Change 记录本轮变更原因、Review 和验证证据。

# 交付

- 分支：`feature/voice-type-prompt-table`
- PR：#258 `调整：更新发声类型定义并统一 Prompt 判断表格`
- 最终实现预审 HEAD：`7ffe6931c906105a142a71fb0e2e03d1c2490dd1`
- 合并：PR #258 已使用 expected HEAD 正常 squash merge，merge/main SHA 为 `66ccfb7f26d9a904ee1db626eb3e9acc10cac56d`；合并后 main 五个永久 workflow 全绿。
- 归档：本 Change 通过独立 docs-only PR 移入 `changes/archive/2026-08/`；归档只移动/补记 Change，不修改生产代码。
- 发布/部署：本任务不执行生产部署或历史数据重新打标。
