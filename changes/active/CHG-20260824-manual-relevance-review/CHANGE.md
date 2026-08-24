---
schema: rvc-change/v1
id: CHG-20260824-manual-relevance-review
title: AI 不相关内容人工复核与相关性覆盖
level: L3
status: ready_for_review
owner: aima
branch: feature/manual-relevance-review
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - content
  - frontend
  - contracts
  - database
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/analysis/relevance_review.py
  - backend/src/aima_ugc/modules/analysis/relevance_review_tables.py
  - backend/src/aima_ugc/adapters/persistence/postgres/relevance_reviews.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/modules/content/http.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/contracts/relevance_review.py
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/20260824_0025_manual_relevance_review.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/tests/voice-plaza.spec.ts
  - frontend/e2e/manual-relevance-review.spec.ts
  - frontend/e2e-fullstack/manual-relevance-review.spec.ts
  - tests/api/test_content_relevance_review_api.py
  - tests/integration/content/test_manual_relevance_review.py
  - tests/fullstack/seed_stage8f_manual_relevance_review.py
  - .github/workflows/stage8f-fullstack.yml
  - docs/blueprint/03_数据库与文件存储.md
  - docs/blueprint/04_后端任务API与前端.md
  - docs/blueprint/07_技术决策与实施门禁.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - backend/src/aima_ugc/modules/analysis/README.md
contracts:
  - HTTP OpenAPI
data_changes:
  - analysis_content_relevance_reviews
---

# 目标

让 AI 当前判定为 `irrelevant` 的 Content 在声音广场通过明确筛选可见，并支持单条或批量人工复核为“相关”。人工决定作为 Analysis Domain 的独立审计事实保存，不覆盖模型原始 `analysis_content_results`；业务默认列表、显式 `relevance` 查询、查询型 Analysis 目标和查询型 Export 统一按人工决定后的有效相关性处理。

# 成功标准

- [x] 声音广场提供“AI 相关性”筛选，可显式查看当前有效不相关内容。
- [x] AI 原始 `irrelevant` 结果继续完整保留；人工复核不 UPDATE/DELETE 原模型结果。
- [x] 单条与批量操作复用同一后端能力，把当前版本的业务有效相关性人工覆盖为 `relevant`。
- [x] 人工复核绑定 `content_id + content_version`，并通过 `analysis_result_id` 精确关联被复核 AI Result；Content 新版本产生后旧人工决定不自动套用。
- [x] 已人工纳入的内容从“不相关”筛选退出，并进入默认业务列表与 `relevance=relevant` 查询。
- [x] 查询型 Analysis Target 与查询型 Export 复用同一有效相关性语义，不建立平行业务过滤逻辑。
- [x] 重复提交同一当前版本人工复核幂等；批量请求任一目标不可复核时整体失败，不产生隐蔽部分成功。
- [x] OpenAPI、Orval generated client、前端 UI、数据库 Migration、测试与正式文档一致。

# 范围

- Analysis Domain 新增 `analysis_content_relevance_reviews` 事实表与 Owner Repository。
- 每条 review 保存 `content_id + content_version + analysis_result_id + decision + request_id + reviewed_at`；当前只允许 `decision=relevant`。
- Content Query 在查询层计算业务有效相关性：当前版本存在人工 `relevant` review 时优先采用人工决定，否则采用当前 AI relevance。
- 新增单条/批量共用 `POST /api/v1/content-relevance-reviews`。
- `ContentAnalysisResponse.relevance` 继续只表达模型原始判断；不新增会伪装成 AI 输出的 `effective_relevance` / `relevance_source` 公共字段。
- 声音广场增加相关性筛选、待复核说明、单条/批量“人工标记为相关”入口与成功/错误反馈。
- PostgreSQL Integration、HTTP Contract、Browser Mock、Real Full-stack、永久 CI 与正式文档同步。

# 非目标

- 本 Change 不实现“人工把 AI relevant 改成 irrelevant”。
- 不删除 Content，不向 `contents` 增加 `is_relevant` 或其他平行 Analysis 字段。
- 不修改 Prompt、Taxonomy、LLM Provider、AI 标签/情感规则。
- 不引入认证/Reviewer 用户身份；当前系统尚无正式 Authorization，因此不伪造 reviewer identity。
- 不新增异步 Review Job；人工复核是同步短事务。
- 不修改 TikHub Provider、采集策略或 Excel 入口的确定性关键词规则。
- 不为人工纳入项伪造情感或标签；原 AI `irrelevant` 的 `sentiment=null`、`labels=[]` 保持不变。

# 必须保持不变

- `analysis_content_results.relevance` 继续表示模型原始 Analysis 事实。
- AI 派生事实与人工覆盖都留在 Analysis Domain，不向 Content Owner 复制第二事实源。
- Content 稳定身份 `(platform, external_content_id)`、Current/Version/Metric 机制不变。
- 前端通过 Pydantic → OpenAPI → Orval generated Client 调用后端，不维护第二套 HTTP 类型。
- 查询型 Analysis/Export 继续复用 `PostgresContentQueryRepository.freeze_targets()`。

# L3 方案比较与已确认决策

## 方案 A：直接改写 `analysis_content_results.relevance`

优点：代码少。

缺点：模型原判被覆盖，无法回答“AI 当时判了什么”，并破坏 irrelevant 对 sentiment/labels 的结构约束和历史可复现性。

结论：不采用。

## 方案 B：给 `contents` 增加 `is_relevant`

优点：页面查询直观。

缺点：违反 Blueprint Decision G，把 Analysis 派生事实复制进 Content Owner，形成两个相关性事实源。

结论：不采用。

## 方案 C：Analysis 独立人工复核表 + Content Query 有效相关性投影

机制：保存当前 Content Version 和被复核 `analysis_result_id`；模型原始结果不变；查询层在当前版本有人工作为 `relevant` 时优先按人工决定参与业务集合。

优点：可审计、版本安全、符合 Owner 边界，默认列表、显式筛选、查询型 Analysis 和查询型 Export 自然复用同一语义。

结论：采用。用户于 2026-08-24 明确要求 AI 不相关内容可在前端查看并进行单条/批量人工纳入；实现遵循“保留 AI 原判、人工覆盖业务有效相关性”。

# 关键业务语义

1. `ContentAnalysisResponse.relevance` 始终返回模型原始结果，不因人工复核改写。
2. 业务有效相关性只在 Query Adapter 内计算，不新增公共 Analysis 字段：当前 `content_id + current_version` 存在人工作为 `relevant` 时为 relevant，否则采用当前 AI relevance。
3. 人工 review 只允许对当前版本、当前配置身份下最新 AI 原判为 `irrelevant` 的 Content 创建；同版本重复提交幂等。
4. Review 保存 `analysis_result_id`，可精确回答“人工纠正的是哪条 AI Result”。
5. 批量写操作按 Content ID 稳定顺序加锁，在一个事务中校验并提交；存在不可复核目标时整个请求返回 409。
6. Content Version 更新后旧 review 留作历史审计，但不参与新版本有效相关性。
7. Prompt/Model identity 后续变化时，既有人工 review 仍绑定同一 Content Version 作为人类业务判断；AI current/stale/pending 状态仍按原有身份规则解释。
8. 人工纳入只改变“是否进入相关业务集合”；不会把 AI 原始 irrelevant 伪造成带情感/标签的 relevant AI 结果。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 前端能看到 AI 判定不相关的数据并逐条复核 | user:2026-08-24-manual-relevance-review | satisfied | `VoicePlazaFilters.vue` + `VoicePlazaTable.vue`；Browser Mock 2 个 review E2E 全绿；Stage 8F run 32706100571 真实全栈通过。 |
| R2 | 支持某条数据人工改为相关 | user:2026-08-24-manual-relevance-review | satisfied | 行级“人工标记为相关”调用 `POST /api/v1/content-relevance-reviews`；CI run 32706100520 的 19/19 Playwright 通过。 |
| R3 | 支持批量选择后人工改为相关 | user:2026-08-24-manual-relevance-review | satisfied | 同一 Request Contract 支持 1—1000 个唯一 Content ID；批量 Browser E2E 与 PostgreSQL 原子性回归通过。 |
| R4 | AI 原始无关结果必须继续保留并可精确审计 | docs/blueprint/07_技术决策与实施门禁.md | satisfied | `analysis_content_results` 不被改写；review 保存 `analysis_result_id` FK；PostgreSQL integration 断言 raw relevance 仍为 irrelevant。 |
| R5 | AI/人工派生相关性不能写进 Content Owner | docs/blueprint/07_技术决策与实施门禁.md | satisfied | `analysis_content_relevance_reviews` owner=analysis；CI table ownership gate 通过，`contents` 无新增相关性字段。 |
| R6 | 人工纳入后默认业务列表与查询型下游按相关处理 | backend/src/aima_ugc/modules/analysis/README.md | satisfied | `PostgresContentQueryRepository` 统一计算有效相关性；Integration 验证默认/relevant/irrelevant、query Analysis 与 query Export；Stage 6 run 32706100514 全绿。 |
| R7 | 公共 API 改动必须走 Pydantic→OpenAPI→generated client | docs/blueprint/04_后端任务API与前端.md | satisfied | `contracts/relevance_review.py` → FastAPI → OpenAPI → Orval；CI run 32706100520 generated drift/compatibility 全通过。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | CI run 32706100520：Vitest 38/38；Playwright 19/19，其中单条/批量人工复核 2/2。 |
| Backend/API/PostgreSQL Integration | required | CI run 32706100520：backend unit 618、Contract 74、API 31 全通过；Stage 3A Migration/PG 全绿；Stage 6 run 32706100514 全绿。 |
| Contract / Generated Client | required | CI run 32706100520：OpenAPI/Orval 重新生成后无 diff，Contract compatibility 通过。 |
| Real Full-stack Golden Path | required | Stage 8F run 32706100571：真实 PostgreSQL、API、前端浏览器链完成 AI irrelevant → 筛出 → 人工纳入 → 默认列表恢复。 |
| Real Provider Probe | not_applicable | 本 Change 不修改 TikHub/LLM 外部协议、Mapper 或付费调用形状；无需真实 Provider Probe。 |
| Docs / Governance / Other | required | Blueprint 03/04/07、AI Appendix、Analysis README 已同步；主代码候选除 Completion Gate 外永久 workflow 均成功。 |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取当前 `AGENTS.md`、用户本轮决定、Blueprint 03/04/07、Analysis README 与 AI Appendix；确认人工覆盖仍必须留在 Analysis Domain，公共 AI relevance 保留原判。
- [x] change_coverage：按 R1—R7 重新从上游要求映射到 Schema/Repository/Query/API/generated client/UI/测试/文档；未发现缺失需求或未声明语义扩张。
- [x] reverse_audit：后端 review endpoint 有声音广场单条/批量入口；前端动作有真实 API/DB 支撑；默认列表、显式 relevance、query Analysis 和 query Export 都复用同一 Query Repository；新版本失效路径有 PostgreSQL 回归。
- [x] unresolved_cleared：Requirement 全部 satisfied；required Validation Matrix 均有当前候选证据；两阶段 Review 未发现未解决的 Serious/Important 问题，剩余边界均已列为非目标或回滚风险。

# 两阶段 Review

## A1：需求与契约 Review

- 前端“不相关”可见、逐条复核、批量复核均有 UI 与 Browser/Full-stack 证据。
- 写 API 与数据库事实一一对应；Request 唯一 ID 约束、1000 上限、409 原子冲突语义明确。
- 原 AI `relevance/sentiment/labels` 不因人工操作变化；人工结果单独保存并精确关联原 Analysis Result。
- Content Version 更新后 review 不继承；查询型下游统一复用有效相关性。
- 结论：R1—R7 均满足，无 Serious/Important 缺口。

## A2：实现与测试 Review

- Repository 按 Content ID 稳定顺序 `FOR UPDATE`，批量全量校验后单事务写入；没有外部 I/O 持锁。
- 同一 `content_id + content_version` 唯一约束与重复请求路径提供幂等；`analysis_result_id` 提供精确审计来源。
- Query 层只覆盖集合相关性，不伪造 AI 情感/标签；Export 当前没有相关性列，不产生“人工纳入却写 AI relevant”的假数据。
- Version 回归不再假设 Job 队列下一项类型，而是等待目标 Import Batch 自身成功，符合持久 Job 真实语义。
- Ruff、mypy、Contract drift、Migration drift、PostgreSQL round-trip、Browser Mock、Real Full-stack 均通过。
- 结论：未发现未解决的 Serious/Important 问题。

# 任务

- [x] 读取当前 main、规则、AI/Content/Frontend/Contract/Migration 事实并完成方案比较
- [x] 清理已经合并但残留 active 的 `CHG-20260824-multi-keyword-pack-entrypoints`
- [x] 建立 Red 测试并取得缺少 review API 的实际 404 失败证据
- [x] 新增 Analysis 人工复核 Schema/Migration/Repository
- [x] 实现统一有效相关性查询与 HTTP Contract/API
- [x] 由正式生成链同步 OpenAPI/Orval client
- [x] 完成声音广场相关性筛选、单条/批量人工复核 UI
- [x] 同步 Blueprint 03/04/07、AI Appendix 与 Analysis README
- [x] 完成 Browser、API、PostgreSQL、Stage 6、Stage 8F 与永久 CI 验证
- [x] 完成 Completion Audit 与两阶段 Review

# 验证结果

当前代码候选 `ca13bb69208079105f4c8ac0779ba9dadd83a42a` 与当时最新 `main` `db749e354b1cf216be9d670a142b825d34e72757` 的 synthetic merge 已用于永久 PR Workflow。

- CI `32706100520`：success；618 unit、74 Contract、31 API、38 Vitest、19 Playwright；Ruff、mypy、OpenAPI/Orval drift、compatibility、Wheel、architecture、table ownership、Secret/Docs 全通过。
- Stage 6 `32706100514`：success；Unit/Quality/PostgreSQL integration、历史 revision→head 与 base round-trip 全通过。
- Stage 8F `32706100571`：success；真实 PostgreSQL/API/Worker/浏览器 Golden Path 通过。
- Internal V1-A `32706100512`、Windows Compose `32706100511`、Stage 4/5/7 与 Audit workflows 均成功。
- 本次 Change 文档更新为 `ready_for_review` 后将由新的最终 HEAD 重新运行 Change Completion Gate 和全部永久 Workflow；交付结论只采用该最终 HEAD 的最新证据。

# 文档影响

- Blueprint 03：Analysis 表清单增加人工 relevance review 表，明确 Analysis Owner、版本绑定与 `analysis_result_id` 审计来源。
- Blueprint 04：新增 review endpoint、声音广场 UI 与查询层有效相关性语义；公共 AI Response 继续表达原模型结果。
- Blueprint 07：Decision G 固化“人工 Analysis 覆盖也是 Analysis Domain，AI 原始结果不可改写”。
- AI Appendix/README：记录人工 review、版本绑定、下游查询语义和精确 Analysis Result 来源。

# Migration、部署、回滚与风险

- 新增 Alembic Migration `20260824_0025_manual_relevance_review.py`，基于 `20260822_0024`；空库 upgrade、drift、历史 revision 与 base round-trip 已验证。
- 部署顺序：先执行 Migration，再部署同时包含新 API 与前端的应用版本；旧代码面对新增表没有写入行为。
- 应用回滚前应停止使用新 review API。Migration downgrade 会删除人工 review 表；模型原始 Analysis Result 与 Content 不受影响，但人工复核历史会丢失，因此生产 downgrade 前必须备份或明确接受该数据损失。
- 批量 review 上限固定 1000，禁止无限 `IN`；批量失败为全事务回滚。
- 当前没有 Authorization，因此只保存 `request_id/reviewed_at` 而不伪造 reviewer user；正式 reviewer identity 需等认证/授权阶段。
- 当前只支持 `irrelevant → relevant`，不提供撤销或 `relevant → irrelevant`；属于明确非目标。

# 交付

- 分支：`feature/manual-relevance-review`
- PR：#202 `增加 AI 不相关内容人工复核`
- 当前交付目标：通过最终 Completion Gate 后将 Draft PR 转 Ready。
- 合并：未经用户明确授权，不合并 `main`。
