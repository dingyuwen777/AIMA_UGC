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
  - frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentCommentSection.vue
  - frontend/src/main.ts
  - frontend/src/shared/styles/voice-plaza-media-carousel.css
  - frontend/tests/content-comment-section.spec.ts
  - tests/
  - docs/blueprint/03_数据库与文件存储.md
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
- 未做辅助补采不会让详情退化为错误态：已有媒体 URL 时首次打开按需懒缓存，无媒体事实时不渲染大空槽，媒体源不可用时显示固定同源占位图，评论未采集时显示中性状态。
- 正式 Figma `EAPm8KVarUe7BFTSnzvOpT / 4627:7429` 已修改共享 Detail Drawer body Owner，并新增未补采/媒体回退状态规格 `5363:2514`；两处均通过 Fresh Screenshot 复核。

# 目标、范围与非目标

## 成功标准

- [x] 小红书图片只允许从受信任 xhscdn / ci.xiaohongshu.com 资源获取，请求最终规范为 HTTPS，并拒绝任意 URL 代理、重定向、非栅格图片与超 10 MiB 响应。
- [x] 辅助补采先完成既有 Detail/Comments/SubComments，再 best-effort 预热图片；缓存失败不阻塞评论，不改变既有补采终态。
- [x] 浏览器通过 AIMA 同源媒体资源读取小红书图片；缓存 miss 可按数据库中的原始 URL 重建，源 URL/fileid 不因缓存清理丢失。
- [x] 缓存 Artifact 创建时 TTL 为 30 天；Housekeeping 到期清理，并在媒体缓存总量超过 30 GiB 时按最旧优先回收到 24 GiB。
- [x] 声音广场详情多图可水平滑动，主图完整呈现、留白克制、与现有 Drawer 信息层级一致；图片失败不会破坏正文、AI 信息和评论区。
- [x] 未进行辅助补采或评论采集的帖子仍保持产品化可读：有媒体 URL 时懒缓存，无媒体时不占大块空白，媒体源失败显示统一占位图，评论未采集与平台 0 评论使用不同中性状态。
- [x] Figma 正式页面与代码行为同步，Normal Drawer 与未补采/回退状态 Fresh Screenshot 均未发现裁切、重叠、拥挤或开发工具感。
- [ ] PR #477 完整 CI、独立 Review 与合并后 main 新鲜验证属于 Ready 后的交付门禁；只有这些全部通过才执行/声明最终完成。

## 范围

- Xiaohongshu Content image cache；Artifact TTL/容量回收；内部同源媒体读取；辅助补采预热；未补采懒缓存与媒体失败占位；声音广场详情媒体/评论状态展示；Figma 与必要文档/测试。

## 非目标

- 不缓存视频、评论图片或其它平台媒体。
- 不把图片字节存入 PostgreSQL，不永久归档所有图片，不把缓存失败升级为 Provider/Collection 失败。
- 不新增前端 UI Library、轮播依赖或第二套文件存储系统。
- 不改变 TikHub Endpoint、定价、评论分页/父子关系或 AI 打标语义。
- 不因为帖子未补采而自动触发付费 TikHub 评论请求。

## 必须保持不变

- `content_media.url` 和 Provider Raw 保留第三方原始事实；缓存是派生副本。
- 既有 ArtifactStore 的路径安全、原子写入、SHA-256 与删除状态机继续作为文件字节 Owner。
- 现有 610 px Detail Drawer、正文/AI/人工确认/评论的主要信息层级继续保持。
- 缓存行为不依赖 TikHub API Key，也不把任何 Secret 写入数据库、日志、URL 或前端。
- “评论尚未采集”只是当前本地覆盖状态，不能被展示成 Provider/Collection 失败。

# 已确认关键决策

1. **方案 A（采用）**：Artifact-backed 可重建缓存 + 独立 `content_media_cache_entries` 当前绑定；复用现有 Artifact TTL/Housekeeping，原始 URL 与缓存生命周期解耦。
2. 方案 B：直接给 `content_media` 增加 cache artifact 字段。改动较小，但把可丢弃缓存状态耦合到业务媒体事实，刷新/清理与并发语义更差。
3. 方案 C：单独文件目录按 mtime/容量清理。实现快，但会形成第二套文件生命周期与安全边界，不采用。
4. 容量采用 high-water / low-water：30 GiB 触发、24 GiB 停止；先正常 TTL 回收，再做容量回收。
5. 不新增轮播运行时依赖，使用浏览器原生横向滚动/scroll-snap 与现有 Vue 页面结构。
6. 同源图片字节路由为产品内部资源路由，不加入业务 OpenAPI/generated client；正式 Content Detail Contract 仍只暴露媒体事实。
7. 辅助补采图片预热只用于降低首次访问延迟；声音广场对已有媒体事实始终支持懒缓存，未采集评论不自动触发 Provider 请求。
8. 媒体源暂不可用时内部路由返回固定静态 SVG 占位图并短缓存 60 秒；没有任何媒体事实时前端直接不渲染媒体区。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 小红书辅助补采后服务器缓存帖子图片，缓存可重建且不影响评论补采 | user:xhs-media-cache-carousel / AC1 | satisfied | `media_cache_collection_scope.py` 在 `super().execute()` 完成后仅对成功/部分成功 enrichment 预热；`content_media_cache.py` 实现 hit/miss 重建；对应 Collection/API 单元测试已随 PR 提交 |
| R2 | 图片缓存 30 天，最大 30GB，超过后回收到 24GB，避免无限增长 | user:xhs-media-cache-carousel / AC2 | satisfied | `retention.py` 固化 30 天、10 MiB、30/24 GiB；`artifact_cleanup.py` 复用每小时 housekeeping 做 TTL 后容量回收；Runtime Acceptance 已持续覆盖 Compose/Migration/持久化链路 |
| R3 | 声音广场多图左右滑动，界面干净整洁、大方、美观 | user:xhs-media-cache-carousel / AC3 | satisfied | `voice-plaza/api.ts` 投影同源 preview；`voice-plaza-media-carousel.css` 使用原生 scroll-snap/FIT；正式 Figma `4627:8510` Fresh Screenshot 1440×900 复核主图完整、Drawer 层级与固定操作区未破坏 |
| R4 | 同步正式 Figma 页面 4627:7429，并保持设计/代码一致 | user:xhs-media-cache-carousel / AC4 | satisfied | 已修改共享 Owner `4861:31020` / media `4627:8557` / image `4627:8558`，新增第二图示例 `5362:14408`；正式 Detail Drawer `4627:8510` Fresh Screenshot 复核通过 |
| R5 | 代码验证无问题后合并主分支 | user:xhs-media-cache-carousel / AC5 | explicitly_deferred | 用户已授权端到端交付；merge 只能在 PR #477 required CI 与独立 Review 全绿后执行，随后再验证 main/Change Archive，属于 Ready 后 post-merge finalization |
| R6 | 未做辅助补采/评论采集的帖子也必须美观可读，且不能把未采集误报为错误 | user:xhs-media-cache-carousel / AC6 | satisfied | 已有媒体通过 `fetchContentDetail()` 同源 preview + media route 懒缓存；`ContentDetailDrawer.vue` 在 `media=[]` 时不渲染媒体区；`content_media_http.py` 对源不可用返回固定占位图；`ContentCommentSection.vue` 区分评论尚未采集与平台 0 评论，`content-comment-section.spec.ts`/`test_content_media_http.py` 覆盖；Figma 状态规格 `5363:2514` Fresh Screenshot 复核四种回退状态无裁切 |

# 实施与验证计划

1. 新增缓存绑定表/Migration 与 Repository；缓存 Artifact 使用既有 Store/Service，不保存图片 BLOB。
2. 实现小红书 CDN URL 安全规范化、图片下载上限、cache hit/miss、重建与同源媒体响应。
3. 用 Collection Scope 装饰器在辅助补采原流程成功/部分成功返回后执行 best-effort 预热，确保评论请求先完成。
4. 扩展 Artifact housekeeping：30 天 TTL 复用既有过期删除；超过 30 GiB 时按最旧缓存回收至 24 GiB。
5. 在最终 API assembly 安装内部媒体路由，并在 Voice Plaza API adapter 中把小红书 image `preview_url` 投影为同源媒体 URL。
6. 前端使用原生横向 scroll-snap 打造克制的多图浏览区；图片 `contain`，单图不制造额外控制噪音。
7. 补齐未补采路径：已有媒体懒缓存、无媒体不渲染、源不可用占位图、评论未采集中性状态与对应回归测试。
8. 同步 Figma 实际 Owner 与未补采/媒体回退状态规格；执行正式画板 Fresh Screenshot / Canvas-level Review。
9. Ready 后由 PR #477 执行完整后端、PostgreSQL、Contract、前端、Browser、Build CI 和独立 Review；全部绿后合并 `main` 并做 post-merge 验证。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 单元 / Component | required | URL allowlist、图片类型/10MiB、TTL/容量、媒体路由、不可用占位、Collection prefetch、未采集评论状态；完整执行由 PR CI 证明 |
| Contract / API | required | 内部媒体路由不进入 OpenAPI，Content Detail/generated client 不漂移；不可用媒体仍为内部资源语义 |
| PostgreSQL / Persistence | required | 0052 Migration、cache binding/Artifact 生命周期、删除后按原始媒体事实可重建 |
| Browser Mock Acceptance | required | 单图/多图/无媒体/评论未采集、Detail Drawer 其它信息不回归；Figma Fresh Screenshot 已验证 Normal 与回退状态视觉，Browser 自动验收由 PR CI 证明 |
| Collection Integration | required | 辅助补采先完成原 Scope 后 best-effort 预热；缓存异常不改变结果；未补采查看不触发评论 Provider 请求 |
| External Provider Probe | not_applicable | 缓存链路以受控 HTTP Mock 验证，不为回归再次调用付费 TikHub |
| Build / Runtime | required | 当前 Python/Node、API/Vite startup、Runtime Compose 与开发工具工作流均由 PR Actions 新鲜证明 |
| Figma / Docs / Governance | required | Figma Normal Owner/`4627:8510` 与回退状态 `5363:2514` 已 Fresh Screenshot；长期媒体缓存文档已纳入未补采行为；Requirement Source/Ready 门禁继续执行 |

# 风险、兼容、迁移、部署与回滚

| 项目 | 结论 |
| --- | --- |
| 安全 | 媒体 URL 是外部 I/O；仅 allowlist XHS Host、禁止 redirect/任意代理、限制栅格类型与 10 MiB、`trust_env=False`；占位 SVG 是固定静态服务器内容，不插入用户输入 |
| 性能 | 预热发生在评论链路完成后且 best-effort；API cache miss 允许懒重建；未补采历史数据首次打开可能有一次图片下载延迟；文件不进入数据库 |
| 容量 | TTL 30 天 + 30/24 GiB 双阈值，现有 Scheduler 每小时 Housekeeping 执行；单次容量回收最多 10,000 项 |
| 兼容性 | Content 原始 URL/既有业务 Contract 字段保留；业务 OpenAPI/generated client 无变化；其它平台媒体不投影同源缓存；未采集评论只改变展示文案不改数据语义 |
| 数据 / Migration | 新增可丢弃缓存绑定表 0052；不回写历史业务媒体，历史记录首次查看时可懒缓存 |
| 部署 | 正常 Backend/Frontend 发布并执行 Alembic upgrade；Artifact 根目录维持现有可写挂载，无新增存储卷 |
| 回滚 | 先回滚应用代码，再 downgrade 0052 删除缓存绑定表；缓存 Artifact 字节可由 Housekeeping/人工清理，不影响 Content 原始事实、评论或 Provider Raw |

# 完成审计

- [x] upstream_re_read：已重读本轮用户确认的 30 天/30GB/美观/Figma/合并要求，以及新增“未做辅助补采/评论采集仍要美观显示”的要求，并重新核对 Content/Artifact/Collection/API/Frontend/Figma Owner 与任务基线 main。
- [x] change_coverage：R1—R4、R6 已映射到真实实现、测试与 Figma 证据；R5 明确绑定 PR #477 全绿后的 post-merge finalization，没有把未来 merge 伪装成已完成。
- [x] reverse_audit：已反向核对 `Collection→prefetch→Artifact`、`Content media→内部 media route→Voice Plaza`、`未补采→lazy cache/neutral comments`、`TTL/30GiB→hourly housekeeping` 四条链路；业务 OpenAPI 与 TikHub 主链保持不变。
- [x] unresolved_cleared：实现侧无已知未满足 requirement；完整 PR CI / 独立 Review 是 Ready 后 merge gate，若出现失败则立即回到实现修复而不是继续合并。

# 两阶段 Review

## Review A1：上游要求 → Change

已重新核对用户确认的 30 天 TTL、30 GiB 上限、24 GiB 回落、多图横滑、美观、Figma 同步、未补采详情回退和最终合并 main，均有对应实施/验证边界；merge/main 验证按交付顺序明确后置。

## Review A2：Change → 实现、测试与文档

实现、测试用例、Migration、长期文档、Figma Normal Owner 与未补采/媒体回退状态规格已覆盖 Change 当前范围；PR #477 的完整 CI 与独立 Review 作为 Ready 后强门禁继续执行，任何阻断 Finding 都会回到本 Change 修复。

# 完成证据与交付状态

- 当前状态：`ready_for_review`，不是最终完成。
- 基线：`main@6651a0fb484a58911790bb590b839fd670142233`。
- PR：`#477`；Requirement Source、Ready、Secret、Docs/Schema Facts、OpenAPI/generated client 和 API/Vite startup 已在多轮 PR Actions 中取得新鲜通过证据；此前失败均已按真实诊断修复，最终 head 仍需完整 CI 收口。
- Runtime / Tooling：Developer Tooling 最新已出现成功 run；Runtime Acceptance 持续执行 canonical Compose/Migration/host-root/Windows overlay，最终以待合并 head 的新鲜结果为准。
- Figma：共享 Detail Drawer body Owner `4861:31020` 与正式 `4627:8510` 已同步；未补采/媒体回退状态规格 `5363:2514` Fresh Screenshot 为 1440×669，四种状态完整无裁切，正常详情与固定底部操作未被改写。
- 文档：`docs/collection/xiaohongshu_media_cache.md` 已建立并从 `docs/collection/README.md` 导航，现已明确预热非前置条件、懒缓存、无媒体、媒体不可用占位及未采集评论语义。
- 下一门禁：当前 head 的完整 PR CI / Runtime / PostgreSQL / Browser + 独立 Review；全部绿后才执行 squash merge 与 main 新鲜验证。
