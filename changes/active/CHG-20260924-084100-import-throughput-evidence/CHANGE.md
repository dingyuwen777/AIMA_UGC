---
schema: coding-change/v1
id: CHG-20260924-084100-import-throughput-evidence
title: 数据导入真实负载吞吐与确定性性能证据
level: L3
status: ready_for_review
owner: yuwen.ding
branch: perf/import-throughput-evidence
created: 2026-09-24T08:41:00+08:00
updated: 2026-09-24
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - accounts
  - vehicles
  - voice_plaza
  - persistence
  - logging
  - performance
affected_paths:
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/ingestion/
  - migrations/versions/
  - scripts/performance/
  - tests/
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/operations/02_4000万历史迁移与Analysis Run运行手册.md
contracts:
  - canonical-content.v1
  - ingestion.import-excel.v2
  - ingestion.historical-import-chunk.v2
  - ingestion.canonical-replay.v1
data_changes:
  - PostgreSQL projection trigger/function implementation may change without changing business schema
---

# 变更摘要

继续优化本地 Excel、统一历史导入和全历史 Canonical 重筛共享的 Content 写入链路。先用包含稳定作者、已有/新增 Content、品牌车型 Evidence、声音广场投影和多 Canonical 文件的 current-main 基准恢复真实热点，再只对被证据确认的逐行账号回退、投影 Trigger 写放大及其直接调用链做集合化改造。合并必须同时满足结果一致、取消/接管/撤回语义一致和多轮 p50 明确提升，不能用 SQL 数量或代码推断代替墙钟证据。

# 当前事实与问题边界

- 已合并的第一阶段优化在开发机 1000 行合成样本中把 Excel、历史和 Replay 的 SQL/千行大幅降低，并在不含真实稳定作者压力的代表场景取得约 2—4 倍提升。
- 服务器全历史 Replay 的既有日志显示 Worker CPU 较低、PostgreSQL CPU 和块 I/O 较高；这说明继续盲目增加 Worker 不能证明有效。
- 当前必须重新核验：真实 TikHub 稳定作者是否仍进入逐行兼容路径；Content/Version/Metric、来源贡献和 Evidence 写入后，声音广场行级 Trigger 是否造成同步投影/筛选统计写放大；现有阶段日志是否能把两者分离。
- 用户磁盘空间有限。所有新增验证必须使用有界样本、独立任务目录、专用容量数据库和完成/异常清理；不得把持久业务 Artifact 当作可删除验证数据。

# 目标与成功标准

1. 建立可重复的 stable-author + mixed-content + evidence + projection + multi-artifact 容量场景，并保存 current-main 与候选分支同机、同库、同输入、至少三轮的原始样本和 p50。
2. 日志能直接分辨 Artifact/预检、账号合并、Content/Version/Metric、来源贡献、Evidence、投影、账本和提交阶段；INFO 只记录低频任务摘要，批次细节使用 DEBUG。
3. 被确认的目标瓶颈场景至少达到 current-main 的 2 倍 p50 吞吐；既有 Excel/历史/Replay 新建与混合基准不得回退超过 10%。未达到门槛时继续基于阶段证据诊断或停止合并，不降低成功标准。
4. 新旧结果对账覆盖 Content、Version、Metric、账号/备用身份、来源贡献、品牌车型 Evidence、Replay ledger、声音广场投影及筛选统计。
5. 取消、Lease/Fencing 接管、重试、Replay 撤回、首次业务写前完整预检、Artifact 追溯和 PostgreSQL durability 保持不变。
6. 验证结束后删除可确认属于此前/本次验证的临时目录和专用容量数据库，记录绝对目标、删除前后大小与剩余空间；不删除用户文件、持久 Canonical 或业务 Artifact。
7. 当前 HEAD 完成受影响 Unit、PostgreSQL integration、Migration 回环、容量对照、静态检查、文档同步、独立 Review、required CI、guarded merge 和 main-fresh 验证。

# 非目标与必须保持不变

- 不通过关闭 `fsync`、WAL、`synchronous_commit` 或其他 durability 换速度。
- 不删除或降低 Canonical 首次完整校验、Raw/Input/Canonical 证据、来源贡献、Evidence、Replay 可撤回账本、Job Lease/Fencing/取消语义。
- 不先假定异步投影、Canonical Pack、全链路 COPY 或更多 Worker 必须上线；只有当前阶段证据证明同步集合化仍不能满足目标时，才重新进入方案决策。
- 不升级依赖、Runtime、PostgreSQL 或前端框架，不修改任务外 `.codex/config.toml` 和用户数据。

# 方案与取舍

## 采用方案：证据驱动的同步集合化

1. 扩展现有容量脚本，生成真实稳定作者和声音广场投影可见的代表数据，记录阶段墙钟、SQL、WAL/临时空间和结果摘要。
2. 在 Content Owner 内批量归并稳定作者与备用身份；保持现有 freshness、人工锁、唯一约束和冲突回退语义，不在 Worker 复制账号规则。
3. 把声音广场 Content/Version/Contribution/Evidence 的逐行刷新收敛为语句级/集合式刷新，并集合维护筛选统计；事务提交后仍同步可见，不先引入最终一致性。
4. 为每批增加低噪声阶段耗时和回退计数，服务器可仅凭稳定 event 判断账号、内容、Evidence、投影或提交瓶颈。
5. 同一输入在 current-main 与候选分支上多轮运行并对账；只有目标场景达到门槛且其他场景无显著回退，才继续交付。

## 暂不采用

- 完全异步投影：潜在收益高，但会改变任务成功与页面可见时序。先验证同步集合化是否充分。
- 全链路 COPY/Staging 重写：会复制复杂 Content 状态机，当前只有在集合 Owner 仍被数据库往返限制时才有必要。
- 直接增加 Worker：当前服务器证据更接近 PostgreSQL 写放大瓶颈，并发可能放大锁/WAL/IO。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 建立覆盖稳定作者、新旧 Content、Evidence、声音广场和 Canonical 的代表性容量场景 | #589 / AC1 | satisfied | 基准使用正式 Excel→Canonical→Replay 路径、1 个 Worker、1000 行、200 已有 + 800 新建，可切换每行稳定作者/备用 ID；同机最终三轮数据见 `performance-results.json` |
| R2 | 目标瓶颈场景至少 2 倍 p50，既有场景回退不超过 10% | #589 / AC3 | satisfied | 稳定作者 p50 `21.991s → 3.147s`（6.99×）、SQL `16,464 → 110`；无稳定作者混合场景 `11.010s → 2.704s`（4.07×）；全新内容 `5.985s → 2.799s`（2.14×） |
| R3 | 新旧实现对 Content、Version、Metric、账号/备用身份、来源贡献、Evidence、Replay ledger 和声音广场结果一致 | #589 / AC4 | satisfied | 受影响 PostgreSQL/Worker/Migration 集合 `77 passed`；最终关键子集 `13 passed`；覆盖账号冲突整事务回滚、投影提交后立即可见与并发目录计数 |
| R4 | 增加可用于服务器排障的低噪声阶段日志 | #589 / AC2 | satisfied | Replay DEBUG 批次摘要新增 `stable_author_count / batched_remainder_count / scalar_fallback_count`；Excel I/O Retry 记录 stage/operation/type/errno/脱敏文件名；Appendix/Operations 已同步 |
| R5 | 有界验证并清理此前/本次测试数据，避免撑爆磁盘 | #589 / AC6 | satisfied | 每轮基准 64 MiB 硬预算；结束后删除 49 个经过父目录/名称/非重解析点校验的临时目录（7,074 个文件，23,989,050 bytes），删除专用容量库并停止本任务启动的 PostgreSQL 容器；未删除 Canonical/业务 Artifact 或用户文件 |
| R6 | required gate 后通过 PR 合并 main | #589 / AC7 | explicitly_deferred | 必须在实现、Review 与 current-head CI 完成后执行 |
| R7 | 取消、Lease/Fencing 接管、重试、Replay 撤回、PostgreSQL durability 和持久证据保持 | #589 / AC5 | satisfied | 受影响回归覆盖 running 取消、提交前 Fence 失效整批回滚、Lease 接管 checkpoint 恢复、I/O Retry、撤回与贡献账本；未关闭 fsync/WAL/synchronous_commit，未删除 Raw/Input/Canonical |

# Validation Matrix

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | 稳定账号批量归并、集合投影 ID、阶段计时、日志字段和磁盘预算/清理 |
| 接口 / Contract | required | Canonical/Job/HTTP Contract 保持兼容；Schema 变化时同步 Migration/生成物 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 下账号冲突/freshness/人工锁、Content/Version/Metric、贡献、Evidence、投影/筛选统计、取消/接管/重试/撤回和 Migration 回环 |
| 用户 / Workflow Acceptance | required | Excel、历史 Campaign、Replay 的进度、终态和页面读模型在同步事务后可见 |
| 跨组件 Golden Path | required | Artifact→Job→Worker→Content Owner→Projection 的三条代表路径 |
| 外部依赖 Probe | not_applicable | 不调用 TikHub/LLM，使用脱敏合成 Fixture |
| Build / Package / Runtime | required | Python 静态检查、正式 Worker 启动相关测试、Compose/Migration 检查 |
| Docs / Governance / Other | required | Appendix/Operations、性能原始 JSON、Completion Audit、独立 Review、CI/main-fresh |

# 实施步骤

1. 基线与日志 Red：扩展生产路径基准和阶段测量，先在 current-main 取得三轮小样本基线；磁盘不足或数据库门禁不满足时在生成前失败。
2. 稳定作者集合化：复用账号 Owner 批量归并，补结果差分和并发/冲突回归，再重测目标场景。
3. 同步集合投影：新增 Alembic Revision 将受影响行级 Trigger 收敛为语句级集合刷新，保持提交即刻可见；补 Migration 回环和投影/筛选对账，再重测。
4. 观测与服务器手册：输出任务级 INFO 总结和 DEBUG 批次细分，提供可直接复制的日志/SQL 排障命令。
5. 回归与容量：复跑现有三条链路容量场景、取消/接管/撤回、静态检查和文档检查；固化 current-main/候选多轮结果。
6. 清理、Completion Audit、独立 Review、PR current-head CI、guarded merge、main-fresh、自动归档和 Issue Closure。

# 风险、迁移、部署与回滚

- 账号风险：批量路径可能改变主/备用身份冲突和新旧资料赢家。以旧逐行路径为语义参照，冲突失败关闭，不能静默合并。
- 投影风险：Transition Table/集合函数可能漏掉 UPDATE 前后 ID、DELETE 或来源/Evidence 变化。每类触发动作分别覆盖，写后逐表对账。
- 锁与批次风险：集合刷新仍可能形成大事务。保持有界批次，以事务 p95、取消响应和锁等待决定上限，不无限增大批次。
- Migration：采用 expand/replace 方式创建新函数/Trigger 后再移除旧 Trigger；`downgrade` 恢复原行级机制。部署顺序为先 Migration 后新 Worker/API；本任务不执行生产 Migration。
- 回滚：性能或一致性门槛未满足则不合并；合并后代码可整体 revert，数据库使用正式 downgrade 恢复旧 Trigger。已正确写入的业务事实不做手工删除。
- 磁盘：基准创建前检查预算和可用空间；任务只清理经过绝对路径/名称校验的专用测试目录和数据库。

# 文档影响

Docs Impact 为 targeted：同步统一入库实现、4000 万容量/排障运行手册，以及 Migration head/部署注意事项实际受影响的现有文档。不创建新的平行架构说明。

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取 #589、本轮用户对磁盘和声音广场时效的决定、相关 Appendix/Operations、实际 Schema/Migration 和最终代码。
- [x] change_coverage：对 Issue 与最终实现重建覆盖，稳定作者、无稳定作者、新建/已有 Content、Evidence、贡献账本、投影和并发筛选目录都有独立证据。
- [x] reverse_audit：Excel/历史 Campaign/Replay 共用 Content Owner；投影在同事务中刷新；取消、Fence 接管、撤回、日志和运行中心原有消费者保持。
- [x] unresolved_cleared：`not_satisfied` 已清零；只有 PR current-head CI/合并/main-fresh 按生命周期正常延后，性能原始 JSON、测试、Review 和清理证据已固化。

# Review 与验证结论

- 第一阶段语义 Review 发现并修复了批量/单行路径 Account→Content 锁顺序不一致、备用 ID 冲突未显式回归、过长 Trigger 名被 PostgreSQL 截断和并发删除最后一条筛选值时的计数竞态；均已有回归。
- 第二阶段代码/证据 Review 未发现剩余阻断项。Ruff、mypy `367` 个源文件、Unit `1247 passed / 8 skipped / 12 subtests passed`、Contract `112 passed`、API `77 passed`、受影响 PostgreSQL `77 passed`、最终关键子集 `13 passed`、Migration `downgrade → upgrade → current → check`、架构/归属/Secret/文档/Contract 门禁均通过。Windows 不支持的 POSIX host 权限测试本地未执行，由 Linux CI 负责。

# 当前状态

Requirement Source 为 #589，分支为 `perf/import-throughput-evidence`，PR #590 已建立。生产实现、Migration、回归、性能证据、文档、Review 与清理已完成，当前进入 `ready_for_review`；待 current-head required CI 通过后执行用户已授权的合并、main-fresh 和自动归档。用户工作区 `.codex/config.toml` 属于任务外修改，已保留且不会提交。
