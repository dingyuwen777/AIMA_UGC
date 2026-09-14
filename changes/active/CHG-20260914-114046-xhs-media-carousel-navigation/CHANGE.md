---
schema: coding-change/v1
id: CHG-20260914-114046-xhs-media-carousel-navigation
title: 修复小红书多图画廊鼠标切换
level: L2
status: in_progress
owner: Codex
branch: fix/xhs-media-carousel-navigation
created: 2026-09-14
updated: 2026-09-14
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - docs
affected_paths:
  - frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue
  - frontend/src/shared/ui/AimaIcon.vue
  - frontend/src/shared/styles/voice-plaza-media-carousel.css
  - frontend/tests/content-detail-supplement-status.spec.ts
  - frontend/e2e/voice-plaza-media-carousel.spec.ts
  - docs/collection/xiaohongshu_media_cache.md
  - changes/active/CHG-20260914-114046-xhs-media-carousel-navigation/CHANGE.md
contracts:
  - Content Detail、OpenAPI 与 generated client 不变；只增强既有小红书缓存媒体画廊交互
data_changes:
  - 无 Schema、Migration、业务数据或缓存生命周期变化
---

# 变更摘要

为声音广场内容详情中的小红书多图缓存画廊增加清晰、可点击的上一张/下一张入口与当前位置提示，让普通鼠标和键盘用户能够访问全部图片，同时保留触屏与触控板的原生横向滑动。

# 目标、范围与非目标

## 成功标准

- [ ] 多图缓存画廊显示上一张、下一张控件，点击后逐张切换并能访问全部图片。
- [ ] 画廊显示当前位置；首张禁用上一张，末张禁用下一张，原生滑动后状态同步。
- [ ] 控件复用现有视觉 Token 与图标体系，具备中文无障碍标签和键盘操作。
- [ ] 单图、小红书非内部缓存媒体和其它平台原有媒体布局与链接行为不变。
- [ ] 组件与 Browser Mock 回归、前端质量门禁、PR CI、合并后 main 新鲜验证和 Change 归档全部完成。

## 范围

- 声音广场内容详情的小红书内部缓存多图画廊。
- 对应共享图标、画廊样式、组件测试、浏览器用户路径和媒体缓存说明。

## 非目标

- 不改 Content Detail Contract、OpenAPI、generated client、后端媒体缓存、Artifact、数据库或 Provider。
- 不为其它平台强制启用相同轮播控件。
- 不引入 Carousel/UI Library，不实现高风险的鼠标拖拽手势或改变图片点击查看行为。

## 必须保持不变

- 小红书图片展示和点击继续优先使用 AIMA 同源 `preview_url`。
- 触屏与触控板继续使用原生横向滚动和 `scroll-snap`。
- 图片继续使用 `object-fit: contain`，不裁切产品主体。

# 已确认关键决策

1. **采用**轻量左右按钮 + 当前序号：普通鼠标有明确入口，键盘可操作，同时不替换浏览器原生滑动。
2. 不采用鼠标按住拖拽：需要处理锚点误点击、拖拽阈值和文本/图片默认行为，超出本缺陷最小范围。
3. 控件只对两张及以上的小红书内部缓存媒体出现；单图和其它平台保持现状。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 多张图片可以左右切换并查看其它图片 | #480 / 用户截图与请求 | not_satisfied | 待补失败 Browser 回归与实现 |
| R2 | 新增 UI 与现有风格一致、简单大方、美观 | #480 / 用户请求 | not_satisfied | 待复用现有 Token、图标和视觉验收 |
| R3 | 不破坏原生滑动、单图和其它平台兼容行为 | #480 / Issue AC2—AC3 | not_satisfied | 待组件与 Browser 回归 |
| R4 | 本地验证无问题后合并远程主分支 | #480 / 用户请求 | explicitly_deferred | PR CI、Review、merge、main-fresh 与归档按交付顺序执行 |

# 实施与验证计划

1. 先补组件与 Browser Mock 失败回归，稳定复现多图没有可点击切换入口。
2. 在现有画廊内增加左右按钮、当前位置和滚动状态同步，复用现有 Token/图标，不改变数据链。
3. 运行目标测试、完整前端测试、lint、typecheck、build 与浏览器视觉/交互验收。
4. 同步媒体缓存说明，完成需求追溯、反向能力审计、两阶段 Review、PR/CI/merge/main-fresh/归档。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| Component | required | 多图控件、首尾状态、单图与其它平台兼容 |
| Browser / Workflow Acceptance | required | 鼠标点击前后切换、序号同步、全部图片可达、原生滚动后状态同步 |
| Contract / API | not_applicable | 不修改公共 Contract、请求或 generated client |
| PostgreSQL / External Provider | not_applicable | 不修改缓存、数据库或 Provider |
| Build / Static Quality | required | Vitest、Playwright、ESLint、TypeScript/Vue、Vite build |
| Docs / Governance | required | 媒体缓存说明、Change 完成检查、Review 与 PR CI |

# 风险、兼容、部署与回滚

- 风险：滚动位置与序号可能不同步；通过真实浏览器点击和原生滚动回归覆盖。
- 兼容：公共 API、缓存资源、Schema、依赖和其它平台行为不变。
- 部署：仅需更新 Frontend 静态产物；不需要数据迁移或后端重启语义变化。
- 回滚：回滚前端组件、共享图标、画廊样式和文档即可，无数据回滚。

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 两阶段 Review

## Review A1：上游要求 → Change

待实现完成后独立重建 #480 与本轮用户要求并复核覆盖。

## Review A2：Change → 实现、测试与文档

待生产实现、回归和文档完成后执行。

# 完成证据与交付状态

- 当前状态：`in_progress`。
- 基线：`origin/main@48daeb29a8b33f1078b4a17932830f7f56fc1344`。
- Requirement Source：Issue #480。
