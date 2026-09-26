---
schema: coding-change/v1
id: CHG-20260926-voice-catalog-lock
title: 缩短导入事务持有声音广场筛选目录热行锁的时间
level: L3
status: in_progress
owner: codex
branch: fix/616-voice-catalog-lock
created: 2026-09-26
updated: 2026-09-26
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - database
  - documentation
affected_paths:
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - migrations/versions/
  - tests/integration/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes:
  - PostgreSQL 声音广场派生投影触发器执行时机；读模型仍随业务事务原子提交
---

# 变更摘要

Issue #616。Linux 导入期间多数 PostgreSQL 活动写事务等待 `voice_plaza_filter_catalog` 的同一计数行，机器 CPU、内存及配额均未饱和。缩短同事务内该热行锁的持有时间，保持精确读模型及取消、重试、回滚语义。

# 事实与证据

| 编号 | 已确认事实 | 依据 |
| --- | --- | --- |
| E1 | 活动导入的 `INSERT INTO content_versions` 出现 5 路锁等待 | 用户 2026-09-26 Linux `pg_stat_activity` 三次采样 |
| E2 | 等待元组属于 `voice_plaza_filter_catalog` | 用户 Linux `pg_locks` 只读查询 |
| E3 | 该表由声音广场投影触发器在 Content 写入期间同步增减 | Migration 0054、0061 与当前 Chunk Worker |
| E4 | 同一 Chunk 的来源账本、Evidence、完成和调度继续在投影更新之后执行 | `historical_import_worker.py` 事务调用链 |

# 目标与范围

- 已提交的 Content、投影与筛选目录始终原子一致，任何失败均整笔回滚。
- 不同 Content 同值写入的并发 Chunk 不再因过早持有筛选目录计数行而被串行化；用 PostgreSQL 并发测试和本机相同数据量对照验证。
- 检查普通导入、历史导入、重筛及撤回调用链对相同触发器的影响，按证据确定可安全共享的修复范围。
- 不修改公共 API、依赖、读模型精度或用户数据删除语义；不执行生产部署。

# 方案判断

1. 本事务延迟派生投影刷新至业务写入尾部，仍在同一事务提交：锁持有期短，迁移和调用方都需要明确覆盖写入的 Content ID。
2. 分桶计数：必须修改 Schema、查询和旧数据回填；各 Chunk 同时写多个分桶仍可能冲突。
3. 异步投影：可以解耦写吞吐，但会改变产品精确计数与失败恢复语义。本次选择方案 1，并以隔离 PostgreSQL 测量作为继续交付条件。

# Requirement Traceability

| Requirement | 上游依据 | 状态 | 实现/验证 |
| --- | --- | --- | --- |
| R1：解除已确认的目录计数热行锁长事务占用 | Issue #616、用户采样 | not_satisfied | 待并发回归与对照测量 |
| R2：入口、重筛、撤回与投影账本保持正确 | 用户全链路要求、项目数据规则 | not_satisfied | 待调用链审计与事务回归 |
| R3：资源适应不同机器，不以这台服务器的数值硬编码 | 用户明确要求 | not_satisfied | 待资源控制审计与文档 |
| R4：迁移可升级、可回滚，CI 与 PR 可审查 | 项目 AGENTS.md、Issue #616 | not_satisfied | 待隔离 PostgreSQL、PR CI |

# 实施步骤

1. 在隔离 PostgreSQL 复现共享目录计数行阻塞，记录基线和正确性断言。
2. 添加可逆 Migration 与 Content Owner 的事务内批量刷新入口；在 Chunk 业务写入尾部刷新并增加阶段耗时日志。
3. 检查普通导入、重筛、撤回是否可使用同一机制，并测试多写入路径、并发、回滚及重试。
4. 测量同条件前后耗时与等待，运行目标回归、迁移和完整门禁；复核文档与 Issue 要求后提交 PR。

# Completion Audit

待实现和新鲜证据完成后独立复核 R1–R4、异步状态、取消与反向读取能力。
