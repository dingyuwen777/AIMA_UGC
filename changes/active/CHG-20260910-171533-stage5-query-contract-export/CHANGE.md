---
schema: coding-change/v1
id: CHG-20260910-171533-stage5-query-contract-export
title: 搜索与品牌车型过滤 Stage 5 查询 Contract 与导出
level: L3
status: in_progress
owner: chatgpt
branch: feature/stage5-query-contract-export
created: 2026-09-10
updated: 2026-09-10
completion_gate: required
depends_on:
  - CHG-20260909-235500-stage3-excel-brand-vehicle-filter
  - CHG-20260910-132342-stage4-tikhub-search-brand-filter
affected_areas:
  - content
  - vehicles
  - analysis
  - reporting
  - api
  - contracts
  - persistence
  - frontend-generated-client
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/contracts/export
  - backend/src/aima_ugc/modules/content/query.py
  - backend/src/aima_ugc/modules/reporting/column_catalog.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/reporting.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/platform/export/excel.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - tests/contracts
  - tests/integration/content
  - tests/unit/platform
  - docs/blueprint/04_后端任务API与前端.md
  - docs/appendix/06_Excel统一数据导出与离线调试.md
  - backend/src/aima_ugc/platform/reporting/README.md
contracts:
  - Voice Plaza Brand/Vehicle/Competition Read Model
  - ContentFilterSnapshot Brand/Competition query filters
  - Data Export column catalog and Workbook projection
data_changes:
  - 无 Schema/Migration；只读取现有当前版本 Brand/Vehicle Evidence 与 Brand Role
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 5，把 Stage 3/4 已写入 PostgreSQL 的 Brand/Vehicle Evidence 与 Brand Role 变成正式查询、分析目标冻结和 Excel 导出事实。List、Count、Analysis Query Target 与 Export Query Target 必须共享同一 `ContentFilterSnapshot` 和同一 PostgreSQL 过滤语义。

Requirement Source：#431。

# 范围与非目标

- 范围：Voice Plaza Read Model、公共 Pydantic Contract、Content Query Repository、Count/Analysis/Export 查询目标、Cursor hash、Reporting 投影与 Workbook、OpenAPI/Orval、测试与长期事实文档。
- 非目标：不实施 Stage 6 Figma/Vue 产品化；不执行 Stage 7 重分类或旧表/API/UI 清理；不新增表、Migration、搜索系统、AI/Embedding、Provider 调用或依赖升级。
- 必须保持：默认相关性与来源可见性、Current Content Version、人工锁、Vehicle merge、selected target、Export 冻结列、`matched_keywords`、Owner 边界和生产 Schema。

# 已确认方案

1. `brands[]` 和 `vehicles[].brand` 从当前 Content Version 的有效 Evidence、Vehicle 当前归属与 Brand 目录联表读取；品牌按 code/ID 稳定去重排序。
2. `competition_scope` 只由当前投影内实际 Brand Role 集合派生：无品牌为 `none_detected`；只有 owned/competitor/other 分别映射单一 Scope；两种及以上 Role 为 `mixed`。
3. `brand_ids` 与 `competition_scopes` 在同维度 OR、跨维度 AND；Vehicle 筛选继续兼容 merged model。四个消费者通过现有共享 `_base_statement` / `freeze_target_statement` 路径保持一致。
4. Export 新增独立 Brand、Brand Role、Competition Scope、Vehicle 列，读取导出冻结的 Content Version Evidence；不改变 `matched_keywords`。
5. 不创建 Migration；Contract 稳定后只通过正式 generator 更新 OpenAPI 与 TypeScript Client。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Read Model 返回 `brands[]`、`vehicles[].brand` 与五值派生 `competition_scope` | #431 / AC1 | not_satisfied | 待实现与直接 PostgreSQL/API 测试。 |
| R2 | `brand_ids`、`competition_scopes` 校验和同维度 OR/跨维度 AND 语义正确 | #431 / AC2 | not_satisfied | 待 Contract 与查询测试。 |
| R3 | List、Count、Analysis Query Target、Export Query Target 目标集合一致 | #431 / AC3 | not_satisfied | 待共享查询链集成证据。 |
| R4 | Cursor/query hash 包含新增完整筛选快照并拒绝跨筛选复用 | #431 / AC4 | not_satisfied | 待 Cursor 回归测试。 |
| R5 | Export 独立输出 Brand/Role/Competition/Vehicle 且保留 `matched_keywords` 语义 | #431 / AC5 | not_satisfied | 待目录、投影和实际 Workbook 证据。 |
| R6 | OpenAPI/Orval 与兼容检查无漂移 | #431 / AC6 | not_satisfied | 待生成与检查。 |
| R7 | owned/competitor/mixed/other/none、Brand/Vehicle 交集、merge 与版本冻结有直接证据 | #431 / AC7 | not_satisfied | 待 PostgreSQL 18 集成测试。 |
| R8 | L3 Completion Audit、Review、PR/main CI、归档、Roadmap 与 Issue 收口 | #431 / AC8 | explicitly_deferred | 交付生命周期后置门禁；实现完成后逐项取证。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Contract / Unit | required | 先建立失败测试，再覆盖枚举、唯一性、Read Model、Cursor hash、列目录与 Workbook 投影。 |
| PostgreSQL Integration | required | 直接覆盖当前版本 Evidence、五种 Scope、Brand/Vehicle AND、merged Vehicle 与四消费者集合一致。 |
| API / Generated Client | required | Pydantic/FastAPI、OpenAPI generator、compatibility、Orval generate/check。 |
| Browser Mock Acceptance | required | Stage 5 不改正式页面，但 generated Client 变化需执行现有 Voice Plaza Browser Mock 回归。 |
| Real Full-stack Golden Path | required | PR CI 在 PostgreSQL 18 与真实 API/前端组合上复核现有旅程。 |
| Static / Build / Governance | required | Ruff、mypy、前端 lint/typecheck/build、docs checks、Change Ready Check、`git diff --check`。 |
| External Provider Probe | not_applicable | Stage 5 只读现有 PostgreSQL 事实，不调用付费 Provider。 |
| Docs / Delivery | required | 同步 API/导出长期事实；PR/main CI、原生归档、Roadmap 状态和 Issue Closure 后置完成。 |

# 兼容、迁移、部署与回滚

- 公共 Contract 仅新增可选筛选和响应字段；前端生成 Client 同步，Stage 6 再消费新字段。
- 无数据库 Schema/Migration；读取既有 Evidence 与目录，部署顺序无新增数据库前置条件。
- Export 列目录版本会随新增稳定列升级；既有 Export 记录继续使用其冻结列和版本。
- 回滚应用不需要数据回滚；新 Contract 客户端不得在旧服务端提交新增筛选。
- 不执行生产部署，不调用真实 TikHub/LLM。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #431、Roadmap Stage 5、相关 Contract/Schema/实现/测试和长期文档。
- [ ] change_coverage：逐条核对 R1-R7 的实现、测试、生成物和文档证据；R8 只保留合并生命周期后置项。
- [ ] reverse_audit：按 Brand/Vehicle Evidence → List/Detail → Count → Analysis Target → Export Target/Workbook 和 Contract → Generated Client 反查生产者/消费者。
- [ ] two_stage_review：A1 独立重建需求与风险；A2 以最终候选 diff 核对实现、测试、文档与证据。
- [ ] unresolved_cleared：Ready 前清零 `not_satisfied` 和已知 P0/P1/P2 Finding，明确所有未验证项。
