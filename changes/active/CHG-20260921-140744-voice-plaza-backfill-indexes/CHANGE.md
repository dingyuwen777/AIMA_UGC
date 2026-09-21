---
schema: coding-change/v1
id: CHG-20260921-140744-voice-plaza-backfill-indexes
title: 声音广场读模型回填索引与超时整改
level: L3
status: ready_for_review
owner: codex
branch: fix/voice-plaza-projection-backfill-indexes
created: 2026-09-21
updated: 2026-09-21
completion_gate: required
depends_on: []
affected_areas:
  - content
  - product
  - frontend
  - collection
  - ingestion
  - jobs
  - database
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/collection/candidate_tables.py
  - backend/src/aima_ugc/modules/ingestion/historical_tables.py
  - backend/src/aima_ugc/bootstrap/voice_plaza_projection_worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_product.py
  - backend/src/aima_ugc/bootstrap/product_http.py
  - frontend/src/features/voice-plaza/
  - migrations/versions/
  - tests/
  - docs/operations/04_声音广场读模型回填与性能验证.md
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/04_后端任务API与前端.md
  - backend/src/aima_ugc/modules/content/README.md
  - frontend/README.md
contracts:
  - content.voice-plaza-projection-backfill.v1
data_changes:
  - processing_import_batch_items
  - collection_candidate_ingestions
---

# 变更摘要

- **要解决的问题**：真实 1,823,565+ 数据环境中，声音广场投影回填单次 Attempt 运行数小时后超时，投影始终未进入 `ready`，列表、筛选、加载更多和详情继续走旧查询。
- **已实施修改**：为两类来源账本增加按 `content_id` 反查的部分索引，为每个回填批次设置短于 Job Deadline 的 PostgreSQL 语句与事务超时并记录安全批次日志；投影就绪后，后台 Count 在窄投影上复用列表筛选返回精确总数，页面把总数与当前已加载数分开显示。
- **预期结果**：回填不再对历史账本重复做无索引扫描，也不会在单条 SQL 卡住时占用 Worker 数小时；投影可持续推进并最终切换读取路径，筛选区不再用首屏或已加载页数冒充匹配总数。
- **追加用户要求**：声音广场筛选区下方显示当前已应用筛选命中的总数据量，不得再用当前已加载页数冒充总数；总数仍异步读取，不能阻塞最新倒序第一页。

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

- [x] Metadata 与 Alembic head 同时包含两张来源账本的 `content_id IS NOT NULL` 部分索引。
- [x] 单条 SQL 限制为 180 秒、整个批次事务限制为 240 秒；五批最坏事务上限低于 1800 秒 Job Attempt Deadline，超时复用现有 Retry。
- [x] 批次开始、完成和数据库失败均有安全结构化日志，可看到 generation、批次序号、处理量、进度和耗时。
- [x] Migration upgrade/downgrade、`alembic check`、目标单元测试和 PostgreSQL 集成测试通过。
- [x] 运维文档给出本地离线包部署后确认索引、投影进度、`ready` 切换和真实性能验收的方法。
- [x] 无筛选和任意已应用筛选都返回与列表语义一致的总数；页面明确区分“总数”和“当前已加载数”，且计数不阻塞第一页。

## 范围

- Collection/Ingestion 来源账本索引及新 Alembic Migration。
- 声音广场投影回填的单批语句超时和批次级安全日志。
- 对应单元、PostgreSQL 集成测试和运维说明。

## 非目标

- 不修改声音广场 HTTP Contract、筛选语义、排序或 Cursor。
- 不把总数计算并入列表请求，不因计数失败阻断第一页或加载更多。
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
2. 在每个回填短事务内用 PostgreSQL `set_config(..., true)` 分别设置 180 秒语句超时和 240 秒事务超时，确保五个批次的事务上限低于 1800 秒 Attempt Deadline。
3. 在现有统一日志中记录批次开始、完成和数据库错误，不输出 Content ID、正文或 SQL Payload。
4. 用 Metadata、Migration 往返、PostgreSQL 集成和日志回归证明索引与恢复语义。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：来源账本反查索引 | E3、E4 | 直接切断已确认的大表无索引反查，不增加新基础设施 |
| D2：语句与批次事务双重超时 | E2 | 单条 SQL 与整个事务分别有界，即使仍有数据库异常，也能在 Deadline 前回到 Job Retry，而不是卡到重启 |
| D3：批次级安全日志 | E2 | 让服务器测试能区分索引无效、锁等待和批次推进 |

## 备选方案与取舍

- 只缩小 batch：仍会重复无索引扫描，只是单次扫描数量变少，不能修根因。
- 只提高 Job timeout：延长卡死时间，不能让 Handler 有界返回。
- 引入额外进程或缓存：不解决来源账本反查与回填 SQL，增加一致性和运维成本。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 读模型可分片回填、可观察且可安全回滚 | #551 / AC7 | satisfied | Migration `0055`、双重超时、批次日志、迁移往返与真实 PostgreSQL 回填测试均通过 |
| R2 | 在真实服务器完成列表、筛选、详情和评论性能验收 | #551 / AC8 | explicitly_deferred | 用户明确先在本地构建离线包测试；本 Change 已修复阻塞回填并同步验收手册，不伪造 182 万规模结论 |
| R3 | 按确认方案修改但暂不合并主分支 | user:2026-09-21#AC1 | satisfied | 实现保留在本地 `fix/voice-plaza-projection-backfill-indexes`，未 push、未建 PR、未合并 `main` |
| R4 | 筛选区域下方显示当前筛选命中的全部数据量；无筛选时显示全部可见数据量 | user:2026-09-21#AC2 | satisfied | 投影精确 Count 复用列表筛选；页面显示“共 N 条 / 当前已加载 M 条”；PostgreSQL、Store 与 Playwright 回归通过 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Collection/Ingestion tables | 增加部分索引 Metadata | 防止来源可见性反查大表扫描 | R1 / E3 |
| `migrations/versions/20260921_0055_*` | 创建/删除索引 | Schema 单一事实与安全回滚 | R1 |
| `voice_plaza_projection_worker.py` | 语句超时和批次日志 | 避免数小时卡死并支持定位 | R1 / E2 |
| Content Query/Product Service | 投影 ready 后按当前筛选精确计数，升级窗口保留明确标注的无筛选估算 | 既满足总数语义，又不把 Count 并入首屏列表 | R4 |
| Voice Plaza Store/Page | 筛选切换立即使旧总数失效，异步加载新总数并区分已加载数 | 防止旧筛选或分页条数冒充当前总数 | R4 |
| Content unit/integration tests | Metadata、超时、日志和 Migration 回归 | 证明真实 PostgreSQL 边界 | R1 |
| Frontend unit/E2E | 当前筛选请求、旧总数失效和百万级格式化展示回归 | 证明用户可见行为 | R4 |
| 运维文档 | 同步索引、超时和验收方法 | 支持用户离线包验证 | R2 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档
- [x] 取得仍覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Metadata 索引、批次超时和日志字段回归 |
| 接口 / 契约 | required | HTTP 字段不变；`estimated` 请求可返回质量更高的 `count_kind=exact`，由现有 Contract 与 Contract 测试覆盖 |
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

- [x] upstream_re_read：已重新读取 Issue #551、用户本轮决定和正式项目文档，并独立重建完成定义。
- [x] change_coverage：已确认当前变更覆盖全部上游要求，没有把变更自身当作需求全集；新增总数要求已从页面反查到 Count Service 与投影筛选，真实服务器性能验收按用户决定显式延期到离线包测试。
- [x] reverse_audit：已复核 Metadata → Migration → Worker → projection state → 列表/Count 查询切换与 downgrade 边界；审查中发现单独 `statement_timeout` 不能约束整个批次，已增加 PostgreSQL 18 `transaction_timeout`；又发现筛选提交到新 Count 启动之间可能短暂保留旧总数，已在 Store 提交筛选时立即失效旧值并重验。
- [x] unresolved_cleared：所有 `not_satisfied` 已清零；真实 182 万性能仅在用户离线包测试后验收。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明范围 |
| --- | --- | --- | --- | --- |
| V1 | Red `66cdc8c6` / Windows / Python 3.14 | `pytest tests/unit/content/test_voice_plaza_read_model.py tests/unit/content/test_voice_plaza_projection_worker.py -q` | 3 failed、4 passed；缺少两个索引、超时设置和失败日志 | 修复前缺陷可复现，失败原因与目标一致 |
| V2 | `536c413e` / Windows / Python 3.14 | `pytest tests/unit/content -q -p no:cacheprovider` | 35 passed | Content 单元回归、索引 Metadata、180/240 秒双重超时和安全日志成立 |
| V3 | `536c413e` / PostgreSQL 18.4 一次性无数据卷容器 | `test_0055_creates_and_drops_voice_plaza_source_lookup_indexes`；`alembic upgrade head`；`alembic check` | 迁移往返 1 passed；自动差异清零 | `0054 → 0055` 可建索引、可回滚且 Metadata/DDL 一致 |
| V4 | `536c413e` / PostgreSQL 18.4 一次性无数据卷容器 | `test_voice_plaza_projection_backfill_switches_reads_to_ready_catalog` | 1 passed | PostgreSQL 18 接受事务超时；生产 Job 链能从 pending 回填到 ready 并切换列表/目录读取 |
| V5 | `536c413e` / Windows | 变更文件 `ruff format --check`、`ruff check`；`mypy backend/src` | 通过；350 个源码文件无类型错误 | 格式、静态规则和生产源码类型正确 |
| V6 | `536c413e` / Windows | `check_architecture.py`、`check_table_ownership.py`、`check_docs.py`、`check_docs_facts.py` | 全部通过 | 模块 Owner、文档链接与长期事实同步 |
| V7 | `d60ff6fa` / Windows / Python 3.14 | `pytest tests/unit/content -q`；`pytest tests/contracts/test_u1_u5_contracts.py -q`；`mypy backend/src` | 36 passed；9 passed；350 个源码文件无类型错误 | 投影 Count SQL 不重建窗口，Count Contract 与生产类型保持兼容 |
| V8 | `d60ff6fa` / PostgreSQL 18.4 一次性无数据卷容器 | `test_voice_plaza_projection_backfill_switches_reads_to_ready_catalog` | 1 passed | 回填 ready 后无筛选返回精确 2，平台 + 文本筛选返回精确 1，且列表结果一致 |
| V9 | `d60ff6fa` / Windows / Chrome | Voice Plaza Vitest；目标 Playwright；ESLint；TypeScript/Vue typecheck；生产构建 | 31 passed；1 passed；Lint/类型检查通过；Vite build 成功 | 已应用筛选参与 Count、旧总数立即失效，页面展示 `共 1,823,565 条 / 当前已加载 3 条`，可生产构建 |
| V10 | `d60ff6fa` / Windows | `check_architecture.py`、`check_table_ownership.py`、`check_docs.py`、`check_docs_facts.py` | 全部通过 | 新计数调用链、模块 Owner 与定向文档同步 |

## 未验证内容与剩余风险

- 当前没有生产数据库访问权，无法在本地证明 182 万规模的最终耗时、P50/P95 或实际建索引时长。
- 精确筛选总数仍需扫描投影中命中的索引范围；它与首屏列表独立，不阻塞第一页，但 182 万规模下的实际 Count 耗时和并发资源占用仍需用户离线包环境日志验证。
- 用户本地离线包构建和服务器运行验收尚未执行。

## 交付状态

- 分支：`fix/voice-plaza-projection-backfill-indexes`。
- 提交：Red 基线 `66cdc8c6`；回填实现、测试与文档 `536c413e`、`8bf09805`；筛选总数实现与回归 `d60ff6fa`。
- PR：按用户“先不用合并主分支”的本地测试边界未创建，也未推送远程分支。
- Review：已审查 Migration、调用链、超时、Fencing/Heartbeat、日志安全、Count/列表筛选一致性、筛选竞态和回滚；事务总时长与旧筛选总数短暂残留问题均已修复并重验，当前无剩余阻塞 Finding。
- 合并：按用户要求暂不合并 `main`。
- 发布 / 部署：不在本次执行范围。
