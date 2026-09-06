# 4000 万历史迁移与 Analysis Run 运行手册

本文负责**当前已经实现的软件怎样安全运行、排障和进入生产 Go/No-Go**。软件能力已完成；公司服务器容量门禁、生产写授权、正式 4000 万执行与全量对账仍未完成，当前状态见 [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../roadmap/03_4000万历史数据迁移实施方案.md)。

精确字段以 Pydantic Contract、SQLAlchemy Table、Alembic Migration 和生成 OpenAPI/Client 为准；本文不复制第二套 Schema。

---

## 1. 一个入口承载两种来源和两种策略

采集运行中心只有一个用户可见“导入数据”入口：

```text
本地电脑
→ 多选 .xlsx，或显式选择文件夹
→ 浏览器只提交用户选择范围内的相对路径和文件字节

服务器目录
→ 只枚举管理员批准、只读挂载的服务器根目录
→ Worker 快照所选相对路径为 Source Artifact

两种来源
→ 同一个 Data Import Campaign
→ 不可变 Artifact / SHA-256 / 全量预检 / 有界 Chunk
→ 用户显式开始
→ PostgreSQL Durable Job
→ 逐行或区间终态账本
```

来源与写入策略相互独立：

```text
source_kind
→ local_upload
→ server_path

ingestion_policy
→ standard_observation
→ historical_fill_only
```

`standard_observation` 使用普通字段新鲜度、Version 与可信 Metric 语义；`historical_fill_only` 使用“只补空、不覆盖已有非空 Current、冲突留痕、无可信时间不更新 Metric”的历史迁移语义。

两维必须在 Campaign 创建时分别选择并冻结；来源不能静默决定写入策略。页面可以给本地来源和服务器来源不同初始建议，但用户在创建前可以显式修改。

旧 `/api/v1/import-batches` 和 `/api/v1/historical-import-*` 继续承担兼容，不作为页面平行入口。数据库表和 Job type 中保留 `historical_*` 物理名称也不表示存在第二套业务系统。

**4000 万容量门禁只适用于 `server_path + historical_fill_only`。** `standard_observation` 虽复用 Campaign/Chunk/账本，但不能据此声称具有同等 4000 万吞吐能力。

---

## 2. 服务器目录安全边界

源码开发时，批准根由本地配置提供；完整 Compose 中，宿主配置：

```text
AIMA_HISTORICAL_IMPORT_HOST_ROOT
```

并只读挂载到 API/Worker 的固定容器路径。应用只接收和返回批准根下的相对路径，拒绝：

- 绝对路径；
- `..` 路径逃逸；
- 混合分隔符绕过；
- Symlink/Junction/Reparse Point；
- 上传、删除、移动、改名或下载服务器源文件。

当前已经存在 Provider-neutral `Principal/AuthContext` 和后端角色授权守卫；默认开发装配仍使用 `DevelopmentIdentityResolver`，把请求解析为固定开发 Principal，**这不是企业真实 Authentication**。扩大网络范围或把这些管理端点作为完整 Production 能力前，必须先完成真实企业身份接入、Principal 映射、Session/Claims 生命周期、对象级授权和安全验收。

目录 HTTP 分页只限制单页返回量；当前目录实现仍可能先读取并稳定排序目标目录的直接子项再截取。因此批准根应是专用、层级清晰、单目录规模受控的迁移目录，不应直接暴露拥有海量直接子项的通用共享盘根目录。

---

## 3. Campaign 状态与调用链

主要 HTTP：

```text
GET  /api/v1/data-import-sources/server/directories
POST /api/v1/data-import-campaigns/server
POST /api/v1/data-import-campaigns/local
PUT  /api/v1/data-import-campaigns/{campaign_id}/items/{item_id}/content
POST /api/v1/data-import-campaigns/{campaign_id}/finalize
GET  /api/v1/data-import-campaigns
GET  /api/v1/data-import-campaigns/{campaign_id}
GET  /api/v1/data-import-campaigns/{campaign_id}/items
GET  /api/v1/data-import-campaigns/{campaign_id}/conflicts
POST /api/v1/data-import-campaigns/{campaign_id}/start
POST /api/v1/data-import-campaigns/{campaign_id}/cancel
POST /api/v1/data-import-campaigns/{campaign_id}/retry-failed
```

服务器来源创建 Campaign 后建立 Discover Job；本地来源先进入 `uploading`，文件上传完成后 `finalize` 建立 Snapshot Job：

```text
uploading（仅本地）
→ Source Artifact 绑定
→ finalize
→ discovering / snapshotting
→ 不可变 Source Artifact + SHA-256
→ 流式读取 XLSX
→ 有界 gzip JSONL Chunk Artifact
→ 全量预检成功
→ ready
→ start
→ 低优先级 Chunk Job
→ succeeded / failed / cancelled 等终态
```

只有 `ready` 才允许 `start`。

本地重复 PUT 会核对冻结文件事实和 SHA-256，不能用不同内容静默复用 Item。服务器源文件快照完成前后必须复核 Manifest/Hash，源文件在发现到快照期间变化时 Campaign 失败为 `historical_source_changed`，不能把不同版本混入同一冻结输入。

导入阶段按冻结的 `chunk_rows` 和 `max_in_flight_jobs` 有界调度。不同文件可以并行；同一文件保持稳定 Chunk 顺序，避免跨 Chunk 的首行身份顺序漂移。取消、人工重试、Lease 接管和终态回调继续复用 PostgreSQL Job Runtime 的 Lease/Fencing/Deadline 语义。

页面运行中只轮询 Campaign 汇总，不重复读取全部 Chunk。Item/冲突页面可以是有界预览；完整逐行事实仍以 PostgreSQL 账本为准。

---

## 4. Historical Fill-Only 的写入语义

本节只适用于：

```text
ingestion_policy=historical_fill_only
```

历史行命中同一 `(platform, external_content_id)` 时：

| 当前事实 | 历史输入 | 处理 |
| --- | --- | --- |
| 实体不存在 | 合法非空事实 | 创建实体和初始 Version |
| Current 字段为空 | 历史值非空 | 只补齐该字段 |
| Current 字段非空 | 历史值相同 | 不改 Current，不推进 freshness/`last_seen_at` |
| Current 字段非空 | 历史值不同 | 保留 Current，写冲突账本 |
| 历史值为空 | 任意 | 不清空 Current |

没有可信来源观测时间的历史 Metric 不得伪造成当前 Observation，也不得据此覆盖 Current Metric。

已经进入 Chunk 业务事务的源行最终进入一个适用 outcome：

```text
created / filled / updated / unchanged / conflict /
filtered / duplicate / invalid / failed
```

其中 `updated` 主要属于 `standard_observation`；`historical_fill_only` 不得借该状态覆盖已有非空事实。

业务写入、逐行账本与 Chunk 成功终态需要保持原子性。尚未进入业务事务的整段失败/取消范围由不可变 Chunk 的 `row_start / row_end / row_count + terminal status` 形成区间终态，不为从未处理的行伪造成功账本。

同一 Chunk 技术重试必须幂等；人工重试失败 Chunk 也不能让之前成功范围再次产生业务副作用。

---

## 5. 手动 AI Analysis Run

历史导入**不会自动创建 AI Job**。用户在声音广场显式发起：

```text
POST /api/v1/analysis/content-runs/preview
→ 返回目标数量、Shard 计划和当前配置身份
→ 当前没有可靠费用事实时不伪造费用估算
→ 用户确认
POST /api/v1/analysis/content-runs
```

当前正式 `AnalysisRunTargetSelection` 支持两种范围：

```text
selected
→ 显式提交 1—1000 个 content_id

all
→ 不提交 content_id
→ 目标为数据库当前全部 Content Current
```

`all` 不是“当前页面已加载内容”，也不受前端当前筛选影响。前端只提交正式 Contract，不先翻页收集全部 ID。

创建 Run 时保存 Run Header 与 `analysis.content-run-plan.v1` Planner Job。Planner 根据 Run 冻结的目标范围和配置身份，把目标冻结为 `Content ID + Content Version`，再以有界窗口创建 `analysis.content-label.v1` Shard。Planner/Shard 的重试必须复用已经提交的冻结事实，不重复产生业务副作用。

兼容入口 `POST /api/v1/content-analysis-requests` 继续承担旧 Request Contract；新声音广场使用 Analysis Run + Planner 链。两者不能被解释成两套不同 Analysis 事实系统。

不同 Run 对同一 Content Version 的结果全部保留。Current 结果按当前正式 Run 顺序规则选择，不按 Worker 完成先后让较早用户意图覆盖较晚 Run。最新 Run 失败或取消时，旧成功结果仍可保留，同时页面单独显示最新 Run 状态。

Worker 在调用 LLM 前会校验 Run 冻结的 Prompt/Taxonomy/Provider/Model/生成配置身份；身份漂移时必须失败关闭，不能继续调用模型后把结果写成该 Run 的合法结果。

当前 Shard Size、最大 in-flight Job 等精确运行参数直接看代码/配置，不在运行手册复制第二套默认值。显式 `selected` 的 1000 条上限来自 Pydantic/OpenAPI Contract；`all` 不受这个显式 ID 数量上限约束，但仍由 Planner/Shard 有界处理。

---

## 6. 容量验证怎么执行

容量入口：

- [`scripts/performance/benchmark_stage12_historical.py`](../../scripts/performance/benchmark_stage12_historical.py)

脚本只允许使用专用容量数据库，生成测试 XLSX 并调用生产 Campaign/API/Artifact/Chunk/Worker/Content Owner；它不是裸 SQL benchmark。

容量报告至少需要记录：

- 硬件与 PostgreSQL 配置；
- 文件数、行数与真实/代表性分布；
- 阶段吞吐和总耗时；
- Chunk P50/P95；
- CPU/RSS；
- PostgreSQL/表/Artifact/WAL/临时文件增长；
- 锁等待和查询延迟；
- 逐行/区间对账；
- 普通 Job 饥饿探针。

本地已有容量实验只能作为软件基线证据，**公司服务器 500 万或业务 Owner 批准的等效比例演练仍是生产前门禁**。未形成完整报告的中断实验不能写成通过。

---

## 7. 生产 4000 万 Go/No-Go

开始生产写入前必须另行批准，并至少满足：

- 真实输入完成只读剖析，明确文件/行数、平台/ID、重复、过滤、无效和冲突分布；
- 公司服务器完成 500 万或批准的等效比例容量演练；
- 根据真实分布校正时间、PostgreSQL、Artifact、临时盘和 WAL 预测；
- 全量后仍保留业务 Owner 批准的安全余量；
- 可用备份事实、恢复验证、维护窗口、负责人、暂停条件和失败处置已批准；
- 生产 Release/SHA、配置和 Campaign Manifest 冻结；
- 普通 Job 不存在不可接受的持续饥饿；
- 已获得**独立生产写授权**。

当前完整协调 Backup/Restore 尚未闭环，因此“软件能导入”不等于“生产 4000 万可以 Go”。

执行完成后必须做全量对账：Manifest 行数、逐行/区间终态、冲突/失败、Content/Author 保护规则、Artifact、数据库/WAL 增长和业务查询结果都要能回溯到 Campaign。

代码回滚只停止后续应用行为，不自动删除已经写入的历史事实；如需数据补偿，必须基于 Campaign 账本另建高风险 Change。

---

## 8. 排障顺序

### Campaign 卡住

```text
historical_import_campaigns
→ historical_import_campaign_items
→ jobs / job_attempt_events
→ artifacts
→ processing_import_batches
→ processing_import_batch_items
→ worker.log
```

### Analysis Run 卡住

```text
analysis_content_runs
→ analysis_content_run_targets
→ analysis_content_requests / request_items
→ jobs
→ analysis_content_results
→ worker.log / LLM 调用审计
```

不要手工 UPDATE 状态或删除账本“解卡”。先确认 Job Lease、Fencing Token、Attempt Deadline、error_code、Artifact 完整性和正式取消/重试入口。

---

## 9. 精确事实源

### HTTP

- [`backend/src/aima_ugc/contracts/http.py`](../../backend/src/aima_ugc/contracts/http.py)
- [`contracts/openapi/openapi.json`](../../contracts/openapi/openapi.json)
- [`frontend/src/generated/api/`](../../frontend/src/generated/api/)

### Schema

- [`backend/src/aima_ugc/modules/ingestion/historical_tables.py`](../../backend/src/aima_ugc/modules/ingestion/historical_tables.py)
- [`backend/src/aima_ugc/modules/analysis/tables.py`](../../backend/src/aima_ugc/modules/analysis/tables.py)
- [`migrations/versions/`](../../migrations/versions/)

### Worker / Repository

- [`backend/src/aima_ugc/bootstrap/historical_import_worker.py`](../../backend/src/aima_ugc/bootstrap/historical_import_worker.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/analysis.py)

### 测试与生产门禁

- `tests/**/test_stage12_*.py`
- [`frontend/e2e-fullstack/stage12-historical-analysis.spec.ts`](../../frontend/e2e-fullstack/stage12-historical-analysis.spec.ts)
- [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../roadmap/03_4000万历史数据迁移实施方案.md)
