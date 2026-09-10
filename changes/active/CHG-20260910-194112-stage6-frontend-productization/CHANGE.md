---
schema: coding-change/v1
id: CHG-20260910-194112-stage6-frontend-productization
title: 搜索与品牌车型过滤 Stage 6 前端产品化
level: L3
status: ready_for_review
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
| R1 | Admin 只保留五个目标 Tab，并通过正式 Brand/Vehicle API 管理品牌、识别词与 1:N 车型，不调用词包车型关联 | #434 / AC1 | satisfied | `AdminConfigurationPage.vue` 与 `api.ts` 已收敛为“品牌与车型、AI 模型、TikHub、AI 分析规则、操作记录”，使用 generated Brand/Vehicle API；Browser Mock 覆盖品牌、识别词、旗下车型与错误/分页，Real Full-stack 覆盖真实创建链。 |
| R2 | Collection Strategy 只保留 Keyword Pack/Plan，并区分 Search Terms 与 all_active/selected Brands | #434 / AC2 | satisfied | Strategy Store/Page 只保留 Keyword Pack/Plan；新 Plan 提交 `brand_ids` 且不提交 Vehicle Search，Browser 与 PostgreSQL Full-stack 验证 selected Brand；legacy Vehicle-only Plan 编辑默认保留原语义。 |
| R3 | Excel、TikHub Discovery 与 Batch Supplement 分别遵守批准的 Search/Brand Filter/补采语义 | #434 / AC3 | satisfied | Excel UI 明确 Search 不适用并提交 all-active/selected Brand；Discovery 提交 Keyword Pack Search + Brand Filter；Batch Supplement 不提交 Search/Brand/Vehicle。Runtime Browser 请求断言和 Real Full-stack Excel/历史 Campaign 均通过。 |
| R4 | Voice Plaza 支持 Brand/Vehicle/Competition 查询、结果 Evidence 和 Brand/Role/Competition/Vehicle 导出选择 | #434 / AC4 | satisfied | Voice Store 的共享 Filter Snapshot 已包含 `brand_ids`/`vehicle_model_ids`/`competition_scopes`；筛选、列表、详情和 Column Catalog v2 导出已产品化。Browser Mock 验证查询参数和显示，Real Full-stack 验证精确筛选快照与 Workbook 四类列。 |
| R5 | 旧 Keyword Pack↔Vehicle、Global Keyword Relevance、Discovery Vehicle Search 前端职责退出，legacy 记录仍可只读显示 | #434 / AC5 | satisfied | 生产 Feature 已无旧 Global Relevance 或 Keyword Pack↔Vehicle 调用；Discovery 无 Vehicle 选择；legacy Plan 的 Vehicle ID 可显示且编辑默认保留。死代码 `RelevancePanel.vue` 与后端/生成 Contract 的物理删除明确留给 Stage 7。 |
| R6 | 四条用户路径的 Browser Mock、前端 lint/typecheck/unit/build 均有当前 revision 新鲜证据 | #434 / AC6 | satisfied | 当前候选本地 ESLint、TypeScript/Vue typecheck、Vitest 24 files / 140 tests、Vite build 和 Browser Mock 106 tests 全部通过；最终 Ready revision 再执行同组门禁。 |
| R7 | Brand/Vehicle 配置到 Import/Collection、Voice Plaza Filter/Export 的真实跨组件链通过 | #434 / AC7 | satisfied | Full-stack Acceptance Run `34483499943` 在精确实现提交 `05386b79` 上以 PostgreSQL 18、Migration、真实 API/Worker/Browser 运行四个 Stage 6 相关 spec，10 tests 全部通过。 |
| R8 | Figma/实现一致、长期文档、Completion Audit、Deep Review、PR/main CI、归档、Roadmap 与 Issue 收口 | #434 / AC8 | explicitly_deferred | Figma、最终 Contract/实现复核、长期文档、Completion Audit 和 Deep Review 已完成；最终 PR HEAD CI、expected-head merge、main fresh CI、原生归档、Roadmap/Issue 收口属于 Ready 后交付生命周期门禁。自动 Figma 同步状态为 `SYNCHRONIZED_PENDING_HUMAN_REVIEW`，不冒充人工视觉确认。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Red 基线提交 `4caf2819`；最终候选 Vitest 24 files / 140 tests 通过，覆盖 Store、表单、筛选、显示映射及 legacy Plan 编辑兼容。 |
| 接口 / Contract | required | 未修改 Pydantic/OpenAPI/generated client；正式 generator `--check`、compatibility 与生成目录 drift 检查退出 0。 |
| 集成 / Persistence / Runtime Dependency | required | Full-stack Run `34483499943` 迁移隔离 PostgreSQL 18，并通过真实 API/Worker 持久化 Brand/Vehicle、Plan、Import、Content 与 Export。 |
| 用户 / Workflow Acceptance | required | Browser Mock 106/106 通过，覆盖 Admin、Strategy、Excel/Discovery、Voice 的成功、加载、错误和关键 method/URL/query/payload。 |
| 跨组件 Golden Path | required | Full-stack Run `34483499943` 的 Brand/Vehicle 管理 → Brand Scope Import → Voice Filter/Detail → Export 真实闭环通过；四个 Stage 6 相关 spec 共 10/10。 |
| External Dependency / Provider Probe | not_applicable | 本阶段不改变 Provider Operation 或真实第三方字段；稳定 Fixture/已有 Contract 足够，且禁止付费 Probe。 |
| Build / Package / Runtime | required | ESLint、TypeScript/Vue typecheck、Vitest、Vite production build 与 Browser Mock 均通过；Full-stack Run `34483499943` 成功。 |
| Docs / Governance / Other | required | docs/check facts、Change、architecture、Contract/Client drift 与 `git diff --check` 均通过；Figma 为 `READY_WITH_NOTES`，最终五页面/四业务路径 Design Context 已复核，待人工视觉确认。 |

# 兼容、迁移、部署与回滚

- 公共 Contract、Schema/Migration 与依赖不变；只消费 Stage 2—5 已生成 TypeScript 类型和 API。
- legacy Plan/Run/Import 中已冻结的 Vehicle 字段继续只读显示，不再为新创建流程提供 Discovery Vehicle 选择。
- 部署无新增数据库前置条件；应用回滚不需要数据回滚，但旧前端不会展示本阶段新增用户路径。
- 不执行生产部署或外部 Provider 调用。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #434、Roadmap Stage 6、最终 Figma、当前 Brand/Plan/Import/Content/Export Contract、generated client 和项目正式前端边界；确认 Stage 6 不新增后端 Contract/Schema，不提前执行 Stage 7。
- [x] change_coverage：逐条比较 AC1—AC8/R1—R8 与 Admin、Strategy、Runtime、Voice、测试、文档和交付证据；R1—R7 已满足，R8 仅保留必须发生在 Ready/合并后的生命周期动作。
- [x] reverse_audit：按 Brand/Vehicle API → Admin 入口、Plan/Import/Collection `brand_ids` → Strategy/Runtime、Content Read Model/Filter → Voice List/Detail/Analysis/Export 反查；前端动作均有 Stage 2—5 generated Contract 支持，legacy Vehicle Plan 未被静默扩域。
- [x] two_stage_review：Review Target 为 `692b59c29218ce97bca8d3e505cb777b1840bf09...05386b7912e3d0cb8070da37af1f36c750e15e8d`。A1 从 #434/Roadmap/Figma/Contract 独立重建完成定义；A2 沿四条页面路径、请求快照、异步 Worker/Export、测试与文档审查。Review 发现并修复 legacy Vehicle-only Plan 编辑被静默改为 all-active Brand 的兼容缺陷；Browser/Full-stack 定位又收紧 Brand 与 Vehicle Owner 的证据列。当前无已知 P0/P1/P2 实现 Finding。
- [x] unresolved_cleared：所有 `not_satisfied` 已清零；Provider Probe 因本阶段不改外部 Operation 正式不适用；R8 的 PR HEAD CI、合并、main 验证、归档、Roadmap 与 Issue 动作为后置交付门禁，不冒充已完成。
