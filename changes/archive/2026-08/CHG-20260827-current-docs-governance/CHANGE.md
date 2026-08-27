---
schema: rvc-change/v1
id: CHG-20260827-current-docs-governance
title: 按当前机器事实治理现行文档
level: L2
status: done
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

以当时 `main` 的代码、Pydantic Contract、Alembic Migration、generated client、测试、锁文件和已完成 Change 为机器事实，对现行文档做受影响域内的 `full` 治理，修复已经过期、互相矛盾或把历史施工状态写成当前状态的内容。

本 Change 只治理当时仍承担事实说明、开发导航、Roadmap 或实施方案职责的现行文档。`changes/archive/**` 作为历史证据不因当前实现变化而改写。

# 成功标准

- [x] 现行文档不再把 Stage 12 软件开发写成“当前下一正式单元”或“当前第一优先级开发”；明确区分“软件实现已完成”“公司服务器 500 万/等效比例容量门禁待完成”“生产 4000 万执行待独立授权”。
- [x] Worker Job Registry、Analysis Planner、Data Import Campaign 等当前能力以真实代码中的版本化 Job Type 和调用链为准，不继续复制旧 4-Job 清单。
- [x] Stage 12 实施方案从施工期口径收敛为“已实现的软件基线 + 尚未完成的生产门禁/操作要求”，不把已通过 Completion Audit/CI 的能力继续写成待实现。
- [x] 统一“导入数据”入口、本地/服务器两类来源、`standard_observation / historical_fill_only` 两种独立策略、Artifact/Campaign/Chunk/逐行账本、手动 Analysis Run 的当前说明与代码一致。
- [x] Production Roadmap 继续保留尚未实现的认证授权、Coordinated Backup/Restore、SBOM/签名/provenance、Deploy/Rollback、完整 Production Acceptance 等批准目标，并明确它们是未来能力。
- [x] 当前路由、模块边界、部署拓扑、持久化边界、兼容入口与实际实现一致；未发现证据的能力不写成已实现。
- [x] 不修改业务代码、Contract、Schema/Migration、generated client、依赖、Prompt、Workflow 或既有历史归档 Change。
- [x] 完成受影响文档域的反向审计、两阶段 Review 和仓库适用文档/治理门禁。

# 实际治理范围

本 Change 实际修改：

```text
AGENTS.md
README.md
docs/01_代码结构与修改导航.md
docs/03_API接口说明.md
docs/blueprint/README.md
docs/blueprint/04_后端任务API与前端.md
docs/blueprint/07_技术决策与实施门禁.md
docs/roadmap/01_内网V1上线实施计划.md
docs/roadmap/02_生产上线实施路线.md
docs/roadmap/03_4000万历史数据迁移实施方案.md
backend/src/aima_ugc/modules/ingestion/README.md
backend/src/aima_ugc/modules/analysis/README.md
frontend/README.md
```

审计后确认已经与当时实现一致，因此没有制造无关差异：

```text
docs/blueprint/02_采集系统与数据标准化.md
docs/blueprint/03_数据库与文件存储.md
docs/appendix/08_数据入口与统一入库实现.md
docs/appendix/11_生产部署与离线Release方案.md
docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md
docs/AGENTS.md
```

# 非目标

- 不新增、删除或改变任何业务能力。
- 不修改 HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Job Payload、Prompt、依赖或 Runtime 配置。
- 不提前实现完整 Production Backlog。
- 不执行公司服务器 500 万/等效比例容量演练，也不执行生产 4000 万迁移。
- 不机械重写所有 Markdown，不做无关润色、编号重排或格式化。
- 不改写既有 `changes/archive/**` 的历史过程、当时状态或验收证据。

# 治理后固定的当前事实

## Worker Registry

当时 `backend/src/aima_ugc/bootstrap/worker.py` 的真实正式 Job：

```text
collection.run.v1
ingestion.import-excel.v1
ingestion.historical-discover.v1
ingestion.historical-snapshot.v1
ingestion.historical-import-chunk.v1
analysis.content-run-plan.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

其中三个 `ingestion.historical-*` 是统一 Data Import Campaign 兼容保留的物理 Job type；新版 Analysis Run Planner 的真实名称是 `analysis.content-run-plan.v1`，不是早期方案里的 `analysis.plan-content-run.v1`。

## 统一 Data Import

当前页面主链统一为：

```text
local_upload / server_path
→ Source Artifact / SHA-256
→ Data Import Campaign
→ 预检 / 有界 Chunk / 持久 Job
→ Reader / Mapper / Canonical / Relevance
→ standard_observation 或 historical_fill_only
→ Content Owner
→ 逐行终态账本 / 冲突账本
```

旧 `/api/v1/import-batches` 与 `/api/v1/historical-import-*` 继续作为兼容 Contract 存在，不作为当前页面第二套主工作流。

## Analysis Run

新版页面链：

```text
POST /api/v1/analysis/content-runs/preview
→ POST /api/v1/analysis/content-runs
→ analysis.content-run-plan.v1
→ 冻结 content_id + content_version
→ 有界 analysis.content-label.v1 Shard
→ 每轮结果保留
```

当前页面只开放显式选择 1—1000 条；兼容 Analysis Request 仍保留合法兼容语义。

## Stage 12 状态

```text
Stage 12 软件设计 / Schema / Contract / API / Worker / 页面 / 测试
→ 已完成、合入 main、软件 Change 已归档

公司服务器 500 万或业务 Owner 批准的等效比例容量演练
→ 待执行

生产 4000 万实际 Campaign + 全量对账
→ 待独立生产写授权
```

禁止再把“继续实现 Stage 12 软件”作为默认下一开发导航。

## Release / Production 状态

当时 `.github/workflows/release.yml` 已真实具备：

```text
Linux/AMD64 Backend/Frontend
+ 固定 postgres:18.4
→ images.tar
→ release-manifest.json / migration-manifest.json
→ SHA256SUMS / DEPLOY.md
→ 删除候选镜像后 docker load
→ canonical Compose --no-build --pull never 回放
→ 正式 dispatch 的 GHCR digest / Git Tag / GitHub Release 基础
```

因此不能再把离线 Bundle/Manifest/回放基础整体写成未实现。

完整 Production 仍为 No-Go，尚缺：

```text
认证授权 / HTTPS
SBOM / 独立签名 / 完整 provenance
PostgreSQL + Artifact Coordinated Backup/Restore
生产服务器完整 preflight / backup / migrate / start / smoke / rollback
完整生产容量 / 安全 / 恢复验收
```

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 以代码等机器事实为准治理当前文档，包括实施方案 | user:current-request | satisfied | 已治理根 README、AGENTS、代码/API 导航、Blueprint、Roadmap 01/02/03、Ingestion/Analysis/Frontend README |
| R2 | 已实现能力由机器事实证明，不用旧聊天/旧 Stage 代替 | AGENTS.md | satisfied | 反查 `bootstrap/worker.py`、`historical_jobs.py`、`content_analysis_job.py`、`bootstrap/api.py`、`historical_tables.py`、`routes.ts`、Release Workflow、版本文件和相关现行测试/运行手册 |
| R3 | Stage 12 当前状态与真实归档 Change、Job Registry 和测试证据一致 | `backend/src/aima_ugc/bootstrap/worker.py` | satisfied | 当前 Registry 8 类 Job；Planner 名已校正；Stage 12 软件 Change 已 done/归档，生产容量/全量仍未完成 |
| R4 | 保留已批准但未实现的 Production 目标，并明确未来状态 | `docs/roadmap/02_生产上线实施路线.md` | satisfied | 保留 Auth/HTTPS、Backup/Restore、SBOM/签名/provenance、Deploy/Rollback、Stage 11E；同时承认当前 Release 基础已经实现 |
| R5 | 历史 Change 不作为当前文档重写对象 | Docs Skill | satisfied | 既有 `changes/archive/**` 未改写，只作为历史证据读取 |
| R6 | 当前 API、前端入口和兼容边界必须与真实 Assembly/Router 一致 | `backend/src/aima_ugc/bootstrap/api.py` | satisfied | API 说明、Blueprint 04、Frontend README 已按 `/data-import-*`、`/analysis/content-runs*`、人工 relevance review、兼容 Route 与真实前端路由同步 |
| R7 | 当前 Ingestion Owner/父事实覆盖 Stage 12 已落库能力 | `modules/ingestion/historical_tables.py` | satisfied | Blueprint 07 与 Ingestion README 已同步 Campaign/Item、row ledger/conflict、两类策略与 Owner 边界 |

# Validation Matrix

| Layer | Required | Evidence |
| --- | --- | --- |
| Behavior / Unit / Component | not_applicable | 纯文档治理，不改变可执行行为，不伪造 TDD |
| Contract | not_applicable | 未修改 Pydantic/OpenAPI/generated client；API 文档路径直接反查 FastAPI Assembly |
| Integration / Persistence / Runtime | not_applicable | 未修改数据库/Runtime；表名、Owner、Job/Release 状态由当前实现反查 |
| User / Browser | not_applicable | 未改变产品交互；只同步 Router/Feature 已存在事实 |
| Full-stack / Provider | not_applicable | 未改变接线或 Provider 行为，无需付费 Probe |
| Build / Package / Runtime | not_applicable | 未修改构建、依赖、镜像或部署配置 |
| Docs / Governance | required | `ready_for_review` 候选 `631f9d995ce9d0a937f38d634778f7436e2edf7a`：CI `33070290791` success；Runtime Acceptance `33070290713` success；Change Completion Gate `33070290709` success |

# 两阶段 Review

## A1 Requirement Completeness Review

结论：PASS。

- 用户要求的“按代码实际治理当前文档，包括实施方案”已覆盖根入口、Agent 入口、代码/API 导航、核心 Blueprint、Roadmap/Stage 12 方案和主要模块/前端 README；
- 已实现软件事实与批准但未实现的 Production 目标明确分层；
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

测试专家结论：本 Change 是纯文档治理，不新增或改变可执行行为；新 Unit/Integration/Browser 测试不适用。适用证据是当前实现反查、文档/Secret Gate、Change Completion Gate 和现有 Runtime 保护门禁。

# Completion Audit

- [x] upstream_re_read：重新读取用户要求、AGENTS、Coding/Docs/Review Skill、Blueprint、Roadmap、Stage 12 归档 Change 和当前机器事实，独立重建“当前实现 / 未来批准目标 / 历史证据”三类完成定义。
- [x] change_coverage：R1—R7 全部 `satisfied`，没有 `not_satisfied`。
- [x] reverse_audit：从治理后的 README/Blueprint/Roadmap/API/模块文档反向定位实际 Worker/API/Historical/Analysis/Router/Release/Table 事实；未发现会改变当前开发判断的 BLOCKER/HIGH/MEDIUM 漂移。
- [x] unresolved_cleared：旧 4-Job 清单、错误 Planner 名、Stage 12“当前下一开发单元”、旧单文件 Import 作为页面主链、离线 Release 基础整体写成未实现等已修正。

# 交付证据

治理前基线：

```text
262cfa35c56bd4d293f61419ee712e423f37c5ac
```

语义 Review 完成候选：

```text
631f9d995ce9d0a937f38d634778f7436e2edf7a
```

该候选的永久门禁：

```text
CI                     33070290791  success
Runtime Acceptance     33070290713  success
Change Completion Gate 33070290709  success
```

本 Change 没有执行公司服务器 500 万/等效比例容量演练，也没有执行生产 4000 万写入。归档后仍需以归档提交后的最终 `main` HEAD 重新确认仓库门禁状态，不能用上述候选结果替代最终归档 HEAD 的验证。
