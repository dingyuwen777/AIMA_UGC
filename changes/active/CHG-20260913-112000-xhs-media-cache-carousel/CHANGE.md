---
schema: coding-change/v1
id: CHG-20260913-112000-xhs-media-cache-carousel
title: 小红书图片缓存与声音广场多图轮播
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feat/xhs-media-cache-carousel-20260913
created: 2026-09-13
updated: 2026-09-13
completion_gate: required
depends_on: []
affected_areas:
  - collection
  - content
  - storage
  - api
  - frontend
  - figma
  - docs
affected_paths:
  - backend/src/aima_ugc/bootstrap/content_media_cache.py
  - backend/src/aima_ugc/bootstrap/content_media_http.py
  - backend/src/aima_ugc/bootstrap/media_cache_collection_scope.py
  - backend/src/aima_ugc/bootstrap/artifact_cleanup.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/entrypoints/api_main.py
  - backend/src/aima_ugc/modules/content/media_cache_tables.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_media_cache.py
  - backend/src/aima_ugc/platform/storage/retention.py
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/20260913_0052_content_media_cache.py
  - frontend/src/features/voice-plaza/api.ts
  - frontend/src/main.ts
  - frontend/src/shared/styles/voice-plaza-media-carousel.css
  - tests/
  - docs/collection/README.md
  - docs/collection/xiaohongshu_media_cache.md
  - changes/active/CHG-20260913-112000-xhs-media-cache-carousel/CHANGE.md
contracts:
  - 业务 OpenAPI/generated client 无变化；内部同源媒体资源路由 include_in_schema=false
data_changes:
  - 新增 content_media_cache_entries，保存 Content 媒体位置到可丢弃缓存 Artifact 的当前绑定
---

# 变更摘要

- 小红书辅助补采完整执行既有 Detail/Comments/SubComments 后，以 best-effort 方式预热图文图片缓存；缓存失败不改变原 Collection 结果。
- 原始 `content_media.url` / `external_media_id` 继续作为长期媒体事实；服务器缓存只是可删除、可重建的派生字节。
- 媒体缓存 TTL 30 天，单张最大 10 MiB；总缓存超过 30 GiB 时按最旧缓存优先回收到 24 GiB，复用现有每小时 Artifact housekeeping。
- 声音广场详情保持 610 px 干净抽屉；小红书多图通过同源缓存 URL 以原生横向 scroll-snap 展示，主图 `contain`、多图轻微露出下一张，不引入额外 Carousel/UI 依赖。
- 正式 Figma `EAPm8KVarUe7BFTSnzvOpT / 4627:7429` 已修改共享 Detail Drawer body Owner，并通过正式 1440×900 画板 Fresh Screenshot 复核。

# 目标、范围与非目标

## 成功标准

- [x] 小红书图片只允许从受信任 xhscdn / ci.xiaohongshu.com 资源获取，请求最终规范为 HTTPS，并拒绝任意 URL 代理、重定向、非栅格图片与超 10 MiB 响应。
- [x] 辅助补采先完成既有 Detail/Comments/SubComments，再 best-effort 预热图片；缓存失败不阻塞评论，不改变既有补采终态。
- [x] 浏览器通过 AIMA 同源媒体资源读取小红书图片；缓存 miss 可按数据库中的原始 URL 重建，源 URL/fileid 不因缓存清理丢失。
- [x] 缓存 Artifact 创建时 TTL 为 30 天；Housekeeping 到期清理，并在媒体缓存总量超过 30 GiB 时按最旧优先回收到 24 GiB。
- [x] 声音广场详情多图可水平滑动，主图完整呈现、留白克制、与现有 Drawer 信息层级一致；图片失败不会破坏正文、AI 信息和评论区。
- [x] Figma 正式页面与代码行为同步，Fresh Screenshot 未发现裁切、重叠、拥挤或开发工具感。
- [ ] PR #477 完整 CI、独立 Review 与合并后 main 新鲜验证属于 Ready 后的交付门禁；只有这些全部通过才执行/声明最终完成。

## 范围

- Xiaohongshu Content image cache；Artifact TTL/容量回收；内部同源媒体读取；辅助补采预热；声音广场详情媒体展示；Figma 与必要文档/测试。

## 非目标

- 不缓存视频、评论图片或其它平台媒体。
- 不把图片字节存入 PostgreSQL，不永久归档所有图片，不把缓存失败升级为 Provider/Collection 失败。
- 不新增前端 UI Library、轮播依赖或第二套文件存储系统。
- 不改变 TikHub Endpoint、定价、评论分页/父子关系或 AI 打标语义。

## 必须保持不变

- `content_media.url` 和 Provider Raw 保留第三方原始事实；缓存是派生副本。
- 既有 ArtifactStore 的路径安全、原子写入、SHA-256 与删除状态机继续作为文件字节 Owner。
- 现有 610 px Detail Drawer、正文/AI/人工确认/评论的主要信息层级继续保持。
- 缓存行为不依赖 TikHub API Key，也不把任何 Secret 写入数据库、日志、URL 或前端。

# 已确认关键决策

1. **方案 A（采用）**：Artifact-backed 可重建缓存 + 独立 `content_media_cache_entries` 当前绑定；复用现有 Artifact TTL/Housekeeping，原始 URL 与缓存生命周期解耦。
2. 方案 B：直接给 `content_media` 增加 cache artifact 字段。改动较小，但把可丢弃缓存状态耦合到业务媒体事实，刷新/清理与并发语义更差。
3. 方案 C：单独文件目录按 mtime/容量清理。实现快，但会形成第二套文件生命周期与安全边界，不采用。
4. 容量采用 high-water / low-water：30 GiB 触发、24 GiB 停止；先正常 TTL 回收，再做容量回收。
5. 不新增轮播运行时依赖，使用浏览器原生横向滚动/scroll-snap 与现有 Vue 页面结构。
6. 同源图片字节路由为产品内部资源路由，不加入业务 OpenAPI/generated client；正式 Content Detail Contract 仍只暴露媒体事实。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 小红书辅助补采后服务器缓存帖子图片，缓存可重建且不影响评论补采 | user:xhs-media-cache-carousel | satisfied | `media_cache_collection_scope.py` 在 `super().execute()` 完成后仅对成功/部分成功 enrichment 预热；`content_media_cache.py` 实现 hit/miss 重建；对应 Collection/API 单元测试已随 PR 提交 |
| R2 | 图片缓存 30 天，最大 30GB，超过后回收到 24GB，避免无限增长 | user:xhs-media-cache-carousel | satisfied | `retention.py` 固化 30 天、10 MiB、30/24 GiB；`artifact_cleanup.py` 复用每小时 housekeeping 做 TTL 后容量回收；首轮 Runtime Acceptance 已通过 canonical Compose/Migration/持久化主步骤 |
| R3 | 声音广场多图左右滑动，界面干净整洁、大方、美观 | user:xhs-media-cache-carousel | satisfied | `voice-plaza/api.ts` 投影同源 preview；`voice-plaza-media-carousel.css` 使用原生 scroll-snap/FIT；正式 Figma `4627:8510` Fresh Screenshot 1440×900 复核主图完整、Drawer 层级与固定操作区未破坏 |
| R4 | 同步正式 Figma 页面 4627:7429，并保持设计/代码一致 | user:xhs-media-cache-carousel | satisfied | 已修改共享 Owner `4861:31020` / media `4627:8557` / image `4627:8558`，新增第二图示例 `5362:14408`；正式 Detail Drawer `4627:8510` Fresh Screenshot 复核通过 |
| R5 | 代码验证无问题后合并主分支 | user:xhs-media-cache-carousel | explicitly_deferred | 用户已授权端到端交付；merge 只能在 PR #477 required CI 与独立 Review 全绿后执行，随后再验证 main/Change Archive，属于 Ready 后 post-merge finalization |

# 实施与验证计划

1. 新增缓存绑定表/Migration 与 Repository；缓存 Artifact 使用既有 Store/Service，不保存图片 BLOB。
2. 实现小红书 CDN URL 安全规范化、图片下载上限、cache hit/miss、重建与同源媒体响应。
3. 用 Collection Scope 装饰器在辅助补采原流程成功/部分成功返回后执行 best-effort 预热，确保评论请求先完成。
4. 扩展 Artifact housekeeping：30 天 TTL 复用既有过期删除；超过 30 GiB 时按最旧缓存回收至 24 GiB。
5. 在最终 API assembly 安装内部媒体路由，并在 Voice Plaza API adapter 中把小红书 image `preview_url` 投影为同源媒体 URL。
6. 前端使用原生横向 scroll-snap 打造克制的多图浏览区；图片 `contain`，单图不制造额外控制噪音。
7. 同步 Figma 实际 Owner；执行正式画板 Fresh Screenshot / Canvas-level Review。
8. Ready 后由 PR #477 执行完整后端、PostgreSQL、Contract、前端、Browser、Build CI 和独立 Review；全部绿后合并 `main` 并做 post-merge 验证。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 单元 / Component | required | URL allowlist、图片类型/10MiB、TTL/容量、媒体路由、Collection prefetch；完整执行由 Ready 后 PR CI 证明 |
| Contract / API | required | 内部媒体路由不进入 OpenAPI，Content Detail/generated client 不漂移；完整执行由 Ready 后 PR CI 证明 |
| PostgreSQL / Persistence | required | 0052 Migration、cache binding/Artifact 生命周期；首轮 Runtime canonical Compose 主步骤已通过，PR CI 再执行 PostgreSQL Integration |
| Browser Mock Acceptance | required | 单图/多图、Detail Drawer 其它信息不回归；Figma Fresh Screenshot 已验证视觉，Browser 自动验收由 Ready 后 PR CI 证明 |
| Collection Integration | required | 辅助补采先完成原 Scope 后 best-effort 预热；缓存异常不改变结果；单元用例已提交，完整执行由 Ready 后 PR CI 证明 |
| External Provider Probe | not_applicable | 缓存链路以受控 HTTP Mock 验证，不为回归再次调用付费 TikHub |
| Build / Runtime | required | Developer Tooling run #886 已成功；首轮 Runtime run #1945 canonical Compose/host-root 主步骤成功；完整 CI/Runtime 由 Ready 后新 head 证明 |
| Figma / Docs / Governance | required | Figma Owner 写入和 `4627:8510` Fresh Screenshot 已完成；新增 `docs/collection/xiaohongshu_media_cache.md` 并接入 collection README；PR Requirement Source/governance 首轮通过 |

# 风险、兼容、迁移、部署与回滚

| 项目 | 结论 |
| --- | --- |
| 安全 | 媒体 URL 是外部 I/O；仅 allowlist XHS Host、禁止 redirect/任意代理、限制栅格类型与 10 MiB、`trust_env=False` |
| 性能 | 预热发生在评论链路完成后且 best-effort；API cache miss 允许懒重建；文件不进入数据库 |
| 容量 | TTL 30 天 + 30/24 GiB 双阈值，现有 Scheduler 每小时 Housekeeping 执行；单次容量回收最多 10,000 项 |
| 兼容性 | Content 原始 URL/既有业务 Contract 字段保留；业务 OpenAPI/generated client 无变化；其它平台媒体不投影同源缓存 |
| 数据 / Migration | 新增可丢弃缓存绑定表 0052；不回写历史业务媒体，历史记录首次查看时可懒缓存 |
| 部署 | 正常 Backend/Frontend 发布并执行 Alembic upgrade；Artifact 根目录维持现有可写挂载，无新增存储卷 |
| 回滚 | 先回滚应用代码，再 downgrade 0052 删除缓存绑定表；缓存 Artifact 字节可由 Housekeeping/人工清理，不影响 Content 原始事实 |

# 完成审计

- [x] upstream_re_read：已重读本轮用户确认的 30 天/30GB/美观/Figma/合并要求、当前 Change、Content/Artifact/Collection/API/Frontend/Figma Owner 与任务基线 main。
- [x] change_coverage：R1—R4 已映射到真实实现与 Figma 证据；R5 明确绑定 PR #477 全绿后的 post-merge finalization，没有把未来 merge 伪装成已完成。
- [x] reverse_audit：已反向核对 `Collection→prefetch→Artifact`、`Content media→内部 media route→Voice Plaza`、`TTL/30GiB→hourly housekeeping` 三条链路；业务 OpenAPI 与 TikHub 主链保持不变。
- [x] unresolved_cleared：实现侧无已知未满足 requirement；完整 PR CI / 独立 Review 是 Ready 后 merge gate，若出现失败则立即回到实现修复而不是继续合并。

# 两阶段 Review

## Review A1：上游要求 → Change

已重新核对用户确认的 30 天 TTL、30 GiB 上限、24 GiB 回落、多图横滑、美观、Figma 同步和最终合并 main，均有对应实施/验证边界；merge/main 验证按交付顺序明确后置。

## Review A2：Change → 实现、测试与文档

实现、测试用例、Migration、长期文档和 Figma Owner 已覆盖 Change 当前范围；PR #477 的完整 CI 与独立 Review 作为 Ready 后强门禁继续执行，任何阻断 Finding 都会回到本 Change 修复。

# 完成证据与交付状态

- 当前状态：`ready_for_review`，不是最终完成。
- 基线：`main@6651a0fb484a58911790bb590b839fd670142233`。
- PR：`#477`；首轮 `CI #4878` 的 Requirement Source / governance 通过，仅按预期停在 in_progress Change readiness；Developer Tooling run `#886` success。
- Runtime：首轮 `Runtime Acceptance #1945` 已通过 canonical Compose startup/security/persistence/recovery、repository-relative host-root 等主步骤；后续 head 会重新执行完整 Runtime。
- Figma：共享 Detail Drawer body Owner `4861:31020` 已同步；正式 `4627:8510` Fresh Screenshot 为 1440×900，视觉复核主图完整、下一图轻微露出、信息层级/固定底部操作无异常。
- 文档：`docs/collection/xiaohongshu_media_cache.md` 已建立并从 `docs/collection/README.md` 导航。
- 下一门禁：当前 head 的完整 PR CI / Runtime / PostgreSQL / Browser + 独立 Review；全部绿后才执行 squash merge 与 main 新鲜验证。
