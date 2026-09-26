---
schema: coding-change/v1
id: CHG-20260926-voice-catalog-lock
title: 缩短导入事务持有声音广场筛选目录热行锁的时间
level: L3
status: ready_for_review
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
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_reversal_worker.py
  - backend/src/aima_ugc/bootstrap/import_revocation_worker.py
  - backend/src/aima_ugc/modules/ingestion/canonical_replay_tables.py
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

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 解除已确认的目录计数热行锁长事务占用 | #616 / AC1 | satisfied | PostgreSQL 并发回归：第二事务在第一事务收尾前完成 Content 写入；同机每路 500 行、六路总计 3000 行，旧版 6.548 秒，新版 2.259 秒；服务器吞吐待部署后复测。 |
| R2 | 入口、重筛、撤回与投影账本保持正确 | #616 / AC2 | satisfied | 统一 Campaign Chunk、兼容单文件 Job、Replay 批次、普通撤销批次、重筛撤回批次均在事务尾结清投影；隔离 PostgreSQL 71 条受影响回归、8 条单文件回归与可见性断言通过；撤回部分提交与既有投影不一致的缺陷同步修复。 |
| R3 | 资源适应不同机器，不以这台服务器的数值硬编码 | #616 / AC3 | satisfied | 沿 `detect_resources`、`worker_process_limit`、`AdaptiveJobWindowController`、Batch Tuner 与 Compose 预算检查；本次没有写入任何主机专用档位，投影尾刷新使现有吞吐探索不再被已确认热行锁过早压制。 |
| R4 | 迁移可升级、可回滚，CI 与 PR 可审查 | #616 / AC4 | satisfied | Migration 0067 在隔离 PostgreSQL 反复降级/升级、相邻迁移集成 2 条通过；包含已撤回重筛旧投影的定向修复和可见性索引；Draft PR #617 已建立。Current-head CI 属 Ready 后平台门禁，不把未发生的结果写成本地验证。 |

# 实施步骤

1. 在隔离 PostgreSQL 复现共享目录计数行阻塞，记录基线和正确性断言。
2. 添加可逆 Migration 与 Content Owner 的事务内批量刷新入口；在 Chunk 业务写入尾部刷新并增加阶段耗时日志。
3. 检查普通导入、重筛、撤回是否可使用同一机制，并测试多写入路径、并发、回滚及重试。
4. 测量同条件前后耗时与等待，运行目标回归、迁移和完整门禁；复核文档与 Issue 要求后提交 PR。

# Completion Audit

- [x] upstream_re_read：重读 Issue #616、用户服务器锁采样、项目数据与 Job 规则及当前入口调用链。
- [x] change_coverage：R1–R4 的机制、迁移、测试和文档均有对应落点。
- [x] reverse_audit：从已提交 Chunk、单文件 Job、Replay 批次和两类撤回反查声音广场；从投影可见性反查 Content 来源判断，补齐撤回部分提交时的差异。无前端 Contract 改动。
- [x] unresolved_cleared：本地实现要求无 `not_satisfied`；生产服务器全量速度、锁等待、CI 与合并后验证仍由各自环境的新鲜证据证明。

# 验证与边界

- 隔离 PostgreSQL：受影响导入/重筛/撤销/取消 71 条、兼容单文件导入 8 条、迁移 2 条，以及 Campaign 运行中投影和 1 万条撤回分片的定向回归，均通过；六路每路 500 行同条件对照 6.548 秒 → 2.259 秒。
- `ruff check`、`mypy backend/src/aima_ugc` 已通过；最终格式和当前 HEAD CI 仍需检查。
- 投影仍是每个业务事务的同库同步工作，不声明服务器 24,874,335 行全程已经达到最优；上线后需比较 `projection_refresh_ms`、`content_ingestion_ms`、Worker/PG 活动等待及完整吞吐。
- Migration 升级会定向修复已撤回重筛但仍显示可见的旧投影；回滚至 0065 会恢复旧触发器与旧可见性函数，可能重现原问题。
