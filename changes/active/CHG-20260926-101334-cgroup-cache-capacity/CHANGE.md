---
schema: coding-change/v1
id: CHG-20260926-101334-cgroup-cache-capacity
title: 修复容器资源误降档与导入 Chunk 父锁串行
level: L2
status: in_progress
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
| R1 | 大量 inactive_file、少量匿名内存时不误判内存耗尽 | #610 AC1；服务器 cgroup 与日志 | not_satisfied | 待测试与实现 |
| R2 | 真实匿名内存压力、宿主可用内存不足或统计缺失时保守降档 | #610 AC2；项目资源安全要求 | not_satisfied | 待测试与实现 |
| R3 | Worker 进程池、Job 窗口、批量控制器共用修正后的资源快照并可观测 | #610 AC3；当前调用链 | not_satisfied | 待测试与实现 |
| R4 | 数据/恢复语义不变，现有导入不中断，目标回归通过 | #610 AC4–AC5；用户本轮要求 | not_satisfied | 待验证 |
| R5 | 同一 Campaign 的不同来源 Chunk 能并发进入业务写入，取消仍线性化 | 用户要求全链路真实提速；当前父行锁与共享取消门 | not_satisfied | PostgreSQL 双 Worker 并发测试待跑 |
| R6 | 分别审查预检、入库、重筛、撤销/撤回与进程池，区分已测和未测 | 用户本轮要求；服务器日志与代码 | not_satisfied | 日志审计与完成审计待填 |

# 实施计划

1. 用服务器数值写资源探测失败测试，并覆盖匿名内存、宿主压力、统计缺失与边界值；观察预期失败。
2. 在公共 cgroup 探测处修正有效余量，保持回退保守；在现有低频资源调整日志中记录原始用量与可回收缓存。
3. 用 PostgreSQL 双 Worker 测试验证同 Campaign Chunk 可并发进入 Content 写入，再缩短 Campaign 父行锁覆盖的事务区间；保留并发取消回归。
4. 运行目标单元、相关回归和静态检查，审查 Worker、导入、重筛、撤回消费者；同步数据链路排障文档。
5. 对照 Issue 与上游要求完成审计，取得 PR/CI 和 Review 证据；服务器真实吞吐留待部署后对比。

# 验证矩阵

| 层次 | 验证内容 | 当前状态 |
| --- | --- | --- |
| 单元 | cgroup v2 数值、压力与回退；Job/Worker 消费 | 待运行 |
| PostgreSQL 集成 | 同 Campaign 双 Worker 并行写入、取消与恢复状态 | 待 CI 运行 |
| 静态 | Ruff、Mypy、Change 校验 | 待运行 |
| Linux CI | 目标回归及仓库必需检查 | 待运行 |
| 服务器 | 同类导入和重筛吞吐、OOM/压力事件 | 未部署，不宣称已提速 |

# 风险、回滚与完成审计

风险一是把不可回收内存错判为缓存而过度升档，因此仅对 Linux 报告的 `inactive_file` 扣除脏页/写回页后作有界折减，读取异常回退原计算，且宿主可用内存仍约束最终结果。风险二是 Chunk 并发引起 Content 共享身份锁竞争，需用真实 PostgreSQL 集成和现有取消回归验证，数据库瞬时冲突沿现有 Job 重试恢复。回滚为恢复旧镜像，Job/数据格式无迁移。完成审计在 Ready 前重读本轮用户要求、Issue、实现和测试后填写。
