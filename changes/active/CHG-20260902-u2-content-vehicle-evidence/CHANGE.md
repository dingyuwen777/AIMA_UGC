---
schema: coding-change/v1
id: CHG-20260902-u2-content-vehicle-evidence
title: U2 内容车型证据与查询增强
level: L3
status: ready_for_review
owner: codex
branch: test/294-vp5-u1-u5-runtime-validation
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: [CHG-20260902-u1-vehicle-catalog]
affected_areas: [vehicles, content, analysis, ingestion, api, contracts, frontend, reporting, documentation]
affected_paths:
  - backend/src/aima_ugc/modules/vehicles/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/product.py
  - backend/src/aima_ugc/contracts/http.py
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/voice-plaza/
  - tests/
  - docs/
contracts:
  - Content vehicle evidence projection
  - Content vehicle filters and facets
data_changes: [content_vehicle_evidence]
---

# 背景、目标与边界

U2 把车型从选择资源升级为可追溯的内容匹配事实。每条内容可有零到多个车型，每条关联保留方法、命中文本、来源字段、目录版本和证据来源；人工修正是追加事实并锁定，不被后续 AI 自动覆盖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 内容车型是 0..N、多证据、无主车型 | user:2026-09-02-recommended-decisions | satisfied | 用户确认推荐方案 |
| R2 | 先确定性别名匹配；歧义不落确定车型；无候选保持未识别 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | 用户确认推荐方案 |
| R3 | 人工修正后禁止后续 AI 自动覆盖，除非人工解除锁定 | user:2026-09-02-recommended-decisions | satisfied | 用户确认其余语义按推荐方案 |
| R4 | 声音广场支持车型筛选并展示证据，不在前端二次筛选 | AGENTS.md | satisfied | 生产 Query Repository 与 generated Client 为唯一链 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 别名匹配、歧义、人工锁定和证据排序 |
| 接口 / Contract | required | Content list/detail/filter/facet additive Contract |
| Backend/API/PostgreSQL | required | 多车型 FK/幂等/追加证据与真实查询 |
| Browser Mock Acceptance | required | 车型筛选、证据展示、未识别与人工修正 |
| Real Full-stack Golden Path | required | 内容→匹配→筛选→详情 |
| External Provider Probe | not_applicable | 不改变 Provider operation |
| Build / Runtime | required | 后端与前端构建 |
| Docs / Governance / Other | required | Content/Vehicle Owner 与路线同步 |

# 实施步骤

- [x] Red：车型匹配、人工锁定、查询与 Contract 回归。
- [x] Green：Evidence 表、Repository/Service、查询投影与前端。
- [x] 接入统一导入后的确定性匹配入口，不复制 Mapper/Content Owner。
- [x] 同步文档并执行 Deep Review。

# Completion Audit

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [x] unresolved_cleared

当前无语义未决项：本地 required 验证与独立 Review 已完成，本 Change 进入 `ready_for_review`；PR CI、合并与 main 新鲜验证仍是外部交付门禁。

# 本轮验证证据

- API/Contract/Unit 受支持范围：`866 passed, 8 skipped, 0 failed`；U1–U5 目标 Contract/API/Schema 测试包含车型当前版本、人工锁和查询投影；
- 前端车型筛选、列表、详情、人工复核、导入和采集计划入口已做反向能力审计，ESLint/typecheck、`67 passed`、production build 通过；
- 变更集 Ruff、全后端 Mypy、六项质量门禁与 `git diff --check` 通过；
- PostgreSQL Integration `186 passed`，覆盖车型 FK、证据、人工锁、查询和导出投影；
- Real Full-stack 已通过“Excel 导入→车型别名匹配→车型筛选→详情证据”闭环。
