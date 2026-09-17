---
schema: coding-change/v1
id: CHG-20260916-174631-voice-plaza-compact-overflow
title: 修复声音广场紧凑桌面溢出
level: L2
status: done
owner: dingyuwen777
branch: fix/voice-plaza-compact-overflow-515
created: 2026-09-16
updated: 2026-09-16
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - voice-plaza
affected_paths:
  - frontend/src/app/layouts/AppShell.vue
  - frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaTable.vue
  - frontend/src/shared/styles/responsive.css
  - frontend/e2e/voice-plaza-design.spec.ts
  - frontend/e2e/responsive-layout.spec.ts
  - docs/guides/01_Figma与前端设计开发工作流.md
contracts: []
data_changes: []
---

# 背景与目标

Requirement Source 为 GitHub Issue #515 / AC1–AC4；旧 #501 验收的 1212px 局部横滚是历史基线，不是本轮目标。当前 AppShell 导航项固定宽度略大于侧栏内宽；声音广场表格在 1180/1280 仍强制 1212px，末列详情需横向滚动。本轮只调整紧凑桌面布局，保留宽屏与真实业务流程。

# 范围与不变项

- AppShell 导航填满而不撑出侧栏，仍可纵向滚动。
- 声音广场 1180–1439 使用表头/行一致的 952px 最小宽度；1440 及以上保留 1212px 基线；极窄窗口保留表格局部横滚。
- 保留七列、字号、筛选/排序/Cursor/详情/AI/导出、现有 Vue/Pinia/生成 Client；不改后端 Contract、Schema、依赖或 Figma 文件。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 1180/1280 七列和详情无需横滚，极窄窗口局部滚动兜底 | #515 / AC1 | satisfied | `voice-plaza-design.spec.ts` 断言紧凑窗口七列、日期/详情可见可点击，1100px 仍为表格局部滚动；最终目标回归 25/25 通过 |
| R2 | 公共侧栏导航不横向溢出且交互保持 | #515 / AC2 | satisfied | `responsive-layout.spec.ts` 覆盖六档视口导航 `scrollWidth <= clientWidth`，560px 窄窗口点击“采集策略”路由成功；最终目标回归 25/25 通过 |
| R3 | 1440/1920 列宽基线、表头/行对齐和业务行为保持 | #515 / AC3 | satisfied | 1440/1600/1920/2560 实际浏览器几何断言保留 1212px/标题 422px 基线并校验表头与行；现有详情、筛选、导出等 `voice-plaza-design.spec.ts` 回归通过 |
| R4 | Ready 阶段前端检查及实现↔Figma Compact 核对 | #515 / AC4 | satisfied | 前端 lint/typecheck/build 均退出 0；Unit 28 文件/157 测试通过；目标 E2E 25/25 通过；正式 release-2 Compact 截图与实现 1180 截图核对七列、标题换行和末列可达；PR/current-head CI 与合并后 main CI 属于后续交付门禁，不能在 Ready 阶段伪称通过 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 既有前端单元回归，确保交互行为不变 |
| 接口 / Contract | not_applicable | 本次只改 CSS 和浏览器断言，不改 API/生成 Client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改后端、持久化或外部运行依赖 |
| 用户 / Workflow Acceptance | required | Playwright 覆盖 1180/1280/1440/1920 与窄窗口侧栏、详情可达性 |
| 跨组件 Golden Path | not_applicable | 不改前后端接线；现有浏览器层直接验证此处可观察布局和点击 |
| 外部依赖 Probe | not_applicable | 不改 Provider 或付费服务边界 |
| Build / Package / Runtime | required | 前端 lint/typecheck/unit/build 均退出 0；PR/current-head CI 与合并后 main CI 留待交付阶段验证 |
| Docs / Governance / Other | required | 已同步响应式说明及正式 Figma 文件入口；`check_docs.py`、`check_docs_facts.py` 退出 0；Change Ready 检查与 PR/主分支证据分别按阶段取得 |

# 实施计划

- [x] 补浏览器几何与详情可达性断言；旧实现 1180 标题列宽 422px 与目标 162px 不符，公共导航宽度 156px 大于内宽 155px，Red 均可复现。
- [x] 最小修改 AppShell 与声音广场表格 CSS；同步受影响的响应式说明及正式 Figma 导航。
- [x] 目标及前端回归通过，完成 Compact 设计一致性核对。
- [x] 重读 #515 做完成审计并复核当前差异；未发现阻断项。
- [ ] 取得 PR current-head required CI 后合并；随后验证 main fresh CI、归档 Change 并完成 Issue Closure Audit。

# Completion Audit

- [x] upstream_re_read：Ready 前重读 #515、正式 Figma release-2 Compact 节点/截图、当前 AppShell/Table/测试/CI/项目规则；旧 #501 的横滚验收仅为历史基线。
- [x] change_coverage：A1 从 #515 反查 R1–R4，AC1–AC3 的布局/交互有浏览器断言，AC4 的 Ready 部分有本地检查与设计核对；PR 与 main 新鲜 CI、合并、Issue close 是独立的后续交付门禁，未提前宣称完成。
- [x] reverse_audit：A2 从修改反查公共侧栏六档视口和 560px 路由、声音广场 1100/1180/1280/1440/1600/1920/2560 表头/行/详情、业务对话框与日期/车型/导出路径；不改后端 Contract、Schema、依赖或部署。
- [x] unresolved_cleared：Ready 范围内 R1–R4 均有本轮证据；正式 Normal 截图请求超时，故不宣称全页面像素级核对；宽屏几何由浏览器断言验证。PR/current-head CI、main fresh CI 和归档仍是未完成的交付门禁。

# Ready 阶段验证与剩余交付

- Red：未修改 CSS 时，1180px 标题列实际 422px 而目标为 162px；1180px 侧栏导航 `scrollWidth=156` 大于 `clientWidth=155`，两条新增回归均失败。
- Green：`npm --prefix frontend run test:e2e -- voice-plaza-design.spec.ts responsive-layout.spec.ts`，25/25 通过、退出 0；`npm --prefix frontend run lint`、`typecheck`、`build` 均退出 0；`npm --prefix frontend run test -- --run` 为 28 文件/157 测试通过、退出 0。
- 文档：`python scripts/quality/check_docs.py` 与 `python scripts/quality/check_docs_facts.py` 均退出 0；`git diff --check` 退出 0。
- 设计：已读取 release-2 Compact 1180 正式节点并查看截图；实现 1180 截图显示七列、换行标题和末列详情。正式 Normal 截图请求超时，故 1440/1920 仅声明代码基线及浏览器几何验证，不声明全屏视觉验收。
- 交付剩余：本 Change Ready 不等于 Issue #515/AC4 已全部完成；PR current-head required CI、合并后 main fresh CI、Change 归档及 Issue close 必须依次取得新鲜证据。

# 兼容与回滚

纯前端布局变更，无依赖、配置、Contract、Schema/Migration 或生产部署变化。若验证发现回归，可回滚本次前端提交，不需数据操作。
