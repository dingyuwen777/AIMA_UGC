---
schema: coding-change/v1
id: CHG-20260909-204600-stage2-brand-vehicle-resolver
title: 搜索与品牌车型过滤 Stage 2 管理面与统一解析器
level: L3
status: ready_for_review
owner: chatgpt
branch: feature/stage2-brand-vehicle-resolver
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - vehicles
  - administration
  - contracts
  - database
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/vehicles/models.py
  - backend/src/aima_ugc/modules/vehicles/resolver.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/contracts/brand_vehicle.py
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_http.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_routes.py
  - backend/src/aima_ugc/entrypoints/api_main.py
  - tests/unit/vehicles/test_brand_vehicle_resolver.py
  - tests/integration/database/test_brand_vehicle_stage2.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - docs/blueprint/03_数据库与文件存储.md
contracts:
  - Administration HTTP / OpenAPI
data_changes:
  - 复用 Stage 1 Schema；仅通过现有表写 Brand/Vehicle 主数据与证据，不猜测或批量反推历史品牌
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 2：在 Stage 1 Schema 基础上形成唯一 Brand/Vehicle 主数据管理面、统一冻结 Catalog Snapshot 与纯确定性 `BrandVehicleResolver`，为 Stage 3/4 提供可复现前置能力。本 Change 不接入 Excel/TikHub Runtime、不改变 Collection Plan/Keyword Pack 既有运行语义、不修改声音广场 UI，也不进入 Stage 3/4。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Brand CRUD/Alias/生命周期/审计与共享 catalog version | #418 / AC1 | satisfied | `brand_vehicle.py`、`brand_vehicle_http.py`、扩展管理路由；Brand/Vehicle 共用 `vehicle_catalog_versions` |
| R2 | 现有 Vehicle Create/Update/Read 正式包含 `brand_id`；active Vehicle 必须绑定 active Brand，旧数据只显式修复 | #418 / AC2 | satisfied | `contracts/administration.py` + `administration_http.py` + `PostgresVehicleCatalogRepository` 唯一写 Owner；独立 assignment 也委托该 Owner |
| R3 | 冻结 `CatalogSnapshot` 支持 `all_active` / `selected brand_ids`，selected Brand 自动包含全部 active Vehicle；旧 Collection Snapshot 保持兼容 | #418 / AC3 | satisfied | `CatalogSnapshot` + `catalog_snapshot(filter_mode, selected_brand_ids)`；共享 seed lock 冻结 catalog version；`VehicleCatalogSnapshot` 与旧 Collection 路径未改 |
| R4 | 纯确定性 Resolver 消费 `CanonicalContentV1 + frozen CatalogSnapshot`，允许多实体同时命中，只对同 Alias 多候选保留歧义且不猜 | #418 / AC4 | satisfied | `BrandVehicleResolver` + unit tests；正式输出 `matched/brand_matches/vehicle_matches/effective_*_ids/conflicts` |
| R5 | Brand Evidence/review lock 可持久化，自动替换尊重 Brand/Vehicle 人工锁 | #418 / AC5 | satisfied | `replace_automatic_*_evidence`、`replace_manual_*_evidence` + PostgreSQL integration test |
| R6 | 真实 PostgreSQL 覆盖 Brand/Vehicle 管理、共享版本、active Brand 不变量、legacy 显式修复、两种 Snapshot 与人工锁 | #418 / AC6 | explicitly_deferred | 测试已补齐；等待当前最终 PR HEAD 正式 PostgreSQL CI，不豁免 |
| R7 | Collection/Keyword Pack 现有 Contract/引用/运行行为不变，不实施 Runtime 自动过滤/UI/Legacy 删除 | #418 / AC7 | satisfied | 旧 `VehicleCatalogSnapshot`、Pack/Plan 关系与 Runtime 未切换；全量回归作为最终证据 |
| R8 | OpenAPI/生成客户端/事实文档同步；Resolver 单测覆盖 Canonical 输入、多实体/歧义/unmatched/scope | #418 / AC8 | satisfied | OpenAPI/client 已重新生成；事实文档已同步；Resolver 定向测试覆盖 Canonical、多实体、歧义、unmatched 与冻结 scope，最终仍由正式 generated/docs gate 复核 |
| R9 | Completion Audit、独立 Review、PR HEAD/main fresh CI、expected-head merge、原生归档和 Roadmap 收口 | #418 / AC9 | explicitly_deferred | 交付生命周期后置门禁，不豁免；Stage 2 未满足前不合并，不自动启动 Stage 3/4 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit | required | `CanonicalContentV1`、Vehicle→Brand、多非歧义实体、同 Alias 歧义、unmatched、冻结 scope |
| Contract/API | required | 既有 Vehicle Create/Update/Read `brand_id` + Brand CRUD/assignment/integrity/snapshot OpenAPI 与 API 回归 |
| PostgreSQL Integration | required | Brand/Vehicle CRUD/Alias、shared catalog version、active Brand invariant、legacy 显式修复、all_active/selected Snapshot、Brand/Vehicle lock |
| Generated Client | required | OpenAPI/client 生成一致性 |
| Collection regression | required | 既有 Vehicle snapshot、Keyword Pack/Collection 语义不变 |
| Docs/Governance | required | Change、Issue AC、facts、Review、CI、main/归档/Roadmap 收口 |

# 实施事实

1. Brand CRUD/Alias/lifecycle 由 `PostgresBrandVehicleCatalogRepository` 管理；目录变更与 Vehicle 共用 `vehicle_catalog_versions`。
2. `vehicle_models` 的写入 Owner 仍唯一为 `PostgresVehicleCatalogRepository`；Brand façade 的独立归属入口只委托 `assign_brand()`，不建立第二个 Vehicle 写 Owner。
3. 既有 `/vehicle-models` Create Contract 现在必须提供 `brand_id`；Update/Read 也公开 `brand_id`。任何最终为 active 的 Vehicle 都必须拥有有效 active Brand；停用存在 active children 的 Brand fail closed。
4. 历史 active Vehicle 若 `brand_id IS NULL`，完整性检查会显式暴露；`all_active` Snapshot 在修复前 fail closed，只能通过管理员/受控显式赋值修复，不从 Keyword Pack 或旧关系猜测。
5. `CatalogSnapshot` 支持 `all_active` 和 `selected brand_ids`；selected Brand 自动包含其全部 active Vehicle 与对应 Alias。Snapshot 在事务内对 catalog seed 取共享锁，目录写在同 seed 上取排它锁，从而冻结版本与实体集合。
6. `BrandVehicleResolver` 只读取 `CanonicalContentV1.title/text` 和冻结 Snapshot；无 LLM/Embedding/网络调用。不同 Alias 的多个 Brand/Vehicle 可同时返回；仅同一 normalized Alias 对应多个 active 实体时输出 `conflicts` 且不猜。
7. Brand/Vehicle 自动 Evidence 替换在人工锁存在时拒绝覆盖；Evidence 保留匹配文本、来源字段、catalog version、confidence 等追溯事实。
8. Stage 2 无新 Migration：继续复用 Stage 1 nullable `vehicle_models.brand_id` 作为历史显式修复窗口；不改写历史数据，不增加猜测型 backfill。

# Completion Audit

- [x] upstream_re_read：已重读最新 main、Roadmap Stage 2/Exit、Stage 1 Schema、现有 Vehicle Repository/Administration/API assembly 与 Agent_Skills Source Mode 约束。
- [x] change_coverage：AC1-AC9 已映射到 Brand 管理、Vehicle 唯一 Owner、归属不变量、Snapshot、Resolver、证据锁、真实 PG、兼容、Contract/docs 与交付生命周期。
- [x] reverse_audit：已从 `vehicle_models` 写路径、公共 Vehicle API、Brand 生命周期、Catalog Version 锁、Collection 旧 Snapshot、证据锁和 Stage 3 reader 反查；没有第二套 catalog version、第二个 Vehicle 写 Owner 或旧词包反推品牌。
- [x] unresolved_cleared：实现决策、Owner 边界、Contract、Scope 和兼容策略均已收敛；剩余事项仅为 R6/R9 明示的正式 CI、独立 Review 和交付生命周期证据，不存在未决实现方案。
- [ ] final_validation：等待最终 PR HEAD 全量 CI、真实 PostgreSQL/API、generated/docs gate 全绿。
- [ ] independent_review：等待稳定最终 HEAD 后执行独立 Review，并清零阻断 P0/P1/P2。
- [ ] delivery_closure：等待 expected-head merge、main fresh CI、Change 原生归档、Issue/Roadmap/branch 收口。

# 当前证据

- 开工基线 `main=ebecba7efaaab73ca0ecca30ce65b82bbc36bb4e`；Stage 1 completed、Stage 2 planned。
- Issue #418 是本 Stage 稳定需求源；PR #419 是实现交付链。
- 一次性 branch-only 同步 Run `34356450692` 已成功执行 frozen env、Ruff format/lint、OpenAPI/client 生成和 Resolver 定向测试，并提交 canonical generated outputs；临时 Workflow/patch script 均已从分支删除，不进入最终 diff。
- 文档/格式预验证 Run `34357180710` 已成功执行事实文档补丁、最新 Python Ruff format/lint 与 Resolver 定向测试；临时 Workflow/patch script 同样已清理。
- Resolver 事实源字段已校准为真实 `CanonicalContentV1.title/text`；不再使用不存在的 `raw_text/transcript_text`。
- PostgreSQL 测试已补齐 active Vehicle→active Brand 不变量、`all_active/selected` Scope、历史未归属显式修复和 Brand/Vehicle 人工锁；正式结果以当前 PR HEAD CI 为准。
- 首次正式 PR run `34357304745` 已确认 Requirement Source 通过、CI profile=contract、PostgreSQL suites=all、Full-stack specs=all；其唯一前置失败是 Change 状态仍使用旧值 `active`，导致后续作业按门禁设计跳过。现已改为仓库当前支持的 `ready_for_review`，不把被跳过作业视为通过。
- 本 Change 尚未完成：R6/R9 与三个最终交付项必须在最终门禁后更新，当前不得合并。