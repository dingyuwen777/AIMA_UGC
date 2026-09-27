---
schema: coding-change/v1
id: CHG-20260927-160343-replay-cancel-import-performance
title: 历史重筛、取消撤回与数据导入性能修复
level: L2
status: in_progress
owner: codex
branch: fix/630-replay-import-performance
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - backend-api
  - ingestion
  - jobs
  - database
  - performance
affected_paths:
  - frontend/src/features/import-batches/
  - frontend/tests/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/modules/ingestion/
  - tests/
  - scripts/performance/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts:
  - 保持现有 HTTP/OpenAPI 与持久 Job Payload 兼容
data_changes:
  - 无 Schema 或生产数据迁移
---

# 变更摘要

Issue #630 统一处理三个生产问题：全历史重筛约每分钟处理一万原始行；“取消并撤回”确认后按钮短暂置灰又恢复，未稳定进入撤回完成态；数据导入在重筛并发时明显变慢。现有日志可确认导入批次的大部分事务时间位于品牌/车型 Evidence 写入，但不足以把重筛、取消和导入的全部耗时归因到单一机制。

# 目标与成功标准

- 服务器应用日志能以 HTTP request ID、Replay 父请求 ID 和 Job ID 追踪取消请求的接收、数据库阶段、事务提交、协调取消和撤回终态；失败记录安全的阶段与错误分类，不记录正文、Raw 或凭据。
- 修复取消请求未稳定持久化或前端刷新后恢复为可再次取消的真实原因；重复操作保持幂等。
- 分离测量 Replay 扫描、匹配、Content 写入、Evidence 写入、投影刷新、等待锁与事务提交，取得同机 PostgreSQL 的隔离及 mixed-load 证据。
- 修复已证实的 Replay 与数据导入瓶颈；若剩余瓶颈属于机器资源饱和，提供 CPU、I/O、锁等待或数据库吞吐证据及投入产出边界。
- 保持公共 HTTP、数据库 Schema、贡献账本、Fencing、Checkpoint、精确撤回和其他数据链路的业务语义。

非目标：升级依赖、提高全局资源预算、绕过统一 Job Runtime、部署或修改生产数据。

# 已确认事实、推断与未知项

## 已确认事实

- 用户复现中，二次确认后按钮会置灰，随后恢复为“取消并撤回”；这证明前端进入了异步提交状态，但不能单独证明后端是否提交。
- 本次日志窗口中，两个 2,000 行导入批次总耗时约 69–94 秒；Evidence 阶段约 57–64 秒，是已观测的主要耗时阶段。
- 同一日志窗口有五个 Replay Worker 与一个前台预留 Worker并发使用 PostgreSQL；导入能被领取，但执行吞吐可能受共享数据库写竞争影响。
- 当前前端在 5xx、非 JSON 或网络异常后刷新父状态；若父状态仍未变化，按钮会恢复可操作并提示结果未确认。

## 合理推断

- 按钮恢复可能来自取消请求未到应用、API 等待数据库锁后超时、事务未提交、或刷新读取到尚未可见的旧父状态；必须用同一请求的阶段日志与数据库状态区分。
- Evidence 写入慢可能来自锁等待、重复索引/存在性查询、逐行写入或与 Replay 竞争；仅凭阶段总时长不能选择永久优化方案。

## 暂时无法验证

- 服务器当前部署的精确 Git SHA、镜像 digest 与新日志对应版本。
- 大库上 Replay 和 Evidence 阶段的 SQL 时间、锁等待、WAL、I/O 与 CPU 占比。
- 当前取消请求究竟在哪个阶段未收敛。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 计划证据 |
| --- | --- | --- | --- | --- |
| R1 | 系统解决历史重筛吞吐慢，最差重新筛选应与初次入库有可比速度 | Issue #630 / 用户生产复现 | not_satisfied | 隔离与 mixed-load 基准；阶段日志；同输入实际写入量对比 |
| R2 | “取消并撤回”必须正确持久受理、显示真实状态并最终撤回 | Issue #630 / 用户生产复现 | not_satisfied | API/数据库并发回归、前端状态回归、服务器阶段日志、Worker 终态 |
| R3 | 修复数据导入性能回退，不得以提高全局资源掩盖共享数据库争用 | Issue #630 / 用户生产复现 | not_satisfied | Historical Import 阶段/SQL 证据、重筛前/并行/后对照 |
| R4 | 日志足以由用户重新运行后定位，不要求浏览器 Console 或 Network | 用户明确要求 | not_satisfied | API 与 Worker 的关联日志字段及日志测试 |
| R5 | 保持 Contract、Schema、贡献账本、Fencing、Checkpoint 与精确撤回 | 项目 AGENTS.md | not_satisfied | Contract、集成和回归测试 |
| R6 | 完成 Review、CI、PR 与交付门禁 | 项目 AGENTS.md | not_satisfied | Completion Audit、独立 Review、current-head CI |

# 实施计划

1. 为取消路径增加低频阶段日志：HTTP 到达、管理员校验后受理、父状态/锁阶段、取消协调 Job 入队、事务提交、返回，以及协调 Worker 的批次/锁忙/完成/失败。
2. 用并发 PostgreSQL 测试复现按钮恢复所对应的服务端失败边界；若取消仍能被 Replay 父行或 Job 行阻塞，缩短 HTTP 事务并修复锁顺序/状态收敛。
3. 把 Replay 与 Historical Import 的高耗时阶段细分为可比较、低频的聚合日志；避免每批刷 INFO。
4. 在本地 PostgreSQL 分别运行 Replay、初次导入、Evidence 写入和 mixed-load；根据结果优化真正主导的 SQL/批处理或并发边界。
5. 回归取消、撤回、入库正确性、性能、静态检查和构建；同步长期排障文档并完成独立 Review。

# 验证矩阵

| 维度 | 状态 | 验证 |
| --- | --- | --- |
| 前端状态 | required | 确认提交、请求异常、刷新旧/新父状态、重复点击 |
| API / 日志 | required | 接收、提交、冲突/异常和 request/replay ID 关联 |
| PostgreSQL 并发 | required | 父行/Job 行锁、幂等受理、取消协调、自动撤回 |
| Replay 正确性/性能 | required | New/Existing/低命中；隔离和 mixed-load 阶段吞吐 |
| Historical Import | required | Evidence 阶段、初次导入、重筛前/并行/后对照 |
| 静态/生成/构建 | required | Ruff、mypy、前端 lint/typecheck/build、Contract check |
| 生产实测 | limited | 用户部署后重跑；本任务不擅自部署或写生产数据 |

# 风险、兼容与回滚

- 日志必须低频且只记录 ID、状态、数量、阶段、耗时和安全错误类；禁止正文、Raw、Token、Cookie 或 Secret。
- 若修改内部批处理或锁边界，必须通过真实 PostgreSQL 的账本、幂等、Fencing 与撤回回归。
- 公共 HTTP 与数据库 Schema 默认不变；发现必须变更时先更新本 Change 与对应 Contract/Migration 决策。
- 应用代码可按既有 Release 回滚；若存在新状态或新 Job 类型，必须先证明旧 Worker 可识别，否则以前滚修复为主。

# 完成审计

- [ ] upstream_re_read：重新读取 Issue #630、用户日志与最终代码。
- [ ] change_coverage：R1–R6 均达到 satisfied 或有正式延期依据。
- [ ] reverse_audit：前端动作到 API、API 到父状态/协调 Job、Worker 到撤回终态；Replay 到 Import 共享数据库影响。
- [ ] unresolved_cleared：没有用日志、机器性能或局部优化冒充根因闭环。

