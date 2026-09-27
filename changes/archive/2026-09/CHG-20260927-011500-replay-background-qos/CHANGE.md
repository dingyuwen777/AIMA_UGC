---
schema: coding-change/v1
id: CHG-20260927-011500-replay-background-qos
title: 低命中历史重筛后台 QoS 与单位资源吞吐优化
level: L3
status: done
owner: codex
branch: perf/624-replay-background-qos
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - jobs
  - database
  - operations
affected_paths:
  - backend/src/aima_ugc/entrypoints/worker_main.py
  - backend/src/aima_ugc/platform/jobs/
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - tests/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes: []
---

# 变更摘要

Issue #624。保持现有 Host/Compose CPU 与内存安全余量、Worker/PostgreSQL 总预算和非 Replay 数据链路并发语义不变，只优化 Canonical Replay 自身：为前台/非 Replay Job 保留 Worker 执行能力，修复 Replay 子任务优先级倒置，以 matched rows/事务墙钟驱动低命中扫描批量，并减少 Existing Evidence 冗余数据库往返，补充脱敏结构化诊断日志。

# 背景、现状与问题

生产日志已确认：Replay Worker 已达到当前容器配额允许的最大并发；典型命中率约 20%—30%，Run 内 identity shard 因重复读取完整输入而在低于 50% 命中时强制单片。Existing-heavy Run 中 PostgreSQL transaction / Evidence 收敛占主要耗时，Artifact read 不是首要瓶颈。同时未来多用户并发要求 Replay 不能占满全部 Worker，也不能通过提高 Host/Compose 资源预算换速度。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策依据 |
| --- | --- | --- | --- |
| E1 | 当前 Worker Pool 按容器有效资源计算总进程上限，所有子进程默认支持全部 Job 类型 | worker_main.py / JobWorker | Replay QoS 应在既有 Worker 预算内实现 |
| E2 | Collection Job priority=10；Replay Run priority=0；Replay Shard priority=40；Historical priority=-20 | 当前 Job enqueue 实现 | Replay Shard 存在优先级倒置 |
| E3 | 当前 Replay identity shard 会让每片重读完整冻结输入，低命中时因此直接返回 shard_count=1 | replay_shards.py / canonical_replay_worker.py | 不能简单删除 50% gate |
| E4 | 当前 Replay batch controller 以 raw batch size 作为 size/rows 反馈 | canonical_replay_worker.py / capacity.py | 低命中时小 raw batch 会浪费事务能力 |
| E5 | 用户日志中 Existing-heavy Replay 的 transaction / Evidence 阶段占主要耗时，scalar_fallback_count=0 | user:2026-09-27-replay-logs | 应优化集合 Evidence 往返而不是继续做逐行 fallback 修复 |
| E6 | 用户要求保留 Host 余量并不得降低其他数据链路处理过程 | user:2026-09-27-resource-isolation | 不修改 Compose 资源预算或其他链路控制器 |
| E7 | Issue #624 已按当前技术变更 Project Profile 维护完整动机、当前/目标状态、兼容/回滚与 AC | #624 | PR Requirement Source 可由 CI 直接核验 |

# 目标、成功标准与非目标

目标：在总资源预算不变的前提下，提高 Replay 单位资源吞吐，并让 Replay 主动为其他业务让路。

- [ ] Worker 上限 >=2 时，Replay Run/Shard 无法占满全部 Worker；非 Replay 任务始终有保留执行能力，其他链路仍可使用全部 Worker。
- [ ] Replay Run/Shard 使用后台优先级；Import Reversal 等非 Replay 优先级保持。
- [ ] 5%/25% 命中时 raw scan 可随 hit ratio 增大，数据库批次仍以 matched rows 和 transaction ceiling 有界。
- [ ] Existing Evidence 减少冗余数据库 round trip，before/after ledger 与撤回语义不变。
- [ ] 新增日志能够解释 QoS、scan/matched 决策和 Evidence/transaction 热点，且不泄露正文/Secret。
- [ ] mixed-load 回归证明 Collection/Import/Historical/Analysis/Export 不出现由本变更导致的持续性能退化。

非目标：不修改 scripts/deploy/start_compose.py 资源分配，不提高 Worker/PostgreSQL 全局配额，不升级依赖/Runtime，不重构为新的两阶段 Scan/Match Staging/Writer 架构，不执行生产部署或生产数据操作。

# 约束与意图决策

保持现有 Host/Compose CPU 与内存安全余量、Worker/PostgreSQL 总预算和非 Replay 数据链路并发语义不变；Replay 只能在现有资源上提高单位资源产出并主动让路。完整预检、Job Fence、checkpoint、取消/接管、贡献账本、精确撤回、人工锁和声音广场强一致投影继续作为不可降低的不变量。

# 修改方案与决策依据

采用 Replay 局部 QoS + matched-aware batch + Existing Evidence round-trip 优化：在既有 Worker 总上限内保留一个不领取 Replay 长任务的 foreground-reserve；Replay 父/子 Job 使用后台优先级；低命中时扩大只读 scan window 但 matched target 与事务墙钟仍受控；Existing Evidence 在同一锁边界内用一次联合快照和 DML RETURNING 形成 before/after。

## 备选方案与取舍

1. 直接提高 Worker/PostgreSQL CPU 配额：能增加峰值资源，但破坏用户明确的宿主机余量与多用户保障，拒绝。
2. 删除低命中 shard gate：会让当前 identity shard 重复读取完整 Canonical 多次，可能降低吞吐，拒绝。
3. Scan → Match staging → Identity Writer：可从根上消除重复读取，但会增加新的持久状态/恢复边界；本 Change 完成后只有新证据仍指向读放大时才单独立项。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 保留现有 Host/Compose 安全余量与 Worker/PostgreSQL 总资源预算 | user:2026-09-27-replay-qos / AC1 | satisfied | 本 PR 未修改 start_compose.py / compose 资源预算；Worker reserve 只在既有进程上限内分配角色 |
| R2 | Worker 上限 >=2 时 Replay 不得占满全部 Worker；单进程仍可执行 Replay | user:2026-09-27-replay-qos / AC2 | satisfied | 多进程 Worker Pool 增加 foreground-reserve；单进程自动回退完整类型集；回归已加入 |
| R3 | Collection / Import / Historical / Analysis / Export 的现有调度与业务 Contract 不因 Replay 优化降低 | user:2026-09-27-replay-qos / AC3 | satisfied | 非 Replay Job 类型、优先级和控制器未修改；reserve 允许 priority>-30 的 Historical(-20)及普通任务，general Worker 仍支持全部 Job |
| R4 | Replay Shard 与 Replay Reversal 后台让路，同时 Import Reversal 保持原优先级 | user:2026-09-27-replay-qos / AC4 | satisfied | Replay 父/Planner/Shard=-30；Replay Reversal Shard=-30；Import Reversal Shard=40；共享 shard 用 reserve priority floor 隔离 |
| R5 | 5%/25% 低命中按 hit ratio 扩大 raw scan，数据库事务仍按 matched target/墙钟有界 | user:2026-09-27-replay-qos / AC5 | satisfied | _ReplayScanBatchController + _partition_resolved_batch；5%/25%/0% 与突升命中单元回归、低命中 benchmark fixture |
| R6 | Existing Brand/Vehicle Evidence 减少冗余往返且精确撤回不变 | user:2026-09-27-replay-qos / AC6 | satisfied | Replay convergence 在审核锁内各一次联合 before/target 快照，DML RETURNING 形成 after；Replay/Reversal 与单次快照断言覆盖 |
| R7 | 新日志安全且能解释 Worker QoS、scan/matched 与 Evidence/transaction 热点 | user:2026-09-27-replay-qos / AC7 | satisfied | worker role/reserve、capacity.replay_scan_batch_selected、resource ceiling 与既有 batch_completed 阶段耗时；不记录正文/Secret |
| R8 | Replay 性能基准覆盖低/高命中 Existing/New，mixed-load 证明正常链路无持续退化 | user:2026-09-27-replay-qos / AC8 | satisfied | 同机 PostgreSQL 18.4 专用库的 main/PR 对照见下表；Replay 运行期间的普通 Excel 导入均成功，Worker reserve/优先级有回归覆盖；生产环境收益仍须发布后复测 |
| R9 | Unit、PostgreSQL Integration、Job/Worker、Replay/Reversal、静态、文档、Completion Audit、Review 与 required CI 通过 | user:2026-09-27-replay-qos / AC9 | explicitly_deferred | 当前实现已进入 ready_for_review；current-head required CI 与独立 Review 未通过前禁止 merge |
| R10 | PR merge 后完成 main-fresh、Change Archive、Issue Closure 与分支清理 | user:2026-09-27-replay-qos / AC10 | explicitly_deferred | 按项目交付状态机在 merge 后执行；未完成前不得声明端到端交付完成 |

# 计划改动

1. 先建立失败回归：Replay reserve worker、优先级、低命中 scan/matched 控制与 Evidence 查询次数。
2. 在 Worker 子进程支持集上增加一个非 Replay reserve role；总 Worker 上限及其他链路 supported types 不变。
3. 收敛 Replay 后台 priority，按 reversal kind 区分 Replay 与 Import 子任务。
4. 在 Replay Worker 内实现 matched-aware scan controller；高命中/现有 shard 路径保持兼容。
5. 在 Evidence Repository 增加 Replay 所需的原子 before/after 集合能力，减少 after 重查；保持现有 Import 等调用接口不变。
6. 补结构化日志、targeted 文档、性能/mixed-load benchmark 与完整回归。

# 验证矩阵

2026-09-27 同机隔离基准：Windows Docker PostgreSQL 18.4，main `8778f8e7` 与本 Change 分支使用同一版基准夹具，交替运行；Planner 完成后才开始 Replay 计时。每个场景运行一次，秒数受机器噪声影响，不能把小幅差异当成稳定收益。SQL 为 Replay 计时窗口内语句数。

| 样本 | main Replay | PR Replay | main / PR SQL |
| --- | ---: | ---: | ---: |
| 5000 raw / 5% 命中 / 80% Existing | 1.139 s | 1.188 s | 248 / 244 |
| 5000 raw / 5% 命中 / 10% Existing | 1.133 s | 1.053 s | 232 / 230 |
| 5000 raw / 25% 命中 / 80% Existing | 3.190 s | 2.617 s | 614 / 404 |
| 5000 raw / 80% 命中 / 80% Existing | 7.488 s | 6.552 s | 1150 / 606 |
| 5000 raw / 80% 命中 / 10% Existing | 5.315 s | 5.407 s | 394 / 494 |
| 20000 raw / 5% 命中 / 80% Existing | 3.584 s | 3.571 s | 582 / 508 |

混合负载中，在 10000 raw / 80% 命中 Replay 开始批次后启动独立专用库的 5000 行正式 Excel 导入；main Replay / 导入分别为 17.178 / 6.242 s，PR 为 16.705 / 6.199 s，两版导入与 Replay 都成功。独立导入参考耗时为 5.350 s。该样本与 Worker 领取回归支持“正常导入未失去执行能力”，不替代生产多用户容量验收，也不能证明所有正常链路的实际吞吐完全相同。

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Worker reserve role、Replay priority、5%/25% matched-aware batch、日志选择 |
| 接口 / 契约 | required | HTTP/Job Payload/OpenAPI 不变；内部 Job 调度行为兼容 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL Replay Existing Evidence、Fencing、checkpoint、取消/接管、撤回 |
| 用户 / 工作流验收 | required | 全历史重筛运行/取消/撤回及正常 Collection/Import 等任务同时排队 |
| 跨组件关键路径 | required | Planner → Replay Run → Worker/QoS → Content/Evidence/Ledger → 运行状态 |
| 外部依赖 / Provider | not_applicable | 不调用 TikHub/LLM |
| 构建 / 打包 / 运行 | required | ruff、mypy、相关 tests、CI；Compose 资源文件无 diff |
| 文档 / 治理 / 其他 | required | 数据入口/运行排障文档、Completion Audit、Review |

# 风险、兼容性、迁移与回滚

不改变 public Contract、Schema/Migration、依赖或 Compose 资源预算。主要风险是 reserve role 误阻塞 Replay、低命中 scan 过大导致内存压力、Evidence after 推导与实际持久状态漂移、优先级修改误影响 Import Reversal。所有新行为必须由当前 Job 类型/Replay 专属入口显式触发；默认 JobWorker/Repository API 保持兼容。回滚为应用代码整体 revert，无数据 Migration。

# 文档、依赖、部署与发布影响

targeted 更新 Replay 并发/批量/排障说明；不新增部署配置，不改变服务器资源预算。合并不代表生产已部署，生产收益仍需新 Release 后用同类完整输入复测。

# 完成审计

- [x] upstream_re_read：已重新读取 #624、当前 main 的 Worker/Job/Replay/Evidence/资源与文档 Owner。
- [x] change_coverage：R1-R8 已落实实现、回归和隔离同机基准；R9-R10 保留为 CI/Review 与 merge 后交付门禁，不把尚未完成的门禁冒充已通过。
- [x] reverse_audit：已反查非 Replay Job → reserve/general Worker；Replay → QoS/priority/batch/Evidence → ledger/reversal。
- [x] unresolved_cleared：Ready 前无 not_satisfied；R9-R10 仅因项目交付状态机后置 current-head CI/Review/merge，以 explicitly_deferred 保留且未降低门禁。生产复测属于后续 Release 验收，不计入本次未部署变更的当前性能证明。

# 完成证据与状态

实现、回归与 targeted 文档已落分支。Change 进入 ready_for_review；current-head CI / 独立 Review 仍是 merge 前硬门禁，未取得前禁止合并。
