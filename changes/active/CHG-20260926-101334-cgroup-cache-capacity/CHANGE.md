---
schema: coding-change/v1
id: CHG-20260926-101334-cgroup-cache-capacity
title: 修复文件缓存引发的容器资源误降档
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
  - tests/unit/platform/test_capacity.py
  - tests/unit/jobs/test_worker_entrypoint.py
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes: []
---

# 背景与目标

Linux v3.1.1 上正在导入 24,874,335 行。Worker cgroup 的 `memory.current` 接近 12.55 GiB 上限，但 `inactive_file` 约 12.06 GiB、`anon` 约 228 MiB，Docker stats 显示约 496 MiB，`memory.events` 无 OOM。代码以 `memory.max - memory.current` 判断可用内存，运行日志显示历史 Job 窗口由 6 降到 1，重筛批量由 1000 降到 500。目标是让共享资源快照反映可回收文件缓存，同时保留真实匿名内存和宿主内存不足时的降档。

# 范围与约束

复用现有资源探测和控制器，不改历史 Chunk 冻结语义、Job/断点/Fencing、业务结果、HTTP Contract、Schema、Migration、依赖和启动方式。正在运行的服务器任务不重启；真实服务器吞吐只能在新版本部署后的同类输入上验证。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 大量 inactive_file、少量匿名内存时不误判内存耗尽 | #610 AC1；服务器 cgroup 与日志 | not_satisfied | 待测试与实现 |
| R2 | 真实匿名内存压力、宿主可用内存不足或统计缺失时保守降档 | #610 AC2；项目资源安全要求 | not_satisfied | 待测试与实现 |
| R3 | Worker 进程池、Job 窗口、批量控制器共用修正后的资源快照并可观测 | #610 AC3；当前调用链 | not_satisfied | 待测试与实现 |
| R4 | 数据/恢复语义不变，现有导入不中断，目标回归通过 | #610 AC4–AC5；用户本轮要求 | not_satisfied | 待验证 |

# 实施计划

1. 用服务器数值写资源探测失败测试，并覆盖匿名内存、宿主压力、统计缺失与边界值；观察预期失败。
2. 在公共 cgroup 探测处修正有效余量，保持回退保守；在现有低频资源调整日志中记录原始用量与可回收缓存。
3. 运行目标单元、相关回归和静态检查，审查 Worker、导入、重筛、撤回消费者；同步数据链路排障文档。
4. 对照 Issue 与上游要求完成审计，取得 PR/CI 和 Review 证据；服务器真实吞吐留待部署后对比。

# 验证矩阵

| 层次 | 验证内容 | 当前状态 |
| --- | --- | --- |
| 单元 | cgroup v2 数值、压力与回退；Job/Worker 消费 | 待运行 |
| 静态 | Ruff、Mypy、Change 校验 | 待运行 |
| Linux CI | 目标回归及仓库必需检查 | 待运行 |
| 服务器 | 同类导入和重筛吞吐、OOM/压力事件 | 未部署，不宣称已提速 |

# 风险、回滚与完成审计

风险是把不可回收内存错判为缓存而过度升档，因此仅对 Linux 报告的 `inactive_file` 作有界折减，读取异常回退原计算，且宿主可用内存仍约束最终结果。回滚为恢复旧镜像，Job/数据格式无迁移。完成审计在 Ready 前重读本轮用户要求、Issue、实现和测试后填写。
