---
schema: rvc-change/v1
id: "CHG-20260828-voice-type-taxonomy"
title: "统一 voice_type 为 Prompt Taxonomy 驱动"
level: L3
status: in_progress
owner: "chatgpt"
branch: "feature/voice-type-taxonomy"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "analysis"
  - "contracts"
  - "database"
  - "generated-client"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc/modules/analysis/"
  - "backend/src/aima_ugc/contracts/analysis/"
  - "backend/src/aima_ugc/modules/analysis/tables.py"
  - "migrations/versions/"
  - "contracts/"
  - "frontend/src/generated/api/"
  - "tests/unit/analysis/"
  - "tests/integration/database/"
  - "docs/appendix/07_AI舆情打标与分析实现.md"
contracts:
  - "ContentVoiceType"
  - "ContentLabelAnalysisV3"
  - "ContentAnalysisResponse"
data_changes:
  - "analysis_content_results.voice_type"
---

# 目标

把 `voice_type` 的合法值集合统一交给 `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md` 中的机器可读 Taxonomy 管理，使它与 `sentiments`、一级/二级 `labels` 使用同一机制：输出 JSON 结构仍由代码固定，业务可选值由 Prompt Taxonomy 在运行时解析并由 `RuntimeTaxonomyValidator` 严格校验。

同时保留 Prompt 中完整的自然语言判断经验：主体证据、表达目的证据、`七类边界与高混淆场景`、具体正反例和后续用户补充的示例继续用于教模型“怎么判”，不压缩进机器 JSON，也不因本次结构调整删除。

# 成功标准

- [ ] 机器 Taxonomy 增加 `voice_types`，当前 7 个机器值保持不变；Taxonomy schema 对新增字段显式版本化。
- [ ] `PromptTaxonomyLoader` 解析、清洗、去重并把 `voice_types` 纳入 `taxonomy_sha256`；非法/重复值在调用 LLM 前 fail closed。
- [ ] `RuntimeTaxonomyValidator` 像校验 `sentiment` 一样校验 `voice_type` membership，并提供稳定 `unknown_voice_type` Validation Retry 错误码。
- [ ] Python Contract 不再复制当前 7 类为 `Literal`；只保留字符串结构约束，新增 Prompt voice type 不要求改 Python。
- [ ] PostgreSQL 不再复制当前 7 类为业务枚举 `CHECK`；只保留非空/结构约束，新增 Prompt voice type 不要求 Schema Migration。
- [ ] 新 Alembic Migration 保留已有数据原值，按“先扩数据库约束、再部署代码”可兼容升级；降级遇到旧 schema 不支持的新值时 fail closed，不静默改数据。
- [ ] Prompt 的 `内容发声类型判断标准`、`七类边界与高混淆场景` 和示例完整保留；以后可继续在同一 Prompt 增加类别定义和学习示例。
- [ ] 当前 7 类的机器值与业务判断语义不改变；历史 Analysis Result 不回写、不重分类，继续由既有 `prompt_sha256/taxonomy_sha256` 追溯当时规则。
- [ ] OpenAPI / generated TypeScript Client 由正式生成流程同步；现有字段名、JSON 结构和接口路径不变。
- [ ] 目标 Unit、PostgreSQL Integration、Contract/generated drift、质量门禁和完整 PR CI 取得本轮新鲜绿色证据。

# 范围

- 扩展当前 `content_labeling_v3.md` 机器 Taxonomy 增加 `voice_types`。
- 保留并只做必要措辞调整的 voice type 自然语言定义、边界、混淆场景和示例。
- 扩展 `PromptTaxonomy` / `PromptTaxonomyLoader`。
- 把模型响应 `voice_type` 的合法性校验移入 `RuntimeTaxonomyValidator`。
- 把 `ContentVoiceType` 从固定业务 Literal 收敛为受长度约束的字符串结构类型。
- 把 `analysis_content_results.voice_type` 从固定七值数据库 CHECK 收敛为字符串结构约束，并新增 Alembic Migration。
- 同步 Analysis README / Appendix 和正式 generated contracts/client。
- 增加运行时 Taxonomy、Contract、数据库约束回归测试。

# 非目标

- 不改变 `relevance` 的 `relevant/irrelevant` 固定结构语义。
- 不修改当前 7 个 voice type 的名称、定义或分类边界。
- 不删除或简化 `七类边界与高混淆场景`、现有示例。
- 不新增独立 Taxonomy 数据库表、配置中心或前端 Taxonomy API。
- 不在本次给声音广场新增 voice type 筛选/展示 UI。
- 不重跑历史 AI 打标，不批量迁移历史结果值。
- 不升级 Python、Node、依赖或框架。

# 必须保持不变

- 模型输出字段仍固定为 `item_no/relevance/voice_type/sentiment/labels`。
- `relevance=relevant` 时仍必须有合法 sentiment 和至少一个合法标签对；`irrelevant` 时仍必须 `sentiment=null, labels=[]`。
- Prompt Markdown 继续是 AI taxonomy/判断规则唯一业务事实源，不新增 Python/DB/前端平行业务列表。
- Analysis Result 的 Prompt/Taxonomy/Model/Input 审计身份和 Current/History 选择语义保持不变。
- PostgreSQL 仍是唯一业务事实库，Schema 演进只通过 SQLAlchemy tables + Alembic Migration。
- 前端 generated client 继续由 Pydantic/OpenAPI → Orval 生成，禁止手写第二套类型。

# 关键决策与方案比较

## 方案 A：运行时 Prompt Taxonomy 驱动（采用）

- Prompt JSON 维护 `sentiments + voice_types + labels`。
- Python/Pydantic 只固定字段结构和字符串边界。
- Runtime Validator 对三个业务分类维度做 membership / 父子关系校验。
- PostgreSQL 只约束结构，不复制业务枚举。

优点：与现有 sentiment/labels 机制一致；以后增删 voice type 只需改同一 Prompt 的机器列表与自然语言判断/示例；无需普通 Schema Migration。风险：HTTP OpenAPI 不再暴露固定 voice type enum，但这正是允许运行时 Taxonomy 演进所需的兼容边界。

## 方案 B：从 Prompt 在构建期生成 Python Enum 和数据库 CHECK（不采用）

能减少手工复制，但每次分类变化仍会改变公共 enum 和数据库 Schema，并要求生成/Migration；没有达到“后续只改 Prompt”的目标。

## 方案 C：新增数据库 Taxonomy 配置表（不采用）

可做运行时管理后台，但引入新的持久化 Owner、版本发布和配置一致性问题；当前唯一事实源已明确是 Prompt Markdown，本次没有后台动态配置需求，复杂度无证据支持。

# Migration / 部署 / 回滚

- Upgrade：先删除 `voice_type` 固定七值 CHECK，再增加非空/结构 CHECK；不修改任何现有行值。
- 部署顺序：Migration 可先于新代码执行；旧代码只写原 7 类，仍满足放宽后的数据库约束。随后部署新代码。
- 代码回滚：先回滚应用代码仍可读取/写入原 7 类；若新 Prompt 从未引入新值，可再安全 downgrade Migration。
- Migration downgrade：恢复 0029 之前的七值约束；如果数据库已经出现旧约束不支持的新 voice type，明确失败并列出阻塞值，不删除、不映射、不篡改数据。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | `voice_type` 与 sentiment/labels 一样由同一 Prompt 机器 Taxonomy 管理合法值，后续增删类别不再改 Python/DB 业务枚举 | user:统一发声类型为提示词驱动 | not_satisfied | Red/Green 实现与测试待完成 |
| R2 | `内容发声类型判断标准` 保持自然语言形式，可在 Prompt 中增加类别和定义 | user:判断标准继续放提示词 | not_satisfied | Prompt 与文档修改待完成 |
| R3 | `七类边界与高混淆场景` 必须保留，并保留/允许继续增加 AI 学习示例 | user:保留高混淆场景和示例 | not_satisfied | 回归测试已计划覆盖，Prompt 实现待完成 |
| R4 | 当前 7 类机器值和现有业务语义不改变，历史结果不被静默重分类 | backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md | not_satisfied | Prompt/迁移/历史兼容复核待完成 |
| R5 | AI taxonomy 不得在 Python、数据库和前端维护平行业务列表 | AGENTS.md | not_satisfied | Python/DB 硬编码移除与 generated contract 待完成 |
| R6 | Schema 变化必须通过 SQLAlchemy + Alembic，并用真实 PostgreSQL 验证 | AGENTS.md | not_satisfied | Migration 与 PostgreSQL Integration 待完成 |
| R7 | generated client 必须由正式 Pydantic/OpenAPI/Orval 流程同步，不手写第二套 Contract | docs/blueprint/07_技术决策与实施门禁.md | not_satisfied | CI generation drift 证据待完成 |
| R8 | 正常 PR/CI 后合并并推送到 `main` | user:改完推送主分支 | not_satisfied | PR/CI/merge 证据待完成 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Prompt Loader 解析/去重/hash、动态新增 voice type、unknown_voice_type Validation Retry、自然语言边界/示例保留 |
| 接口 / Contract | required | ContentVoiceType 从固定 enum 放宽为结构字符串后，Pydantic/OpenAPI/generated client 通过正式生成与 compatibility/drift 检查 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 18 执行 Alembic head，确认固定七值 CHECK 已移除且结构约束存在；Migration 生命周期保持数据安全 |
| 用户 / Workflow Acceptance | not_applicable | 本次不改变现有页面入口、按钮、状态或可见结果，只放宽后端 Taxonomy 可演进边界 |
| 跨组件 Golden Path | not_applicable | 不改变 API 路径、Job 链、Worker 装配或前端业务行为；Contract + Backend/PostgreSQL 证据直接覆盖独立风险 |
| External Dependency / Provider Probe | not_applicable | 不修改 TikHub/LLM 网络协议或真实 Provider 字段，不需要付费外部 Probe |
| Build / Package / Runtime | required | 完整 CI 的 Python type/lint、wheel、frontend type/build 与 source startup smoke |
| Docs / Governance / Other | required | Change Completion Gate、architecture/ownership/secret/docs gates、Analysis README/Appendix 同步 |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取本轮用户决定、AGENTS、当前 Prompt、Analysis README/Appendix 和机器事实。
- [ ] change_coverage：逐项核对“只改 Prompt 即可演进 + 自然语言判断/边界/示例保留 + 当前 7 类不变 + DB/Contract 去平行枚举”。
- [ ] reverse_audit：执行 Prompt → Loader → Validator → Contract → Repository/DB → API/generated consumer 的正反向审计，并复核 Migration upgrade/downgrade。
- [ ] unresolved_cleared：Ready 前清零 `not_satisfied`，所有不适用项有事实依据。

# 任务

- [x] 从最新 `main` 恢复 AGENTS/Coding Skill/AI 实现/Contract/Schema/Migration/测试事实。
- [x] 创建 `feature/voice-type-taxonomy` 分支和 L3 Change。
- [ ] Red：新增动态 voice type、非法 voice type、Contract 去固定枚举、DB 去固定七值约束的失败测试并取得失败证据。
- [ ] Green：扩展 Prompt Taxonomy 与 Loader/Validator，保留自然语言边界和示例。
- [ ] Green：移除 Python 固定七值 Literal，保留字符串结构约束。
- [ ] Green：更新 tables.py + 新 Alembic Migration，保留数据与安全 downgrade。
- [ ] 同步 generated contracts/client 与 Analysis README/Appendix。
- [ ] 运行目标测试、PostgreSQL Integration、Contract、质量门禁和完整 CI。
- [ ] 执行 Completion Audit、A1/A2 与代码质量 Review，解决严重/重要 Finding。
- [ ] Change 进入 ready_for_review，PR 正常合并 `main`；合并后验证 main push CI。
- [ ] 单独归档 Change。

# 验证

## Red 证据

待 PR/Runner 实际运行后记录。

## Green / 回归证据

待实现后记录本轮实际命令、退出码、失败数和 GitHub Actions run。

# 文档影响

- `backend/src/aima_ugc/modules/analysis/README.md`：从“改 voice_type 必须改 Prompt+Contract+DB+Migration”更新为 Prompt Taxonomy 驱动。
- `docs/appendix/07_AI舆情打标与分析实现.md`：同步 Loader/Validator/DB 约束与后续修改入口。
- 不复制完整 7 类列表到文档；业务定义、边界和示例继续只在当前 Prompt 保存。

# 交付

- 分支：`feature/voice-type-taxonomy`
- PR：待创建
- 合并：待 CI/Review 后正常合并
- 发布/部署：本任务不执行生产部署
