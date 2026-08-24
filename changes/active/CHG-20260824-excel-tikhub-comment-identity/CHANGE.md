---
schema: rvc-change/v1
id: CHG-20260824-excel-tikhub-comment-identity
title: Excel 与 TikHub 内容身份和评论补采定位统一
level: L2
status: in_progress
owner: aima
branch: feature/excel-tikhub-identity-alignment
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - collection
  - content
  - ingestion
affected_paths:
  - backend/src/aima_ugc/adapters/providers/tikhub/runtime.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_complete.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - tests/unit/collection/
  - tests/integration/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts:
  - CanonicalContentV1 alternate_ids
data_changes: []
---

# 目标

统一 Excel 与 TikHub 的内容身份使用方式：数据库稳定 Content 身份保持不变，同时把 `note_id`、`aweme_id`、`status_id`、`av_id`/`bv_id`、`photo_id` 等 typed Provider identity 作为详情、一级评论和二级回复补采 locator 使用；不同来源观察到的 typed identity 需要在同一 Content 上保留，而不是被后一次来源整体覆盖。

# 成功标准

- [ ] Excel 已解析出的平台原生 typed ID 可以用于 TikHub Detail 和一级评论补采，不要求它必须等于 `external_content_id`。
- [ ] 二级回复继续使用同一内容的 Provider locator，不因 Canonical 稳定 ID 与 Provider locator 不同而请求错误。
- [ ] Import Batch enrichment seed 从已落库 `content_external_ids` 恢复 typed identity 并传入 Runtime。
- [ ] TikHub Detail 新观察到的 Provider ID 与 Excel 已保存的 `source_article_id`/其他 typed ID 合并保留，不整体删除旧 identity。
- [ ] 现有 `(platform, external_content_id)` Content 稳定身份、Comments 外键语义、Provider Raw/Attempt 来源链保持不变。
- [ ] 五个平台既有直接 `external_content_id` 补采路径继续兼容。

# 范围

- Import Batch enrichment target 的 typed identity 资格判断与 seed 透传。
- TikHub Runtime 的 Detail/Comments/SubComments locator 解析。
- Content `alternate_ids` 的跨来源合并持久化语义。
- 对应单元/集成回归测试和当前数据入口文档。

# 非目标

- 不修改 Content 主键或 `(platform, external_content_id)` 唯一键。
- 不做历史 Content 合并或新增 Identity Registry/Migration。
- 不改变评论采样、分页、预算、Relevance、Decision Policy。
- 不新增 TikHub Endpoint，不改变 App/Web fallback 策略。

# 必须保持不变

- Canonical `external_content_id` 仍是数据库稳定内容身份和 Comment 归属身份。
- Provider lookup identity 只用于构造外部 Provider 请求，不反向改写已存在 Content 主身份。
- Raw Artifact、Provider Attempt、Candidate、Content Ingestion 的事务与来源约束保持现状。
- 不升级依赖，不新增数据库表。

# 方案比较与决策

1. **推荐：稳定 ID 与 Provider locator 分离。** 继续使用 `external_content_id` 作为 Canonical/数据库稳定身份，优先从 `alternate_ids` 选择平台已验证 typed locator；Detail/Comment Mapper 仍用稳定 ID 写回 Canonical。优点是最小、兼容、无需 Migration，也能让 Excel ID 直接参与补采。
2. 将各平台 Provider ID 强制改成统一 `external_content_id`。B站 AV/BV、多来源历史数据会产生迁移和兼容风险，且会把数据库身份与 Provider 参数耦合，不采用。
3. 新建独立 Identity Registry 并做跨别名主实体合并。长期能力更强，但当前需求不需要新增 Schema/Migration，范围过大，不采用。

已确认采用方案 1。本轮同时把 `alternate_ids` 作为身份别名集合按 id_type 合并，避免 Excel 与 TikHub 不同来源互相擦除 identity。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Excel 或 TikHub 获取到的笔记/作品 ID 都能用于评论补采 | user:2026-08-24-comment-identity | not_satisfied | 待 Runtime/Enrichment 实现与测试 |
| R2 | 多来源统一考虑，不能只解决单一路径 | user:2026-08-24-comment-identity | not_satisfied | 待 alternate_ids 合并与五平台回归 |
| R3 | 保持现有稳定 Content 身份和入库架构 | AGENTS.md + Canonical/Content Owner current implementation | not_satisfied | 待回归证明 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 无前端/HTTP Contract 行为变化。 |
| Backend/API/PostgreSQL Integration | required | 证明 Import Batch target 能恢复 typed IDs，跨来源 alternate_ids 不被覆盖。 |
| Contract / Generated Client | not_applicable | 不修改 HTTP/OpenAPI/generated client。 |
| Real Full-stack Golden Path | not_applicable | 本轮风险位于内部 Collection/Content 边界，已有 PostgreSQL integration 更直接。 |
| Real Provider Probe | not_applicable | 当前五平台 Detail/Comments locator 类型已由现有真实样本/Operation 测试验证，本轮不改 Endpoint。 |
| Docs / Governance / Other | required | 数据入口文档与 gated Change Ready Check。 |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取 AGENTS、相关 Runtime/Repository/正式数据入口文档。
- [ ] change_coverage：逐项核对 R1—R3 与用户本轮补充要求。
- [ ] reverse_audit：从 Excel Import → Batch target → Detail → Comments → SubComments → Canonical 写回反向核对 locator 与稳定 ID。
- [ ] unresolved_cleared：进入 ready_for_review 前清零 not_satisfied。

# 任务

- [x] 调查当前 Excel identity、TikHub Operation/Mapper、Batch enrichment target、Content alternate_ids 持久化事实。
- [ ] 先补 locator/identity merge 回归测试并取得失败证据。
- [ ] 最小实现 Runtime typed locator 与 Batch seed 透传。
- [ ] 最小实现跨来源 alternate_ids 按 id_type 合并。
- [ ] 同步数据入口文档。
- [ ] 跑目标测试、相关 Integration、静态检查和 Ready Check。
- [ ] 完成两阶段 Review 与 Completion Audit。

# 验证

目标至少包括：

```bash
pytest -q tests/unit/collection/test_provider_lookup_identity.py tests/unit/collection/test_tikhub_runtime_comment_flow.py
pytest -q tests/integration -k "collection_target or alternate_ids or enrichment"
ruff check backend/src/aima_ugc/adapters/providers/tikhub/runtime.py backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py backend/src/aima_ugc/adapters/persistence/postgres/content_complete.py backend/src/aima_ugc/bootstrap/collection_scope.py tests/unit/collection
python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready
```

实际执行结果在完成前回填。

# 文档影响

- `docs/appendix/08_数据入口与统一入库实现.md`：明确稳定 Content ID 与 Provider lookup identity 分离，以及 Excel/TikHub identity 如何共同用于补采。

# 兼容、部署与回滚

- 无 Schema/Migration、无依赖变化。
- 现有直接以 `external_content_id` 调用 TikHub 的路径保留为 fallback。
- 行为变化仅扩大已验证 typed identity 的可用范围，并把 `alternate_ids` 从跨来源整体替换改为按 id_type 合并。
- 回滚可整体回滚本 Change；无数据迁移回滚步骤。

# 交付

- 分支：`feature/excel-tikhub-identity-alignment`
- PR：待创建
- 合并：待永久 CI 全绿及 Review 后决定
