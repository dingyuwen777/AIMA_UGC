---
schema: coding-change/v1
id: CHG-20260914-114046-xhs-media-carousel-navigation
title: 修复小红书多图画廊鼠标切换
level: L2
status: done
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

- [x] 多图缓存画廊显示上一张、下一张控件，点击后逐张切换并能访问全部图片。
- [x] 画廊显示当前位置；首张禁用上一张，末张禁用下一张，原生滑动后状态同步。
- [x] 控件复用现有视觉 Token 与图标体系，具备中文无障碍标签和键盘操作。
- [x] 单图、小红书非内部缓存媒体和其它平台原有媒体布局与链接行为不变。
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
| R1 | 多张图片可以通过可点击控件逐张访问 | #480 / AC1 | satisfied | `ContentDetailDrawer.vue` 增加上一张/下一张按钮；修复后组件 5/5、目标 Browser 1/1、全量 Browser 107/107 通过 |
| R2 | 当前位置、首尾禁用和原生滚动后的状态正确同步 | #480 / AC2 | satisfied | 画廊显示 `当前序号 / 总数`，Browser 回归覆盖 1→2→3→2、首尾禁用及手动滚回首张 |
| R3 | 保留触屏/触控板原生滑动，单图和其它平台不受影响 | #480 / AC3 | satisfied | 原 `overflow-x + scroll-snap` 保留；组件回归验证单图和两条抖音媒体不显示控制按钮，链接优先级不变 |
| R4 | 新增 UI 与现有风格一致、简单大方、美观且可访问 | #480 / AC4 | satisfied | 复用 `AimaIcon` 与既有颜色、圆角、间距 Token；按钮含中文 `aria-label`，键盘可聚焦；1440×900 Chrome 截图人工复核无主体遮挡 |
| R5 | 完成本地验证后通过 PR 合并远程主分支 | #480 / AC5 | explicitly_deferred | 本地实现与完整前端回归已满足；PR required CI、merge、main-fresh 与自动归档按 Ready 后交付顺序执行 |

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

- [x] upstream_re_read：已重读用户截图、用户“左右滑动/查看其它图片、UI 保持一致、测试后合并”的要求及 Issue #480 AC1—AC5，并复核现有小红书同源缓存展示、画廊样式与前端测试入口。
- [x] change_coverage：AC1—AC4 已映射到组件、共享图标、样式、组件测试、Browser 用户路径和当前缓存说明；AC5 的本地部分已完成，远程 CI/merge/main-fresh/归档明确保留为 Ready 后门禁。
- [x] reverse_audit：已从 `Content Detail media → withLocalMediaPreview → 同源 img/link → 画廊 → 鼠标/键盘按钮` 正向复核，并从“用户要看到全部图片”反查每张图片可达、序号、首尾状态；后端缓存 Contract 无需改变。
- [x] unresolved_cleared：实现侧无 `not_satisfied`；Review 发现显式 JS `smooth` 会覆盖系统减少动画偏好，已改由现有 CSS 控制并复测。余下 PR CI/merge/main-fresh/归档是正常后置交付门禁。

# 两阶段 Review

## Review A1：上游要求 → Change

已独立重建 #480 AC1—AC5：核心结果是普通鼠标可逐张查看全部图片；状态提示、原生滑动与兼容行为、视觉/无障碍、本地与远程交付分别形成独立要求。当前 Change 没有用自身 checklist 代替 Issue，AC1—AC4 均有实现和当前证据，AC5 只把尚未发生的远程交付明确后置。

## Review A2：Change → 实现、测试与文档

已审查 `origin/main...HEAD` 与最终工作区实现、直接调用链、测试和文档。首次复核发现 `scrollTo({ behavior: 'smooth' })` 会绕过现有 `prefers-reduced-motion` CSS，已移除显式行为并用目标 Browser 回归复测；最终未发现新的阻塞 Finding。测试只把 Browser Mock 声明为前端用户交互证据，没有夸大为真实后端/数据库/Provider 闭环；这些边界本次未修改，判定不适用。

# 完成证据与交付状态

- 当前状态：`ready_for_review`，不是最终完成。
- 基线：`origin/main@48daeb29a8b33f1078b4a17932830f7f56fc1344`。
- Requirement Source：Issue #480。
- PR：#481（Draft，待 Ready commit 推送后转为 Ready）。
- Red：组件回归修复前 `1 failed, 4 passed`；Browser Mock 修复前 `1 failed`，均稳定失败在缺少左右控件/当前位置。
- Targeted Green：组件 `5 passed`；目标 Browser 用户路径多次 `1 passed`，覆盖按钮逐张切换、序号、首尾禁用及原生滚动同步。
- Frontend：Vitest `151 passed`；Browser Mock `107 passed`；ESLint、TypeScript native、Vue typecheck 与 Vite production build 通过。
- 视觉：1440×900 Chrome 截图已人工复核，按钮未遮挡主要内容，下一张露出、序号和禁用态清晰，视觉 Token 与当前 Drawer 一致。
- Docs：`check_docs.py`、`check_docs_facts.py`、`scan_secrets.py` 与 `check_agent_governance.py` 均通过；Docs Impact 为 targeted，仅同步 `docs/collection/xiaohongshu_media_cache.md`。
- Contract / Schema / Migration / Dependency / Backend：均未改变；对应 Integration、Full-stack 与 External Provider Probe 不适用。
- Git：`49fd717a` 锁定失败回归，`ac29bbec` 提交生产修复、测试与文档；Review 修正和本 Ready 证据待最终提交。
