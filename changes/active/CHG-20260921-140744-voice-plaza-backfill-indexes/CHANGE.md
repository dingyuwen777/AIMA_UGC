---
schema: coding-change/v1
id: CHG-20260921-140744-voice-plaza-backfill-indexes
title: 声音广场读模型回填索引与超时整改
level: L3
status: proposed
owner: codex
branch: fix/voice-plaza-projection-backfill-indexes
created: 2026-09-21
updated: 2026-09-21
completion_gate: required
depends_on: []
affected_areas:
  - content
  - collection
  - ingestion
  - jobs
  - database
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/collection/candidate_tables.py
  - backend/src/aima_ugc/modules/ingestion/historical_tables.py
  - backend/src/aima_ugc/bootstrap/voice_plaza_projection_worker.py
  - migrations/versions/
  - tests/
  - docs/operations/04_声音广场读模型回填与性能验证.md
contracts:
  - content.voice-plaza-projection-backfill.v1
data_changes:
  - processing_import_batch_items
  - collection_candidate_ingestions
---

# 变更摘要

- **要解决的问题**：真实 1,823,565+ 数据环境中，声音广场投影回填单次 Attempt 运行数小时后超时，投影始终未进入 `ready`，列表、筛选、加载更多和详情继续走旧查询。
- **拟议修改**：为两类来源账本增加按 `content_id` 反查的部分索引，为每个回填批次设置短于 Job Deadline 的 PostgreSQL 语句超时，并记录不含业务正文的批次开始、完成和失败日志。
- **预期结果**：回填不再对历史账本重复做无索引扫描，也不会在单条 SQL 卡住时占用 Worker 数小时；投影可持续推进并最终切换读取路径。

# 背景、现状与问题

## 背景

Issue #551 的 AC8 仍等待真实服务器性能验收。2026-09-21 新日志已经证明当前瓶颈不是前端请求编排，而是读模型回填没有完成。

## 当前现状

- `api.log` 中新版本的全部声音广场列表和详情慢日志均为 `projection_ready=false`，查询耗时约 11–16 秒。
- `worker.log` 中回填 Job `95c0e48c-b0a8-42bf-886b-076750842621` 从 09:52 运行到 13:46 后被 `attempt_timeout` 回收，随后再次从同一 Job 重试。
- `voice_plaza_has_active_source(uuid)` 按 Content 反查 `processing_import_batch_items.content_id` 和 `collection_candidate_ingestions.content_id`，当前 Metadata 与 Migration 均未为这两列建立反查索引。
- 回填执行器只在一个数据库批次返回后 Heartbeat；单条批次 SQL 没有独立语句超时，也没有批次级耗时日志。

## 问题、根因或约束

大规模历史导入使 `processing_import_batch_items` 与 Content 数量同量级。回填每批处理 500 个 Content 时，来源可见性判断缺少按 `content_id` 的索引，可能反复扫描大账本；一旦批次 SQL 超过 Attempt Deadline，单 Worker 又无法在 Handler 阻塞期间主动回收自己，直到进程重启才由 Reaper 接管。

## 不修改的后果

投影持续处于 building/running，所有高频读取继续回退到旧的全局窗口查询；重试会重复消耗数据库资源，且日志只能看到 Job 开始和最终超时，无法定位具体批次。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 首页/筛选第一页中位约 12.7 秒，加载更多中位约 12.2 秒，全部 `projection_ready=false` | `E:/Desktop/logs/logs/api.log` 的 `voice_plaza.read_slow` | 必须先让投影回填完成，不能继续只调前端 |
| E2 | 回填 Attempt 运行约 4 小时后由重启 Reaper 标记 `attempt_timeout` | `E:/Desktop/logs/logs/worker.log` | 单批 SQL 必须有独立于 Job Deadline 的有界失败 |
| E3 | 两张来源账本均有 `content_id` 列但没有相应 Metadata Index | `historical_tables.py`、`candidate_tables.py` | 新增最小反查索引 |
| E4 | 回填函数按 Content 调用来源可见性判断 | Migration `20260920_0054` | 索引必须匹配真实谓词，而不是继续增加无关列表索引 |

## 推断与待确认

- **待确认**：服务器实际 `EXPLAIN (ANALYZE, BUFFERS)` 和索引创建后的真实批次耗时只能在用户本地离线包部署测试后取得；这不阻塞建立与已确认谓词匹配的索引和有界失败机制。

# 目标、成功标准与非目标

## 目标

让 182 万+ 历史数据的声音广场投影回填具备正确的反查索引、批次超时和进度日志，使其可以安全完成并让读取切换到投影路径。

## 成功标准

- [ ] Metadata 与 Alembic head 同时包含两张来源账本的 `content_id IS NOT NULL` 部分索引。
- [ ] 每个回填批次的 PostgreSQL 语句耗时被限制在 Job Attempt Deadline 以内，超时进入现有可重试语义。
- [ ] 批次开始、完成和数据库失败均有安全结构化日志，可看到 generation、批次序号、处理量、进度和耗时。
- [ ] Migration upgrade/downgrade、`alembic check`、目标单元测试和 PostgreSQL 集成测试通过。
- [ ] 用户可从本地离线包部署后的日志确认投影推进到 `ready`，再完成真实性能验收。

## 范围

- Collection/Ingestion 来源账本索引及新 Alembic Migration。
- 声音广场投影回填的单批语句超时和批次级安全日志。
- 对应单元、PostgreSQL 集成测试和运维说明。

## 非目标

- 不修改声音广场 HTTP Contract、筛选语义、排序或 Cursor。
- 不在本地伪造 182 万数据并宣称生产性能已经通过。
- 不引入 Redis、消息队列、搜索引擎、新进程或新依赖。
- 本次不合并 `main`、不构建正式 Release、不执行生产 Migration。

## 必须保持不变

- PostgreSQL 仍是唯一事实库，投影仍是可重建派生数据。
- Job Payload 版本、幂等键、Fencing、Retry、取消和终态串接语义保持兼容。
- `processing_import_batch_items` 与 `collection_candidate_ingestions` 的写 Owner 不变。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只增加 Owner 表的读索引，不改变写入口 | E3、项目表 Owner 规则 | Collection/Ingestion 写语义不变 |
| 接口与契约 | HTTP 与 Job Payload 均保持兼容 | 用户目标只涉及性能恢复 | 不生成 OpenAPI/Client 变化 |
| 数据与迁移 | 新增 `20260921_0055`，只创建可删除索引 | E3、历史 Migration 不改写 | 无业务数据重写 |
| 错误与失败语义 | 单批 SQL 超时复用现有 `voice_plaza_projection_database_error` Retry | E2、现有 Job Contract | 避免新增平行状态或错误协议 |
| 兼容性 | 读结果、筛选、排序、Cursor 和投影内容不变 | #551 / AC1–AC7 | 仅改变查询计划和故障恢复 |
| 部署与回滚 | 先 Migration 再启动 Worker；回滚先停 Worker/应用再 downgrade | 当前部署与 Migration 边界 | 索引可安全删除，业务事实不丢失 |

# 修改方案与决策依据

## 最小充分方案

1. 新增两张来源账本的部分索引并用 Migration 管理。
2. 在每个回填短事务内用 PostgreSQL `set_config(..., true)` 设置语句超时，确保五个批次的最坏上限低于 1800 秒 Attempt Deadline。
3. 在现有统一日志中记录批次开始、完成和数据库错误，不输出 Content ID、正文或 SQL Payload。
4. 用 Metadata、Migration 往返、PostgreSQL 集成和日志回归证明索引与恢复语义。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：来源账本反查索引 | E3、E4 | 直接切断已确认的大表无索引反查，不增加新基础设施 |
| D2：批次级语句超时 | E2 | 即使仍有数据库异常，也能在 Deadline 前回到 Job Retry，而不是卡到重启 |
| D3：批次级安全日志 | E2 | 让服务器测试能区分索引无效、锁等待和批次推进 |

## 备选方案与取舍

- 只缩小 batch：仍会重复无索引扫描，只是单次扫描数量变少，不能修根因。
- 只提高 Job timeout：延长卡死时间，不能让 Handler 有界返回。
- 引入额外进程或缓存：不解决来源账本反查与回填 SQL，增加一致性和运维成本。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 读模型可分片回填、可观察且可安全回滚 | #551 / AC7 | not_satisfied | 待 Migration、超时和日志验证 |
| R2 | 在真实服务器完成列表、筛选、详情和评论性能验收 | #551 / AC8 | not_satisfied | 本次先修复阻塞验收的回填，真实性能仍由用户离线包测试 |
| R3 | 按确认方案修改但暂不合并主分支 | user:2026-09-21#AC1 | not_satisfied | 待本地分支实现、验证并保持未合并 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Collection/Ingestion tables | 增加部分索引 Metadata | 防止来源可见性反查大表扫描 | R1 / E3 |
| `migrations/versions/20260921_0055_*` | 创建/删除索引 | Schema 单一事实与安全回滚 | R1 |
| `voice_plaza_projection_worker.py` | 语句超时和批次日志 | 避免数小时卡死并支持定位 | R1 / E2 |
| Content unit/integration tests | Metadata、超时、日志和 Migration 回归 | 证明真实 PostgreSQL 边界 | R1 |
| 运维文档 | 同步索引、超时和验收方法 | 支持用户离线包验证 | R2 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [ ] 行为变化建立失败证据
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Metadata 索引、批次超时和日志字段回归 |
| 接口 / 契约 | not_applicable | HTTP 与 Job Payload Contract 不变 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL Migration 往返、Alembic diff、真实回填 |
| 用户 / 工作流验收 | required | 用户离线包环境确认投影推进到 ready；本地先验证小规模正式链 |
| 跨组件关键路径 | required | Migration → Worker → projection state 的 PostgreSQL 链路 |
| 外部依赖 / 供应方探测 | not_applicable | 不修改或调用外部 Provider |
| 构建 / 打包 / 运行 | required | Python 静态检查与受影响测试；离线包由用户后续构建 |
| 文档 / 治理 / 其他 | required | 运维说明、Change Ready 和 Secret/Docs 检查 |

## 验证计划

- 目标测试：声音广场读模型 Metadata、Worker 超时/日志单元测试。
- 相关回归：声音广场 Job Contract 与 PostgreSQL 回填集成测试。
- 静态检查或构建：变更文件 Ruff、Mypy；Migration 格式与 imports。
- 专项真实边界：PostgreSQL downgrade/upgrade、`alembic check`、索引定义检查。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 创建索引会消耗数据库 IO；语句超时过短可能增加 Retry | 索引不重写业务数据；超时上限只防失控并保留现有 Retry |
| 兼容性 | 向后兼容 | 不改变公共 Contract、Job Payload 或查询结果 |
| 数据 / Migration | 新增两个可逆部分索引 | downgrade 删除索引，不删除业务数据 |
| 部署 / 运行 | Migration 完成后再启动 Worker | 避免旧无索引回填继续占用数据库 |
| 回滚 / 恢复 | 先停止新 Worker/应用，再 downgrade | 投影是派生数据，业务事实不受影响 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 更新声音广场回填与性能验证运行手册。
- **依赖 / Runtime**：不新增依赖、不升级 Runtime 或锁文件。
- **配置 / Secret**：不新增配置和 Secret；批次超时是内部恢复边界。
- **部署 / Release**：需要运行新 Migration；本次只交付本地分支，不构建或发布正式 Release。
- **兼容 / 消费方通知**：HTTP/前端无变化；运维需关注新批次日志与 projection state。

# 完成审计

- [ ] upstream_re_read：已重新读取 Issue #551、用户本轮决定和正式项目文档，并独立重建完成定义。
- [ ] change_coverage：已确认当前变更覆盖全部上游要求，没有把变更自身当作需求全集。
- [ ] reverse_audit：已复核 Metadata → Migration → Worker → projection state → 查询切换与 downgrade 边界。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；真实 182 万性能仅在用户离线包测试后验收。

# 完成证据与状态

## 新鲜证据

尚未执行；实现后补当前分支 HEAD 的命令、环境、结果和证明范围。

## 未验证内容与剩余风险

- 当前没有生产数据库访问权，无法在本地证明 182 万规模的最终耗时。
- 用户本地离线包构建和服务器运行验收尚未执行。

## 交付状态

- 分支：`fix/voice-plaza-projection-backfill-indexes`。
- 提交 / PR：尚未创建。
- 合并：按用户要求暂不合并 `main`。
- 发布 / 部署：不在本次执行范围。
