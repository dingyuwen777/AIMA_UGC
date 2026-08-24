---
schema: rvc-change/v1
id: CHG-20260824-manual-relevance-review
title: AI 不相关内容人工复核与相关性覆盖
level: L3
status: in_progress
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
affected_paths:
  - backend/src/aima_ugc/modules/analysis/tables.py
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/modules/content/query.py
  - backend/src/aima_ugc/modules/content/http.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/contracts/http.py
  - migrations/versions/20260824_0025_manual_relevance_review.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/voice-plaza/
  - frontend/e2e/voice-plaza.spec.ts
  - tests/integration/content/test_stage8d_voice_plaza_runtime.py
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

让 AI 当前判定为 `irrelevant` 的 Content 在声音广场通过明确筛选可见，并支持单条或批量人工复核为“相关”。人工决定必须作为 Analysis Domain 的独立审计事实保存，不能覆盖模型原始 `analysis_content_results`，同时业务默认列表、查询型 Analysis 目标和查询型 Export 应按人工决定后的有效相关性处理。

# 成功标准

- [ ] 声音广场提供“AI 相关性”筛选，可显式查看当前有效不相关内容。
- [ ] AI 原始 `irrelevant` 结果继续完整保留；人工复核不得 UPDATE/DELETE 原模型结果。
- [ ] 单条与批量操作复用同一后端能力，把当前版本的有效相关性人工覆盖为 `relevant`。
- [ ] 人工复核绑定 `content_id + content_version`；Content 新版本产生后旧人工决定不自动套用。
- [ ] 已人工纳入的内容从“不相关”筛选退出，并进入默认业务列表/`relevance=relevant` 查询。
- [ ] 查询型 Analysis Target 与查询型 Export 复用同一有效相关性语义，不建立平行业务过滤逻辑。
- [ ] 重复提交同一当前版本人工复核幂等；批量请求不产生部分成功的隐蔽状态。
- [ ] OpenAPI、generated client、前端 UI、数据库 Migration、测试与正式文档一致。

# 范围

- Analysis Domain 新增人工相关性复核事实表与 Owner Repository 写入。
- Content Query 增加人工复核投影，统一计算 effective relevance。
- 新增单条/批量共用 HTTP review endpoint。
- `ContentAnalysisResponse` 增加审计友好的有效相关性/人工复核投影，同时保留 `relevance` 为模型原始结果。
- 声音广场增加相关性筛选、单条和批量“人工标记为相关”入口与状态反馈。
- PostgreSQL Integration、HTTP Contract、Browser Mock、Full-stack 相关回归以及正式文档同步。

# 非目标

- 本 Change 不实现“人工把 AI relevant 改成 irrelevant”。
- 不删除 Content，不把人工复核写进 `contents`。
- 不修改 Prompt、Taxonomy、LLM Provider、AI 标签/情感规则。
- 不引入认证/Reviewer 用户身份；当前系统尚无正式 Authorization，不能伪造 reviewer identity。
- 不新增异步 Job；人工复核是短事务写操作。
- 不修改 TikHub Provider、采集策略或 Excel 规则过滤人工复核。

# 必须保持不变

- `analysis_content_results.relevance` 继续表示模型原始 Analysis 事实。
- AI 派生事实与人工分析覆盖都留在 Analysis Domain，不向 `contents` 增加平行 `is_relevant` 字段。
- Content 稳定身份 `(platform, external_content_id)`、Current/Version/Metric 机制不变。
- 前端通过 Pydantic → OpenAPI → Orval generated Client 调用后端，不维护第二套 HTTP 类型。
- 查询型 Analysis/Export 继续复用 `PostgresContentQueryRepository.freeze_targets()`。

# L3 方案比较与已确认决策

## 方案 A：直接改写 `analysis_content_results.relevance`

优点：代码少。

缺点：模型原判被覆盖，无法回答“AI 当时为什么判为不相关”，还会破坏 irrelevant 对 sentiment/labels 的结构约束与历史可复现性。

结论：不采用。

## 方案 B：给 `contents` 增加 `is_relevant`

优点：页面查询直观。

缺点：违反 Blueprint Decision G，把 Analysis 派生事实复制进 Content Owner，形成两个相关性事实源。

结论：不采用。

## 方案 C：Analysis 独立人工复核表 + Content Query 有效相关性投影

机制：保存 `content_id + content_version + decision=relevant + reviewed_at`；模型原始结果不变；查询层将当前版本人工决定优先于 AI relevance 计算 effective relevance。

优点：可审计、版本安全、符合 Owner 边界，默认列表/查询型 Analysis/Export 可以自然复用同一语义。

结论：采用。用户于 2026-08-24 明确要求 AI 不相关内容可人工单条/批量改为相关；本 Change 采用“保留 AI 原判、人工覆盖业务有效相关性”的实现。

# 关键业务语义

1. `analysis.relevance`：模型原始结果，永不因人工复核被改写。
2. `analysis.effective_relevance`：业务当前使用的相关性；同一 Content Version 存在人工 review 时为 `relevant`，否则等于当前 AI relevance；没有当前 AI/人工结果时为 null。
3. `analysis.relevance_source`：`ai` / `manual_review` / null，用于前端解释有效结果来源。
4. 人工 review 只允许对当前版本、当前 AI 原判为 `irrelevant` 的 Content 创建；已经 review 的同版本重复提交幂等。
5. 批量写操作在一个事务中验证并提交；存在不可复核目标时整个请求失败，避免用户选择 N 条却只悄悄成功一部分。
6. Content Version 更新后旧 review 留作历史审计，但不参与新版本 effective relevance。
7. Prompt/Model identity 变化导致当前 AI stale 时，只要 Content Version 未变，人工 review 仍是有效的人类业务判断；Raw AI status 仍按现有 current/stale/pending 规则展示。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 前端能看到 AI 判定不相关的数据并逐条复核 | user:2026-08-24-manual-relevance-review | not_satisfied | 待实现并由 Browser/Full-stack 验证 |
| R2 | 支持某条数据人工改为相关 | user:2026-08-24-manual-relevance-review | not_satisfied | 待实现 API + Repository + UI |
| R3 | 支持批量选择后人工改为相关 | user:2026-08-24-manual-relevance-review | not_satisfied | 待实现同一批量 Contract + UI |
| R4 | AI 原始无关结果必须继续保留可审计 | docs/blueprint/07_技术决策与实施门禁.md | not_satisfied | 待通过 DB Integration 断言原 Result 不被改写 |
| R5 | AI/人工派生相关性不能写进 Content Owner | docs/blueprint/07_技术决策与实施门禁.md | not_satisfied | 采用 Analysis-owned review table，待 Migration/ownership gate 验证 |
| R6 | 人工纳入后默认业务列表与查询型下游按相关处理 | backend/src/aima_ugc/modules/analysis/README.md | not_satisfied | 待统一 effective relevance 查询并验证 Analysis/Export target |
| R7 | 公共 API 改动必须走 Pydantic→OpenAPI→generated client | docs/blueprint/07_技术决策与实施门禁.md | not_satisfied | 待生成与 drift check |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | 声音广场相关性筛选、单条/批量人工标记、请求 payload、成功/失败反馈与列表刷新。 |
| Backend/API/PostgreSQL Integration | required | Migration、table owner、AI 原结果保留、review 幂等/原子性、版本失效、effective relevance 查询。 |
| Contract / Generated Client | required | Pydantic → OpenAPI → Orval，新增 review API 与 response 字段无 drift。 |
| Real Full-stack Golden Path | required | 真实 PostgreSQL/API/前端链至少验证 AI irrelevant → 前端筛出 → 人工纳入 → 默认列表可见。 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部协议或 Mapper，不需要付费 Provider Probe。 |
| Docs / Governance / Other | required | Blueprint 03/04/07、AI Appendix/README、Change Completion Gate、两阶段 Review。 |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取用户决定、AGENTS、Blueprint 03/04/07 与 AI README/Appendix。
- [ ] change_coverage：Ready 前重新比较 R1—R7 与代码/测试/文档。
- [ ] reverse_audit：后端 review 能力必须有声音广场入口；前端筛选/写操作必须有真实 API/DB 支撑；effective relevance 必须覆盖默认列表与 query target。
- [ ] unresolved_cleared：Ready 前 `not_satisfied` 清零，required 验证层都有当前 HEAD 证据。

# 任务

- [x] 读取当前 main、规则、AI/Content/Frontend/Contract/Migration 事实并完成方案比较
- [x] 清理已经合并但残留 active 的 `CHG-20260824-multi-keyword-pack-entrypoints`
- [ ] 建立 Red 测试并取得实际失败证据
- [ ] 新增 Analysis 人工复核 Schema/Migration/Repository
- [ ] 实现 effective relevance 查询与 HTTP Contract/API
- [ ] 生成 OpenAPI/Orval client
- [ ] 完成声音广场相关性筛选、单条/批量人工复核 UI
- [ ] 同步正式文档
- [ ] 运行 required Validation Matrix、Completion Audit、两阶段 Review 和 Ready Check

# 验证计划

## Red

- 扩展 `test_stage8d_voice_plaza_runtime.py`：AI irrelevant 原始 Result 保留、人工 review 后 effective relevant、默认/显式筛选改变、版本变化失效。
- 扩展 `frontend/e2e/voice-plaza.spec.ts`：选择“不相关”筛选、单条/批量 review POST、成功刷新与错误状态。

## Green / Regression

- 目标 PostgreSQL Integration + API tests。
- Frontend Vitest/Playwright、lint、typecheck、build。
- Contract/OpenAPI/Orval drift。
- Stage 8F Full-stack Golden Path。
- Ruff、mypy、table ownership、Alembic upgrade/head 检查和相关永久 CI。

# 文档影响

- Blueprint 03：Analysis 表清单增加人工 relevance review 表，明确不进入 Content Owner。
- Blueprint 04：Content API/声音广场增加人工 review endpoint 与 UI 行为。
- Blueprint 07：Decision G 补充“人工 Analysis 覆盖也是 Analysis Domain，AI 原始结果不可改写”。
- AI Appendix/README：记录 raw/effective relevance、版本绑定和人工复核调用链。

# Migration、部署、回滚与风险

- 新增单向 Alembic Migration `20260824_0025_manual_relevance_review.py`，基于当前 head `20260822_0024`。
- 部署顺序：先 Migration，再部署同时包含新 API 与前端的应用版本；旧代码面对新增表无行为改变。
- 回滚应用前应停止使用新 review API；Migration downgrade 会删除人工 review 表，模型原始 Analysis Result 与 Content 不受影响，但人工复核历史会丢失，因此生产环境 downgrade 前必须明确备份/接受该数据损失。
- 批量 review 上限复用现有 `ContentTargetSelection` 的 1000 级量级或设置更小有界上限；不得构造无限 `IN` 查询。
- 当前没有 Authorization，因此只记录“发生了人工复核”及时间，不伪造 reviewer user；正式用户身份待认证/授权阶段再扩展。

# 交付

- 分支：`feature/manual-relevance-review`
- PR：待创建 Draft PR
- 合并：未经用户明确授权不合并 main。
