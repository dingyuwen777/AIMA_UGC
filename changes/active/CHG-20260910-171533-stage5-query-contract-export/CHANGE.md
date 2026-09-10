---
schema: coding-change/v1
id: CHG-20260910-171533-stage5-query-contract-export
title: 搜索与品牌车型过滤 Stage 5 查询 Contract 与导出
level: L3
status: ready_for_review
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
| R1 | Read Model 返回 `brands[]`、`vehicles[].brand` 与五值派生 `competition_scope` | #431 / AC1 | satisfied | `ContentReadRecord`/HTTP Response 增加可审计 Brand Evidence、车型有效目录 Brand 与五值派生校验；PostgreSQL Repository 按当前 Content Version 读取并按 Brand code/ID、Evidence created_at/ID 稳定排序。 |
| R2 | `brand_ids`、`competition_scopes` 校验和同维度 OR/跨维度 AND 语义正确 | #431 / AC2 | satisfied | `ContentFilterSnapshot` 限制最多 100 个不重复 Brand ID、最多五个不重复 Scope；`_apply_filters` 对维度内用 `IN/OR`、维度间叠加 `WHERE`，Vehicle 继续兼容 merged target；Contract/API/SQL 集成测试已固化。 |
| R3 | List、Count、Analysis Query Target、Export Query Target 目标集合一致 | #431 / AC3 | satisfied | List/Count 共用 `_base_statement`；Analysis/Export query target 共用 `freeze_target_statement`，统一进入同一 `_apply_filters`。新增 PostgreSQL 18 测试直接比较四个消费者集合，等待 PR HEAD 运行环境复核。 |
| R4 | Cursor/query hash 包含新增完整筛选快照并拒绝跨筛选复用 | #431 / AC4 | satisfied | `_query_hash` 对完整 `ContentFilterSnapshot` 序列化；Contract 回归证明 Scope 改变后旧 Cursor 解码失败，FastAPI 测试证明重复多选参数完整进入 Query。 |
| R5 | Export 独立输出 Brand/Role/Competition/Vehicle 且保留 `matched_keywords` 语义 | #431 / AC5 | satisfied | Column Catalog v2 新增四个独立可选列且默认列不变；Reporting 按冻结 Version 读取 Evidence；共享 Exporter 输出中文角色/竞品范围。Unit 与 PostgreSQL Workbook 测试分别覆盖字段值和版本推进后冻结结果。 |
| R6 | OpenAPI/Orval 与兼容检查无漂移 | #431 / AC6 | satisfied | Pydantic、`openapi.json`、Export JSON Schema 与 generated TypeScript Client 已由正式 generator 同步；本轮 generate `--check` 与 compatibility 均退出 0。 |
| R7 | owned/competitor/mixed/other/none、Brand/Vehicle 交集、merge 与版本冻结有直接证据 | #431 / AC7 | satisfied | `tests/integration/content/test_stage5_brand_query_export.py` 通过正式 Import/Owner 写入五类内容，构造 merged Vehicle 后验证交集、四消费者集合、冻结 v1 后推进 v2 及实际 Workbook；本机无 PostgreSQL/Docker，测试运行结果由当前 PR HEAD PostgreSQL 18 CI 补齐，未把本地静态审查写成运行成功。 |
| R8 | L3 Completion Audit、Review、PR/main CI、归档、Roadmap 与 Issue 收口 | #431 / AC8 | explicitly_deferred | 上游重读、Completion Audit 与候选实现 Deep Review 已完成；PR HEAD PostgreSQL/Full-stack/CI、CI 后 re-review、expected-head merge、main fresh CI、原生归档、Roadmap 和 Issue 收口仍是交付生命周期后置门禁。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Contract / Unit | required | Red 提交 `1edcfd30` 的目标测试在收集期因缺少新 Contract 失败；Green 目标集 36 passed，完整 Contract 112 passed。完整 Unit 在 Windows 为 916 passed / 8 skipped，另 3 个既有 Linux host-preparation 用例因 `os.geteuid/os.chown` 不存在失败，交由 Linux CI 复核。 |
| PostgreSQL Integration | required | 新测试直接覆盖当前版本 Evidence、五种 Scope、Brand/Vehicle AND、merged Vehicle、四消费者集合与 Export 冻结版本。当前 Windows 无 PostgreSQL Secret/Engine 且 Docker daemon 不可用；当前 PR HEAD PostgreSQL 18 CI 是运行证据门禁。 |
| API / Generated Client | required | 完整 API 60 passed；OpenAPI generator `--check`、compatibility、TypeScript generated client、前端 typecheck 均成功。 |
| Browser Mock Acceptance | required | Vitest 23 files / 135 tests passed；Stage 5 不提前实现 Vue 产品化，现有 Voice Plaza Mock 已同步新增 required response 字段。Playwright/真实服务回归由 PR CI 执行。 |
| Real Full-stack Golden Path | required | Vite 生产构建成功；PR CI 在 PostgreSQL 18 与真实 API/前端组合上复核现有旅程。 |
| Static / Build / Governance | required | Ruff check、全仓 Ruff format check、mypy 324 source files、ESLint、Vue/TypeScript typecheck、Vite build、docs facts/check、契约检查与 `git diff --check` 成功。Deep Review 发现的格式门禁已在 `9e867e61` 修复。 |
| External Provider Probe | not_applicable | Stage 5 只读现有 PostgreSQL 事实，不调用付费 Provider。 |
| Docs / Delivery | required | 同步 API/导出长期事实；PR/main CI、原生归档、Roadmap 状态和 Issue Closure 后置完成。 |

# 兼容、迁移、部署与回滚

- 公共 Contract 仅新增可选筛选和响应字段；前端生成 Client 同步，Stage 6 再消费新字段。
- 无数据库 Schema/Migration；读取既有 Evidence 与目录，部署顺序无新增数据库前置条件。
- Export 列目录版本会随新增稳定列升级；既有 Export 记录继续使用其冻结列和版本。
- 回滚应用不需要数据回滚；新 Contract 客户端不得在旧服务端提交新增筛选。
- 不执行生产部署，不调用真实 TikHub/LLM。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #431、Roadmap Stage 5、Brand/Vehicle 表与 Owner、Content Query/HTTP、Analysis/Export 冻结入口、Reporting/Excel、生成物、测试和长期文档；未提前实施 Stage 6 Vue 或 Stage 7 重分类/清理。
- [x] change_coverage：逐条核对 R1-R7 的实现、测试、生成物和文档证据；R8 只保留必须发生在 PR HEAD/合并后的生命周期动作。
- [x] reverse_audit：按 Current Version Brand/Vehicle Evidence → List/Detail → Count → Analysis Query Target → Export Query Target → Frozen Version Reporting/Workbook，以及 Pydantic → OpenAPI/JSON Schema → generated Client 反查；确认 selected target、默认相关性、来源可见性、Vehicle merge 和默认 Export 列未漂移。
- [x] two_stage_review：Deep Review Target 为 `7a44d3656c27a93c229d1e519a0d47e11cdbf3f1...9e867e61`。A1 从 #431/Roadmap 独立重建 AC1-AC8 与 Contract/兼容/冻结/证据风险；A2 沿四消费者与 Export 反查最终候选 diff、测试和文档。Review 发现全量 `ruff format --check` 会失败，已以机械格式提交修复；当前无已知 P0/P1/P2 实现 Finding。PR CI 后仍需基于最终 HEAD re-review。
- [x] unresolved_cleared：R1-R7 无 `not_satisfied`；本机 PostgreSQL/Real Full-stack 未运行的环境边界已明确，并由当前 PR HEAD required CI 补证。R8 的 CI、合并、main 验证、归档、Roadmap 和 Issue 动作是后置交付门禁，不冒充已完成。
