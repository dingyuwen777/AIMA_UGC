---
schema: coding-change/v1
id: CHG-20260925-095824-replay-revocation-impact
title: 校正采集运行全类型计数与数据导入撤销影响
level: L3
status: done
owner: yuwen.ding
branch: fix/603-replay-revocation-impact
created: 2026-09-25T09:58:24+08:00
updated: 2026-09-25
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - collection
  - frontend
  - jobs
  - database
affected_paths:
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_revocation.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_lifecycle.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_reversal_worker.py
  - backend/src/aima_ugc/bootstrap/import_revocation_worker.py
  - backend/src/aima_ugc/bootstrap/adaptive_shard_worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/replay_shards.py
  - backend/src/aima_ugc/adapters/persistence/postgres/reversal_shards.py
  - backend/src/aima_ugc/adapters/persistence/postgres/import_lineage.py
  - backend/src/aima_ugc/modules/ingestion/replay_shards.py
  - backend/src/aima_ugc/modules/ingestion/reversal_shards.py
  - backend/src/aima_ugc/modules/ingestion/replay_shard_tables.py
  - backend/src/aima_ugc/modules/ingestion/reversal_shard_tables.py
  - backend/src/aima_ugc/platform/capacity.py
  - migrations/versions/20260925_0064_reversal_shards.py
  - migrations/versions/20260925_0065_replay_run_shards.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/collection/runtime_query.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CanonicalReplayDetailDrawer.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRunDetailDrawer.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeKpiCards.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportBatchDetailDrawer.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeTable.vue
  - frontend/src/features/task-center/store.ts
  - tests/integration/ingestion/test_import_campaign_revocation_postgres.py
  - tests/integration/ingestion/test_canonical_replay_worker.py
  - tests/integration/ingestion/test_import_lineage_replay.py
  - tests/unit/ingestion/test_replay_shards.py
  - tests/unit/ingestion/test_reversal_shards.py
  - tests/unit/platform/test_capacity.py
  - frontend/tests/collection-runtime-design.spec.ts
  - frontend/tests/collection-runtime-release2.spec.ts
  - frontend/tests/task-center.spec.ts
  - frontend/e2e/collection-runtime.spec.ts
  - frontend/e2e-fullstack/stage12-historical-analysis.spec.ts
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/blueprint/01_总体架构与技术选型.md
  - docs/blueprint/03_数据库与文件存储.md
  - docs/blueprint/04_后端任务API与前端.md
  - docs/product/02_当前产品能力与用户流程.md
  - docs/guides/07_采集运行中心Figma开发基线.md
contracts:
  - CollectionRuntimeItemResponse.revocation_recomputed_content_count
  - ingestion.canonical-replay-shard.v1
  - ingestion.reversal-shard.v1
data_changes:
  - ingestion_reversal_shards 持久撤回工作单元
  - canonical_replay_run_shards 持久重筛工作单元
---

# 变更摘要

## 2026-09-25 扩展：统一分片调度与自适应并行

用户进一步要求在本 PR 中实现一套可维护的通用持久 Job 调度与资源/吞吐反馈机制，分别优化历史导入、全历史重筛入库、普通导入撤销、重筛撤回，并在 CI 通过后合并 main。既有 R1–R7 的完成证据只覆盖原范围，不能用于宣称这项扩展已完成；本 Change 在新实现和验收前恢复为 `in_progress`。

当前事实：历史 Campaign 已按 Canonical Chunk 建 Item/Job；全历史 Replay 每 100 个 Artifact 建一个 Run/Job，本次 34 个 Artifact 只有一个 Run。Replay 去重身份以 `run_id` 为键，直接缩小 Artifact 分组会改变跨组重复行的归属和统计。两种撤回各只有一个父 Job。隔离 PostgreSQL 的同一次普通导入撤销原型，3,000 Content 单/双进程为 2.430/2.900 秒，10,000 为 8.571/6.401 秒（四进程 7.093 秒），20,000 为 17.373/11.727 秒（四进程 11.582 秒）；原型沿用正式来源重组和 Job 认领，但尚未实现生产父任务完成屏障。重筛撤回 20,000 Content 的真实 Job 原型，单/双/四/八进程为 24.688/17.094/18.256/18.653 秒。不同并行度不是单调收益，也不能把本机数字外推到服务器。

扩展完成条件：

- R8：四类任务继续只使用通用 `jobs` Runtime、Worker 进程池和同一资源检测。Replay Run、普通导入撤销与重筛撤回共用持久分片调度及吞吐反馈；历史导入沿既有 Campaign/Chunk 背压和批量反馈，避免改写冻结的恢复粒度与锁顺序。并行度从单路逐级探索，受有效 CPU、内存、数据库连接余量和待处理分片数限制，稳定后复探。
- R9：历史导入保留已冻结 Chunk 和已验证的 Campaign 锁顺序；Replay 在现有 Run 的去重边界内按稳定来源内容身份分片，同一身份的全部输入顺序不变，预检只做必要重复工作；普通导入撤销和重筛撤回按 Content 分片，不按来源行 Chunk 分片。小任务单 Job 回退。
- R10：每个子 Job 有幂等身份、独立 Fence、持久断点；父任务汇总只在全部子工作结清后完成。覆盖取消/撤回交错、Worker 崩溃接管、重试、并发后续写入、共享 Content、人工锁、空任务和多来源重复，并比较入口至入库/撤回终态的墙钟时间。
- R11：刷新正式文档、Change Completion Audit 与 Review，并在当前 PR Head 的 CI 通过后合并；合并后核查 main、归档、关闭 Issue 和清理本地分支。未有正式多 Job 实现和对应验证之前，不把隔离原型当作交付结果。CI 与合并是 Ready 之后的独立交付门禁，不作为 Change 自身的循环前置条件。

本机 2026-09-25 的第二次全历史重筛新增入库为 0，但三个子任务分别收敛 16,469、22,780、1,055 条既有内容。采集运行与任务中心只显示“入库 0”，导致用户误以为没有处理。第四次本地导入 66,139 行全部过滤，但同 Campaign 后续重筛形成 6,757 条来源贡献、涉及 5,747 个 Content；撤销预览按原导入逐行账本显示影响 0，实际 Worker 重组 5,747 个 Content。

目标是让预览与真实贡献账本、执行进度一致，逐类核对采集运行的列表、详情及总览数字，并根据日志拆分慢阶段后验证可行优化。保持不可变历史审计事实、既有公共 API 字段语义、依赖和用户现有数据不变；新增兼容的可选只读字段与两张持久分片表。生产部署与改写既有审计不在范围内。

# 背景、现状与问题

六条现场记录由四条 Campaign 和两条 Replay 组成。导入规则使四条 Campaign 的原始行全部过滤，但冻结的 Canonical 后来经 Replay 形成来源贡献；旧预览只看原导入行与在线补采，因此把应重组的 5,747 个 Content 预估为零。第二次 Replay 新建 Content 为零，列表也只显示零，掩盖了大量已有记录处理。保持现状会继续产生错误撤销确认和“没有处理数据”的误解。

# 事实与证据

- `historical_revocation._affected_content_ids` 只合并原导入行账本与在线补采账本，漏掉重筛沿原 Campaign 来源写入的 `content_source_contributions`。
- 撤销 Worker 的 `content_lifecycle._campaign_contributions_query` 已按 Campaign 关联读取上述贡献，故实际撤销数量大于预览。
- 第二次重筛的 `rows_ingested` 确为 0，`existing_convergence` 合计 40,304 次输入记录处理、`duplicates_removed` 为 6,875；撤回账本涉及 39,189 个不同 Content。不能把这两个计数相加或互换。
- 当前运行中心 API 返回六条记录：四条 Campaign、两条 Replay。四条 Campaign 处理行数分别为 202,168、168,792、66,139、66,139，均全部过滤；后两条撤销的实际重组量分别为 5,747 个不同 Content。其余三种记录类型使用隔离数据库/前端测试覆盖。
- Collection 的 `content_count`/`comment_count` 是每个 Scope 内去重、再按 Scope 累计的目标数，包含已有内容；`filtered_count` 是品牌车型过滤。Excel 的 `rows_ingested` 是本次处理行数，Campaign 同名投影仅累计新建/补空/更新。顶部 `contents_ingested_today` 是各类任务原有入库口径的相加，并非去重 Content 总数。
- 最大子任务的 `fallback_ms` 为 95,544 毫秒。3000 行隔离重筛把此阶段细分后，Content 更新约 3,938 毫秒，占第二轮重复重筛的主要数据库时间；集合 UPDATE 将该阶段缩短至约 1,870 毫秒。这个对照是单次本机实验，不声称所有服务器均有相同比例。

证据来源：本机 `.runtime/compose/runtime/logs/worker-*.log` 和 `api.log`、当前六条运行记录 API、只读 PostgreSQL 贡献/撤销请求查询、`content_lifecycle.py` 与 `historical_revocation.py` 的同源归属查询、隔离 PostgreSQL 集成测试及基准日志。

# 目标、成功标准与非目标

- 成功：撤销预览与贡献账本及 Worker 实际处理对象对齐；五类列表和详情使用与真实计数单位一致的标签；旧错误预估明确显示差异；第二次重筛的已有处理量可见；单机隔离实验在结果不变的条件下减少重复重筛耗时；全链路说明当前 Job 并行边界，以对照实验决定是否拆分单次撤回。
- 范围：导入撤销预览、采集运行只读投影、前端统计文案与组件、重筛聚合计时、既有 Content 批量更新、测试和相关正式文档。
- 非目标：改写已提交撤销审计、改变重筛/导入的持久语义、重新设计全库唯一 Content KPI 或生产部署。
- 保持：历史文件与来源账本、Job Fencing/Checkpoint、用户数据、既有 API 字段和失败语义、无外部 Provider 调用。

# 约束与意图决策

| 维度 | 决策与依据 |
| --- | --- |
| Contract | 仅新增可选只读字段，旧客户端与既有统计字段语义不变；生成 OpenAPI/Client 同步。 |
| 数据与迁移 | 撤销事实不可变，终态展示 Worker 已提交实绩；0064/0065 只新增持久分片表，不改写既有业务行。 |
| 性能与正确性 | 更新已锁定的不同 Content，按相同列集合分组并以 500 行集合 SQL 提交；不改变来源、版本与观测字段规则。 |
| 兼容与回滚 | API、Worker、Frontend 可按正常镜像回滚；历史预估留存，新增可选响应字段无需数据回填。 |

# 修改方案与决策依据

1. 从 Content Owner 的 Campaign 贡献查询复用归属条件，合并到撤销预览的受影响 Content 集合；用真实 Campaign→Replay→撤销路径验证。
2. 运行中心按五种类型分别呈现输入、过滤、重复、处理、撤销实绩；给 Campaign 增加只读实绩字段；用现场六条记录和组件测试对账。
3. 在已有低频 Replay 完成日志拆分 Content、证据与账本阶段；确认 Content 为慢段后采用有界集合 UPDATE；用隔离数据库回归和重复基准验证。
4. 对导入撤销和重筛撤回分别做隔离数据基准及分段取证；重筛撤回的常见 Content Delta、自动证据、人工锁、可见性归属和账本改用有界集合读写，复杂 Delta 保留精确路径。普通导入撤销的两个候选改动未改善总时长，故保留原集合写入和动态批次，仅增加读取/应用/批次耗时日志。
5. 沿本地上传/服务器目录、预检、Chunk、Replay 与撤回核对 Job 拆分；分别测单次大撤回及两个独立 Campaign 串行/并行。现有撤回批次持有父请求锁，同一 Content 的 Delta 必须原子回退；若数据库并行收益不足，不新增缺少可靠领取与完成屏障的子 Job。

## 备选方案与取舍

- 直接改写旧撤销影响审计会丢失“当时系统预估为何错误”的事实，故保留旧值并在终态展示实际重组量。
- 用统一的“入库条数”概括全部五种任务会混合输入记录次数、按 Scope 累计目标与不同 Content，故保留各来源原始语义并在界面标明计数单位。
- 提高全局批大小没有证据能解决重复重筛的 Content UPDATE 往返，且可能增加事务资源压力；选择局部 500 行集合更新并保持运行时资源约束。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 过滤行后经重筛产生贡献时，撤销预览与实际撤销数量及进度口径一致 | #603 / AC1 | satisfied | PostgreSQL 真实 Campaign→Replay→预览→撤销集成测试；现场只读账本与 Worker 5,747 对账 |
| R2 | 第二次重筛新增 0 时显示已有记录处理量，不误称无处理 | #603 / AC2 | satisfied | 运行列表、任务中心渲染测试；现场 0/40,304/6,875 对账 |
| R3 | 分析全链路日志和贡献归属，拆分关键慢阶段并以实验决定优化 | #603 / AC3 | satisfied | 新增聚合分段日志；隔离数据库 3,000 行两轮实验及 Content 更新回归 |
| R4 | 六条现场记录与五种类型的列表/详情/总览计数和标签对齐真实统计对象，旧预估漏算时可见实际量 | #603 / AC4 | satisfied | 六条现场 API/数据库只读对账；五类型列表测试、旧预估差异详情 SSR、汇总语义文案 |
| R5 | 回归、文档和 Review 保持数据正确性；PR CI 作为独立合并门禁 | #603 / AC5 | satisfied | PostgreSQL 95 测试、前端 233 测试、构建、lint、类型、Contract/架构/Owner/文档检查；CI 待 PR Head 提交后验证 |
| R6 | 普通导入撤销与重筛撤回的实际耗时和慢段都有实测依据；减少逐条 SQL 往返并维持版本、证据和断点正确性 | #603 / AC6 | satisfied | 隔离库同量重筛撤回由 52.023s 降至 3.012s（Worker），101 Content SQL 次数回归、95 个 PostgreSQL 回归通过；普通导入撤销 3,000 Content 基线约 2.5s，两个候选改动无稳定收益已撤回，仅保留分段日志 |
| R7 | 核对全链路 Job/Worker 并行边界，实验判断单次撤回拆分的收益、正确性前提和当前方案 | #603 / AC7 | satisfied | 本地/服务器入口与快照/Chunk/Replay Job 代码及现场日志；独立 Campaign 两 Job 串行 5.708s、并行 4.591s，单 Job 20,000 Content 重筛撤回 23.108s；同请求 10,000 Content 两轮顺序反转原型串行 10.565/10.307s、两分区 9.009/9.002s；原型未覆盖 Fence/恢复，故不进入生产；技术文档记录取舍 |
| R8 | 通用 Job Runtime、资源检测和三类大任务共用单路起步的持久分片吞吐反馈；历史 Chunk 保持既有恢复语义 | #603 / AC8 | satisfied | `AdaptiveShardCoordinator` 与 `AdaptiveJobWindowController`；容量单元测试证明单路起步、按实测逐级升降档、资源/连接上界及稳定后复探；78 个 ingestion 集成测试通过 |
| R9 | Replay 保留 Run 内去重顺序；两种撤回按 Content 分片；小任务沿原路径 | #603 / AC9 | satisfied | 隔离 PostgreSQL 覆盖跨 Artifact 去重及父计数、两种撤回持久分片及小任务路径；低命中 Replay 经正式 Worker 实测保留串行以避免重复读取 |
| R10 | 子 Job Fence/断点/完成屏障及故障恢复、取消、交错写入正确性和正式墙钟对照 | #603 / AC10 | satisfied | 两类撤回父 Job 失败重试、子 Job 业务提交后终态失败、Replay 分片去重与既有取消/并发写入回归通过；正式 Worker 对照见 V8、V12、V13，收益边界明确 |
| R11 | 文档、完成审计、Review 与本地交付检查 | #603 / AC11 | satisfied | 本 Change 完成上游与反向审计；静态/Contract/文档/Migration 检查及前后端回归通过；PR #604 的新 Head CI、合并和清理仍是后续交付门禁 |

# 计划改动

| 步骤 | 修改范围 | 可观察结果与验证 |
| --- | --- | --- |
| 来源对齐 | 撤销影响查询、贡献查询、PostgreSQL 集成测试 | 预览受影响数量等于实际处理的独立 Content 数，普通/补采场景不回退 |
| 口径修正 | 采集运行只读投影、列表/详情/总览、任务中心及其测试 | 六条现场记录和五种类型的数字能对账；区分任务处理次数、范围累计和不同 Content；旧撤销记录展示实际处理量 |
| 性能取证 | 重筛 Worker 聚合阶段日志、Content 批量更新、隔离数据库实验 | 找到慢阶段，实测同数据结果不变且第二轮重筛加快 |
| 撤回优化 | Content 生命周期撤回、重筛撤回 Worker、导入撤销 Worker 日志及集成/基准 | 减少逐条 SQL 往返；改前改后业务计数、版本、证据及耗时可对照 |
| 并行取舍 | Worker 进程池、Job 调度与撤回父请求锁；隔离库双任务对照 | 明确多 Worker 能处理哪些任务、单请求拆分的必要条件和可复核收益，不以进程数推算线性提速 |
| 完成检查 | 文档、测试、Review、CI | 需求与结果逐项对齐，不改写旧审计事实 |

# 验证矩阵

| 层 | 要求 | 证据 |
| --- | --- | --- |
| PostgreSQL / Worker | required | 扩展后的 ingestion 全量 78 passed；Content 清理独立测试库后单独 73 passed；父子失败重试、提交后子 Job 终态失败、Replay 去重及恢复均由隔离 PostgreSQL 覆盖 |
| 前端行为 | required | 全量 Vitest 234 passed、采集运行 Playwright 18 passed，lint 和生产构建通过；失败撤回的重试入口 SSR 覆盖 |
| 静态检查与生成一致性 | required | Ruff format/check、mypy、Contract 生成检查、架构/表 Owner、文档、Alembic check 通过；新 Head Linux CI 待提交后验证 |
| 当前日志与隔离性能实验 | required | 现场 6 记录与 Worker 日志对账；3,000 行重复重筛改动前 6.744s、改动后 4.620s/4.326s（单机样本） |
| 外部 Provider | not_applicable | 当前链路不发送外部请求 |

# 风险、兼容性、迁移与回滚

无依赖或既有公共字段语义变动；新增可选只读 `revocation_recomputed_content_count` 并同步生成 Contract。0064/0065 Migration 新增两张业务分片表，既有 Campaign/Run/内容行不回填或重写。历史已落地的错误撤销预估是不可变审计事实，本轮不追溯改写；终态展示实际重组量及预估差异。顶部入库量仍是不同任务原计数的累计，不代表全库不同 Content 数。

集合 UPDATE 的主要风险是列集分组、JSONB/时间戳类型及并发锁语义漂移；PostgreSQL Content 并发与 Replay 集成回归覆盖该边界。新增分片表与旧镜像并存时不改变旧业务表，回滚代码应先停新 Worker 并让已受理父子 Job 结清或明确接管，保留分片表；不能在活跃 Job 期间直接 downgrade。当前用户 Compose 未部署此提交，也未改变其数据库。

# 文档、依赖、部署与发布影响

同步 `docs/product/02_当前产品能力与用户流程.md` 的五类运行计数语义、`docs/appendix/08_数据入口与统一入库实现.md` 的 Replay/撤销单位和新分片恢复边界、`docs/blueprint/04_后端任务API与前端.md` 的 Job 类型，以及运行中心设计基线的 KPI 与表宽。未新增、删除或升级依赖、Runtime、配置、Secret；部署需先运行 0064/0065 Migration，再启动新 Worker/API。回滚代码前需让新版父子 Job 结清或明确恢复方案，保留新表。本轮没有执行用户 Compose 或生产部署。

# 完成审计

本次扩展重新核对用户关于统一 Job、自适应调度、历史重筛单路起步、普通导入撤销和重筛撤回的决定，并反查当前业务表、Job 注册、两个 Migration、前端撤回入口与测试。R1–R7 的原有事实、统计口径和既有测试继续有效；R8–R11 已用本轮工作树验证，不复用旧 Head 的 Ready 声明。

上游→实现：历史导入继续沿冻结 Chunk 与 Campaign 锁顺序调度；较大、预检样本主要命中的 Replay Run 按稳定来源身份在原 Run 去重边界内分片；两类大撤回按互不重叠的 Content UUID 范围分片。Replay Run 与两类撤回共用父子 Job、Fence、完成屏障和单路起步的资源/吞吐反馈控制；各业务执行器保存自己的来源、断点、计数和结果。两片 Replay 因没有运行中试双路的机会而沿串行路径，低命中率输入也沿串行路径，避免各片重复读取拖慢整次 Run。

实现→测试：跨 Artifact 同身份去重、两类撤回父 Job 失败后的持久断点接管，以及正式 Worker 的两片 Replay 墙钟对照已有证据。父任务重试时，完成屏障曾把旧父 Job 当作子 Job；本轮按 Job 类型区分后，两类撤回的父失败重试测试均通过。子 Job 在业务提交后终态失败时，以已原子结清的业务分片为准；针对性故障注入已通过。Replay 首次并发创建来源尝试的请求行锁问题已修复并有集成测试。ingestion 全量 78 个回归通过；当前 Head CI 仍是合并前独立门禁。

反向能力审计：用户可见父请求只在所有业务分片已提交、关联子 Job 到终态及父计数对账后报告成功；子 Job 在业务提交后终态失败由已提交分片证明并记 WARNING，未结清的失败仍阻止父任务成功。失败的 Replay 撤回提供重试入口。列表、详情及任务中心的原统计口径继续由 API/页面对应分支提供。新分片表只保存工作单元身份与断点，业务 Current/Version/来源仍由原 Owner 写入；旧串行断点不被新分片重切。新增两个持久 Job 类型已注册到同一个 Worker Registry，没有新队列。

- [x] upstream_re_read：已重新读取用户扩展决定、#603 原验收与当前实现边界。
- [x] change_coverage：R1–R11 均有对应上游来源和本轮证据。
- [x] reverse_audit：已反查四类流程的 API/Worker/业务表/页面与父子完成状态。
- [x] unresolved_cleared：本地全量 ingestion、针对性故障恢复及两阶段 Review 已完成；新 Head CI、合并和清理仍为交付门禁。

# 两阶段 Review

第一阶段复核原现场六条记录、贡献归属及五类运行计数，证据见 R1–R7。扩展阶段复核冻结输入、来源身份、Content 范围、事务 Fence/断点、父子终态与资源反馈。已发现并修复旧父 Job 误判、Replay 首次来源尝试并发冲突；同文件正式 Worker 实测自动七片 45.882 秒慢于串行约 30–31 秒，因此增加有界预检命中样本与小输入保护。新策略在该文件抽样 2,176/239 行后选单路，正式 Worker 29.974 秒、结果对账不变。

第二阶段复核最终 diff、取消和重试时序、Migration 降级、文档、静态检查及集成测试，未发现当前范围内的阻塞问题。全历史重筛保留单路起步；仅在冻结输入大、预检样本命中较多且资源足够时创建足够的持久片，同一次 Run 才有逐级试档的工作量。低命中或小输入沿串行路径，以避免每片重新解析全部输入造成已实测的回退。不得用原型单/双路速度推算正式实现或其他服务器收益。

# 完成证据与状态

| 证据 | 环境与命令 | 结果与边界 |
| --- | --- | --- |
| V1–V7 | 原范围采集运行计数、撤销预览、集合写入与现场/隔离实验 | 证据详见 R1–R7；发生于扩展前的 revision，不证明新增分片实现。 |
| V8 | Windows 隔离 PostgreSQL 18；正式 Worker 的同一份 66,139 行 XLSX | 串行 30.106/30.922 秒，双 Worker/两片 26.140/30.664/31.341 秒，自动七片 45.882 秒；加入有界命中样本后自动选单路 29.974 秒。四种路径均为 5,965 新增、1,091 去重；双路收益不稳定，不能宣称已找到服务器最优并行度。 |
| V9 | 当前工作树；容量单元测试、两类撤回父失败重试及 Replay 分片去重集成测试 | 容量/分片单元 15+11 passed，两类撤回父失败重试与 Replay 分片去重针对性集成通过；ingestion 全量 78 passed，Content 在清理隔离测试库后单独 73 passed。 |
| V10 | 当前工作树；Ruff format/check、mypy、前端 lint/Vitest/build | 已通过；前端 234 tests passed，生产构建通过。Windows 合跑的 9 个文档路径/宿主准备单元断言仍失败，待 Linux CI 复核。 |
| V11 | 隔离 PostgreSQL 18；Migration 0064→0065 | 升级、非空表降级拒绝及 Alembic check 已完成；部署前仍需正常备份和既有迁移门禁。 |
| V12 | Windows 隔离 PostgreSQL 18；正式 Job/独立 Worker 进程执行重筛撤回 | 10,000 Content 单路 11.085 秒、自适应双 Worker 10.140 秒；20,000 Content 单路 24.110 秒、自适应双 Worker 23.754 秒。计数及未撤回账本分别为全部结清/0；单轮样本收益小，不能外推。 |
| V13 | 同一隔离库；正式 Job/独立 Worker 进程执行普通导入撤销 | 10,000 Content 先单路 19.394 秒、后自适应双 Worker 9.177 秒；20,000 Content 反向顺序先自适应 15.266 秒、后单路 20.759 秒。两边重组计数均与输入相等。10,000 单路的贡献读取累计约 10.24 秒；分片降低反复扫描成本。幅度随数据和缓存变化，不作生产百分比承诺。 |

未验证：新版在用户 Compose、不同规格服务器上的持续吞吐收益，动态窗口的跨机器最优性，正式生产数据负载。新增分片对大撤回的正确性已有针对性证据，但不能把早期无父子调度原型数字当成正式耗时。PR #604 当前工作树尚未提交到新 Head，CI、merge、main-fresh、归档、Issue Closure 与分支清理均待完成；本轮未执行 Release 或生产部署。
