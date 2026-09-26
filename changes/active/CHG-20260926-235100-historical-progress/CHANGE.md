---
schema: coding-change/v1
id: CHG-20260926-235100-historical-progress
title: 消除大 Campaign 的逐 Chunk 重复扫描
level: L3
status: ready_for_review
owner: codex
branch: fix/618-historical-progress
created: 2026-09-26
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - collection
  - database
affected_paths:
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
  - backend/src/aima_ugc/modules/ingestion/historical_tables.py
  - migrations/versions/
  - tests/integration/ingestion/
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/operations/05_性能审计服务器复测.md
contracts: []
data_changes:
  - Source Item 增加触发器维护的已完成行数和失败 Chunk 数派生计数
  - 历史 Chunk 活跃状态与下一待处理 Chunk 索引
---

# 变更摘要

Issue #618 / AC2、AC5 的工作包。每个 Chunk 收口不再读取整组 Chunk 状态和调度时重排全部剩余 Chunk；运行中心进度从 Source Item 的同步派生计数读取。保留取消、失败、人工重试和事务内可见语义。

# 背景、现状与问题

`refresh_batch_and_campaign()` 每次 Chunk 完成/失败都将 Source 与 Campaign 下全部 Chunk 状态加载到 Python。`schedule_import_jobs()` 的窗口函数对剩余 ready Chunk 重新排序；运行中心每轮聚合全部 Chunk。一个大 Source 的 Chunk 数增长时，这三条重复路径造成平方级总工作量。#616 已证实生产中共享行锁竞争，不能把计数写到每个并发 Chunk 共同持有的 Campaign 行。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策依据 |
| --- | --- | --- | --- |
| E1 | 状态刷新把全部 Source/Campaign Chunk 状态读成 tuple | `historical_import.py` 当前实现 | 改为索引支持的 `EXISTS` |
| E2 | 调度每次对 ready Chunk 做 `row_number()` 排名 | `schedule_import_jobs()` | 按 Source 索引取最早 ready Chunk |
| E3 | Campaign API 与运行中心分别对全部 Chunk 做行数聚合 | `campaign_progresses()` 与 `_campaign_progress_subqueries()` | 从 Source 派生计数读取 |
| E4 | 当前调度同一 Source 仅允许一个 queued/running Chunk，不同 Source 可并行 | `active_for_same_source` 条件及项目正式数据入口文档 | 计数按 Source 分散，避免 Campaign 热行 |

推断与待确认：真实生产 Campaign 规模、查询计划与吞吐待用户服务器日志；本地隔离库提供同数据路径对照。异常网络/Worker 复发路径仍由现有持久 Job 机制处理。

# 目标、成功标准与非目标

目标：Chunk 完成/失败及列表轮询不再随已经存在的 Chunk 数重复全量扫描；同一 Source 的顺序和不同 Source 的并发保持。

- [x] 新 Migration 对存量终态 Chunk 回填计数，升降级可逆；所有状态转换后计数与底层项一致。
- [x] Source/Campaign 收口和调度按索引查未完成状态/首个 ready，既有终态、取消和重试结果保持。
- [x] Campaign API 与运行中心在大 Campaign 下不再聚合全部 Chunk；本地真实 PostgreSQL 给出执行计划/耗时对照。
- [x] 不增加每个并发 Chunk 争用的 Campaign 计数行，回归/并发测试通过。

范围：Ingestion Owner 的 Item 派生计数与状态/调度查询、Collection 只读进度、Migration、相关测试和运行文档。非目标：Provider 并发预算、Content 写入、声音广场投影或任务调度语义重设计。必须保持公共 HTTP/Job Contract、错误及现有 Archive/撤销路径。

# 约束与意图决策

派生计数以数据库 Trigger 在同事务从 Chunk 终态变化维护，稳定字段用 typed columns；Source 行是每个文件的自然分片，当前同 Source 单活跃 Chunk 避免新 Campaign 热行。Collection 只读，不写 Ingestion 表。Migration 先应用，旧代码对新增列向后兼容；降级恢复旧扫描实现需要同步应用回滚。

# 修改方案与决策依据

Migration 0070 给 Source/Item 增加计数列、回填历史终态；语句级 Trigger 对 INSERT/UPDATE/DELETE 的净变化按 Source 合并，避免批量取消逐行更新。增建活跃状态和 ready 顺序索引。Repository 用 `EXISTS` 收口，按 Source 索引取下一 Chunk。Campaign API 与 Collection Runtime 只聚合 Source 行计数。用取消/失败/重试/批量状态变更与真实 Worker 纵切验证。

## 备选方案与取舍

直接在 Campaign 行加计数会使所有并发来源锁同一行，与 #616 的热行失败机制一致；每轮加 `LIMIT` 的 Chunk 聚合仍会随进度重复扫描。按 Source 维护计数与现有单来源串行调度匹配，且读模型只需 Source 规模的聚合。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 大 Campaign 状态/进度不再重复全量扫 Chunk，取消/失败/恢复/并发和运行中心一致，不造新长热锁 | #618 / AC2 | satisfied | 0070 Source 分片计数、索引 EXISTS/LATERAL、39 项 PostgreSQL 工作流回归；双 Worker 不同 Source 并行测试通过 |
| R2 | 集成、迁移与性能对照 | #618 / AC5 | satisfied | 0069→0070→0069→0070 存量回填均为 20 行/1 失败；2 万 Chunk 隔离库对照和 EXPLAIN；ruff/mypy/Alembic check |
| R3 | 服务器只读观察与脱敏日志说明 | #618 / AC6 | satisfied | `docs/operations/05_性能审计服务器复测.md` 复用既有 Chunk 分段耗时与全局慢请求事件 |

# 计划改动

| 模块 / 文件 | 修改 | 原因 | 对应 |
| --- | --- | --- | --- |
| Migration 0070 与 `historical_tables.py` | 派生计数、净变化 Trigger、索引 | 消除读时全量聚合、保留事务一致 | R1 / E3-E4 |
| `historical_import.py` | `EXISTS` 收口、索引首个 ready、Source 计数读取 | 消除逐 Chunk O(N) 状态/排序 | R1 / E1-E2 |
| `collection_runtime_queries.py` | 运行中心读 Source 计数 | 消除轮询的 Chunk 聚合 | R1 / E3 |
| 集成测试与文档 | 状态、迁移、性能和恢复验证 | 防偏差 | R1-R2 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 终态、重试和计数净变化 |
| 接口 / 契约 | required | 公共响应结构与含义不变 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL Trigger、索引、Migration、并发与真实 Worker |
| 用户 / 工作流验收 | required | Campaign 详情与运行中心进度、取消、重试 |
| 跨组件关键路径 | required | Chunk Job → Source/Campaign → API/运行中心 |
| 外部依赖 / 供应方探测 | not_applicable | 不调用 Provider |
| 构建 / 打包 / 运行 | required | Migration 升降级、Schema、类型和 CI |
| 文档 / 治理 / 其他 | required | 正式数据入口文档、Change 与当前 CI |

# 风险、兼容性、迁移与回滚

主要风险是计数与 Chunk 状态漂移、触发器递归、取消批量更新和 Source 行锁等待。Migration 回填并用真实 PostgreSQL 状态矩阵/并发验证；Trigger 仅在净变化非零时更新 Source，调度保持单 Source 单活跃。回滚需先回旧应用，再降级 Migration；业务 Chunk 事实保留，可由迁移重新计算计数。

# 文档、依赖、部署与发布影响

同步数据入口文档与 Ingestion 模块说明；不新增依赖、Runtime、配置、Secret 或公共 Contract。发布有 0070 Migration，生产迁移/部署仍不在本地开发动作范围。

# 完成审计

- [x] upstream_re_read：Ready 前重读 #618 / AC2、AC5、AC6 和当前状态、调度、查询事实。
- [x] change_coverage：状态收口、进度、取消、重试、并发、迁移和回滚。
- [x] reverse_audit：Job 状态到 API 与运行中心；两处进度都由 Source 派生计数汇总。
- [x] unresolved_cleared：Ready 前清零 `not_satisfied`。

# 完成证据与状态

新增计数测试在旧 Schema 上先因缺列失败；修正触发器递归后通过。隔离 PostgreSQL 18.4：Stage 12 Worker/运行中心 24 项，取消、部分预检和撤销 15 项通过；0069→0070→0069→0070 存量 3 Chunk 回填两次均为已完成 20 行、失败 1 Chunk；`alembic check` 无差异；`ruff check` 和 378 文件 mypy 通过。2 万 Chunk 预热后，旧状态查询返回 2 万行耗时 10–16 ms，新活跃状态探测返回 1 行耗时约 2.5–4.0 ms；旧进度聚合 3.1 ms / 607 shared hit blocks，新 Source 聚合 0.02 ms / 2 blocks；旧下一 Chunk 排名 1.9 ms / 313 blocks，新索引查找 0.03 ms / 5 blocks。新旧返回进度数与首个 ready Chunk ID 相同。PR 当前 HEAD CI、两阶段 Review、生产服务器实测与合并后主分支验证仍需完成；本 Change 不声称生产收益已实测。
