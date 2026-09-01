---
schema: coding-change/v1
id: CHG-20260902-u1-vehicle-catalog
title: U1 车型目录与词包资源统一
level: L3
status: in_progress
owner: codex
branch: main
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas: [vehicles, system, collection, ingestion, api, contracts, frontend, documentation]
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

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [ ] unresolved_cleared

当前未清零项：本机 Docker Desktop Linux Engine 因 `dockerInference` reparse point 故障不可用，且无独立 PostgreSQL 二进制；真实 Migration、PostgreSQL Integration 与 Real Full-stack 证据尚未取得，因此本 Change 保持 `in_progress`。

# 本轮验证证据

- API/Contract/Unit 受支持范围：`866 passed, 8 skipped, 0 failed`；
- 生成后 Contract 专项：`101 passed, 0 failed`；OpenAPI 与 Orval Client 重新生成成功；
- 前端：ESLint、TypeScript/Vue typecheck、`67 passed`、production build 通过；
- 变更集 Ruff、全后端 Mypy、六项架构/Owner/Secret/Docs/Governance 门禁通过；
- Alembic 静态链为 `20260902_0031 -> ... -> 20260902_0036 (head)`；未把静态链检查写成真实迁移成功。
