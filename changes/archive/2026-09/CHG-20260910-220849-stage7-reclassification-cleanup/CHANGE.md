---
schema: coding-change/v1
id: CHG-20260910-220849-stage7-reclassification-cleanup
title: 搜索与品牌车型过滤 Stage 7 旧数据回填与 Cleanup
level: L3
status: done
owner: chatgpt
branch: feat/stage7-reclassification-cleanup
created: 2026-09-10
updated: 2026-09-11
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
  - ci
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
  - .github/workflows/ci.yml
  - scripts/quality/classify_ci_scope.py
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
  - 受门禁保护的 Cleanup Migration 只删除三组空 Legacy 表，downgrade 恢复空表结构
  - vehicle_models.brand_id 在缺少真实生产数据证明时继续保持 nullable
---

# 背景与目标

实施历史上游 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` 的 Stage 7。该 Roadmap 在本 Change 完成生命周期收尾时按批准规则退出 live 目录；完整验收要求继续由 Requirement Source #437 持有。目标是在 Stage 1—6 已稳定的新写入、查询和前端链上，建立数千万级旧 Content 的可恢复重分类能力，按 fail-closed 门禁清理已退出生产调用链的 Legacy Schema/Contract/Repository/UI，并完成整条 Roadmap 的 Completion Audit 与生命周期收尾。

Requirement Source：#437。

# 范围与非目标

- 范围：旧 Content Brand/Vehicle Reclassification 持久 Job；Cleanup preflight 与可恢复 Migration；旧 API/Contract/Repository/UI/生成物清理；分层验证；长期文档；Stage 1—7 总体 Completion Audit；Roadmap 退出 live 目录；端到端 Git 交付与原生归档。
- 非目标：不执行生产部署、生产回填或生产 Migration；不调用 TikHub/LLM；不改变 Provider family、AI taxonomy、认证授权或预算模型；不升级依赖；Stage 7 不新增 Figma 能力。
- 必须保持：PostgreSQL 单一业务事实库；正式 Resolver/Evidence/Job Runtime Owner；Pydantic → OpenAPI → generated client 唯一 HTTP 类型链；不从旧词包关系猜 Brand Ownership；不在 Alembic Migration 扫描 Content；不降低 fencing/retry/cancel/Secret/回滚门禁。

# 已确认方案与待证门禁

1. Reclassification 作为新的版本化持久 Job，复用既有 Job Runtime、Vehicles Resolver 与 Ingestion Evidence 写 Owner；分两层执行，使用 keyset + shard + checkpoint 有界推进。
2. 第一层只从当前有效 Vehicle Evidence 与真实 `vehicle_models.brand_id` 推导 `source=vehicle_match` Brand Evidence；第二层只读取 Current Content 的 `title + text`，使用 Job 创建时冻结的 Catalog Snapshot 解析并幂等写 Evidence。
3. Cleanup 使用“代码调用链静态门禁 + 数据库运行前 preflight + 空表断言 + Alembic Schema 变更/结构 downgrade”的组合。Owner 已确认不存在需备份的旧业务数据；Migration 不承担数千万 Content 回填，也不能把 Fixture 当生产执行证明。
4. `vehicle_models.brand_id NOT NULL` 有三种方案：A. 无证据也直接收紧（拒绝，会制造未知归属或生产失败）；B. 创建 unknown Brand 后收紧（拒绝，违反正式语义）；C. 缺少真实生产数据直接证据时保持 nullable，并由 preflight/运维对账报告未归属记录（采用）。
5. 业务 Owner 于 2026-09-10 明确确认当前尚未执行任何数据导入，不存在需保留的旧业务数据或旧排队任务兼容需求；Stage 7 一并删除 Legacy 代码、Contract、Schema/表和兼容分支。Migration upgrade 对任一非空 Legacy 表 fail closed，downgrade 恢复旧表结构；真实生产环境的空数据确认和 Migration 执行仍需独立授权。
6. Brand Ownership、Backend/Frontend/generated consumer、新 Filter/Query/Export 与 Migration 空表门禁任一缺少直接证据时，Cleanup 必须 fail closed；生产执行授权不包含在本开发任务中。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正式持久 Job 分两层完成旧 Content Brand/Vehicle Reclassification | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC1 | satisfied | `vehicles.content-reclassification.v1` 已由正式 Worker Registry 注册；第一层从当前非 alias Vehicle Evidence 与冻结 Ownership 生成 `vehicle_match` Brand Evidence，第二层以 Current `title + text`、冻结 Snapshot 和正式 Resolver 替换自动 alias Evidence；Unit、类型与代码审查通过。 |
| R2 | keyset/shard/checkpoint、retry/cancel/progress/recovery、幂等、统计对账；不调用 LLM、不改 Content Current | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC2 | satisfied | Run/Repository/Executor 已实现 UUID keyset、稳定 hash shard、有界 batch/max、同事务 Evidence+checkpoint、Fence、Job retry/cancel/heartbeat/progress、幂等键和九项对账统计；测试显式断言 Current/人工锁/重试与过期 Fence。 |
| R3 | Cleanup preflight 对全部前置条件 fail closed；任一 Legacy 表非空即拒绝 Upgrade | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC3 | satisfied | Migration `0047` 在任何 Drop 前检查三张 Legacy 表、旧 v1 Job、含 `keyword_selection` 的旧 Batch、旧 Run/Campaign Snapshot 和 active Vehicle Ownership；非空/冲突 Fixture 均要求事务拒绝。 |
| R4 | 满足门禁时删除三组 Legacy 表及对应旧 API/Contract/Repository/UI，Migration 可恢复且生成物无漂移 | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC4 | satisfied | `0047` 删除三表并在 downgrade 恢复经核对的空表结构；Owner 决定明确不存在旧数据，因此不伪造数据恢复。旧 API/Contract/Repository/UI/Job 分支及 Strategy Store 隐藏车型读取已删除；OpenAPI/client 生成、兼容与生产 consumer 搜索无漂移。 |
| R5 | 只有真实数据证明时才收紧 brand_id；否则 nullable 且不制造 unknown Brand | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC5 | satisfied | 当前 SQLAlchemy/Migration 继续保持 `vehicle_models.brand_id` nullable，未创建 unknown Brand；Cleanup 只对 active Vehicle 缺少有效 Ownership fail closed，正式文档同步该结论。 |
| R6 | 完成 Schema/数据链反向审计与分层回归 | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC6 | satisfied | 已沿 Schema writer/Migration/reader、Excel/TikHub→Resolver→Content→Voice Plaza/Export、Backend→Frontend/generated、Job→Worker 反查；本地 Unit 918 passed/8 skipped（另有 3 个已知 Windows POSIX-only 失败）、Contract 111、API 60、Stage 7 targeted 43、前端 Vitest 139、Browser 106、lint/typecheck/build 与文档/生成门禁通过；首轮 PR CI 的 PostgreSQL 18 已通过，Real Full-stack 暴露并已修复 Excel Fixture 对删除接口的调用，精确 current-head 仍须重跑 required CI。 |
| R7 | 长期文档、Roadmap 03 关系和 Roadmap 04 生命周期正确收口 | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC7 | satisfied | Product/Blueprint/Appendix/Operations/模块 README 已承接长期事实；Roadmap 03/05 已改为依赖当前 Brand/Vehicle Filter 机器事实；Roadmap 04 已从 live README 和文件树移除，历史需求由 #437、Change 与 Git 保留。 |
| R8 | L3 Completion/Review/CI/merge/main/archive/Closure/cleanup 完整交付 | https://github.com/dingyuwen777/AIMA_UGC/issues/437#AC8 | explicitly_deferred | Requirement Traceability、Validation Matrix、Completion Audit 与 Deep Review 已完成；PR current-head CI、expected-head guarded merge、main fresh CI、原生归档、Issue Closure 和分支清理按强制顺序只能在 Ready 后执行。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Stage 7 targeted 43/43；完整后端 Unit 918 passed、8 skipped（排除 3 个只在 POSIX 有 `geteuid/chown` 的已知 Windows host-preparation 用例）；重分类两层、keyset/shard/checkpoint、幂等、统计、cancel/retry/recovery 与 Cleanup preflight 均有直接测试。 |
| 接口 / Contract | required | Contract 111/111、API 60/60；`python scripts/quality/generate_contracts.py --check` 与 compatibility 退出 0，Legacy HTTP Schema 已从 OpenAPI/generated client 删除。 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 18 测试已覆盖 Evidence、Job/Fence/事务、Migration 空库/非空拒绝及 upgrade→downgrade→upgrade；本机缺少可用 PostgreSQL/Docker，精确 current-head 直接执行证据由 PR Ready 后 required CI 提供，生产备份/迁移不在授权范围。 |
| 用户 / Workflow Acceptance | required | Playwright Browser Mock 106/106；旧 Plan Vehicle/Global Relevance 测试资产已移除，并由测试暴露后删除 Strategy Store 无 UI 消费者仍后台读取车型目录的残留。 |
| 跨组件 Golden Path | required | Real Full-stack 影响分类覆盖 Brand/Vehicle Filter→Content→Voice Plaza/Export 当前链；首轮执行 12/14 通过，并发现两个 Excel 用例仍调用已删除的 `/api/v1/relevance-config`，测试准备已按当前“全部已启用品牌快照”链修复；精确 current-head 重跑是合并门禁。重分类/Schema 的 PostgreSQL 直接链首轮 CI 已通过。 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub/LLM Operation 或真实第三方字段，且用户明确禁止付费 Probe；Fixture/Contract 回归足够。 |
| Build / Package / Runtime | required | Ruff check/format、Mypy 325 files、前端 ESLint、TS7/Vue typecheck、Vitest 24 files/139 tests、Vite build 均退出 0；正式 CI 仍作为 Ready 后合并门禁。 |
| Docs / Governance / Other | required | docs/check、docs facts、architecture/table ownership/Secret、Contract drift/compatibility 与 `git diff --check` 退出 0；Deep Review 当前无已知 P0/P1/P2 Finding，后续仍需 PR/main CI、原生归档与 Issue Closure。 |

# 任务与验证计划

1. 恢复 Schema/Migration、Evidence/Resolver、Job/Worker、Legacy consumer、generated client、测试/CI/Operations 的当前事实，固定最终设计和 Cleanup 数据门禁。
2. 先建立 Reclassification 与 Cleanup preflight 的失败测试，再实现最小生产能力和 PostgreSQL 集成。
3. 生成 Cleanup Migration，删除旧 Contract/Repository/UI，重新生成 OpenAPI/client，并完成 downgrade/备份恢复证据。
4. 执行 targeted → module → Contract/Migration/PostgreSQL → Browser/Full-stack → CI 等价验证；修复 Finding 后重验。
5. 同步 Product/Blueprint/Appendix/Operations/README，执行 Stage 1—7 Completion Audit，让 Roadmap 04 退出 live roadmap。
6. Change 进入 `ready_for_review` 后完成 Deep Review、current-head CI、guarded merge、main fresh CI、原生归档、Closure Audit 与分支清理。

# 兼容、迁移、部署与回滚

- 公共 Contract 会删除只服务 Legacy 配置的接口/类型；当前生产消费者必须先由调用链、生成物和 Browser/Full-stack 证据证明已退出。
- 新 Reclassification Job 使用新 job type/payload version；依据 2026-09-10 Owner 明确确认的无历史导入事实，不保留旧 Job Payload/执行器兼容分支，Migration 对任何非空 Legacy 表 fail closed。
- Cleanup Migration 只在数据库门禁满足时执行；生产仍须单独授权、目标环境备份、运行前对账与部署窗口。
- `vehicle_models.brand_id` 当前默认不收紧；未来真实数据满足时必须作为新的有证据 Schema 决策，不能由本次 Fixture 代替。
- downgrade/回滚必须恢复被 Drop 的 Legacy 表结构；由于 Owner 已确认不存在历史业务数据，空表恢复是本次批准边界，但 Upgrade 必须拒绝非空 Legacy 表，不能静默丢数。应用回滚与数据库 downgrade 的先后顺序将在 Operations 中明确。

# Completion Audit

- [x] upstream_re_read：重新读取 #437 与 Owner 补充决定、`origin/main` Roadmap 04 Stage 1—7/退出条件、当前 Roadmap 03/05 关系、Blueprint 02/03/04/07、Operations 03、Pydantic/OpenAPI、SQLAlchemy/Alembic、Worker Registry 和当前 `origin/main` `94b3ab6f`；确认生产部署/回填/Migration 未获授权。
- [x] change_coverage：逐条比较 AC1—AC8/R1—R8 与 Job/Repository/Worker、Migration/Schema、Legacy consumer 删除、生成物、测试、长期文档和交付顺序；R1—R7 已满足，R8 只保留 Ready 后强制生命周期动作。
- [x] reverse_audit：沿 `content_reclassification_runs` writer→Migration→Repository/Worker、Existing Evidence+Current Content→Resolver→Evidence→Voice Plaza/Export、Excel/TikHub 新 Snapshot→Content、Plan/Import Contract→generated client→Vue 反查；生产源与 OpenAPI 对三张 Legacy 表、旧 v1 Job/Run 和 `/relevance-config` 均无命中，声音广场结果查询的 `vehicle_model_ids` 属于明确保留边界。
- [x] two_stage_review：Review Target 为 `94b3ab6fa0d7007cd49e86f263d2ca454f3c79ff...fceed7be620ad62616a782b4fb72706b2fe7bc37`。A1 从 #437/Owner 决定/Roadmap 独立重建完成定义；A2 按 Job/Schema/Migration/Contract/Frontend/Docs/Tests 审查。Review 发现并修复 Vehicles PostgreSQL suite 未进入 CI、Cleanup 漏查旧 Batch Snapshot、旧文档/测试残留、Strategy Store 在 UI 移除后仍后台读取车型目录，以及 Real Full-stack Excel Fixture 仍调用已删除的全局相关性接口；当前无已知 P0/P1/P2 Finding。
- [x] unresolved_cleared：所有 `not_satisfied` 已清零；External Provider Probe 因不改外部 Operation 且禁止付费调用正式不适用；R8 的 CI/合并/main/归档/Closure/cleanup 是必须发生在 Ready 后的后置门禁，不冒充已完成。
