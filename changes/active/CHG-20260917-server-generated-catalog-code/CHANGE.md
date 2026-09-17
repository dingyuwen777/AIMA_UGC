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
| R6 | 管理员新增品牌/车型 UI 不再展示、校验或提交编码 | #522 / AC6 | satisfied | `CatalogConfigurationPanel.vue` 已移除 draft/validation/payload/input code；SSR、unit/build 与 Browser Mock 在 run `35178746591` 全绿 |
| R7 | 正式 Figma source component 与开发规格同步 | #522 / AC7 | satisfied | 正式 `qmZEFvPrB8u9JX5fyqc93S / 3957:2` 新鲜回读：新增品牌 `7511:11637`、新增车型 `7511:11276` 均无编码输入；DEV 规格明确“创建请求不接收 code、响应仍返回 code”，截图已重新获取；设计已正确，无需制造无意义画布差异 |
| R8 | 相关后端、Contract、前端、E2E 与 required PR CI 通过 | #522 / AC8 | explicitly_deferred | pre-ready run `35178746591` 已通过 format/lint/Contract regression/generated drift/frontend lint/typecheck/unit/build/Browser Mock；正式 PR required CI 必须在 PR 转 Ready 后再执行并作为 merge gate |
| R9 | 合并后 main required CI 再次通过 | #522 / AC9 | explicitly_deferred | 这是 post-merge fresh-evidence gate；合并完成后必须绑定 merge SHA 重新读取 main workflow 结果，绿色后才关闭 #522 和完成分支清理 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | pre-ready run `35178746591`：Backend Contract regression、Frontend unit tests success |
| 接口 / Contract | required | pre-ready run `35178746591`：Pydantic → OpenAPI → Orval generated drift success；create 无 code、response 有 code、extra forbid |
| Backend/API/PostgreSQL | required | 生产创建应用服务生成 code；正式 PR Real Full-stack job 在 Ready 后执行；Schema/Migration 无 diff |
| Browser Mock Acceptance | required | pre-ready run `35178746591`：`admin-configuration-figma.spec.ts` success，创建弹窗无编码控件且 payload 无 code |
| Real Full-stack Golden Path | required | `admin-product-capabilities.spec.ts` 已更新为真实 API/DB 路径与服务器 code 断言；正式 PR CI 执行结果是 merge gate |
| External Provider Probe | not_applicable | 不改变 TikHub/外部 Provider |
| Build / Runtime | required | pre-ready run `35178746591`：backend format/lint、frontend lint/typecheck/build 全部 success；正式 required CI 仍需 Ready 后运行 |
| Docs / Governance / Other | required | Issue #522 AC1—AC9、本文 Traceability/Completion Audit、管理员配置开发基线均已同步 |
| Figma | required | `qmZEFvPrB8u9JX5fyqc93S / 3957:2` Design Context + Plugin readback + 两个创建状态 screenshot 均为当前新鲜证据 |

# 实施与兼容

- [x] Create Contract 移除客户端 `code` 输入，Response/DB `code` 保留。
- [x] HTTP 创建应用服务生成稳定唯一内部 code；Repository/Schema 不改，内部显式 code 调用兼容。
- [x] 前端创建品牌/车型不再显示、校验或提交 `code`；已有品牌 code 仅在技术信息只读展示。
- [x] OpenAPI 与 Orval generated client 通过正式生成链重新生成，未手改 generated client。
- [x] 补 Contract、SSR、Browser Mock 与 Real Full-stack 直接回归。
- [x] 同步管理员配置开发基线；正式 Figma 当前状态已与要求一致并完成 readback/screenshot 复核。
- [ ] PR Ready 后 required CI 全绿并完成独立 Review。
- [ ] merge 后 main required CI 全绿，再关闭 Requirement Issue 并清理任务分支。

# Completion Audit

- [x] upstream_re_read：已重新读取 Issue #522 AC1—AC9、当前 Create/Response Contract、HTTP 创建链、前端表单、generated artifacts、正式 Figma 页面与本轮验证结果；没有继续使用旧会话快照代替当前事实。
- [x] change_coverage：R1—R7 已有直接实现与新鲜证据；R8/R9 仅是按交付生命周期显式递延的 PR/post-merge CI 门禁，没有隐藏实现缺口。
- [x] reverse_audit：已从管理员新增品牌/车型动作反查 `CatalogConfigurationPanel` → Orval generated client → FastAPI/Pydantic Create Contract → Bootstrap Application Service → Repository/DB → Response；client code 输入在 UI、payload、Contract 三层均被切断，Response/DB code 保留。
- [x] unresolved_cleared：当前无 `not_satisfied` Requirement；唯一剩余项是 R8 正式 PR CI 与 R9 post-merge main CI，均有明确执行时点且在完成前不会宣称通过或关闭 #522。

# 本轮验证证据

1. 正式 Contract 生成链 workflow run `35177820419`：`uv run python scripts/contracts/generate.py` + `npm --prefix frontend run generate:api` success，生成提交 `9f1c2fd9ce6f9a485b5bdfc86afdb4b2d32bb637`；临时 workflow 已删除。
2. Browser/Full-stack acceptance 更新 workflow run `35177948358` success；临时 workflow 已删除。
3. pre-ready validation run `35178746591` success：
   - `ruff format --check` success；
   - `ruff check` success；
   - `pytest -q tests/api/test_brand_vehicle_stage2_contract.py` success；
   - OpenAPI + Orval regenerate 后 `git diff --exit-code -- contracts frontend/src/generated/api` success；
   - frontend lint/typecheck/unit/build success；
   - `test:e2e -- e2e/admin-configuration-figma.spec.ts` success。
4. Figma：正式 source `qmZEFvPrB8u9JX5fyqc93S / 3957:2` 的新增品牌 `7511:11637`、新增车型 `7511:11276` 完成当前 Design Context 与截图复核；Plugin 全页文本扫描只发现 DEV 规格中的两处 code 说明，且均明确“服务端创建时生成、创建请求不接收 code、响应仍返回 code”。
5. 正式 PR required CI 和 post-merge main CI 不提前冒充；分别在 Ready/merge 后执行并回填最终证据。
