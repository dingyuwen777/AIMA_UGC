---
schema: coding-change/v1
id: CHG-20260923-205123-canonical-replay-bulk-ingestion
title: 全历史 Canonical 重筛集合式入库优化
level: L3
status: done
owner: yuwen.ding
branch: perf/canonical-replay-bulk-ingestion
created: 2026-09-23T20:51:23+08:00
updated: 2026-09-23
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - vehicles
  - jobs
  - persistence
  - logging
affected_paths:
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_reversal_worker.py
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - tests/
  - scripts/performance/
  - docs/operations/02_4000万历史迁移与Analysis Run运行手册.md
contracts:
  - canonical-content.v1
  - ingestion.canonical-replay.v1
  - ingestion.canonical-replay-reversal.v1
data_changes: []
---

# 变更摘要

把全历史 Canonical 重筛的命中新内容主路径从逐行数据库往返改为现有业务 Owner 内的集合式批量写入；对并发冲突和已有内容保留兼容回退。同步收紧事务、checkpoint、取消/Fencing 和撤回性能边界，并用同一 PostgreSQL、同一数据形态的旧/新对照证明端到端吞吐，而不是再以局部 SQL 减少量代替真实改善。

# 背景、现状与问题

服务器以当前 `main` 处理 25,819 个 Canonical 文件时，一个子任务在约 22 分钟只读取 17,017 行；后续状态为读取 28,151、匹配 6,188、新入库 5,379、已有收敛 809。同期 PostgreSQL 约 185% CPU、Worker 约 5.9% CPU。当前证据表明预检和文件读取不是主要耗时，命中行进入 Content、来源贡献、品牌/车型证据、贡献账本时的逐行查询/写入/快照才是主要瓶颈。

上一轮优化已经批量认领 Replay 身份、批量插入部分账本并复用事务内快照，但本地 100 行样本只从 3.603 秒降到 3.067 秒，服务器端仍不可接受。它切掉了部分往返，没有切断“每个命中行分别经历完整数据库状态机”的主要机制，因此本任务必须建立真实批量 Owner 能力和同环境回归门槛。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策作用 |
| --- | --- | --- | --- |
| E1 | Replay 在首笔业务写入前对当前子任务全部 Canonical 执行完整性预检 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` | 预检是安全边界，不能为提速删除 |
| E2 | 命中行虽共享事务和部分缓存，仍逐行完成 Content、贡献快照、自动证据和 ledger 构造 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py`、`backend/src/aima_ugc/adapters/persistence/postgres/content_complete.py` | 真实批量必须落在表 Owner 内，不能由 Worker 直写业务表 |
| E3 | 服务器样本中命中行约 87% 是新入库，PostgreSQL CPU 显著高于 Worker | user:#585 的运行证据 | 优先批量化新内容主路径能直接覆盖当前主要工作量 |
| E4 | Replay checkpoint、业务写入和贡献 ledger 需要同事务且受 Fencing 保护 | 现有 Replay/Job Repository 与集成测试 | 不能以长事务、异步补账或提前 checkpoint 换吞吐 |
| E5 | Reversal 每个 100 Content 批次都会重新统计全部剩余 ledger | `backend/src/aima_ugc/bootstrap/canonical_replay_reversal_worker.py` | 撤回大任务存在可消除的重复全表统计 |

仍待本任务用隔离 PostgreSQL 确认：逐阶段墙钟与 SQL 分布、不同新内容比例下的实际加速、事务批大小的最优安全范围。服务器完整硬件/I/O/WAL 状态未提供，因此本地改善不能被推算为服务器固定耗时承诺。

# 目标、成功标准与非目标

- 在现有 Owner 内批量写入新 Content、Version/Metric、来源贡献、自动品牌/车型证据和 Replay ledger，消除主路径逐行往返。
- 同一输入的新旧实现数据库结果等价；已有内容、并发冲突或无法安全批量处理的行回退到既有语义。
- 业务写入、账本、checkpoint 和 Fencing 在有界事务内原子提交；取消、接管、异常和重试不会产生半批可见结果。
- 保留第一次业务写入前的完整预检和精确撤回；撤回不再在每批后重复统计全部剩余账本。
- 在同一 PostgreSQL、同一数据集与配置下取得至少 3 倍命中行端到端吞吐，并报告墙钟、SQL 和结果对账。
- 不修改公开 HTTP/Job/Canonical Contract，不新增 Migration、依赖、必填配置或前端行为；不部署、不操作生产数据。

# 约束与意图决策

Content、来源贡献、品牌/车型证据仍由各自正式 Owner 写入；Replay Worker 只能编排，不得通过临时 SQL 绕过业务表 Owner。完整预检、Job Lease/Fencing、取消、幂等、checkpoint、贡献 ledger 和精确撤回是硬不变量。性能门槛以同环境旧/新端到端结果为准，不能只用查询数、单个 helper 微基准或不同机器结果声称满足。

本次不预先授权 Schema 变化。如果现有表约束不能支持安全集合写入，必须回到用户决策门禁重新评估，而不是在实施中顺手增加 Migration。用户授权 Git 分支、提交、PR 和完成门禁后的主分支合并；未授权 Release、部署、生产 Migration 或服务器数据操作。

# 修改方案与决策依据

采用方案 2：为现有写 Owner 增加针对 Replay 的集合式批量能力。先批量预取/认领输入状态，按“可证明为新内容的安全快路径”与“已有或竞争行兼容路径”分区；快路径使用集合式 SQL 并由数据库冲突结果决定是否回退，不能仅依赖先查后写。业务写入、来源贡献、自动证据、ledger 与 checkpoint 仍在一个有界事务内完成。阶段耗时使用 DEBUG 级安全字段，批次结束才记录一次。

## 备选方案与取舍

1. 继续调大批次、减少少量查询并直接增加 Worker：改动小，但服务器已经证明单 Worker 主要耗在逐行数据库写入；更多 Worker 会先放大 PostgreSQL CPU、WAL 和锁竞争，不能切断主因。
2. 已采用：在各业务 Owner 内提供集合式新内容快路径，已有/冲突行回退。能覆盖当前约 87% 的匹配工作量，同时保留原有复杂更新语义和回滚边界；实现与测试成本中等。
3. 使用临时 staging 表或 `COPY` 后用大型 SQL 全量合并全部 Content/证据/账本：理论吞吐更高，但会把多个 Owner 的状态机、版本/指标和证据规则压进新的数据库程序，形成第二套实现，正确性和长期维护风险过高，当前不采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 同环境代表性负载的命中行端到端吞吐至少达到当前 main 基线 3 倍 | #585 / AC1 | satisfied | 同一 PostgreSQL 18.4、1 Worker、1000 行全命中新内容：main 三轮中位数 25.067 秒 / 18,069 SQL；最终实现三轮中位数 5.817 秒 / 72 SQL，约 4.31 倍、SQL 减少约 99.6%；持久计数 rows_seen=1000、matched=1000、ingested=1000、existing=0 |
| R2 | 新旧路径对 Content、Version、Metric、来源贡献、自动证据、ledger、计数、checkpoint 等价且重跑幂等 | #585 / AC2 | satisfied | `test_canonical_replay_worker.py` 21 passed；101 行验证 Current/Version/Metric/External ID/来源贡献/Brand/ledger 数量和 delta；富 Canonical Content 回归 6 passed，覆盖 media/topics/mentions/locations；车型与派生品牌证据进入 ledger；既有收敛与重复重跑仍走兼容路径 |
| R3 | 取消、Lease/Fencing 接管、异常回滚和重试保持事务边界 | #585 / AC3 | satisfied | 21 项 Replay 集成覆盖批次间取消、业务写后 checkpoint 前取消整批回滚、Lease 接管和 stale fence 拒绝；业务、seen、ledger 与 checkpoint 零半批变化 |
| R4 | 精确撤回保持正确且移除逐批剩余总数全表扫描 | #585 / AC4 | satisfied | 101 Content 跨两批撤回成功，精确恢复/隐藏语义既有回归通过；SQL listener 证明整个 Reversal 仅 1 条 `count(distinct ...)` 初始统计，结束仍检查未结清 ledger |
| R5 | 完整性预检仍先于首笔业务写入，失败时业务/ledger/checkpoint 零变化 | #585 / AC5 | satisfied | Replay 集成的后部坏件、Import parent 失败、证明失效与文件只开一次等预检回归均通过；首笔业务写前验证边界未改 |
| R6 | 不改公开 Contract、Schema、依赖或必填配置；同步性能观测与基准文档 | #585 / AC6 | satisfied | `generate.py --check`、`check_compatibility.py`、架构/表所有权/文档检查通过；无 Migration、Manifest、lock、配置、HTTP/Job/Canonical 变更；运行手册同步批量边界、DEBUG 阶段耗时和最终基准 |
| R7 | Unit/Contract/PostgreSQL/Job workflow、基准、静态检查和独立 Deep Review 完成 | #585 / AC7 | satisfied | targeted Unit、38 项相关 PostgreSQL 回归、三轮基准、Ruff、Mypy、Contract/Docs/Architecture 已通过；Deep Review 发现的多值 SQL 上限、基准持久计数和车型证据覆盖缺口已修复并复验，当前无阻塞 Finding |
| R8 | PR current-head CI、guarded merge 和合并后 main fresh CI 完成 | #585 / AC7 | explicitly_deferred | `.github/workflows/ci.yml` 只在 Change 先进入 `ready_for_review` 且 Draft 转 Ready 后运行完整 PR CI，main fresh CI 只能在合并后运行；这些步骤按必需交付顺序延后到本 Change 的外部 GitHub 门禁，不延期到未来功能、不豁免，PR 未绿禁止 merge，main 未绿禁止关闭 #585 |

# 计划改动

1. 建立基线与 Red：固定代表性 Canonical 数据形态，记录当前 main 的端到端墙钟、SQL 分布和结果摘要；新增批量等价、失败回滚、取消/接管和撤回回归并确认目标缺口。
2. Content/贡献 Owner：增加集合式新内容写入与贡献快照构造；数据库唯一约束决定并发冲突，冲突行回退正式逐行路径。
3. 证据/Replay 编排：批量写入自动品牌/车型证据和 Replay ledger；按安全批次原子推进 checkpoint/Fencing，补阶段级低噪声观测。
4. Reversal：一次取得剩余规模并按已处理量推进进度，避免每批重扫；保持独占贡献判断和精确前态恢复。
5. 对照验证与调优：同库同数据运行旧/新至少三轮，只有结果等价且吞吐门槛满足才进入 Ready；否则回到瓶颈证据，不合并。
6. targeted 文档同步、Completion Audit、Deep Review、PR current-head CI、guarded merge、main fresh CI、自动 Change 归档与 Issue Closure。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | 批量分区、结果聚合、checkpoint 计算、阶段统计和 reversal 进度 |
| 接口 / Contract | required | Canonical/Job/HTTP Contract 与生成物不变，Schema 无漂移 |
| 集成 / Persistence / Runtime Dependency | required | 真实 PostgreSQL 下集合写入、唯一约束竞争、事务回滚、幂等、Fencing、取消、checkpoint、撤回和 SQL 计数 |
| 用户 / Workflow Acceptance | required | 正式 Replay Worker 从预检到成功/取消/撤回的 operator 可观察状态与结果 |
| 跨组件 Golden Path | required | API/Job/Worker/Artifact/Content/Replay result 的代表性真实链；不在此层穷举所有错误状态 |
| External Dependency / Provider Probe | not_applicable | Replay 不调用 TikHub、LLM 或其他远端 Provider，当前问题不依赖外部协议事实 |
| Build / Package / Runtime | required | Python 静态检查、正式 Worker 装配、Docker/Runtime 受影响入口检查 |
| Docs / Governance / Other | required | Operations 文档、Issue/Change/PR 追溯、Completion Gate、Deep Review、PR/main CI |

# 风险、兼容性、迁移与回滚

- 正确性风险：批量状态构造与逐行语义漂移。通过同输入双路径数据库快照/账本差分和现有 Owner 回退控制。
- 并发风险：预取后其他写入者抢占身份。批量插入必须以数据库冲突返回为准，冲突行不能被当作已成功新建。
- 事务风险：批次过大会阻塞 Heartbeat 或延长 Job 行锁。使用有界匹配行批次，并避免重复锁 Job；以取消/接管和阶段时长测试确定上限。
- 性能风险：测试数据不能代表生产新/旧内容比例。基准显式报告比例并至少覆盖服务器当前以新内容为主的形态；服务器真实耗时仍需部署后测量。
- 兼容 / Migration：无公开 Contract、Schema、Migration、依赖和配置变化；旧代码路径保留为兼容回退。
- 回滚：合并前性能或正确性门槛失败则不合并；发布后异常由正式 Release 回退镜像。已产生 Replay 贡献由现有 reversal 操作撤回，不使用手工 SQL。

# 文档、依赖、部署与发布影响

Docs Impact 为 targeted：更新 4000 万历史迁移运行手册中 Replay 批量写入、阶段观测、同环境基准和 Worker 扩容顺序；其他架构文档只有在最终实现改变其当前事实时才修改。无新依赖、锁文件、Migration、公共 API 或前端生成物。合并不包含 Release/Deploy；服务器只有发布新镜像后才会获得新实现。

# 完成审计

- [x] upstream_re_read：重新读取 #585、用户运行证据和相关 Blueprint/Operations，独立重建 AC1—AC7。
- [x] change_coverage：确认所有 AC、不变项、非目标、取消/接管/checkpoint/撤回与性能门槛均进入实现和验证。
- [x] reverse_audit：从 Canonical/Job 输入到 Content/证据/ledger/checkpoint，再从取消/接管/撤回和运行中心结果反向核对；复核所有 Validation Matrix 证据边界。
- [x] unresolved_cleared：所有 `not_satisfied` 已清零；R8 仅因 GitHub 门禁顺序显式延后，未被豁免；没有用服务器未部署事实、不同环境样本或 CI 绿色替代 AC 的直接证据。

# 完成证据与状态

当前分支 `perf/canonical-replay-bulk-ingestion`，Requirement Source 为 #585。实现已完成本地正确性、性能、静态、文档和独立 Deep Review，当前进入 `ready_for_review`。PR current-head CI、guarded merge 和 main fresh CI 按 R8 的 GitHub 顺序门禁继续执行。用户工作区 `.codex/config.toml` 和既有本地 pytest 临时目录不属于本 Change，不得修改或提交。

## 当前本地证据

- Red：101 行 Replay 原实现出现 101 条 `UPDATE contents`，确认逐行状态机是可执行缺口，而非只凭日志推断。
- Green：最终 Replay Worker PostgreSQL workflow `21 passed`；相邻 Replay Repository、Import Reversal、Content Audit 合计 `17 passed`（其中富 Canonical Content Audit `6 passed`）；Replay Benchmark/Job/Schema targeted Unit `6 passed`，更新后 benchmark guard `2 passed`。
- 性能：main 三轮 25.061 / 25.402 / 25.067 秒、18,069 SQL；最终实现三轮 5.817 / 5.797 / 6.101 秒、72 SQL，中位吞吐约 171.9 行/秒，约 4.31 倍。每轮使用新的空数据库和空工作目录，输入导入不计 Replay 窗口。
- 静态/边界：Ruff targeted、Mypy 366 source files、Contract 生成/兼容、架构、表 Owner、Docs/Facts 均通过；无 Migration、依赖、锁文件或公共 Contract 变化。
- 广域测试：Unit 全量在 Windows 沙箱外为 `1228 passed, 8 skipped, 9 failed`；9 项均为仓库既有 Windows 平台/文档隔离路径断言（6 项文档导航，3 项 POSIX `geteuid/chown`），不触及本 Change。Contract/API 为 `188 passed, 1 failed`；唯一失败由仓库既有 Provider 调试输出中的 `xhsdiscover://` 原始链接触发平台别名扫描，不触及本 Change。Linux PR CI 仍是这些环境项的交付门禁。
- Deep Review：重新以 #585 AC1—AC7 和 `origin/main@6c48fe6e` 审查 Owner、并发冲突、事务、Fencing、checkpoint、取消、撤回和容量证据；多值 SQL 改为每条最多 500 行，基准补齐持久计数，车型/派生品牌证据补齐集成覆盖，修复后无未解决阻塞 Finding。
