---
schema: coding-change/v1
id: CHG-20260913-112000-xhs-media-cache-carousel
title: 小红书图片缓存与声音广场多图轮播
level: L3
status: in_progress
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
  - frontend/src/main.ts
  - frontend/src/shared/styles/voice-plaza-media-carousel.css
  - tests/
  - docs/collection/01_xiaohongshu.md
  - changes/active/CHG-20260913-112000-xhs-media-cache-carousel/CHANGE.md
contracts:
  - GET /api/v1/contents/{content_id}/media/{position}
data_changes:
  - 新增 content_media_cache_entries，保存 Content 媒体位置到可丢弃缓存 Artifact 的当前绑定
---

# 变更摘要

- 小红书辅助补采完成 Detail/评论链路后，以 best-effort 方式预热图文图片缓存；缓存失败不得改变原 Collection 成功/部分成功结论。
- 原始 `content_media.url` / `external_media_id` 继续作为长期媒体事实；服务器缓存只是可删除、可重建的派生字节。
- 媒体缓存默认 TTL 30 天，单张 10 MiB；总缓存超过 30 GiB 时按最旧缓存优先回收到 24 GiB，复用现有每小时 Artifact housekeeping。
- 声音广场详情仍保持 610 px 干净抽屉；小红书多图以同源缓存 URL 展示为横向 scroll-snap 轮播，支持触控/触控板左右滑动，单图不制造额外控制噪音。
- 正式 Figma `EAPm8KVarUe7BFTSnzvOpT / 4627:7429` 同步相同产品行为与视觉基线。

# 目标、范围与非目标

## 成功标准

- [ ] 小红书图片只允许从受信任 xhscdn / ci.xiaohongshu.com HTTPS 资源获取，拒绝任意 URL 代理、重定向、非图片与超 10 MiB 响应。
- [ ] 辅助补采先完成既有 Detail/Comments/SubComments，再 best-effort 预热图片；缓存失败不阻塞评论，不改变既有补采终态。
- [ ] 浏览器只通过 AIMA 同源媒体接口读取小红书图片；缓存 miss 可按数据库中的原始 URL 重建，源 URL/fileid 不因缓存清理丢失。
- [ ] 缓存 Artifact 创建时 TTL 为 30 天；Housekeeping 到期清理，并在媒体缓存总量超过 30 GiB 时按最旧优先回收到不高于 24 GiB。
- [ ] 声音广场详情多图可水平滑动，主图完整呈现、留白克制、与现有 Drawer 信息层级一致；无图/加载失败不会破坏正文、AI 信息和评论区。
- [ ] Figma 正式页面与代码行为同步，Fresh Screenshot 无裁切、重叠、拥挤或开发工具感。
- [ ] Migration、Contract、后端/前端测试、构建、独立 Review、PR CI 与合并后 main 验证通过后才完成。

## 范围

- Xiaohongshu Content image cache；Artifact TTL/容量回收；媒体读取 API；辅助补采预热；声音广场详情媒体展示；Figma 与必要文档/测试。

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

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 小红书辅助补采后服务器缓存帖子图片，缓存可重建且不影响评论补采 | user:xhs-media-cache-carousel | not_satisfied | 实现与集成验证完成后更新 |
| R2 | 图片缓存 30 天，最大 30GB，超过后回收到 24GB，避免无限增长 | user:xhs-media-cache-carousel | not_satisfied | Retention/Housekeeping 单元与 PostgreSQL 证据完成后更新 |
| R3 | 声音广场多图左右滑动，界面干净整洁、大方、美观 | user:xhs-media-cache-carousel | not_satisfied | 前端 Browser Acceptance 与视觉复核完成后更新 |
| R4 | 同步正式 Figma 页面 4627:7429，并保持设计/代码一致 | user:xhs-media-cache-carousel | not_satisfied | Figma write + Fresh Screenshot + machine audit 完成后更新 |
| R5 | 代码验证无问题后合并主分支 | user:xhs-media-cache-carousel | not_satisfied | PR CI、独立 Review、merge、main 新鲜验证后更新 |

# 实施与验证计划

1. 新增缓存绑定表/Migration 与 Repository；缓存 Artifact 使用既有 Store/Service，不保存图片 BLOB。
2. 实现小红书 CDN URL 安全规范化、图片下载上限、cache hit/miss、重建与同源媒体响应。
3. 用 Collection Scope 装饰器在辅助补采原流程成功/部分成功返回后执行 best-effort 预热，确保评论请求先完成。
4. 扩展 Artifact housekeeping：30 天 TTL 复用既有过期删除；超过 30 GiB 时按最旧缓存回收至 24 GiB。
5. 在最终 API assembly 安装媒体路由，并把 Content Detail 中小红书图片的 `preview_url` 投影为同源媒体 URL。
6. 前端使用原生横向 scroll-snap 打造克制的多图浏览区；补加载失败/空态视觉和响应式行为。
7. 同步 Figma 实际 Owner；执行截图/Canvas-level Review，再跑后端、PostgreSQL、Contract、前端、Browser、Build 与独立 Review。
8. Completion Audit 通过后提交 PR；必需 CI 通过再合并 `main` 并复核 main 新鲜结果。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 单元 / Component | required | URL allowlist、图片类型/10MiB、TTL/容量选择、轮播样式/状态 |
| Contract / API | required | 同源媒体路由、Content Detail preview 投影、OpenAPI/generated client 不漂移 |
| PostgreSQL / Persistence | required | 0052 Migration、cache binding upsert/refresh、Artifact 删除后可重建 |
| Browser Mock Acceptance | required | 单图/多图/图片失败、触控式横向浏览及 Detail Drawer 其余信息不回归 |
| Collection Integration | required | 辅助补采先评论后 best-effort 预热；缓存异常不改变 Collection 终态 |
| External Provider Probe | not_applicable | 缓存链路以受控 HTTP Fake/Mock 验证，不为回归再次调用付费 TikHub |
| Build / Runtime | required | Python format/lint/type/test、frontend lint/test/build、migration/check、相关 Compose/包验证 |
| Figma / Docs / Governance | required | Figma Fresh Screenshot、Canvas audit、文档同步、Completion/Review/PR/CI/main |

# 风险、兼容、迁移、部署与回滚

| 项目 | 结论 |
| --- | --- |
| 安全 | 媒体 URL 是外部 I/O；必须 allowlist Host、禁止任意重定向/代理、限制类型与大小、`trust_env=False` |
| 性能 | 预热发生在评论链路完成后且 best-effort；API cache miss 允许懒重建；文件不进入数据库 |
| 容量 | TTL 30 天 + 30/24 GiB 双阈值，现有 Scheduler 每小时 Housekeeping 执行 |
| 兼容性 | Content 原始 URL/既有 Contract 字段保留；前端其它平台媒体继续使用原 preview/url 语义 |
| 数据 / Migration | 新增可丢弃缓存绑定表 0052；不回写历史业务媒体，历史记录首次查看时可懒缓存 |
| 部署 | 正常 Backend/Frontend 发布并执行 Alembic upgrade；Artifact 根目录需维持现有可写挂载 |
| 回滚 | 先回滚应用代码，再 downgrade 0052 删除缓存绑定表；缓存 Artifact 字节可由 Housekeeping/人工清理，不影响 Content 原始事实 |

# 完成审计

- [ ] upstream_re_read：完成前重读用户要求、当前 Change、相关实现/Contract/Figma 与最新 main。
- [ ] change_coverage：R1—R5 均有本轮新鲜实现或验证证据。
- [ ] reverse_audit：验证 Collection→cache、Detail→media API→browser、TTL/容量→housekeeping 三条反向链路无断点。
- [ ] unresolved_cleared：`not_satisfied` 清零，required 验证均有证据，阻断 Finding 清零。

# 两阶段 Review

## Review A1：上游要求 → Change

进行中。已覆盖 30 天、30/24GB、补采缓存、多图横滑、美观、Figma 同步与合并 main；完成前重新核验。

## Review A2：Change → 实现、测试与文档

进行中。实现与新鲜验证完成后由独立 Review 复核。

# 完成证据与交付状态

- 当前状态：`in_progress`。
- 基线：`main@6651a0fb484a58911790bb590b839fd670142233`。
- Figma 基线：`EAPm8KVarUe7BFTSnzvOpT / 4627:7429`，Detail Drawer 为 610 px；当前媒体区为静态小卡片，本 Change 负责同步升级。
