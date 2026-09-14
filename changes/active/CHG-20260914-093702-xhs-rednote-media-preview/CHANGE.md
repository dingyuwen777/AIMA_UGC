---
schema: coding-change/v1
id: CHG-20260914-093702-xhs-rednote-media-preview
title: 修复小红书缓存图片网页内联展示
level: L3
status: active
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

- [ ] 真实 `*.rednotecdn.com` 小红书图片 URL 通过既有 HTTPS、端口、userinfo、类型和 10 MiB 安全校验后可缓存并返回浏览器。
- [ ] 相似恶意后缀域名仍被拒绝，缓存端点不退化为任意 URL proxy。
- [ ] 详情画廊直接显示同源缓存图片；点击图片打开同源缓存资源，不触发原始 CDN 的附件下载语义。
- [ ] 当前截图对应 Content 的媒体端点返回 `image/webp` 与 `X-AIMA-Media-State: available`。

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

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 缓存图片应在网页详情中直接显示 | user:2026-09-14 当前请求 | not_satisfied | 待后端 allowlist 修复、目标测试和真实媒体端点复测 |
| R2 | 点击图片不再得到下载链接 | user:2026-09-14 当前请求 | not_satisfied | 待画廊 href 使用同源 preview URL，并以 SSR 测试验证 |
| R3 | 保持缓存安全边界，不能成为任意代理 | AGENTS.md 安全规则；既有媒体缓存设计 | not_satisfied | 待 allowlist 正反例单测与真实响应 MIME 探测 |

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

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared
