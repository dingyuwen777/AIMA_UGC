---
schema: rvc-change/v1
id: CHG-20260824-manual-relevance-review
title: AI 相关性双向人工复核与撤销
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

把当前单向“AI irrelevant → 人工 relevant”扩展为完整但仍受控的人工相关性复核：

- AI `irrelevant` 可以人工标记为 `relevant`；
- AI `relevant` 可以人工标记为 `irrelevant`；
- 已存在的人工相关性决定可以撤销，恢复为 AI 当前业务基线；
- 每次人工设置与撤销都保留审计历史，不 UPDATE/DELETE 模型原始 `analysis_content_results`，也不删除旧人工事件；
- 默认列表、显式 `relevance` 查询、查询型 Analysis Target 和查询型 Export 继续复用同一业务有效相关性。

# 成功标准

- [x] 声音广场可显式查看业务有效 `irrelevant` 内容。
- [x] AI 原始 relevance/sentiment/labels 不因人工复核被改写。
- [x] 支持单条/批量 `irrelevant → relevant`。
- [ ] 支持单条/批量 `relevant → irrelevant`，并从默认业务列表退出、进入 `relevance=irrelevant`。
- [ ] 支持撤销当前人工决定；撤销后业务有效相关性重新继承 AI 基线。
- [ ] 人工设置与撤销采用追加审计账本，能保留同一 Content Version 的多次操作历史及顺序。
- [ ] 同一目标状态重复提交幂等；批量请求任一目标不满足状态约束时整体失败。
- [x] Content 新版本不继承旧版本人工决定。
- [ ] OpenAPI、Orval generated client、Vue UI、Migration、PostgreSQL/Browser/Full-stack 测试与正式文档全部同步。

# 范围

- `analysis_content_relevance_reviews` 从“每版本唯一单向 row”调整为每个 `content_id + content_version` 的追加式 review event ledger。
- 每个事件保存 `content_id + content_version + analysis_result_id + review_no + decision + request_id + reviewed_at`。
- `decision` 机器值固定为：
  - `relevant`：人工覆盖为相关；
  - `irrelevant`：人工覆盖为不相关；
  - `inherit_ai`：撤销当前人工覆盖，业务有效相关性重新采用 AI 基线。
- `(content_id, content_version, review_no)` 唯一；Repository 在锁定 Content Current 后分配下一个 `review_no`，保证同一版本事件顺序可确定。
- `POST /api/v1/content-relevance-reviews` 继续作为单条/批量统一入口，请求显式携带 `decision`。
- Response 使用通用的 `requested_count / changed_count / unchanged_count`，不再使用只适合单向操作的 `reviewed_count / already_reviewed_count`。
- Content 公共 Analysis Response 继续表示 AI 原判，不新增伪装成模型输出的第二套 relevance 字段。
- 声音广场根据当前业务筛选与 AI 原判展示：人工标记为相关、人工标记为不相关、撤销人工判断及批量操作。

# 非目标

- 不修改 Prompt、Taxonomy、LLM Provider、AI 情感/标签规则。
- 不向 `contents` 增加 `is_relevant` 或其他平行 Analysis 字段。
- 不删除 Content，也不因人工改为 irrelevant 删除数据。
- 不引入认证/Reviewer 用户身份；当前没有正式 Authorization，不伪造 reviewer identity。
- 不新增异步 Review Job；复核仍是同步短事务。
- 不修改 TikHub、Excel 关键词规则相关性或 Provider 协议。
- 不支持人工直接编辑 sentiment/labels/voice_type。

# 必须保持不变

- `analysis_content_results.relevance` 始终表示 AI 原始 Analysis 事实。
- 人工相关性属于 Analysis Domain；Content Owner 不保存平行相关性事实。
- Content 身份 `(platform, external_content_id)` 与 Current/Version/Metric 机制不变。
- 查询型 Analysis/Export 继续复用 `PostgresContentQueryRepository.freeze_targets()`。
- Pydantic → FastAPI/OpenAPI → Orval → Frontend 是唯一 HTTP Contract 链。
- 批量写在同一数据库事务内全量校验后提交；不产生隐蔽部分成功。

# L3 方案比较与已确认决策

## 方案 A：继续每版本单 row，撤销时 DELETE

优点：改动最少。

缺点：撤销直接抹掉人工审计事实；相关→撤销→不相关等历史无法回答。

结论：不采用。

## 方案 B：每版本单 row，加 `revoked_at` 并反复 UPDATE

优点：能知道当前是否撤销。

缺点：同一版本多轮人工判断仍被覆盖，不能完整重建操作序列；“人工审计事实”退化成 mutable current state。

结论：不采用。

## 方案 C：追加式人工决定账本

机制：同一 Content Version 允许多个按 `review_no` 排序的事件；最新事件决定当前人工覆盖。`relevant/irrelevant` 表示人工覆盖，`inherit_ai` 表示明确撤销并回到 AI 基线。

优点：完整可审计；无需改 AI Result；支持双向与撤销；查询层只需要读取每版本最新事件；并发可通过现有 Content row lock 串行化。

代价：Schema/Repository/Query 比单 row 多一个事件序号与 latest-event 子查询。

结论：采用。用户于 2026-08-24 明确追加要求“实现撤销和 AI 相关 → 人工不相关”。

# 关键业务语义

1. 没有人工事件或最新事件为 `inherit_ai`：业务有效相关性采用当前 AI relevance；没有当前 AI 时为未知/null。
2. 最新事件为 `relevant` / `irrelevant`：业务有效相关性采用该人工值，但公共 `ContentAnalysisResponse.relevance` 仍返回 AI 原判。
3. 对没有活动人工覆盖的内容，人工设置只允许把当前 AI relevance 改成相反值；与 AI 原判相同的请求视为 unchanged，不产生冗余事件。
4. 已有活动人工覆盖时，重复同一人工值幂等；直接切到另一人工值返回 409，要求先执行 `inherit_ai` 撤销，再作新的人工判断，使审计语义显式。
5. `inherit_ai` 只在存在活动人工覆盖时新增撤销事件；重复撤销幂等，不重复写账本。
6. 撤销事件沿用被撤销人工事件的 `analysis_result_id`，即使当前模型配置身份已变化，也能精确说明撤销的是哪次人工纠正链。
7. Content Version 更新后，旧版本全部人工事件只保留审计，不参与新版本业务有效相关性。
8. 人工 `irrelevant` 只影响是否进入业务集合；AI 原有 sentiment/labels 仍保留为模型事实，不被清空或伪造。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 前端能查看业务有效不相关内容并逐条复核 | user:2026-08-24-manual-relevance-review | satisfied | 现有声音广场 relevance 筛选、Browser/Full-stack 已验证。 |
| R2 | 支持单条/批量 AI irrelevant → 人工 relevant | user:2026-08-24-manual-relevance-review | satisfied | 现有 review API/UI/PG integration 已验证；本轮需保持回归。 |
| R3 | AI 原始结果保持不可改写，人工事实归 Analysis Owner | docs/blueprint/07_技术决策与实施门禁.md | satisfied | 当前 Analysis-owned 表及 table ownership 已建立；本轮继续保持。 |
| R4 | 默认列表、relevance 查询、query Analysis/Export 使用统一有效相关性 | backend/src/aima_ugc/modules/analysis/README.md | satisfied | 当前统一 Query Repository 已建立；本轮扩展 latest event 语义。 |
| R5 | 公共 API 变化走 Pydantic→OpenAPI→generated client | docs/blueprint/04_后端任务API与前端.md | satisfied | 现有生成链已建立；本轮 decision/response 字段变更重新生成。 |
| R6 | 支持 AI relevant → 人工 irrelevant | user:2026-08-24-bidirectional-relevance-review | not_satisfied | 待新增 Contract、Repository、Query、UI、PG/Browser/Full-stack 测试。 |
| R7 | 支持撤销人工相关性决定并恢复 AI 基线 | user:2026-08-24-bidirectional-relevance-review | not_satisfied | 待新增 `inherit_ai` 事件与 UI 撤销入口。 |
| R8 | 撤销和多轮人工决定不得丢失历史审计 | docs/blueprint/07_技术决策与实施门禁.md | not_satisfied | 待把单 row 改为 `review_no` 追加账本，并验证事件历史。 |
| R9 | 双向/撤销仍需保证批量原子性、幂等和版本隔离 | .agents/skills/reliable-vibe-coding/SKILL.md | not_satisfied | 待扩展 PostgreSQL integration 和 API/Browser 回归。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | 单条/批量 relevant→irrelevant、撤销两种方向、按钮状态、payload、成功/409 反馈、刷新后列表位置。 |
| Backend/API/PostgreSQL Integration | required | 0025 Schema、review_no 账本顺序、双向覆盖、撤销、重复幂等、直接反向冲突、批量原子性、Content Version 隔离、AI 原结果不变。 |
| Contract / Generated Client | required | `decision` 三值、通用 response count、OpenAPI/Orval 无 drift。 |
| Real Full-stack Golden Path | required | 至少覆盖 AI relevant → 人工 irrelevant → irrelevant 列表 → 撤销 → 默认列表恢复，并保留原 AI Result。 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部协议、Mapper 或付费调用形状。 |
| Docs / Governance / Other | required | Blueprint 03/04/07、AI Appendix/README、Change Completion Gate、两阶段 Review、永久 CI。 |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取用户双向/撤销决定、AGENTS、Blueprint 03/04/07、Analysis README/Appendix。
- [ ] change_coverage：Ready 前重新比较 R1—R9 与 Schema/Repository/Query/API/generated/UI/tests/docs。
- [ ] reverse_audit：确认所有后端 decision 有前端入口，所有前端动作都有真实 DB 语义；默认/relevant/irrelevant/query Analysis/query Export 统一使用 latest-event effective relevance。
- [ ] unresolved_cleared：Ready 前 R6—R9 清零，required 验证层取得当前最终 HEAD 新鲜证据。

# 任务

- [x] 重新读取当前分支 AGENTS、Skill、Blueprint 与现有人工复核实现
- [x] 将 PR #202 退回 Draft，并把 Change 从 ready_for_review 退回 in_progress
- [ ] Red：先扩展 API/PG/Browser 测试，确认双向与撤销因能力缺失而失败
- [ ] Green：调整 0025 Schema、Analysis Repository 与 effective relevance Query
- [ ] Green：扩展 HTTP Contract、OpenAPI/Orval 和声音广场 UI
- [ ] 同步 Blueprint 03/04/07、AI Appendix 与 Analysis README
- [ ] 跑目标测试、永久 CI、Stage 6、Stage 8F、Completion Gate
- [ ] 完成 Completion Audit、A1/A2 Review，再转 Ready

# Migration、部署、回滚与风险

- `20260824_0025_manual_relevance_review.py` 尚未进入 `main`，因此直接修改本 PR 内 0025 为最终账本结构，不新增“修未发布 migration”的 0026。
- 部署顺序仍为：Migration → 同版本 API/Frontend。
- downgrade 仍会删除整个人工复核账本；AI 原始 Analysis Result 与 Content 不受影响，但全部人工历史会丢失，生产 downgrade 前必须备份或明确接受数据损失。
- 单请求继续限制 1—1000 个不重复 Content ID；同批任一非法状态导致全事务回滚。
- 当前无 Authorization，只保存 request_id/reviewed_at，不伪造 reviewer user。

# 交付

- 分支：`feature/manual-relevance-review`
- PR：#202，施工期间保持 Draft。
- 合并：未经用户明确授权，不合并 `main`。
