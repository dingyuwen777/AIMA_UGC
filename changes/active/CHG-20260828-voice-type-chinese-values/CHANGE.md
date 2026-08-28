---
schema: rvc-change/v1
id: "CHG-20260828-voice-type-chinese-values"
title: "发声类型直接使用中文业务名称作为机器值"
level: L3
status: ready_for_review
owner: "chatgpt"
branch: "feature/voice-type-chinese-values"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "analysis"
  - "export"
  - "docs"
  - "tests"
affected_paths:
  - "backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md"
  - "backend/src/aima_ugc/modules/analysis/README.md"
  - "backend/src/aima_ugc/platform/export/excel.py"
  - "README.md"
  - "docs/01_代码结构与修改导航.md"
  - "docs/appendix/01_PostgreSQL查询与调试实战.md"
  - "docs/appendix/06_Excel统一数据导出与离线调试.md"
  - "docs/appendix/07_AI舆情打标与分析实现.md"
  - "docs/appendix/13_AI大规模打标与成本优化方案.md"
  - "docs/blueprint/03_数据库与文件存储.md"
  - "docs/blueprint/07_技术决策与实施门禁.md"
  - "frontend/tests"
  - "frontend/e2e"
  - "scripts/performance"
  - "tests"
contracts: []
data_changes:
  - "analysis_content_results.voice_type 新写入值语义"
---

# 目标

将当前 `voice_type` 与 sentiment、一级/二级标签统一：合法机器值直接使用中文业务名称，不再维护英文稳定 ID 或英文→中文展示映射。

当前七类合法机器值：

```text
真实用户发声
品牌官方发声
门店经销商发声
营销推广发声
行业从业发声
媒体机构发声
无法判断
```

用户明确批准破坏性兼容策略：不需要旧英文 `voice_type` 的历史兼容读取。本次不回填、不迁移、不翻译已有数据库历史值，也不保留 `user_voice -> 真实用户发声` 等专门兼容映射。

# 已确认方案

采用“中文业务名称直接作为合法机器值”。不采用英文 ID + 中文展示名，也不采用 `value + name` 双层对象结构。

原因：当前 sentiment 与一级/二级标签已经直接使用中文业务值；`ContentVoiceType`、PostgreSQL、HTTP/OpenAPI 都只约束字符串结构，具体业务集合由 Prompt Taxonomy + RuntimeTaxonomyValidator 驱动。直接使用中文可以删除重复映射，同时保持现有 Taxonomy-driven 架构。

# 成功标准

- [x] Prompt `voice_types` 只包含七个中文业务名称，不包含当前英文机器 ID。
- [x] 发声类型判断表删除“机器值”列，正文、高混淆场景、示例直接使用中文分类名称。
- [x] 新 LLM 输出、RuntimeTaxonomyValidator membership、`ContentLabelAnalysisV3.voice_type` 新写入语义均直接使用中文业务名称。
- [x] Excel 删除当前/历史英文 `voice_type` 中文展示映射，直接输出传入字符串。
- [x] V1/V2 无 `voice_type` 的 Excel 投影缺省值直接使用 `无法判断`，不再依赖英文 `unknown`。
- [x] 不保留旧英文值兼容读取/映射，不新增数据 backfill 或 Alembic Migration；历史 Migration 保持原样。
- [x] README、Analysis README、Blueprint、AI/Excel/PostgreSQL Appendix 及当前 Fixture/Mock/性能脚本已同步当前中文值事实。
- [x] Pydantic/HTTP Contract、OpenAPI、generated client 结构不变，正式生成链 drift/compatibility 全绿。
- [x] 第一轮 Green HEAD 已通过 CI、PostgreSQL、Full-stack、Runtime、Tooling；Ready HEAD 必须重新通过全部永久门禁后才允许合并。

# 范围与非目标

范围：修改 Prompt、删除 Excel 英文展示/兼容映射、同步当前测试/Fixture/Frontend Mock/性能脚本和实时文档，并全仓审计旧英文值。

非目标：不改 `voice_type` 字段名/V3 JSON 结构；不改成 enum 或对象；不改 PostgreSQL 列类型；不新增 Migration；不迁移历史英文数据；不新增兼容层；不批量重跑历史 AI；不改 sentiment/标签集合；不新增前端功能。

# 兼容、Migration、部署与回滚

- 新 Analysis Result 的 `voice_type` 使用中文值。
- 旧英文历史值不属于当前 Taxonomy，不提供专门兼容读取或展示映射；通用字符串路径遇到旧值时只保留原始字符串。
- PostgreSQL `voice_type` 已是通用非空字符串，不需要 Schema Migration；不做 backfill/update。
- 历史 Alembic Migration 的旧英文 CHECK 保持原样，Green PostgreSQL Integration 已证明空库升级与历史 Migration compatibility 正常。
- `taxonomy_sha256` / `prompt_sha256` 继续区分新旧规则版本。
- 无 Schema 依赖，应用代码与 Prompt 同版本部署即可；本任务不执行生产部署。
- 回滚到上一应用/Prompt 版本即可，不需要数据库 downgrade，也不改写已经产生的中文值。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 所有当前发声类型直接使用中文业务名称作为合法机器值，不维护英文机器 ID | user:2026-08-28-中文voice-type机器值 | satisfied | Prompt `voice_types` 与判断示例已切为七个中文值；动态新增中文类型测试通过；Unit 705 passed |
| R2 | 不需要旧英文 `voice_type` 的历史兼容读取/映射 | user:2026-08-28-删除英文历史兼容 | satisfied | Excel `_VOICE_TYPE_DISPLAY_NAMES` / `_voice_type_display_name()` 已删除；测试证明 `user_voice` / `other_organization` 只原样输出，不翻译 |
| R3 | 与 sentiment、一级/二级标签保持同一种 Taxonomy 维护模式 | user:2026-08-28-统一Taxonomy模式 | satisfied | Prompt 机器 Taxonomy 直接保存中文字符串，发声类型表只保留“发声类型/核心定义/说明”；Contract/DB 不复制业务集合 |
| R4 | 修改所有真实受影响代码/测试/文档，不假设只改 Prompt | AGENTS.md | satisfied | 两轮 Runner 扫描确认生产额外影响为 Excel；收口扫描发现 10 处当前 `voice_type="unknown"` Fixture 并已改为“无法判断”；实时 README/Blueprint/Appendix、Frontend/Full-stack/Tests/性能 Fixture 已同步；历史 Migration 未改 |
| R5 | 正常推送并合并 `main`，不绕过仓库门禁 | user:2026-08-28-推送主分支 | explicitly_deferred | Draft PR #263 已建立；实际 Ready、squash merge、main push CI 必须在本 Change Ready Gate 与同一 Ready HEAD 全部永久 CI 成功后执行，并在独立归档 PR 中补最终证据 |

# Validation Matrix

| Layer | Required | Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | CI `33160412433`：Unit 705 passed；中文 Taxonomy、英文值不再合法、Excel 原样输出、V1/V2“无法判断”均有回归测试 |
| 接口 / Contract | required | CI `33160412433`：Contract 92 passed、API 38 passed；generate + Orval + drift + compatibility success |
| 集成 / Persistence / Runtime Dependency | required | CI `33160412433` PostgreSQL Integration success：empty DB upgrade、historical migration compatibility、Platform/Database/Job/Collection/Content/Ingestion 全部通过 |
| 用户 / Workflow Acceptance | required | Full-stack `33160412417` success；Frontend Vitest 50 passed、Playwright 31 passed |
| 跨组件 Golden Path | required | Full-stack `33160412417` 与 Runtime `33160412438` success |
| 外部依赖 Probe | not_applicable | 不修改 LLM HTTP 协议、Provider 字段或外部服务能力，无需真实付费 Probe |
| Build / Package / Runtime | required | CI：Ruff 529 files、mypy 254 source files、Wheel、frontend lint/type/build success；Tooling `33160412421`、Runtime `33160412438` success |
| Docs / Governance / Other | required | architecture/table ownership、Secret/docs success；A1/A2 Review、Completion Audit 已完成；Ready HEAD 必须重新通过 Change Completion Gate |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取目标分支 `AGENTS.md`、Coding/Review 规则、最新 `main=d86015f21b1e2db994519705a1350c6df623dd23`、本轮用户“全部中文机器值 + 不要旧英文兼容”决定、当前 Prompt/Analysis README/AI/Excel Appendix。
- [x] change_coverage：独立从用户上游决定重建完成定义，逐项核对中文七值、删除机器值列、删除 Excel 翻译层、V1/V2 缺省、实时文档/Fixture 同步、无 Migration/backfill、正常合并 main；R1-R4 已有 Green 证据。
- [x] reverse_audit：沿 `Prompt -> Loader/Validator -> ContentLabelAnalysisV3 -> PostgreSQL/API -> Frontend Fixture/Full-stack -> Excel` 双向审计；具体合法集合只存在 Prompt，其他运行边界使用通用字符串；Excel 不再解释值。旧英文仅允许出现在历史 Migration/Archive、当前 Change 的迁移说明，以及证明“不兼容翻译”的测试输入中。
- [x] unresolved_cleared：PR #263 无 Conversation comment、无 inline review thread、无 submitted review；A1/A2 无严重/重要 Finding。R1-R4 `satisfied`，实现范围 `not_satisfied` 清零；R5 的延期仅用于遵守 Ready→merge→main 验证顺序。

# Red / Green 证据

## Red

- Red HEAD `7037b90d5acc518f577ff6f98c10488ec9154a82`；CI `33159875378` / Repository Quality `98811507063`。
- generated drift、Ruff、mypy 先成功；Unit `4 failed, 701 passed`。
- 失败精确来自：旧英文 Prompt Taxonomy、Prompt 仍有“机器值”列、Excel 仍翻译 `user_voice`、Excel 仍翻译 `other_organization`。

## Green

- Green HEAD `2cdb211e734571e84be4e5ff7d665186e26e2e67`；CI merge ref 实际将该 HEAD 合到当时最新 `main=d86015f21b1e2db994519705a1350c6df623dd23` 后验证。
- CI `33160412433` success / CI Gate success；Repository Quality `98813324795`：Ruff 529 files、mypy 254 source files、Unit 705、Contract 92、API 38、Wheel、architecture/ownership、Secret/docs、Frontend Vitest 50、build、Playwright 31 全部 success。
- PostgreSQL `98813324875` success，包含历史 Migration compatibility。
- Full-stack `33160412417`、Runtime `33160412438`、Tooling `33160412421` 均 success。
- Change Gate `33160412435` 的 completion tests success，但当时 Change 为 `in_progress`，changed-PR readiness 按设计失败。
- 首个 Ready HEAD `655dc22acdbc4a28501444e5ece690a13370eef7` 的 Change Gate `33160926631` 暴露 R4 Source 拼接格式错误：`AGENTS.md + user:...` 被机器视为不存在路径。业务实现无变更，本提交仅修正 R4 Source 为真实仓库文件 `AGENTS.md`。

# 两阶段 Review

## A1 需求符合性

- 七个当前合法 `voice_type` 已全部使用中文业务名称；Prompt 不再维护英文机器 ID 或“推荐名称→机器值”双层。
- “不需要旧英文历史兼容读取”已落实：无英文→中文映射、无数据回填、无兼容 Migration；旧英文经过通用字符串导出时保持原值。
- sentiment 与一级/二级标签集合未改变，`voice_type` 字段结构未改变。
- 所有实时受影响文档和当前 Fixture 已同步，历史 Migration 保持历史事实。
- 无未解决严重/重要需求偏差。

## A2 代码质量

- 实现只删除重复映射并修改业务配置/Fixture，没有新增第二套 Taxonomy、兼容层或无关抽象。
- Pydantic/HTTP/OpenAPI/PostgreSQL 保持通用字符串边界，不把七类硬编码回程序或 Schema。
- Excel 直接透传 `analysis.voice_type`，V1/V2 缺省显式使用 `无法判断`。
- generated drift 为零；无依赖升级、无 Schema/Migration 变更、无临时 Workflow 残留。
- PR 无未解决 comment/thread/review；业务 Green 永久 CI 全绿。
- 无未解决严重/重要代码质量 Finding。

# 任务

- [x] 恢复最新仓库事实并建立 L3 Change/Validation Matrix。
- [x] 全仓审计旧英文 voice type 依赖。
- [x] Red：先提交失败测试并取得有效业务 Red。
- [x] Green：更新 Prompt、Excel、实时文档、当前测试/Fixture/Frontend/Full-stack/性能脚本。
- [x] 收口扫描修正 10 处当前 `voice_type="unknown"` Fixture；历史 Migration 保持不改。
- [x] 第一轮 Green 完整永久 CI / PostgreSQL / Full-stack / Runtime / Tooling 通过。
- [x] 执行 A1/A2 Review、PR unresolved 审计和 Completion Audit。
- [x] 修正 Ready Check 唯一的 R4 Source 结构错误。
- [ ] 当前 Ready HEAD 的 Change Gate / CI / Runtime / Full-stack / Tooling 全绿。
- [ ] PR #263 转 Ready 后使用 expected HEAD 正常 squash merge `main`，验证 main push CI。
- [ ] 独立 docs-only PR 归档 Change。

# Git / 交付

- 分支：`feature/voice-type-chinese-values`
- Draft PR：#263 `调整：发声类型直接使用中文业务机器值`
- 合并：仅在最终 Ready HEAD 五个永久门禁全部成功后执行 squash merge
- 生产部署：本任务不执行
