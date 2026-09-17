---
schema: coding-change/v1
id: CHG-20260917-server-generated-catalog-code
title: 品牌与车型 code 改为服务端生成并同步 Figma
level: L3
status: in_progress
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
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_http.py
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/admin-configuration/
  - tests/
  - docs/guides/02_管理员配置Figma开发基线.md
contracts:
  - Brand Create HTTP Contract
  - Vehicle Model Create HTTP Contract
  - Brand/Vehicle Response Contract
data_changes: []
---

# 背景、目标与边界

Requirement Source：GitHub Issue #522。

管理员配置当前要求人工填写 Brand Code / Vehicle Code。业务决定调整为：数据库 `code` 列、唯一约束、已有数据和响应 Contract 继续保留，但新建 Brand/Vehicle 的 `code` 改为服务端生成的内部稳定字段，管理员不再输入或控制该值，并同步正式 Figma 管理员配置页。

本次不删除数据库字段、不新增 Migration、不修改既有资源 `code`，也不改变品牌/车型的删除、合并、别名、归属等既有业务语义。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | BrandCreateRequest 不再接收 `code`，创建后响应仍返回服务端生成 `code` | issue:#522 | in_progress | 待实现与 Contract/API 验证 |
| R2 | VehicleModelCreateRequest 不再接收 `code`，创建后响应仍返回服务端生成 `code` | issue:#522 | in_progress | 待实现与 Contract/API 验证 |
| R3 | 客户端不能控制新建资源内部 `code`，旧客户端额外提交 `code` 明确失败 | issue:#521/#522 | in_progress | 待 Pydantic extra=forbid Contract 验证 |
| R4 | DB `code` 列、唯一约束、既有记录保持不变，无 Migration | issue:#522 | in_progress | 待 Schema/compare 审计 |
| R5 | 管理员新增品牌/车型不再展示、校验或提交编码 | issue:#522 | in_progress | 待 Frontend test/build |
| R6 | OpenAPI 与 Orval generated client 跟随 Pydantic 重新生成 | issue:#522 | in_progress | 待 CI generated drift gate |
| R7 | 正式 Figma 同步移除人工编码输入，并标明 code 为服务端内部技术字段 | issue:#522 | in_progress | 待 Figma readback/screenshot |
| R8 | 合并后 main required CI 重新通过 | issue:#522 | in_progress | 待 post-merge fresh CI |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 服务端 code 生成规则；管理员创建表单不依赖 code |
| 接口 / Contract | required | Pydantic → OpenAPI → Orval；create 无 code、response 有 code、extra forbid |
| Backend/API/PostgreSQL | required | Brand/Vehicle 创建持久化、唯一 code、DB Schema 无迁移 |
| Browser Mock Acceptance | required | 管理员新增品牌/车型 UI 无编码输入并可提交 |
| Real Full-stack Golden Path | required | 管理员创建品牌/车型经 API/DB 成功返回服务端 code |
| External Provider Probe | not_applicable | 不改变 TikHub/外部 Provider |
| Build / Runtime | required | 后端静态门禁、前端 lint/test/build、启动/CI 按分类执行 |
| Docs / Governance / Other | required | 管理员配置开发基线、Change Completion、PR Requirement Source |
| Figma | required | 正式管理员配置页修改后截图/readback |

# 实施与兼容

- [ ] Create Contract 移除客户端 `code` 输入，Response/DB `code` 保留。
- [ ] Repository 在未显式传入 code 时生成稳定唯一内部 code，同时保留必要内部显式调用兼容。
- [ ] HTTP 创建路径不再从请求读取 `code`。
- [ ] 前端创建品牌/车型不再显示、校验或提交 `code`；技术信息只读展示已有 code。
- [ ] OpenAPI 与 Orval generated client 同步。
- [ ] 补 Contract/API/PostgreSQL/Frontend 直接回归。
- [ ] 同步管理员配置开发基线与正式 Figma。

# Completion Audit

- [ ] upstream_re_read：合并前重新读取 Issue #522、当前 Contract/实现、Figma 和验证事实。
- [ ] change_coverage：R1-R8 均有直接实现与证据。
- [ ] reverse_audit：从管理员创建动作反查 Frontend → generated client → API → Repository → DB → Response。
- [ ] unresolved_cleared：required 项无 `not_satisfied` 或未说明 blocker。

# 本轮验证证据

施工中；最终只记录本轮真实执行的命令/CI/Figma readback，不复制旧结果。
