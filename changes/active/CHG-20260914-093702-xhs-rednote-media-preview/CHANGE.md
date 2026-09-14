---
schema: coding-change/v1
id: CHG-20260914-093702-xhs-rednote-media-preview
title: 修复小红书缓存图片网页内联展示
level: L3
status: ready_for_review
owner: Codex
branch: fix/xhs-rednote-media-preview
created: 2026-09-14
updated: 2026-09-14
completion_gate: required
depends_on: []
affected_areas:
  - content
  - api
  - frontend
  - docs
affected_paths:
  - backend/src/aima_ugc/bootstrap/content_media_cache.py
  - frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue
  - tests/unit/content/test_content_media_cache.py
  - frontend/tests/content-detail-supplement-status.spec.ts
  - docs/collection/xiaohongshu_media_cache.md
  - changes/active/CHG-20260914-093702-xhs-rednote-media-preview/CHANGE.md
contracts:
  - 业务 OpenAPI/generated client 不变；内部同源媒体资源继续返回可内嵌图片字节
data_changes:
  - 无 Schema/Migration/业务数据变化；缓存 miss 会为已存 rednotecdn 源 URL 建立派生 Artifact
---

# 变更摘要

修复当前 TikHub 小红书详情返回 `*.rednotecdn.com` 图片时，被旧 CDN allowlist 拒绝并退化为占位图的问题；详情画廊点击图片继续使用 AIMA 同源缓存资源，不再跳转到带 `Content-Disposition: attachment` 的原始 CDN URL。

# 目标、范围与非目标

## 成功标准

- [x] 真实 `*.rednotecdn.com` 小红书图片 URL 通过既有 HTTPS、端口、userinfo、类型和 10 MiB 安全校验后可缓存并返回浏览器。
- [x] 相似恶意后缀域名仍被拒绝，缓存端点不退化为任意 URL proxy。
- [x] 详情画廊直接显示同源缓存图片；点击图片打开同源缓存资源，不触发原始 CDN 的附件下载语义。
- [x] 当前截图对应 Content 的媒体端点返回 `image/webp` 与 `X-AIMA-Media-State: available`。
- [ ] PR required CI、Review、合并及 main 新鲜验证属于 Ready 后交付门禁；全部通过后才声明最终完成。

## 范围

- 小红书图片缓存 CDN allowlist。
- 声音广场详情媒体链接目标。
- 对应后端、前端回归测试与缓存文档。

## 非目标

- 不扩大到其它平台、视频或评论图片。
- 不改变 Content Detail Contract、OpenAPI、generated client、Schema/Migration、缓存 TTL/容量或 Artifact Owner。
- 不跟随任意重定向，不放宽 MIME、大小和 URL 结构校验。

## 必须保持不变

- `content_media.url` 继续保存原始 Provider 事实；浏览器展示只通过 AIMA 同源缓存资源。
- 只允许已由真实小红书详情响应证明的 CDN 根域及其子域。
- 缓存失败仍不改变正文、评论和采集结果。

# 已确认关键决策

1. **方案 A（采用）**：把真实 Provider 数据中的 `rednotecdn.com` 根域及子域加入现有严格 allowlist，并让小红书画廊显示和点击统一使用 AIMA 同源 `preview_url`；改动最小且继续复用既有缓存、安全和 Artifact 生命周期。
2. 方案 B：前端继续直接打开原始 CDN URL。无需后端改动，但 CDN 当前返回 `Content-Disposition: attachment`，不能满足网页内直接查看，且绕过了缓存目标。
3. 方案 C：新增独立图片代理或改写 `content_media.url`。会形成第二套媒体通道或破坏 Provider 原始事实，成本和兼容风险明显更高，不采用。
4. 画廊链接优先级只对 `xiaohongshu` 改为 `preview_url → url`；其它平台继续保持 `url → preview_url`，避免本修复改变视频原始链接行为。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 缓存图片应在网页详情中直接显示 | user:xhs-rednote-media-preview / AC1 | satisfied | `content_media_cache.py` 接受 `sns-i11.rednotecdn.com`；后端 9 项回归通过；截图 Content 的同源端点返回 200 `image/webp`、`X-AIMA-Media-State: available`，Chrome 实际加载 576×432 图片 |
| R2 | 点击图片不再得到下载链接 | user:xhs-rednote-media-preview / AC2 | satisfied | `ContentDetailDrawer.vue` 对小红书链接优先使用同源 `preview_url`；前端 6 项定向回归通过；Chrome 实际点击后打开 `image/webp` 图片文档而非下载 |
| R3 | 保持缓存安全边界，不能成为任意代理，且其它平台链接行为不变 | docs/collection/xiaohongshu_media_cache.md / AC3 | satisfied | `rednotecdn.com.evil.example` 反例被拒绝；无 redirect、MIME、10 MiB 与 URL 结构原门禁保持；新增抖音原始媒体链接兼容回归并通过 |
| R4 | 本地验证无问题后合并远程主分支 | user:xhs-rednote-media-preview / AC4 | explicitly_deferred | 实现和本地目标链路已满足；PR required CI、Review、merge 与 main-fresh 按用户授权在 Ready 后执行，不能在 Change 入 PR 前伪造完成 |

# 实施与验证计划

1. 先补失败回归：`rednotecdn.com` 正常化正/反例；详情媒体锚点应使用 `preview_url`。
2. 最小修改 CDN allowlist 与画廊链接目标，不改变业务 Contract 或缓存生命周期。
3. 运行后端单元测试、前端定向测试、类型检查/构建，并重建本地容器复测截图对应真实 Content。
4. 同步缓存安全边界和声音广场展示文档，完成需求与反向能力审计。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 单元 / Component | required | URL allowlist 正反例、图片下载响应、画廊同源 href |
| Contract / API | required | 内部媒体路由仍不进入 OpenAPI；Content Detail/generated client 不变 |
| PostgreSQL / Persistence | required | 当前真实 Content 通过已存媒体 URL 建立/读取缓存 Artifact |
| Browser / Workflow Acceptance | required | 详情直接显示图片且点击不触发原 CDN 下载 |
| Real Full-stack Golden Path | required | 当前 Compose 中截图对应 Content 的同源媒体响应可内嵌 |
| External Dependency / Provider Probe | required | 已存真实 CDN URL 有界 GET 返回 200 image/webp；不调用付费 TikHub |
| Build / Runtime | required | Python 定向检查、前端 typecheck/build、Compose 更新后健康检查 |
| Docs / Governance / Other | required | 本 Change、媒体缓存文档、完成检查 |

# 风险、兼容、部署与回滚

- 安全：只增加已由真实 Provider 数据证明的 `rednotecdn.com` 根域/子域；保留 HTTPS、默认端口、无 userinfo、无 redirect、栅格 MIME 和 10 MiB 上限。
- 兼容：公共 Contract、Schema、生成 Client、其它平台媒体行为不变。
- 部署：需重建 Backend 与 Frontend 镜像；首次读取现有 rednotecdn 图片时懒缓存。
- 回滚：回滚两个生产代码文件即可；新增缓存 Artifact 为可丢弃派生数据。

# 完成审计

- [x] upstream_re_read：已重读用户“直接显示图片、点击不下载、缓存用于网页展示”和“本地测试后合并远程主分支”的要求，并复核现有 Content Detail、同源媒体路由、Artifact 缓存、安全门禁与 Windows Compose 正式入口。
- [x] change_coverage：AC1—AC3 均映射到最小实现、后端/前端回归、真实 Content/浏览器证据和长期缓存文档；AC4 明确后置到 PR/merge/main-fresh 交付阶段。
- [x] reverse_audit：已反查 `Provider URL → allowlist → cache Artifact → 同源 HTTP → img` 和 `详情点击 → 同源 href → 浏览器图片文档`；Review 发现并修复“其它平台也优先 preview_url”的范围扩大，新增兼容回归。
- [x] unresolved_cleared：实现侧无 `not_satisfied`；本机全量 Python 中仅有与当前分支无关的 Windows POSIX API 测试和本地 ignored Provider Raw 扫描失败，目标/前端/API/构建/真实浏览器证据均通过，余下 Linux CI/merge/main-fresh 保持 Ready 后门禁。

# 两阶段 Review

## Review A1：上游要求 → Change

已独立重建四项上游要求：网页直接显示、点击不下载、安全边界不退化、本地验证后合并 main。前三项已有当前实现和多层证据；合并要求按项目交付顺序保留在 PR 与 main-fresh 阶段，没有用 Change 自身代替上游要求。

## Review A2：Change → 实现、测试与文档

首次复核发现画廊链接修改会影响所有平台，形成范围外兼容风险；先用抖音媒体回归稳定复现，再把优先级限定为小红书并复测通过。最终 diff 未发现新的阻塞 Finding；公共 Contract、Schema、依赖和缓存生命周期未变，长期文档已同步新增 CDN allowlist 与同源点击语义。

# 完成证据与交付状态

- 当前状态：`ready_for_review`，不是最终完成；基线 `origin/main@a2fab6c80d94b9e1732630ea36c1383a469099f8`。
- Red：后端 allowlist 回归修复前 `1 failed, 5 passed`；前端同源 href 回归修复前 `1 failed, 2 passed`；Review 追加的其它平台兼容回归修复前 `1 failed, 3 passed`。
- Targeted Green：后端媒体缓存/HTTP `9 passed`；前端媒体/详情 `6 passed`。
- Frontend：Vitest `150 passed`；Playwright Browser Mock `106 passed`；lint、TypeScript/Vue typecheck 与 Vite production build 通过。
- Backend/API：API `69 passed`；Mypy `345 source files` 通过；本次 Python 文件 Ruff format/check 通过；Contract 生成 `--check` 通过。
- Runtime/Golden Path：Windows 正式 Compose 镜像构建成功，API/Frontend/PostgreSQL 健康；截图 Content `42cb0f34-414d-4298-849f-699a8110b060` 的媒体端点两次返回 200、80252 字节、`image/webp`、`available`，无 `Content-Disposition`；Chrome 详情图片和点击后图片文档均为 576×432。
- 已知本机非目标失败：完整 Python Unit 为 `991 passed, 8 skipped, 3 failed`，失败仅来自 Windows 无 `os.geteuid/os.chown` 的 POSIX host-preparation 测试；完整 Contract 为 `110 passed, 1 failed`，失败仅来自用户本地 ignored Provider Raw 被平台别名扫描命中。相关失败文件与本分支无差异，远程干净 Linux CI 继续作为合并硬门禁。
- Git：首个本地提交 `60e737f7` 已锁定回归；生产修复、兼容回归、文档与本 Change 待本地 Ready Check 后提交、推送并创建 PR。
