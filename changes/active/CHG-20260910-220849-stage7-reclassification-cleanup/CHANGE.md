---
schema: coding-change/v1
id: CHG-20260910-220849-stage7-reclassification-cleanup
title: 搜索与品牌车型过滤 Stage 7 旧数据回填与 Cleanup
level: L3
status: in_progress
owner: chatgpt
branch: feat/stage7-reclassification-cleanup
created: 2026-09-10
updated: 2026-09-10
completion_gate: required
depends_on:
  - CHG-20260909-235500-stage3-excel-brand-vehicle-filter
  - CHG-20260910-132342-stage4-tikhub-search-brand-filter
  - CHG-20260910-171533-stage5-query-contract-export
  - CHG-20260910-194112-stage6-frontend-productization
affected_areas:
  - ingestion
  - vehicles
  - collection
  - jobs
  - contracts
  - database
  - frontend
  - tests
  - docs
  - operations
affected_paths:
  - backend/src/aima_ugc/modules/ingestion
  - backend/src/aima_ugc/modules/vehicles
  - backend/src/aima_ugc/modules/collection
  - backend/src/aima_ugc/modules/jobs
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/contracts
  - backend/src/aima_ugc/database_schema.py
  - backend/src/aima_ugc/adapters/persistence/postgres
  - migrations/versions
  - contracts
  - frontend/src/generated
  - frontend/src/features/collection-strategy
  - tests
  - docs/product
  - docs/blueprint
  - docs/appendix
  - docs/operations
  - docs/roadmap
contracts:
  - content brand and vehicle reclassification job payload
  - persistent job retry cancel progress and result contract
  - brand and vehicle evidence persistence contract
  - legacy collection configuration HTTP contract removal
  - OpenAPI and generated TypeScript client
data_changes:
  - 独立批处理幂等补齐旧 Content Version 的 Brand/Vehicle Evidence，不修改 Content Current
  - 受门禁保护的 Cleanup Migration 删除三组 Legacy 表并保留可恢复备份
  - vehicle_models.brand_id 在缺少真实生产数据证明时继续保持 nullable
---

# 背景与目标

实施 [`docs/roadmap/04_搜索与品牌车型过滤实施路线.md`](../../../docs/roadmap/04_搜索与品牌车型过滤实施路线.md) Stage 7。目标是在 Stage 1—6 已稳定的新写入、查询和前端链上，建立数千万级旧 Content 的可恢复重分类能力，按 fail-closed 门禁清理已退出生产调用链的 Legacy Schema/Contract/Repository/UI，并完成整条 Roadmap 的 Completion Audit 与生命周期收尾。

Requirement Source：#437。

# 范围与非目标

- 范围：旧 Content Brand/Vehicle Reclassification 持久 Job；Cleanup preflight 与可恢复 Migration；旧 API/Contract/Repository/UI/生成物清理；分层验证；长期文档；Stage 1—7 总体 Completion Audit；Roadmap 退出 live 目录；端到端 Git 交付与原生归档。
- 非目标：不执行生产部署、生产回填或生产 Migration；不调用 TikHub/LLM；不改变 Provider family、AI taxonomy、认证授权或预算模型；不升级依赖；Stage 7 不新增 Figma 能力。
- 必须保持：PostgreSQL 单一业务事实库；正式 Resolver/Evidence/Job Runtime Owner；Pydantic → OpenAPI → generated client 唯一 HTTP 类型链；不从旧词包关系猜 Brand Ownership；不在 Alembic Migration 扫描 Content；不降低 fencing/retry/cancel/Secret/回滚门禁。

# 已确认方案与待证门禁

1. Reclassification 作为新的版本化持久 Job，复用既有 Job Runtime、Vehicles Resolver 与 Ingestion Evidence 写 Owner；分两层执行，使用 keyset + shard + checkpoint 有界推进。
2. 第一层只从当前有效 Vehicle Evidence 与真实 `vehicle_models.brand_id` 推导 `source=vehicle_match` Brand Evidence；第二层只读取 Current Content 的 `title + text`，使用 Job 创建时冻结的 Catalog Snapshot 解析并幂等写 Evidence。
3. Cleanup 使用“代码调用链静态门禁 + 数据库运行前 preflight + 可恢复备份 + Alembic Schema 变更”的组合。Migration 不承担数千万 Content 回填，也不能把 Fixture 当生产执行证明。
4. `vehicle_models.brand_id NOT NULL` 有三种方案：A. 无证据也直接收紧（拒绝，会制造未知归属或生产失败）；B. 创建 unknown Brand 后收紧（拒绝，违反正式语义）；C. 缺少真实生产数据直接证据时保持 nullable，并由 preflight/运维对账报告未归属记录（采用）。
5. Legacy 数据备份有三种方案：A. 只在 downgrade 重建空表（拒绝，不可恢复）；B. Migration 内复制到固定 archive 表后 Drop，再由 downgrade 恢复（候选，需核对项目 Migration/运维惯例）；C. 独立导出 Artifact + 显式确认 token（候选，需核对现有 Artifact/运维入口）。最终选型以当前 Schema、部署与备份事实为准。
6. 旧 queued/running Job、Brand Ownership、Backend/Frontend/generated consumer、新 Filter/Query/Export 和备份任一缺少直接证据时，Cleanup 必须 fail closed；生产执行授权不包含在本开发任务中。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正式持久 Job 分两层完成旧 Content Brand/Vehicle Reclassification | #437 / AC1；Roadmap Stage 7 | not_satisfied | 待实现与验证。 |
| R2 | keyset/shard/checkpoint、retry/cancel/progress/recovery、幂等、统计对账；不调用 LLM、不改 Content Current | #437 / AC2；Roadmap Stage 7 | not_satisfied | 待实现与验证。 |
| R3 | Cleanup preflight 对全部前置条件 fail closed | #437 / AC3；Roadmap Stage 7 | not_satisfied | 待实现与验证。 |
| R4 | 满足门禁时删除三组 Legacy 表及对应旧 API/Contract/Repository/UI，Migration 可恢复且生成物无漂移 | #437 / AC4；Roadmap Stage 7 | not_satisfied | 待实现与验证。 |
| R5 | 只有真实数据证明时才收紧 brand_id；否则 nullable 且不制造 unknown Brand | #437 / AC5；Roadmap Stage 7 | not_satisfied | 待实现与验证。 |
| R6 | 完成 Schema/数据链反向审计与分层回归 | #437 / AC6；Roadmap Stage 7 | not_satisfied | 待实现与验证。 |
| R7 | 长期文档、Roadmap 03 关系和 Roadmap 04 生命周期正确收口 | #437 / AC7；Roadmap Stage 7 | not_satisfied | 待实现与验证。 |
| R8 | L3 Completion/Review/CI/merge/main/archive/Closure/cleanup 完整交付 | #437 / AC8；Roadmap 固定执行口令 | not_satisfied | 待后续交付门禁。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Reclassification 两层选择、keyset/shard/checkpoint、幂等、统计、cancel/retry/recovery 与 Cleanup preflight Red→Green。 |
| 接口 / Contract | required | Job Payload/Result、Pydantic/OpenAPI/generated client 删除 Legacy Contract 后生成与兼容检查。 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 18 上 Evidence 写入、Job Runtime、Migration upgrade/downgrade、备份恢复与 fail-closed preflight。 |
| 用户 / Workflow Acceptance | required | 受影响 Browser Mock 回归证明生产前端没有 Legacy 入口且新 Brand/Vehicle/Competition 路径不回退。 |
| 跨组件 Golden Path | required | Real Full-stack 覆盖新 Filter/Query/Export 与至少一条旧 Content Reclassification → Voice Plaza/Export 关键链。 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub/LLM Operation 或真实第三方字段，且用户明确禁止付费 Probe；Fixture/Contract 回归足够。 |
| Build / Package / Runtime | required | 后端质量门禁、前端 lint/typecheck/unit/build、Migration/Worker 启动与正式 CI。 |
| Docs / Governance / Other | required | 文档事实、Secret、Change/Ready、Deep Review、PR/main CI、原生归档、Issue Closure 与 Roadmap 生命周期。 |

# 任务与验证计划

1. 恢复 Schema/Migration、Evidence/Resolver、Job/Worker、Legacy consumer、generated client、测试/CI/Operations 的当前事实，固定最终设计和 Cleanup 数据门禁。
2. 先建立 Reclassification 与 Cleanup preflight 的失败测试，再实现最小生产能力和 PostgreSQL 集成。
3. 生成 Cleanup Migration，删除旧 Contract/Repository/UI，重新生成 OpenAPI/client，并完成 downgrade/备份恢复证据。
4. 执行 targeted → module → Contract/Migration/PostgreSQL → Browser/Full-stack → CI 等价验证；修复 Finding 后重验。
5. 同步 Product/Blueprint/Appendix/Operations/README，执行 Stage 1—7 Completion Audit，让 Roadmap 04 退出 live roadmap。
6. Change 进入 `ready_for_review` 后完成 Deep Review、current-head CI、guarded merge、main fresh CI、原生归档、Closure Audit 与分支清理。

# 兼容、迁移、部署与回滚

- 公共 Contract 会删除只服务 Legacy 配置的接口/类型；当前生产消费者必须先由调用链、生成物和 Browser/Full-stack 证据证明已退出。
- 新 Reclassification Job 使用新 job type/payload version，不篡改旧 queued/running Job 语义；旧 Job 兼容结论必须由注册、payload 与数据库 preflight 直接证明。
- Cleanup Migration 只在数据库门禁满足时执行；生产仍须单独授权、备份、运行前对账与部署窗口。
- `vehicle_models.brand_id` 当前默认不收紧；未来真实数据满足时必须作为新的有证据 Schema 决策，不能由本次 Fixture 代替。
- downgrade/回滚必须能恢复被 Drop 的 Legacy 结构与原数据；不能只创建空表。应用回滚与数据库 downgrade 的先后顺序将在 Operations 中明确。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 #437、Roadmap Stage 7 与整条 Stage 1—7、Roadmap 03 关系、Blueprint/Contract/Schema/Operations 和当前 main。
- [ ] change_coverage：独立比较 AC1—AC8/R1—R8 与实现、测试、文档、Migration、交付证据，确认没有 requirement omission。
- [ ] reverse_audit：执行 Schema writer→Migration→reader、Excel/TikHub→Resolver→Content→Voice Plaza/Export、旧数据/Legacy 清理对账，以及前后端/异步状态反向审计。
- [ ] two_stage_review：A1 上游→Change、A2 Change→实现/测试/文档；随后完成代码质量、安全、兼容、Migration、回滚和测试充分性 Deep Review。
- [ ] unresolved_cleared：Ready 前清零 not_satisfied；所有 deferred/N/A 必须有正式依据，生产未执行项不得冒充已验证。
