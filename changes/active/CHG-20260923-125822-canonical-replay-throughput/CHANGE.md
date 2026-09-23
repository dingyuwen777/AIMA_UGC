---
schema: coding-change/v1
id: CHG-20260923-125822-canonical-replay-throughput
title: 全历史 Canonical 重筛吞吐优化
level: L3
status: in_progress
owner: yuwen.ding
branch: perf/canonical-replay-throughput
created: 2026-09-23T12:58:22+08:00
updated: 2026-09-23T12:58:22+08:00
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - storage
  - jobs
  - logging
affected_paths:
  - backend/src/aima_ugc/
  - migrations/versions/
  - tests/
  - docs/
  - scripts/performance/
contracts:
  - canonical-content.v1
  - ingestion.canonical-replay.v1
data_changes:
  - artifacts 验证证明
  - canonical_replay_runs 检查点
  - contents 与 canonical_replay_content_changes 业务和撤回事实
---

# 变更摘要

全历史重筛需在不削弱预检、Content Owner、检查点、取消和精确撤回语义的前提下提高总吞吐。当前每文件重复完整解析，每条命中行又产生多次数据库往返；多 Worker 虽可领不同子任务，却共享数据库和同名日志文件。本 Change 记录预检、数据库、派生刷新、并发与基准的完整施工边界；不执行生产迁移、全量重筛或合并 main。

# 当前事实与待确认

| 编号 | 已确认事实 | 来源 | 决策作用 |
| --- | --- | --- | --- |
| E1 | 每 Run 最多 100 个文件，首笔写库前完整预检 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` | 保持坏文件零业务写入 |
| E2 | Reader 每次打开复制并校验摘要，随后解析两遍 | `backend/src/aima_ugc/platform/storage/canonical.py` | 消除重复工作，不能只信元数据 |
| E3 | 1,000 行只是一笔事务／检查点，匹配内容逐条声明身份并写入 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` | 优化 SQL 往返但不绕过 Owner |
| E4 | Replay 的贡献账本与 Source/Evidence 在业务事务内产生 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` | 批量路径必须保留精确撤回 |
| E5 | 多 Worker 共用 `worker.log` 且按进程轮转 | `backend/src/aima_ugc/platform/logging/setup.py`、`compose.yaml` | 扩容前隔离文件名 |

待确认：目标服务器真实总行数、文件大小、命中率、数据库资源和实际瓶颈。没有服务器测量不能宣称固定加速倍数；本任务先建立可重复本地/隔离环境基准。

# 目标与边界

- 预检在每个子任务首笔业务写入前检查全部输入，有损坏文件时保持该子任务零业务写入。
- 通过安全的验证复用减少重复解析，历史文件没有有效证明时仍须完整验证。
- 沿现有 Owner 批量化匹配行处理，保持 Current、Version、Metric、来源、Evidence、检查点和撤回结果。
- 支持可控多 Worker 并发与安全日志轮转，以阶段与数据库指标决定容量。
- 不改变 HTTP、Canonical 文件格式、品牌车型编辑触发条件；不部署、不运行生产 Migration、不合并 main。

# 方案比较

1. 保持当前完整预检，只优化 Reader 第二次读取和批量声明身份：迁移风险低，可立即减少解析和 SQL，但每次重筛仍重复预检，其他逐行写入仍慢。
2. 推荐：在方案 1 基础上增加与字节摘要、当前 Contract 和来源证明绑定的持久验证记录；旧文件有界回填，重筛安全复用；再按测量结果优化 Content Owner 与派生刷新。增加 Schema/回填和并发验证成本，但兼顾长期重复重筛与零写入边界。
3. 删除预检、边读边写、遇错自动撤回：首次读取成本最低，但当前撤回不是失败子任务自动回滚，坏文件会形成已可见部分写入，改变已批准安全语义，不采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 任一坏文件在子任务首笔写入前被发现，取消/重试/Fence 仍有效 | #581 / AC1 | not_satisfied | 待实现与验证 |
| R2 | 消除无必要的重复解析，历史和新 Artifact 均有安全验证路径 | #581 / AC2 | not_satisfied | 待实现与验证 |
| R3 | 减少逐行数据库往返，保持内容、证据、来源、账本及撤回等价 | #581 / AC3 | not_satisfied | 待实现与验证 |
| R4 | 多 Worker 日志安全轮转，并按真实负载控制并发 | #581 / AC4 | not_satisfied | 待实现与验证 |
| R5 | 可重复基准和相关集成、迁移验证证明改进与兼容 | #581 / AC5 | not_satisfied | 待实现与验证 |

# 实施步骤

1. 预检与 Reader：在 `platform/storage` 与 Replay Worker 保留全文件前置校验，消除内部冗余解析；测试后部坏文件和中途取消。
2. 验证证明：依据当前 Artifact/来源 Schema 增加可复用证明和历史回填；测试摘要、Contract/来源版本变化、接管和部分回填。
3. 数据库：先量化逐行热点，再在现有 Owner 内批量声明身份、预取与写入；以隔离 PostgreSQL 对照旧语义和撤回结果。
4. 派生刷新：只在测量证明触发器热点时合并重复刷新，保留同事务可见性；验证内容、版本与证据变更后读模型一致。
5. 并发、观测与基准：隔离 Worker 文件日志，记录阶段耗时和吞吐；从 1、2、4 Worker 逐级比较总吞吐、锁、WAL、I/O 和连接占用。
6. 同步当前运行文档，执行完成审计、独立 Review、CI 和 PR Ready；不合并 main。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Reader 校验、验证证明、日志命名及批次规则 |
| 接口 / 契约 | required | Canonical 文件与 Job/API 兼容、Schema/Migration 检查 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL 的写入、账本、取消/重试/Fence/撤回和 Migration |
| 用户 / 工作流验收 | required | 手动重筛到运行结果，坏文件失败与撤回状态 |
| 跨组件关键路径 | required | API → Job → Artifact → Content → 结果的代表性路径 |
| 外部依赖 / 供应方探测 | not_applicable | Replay 不调用 TikHub 或付费模型，外部服务不是本次瓶颈事实源 |
| 构建 / 打包 / 运行 | required | Worker 启动、Compose 多副本配置与正式包检查 |
| 文档 / 治理 / 其他 | required | Operations/Appendix、Change、架构/Owner/Secret/CI 门禁 |

# 风险、迁移与回滚

新 Schema 仅向前增加验证证明，不改历史 Migration；旧代码不能依赖新表。历史 Artifact 不直接信任 SHA 元数据，需按完整旧路径回填；失败可重试。代码回滚时保留新增证明表但旧 Worker 不读取它；不能对可能已执行重筛的数据直接删除或回滚 Schema。批量写入与派生刷新必须保持事务与锁顺序、Fencing 和现有撤回语义。具体部署顺序和验证结论待实现后记录，本任务没有生产操作授权。

# 完成审计

- [ ] upstream_re_read：重读 #581 和相关正式文档，独立重建完成定义。
- [ ] change_coverage：核对上游要求均进入本 Change。
- [ ] reverse_audit：从 Artifact/数据库生产者到运行中心结果及撤回反向核对。
- [ ] unresolved_cleared：所有要求已满足或有正式延期依据。

# 新鲜证据与交付状态

当前为开工记录，尚未执行目标测试、性能基准、Migration、Review 或 CI；上述 R 行保持 `not_satisfied`。任务分支 `perf/canonical-replay-throughput`，Issue #581，PR 待建立；禁止据此声称可合并。
