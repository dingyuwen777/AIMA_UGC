---
schema: coding-change/v1
id: CHG-20260926-135000-voice-catalog-lock
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

Issue #616。Linux 导入期间，多数 PostgreSQL 活动写事务等待 `voice_plaza_filter_catalog` 的同一计数行。把投影刷新移至每个 Chunk 或 Job 业务事务的尾部，缩短共享行锁持有时间；投影仍随该事务提交，用户无需等整个任务结束。

# 背景、现状与问题

当前 Content 版本写入即触发投影和筛选目录计数更新。Chunk 随后还要写来源账本、Evidence、完成状态并调度后续 Job，因此过早持有目录计数行锁。Linux 采样有 5 路锁等待，Worker 与 PostgreSQL CPU、内存、配额均未饱和。保持现状时增加 Worker 不能有效提高这段吞吐。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 导入中的 `INSERT INTO content_versions` 出现 5 路锁等待 | 用户 2026-09-26 Linux `pg_stat_activity` 采样 | 必须解决写事务等待，而非仅扩大进程池 |
| E2 | 等待元组属于 `voice_plaza_filter_catalog` | 用户 Linux `pg_locks` 查询 | 缩短同一计数行的锁持有时间 |
| E3 | Content 写入期间由投影触发器同步更新该表 | Migration 0054、0061 | 需调整触发时机并保留原子性 |
| E4 | Chunk 在 Content 写入后仍有账本、Evidence 与调度工作 | `historical_import_worker.py` | 投影可在本事务尾部刷新 |

## 推断与待确认

服务器全程速度提升幅度要在部署本 PR 后复测；本机隔离数据库对照只证明已确认锁瓶颈上的收益。

# 目标、成功标准与非目标

## 目标

解除目录计数热行过早锁定，同时使每个已提交 Chunk 或 Job 的声音广场内容、筛选计数立即可见。

## 成功标准

- [x] 同值 Content 并发写入不被前一事务的后续账本工作阻塞，且隔离 PostgreSQL 对照有可测收益。
- [x] 历史导入、兼容单文件导入、重筛、普通撤销与重筛撤回在每次事务提交时保持 Content 与投影一致。
- [x] 迁移可升级和降级，正确修复既有已撤回重筛的错误可见投影。
- [x] 不新增机器专用资源档位，保留现有运行时自适应策略。

## 范围

业务写事务、Content 投影仓储、可逆迁移、集成测试及数据入口文档。

## 非目标

不修改界面、公共 API、产品等待提示、依赖版本或生产服务器部署。

## 必须保持不变

Content 与派生投影原子提交；失败、取消、重试、重放、撤回和 Job fencing 语义；现有 Compose 与资源探测入口。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 由 Content 投影仓储提供事务内批量刷新，各业务 Worker 在提交前调用 | E3、E4 | 单一读模型写入口 |
| 接口与契约 | 公共 HTTP/Job Payload 不变 | 业务事务内部重排 | 无消费者升级 |
| 数据与迁移 | Migration 0067 调整触发器，并定向修复旧撤回可见性 | E3 | 升级时执行有限批次修复 |
| 错误与失败语义 | 刷新失败使同一业务事务回滚 | 原子性目标 | 不出现已入库但投影缺失 |
| 兼容性 | 筛选目录自身入口仍同步触发 | E3 | 保持已有筛选读模型语义 |
| 部署与回滚 | 先迁移再运行新版 Worker；降级恢复旧触发器 | 迁移依赖 0065 | 降级会重现旧锁竞争 |

# 修改方案与决策依据

## 最小充分方案

1. Migration 0067 为业务事实的投影触发器增加事务局部延迟条件；保留筛选目录入口触发器。
2. Content 投影仓储集中实现开启延迟与按受影响 Content ID 批量刷新；各 Chunk、Job、撤回批次在业务提交前调用。
3. 对照隔离 PostgreSQL 并发耗时；验证中途可见性、撤回、重试、降级/升级和现有资源探测边界。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：事务尾刷新 | E1–E4 | 在不牺牲原子性的前提下缩短共享计数行锁持有时间 |
| D2：每个 Chunk/Job 提交即刷新 | E4、用户本轮要求 | 既保持过程可见，又无需等待整项任务结束 |

## 备选方案与取舍

分桶计数需修改读模型 Schema、查询与回填，而且仍会有同桶争用。异步刷新可进一步解耦写入，但会改变精确计数和故障恢复语义。本次保留同事务精确投影，并用实测决定是否仍需更大结构变更。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 缩短已确认目录计数热行锁持有时间 | #616 / AC1 | satisfied | 并发回归确认第二事务可在第一事务收尾前完成 Content 写入；六路各 500 行基线 6.548 秒、新版 2.259 秒 |
| R2 | 入口、重筛、撤回及投影账本正确且逐批可见 | #616 / AC2 | satisfied | Campaign Chunk、单文件 Job、Replay、两类撤回均于事务尾结清投影；真实 PostgreSQL 回归和运行中可见性断言通过 |
| R3 | 不以服务器数值硬编码资源档位 | #616 / AC3 | satisfied | 保留现有资源探测、进程池、Job 窗口与批量 Tuner；新逻辑不写主机专用值 |
| R4 | 可逆迁移、CI 与 PR 可审查 | #616 / AC4 | satisfied | 0067 降级/升级及相邻迁移测试通过；PR #617；当前 HEAD CI 作为独立平台门禁继续验证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Migration 0067、Content 投影仓储 | 延迟触发、批量刷新、可见性修复 | 缩短热行锁，保持原子性 | R1、R2 |
| 导入、Replay、撤回 Worker | 每次业务事务尾刷新受影响 Content | 逐 Chunk/Job 可见 | R2 |
| 历史 Campaign 调度/账本锁 | 调整兼容的行锁模式与取消屏障 | 防止并发死锁 | R2 |
| PostgreSQL 集成测试与数据入口文档 | 证明并发、迁移、部分完成可见性并同步事实 | R1–R4 可复核 | R1–R4 |

- [x] 调查当前实现和事实源。
- [x] 建立风险与验证矩阵。
- [x] 建立并发失败测试与基线。
- [x] 完成实现和文档同步。
- [x] 取得当前提交的本地验证证据。
- [x] 完成需求追溯与完成审计。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Content 来源可见性、撤回状态判断的定向断言 |
| 接口 / 契约 | not_applicable | 未改变公共 HTTP、Job Payload 或生成契约 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PostgreSQL 并发、迁移、导入、重筛与撤回测试 |
| 用户 / 工作流验收 | required | Campaign 运行中首个 Chunk 提交后可见；重筛撤回部分提交时可见性正确 |
| 跨组件关键路径 | required | Worker → Content 账本 → 投影触发器 → 目录读模型 |
| 外部依赖 / 供应方探测 | not_applicable | 不调用外部 Provider，服务器复测是后续部署验证 |
| 构建 / 打包 / 运行 | required | Python 静态检查、迁移升降级；CI 构建当前提交 |
| 文档 / 治理 / 其他 | required | 数据入口文档、Change、Requirement Source 检查与 PR CI |

## 验证计划

- 目标测试：并发写入、运行中投影和撤回部分提交。
- 相关回归：历史 Campaign、单文件导入、Replay、撤回与相邻 Migration。
- 静态检查或构建：`ruff check`、`ruff format --check`、`mypy`、当前 PR CI。
- 专项真实边界：隔离 PostgreSQL 0065 与 0067 同条件对照。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 漏掉某个写入口使投影未刷新 | 全部已注册相关 Worker 调用链审计；同事务回归测试 |
| 兼容性 | 公共 API、Job 与来源账本兼容 | 仅改变事务内投影刷新时机 |
| 数据 / Migration | 0067 修复旧撤回投影并新增定向索引 | 隔离 PostgreSQL 升降级与迁移测试 |
| 部署 / 运行 | 新镜像须在 Migration 0067 后运行 | 保持正式 Compose 迁移顺序 |
| 回滚 / 恢复 | 降级至 0065 恢复旧触发器，可能复发热锁与旧可见性问题 | 停止新版 Worker 后按正式回滚流程执行 |

# 文档、依赖、部署与发布影响

- 长期文档：更新 `docs/appendix/08_数据入口与统一入库实现.md`，说明逐 Chunk/Job 投影和耗时日志。
- 依赖 / Runtime：未改变依赖版本；当前锁文件不需更新。
- 配置 / Secret：不增加环境变量或密钥。
- 部署 / Release：需要运行 Migration 0067 与新版 Worker；本任务不执行服务器部署。
- 兼容 / 消费方通知：公共 Contract 未变，前端无需更新。

# 完成审计

- [x] upstream_re_read：重读 Issue #616、用户 Linux 锁采样、项目数据/Job 规则及当前写入口调用链。
- [x] change_coverage：R1–R4 均有实现、迁移、测试或文档落点。
- [x] reverse_audit：从 Chunk、单文件 Job、Replay 和两类撤回反查声音广场；从投影可见性反查 Content 来源，覆盖撤回部分提交。无前端 Contract 改动。
- [x] unresolved_cleared：本地实现无 `not_satisfied`；服务器全量性能与当前 PR CI 仍按各自环境验证，不以本地结果代替。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 分支提交 `361d4468`，隔离 PostgreSQL 18 | 导入/重筛/撤回/取消受影响集成测试 | 71 passed | 业务及投影原子性回归 |
| V2 | 同提交，隔离 PostgreSQL 18 | 兼容单文件导入测试 | 8 passed | 原入口逐 Job 投影 |
| V3 | 同提交，隔离 PostgreSQL 18 | 0067 降级/升级、相邻迁移测试、`alembic check` | 通过；无新升级操作 | 迁移及 Schema 可逆 |
| V4 | 同提交，隔离 PostgreSQL 18 | 六路各 500 行同条件对照 | 0065 为 6.548 秒；0067 为 2.259 秒 | 已确认热行锁路径显著改善 |
| V5 | 同提交，本机 | `ruff check`、`ruff format --check`、`mypy backend/src/aima_ugc` | 通过 | 静态与类型检查 |

## 未验证内容与剩余风险

服务器 24,874,335 行全程、资源最优点和生产镜像性能尚未在新版部署上实测；上线后需核对 `projection_refresh_ms`、锁等待、Worker/PG 利用率及全程吞吐。本地对照不能证明所有机器的最终增益。

## 交付状态

- 提交：`361d4468`；本 Change 格式修订待后续提交。
- 拉取请求：#617，Ready。
- CI：当前 HEAD 检查中；尚不声明通过。
- 合并：尚未合并。
- Change 归档：合并后按正式门禁处理。
- 发布 / 部署：未执行，用户服务器需后续发布验证。
