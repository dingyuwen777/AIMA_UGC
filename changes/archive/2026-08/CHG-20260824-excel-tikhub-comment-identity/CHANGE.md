---
schema: rvc-change/v1
id: CHG-20260824-excel-tikhub-comment-identity
title: Excel 与 TikHub 内容身份和评论补采定位统一
level: L3
status: done
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
  - backend/src/aima_ugc/adapters/providers/imports/identity.py
  - backend/src/aima_ugc/adapters/providers/tikhub/runtime.py
  - backend/src/aima_ugc/adapters/providers/tikhub/mappers/kuaishou.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_complete.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - tests/unit/collection/
  - tests/integration/collection/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts:
  - CanonicalContentV1 alternate_ids
data_changes:
  - 新摄取的快手内容在可观察 share_info.photoId 时以公开分享作品 ID 作为稳定 external_content_id 和 TikHub 补采 photo_id；Raw 数字 photo_id 保存为 provider_photo_id，不自动迁移历史行。
---

# 目标

统一 Excel 与 TikHub 的内容身份使用方式：当前正式支持的平台内容在 Excel URL 与 TikHub Mapper 间生成一致的稳定 Content 身份；`note_id`、`aweme_id`、`status_id`、`av_id`/`bv_id`、`photo_id` 等 typed Provider identity 用于详情、一级评论和二级回复补采；不同来源观察到的 typed identity 在同一 Content 上按类型合并保留。

# 成功标准

- [x] Excel 已解析出的平台 typed ID 可以用于 TikHub Detail 和一级评论补采，不要求 locator 字符串必须等于所有 Provider Raw 内部 ID。
- [x] 二级回复使用同一 Content 的 Provider locator，不因稳定 Content ID 与内部 Provider ID 不同而请求错误。
- [x] Import Batch enrichment seed 从 `content_external_ids` 恢复 typed identity 并传入 Runtime。
- [x] 不同来源的 `alternate_ids` 按 `id_type` 合并；较旧 Observation 可补缺失类型，但不能覆盖同类型较新值。
- [x] B站视频 Excel BV 链接统一到 TikHub Mapper 使用的数字 AID，同时保留 BV/AV locator。
- [x] 快手 TikHub Search 优先使用公开 `share_info.photoId(3x...)` 作为稳定 Content/补采 ID，与 Excel `/short-video/{id}` 对齐；数字 Provider `photo_id` 单独保留。
- [x] `(platform, external_content_id)`、Comment 内部归属、Provider Raw/Attempt 来源链保持不变。
- [x] 五个平台当前正式支持内容的既有补采路径保持兼容，并完成有界真实 TikHub 验证。

# 范围

- Excel native identity 规范化中的 B站视频 BV→AID。
- 快手 Search/Detail 的公开分享 ID 与数字内部 ID 分离。
- Import Batch enrichment target 的 typed identity 资格判断与 seed 透传。
- TikHub Runtime 的 Detail/Comments/SubComments locator 解析。
- Content `alternate_ids` 的跨来源按类型合并持久化。
- 对应 Unit/PostgreSQL Integration、真实 Provider Probe 和数据入口文档。

# 非目标

- 不修改 Content 内部 UUID 主键或数据库唯一键结构。
- 不自动合并本 Change 之前已经以不同 `external_content_id` 落库的历史 Content；历史实体 reconciliation 需要独立、可回滚的数据任务。
- 不新增 Identity Registry 或数据库 Migration。
- 不改变评论采样、分页、费用、Relevance、Decision Policy。
- 不新增 TikHub Endpoint，不改变 App/Web fallback 策略。
- 不为当前 TikHub Capability 尚未采集的 B站动态/opus、微博独立 `ttarticle` 伪造跨来源身份保证。

# 必须保持不变

- Canonical `external_content_id` 仍是数据库稳定内容身份和 Comment 归属身份。
- Provider lookup identity 只决定外部请求参数；Detail/Comment Mapper 必须写回稳定 Content 身份。
- Raw Artifact、Provider Attempt、Candidate、Content Ingestion 的事务与来源约束保持现状。
- 不升级依赖，不新增数据库表。

# 方案比较与决策

1. **采用：平台稳定身份规范化 + typed Provider locator。** 对可确定性规范化的平台 ID 直接统一稳定身份；对 Provider 内部还存在第二 ID 的情况，通过 typed `alternate_ids` 显式区分请求 locator 与内部审计 ID。无需新表，能满足当前五平台正式 Capability。
2. 强制把所有 Provider Raw ID 原样作为 `external_content_id`。快手数字内部 `photo_id` 与公开分享 `photoId` 不同、B站 BV/AID 也不同，会破坏 Excel/TikHub 去重，不采用。
3. 新建全局 Identity Registry 并自动合并历史实体。可覆盖历史脏数据，但需要 Schema/Migration、冲突裁决、并发合并与回滚机制；当前生产尚未 Go-Live，本 Change 不为未证明存在的历史生产数据扩大到该方案。

用户要求以实际 Excel + TikHub API 验证后再合并。本 Change 因快手真实双 ID 事实升级为 L3；采用方案 1，并把历史 pre-fix 数据作为明确兼容边界而非静默猜测合并。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Excel 或 TikHub 获取到的笔记/作品 ID 能用于详情、一级评论和二级回复补采 | user:2026-08-24-comment-identity | satisfied | `runtime.py` typed locator + `collection_scope.py` seed/评论透传 + Unit/Integration 回归 |
| R2 | Excel 与 TikHub 当前支持内容的稳定 ID 对齐，以实现跨来源去重 | user:2026-08-24-excel-tikhub-dedup | satisfied | B站 BV→AID；快手公开 share photoId；真实 Provider Probe/诊断及 Mapper 回归 |
| R3 | 多来源 identity 共同保留且不破坏 Content/Comment 现有归属架构 | user:2026-08-24-comment-identity | satisfied | `content_complete.py` 按 id_type/freshness upsert；PostgreSQL Integration |
| R4 | 使用原 Excel 数据和 TikHub API 实际验证，确认后再合并 | user:2026-08-24-real-provider-validation | satisfied | 原 Excel fixture + TikHub Runs `32684540763`、`32685203168`、`32686063018` |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 无前端/HTTP Contract 行为变化。 |
| Backend/API/PostgreSQL Integration | required | Batch target typed identity、alternate_ids freshness merge、跨来源收敛均由真实 PostgreSQL Integration 覆盖。 |
| Contract / Generated Client | not_applicable | 不修改 HTTP/OpenAPI/generated client。 |
| Real Full-stack Golden Path | not_applicable | 风险集中在内部 Collection/Content/Provider identity 边界；PostgreSQL Integration + Real Provider Probe 提供更直接证据。 |
| Real Provider Probe | required | 5 平台原 Excel Probe 发现并定位快手差异；快手真实 Search 证明双 ID；修复后原 Excel 快手 Detail/Comments 均 HTTP 200 且父 Content 一致。 |
| Docs / Governance / Other | required | Appendix 08、L3 Change、Secret/Docs/Ready Check 同步验证。 |

# Completion Audit

- [x] upstream_re_read：已重新读取当前 `main` AGENTS、Reliable Vibe Coding、Blueprint 03/07/08、Appendix 08、Runtime/Mapper/Repository/测试事实。
- [x] change_coverage：已覆盖 Excel/TikHub 稳定身份、typed locator、评论/回复、alternate_ids 合并、B站 BV/AID、快手双 ID、真实 Provider 验证与历史兼容边界。
- [x] reverse_audit：已从 Excel URL → Identity Resolver → Batch target → Detail → Comments → SubComments → Canonical/Content Owner 反向核对，也从 TikHub Search → Mapper → Content → Excel 再导入核对去重主身份。
- [x] unresolved_cleared：R1—R4 均有实现与运行证据；当前范围没有 `not_satisfied`。

# 任务

- [x] 调查 Excel identity、TikHub Operation/Mapper、Batch enrichment target、Content alternate_ids 持久化事实。
- [x] 建立失败回归/真实 Probe，确认快手双 ID 根因而非猜测修补。
- [x] 实现 Runtime typed locator 与 Batch seed/评论/回复透传。
- [x] 实现跨来源 alternate_ids 按 id_type + observed_at 合并。
- [x] 实现 B站 BV→AID 与快手公开分享 ID 收敛。
- [x] 同步数据入口文档。
- [x] 执行目标 Unit、PostgreSQL Integration、Ruff、mypy、Docs/Secret/Ready 验证。
- [x] 完成需求符合性与代码质量两阶段 Review、Requirement Traceability 与 Completion Audit。

# 验证证据

- 真实 5 平台 Probe Run `32684540763`：小红书、抖音、微博、B站通过；快手以“Excel ID 与 TikHub Detail 原生 ID 不一致”失败，形成有效 Red 证据，没有放宽断言掩盖问题。
- 快手真实 Search 诊断 Run `32685203168`：仅 1 次请求，证明同一条 Raw 同时返回数字内部 `photo_id` 与公开 `share_info.photoId(3x...)`，且二者不同。
- 快手修复后原 Excel Probe Run `32686063018`：原 Excel row 101，Detail HTTP 200、Comments HTTP 200，稳定 Content/评论父级一致，数字 Provider photo_id 被保留，请求数 2。
- Runner 提交 `88047397880f13599d80a06934607ac9030371bc` 前执行快手目标 Unit、相关 Operation/真实形状 Mapper、Ruff、mypy；未通过不会产生该验证提交。
- 最终实现 HEAD `d1a2eaf5b0b850203eb41f0a34b8bc34fcd19db3` 的 16 条永久 workflow 全部 success，包括 Change Completion Gate、主 CI、Stage 5A–5D、Stage 6、Stage 7、Full-stack、Windows Compose 和 Deployable Stack。

# 文档影响

- `docs/appendix/08_数据入口与统一入库实现.md`：明确稳定 Content ID 与 Provider lookup identity 分离，以及 B站、快手的实际身份规范化和当前不支持内容类型边界。

# 兼容、部署与回滚

- 无 Schema/Migration、无依赖升级、无 HTTP Contract 变化。
- 新/重新摄取的快手 Search 会以公开分享 `photoId` 作为稳定 ID；旧代码已经落库的数字快手 `external_content_id` 不会被本 Change 自动改写或猜测合并。
- 当前项目尚未完成 Production Go-Live；若某环境已经保留 pre-fix 快手业务数据，发布后依赖跨来源去重前应重新摄取或另建有审计/回滚的历史 reconciliation，不得假定旧数字 ID 已自动迁移。
- 回滚可整体回滚本 Change 的 Mapper/Resolver/Runtime/Repository 行为；没有 Schema downgrade 步骤。回滚后新写入的公开快手 ID 数据仍是合法 text 身份，但会恢复旧的跨来源不一致行为。

# 交付

- Commit：实现 PR #188 最终 HEAD `d1a2eaf5b0b850203eb41f0a34b8bc34fcd19db3`。
- PR：#188 已于 2026-08-24 合并到 `main`，merge commit `c9dc6c3e933210fdf1eebfeb9b3332b2747c0792`。
- 发布：未部署；本 Change 无 Schema/Migration、依赖或 HTTP Contract 变化，生产数据历史 reconciliation 不在本 Change 范围内。
