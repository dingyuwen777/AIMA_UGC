---
schema: rvc-change/v1
id: CHG-20260827-current-docs-governance
title: 按当前机器事实治理现行文档
level: L2
status: ready_for_review
owner: aima
branch: main
created: 2026-08-27
updated: 2026-08-27
completion_gate: required
depends_on: []
affected_areas:
  - documentation
  - architecture
  - roadmap
  - ingestion
  - analysis
  - frontend
  - operations
affected_paths:
  - AGENTS.md
  - README.md
  - docs/01_代码结构与修改导航.md
  - docs/03_API接口说明.md
  - docs/blueprint/README.md
  - docs/blueprint/04_后端任务API与前端.md
  - docs/blueprint/07_技术决策与实施门禁.md
  - docs/roadmap/01_内网V1上线实施计划.md
  - docs/roadmap/02_生产上线实施路线.md
  - docs/roadmap/03_4000万历史数据迁移实施方案.md
  - backend/src/aima_ugc/modules/ingestion/README.md
  - backend/src/aima_ugc/modules/analysis/README.md
  - frontend/README.md
contracts: []
data_changes: []
---

# 目标

以当前 `main` 的代码、Pydantic Contract、Alembic Migration、generated client、测试、锁文件和已完成 Change 为机器事实，对现行文档做一次受影响域内的 `full` 治理，修复已经过期、互相矛盾或把历史施工状态写成当前状态的内容。

本 Change 只治理当前仍承担事实说明、开发导航、Roadmap 或实施方案职责的文档。`changes/archive/**` 是历史证据，不因当前实现变化而改写。

# 成功标准

- [x] 现行文档不再把 Stage 12 软件开发写成“当前下一正式单元”或“当前第一优先级开发”；明确区分“软件实现已完成”“公司服务器 500 万/等效比例容量门禁待完成”“生产 4000 万执行待独立授权”。
- [x] Worker Job Registry、Analysis Planner、Historical Campaign 等当前能力以真实代码中的版本化 Job Type 和调用链为准，不继续复制旧 4-Job 清单。
- [x] Stage 12 实施方案从“施工中”口径收敛为“已实现的软件基线 + 尚未完成的生产门禁/操作手册”，不把已通过 Completion Audit/CI 的能力继续写成待实现。
- [x] 统一“导入数据”入口、本地/服务器两类来源、`standard_observation / historical_fill_only` 两种独立策略、Artifact/Campaign/Chunk/逐行账本、手动 Analysis Run 的当前说明与代码一致。
- [x] Production Roadmap 继续保留尚未实现的认证授权、Coordinated Backup/Restore、SBOM/签名/provenance、Deploy/Rollback、完整 Production Acceptance 等批准目标，并明确它们是未来能力，不因代码尚未实现而删除。
- [x] 当前路由、模块边界、部署拓扑、持久化边界、兼容入口与实际实现一致；未发现证据的能力不写成已实现。
- [x] 不修改业务代码、Contract、Schema/Migration、generated client、依赖、Prompt、Workflow 或历史归档 Change。
- [x] 完成受影响文档域的反向审计、两阶段 Review 和仓库适用文档/治理门禁，所有“通过”结论具有本轮新鲜证据。

# 范围

实际修改范围仅包括 `affected_paths` 中列出的当前文档。审计过但确认已经与当前实现一致，因此没有制造无关差异的候选文档包括：

```text
docs/blueprint/02_采集系统与数据标准化.md
docs/blueprint/03_数据库与文件存储.md
docs/appendix/08_数据入口与统一入库实现.md
docs/appendix/11_生产部署与离线Release方案.md
docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md
docs/AGENTS.md
```

`changes/archive/**` 只作为历史原因/验收证据读取，没有被改写。

# 非目标

- 不新增、删除或改变任何业务能力。
- 不修改 HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Job Payload、Prompt、依赖或 Runtime 配置。
- 不把完整 Production Backlog 提前实现。
- 不执行公司服务器 500 万/等效比例容量演练，也不执行生产 4000 万迁移。
- 不机械扫描/重写所有 Markdown，不做无关润色、编号重排或格式化。
- 不改写 `changes/archive/**` 的历史过程、当时状态或验收证据。

# 必须保持不变

- 模块化单体；API / Worker / Scheduler / Migration 分进程。
- PostgreSQL 18 是唯一业务事实库；长任务继续使用 PostgreSQL Durable Job Runtime。
- Provider/File → Raw/Input Artifact → Mapper → Canonical → Relevance → Ingestion → Owner Repository → PostgreSQL 的主链。
- Content Current + Version + Metric、表 Owner、Artifact、Pydantic/OpenAPI/generated client 等长期边界。
- Stage 12 历史补空策略只补空、不覆盖非空、冲突留痕；导入与 AI 解耦。
- 公司内网 V1 已完成与完整 Production Go-Live 仍为 No-Go 是两个不同里程碑。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 以代码等机器事实为准治理当前文档，包括实施方案 | user:current-request | satisfied | 已治理根 README、AGENTS、代码/API 导航、Blueprint、Roadmap 01/02/03、Ingestion/Analysis/Frontend README；Stage 12 实施方案已从施工口径收敛为当前软件基线 + 生产门禁 |
| R2 | 已实现能力由机器事实证明，不用旧聊天/旧 Stage 代替 | AGENTS.md | satisfied | 逐项反查 `bootstrap/worker.py`、`historical_jobs.py`、`content_analysis_job.py`、`bootstrap/api.py`、`historical_tables.py`、`routes.ts`、`.github/workflows/release.yml`、`.python-version` 和相关现行测试/运行手册 |
| R3 | Stage 12 当前状态与真实归档 Change、Job Registry 和测试证据一致 | backend/src/aima_ugc/bootstrap/worker.py | satisfied | 当前 Registry 明确为 8 类 Job；Planner 名修正为 `analysis.content-run-plan.v1`；`CHG-20260826-stage12-historical-migration` 已 `done`/归档；当前文档明确软件完成但服务器容量门禁/生产全量未完成 |
| R4 | 保留已批准但未实现的 Production 目标，并明确未来状态 | docs/roadmap/02_生产上线实施路线.md | satisfied | Roadmap/Blueprint/AGENTS 继续保留认证授权/HTTPS、Coordinated Backup/Restore、SBOM/独立签名/完整 provenance、生产 Deploy/Rollback、Stage 11E 验收；同时按 `.github/workflows/release.yml` 承认现有 `images.tar`/Manifest/no-build-no-pull/GHCR-Tag-Release 基础已实现 |
| R5 | 历史 Change 不作为当前文档重写对象 | .agents/skills/docs/references/01_事实源与同步判断.md | satisfied | `changes/archive/**` 未修改；只读取 Stage 12 归档 Change 等历史证据 |
| R6 | 当前 API、前端入口和兼容边界必须与真实 Assembly/Router 一致 | backend/src/aima_ugc/bootstrap/api.py | satisfied | `docs/03_API接口说明.md`、Blueprint 04、Frontend README 已按当前 `/data-import-*`、`/analysis/content-runs*`、人工 relevance review、旧 `/import-batches`/`/historical-import-*` 兼容 Route 和 4 个真实前端路由同步 |
| R7 | 当前 Ingestion Owner/父事实必须覆盖 Stage 12 已落库能力 | backend/src/aima_ugc/modules/ingestion/historical_tables.py | satisfied | Blueprint 07 与 Ingestion README 已加入 Campaign/Item、row ledger/conflict、两类策略和统一 Campaign 事实；未把 Ingestion 写成第二 Content Owner |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 本 Change 不改变业务代码或运行行为；不伪造 Red/Green |
| 接口 / Contract | not_applicable | 没有修改 Pydantic/OpenAPI/generated client；文档中的 API 路径已直接反查当前 FastAPI Assembly |
| 集成 / Persistence / Runtime Dependency | not_applicable | 没有修改数据库/Runtime；表名、Owner、Job/Release 状态通过现行代码/Migration/Workflow 反查 |
| 用户 / Workflow Acceptance | not_applicable | 不改变产品交互行为；页面能力只同步当前 Router/Feature 已存在事实 |
| 跨组件 Golden Path | not_applicable | 不改变接线；审计时读取现有 Full-stack 入口和 Stage 12 运行手册作为当前事实证据 |
| External Dependency / Provider Probe | not_applicable | 不修改 Provider 行为，也不需要真实付费 Probe |
| Build / Package / Runtime | not_applicable | 不修改构建、依赖、镜像或部署配置；Runtime Acceptance 仍作为仓库现有保护门禁运行 |
| Docs / Governance / Other | required | Review Target `262cfa35c56bd4d293f61419ee712e423f37c5ac..bbd6af4166f3ec4da6b356b8a98a051c332e3b0f` 的 CI `33069729176` 成功、Runtime Acceptance `33069729193` 成功；CI docs fast path 执行 `scan_secrets.py` + `check_docs.py`。最终 ready HEAD 还必须由 Change Completion Gate 重新机器验证后才归档 |

# 分步任务

- [x] 对照真实 Worker Registry、API/Contract、Migration、前端 Router/Feature、模块目录、Compose/Release 机器事实建立漂移清单。
- [x] 修正根 README、代码导航、API 说明、Blueprint 中的当前实现清单和导航。
- [x] 修正 Roadmap 01/02/03 中 Stage 12 的当前状态、执行顺序和剩余生产门禁。
- [x] 修正 Ingestion/Analysis/Frontend README；审计确认正确的 Appendix/Blueprint 候选文件不做无关修改。
- [x] 执行 Docs targeted re-review：从修改后的文档反查机器事实，检查当前/未来/历史三类状态是否混淆。
- [x] 执行需求符合性与文档质量两阶段 Review。
- [x] 更新 Requirement Traceability、Validation Matrix、Completion Audit 和验证证据。
- [x] 当前 Change 进入 `ready_for_review`；归档动作只在最终 ready HEAD 的机器门禁成功后执行。

# 两阶段 Review

## A1 Requirement Completeness Review

结论：PASS。

- 用户要求的“按代码实际治理当前文档，包括实施方案”已覆盖根入口、Agent 入口、代码/API 导航、核心 Blueprint、Roadmap/Stage 12 方案和主要模块/前端 README；
- 已实现软件事实与批准但未实现的 Production 目标被明确分层，没有因为代码里尚不存在就删除未来门禁；
- Stage 12 历史施工 Change 没有被改写；
- 审计确认已经正确的 Blueprint 02/03、Appendix 08/11/14 等没有为凑范围制造差异。

## A2 文档质量 / 事实一致性 Review

结论：PASS；未发现未解决的 BLOCKER / HIGH / MEDIUM Finding。

重点反查：

```text
Worker Registry / Job type
Data Import / Analysis API 路径
Stage 12 Campaign/Item/Row/Conflict 表与 Owner
Frontend Router / Feature 入口
Analysis Run Planner/Shard 语义
Release Workflow 已实现与未实现边界
Internal V1 / Stage 12 / Production Go-Live 状态
Python 版本事实
```

测试专家结论：本 Change 是纯文档治理，不新增或改变可执行行为；Unit/Integration/Browser 新测试不适用。适用的证据是当前实现反查、文档/Secret Gate、Completion Gate 和现有 Runtime 保护门禁，不能把旧业务测试结果冒充本轮文档完成证据。

# Completion Audit

- [x] upstream_re_read：重新读取本轮用户要求、当前 `AGENTS.md`、Coding/Docs/Review Skill、Blueprint README/02/03/04/07、Roadmap 01/02/03、Stage 12 归档 Change 和当前机器事实，独立重建“当前实现 / 未来批准目标 / 历史证据”三类完成定义。
- [x] change_coverage：逐项复核 R1—R7；用户要求的当前文档治理、实施方案同步、Stage 12 状态、API/Job/Owner/Frontend/Release 事实均有对应现行文档；没有 `not_satisfied`。
- [x] reverse_audit：从修改后的 README/Blueprint/Roadmap/API/模块文档反向定位实际 `worker.py`、`api.py`、`historical_*`、Analysis Job、Router、Release Workflow 和表定义；未发现前端/后端/文档之间仍有会改变当前开发判断的 BLOCKER/HIGH/MEDIUM 漂移。
- [x] unresolved_cleared：旧 4-Job 清单、错误 Planner 名 `analysis.plan-content-run.v1`、Stage 12“当前下一开发单元”、旧单文件 Import 作为页面主链、离线 Release 基础整体写成未实现等已修正；没有未解决的 BLOCKER/HIGH/MEDIUM Finding。
