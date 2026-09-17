---
schema: coding-change/v1
id: CHG-20260917-server-generated-catalog-code
title: 品牌与车型 code 改为服务端生成并同步 Figma
level: L3
status: ready_for_review
owner: engineering
branch: feature/server-generated-catalog-code
created: 2026-09-17
updated: 2026-09-17
completion_gate: required
depends_on: []
affected_areas:
  - vehicles
  - api
  - contracts
  - frontend
  - documentation
affected_paths:
  - tests/integration/ingestion/
  - scripts/performance/benchmark_stage12_historical.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/contracts/brand_vehicle.py
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_http.py
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/admin-configuration/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - tests/api/
  - tests/contracts/test_u1_u5_contracts.py
  - tests/unit/content/test_vehicle_display_classification.py
  - tests/fullstack/seed_stage8f_manual_relevance_review.py
  - tests/integration/database/test_brand_vehicle_stage2_repository.py
  - tests/integration/database/test_u1_u5_administration.py
  - tests/integration/stage3_brand_support.py
  - tests/integration/content/test_stage5_brand_query_export.py
  - docs/guides/02_管理员配置Figma开发基线.md
contracts:
  - Brand Create HTTP Contract
  - Vehicle Model Create HTTP Contract
  - Brand/Vehicle Response Contract
data_changes: []
---

# 背景、目标与边界

Requirement Source：GitHub Issue #522，验收绑定 AC1—AC9。

管理员配置原实现要求人工填写 Brand Code / Vehicle Code。业务决定调整为：数据库 `code` 列、唯一约束、已有数据和响应 Contract 继续保留，但新建 Brand/Vehicle 的 `code` 改为服务端生成的内部稳定字段，管理员不再输入或控制该值；正式 Figma 管理员配置页必须表达相同语义。

本次不删除数据库字段、不新增 Migration、不修改既有资源 `code`，也不改变品牌/车型的删除、合并、别名、归属等既有业务语义。内部 Repository 仍接受稳定 code；公共 HTTP 创建入口负责生成内部 code，因此不会破坏既有内部显式调用。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Brand 创建请求不接收 `code`，创建响应返回服务端生成的内部 `code` | #522 / AC1 | satisfied | `BrandCreateRequest` 已移除 code；`PostgresBrandVehicleHttpService.create_brand()` 生成 `BRAND_<UUID>`；OpenAPI/Orval 已由正式生成链更新 |
| R2 | Vehicle 创建请求不接收 `code`，创建响应返回服务端生成的内部 `code` | #522 / AC2 | satisfied | `VehicleModelCreateRequest` 已移除 code；`PostgresAdministrationHttpService.create_vehicle_model()` 生成 `VEHICLE_<UUID>`；Full-stack Golden Path 已更新为断言响应 code 格式 |
| R3 | 客户端不能控制新建资源内部 `code`，旧客户端额外提交 `code` 明确失败 | #522 / AC3 | satisfied | Create Contract 保留 `extra="forbid"`；`test_create_contracts_reject_client_supplied_internal_code` 通过；pre-ready run `35178746591` 绿色 |
| R4 | BrandResponse / VehicleModelResponse 继续返回 `code` | #522 / AC4 | satisfied | Response Contract 未删除 code；OpenAPI Contract 回归明确断言 response `code` required；generated drift 绿色 |
| R5 | DB `code` 列、唯一约束、既有记录保持不变，无 Migration | #522 / AC5 | satisfied | 本 PR 未修改 `tables.py`、Alembic Migration 或 Repository Schema；只改变 HTTP 输入和创建应用服务，`data_changes: []` |
| R6 | 管理员新增品牌/车型 UI 不再展示、校验或提交编码 | #522 / AC6 | satisfied | `CatalogConfigurationPanel.vue` 已移除 draft/validation/payload/input code；SSR、unit/build 与 Browser Mock 在 run `35178746591` 全绿；release2 Browser Mock 旧编码断言已同步新语义 |
| R7 | 正式 Figma source component 与开发规格同步 | #522 / AC7 | satisfied | 正式 `qmZEFvPrB8u9JX5fyqc93S / 3957:2` 新鲜回读：新增品牌 `7511:11637`、新增车型 `7511:11276` 均无编码输入；DEV 规格明确“创建请求不接收 code、响应仍返回 code”，截图已重新获取；设计已正确，无需制造无意义画布差异 |
| R8 | 相关后端、Contract、前端、E2E 与 required PR CI 通过 | #522 / AC8 | explicitly_deferred | run `35182545902` 的核心 CI 与 Real Full-stack 已绿色；PostgreSQL Integration 仅剩 Stage5 查询/导出集成测试仍通过 public Brand/Vehicle Create 传客户端 code，已更新；必须以当前最终 HEAD 重新全绿后再标 satisfied |
| R9 | 合并后 main required CI 再次通过 | #522 / AC9 | explicitly_deferred | 这是 post-merge fresh-evidence gate；合并完成后必须绑定 merge SHA 重新读取 main workflow 结果，绿色后才关闭 #522 和完成分支清理 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | pre-ready run `35178746591` 绿色；正式 CI 暴露的 unit/contract 历史 fixture 已同步新 Create Contract，原业务断言均保留 |
| 接口 / Contract | required | Pydantic → OpenAPI → Orval generated drift success；create 无 code、response 有 code、extra forbid；所有已发现 public Create fixture 均按无-code 输入边界更新 |
| Backend/API/PostgreSQL | required | 生产创建应用服务生成 code；Schema/Migration 无 diff；Stage2/U1-U5、Stage3 与 Stage5 查询/导出集成测试已移除 public Create 的人工 code，同时保留 snapshot、lock、merge、分类、delete、Collection、Query/Export 行为断言 |
| Browser Mock Acceptance | required | `admin-configuration-figma.spec.ts` 与 release2 管理员配置 Browser Mock 均验证创建弹窗无编码输入且其它真实字段保持可用 |
| Real Full-stack Golden Path | required | `admin-product-capabilities.spec.ts` 已更新为真实 API/DB 路径与服务器 code 断言；Stage8F manual relevance seed 不再绕过新 Create Contract；run `35182545902` Real Full-stack 全绿，最终仍以当前 HEAD 重跑结果为 merge gate |
| External Provider Probe | not_applicable | 不改变 TikHub/外部 Provider |
| Build / Runtime | required | Runtime Acceptance 与 Developer Tooling 已有当前任务绿色证据；正式 required CI 仍需当前最终 HEAD 通过 |
| Docs / Governance / Other | required | Issue #522 AC1—AC9、本文 Traceability/Completion Audit、管理员配置开发基线均已同步 |
| Figma | required | `qmZEFvPrB8u9JX5fyqc93S / 3957:2` Design Context + Plugin readback + 两个创建状态 screenshot 均为当前新鲜证据 |

# 实施与兼容

- [x] Create Contract 移除客户端 `code` 输入，Response/DB `code` 保留。
- [x] HTTP 创建应用服务生成稳定唯一内部 code；Repository/Schema 不改，内部显式 code 调用兼容。
- [x] 用户可见品牌/车型顺序不再依赖内部 `code`：管理员目录按显示名稳定排序，内容品牌按业务角色（自有→竞品→其他）再按显示名排序，内容车型按有效显示名排序。
- [x] 使用 AST 全仓扫描公共 Create Contract 调用点，清理所有 `BrandCreateRequest` / `VehicleModelCreateRequest` 中的客户端 `code`；Repository 层显式内部 code 调用保持不变。
- [x] 前端创建品牌/车型不再显示、校验或提交 `code`；已有品牌 code 仅在技术信息只读展示。
- [x] OpenAPI 与 Orval generated client 通过正式生成链重新生成，未手改 generated client。
- [x] 补 Contract、SSR、Browser Mock 与 Real Full-stack 直接回归。
- [x] 同步管理员配置开发基线；正式 Figma 当前状态已与要求一致并完成 readback/screenshot 复核。
- [x] 更新原有车型分类 unit fixture，使其按新 Create Contract 构造无 code 请求；没有删除或弱化分类字段断言。
- [x] 更新 U1—U5 车型别名 Contract fixture，使其按新 Create Contract 构造无 code 请求；保留显示名 trim 与别名规范化/重复拒绝断言。
- [x] 更新 release2 管理员配置 Browser Mock，删除“人工 code 必须存在”的旧断言，改为验证内部 code 不暴露且服务端生成提示存在。
- [x] 更新 Stage8F manual relevance Full-stack seed，使其通过真实无-code `BrandCreateRequest` 创建品牌，不再由测试客户端伪造 code。
- [x] 更新 Stage2 与 U1—U5 PostgreSQL Integration 历史 fixture，删除 public Brand/Vehicle Create 的人工 code，同时保留原 snapshot、readiness、lock、merge、classification、delete 与 audit 断言。
- [x] 更新 Stage3 集成测试共享品牌 helper，使 Collection 集成测试通过真实无-code `BrandCreateRequest` 建立品牌事实；Stage4 Repository 级显式内部 code 测试入口保持不变。
- [x] 更新 Stage5 Brand/Vehicle 查询与冻结导出集成测试中的 3 个 Brand、2 个 Vehicle public Create fixture，删除人工 code，保留五种竞品范围、过滤、分析、导出与冻结版本断言。
- [ ] PR Ready 后 required CI 全绿并完成独立 Review。
- [ ] merge 后 main required CI 全绿，再关闭 Requirement Issue 并清理任务分支。

# Completion Audit

- [x] upstream_re_read：已重新读取 Issue #522 AC1—AC9、当前 Create/Response Contract、HTTP 创建链、前端表单、generated artifacts、正式 Figma 页面与本轮验证结果；没有继续使用旧会话快照代替当前事实。
- [x] change_coverage：R1—R7 已有直接实现与新鲜证据；R8/R9 仅是按交付生命周期显式递延的 PR/post-merge CI 门禁，没有隐藏实现缺口。
- [x] reverse_audit：已从管理员新增品牌/车型动作反查 `CatalogConfigurationPanel` → Orval generated client → FastAPI/Pydantic Create Contract → Bootstrap Application Service → Repository/DB → Response，并继续反查 unit / contract / Browser Mock / PostgreSQL Integration / Full-stack seed / Collection 共享 helper / Stage5 Query-Export；客户端 code 输入在公开创建链及测试调用者中均被切断，Response/DB code 保留。
- [x] unresolved_cleared：当前无 `not_satisfied` Requirement；唯一剩余项是 R8 正式 PR CI 与 R9 post-merge main CI，均有明确执行时点且在完成前不会宣称通过或关闭 #522。

# 本轮验证证据

1. 正式 Contract 生成链 workflow run `35177820419`：`uv run python scripts/contracts/generate.py` + `npm --prefix frontend run generate:api` success，生成提交 `9f1c2fd9ce6f9a485b5bdfc86afdb4b2d32bb637`；临时 workflow 已删除。
2. Browser/Full-stack acceptance 更新 workflow run `35177948358` success；临时 workflow 已删除。
3. pre-ready validation run `35178746591` success：`ruff format --check`、`ruff check`、目标 Contract pytest、OpenAPI/Orval drift、frontend lint/typecheck/unit/build、Browser Mock 均 success。
4. Figma：正式 source `qmZEFvPrB8u9JX5fyqc93S / 3957:2` 的新增品牌 `7511:11637`、新增车型 `7511:11276` 完成当前 Design Context 与截图复核；Plugin 全页文本扫描只发现 DEV 规格中的两处 code 说明，且均明确“服务端创建时生成、创建请求不接收 code、响应仍返回 code”。
5. PR #525 已使用机器门禁要求的独立行 `Requirement-Source: #522` 绑定真实 Requirement Source；Requirement Source / Change readiness 在正式 CI 中已通过。
6. 正式 CI run `35179041234` 首次在全量 unit 阶段暴露 `tests/unit/content/test_vehicle_display_classification.py` 仍使用旧 `VehicleModelCreateRequest(code=...)` fixture；同轮结果 `1 failed, 1028 passed`。该 fixture 已改为无 code 请求，并保留分类字段可选/trim 断言。
7. 正式 CI run `35179364523` 复验时 unit 已达到 `1029 passed`，随后 contracts 暴露 `tests/contracts/test_u1_u5_contracts.py` 的车型别名 fixture 仍传 `code`；同轮 contracts 结果 `1 failed, 110 passed`。该 fixture 已改为无 code 请求，保留显示名 trim、别名内容与重复别名拒绝断言。
8. 正式 CI run `35179642506`：后端 1029 unit / 111 contracts / 71 API、架构、Wheel、前端 157 unit/build 均 success；Browser Mock 仅两条 release2 旧断言仍要求人工编码输入，已同步为无编码输入的新 Contract 行为。
9. 正式 CI run `35180163448`：Requirement Traceability、静态、Contract/API、架构、Wheel、前端 unit/build/Browser Mock 全部 success；Real Full-stack 在启动浏览器前的 `Seed AI irrelevant content for manual review` 阶段发现 `tests/fullstack/seed_stage8f_manual_relevance_review.py` 仍向 `BrandCreateRequest` 传 `code`，已改为无-code 创建。Runtime Acceptance 与 Developer Tooling 同 HEAD 均 success。
10. 正式 CI run `35181067113`：核心 CI（Requirement Source/Change readiness、docs/secret、generated drift、Python format/lint/mypy、全量 unit/contracts/API、architecture、Wheel、frontend unit/build/Browser Mock）全部 success；Real Full-stack 的 Stage8F seed、真实 API/Worker 启动均 success 并进入浏览器 acceptance；PostgreSQL Integration 运行 79 条时仅 6 条历史 fixture 因仍向 `BrandCreateRequest` / `VehicleModelCreateRequest` 传 `code` 失败，其余 73 条通过。已更新 `test_brand_vehicle_stage2_repository.py` 与 `test_u1_u5_administration.py`，不降低原数据库行为断言。
11. 正式 CI run `35181910194`：核心 CI 再次全部 success；PostgreSQL Integration 中数据库 79 条与 jobs 13 条均通过，Collection 集成 96 条中仅 `test_production_worker_consumes_scheduler_created_collection_run` 失败，根因是共享 `tests/integration/stage3_brand_support.py` 仍向 public `BrandCreateRequest` 传 `code`；该 helper 已改为无-code 创建，保留 Stage3/Collection 真实行为。
12. 正式 CI run `35182545902`：核心 CI、Real Full-stack Golden Path、database 79 条、jobs 13 条、Collection 96 条全部 success；PostgreSQL Integration 仅在 content 集成 62 条中剩 `test_brand_vehicle_filters_share_targets_and_export_frozen_version` 因 3 个 Brand / 2 个 Vehicle fixture 仍传客户端 code 失败，其余 61 条通过。已同步 Stage5 Query/Export fixture，原过滤、分析、导出与冻结事实断言不变。
13. 正式 PR required CI 和 post-merge main CI 不提前冒充；分别在当前最终 HEAD/merge 后执行并回填最终证据。

13. 正式 PostgreSQL Integration 在 ingestion 套件集中暴露历史公共 Create fixture 与 Stage12 性能 harness 仍传客户端 `code`；本轮改为 AST 全仓扫描并清零此类调用，仅保留 Repository 层合法内部显式 code。最终通过状态仍以当前 HEAD required CI 为准。
