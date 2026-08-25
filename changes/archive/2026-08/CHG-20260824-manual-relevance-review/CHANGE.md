---
schema: rvc-change/v1
id: CHG-20260824-manual-relevance-review
title: AI 相关性双向人工复核与撤销
level: L3
status: done
owner: aima
branch: feature/manual-relevance-review
created: 2026-08-24
updated: 2026-08-25
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
  - backend/src/aima_ugc/modules/content/query.py
  - backend/src/aima_ugc/modules/content/http.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/contracts/relevance_review.py
  - backend/src/aima_ugc/contracts/http.py
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
  - tests/integration/content/test_bidirectional_relevance_review.py
  - tests/fullstack/create_stage8f_excel_fixture.py
  - tests/fullstack/seed_stage8f_manual_relevance_review.py
  - .github/workflows/fullstack.yml
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

把原单向“AI irrelevant → 人工 relevant”扩展为完整且可审计的双向人工相关性复核：

- AI `irrelevant` 可以人工标记为 `relevant`；
- AI `relevant` 可以人工标记为 `irrelevant`；
- 活动人工决定可以撤销，恢复到当前 AI 业务基线；
- 每次人工设置与撤销都保留追加历史，不 UPDATE/DELETE AI 原始结果，也不删除旧人工事件；
- 默认列表、显式 `relevance` 查询、查询型 Analysis Target 和查询型 Export 继续复用同一业务有效相关性。

# 成功标准

- [x] 声音广场可显式查看业务有效 `irrelevant` 内容。
- [x] AI 原始 relevance/sentiment/labels 不因人工复核被改写。
- [x] 支持单条/批量 `irrelevant → relevant`。
- [x] 支持单条/批量 `relevant → irrelevant`，并从默认业务列表退出、进入 `relevance=irrelevant`。
- [x] 支持撤销当前人工决定；撤销后业务有效相关性重新继承当前 AI 基线。
- [x] 人工设置与撤销采用追加审计账本，保留同一 Content Version 的多次操作历史及顺序，数据库拒绝 UPDATE/DELETE。
- [x] 同一目标状态重复提交幂等；批量请求任一目标不满足状态约束时整体失败。
- [x] Content 新版本不继承旧版本人工决定。
- [x] 当前 AI 因 Prompt/Model 身份变化进入 `stale` 时，活动人工覆盖仍能被识别和撤销。
- [x] OpenAPI、Orval generated client、Vue UI、Migration、PostgreSQL/Browser/Full-stack 测试与正式文档全部同步。

# 范围与最终语义

- `analysis_content_relevance_reviews` 是 Analysis-owned 的追加事件账本；每个事件保存 `content_id + content_version + analysis_result_id + review_no + decision + request_id + reviewed_at`。
- `decision` 机器值固定为：`relevant`、`irrelevant`、`inherit_ai`。
- `(content_id, content_version, review_no)` 唯一；Repository 先锁定 Content Current，再分配下一个 `review_no`，使同一内容版本的并发人工操作串行化。
- Migration 在数据库层安装 `BEFORE UPDATE OR DELETE` Trigger，直接修改或删除人工事件会失败。
- `POST /api/v1/content-relevance-reviews` 是单条/批量统一入口，请求显式携带 `decision`，Response 为 `requested_count / changed_count / unchanged_count`。
- 没有活动人工覆盖，或最新事件为 `inherit_ai` 时，业务有效相关性采用当前 AI relevance；没有当前 AI 时为 null。
- 最新事件为 `relevant/irrelevant` 时，业务有效相关性采用该人工值，但 `ContentAnalysisResponse.relevance` 始终保留 AI 原判。
- Content List/Detail 增加只读派生投影 `effective_relevance` 与 `relevance_source=ai/manual_review`；它们不对应新的数据库写事实。该投影使 AI 当前结果进入 `stale` 后仍能识别并撤销活动人工覆盖。
- 已有活动人工覆盖时，重复相同值幂等；直接切到相反人工值返回 409，必须先 `inherit_ai` 再作新人工判断，使审计链显式。
- `inherit_ai` 只在存在活动人工覆盖时追加撤销事件；重复撤销幂等。
- 撤销事件沿用被撤销人工事件的 `analysis_result_id`，即使当前模型身份已变化，也能说明撤销的是哪条人工纠正链。
- Content Version 更新后，旧版本人工事件只保留审计，不参与新版本业务有效相关性。
- 人工 `irrelevant` 只改变业务集合资格；AI 原有 sentiment/labels 继续保留为模型事实。

# 非目标

- 不修改 Prompt、Taxonomy、LLM Provider、AI 情感/标签规则。
- 不向 `contents` 增加 `is_relevant` 或平行 Analysis 写字段。
- 不删除 Content，也不因人工改为 irrelevant 删除数据。
- 不引入认证/Reviewer 用户身份；当前没有正式 Authorization，不伪造 reviewer identity。
- 不新增异步 Review Job；复核仍是同步短事务。
- 不修改 TikHub、Excel 关键词规则相关性或 Provider 协议。
- 不支持人工直接编辑 sentiment/labels/voice_type。

# 必须保持不变

- `analysis_content_results.relevance` 始终表示 AI 原始 Analysis 事实。
- 人工相关性属于 Analysis Domain；Content Owner 不保存平行相关性写事实。
- Content 身份 `(platform, external_content_id)` 与 Current/Version/Metric 机制不变。
- 查询型 Analysis/Export 继续复用 `PostgresContentQueryRepository.freeze_targets()`。
- Pydantic → FastAPI/OpenAPI → Orval → Frontend 是唯一 HTTP Contract 链。
- 批量写在同一数据库事务内全量校验后提交；不产生隐蔽部分成功。

# L3 方案比较与已确认决策

## 方案 A：继续每版本单 row，撤销时 DELETE

会抹掉人工审计事实，无法回答多轮复核历史，不采用。

## 方案 B：每版本单 row，加 `revoked_at` 并反复 UPDATE

只能保存 Current，不能完整重建操作序列，不采用。

## 方案 C：追加式人工决定账本

同一 Content Version 允许多个按 `review_no` 排序的事件；最新事件决定当前人工覆盖，`inherit_ai` 明确撤销。它保留完整审计、无需改 AI Result，并可利用 Content row lock 串行化并发。采用本方案。用户于 2026-08-24 明确追加要求“实现撤销和 AI 相关 → 人工不相关”。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 前端能查看业务有效不相关内容并逐条复核 | user:2026-08-24-manual-relevance-review | satisfied | `frontend/e2e/manual-relevance-review.spec.ts` 与历史 Stage 8F run 32721400484 已验证。 |
| R2 | 支持单条/批量 AI irrelevant → 人工 relevant | user:2026-08-24-manual-relevance-review | satisfied | API/PG 定向 run 32721400535 与历史 Stage 8F run 32721400484 均通过。 |
| R3 | AI 原始结果保持不可改写，人工事实归 Analysis Owner | docs/blueprint/07_技术决策与实施门禁.md | satisfied | PostgreSQL integration 验证原 AI Result 保留；0025 与 table ownership 均归 Analysis。 |
| R4 | 默认列表、relevance 查询、query Analysis/Export 使用统一有效相关性 | backend/src/aima_ugc/modules/analysis/README.md | satisfied | `PostgresContentQueryRepository` 单一表达式与 PostgreSQL integration 已覆盖默认、显式查询、query Analysis/Export。 |
| R5 | 公共 API 变化走 Pydantic→OpenAPI→generated client | docs/blueprint/04_后端任务API与前端.md | satisfied | 官方生成链已同步 `contracts/openapi/openapi.json` 与 Orval client；旧 CI 曾精确暴露说明文字导致的 `CONTRACT_STALE`，随后重新运行正式生成链并通过 `generate.py --check` 与 compatibility check。 |
| R6 | 支持 AI relevant → 人工 irrelevant | user:2026-08-24-bidirectional-relevance-review | satisfied | Browser Mock、PostgreSQL integration 与历史 Stage 8F 真实链均已覆盖。 |
| R7 | 支持撤销人工决定并恢复 AI 基线 | user:2026-08-24-bidirectional-relevance-review | satisfied | `inherit_ai` API/Repository/UI 已实现；历史 Stage 8F run 32721400484 真实排除→撤销成功。 |
| R8 | 撤销和多轮人工决定不得丢失历史审计 | docs/blueprint/07_技术决策与实施门禁.md | satisfied | `review_no` 追加事件、数据库 UPDATE/DELETE Trigger 与 integration 均已验证。 |
| R9 | 双向/撤销保证批量原子性、幂等、版本隔离和 stale 可撤销 | .agents/skills/coding/SKILL.md | satisfied | PG integration 验证重复幂等、直接反向 409、全量事务、Version 隔离及 Prompt/Model 变化后的 stale 撤销。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | run 32721400535：人工复核 Playwright 5/5；覆盖单条双向、撤销、stale 撤销、批量不相关及显式 payload。 |
| Backend/API/PostgreSQL Integration | required | run 32721400535：API 3/3、人工复核 PostgreSQL integration 2/2；0025 upgrade/check、双向、撤销、append-only、幂等、原子性与版本语义通过。 |
| Contract / Generated Client | required | Pydantic 三值 decision、effective relevance projection 已通过正式 OpenAPI/Orval 生成链；最终生成链还通过 `generate.py --check` 与 `check_compatibility.py`。 |
| Real Full-stack Golden Path | required | 历史 Stage 8F run 32721400484：5/5；AI irrelevant→人工 relevant、AI relevant→人工 irrelevant→撤销均成功。最终 PR HEAD `232e125abc964ce2035b895a6e3021d6a8628b08` 的 `Full-stack Acceptance` run 32734834389 再次成功。 |
| Real Provider Probe | not_applicable | 本次不修改 TikHub/LLM 外部 endpoint、请求字段、Mapper 或真实付费 Provider 行为。 |
| Docs / Governance / Other | required | Blueprint 03/04/07、AI Appendix、Analysis README 已同步；A1/A2 Review 已完成，PR #202 当前无 review comment/thread。 |

# TDD Evidence

- API Red：run 32708662395，三种新 `decision` 在旧 Contract 上均返回 422。
- PostgreSQL 双向 Red：run 32709095687，原有 111 个相关 integration 通过，仅新 `decision=irrelevant` 场景因旧 Contract 失败。
- Browser Red：run 32709123282，旧 payload 缺 `decision`，且缺“不相关 / 撤销 / 批量不相关”按钮。
- Projection Red：真实 PostgreSQL 测试在业务状态已正确计算的前提下，因 `ContentListItemResponse` 缺 `effective_relevance` 失败；随后加入只读派生投影。
- Append-only Red：run 32720466525，直接 UPDATE 人工账本未抛 `DatabaseError`，证明原 Migration 缺数据库级不可变约束。
- Targeted Green：run 32721400535 全部目标层通过；PostgreSQL 日志明确记录账本禁止 UPDATE/DELETE。
- Real Full-stack Green：历史 Stage 8F run 32721400484，5/5 通过；当前 CI 拓扑已迁移为 `Full-stack Acceptance`。
- Contract Drift Regression：旧最终候选 HEAD 的 Provider Persistence 业务/数据库验证 332 + 89 均通过，但 quality gate 以 `CONTRACT_STALE` 拒绝未同步 OpenAPI；之后使用正式 Pydantic→OpenAPI→Orval 生成命令修复，不手改 generated 文件。
- 最终 PR HEAD `232e125abc964ce2035b895a6e3021d6a8628b08` 的 6 个长期 Workflow 全部成功：Change Completion Gate 32734834355、Full-stack Acceptance 32734834389、Local Dev Bootstrap 32734834379、Windows Docker Desktop Compose Compatibility 32734834439、Internal V1-A Deployable Stack 32734834463、CI 32734834423。

# Completion Audit

- [x] upstream_re_read：已重新读取用户双向/撤销要求、当前 `main`/feature `AGENTS.md`、RVC Skill、Blueprint README/03/04/07、Analysis README/Appendix 与当前 Change。
- [x] change_coverage：R1—R9 已逐项映射到 Schema/Migration、Repository、Query、HTTP/generated client、Vue UI、Browser/PG/Full-stack 测试和正式文档，均为 satisfied。
- [x] reverse_audit：每个 `relevant / irrelevant / inherit_ai` 后端 decision 均有明确前端入口；前端按钮直接依赖服务端 `effective_relevance / relevance_source`，不再从筛选条件猜测；默认/relevant/irrelevant/query Analysis/query Export 共用同一 Query Repository 语义。
- [x] unresolved_cleared：双向、撤销、stale、append-only、批量、版本、AI 原结果保留均已有定向或真实 Full-stack 证据；最终 PR HEAD 的 6 个长期 Workflow 已全部成功并完成合并。

# A1 / A2 Review

## A1 Correctness / Scope

- Schema、Migration、Repository、Query、HTTP Contract、generated client 与 UI 的三值语义一致。
- 人工决定没有写回 `contents` 或 `analysis_content_results`；`effective_relevance / relevance_source` 仅为查询派生投影。
- 改动范围未扩展到 TikHub、LLM Provider、Prompt/Taxonomy 或无关模块。
- Full-stack 中两处失败均定位为测试断言错误：标签分隔符与 strict selector 范围；修复只改测试，真实 POST/查询行为当时已成功。
- main 的 CI Validation Layers Change 将旧 `stage8f-fullstack.yml` 收敛为 `fullstack.yml`；本 Change 只把人工复核验收迁移到新长期工作流，没有回滚 main 的 CI 收敛。

## A2 Reliability / Edge Cases

- Content row lock 串行化同一 Content 的并发 review_no 分配；唯一约束提供第二层保护。
- 批量先全量校验后 INSERT，任一目标冲突不会产生部分人工事件。
- 数据库 Trigger 拒绝 UPDATE/DELETE，撤销通过追加 `inherit_ai` 完成。
- 重复相同人工决定与重复撤销均幂等；活动覆盖不能直接反向，必须先撤销。
- Content Version 变化不继承旧人工决定；Prompt/Model 身份变化导致 AI stale 时，活动人工覆盖仍可识别和撤销。
- downgrade 会删除人工复核账本但不影响 AI Result/Content；生产回滚前必须备份或接受人工历史丢失。

# 任务

- [x] 重新读取当前分支 AGENTS、Skill、Blueprint 与现有人工复核实现
- [x] 将 PR #202 退回 Draft，并把 Change 从 ready_for_review 退回 in_progress
- [x] Red：扩展 API/PG/Browser 测试并取得目标能力缺失证据
- [x] Green：调整 0025 Schema、Analysis Repository 与 effective relevance Query
- [x] Green：扩展 HTTP Contract、OpenAPI/Orval 和声音广场 UI
- [x] Green：补数据库级 append-only Trigger 与 stale 人工覆盖只读投影
- [x] 同步 Blueprint 03/04/07、AI Appendix 与 Analysis README
- [x] 跑目标验证矩阵与历史 Stage 8F Golden Path
- [x] 完成 Requirement Traceability、Completion Audit、A1/A2 Review
- [x] 修复 Contract drift，并用正式生成链重新同步 OpenAPI/Orval
- [x] 同步最新 main，并把人工复核 Full-stack 验收迁移到 `.github/workflows/fullstack.yml`

# Migration、部署、回滚与风险

- `20260824_0025_manual_relevance_review.py` 在 PR #202 合并前直接演进为最终账本结构，因此没有新增“修未发布 migration”的 0026；该 Migration 现已随 merge commit `014fb666b6f7f5e979cf5ca71fd940da8f21bb5e` 进入 `main`。
- 部署顺序：Migration → 同版本 API/Frontend；旧 API/Frontend 不应与新三值 Contract 混用。
- downgrade 会先删除 append-only Trigger/Function，再删除整个人工复核账本；AI 原始 Analysis Result 与 Content 不受影响，但人工历史会丢失，生产 downgrade 前必须备份或明确接受数据损失。
- 单请求限制 1—1000 个不重复 Content ID；同批任一非法状态导致全事务回滚。
- 当前无 Authorization，只保存 `request_id/reviewed_at`，不伪造 reviewer user。
- 没有新增依赖，也没有外部 Provider 配置或 Secret 变化。

# 交付

- 分支：`feature/manual-relevance-review`
- 最终 PR HEAD：`232e125abc964ce2035b895a6e3021d6a8628b08`
- PR：#202，已通过 merge commit `014fb666b6f7f5e979cf5ca71fd940da8f21bb5e` 合入 `main`。
- 归档：PR #219，分支 `chore/archive-manual-relevance-review`
