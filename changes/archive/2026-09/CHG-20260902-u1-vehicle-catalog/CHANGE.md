---
schema: coding-change/v1
id: CHG-20260902-u1-vehicle-catalog
title: U1 车型目录与词包资源统一
level: L3
status: done
owner: codex
branch: test/294-vp5-u1-u5-runtime-validation
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas:
  - vehicles
  - system
  - collection
  - ingestion
  - api
  - contracts
  - frontend
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/vehicles/
  - backend/src/aima_ugc/modules/system/
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/contracts/http.py
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/admin-configuration/
  - tests/
  - docs/
contracts:
  - Vehicle Catalog HTTP Contract
  - Keyword Pack to Vehicle Model references
  - Matching Resource Snapshot V2
data_changes:
  - vehicle_catalog_versions
  - vehicle_models
  - vehicle_model_aliases
  - keyword_pack_vehicle_models
---

# 背景、目标与边界

车型当前只存在于 Prompt/Excel 使用语境，没有稳定目录、别名、版本或词包引用。U1 建立独立 Vehicle Catalog，并让 Keyword Pack 显式引用车型；不把车型降级为普通关键词，不改变现有只选词包的合法行为。

范围包括车型目录、别名冲突校验、目录版本、Pack↔车型关系、统一只读选择投影和未来任务可冻结的 V2 Snapshot。非目标包括内容车型证据、AI 自由创造车型、飞书登录和 Analysis Scheme 切换。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 一条内容允许 0..N 个车型且不设主车型 | user:2026-09-02-recommended-decisions | satisfied | 用户确认其余语义按推荐方案执行 |
| R2 | 同维度 OR、不同维度 AND | user:2026-09-02-recommended-decisions | satisfied | 用户确认其余语义按推荐方案执行 |
| R3 | 车型与词包独立建模，通过显式关系组合 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | 用户确认推荐方案 |
| R4 | 别名冲突不能自动选中，必须人工消歧 | user:2026-09-02-recommended-decisions | satisfied | 用户确认推荐方案 |
| R5 | 未引用车型可删除；已引用车型只能停用、改名或合并 | user:2026-09-02-vehicle-delete-decision | satisfied | 当前对话确认的修订规则 |
| R6 | 新任务冻结 Pack/车型版本和解析结果；旧 V1 继续执行 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | additive V2，不删除 keyword_pack_ids |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 车型、别名、版本、冲突、删除资格和选择快照 |
| 接口 / Contract | required | Pydantic→OpenAPI→Orval additive Contract |
| Backend/API/PostgreSQL | required | FK/UNIQUE、版本递增、Pack 引用与删除守卫 |
| Browser Mock Acceptance | required | 管理员车型与词包关联工作流 |
| Real Full-stack Golden Path | required | 新建车型→关联词包→重新读取 |
| External Provider Probe | not_applicable | 不改变 TikHub 当前接口事实 |
| Build / Runtime | required | 后端静态检查、前端 typecheck/build |
| Docs / Governance / Other | required | Blueprint/Roadmap/README/Change 门禁 |

# 实施与兼容

- [x] Red：建立目录、冲突、删除和 Contract 失败测试。
- [x] Green：实现表、Migration、Repository、Service、HTTP 与生成链。
- [x] 让现有 Keyword Pack 能显式引用车型并输出冻结选择身份。
- [x] 同步管理员页面入口、文档并执行 Deep Review。

现有 Keyword Pack、Collection Plan、Import V1 Contract 保持合法；所有新增字段 additive。回滚应用时保留新增表，Migration downgrade 仅在没有下游引用时允许。

# Completion Audit

- [x] upstream_re_read：已重新读取车型与词包用户决定、路线、Contract、Schema、实现和最终验证事实。
- [x] change_coverage：车型目录、别名、版本、冲突、删除资格和词包选择快照均有实现与测试证据。
- [x] reverse_audit：已从管理员车型和词包工作流反查 API、持久化约束及真实全栈闭环。
- [x] unresolved_cleared：所有 Required 项均有证据，无未决语义或 `not_satisfied`。

当前无语义未决项：本地 required 验证与独立 Review 已完成。

# 本轮验证证据

- Windows 可支持 Unit 范围：`723 passed, 8 skipped, 0 failed`；完整 Unit 另有 9 条已知 POSIX-only 失败，交由 Ubuntu PR CI 作权威门禁；
- 生成后 Contract 专项：`101 passed, 0 failed`；OpenAPI 与 Orval Client 重新生成成功；
- 前端：ESLint、TypeScript/Vue typecheck、`67 passed`、production build 通过；
- 变更集 Ruff、全后端 Mypy、六项架构/Owner/Secret/Docs/Governance 门禁通过；
- PostgreSQL 18.4 空库真实升级到 `20260902_0038` 且 `alembic check` 无漂移；既有 `0037` 开发库保留 1 条 Scheme Version 升级到 `0038`；
- PostgreSQL Integration `186 passed`；Real Full-stack 中“新建车型→关联词包→重新读取”通过。

# 交付完成证据

- PR #289 已把 U1–U5 前端与文档接线合并到 `main`（merge commit `b5622e2308193da4bb6878672944f38938bf46d5`）；PR #295 又完成恢复验证与基线修复（merge commit `f60f598c84e0696873cc01fc30f4d817ed51ae52`）；
- `main` 的 CI run #33589659720 与 Runtime Acceptance run #33589659537 均成功，覆盖产品、PostgreSQL、真实浏览器和 Compose 门禁；
- 本 Change 的实现、验证、Review、合并与 main 新鲜验证已闭环，因此转为 `done` 并归档。
