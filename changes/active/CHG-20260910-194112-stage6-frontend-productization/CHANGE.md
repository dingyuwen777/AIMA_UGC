---
schema: coding-change/v1
id: CHG-20260910-194112-stage6-frontend-productization
title: 搜索与品牌车型过滤 Stage 6 前端产品化
level: L3
status: in_progress
owner: chatgpt
branch: feature/stage6-frontend-productization
created: 2026-09-10
updated: 2026-09-10
completion_gate: required
depends_on:
  - CHG-20260909-203000-stage2-brand-vehicle-resolver
  - CHG-20260909-235500-stage3-excel-brand-vehicle-filter
  - CHG-20260910-132342-stage4-tikhub-search-brand-filter
  - CHG-20260910-171533-stage5-query-contract-export
affected_areas:
  - frontend
  - administration
  - collection-strategy
  - ingestion
  - voice-plaza
  - reporting
  - tests
  - docs
  - figma
affected_paths:
  - frontend/src/features/admin-configuration
  - frontend/src/features/collection-strategy
  - frontend/src/features/import-batches
  - frontend/src/features/voice-plaza
  - frontend/e2e
  - tests/fullstack
  - docs/product
  - docs/blueprint
  - docs/appendix
  - docs/guides/01_Figma与前端设计开发工作流.md
  - docs/roadmap/04_搜索与品牌车型过滤实施路线.md
contracts:
  - Stage 2-5 Brand/Vehicle/Competition generated HTTP client
  - Admin Brand and Vehicle management workflow
  - Collection Plan and Import Brand filter workflow
  - Voice Plaza query detail and export workflow
data_changes:
  - 无 Schema/Migration；前端只消费 Stage 2-5 已有 Brand/Vehicle/Competition Contract
---

# 背景与目标

实施 [`docs/roadmap/04_搜索与品牌车型过滤实施路线.md`](../../../docs/roadmap/04_搜索与品牌车型过滤实施路线.md) Stage 6。在 Stage 2—5 已稳定的 Pydantic/OpenAPI/generated client 上，把管理员配置、采集策略、采集运行中心和声音广场改造成一致的 Brand/Vehicle/Competition 用户路径，并从前端删除旧 Keyword Pack↔Vehicle、Global Keyword Relevance 与 Discovery Vehicle Search 职责。

Requirement Source：#434。

# 范围与非目标

- 范围：正式 Figma 基线；四个前端 Feature 的 API/Store/Page/组件；Browser Mock Acceptance；至少一条真实 Full-stack 关键链；受影响长期文档；L3 Review、CI、合并和收口。
- 非目标：不修改后端公共 Contract、Schema/Migration、Provider Operation、AI 规则或依赖；不实现 Brand Manual Review；不执行 Stage 7 旧数据重分类与 Cleanup；不执行真实 TikHub/LLM Probe或生产部署。
- 必须保持：Pydantic → OpenAPI → generated client 唯一类型链；Keyword Pack 只提供 Provider Search Terms；Brand/Vehicle 目录是过滤与分类 Owner；Vehicle merge、人工相关性/车型复核、导入写入策略、Batch Supplement、任务状态、权限和当前前端技术栈保持兼容。

# 已确认方案

1. 先以 Stage 5 generated client 和正式 Figma 为输入，不新增后端接口或手改生成目录。
2. Admin 把品牌、识别词和旗下车型收敛到一个“品牌与车型”Tab；Vehicle 的 Brand 归属继续由 Vehicle API 管理，不在 Brand 编辑页增加第二 Owner。
3. Collection Strategy 与 Runtime 分离 Search Terms 和 Brand Filter；legacy Vehicle 字段仅用于已有记录的只读兼容，不再成为新任务的 Discovery Search Resource。
4. Voice Plaza 使用 Brand/Vehicle 目录 API 提供筛选项，列表/详情直接消费 Stage 5 Read Model，Export 使用 Column Catalog v2 动态列。
5. 广状态由 Browser Mock 覆盖，真实 API/PostgreSQL/Worker/Browser 只保留一条高价值 Brand/Vehicle 配置到筛选/导出的 Golden Path。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Admin 只保留五个目标 Tab，并通过正式 Brand/Vehicle API 管理品牌、识别词与 1:N 车型，不调用词包车型关联 | #434 / AC1 | not_satisfied | 待实现并由 Admin Browser Acceptance、请求断言和旧入口零引用检查证明。 |
| R2 | Collection Strategy 只保留 Keyword Pack/Plan，并区分 Search Terms 与 all_active/selected Brands | #434 / AC2 | not_satisfied | 待实现并由 Plan Store/Page/Browser Acceptance 证明。 |
| R3 | Excel、TikHub Discovery 与 Batch Supplement 分别遵守批准的 Search/Brand Filter/补采语义 | #434 / AC3 | not_satisfied | 待实现并由 Runtime 组件测试、Browser 请求断言和兼容回归证明。 |
| R4 | Voice Plaza 支持 Brand/Vehicle/Competition 查询、结果 Evidence 和 Brand/Role/Competition/Vehicle 导出选择 | #434 / AC4 | not_satisfied | 待实现并由 Store/Component/Browser Acceptance 与真实 Golden Path 证明。 |
| R5 | 旧 Keyword Pack↔Vehicle、Global Keyword Relevance、Discovery Vehicle Search 前端职责退出，legacy 记录仍可只读显示 | #434 / AC5 | not_satisfied | 待实现并由生产代码零引用、legacy fixture 与 Browser 回归证明。 |
| R6 | 四条用户路径的 Browser Mock、前端 lint/typecheck/unit/build 均有当前 revision 新鲜证据 | #434 / AC6 | not_satisfied | 待 Red/Green 和完整前端门禁证明。 |
| R7 | Brand/Vehicle 配置到 Import/Collection、Voice Plaza Filter/Export 的真实跨组件链通过 | #434 / AC7 | not_satisfied | 待 Real Full-stack Golden Path 证明；Mock 只记录其实际边界。 |
| R8 | Figma/实现一致、长期文档、Completion Audit、Deep Review、PR/main CI、归档与 Issue Closure 完整收口 | #434 / AC8 | not_satisfied | Figma 已达到 READY_WITH_NOTES；仍待代码回验、文档、Review 和交付生命周期证据。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Store、表单、筛选、显示映射及 legacy 兼容的 Red/Green 证据。 |
| 接口 / Contract | required | generated client 消费与 OpenAPI/Orval drift/compatibility；不修改后端 Contract。 |
| 集成 / Persistence / Runtime Dependency | required | 复用 Stage 2—5 PostgreSQL/API/Worker 真实边界，在 Golden Path 中验证本次新前端接线。 |
| 用户 / Workflow Acceptance | required | Admin、Strategy、Excel/Discovery、Voice Plaza 的 Browser Mock 成功、加载、错误、关键 method/URL/query/payload。 |
| 跨组件 Golden Path | required | Brand/Vehicle 配置 → Import/Collection → Voice Plaza → Filter/Export 的少量真实链。 |
| External Dependency / Provider Probe | not_applicable | 本阶段不改变 Provider Operation 或真实第三方字段；稳定 Fixture/已有 Contract 足够，且禁止付费 Probe。 |
| Build / Package / Runtime | required | ESLint、TypeScript/Vue typecheck、Vitest、Vite production build 与项目正式 Browser/full-stack 入口。 |
| Docs / Governance / Other | required | Figma/Contract/代码一致性、当前文档同步、Change/Ready/Secret/CI/PR/main/Closure 门禁。 |

# 兼容、迁移、部署与回滚

- 公共 Contract、Schema/Migration 与依赖不变；只消费 Stage 2—5 已生成 TypeScript 类型和 API。
- legacy Plan/Run/Import 中已冻结的 Vehicle 字段继续只读显示，不再为新创建流程提供 Discovery Vehicle 选择。
- 部署无新增数据库前置条件；应用回滚不需要数据回滚，但旧前端不会展示本阶段新增用户路径。
- 不执行生产部署或外部 Provider 调用。

# Completion Audit

- [ ] upstream_re_read：Ready 前从 Issue #434、Roadmap Stage 6、最终 Figma、当前 Contract 和项目正式边界独立重建完成定义。
- [ ] change_coverage：逐条比较 AC/R 与实现、测试、文档和交付证据，清除遗漏。
- [ ] reverse_audit：按后端能力 → 前端入口及前端动作 → 后端支持，反查 Admin、Strategy、Runtime、Voice Plaza 和异步 Export 结果链。
- [ ] two_stage_review：完成 A1 上游要求 → Change、A2 Change → 实现/测试/文档，再做 Deep 代码质量 Review。
- [ ] unresolved_cleared：Ready 前清零所有 `not_satisfied`；延期/不适用必须有正式依据。
