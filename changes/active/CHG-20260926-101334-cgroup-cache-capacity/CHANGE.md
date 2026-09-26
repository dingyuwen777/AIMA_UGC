---
schema: coding-change/v1
id: CHG-20260926-101334-cgroup-cache-capacity
title: 修复容器资源误降档与导入 Chunk 父锁串行
level: L2
status: ready_for_review
owner: yuwen.ding
branch: fix/610-cgroup-cache-pressure
created: 2026-09-26T10:13:34+08:00
updated: 2026-09-26
completion_gate: required
depends_on: []
affected_areas:
  - capacity
  - jobs
  - ingestion
  - operations
affected_paths:
  - backend/src/aima_ugc/platform/capacity.py
  - backend/src/aima_ugc/bootstrap/runtime.py
  - backend/src/aima_ugc/entrypoints/worker_main.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - tests/unit/platform/test_capacity.py
  - tests/unit/jobs/test_worker_entrypoint.py
  - tests/integration/ingestion/test_import_campaign_cancellation_postgres.py
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes: []
---

# 背景与目标

Linux v3.1.1 上正在导入 24,874,335 行。Worker cgroup 的 `memory.current` 接近 12.55 GiB 上限，但 `inactive_file` 约 12.06 GiB、`anon` 约 228 MiB，Docker stats 显示约 496 MiB，`memory.events` 无 OOM。代码以 `memory.max - memory.current` 判断可用内存，运行日志显示历史 Job 窗口由 6 降到 1，重筛批量由 1000 降到 500。同一 Campaign 的每个 Chunk 还在整个 Content 写入期间持有 Campaign 父行锁，限制恢复 Worker 后的并行收益。目标是同时修正资源估算和此串行边界，保持取消/恢复语义。

服务器日志复核：361 个 Snapshot 覆盖 24,874,335 行；前 177 个在约 11 分钟内完成，窗口降至 1 后的 184 个在约 90 分钟内完成。当前日志仅包含该 Campaign 180 个 Chunk（355,122 行），其中 `transaction_ms` 累计 264.7 秒、`content_ingestion_ms` 154.0 秒、`finalization_ms` 44.5 秒。两次 Replay 预检各约 15 秒，唯一完成的一次 Replay 入库约 96.7 秒，样本命中率低而选择单分片。此份日志没有普通撤销或重筛撤回的完成记录，不能宣称它们已有生产测速结果。

# 范围与约束

复用现有资源探测和控制器；Chunk 业务阶段共享取消门，父行锁只用于末尾调度与终态收口。不改历史 Chunk 冻结语义、Job/断点/Fencing、业务结果、HTTP Contract、Schema、Migration、依赖和启动方式。正在运行的服务器任务不重启；真实服务器吞吐只能在新版本部署后的同类输入上验证。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 大量 inactive_file、少量匿名内存时不误判内存耗尽 | #610 / AC1 | satisfied | `capacity.py`；服务器数值与资源消费者单元测试 |
| R2 | 真实匿名内存压力、宿主可用内存不足或统计缺失时保守降档 | #610 / AC2 | satisfied | 脏页、宿主余量、统计缺失单元测试 |
| R3 | Worker 进程池、Job 窗口、批量控制器共用修正后的资源快照并可观测 | #610 / AC3 | satisfied | `worker_main.py`、`runtime.py` 调用链与新低频日志字段 |
| R4 | 数据/恢复语义不变，现有导入不中断，目标回归覆盖 | #610 / AC6 | satisfied | 无 Contract/Schema/部署变更；现有服务器任务未操作；单元已通过，PostgreSQL/CI 待执行 |
| R5 | 同一 Campaign 的不同来源 Chunk 能并发进入业务写入，取消仍线性化 | #610 / AC4 | satisfied | `historical_import_worker.py`；双 Worker PostgreSQL 并发与既有取消回归已编写，待 CI 执行 |
| R6 | 分别审查预检、入库、重筛、撤销/撤回与进程池，区分已测和未测 | #610 / AC5 | satisfied | 下方完成审计；未测生产吞吐明确保留 |

# 实施计划

1. 用服务器数值写资源探测失败测试，并覆盖匿名内存、宿主压力、统计缺失与边界值；观察预期失败。
2. 在公共 cgroup 探测处修正有效余量，保持回退保守；在现有低频资源调整日志中记录原始用量与可回收缓存。
3. 用 PostgreSQL 双 Worker 测试验证同 Campaign Chunk 可并发进入 Content 写入，再缩短 Campaign 父行锁覆盖的事务区间；保留并发取消回归。
4. 运行目标单元、相关回归和静态检查，审查 Worker、导入、重筛、撤回消费者；同步数据链路排障文档。
5. 对照 Issue 与上游要求完成审计，取得 PR/CI 和 Review 证据；服务器真实吞吐留待部署后对比。

# 验证矩阵

| 层次 | 验证内容 | 当前状态 |
| --- | --- | --- |
| 单元 | cgroup v2 数值、压力与回退；Job/Worker 消费 | 24 passed |
| PostgreSQL 集成 | 同 Campaign 双 Worker 并行写入、取消与恢复状态 | 待 Linux CI 运行；本地 Docker daemon 不可用，且现有集成 fixture 会清库，不对用户本地库执行 |
| 静态 | Ruff、Mypy、文档、Change 校验 | Ruff / Mypy / docs 已通过；Change 在 Ready 后检查 |
| Linux CI | 目标回归及仓库必需检查 | 待运行 |
| 服务器 | 同类导入和重筛吞吐、OOM/压力事件 | 未部署，不宣称已提速 |

# 风险、回滚与完成审计

风险一是把不可回收内存错判为缓存而过度升档，因此仅对 Linux 报告的 `inactive_file` 扣除脏页/写回页后作有界折减，读取异常回退原计算，且宿主可用内存仍约束最终结果。风险二是 Chunk 并发引起 Content 共享身份锁竞争，需用真实 PostgreSQL 集成和现有取消回归验证，数据库瞬时冲突沿现有 Job 重试恢复。回滚为恢复旧镜像，Job/数据格式无迁移。

# 完成审计

- [x] upstream_re_read: 已重读本轮用户要求、#610 当前验收、服务器日志与 cgroup 数值、代码入口和项目规则。
- [x] change_coverage: R1–R6 对应实现、测试、文档和明确的外部验收边界；无未满足的施工要求。
- [x] reverse_audit: 资源快照向 Worker/Job/批量控制器传播，Chunk 写入向取消门/父调度/终态收口传播；无页面或公共 Contract 变化。
- [x] unresolved_cleared: 代码范围无未决业务语义；PostgreSQL CI 和生产同类输入测速是后续验证门禁，不冒充已完成。

- Data Import 本地上传：上传流与 Artifact 冻结路径保持原有 Contract；当前服务器日志没有完整本地上传时长，不能据此宣称上传提速。上传后共用 Snapshot/Chunk 链，资源误判修复与 Chunk 父锁缩短对其生效。
- Server Path Discover：日志中 361 文件发现为短操作，主要耗时在其后的 Snapshot；现有目录深度与文件数护栏未改。
- Snapshot 预检：361 文件、24,874,335 行。前 177 文件约 11 分钟，21:45 误降档后 184 文件约 90 分钟；读取/映射和 Chunk 发布是主要阶段。修正公共余量后，窗口不再仅因干净页缓存降到 1；实际六路吞吐仍需部署后复测。
- Chunk 入库：所给日志仅有该 Campaign 180 Chunk / 355,122 行，`transaction_ms`、`content_ingestion_ms` 和 `finalization_ms` 分别累计约 264.7、154.0、44.5 秒。父锁从业务写入前移至末尾调度；新增 `scheduling_ms` / `status_refresh_ms` 供新运行区分收口成本。来源内顺序和逐行账本不变。
- 全历史重筛：两次预检各约 15 秒；一次完成入库 96.7 秒，其中事务约 76.8 秒，回退收敛约 34.1 秒。样本命中 428/6400 与 867/6400，现有分片规则因低命中选择单分片；本次仅修正其批量资源误降档，不擅改分片语义。第二次完成记录不在所给日志中。
- 普通导入撤销、重筛撤回：所给日志没有完整事件，不能量化它们的实际速度。两者的分片准入和逐批升降档均读取公共 `detect_resources()`；新资源快照使可回收缓存不再阻止分片/升档，批次收益仍由各自控制器测量。数据库连接余量、取消/Fencing/断点边界未改。
- Worker 进程池：服务器配额允许上限 6，日志显示已扩到 6 后因错误内存压力回落到 1；新快照进入同一进程池循环与 Job 投放窗口。进程数仍受实际 CPU/内存配额、排队 Job 和数据库竞争约束，未宣称固定六路最优。
- 公共 Contract / 依赖 / Migration / 部署：无变化。现有服务器导入没有重启、部署或生产数据操作；跨环境真实提速需新版本同类输入与 CPU、内存、数据库和 OOM 指标对比。
