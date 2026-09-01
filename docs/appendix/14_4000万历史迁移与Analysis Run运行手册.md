# 4000 万历史迁移与 Analysis Run 运行手册

本文说明 Stage 12 当前软件能力、实际调用链、运行边界和全量执行门禁。精确字段以 Pydantic Contract、SQLAlchemy Table、Alembic Migration 和生成 OpenAPI/Client 为准；本文不复制第二套 Schema。

---

# 1. 一个入口怎样承载两种来源和两种策略

采集运行中心现在只有一个“导入数据”入口：

```text
本地电脑
→ 多选 .xlsx，或显式选择文件夹并由浏览器递归列出其中全部 .xlsx
→ 冻结相对路径 + byte_size 清单
→ 逐 Item 流式上传为 Source Artifact

服务器目录
→ 网页只枚举管理员批准的只读服务器根目录
→ Worker 快照所选相对路径为 Source Artifact

两种来源
→ 同一个 Data Import Campaign
→ SHA-256 + 全部预检 + 有界 Chunk
→ 用户显式开始
→ 低优先级持久 Job + 逐行终态账本
```

浏览器不会把本机绝对路径交给网页，也不允许网页在只选择一个文件后扫描父目录；需要自动遍历时必须点击“选择文件夹（自动遍历）”。服务器来源仍没有上传、删除、移动、改名或下载能力。

来源与写入策略相互独立：`standard_observation` 使用普通字段新鲜度、Version 和可信 Metric 语义；`historical_fill_only` 使用“不覆盖已有非空 Current、冲突留痕、无可信时间不更新 Metric”的方案 A。两者都冻结在 Campaign 中，不用全局开关。页面给本地来源初始建议标准观测、服务器来源初始建议历史补空，但用户可以在创建前显式修改。

旧 `/api/v1/import-batches` 和 `/api/v1/historical-import-*` 继续保留兼容，不再作为页面平行入口。数据库表和 Job type 的 `historical_*` 名称也为兼容保留。4000 万容量报告只适用于 `server_path + historical_fill_only`；标准观测路径虽然共用 Chunk/账本，但当前仍复用逐记录 Content Owner，不能按 4000 万吞吐能力使用。

---

# 2. 服务器目录安全边界

源码开发模式直接在 `env.local` 配置应用批准根：

```text
AIMA_HISTORICAL_IMPORT_ROOT=.runtime/historical-input
```

默认目录由 dev launcher 在仓库 `.runtime/` 下创建，相对路径按仓库根解析。如果改用其他绝对路径，该专用目录必须由管理员预先建立；配置变更后必须重启 Backend，因为 API 和 Worker 都在进程启动时读取同一根目录。

完整 Compose 运行时，管理员只配置宿主路径：

```text
AIMA_HISTORICAL_IMPORT_HOST_ROOT
```

Compose 将它只读挂载到 API/Worker 的固定容器路径：

```text
/data/aima-historical-input:ro
```

应用配置 `AIMA_HISTORICAL_IMPORT_ROOT` 固定指向该容器路径。HTTP 只接受和返回相对路径；目录实现拒绝绝对路径、`..`、混合分隔符、根目录逃逸以及 Symlink/Junction/Reparse Point。页面没有上传、删除、移动、改名或下载服务器源文件的能力。

当前系统尚未接入 Authentication/Authorization，因此所有能访问内网页面的客户端都能调用这些管理端点。扩大网络范围前，认证授权仍是独立 L3 前置门禁。

目录分页只限制 HTTP 单页返回量；当前实现仍会先读取并稳定排序目标目录的全部直接子项，再截取当前页。因此批准根目录应是专用于历史迁移、层级清晰且单目录子项数量受控的只读目录，不应把拥有海量直接子项的通用共享盘根目录直接暴露给应用。递归创建 Campaign 仍受 `max_files` 和 `max_depth` 约束；如果真实服务器目录的单层规模超过当前可接受范围，应先整理目录或另建公共 Contract/容量决策，不能把分页误解为目录扫描本身恒定内存。

---

# 3. Campaign 的状态和调用链

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

服务器来源创建 Campaign 后，HTTP 建立父事实和 Discover Job；本地来源先建立 `uploading` Campaign 与冻结 Source Item 清单，逐项上传完毕后调用 finalize 建立 Snapshot Job：

```text
uploading（仅本地）
→ 全部 Source Artifact 已绑定
→ finalize

discovering
→ 目录发现
→ source_file Item
→ 原文件 Artifact 快照 + SHA-256
→ 流式读取 XLSX
→ 有界 gzip JSONL Chunk Artifact
→ 全部文件预检成功
→ ready
```

只有 `ready` 才允许 `start`。本地上传会核对冻结文件名和大小；重复 PUT 还会流式核对 SHA-256，不会用不同内容静默复用 Item。Source Item 关系与 Artifact `linked` 状态同事务提交。服务器源文件复制并完成前后 Manifest/SHA-256 校验后，同一快照 Job 的瞬时 I/O 重试直接复用该不可变 Artifact，不会再次复制服务器源文件。Artifact 已写入但业务事务失败的窄窗口，以及 Chunk 发布前的同类窗口，会按未引用 Artifact 的孤儿规则在 1 天后由现有清理任务回收；已被 Campaign Item 引用的 Source/Chunk 不进入该规则。

导入阶段按冻结的 `chunk_rows` 和 `max_in_flight_jobs` 调度低优先级 Job；不同源文件可以并行，但同一源文件任一时刻只调度最早的一个 ready Chunk，从而在不把全文件装入内存的前提下保证跨 Chunk 的稳定首行胜出。正常 Job 仍由 PostgreSQL Job Runtime 按 priority 优先认领。取消、人工重试、Lease 过期接管和终态回调都复用同一 Job/Fencing 机制；排队 Job 被取消时，Repository 会同步把对应 Item 和 Campaign 收敛到终态，不等待一个永远不会执行的 Worker 回调。

页面使用后端 Cursor 继续加载服务器目录项，可以选择单个文件，也可以选择目录后让 Campaign 在批准上限内递归发现。本地来源可多选文件或使用文件夹选择器。Campaign 列表保留在同一对话框中，刷新页面后仍可重新打开长期运行任务；两种来源都只在 HTTP Contract 中暴露相对路径。运行中每秒轮询只读取 Campaign 汇总，不重复拉取全部 Chunk。Item 明细固定有界返回最需要处置的前 200 条，按 failed/cancelled/running/queued 优先；冲突预览固定有界返回前 500 条，响应同时给出 `total_count/has_more`，不会把截断伪装成完整清单。完整逐行事实仍以数据库账本为准。

Campaign 汇总中的 `progress` 是可从数据库恢复的事实，不依赖浏览器本地计时：

- `discovering` 时文件总数未知，页面显示不确定进度，不显示 `0%` 等伪精确数字；
- 预检百分比按所有 Source Item 聚合；`snapshotting` 使用对应持久 Snapshot Job 的进度，Source 到达后续状态后该文件预检记为完成；
- 迁移完成行数是状态为 `succeeded / failed / cancelled` 的 Chunk `row_count` 之和，百分比以冻结的 Campaign 总行数为分母；一次 Chunk 事务提交后进度按该 Chunk 行数前进；
- 失败和取消表示该范围已经取得可对账终态，不表示业务成功，必须结合 Campaign 状态、outcome 统计和失败明细判断结果。

同一套可访问进度条还用于声音广场的 Analysis Run、Excel Export Job 和 Collection Scope。Analysis Run 列表本身不展开全部 Shard；页面只为活动 Run 补读现有详情，并以冻结的 Run 总目标数为分母计算 `Shard target_count × progress`，尚未进入有界调度窗口的目标按 0% 计算，避免新 Shard 出现后百分比倒退。普通 Excel Import 与 Collection Run 原有总进度条保持不变；短同步请求或无法确定总量的发现阶段只显示加载/不确定状态。

源文件从发现到快照之间若大小、修改时间或内容哈希变化，Campaign 关闭失败为 `historical_source_changed`，不会把变化后的文件混进已冻结输入。

数据库对 source_file 使用 `campaign_id + relative_path + manifest_identity` 的条件唯一索引；因为 source_file 的 `ordinal` 为空，该约束不能只依赖包含 `ordinal` 的普通唯一约束。即使并发发现或重试穿过应用层检查，数据库也不会为同一 Campaign、路径和 Manifest 建立两个源文件事实。

---

# 4. Historical Fill-Only 的精确业务语义

本节只适用于 Campaign 明确冻结 `ingestion_policy=historical_fill_only` 的情况。选择本地或服务器来源不会自动启用它。`standard_observation` 仍由 `ContentIngestionService + PostgresCompleteContentRepository` 执行普通字段新鲜度、Version 与可信 Metric 行为，并在逐行账本中使用 `created / updated / unchanged` 等适用终态；该路径未通过 4000 万容量验证。

历史行命中同一 `(platform, external_content_id)` 时使用方案 A：

- Current 为空、历史值非空：补入并在需要时创建 Content Version；
- Current 非空且值相同：不写；
- Current 非空且值不同：不覆盖，写稀疏冲突账本；
- 历史值为空：不清空 Current；
- `unchanged/conflict` 不推进字段新鲜度或 `last_seen_at`；
- 没有可信 Metric 观测时间时不更新 Content 或 Author 的 Current Metric，也不伪造 Observation；历史 Excel 中的粉丝数、关注数、作品数和获赞数不会被当作普通 Author 字段补入 Current。

规则覆盖当前输入实际承载的 Content、Author 和扩展 ID。每个源行最终进入且只能进入一个 outcome：

```text
created / filled / unchanged / conflict /
filtered / duplicate / invalid / failed
```

`processing_import_batch_items` 是已进入 Chunk 业务事务的紧凑逐行终态账本；字段冲突单独进入稀疏冲突表，只保存定位和安全哈希，不复制完整正文。业务写入、逐行账本和 Chunk `succeeded` 在同一事务提交。结构失败或取消、尚未进入该事务的整段行，以不可变 Chunk 的 `row_start/row_end/row_count + failed/cancelled` 作为区间终态，并计入 Campaign/Batch 的 `failed`，所以每一输入行仍可定位和对平，但不会为未处理的 4000 万行批量伪造逐行记录。

相同 Chunk 技术重试先命中已有终态行，不再产生第二次业务副作用。人工重试失败 Chunk 时，新 Batch 会通过集合式数据库写入继承前一 Batch 已提交的身份集合；因此先前成功 Chunk 已认领的身份在失败区间重跑时仍判为 `duplicate`。重试成功后，该 Chunk 区间由真实逐行 outcome 替代失败区间统计。

历史 Chunk 的 Provider Request/Attempt 身份由 `Import Batch + Platform + 不可变 Chunk Artifact` 确定。同一 Chunk 重试复用身份，不同 Chunk 不会因请求参数哈希不同发生幂等冲突。

---

# 5. 手动 AI Analysis Run

历史导入不会自动创建 AI Job。用户在声音广场发起时，页面先请求后端预检：

```text
POST /api/v1/analysis/content-runs/preview
→ 返回目标数、Shard 数、Prompt/Taxonomy/Model/生成配置身份
→ 当前没有可靠 tokenizer/定价事实时明确“不提供费用估算”
→ 用户显式确认
POST /api/v1/analysis/content-runs
```

新版创建 HTTP 只接受显式选择的 1—1000 个 Content ID，并在一个短事务内保存 Run 头和 `analysis.content-run-plan.v1` Planner Job。Planner 随后在数据库事务内按 Run 保存的 ID 集合和配置身份执行 `INSERT ... SELECT`，冻结全部 `Content ID + Version`，校验数量仍等于 Preview，并以有界窗口创建 `analysis.content-label.v1` Shard。数量变化时整次冻结回滚，Run 以 `content_analysis_target_changed` 失败，不留下部分 Target；该 Planner 终态错误会随 Run 查询返回并在声音广场展示。Planner 在 Lease 重试时先核对已冻结数量并复用已经提交的 Target/Shard，不重复产生业务副作用。

兼容入口 `POST /api/v1/content-analysis-requests` 仍可读取原有 selected/query 目标语义，并在 HTTP 内同步冻结目标、创建首个 Shard，以保持既有 Response 中 `request_id/job_id` 的行为；新声音广场使用仅 selected 的异步 Planner 链路。客户端幂等键绑定目标快照、预检数量、配置哈希和运行意图；同键不同请求返回冲突。查询范围新版 Run 在真实付费模型 Gold Set、费用和容量报告完成前不开放。

不同 Run 对同一 Content Version 的 Result 全部保留。Current 只按用户创建 Run 的数据库 `sequence_no` 选择最新成功结果，不按 Worker 完成时间，也不因当前进程模型配置变化而改写；最新 Run 失败或取消时，旧成功结果继续展示，同时 API 单独返回最新 Run 的状态。

Worker 每批调用 LLM 前会把实际 Service 的 Prompt/Taxonomy/Provider/Model 身份和当前实际生成配置 Hash，与 Run 在数据库中冻结的身份比较。部署、重启或配置变更造成不一致时，Shard 以 `analysis_run_configuration_changed` 失败关闭，不调用 LLM、不写入 Result；Result 持久化还会再次校验身份，防止绕过执行前检查。0027 只能从已有 Result 尽量推断旧 Prompt/模型身份，无法还原任何旧 Request 的实际 generation config，因此所有 `legacy-request:*` 回填 Run 都保留显式兼容例外；新建 Run 始终严格执行冻结校验。

当前配置：

```text
AIMA_ANALYSIS_RUN_SHARD_SIZE=1
AIMA_ANALYSIS_RUN_MAX_IN_FLIGHT_JOBS=2
新版 Run 最大显式选择数=1000（Pydantic/OpenAPI Contract）
```

Shard=1 和“仅显式选择最多 1000 条”都是尚未执行真实付费 Gold Set 批量质量/费用/容量基准前的保守门禁。不得只为吞吐静默放大，也不得绕过页面直接提交 query scope；固定模型/Prompt/生成配置的真实质量、跨条污染、JSON 有效率、延迟、token 和成本报告完成后才能重新决策。

---

# 6. 容量基准怎样运行

容量脚本：

- [`scripts/performance/benchmark_stage12_historical.py`](../../scripts/performance/benchmark_stage12_historical.py)

它只允许 `AIMA_DB_NAME` 以 `_stage12_capacity` 结尾，并在该专用库内清理上一阶数据。脚本生成 write-only XLSX Fixture，随后调用生产 Campaign/API/Artifact/Chunk/Worker/Content Owner，不是裸 SQL 吞吐脚本。报告记录：硬件和 PostgreSQL 配置、文件/行数、阶段吞吐、Chunk P50/P95、峰值 RSS/CPU、数据库/表/Artifact/WAL/临时文件、锁等待、查询延迟、对账和普通 Job 饥饿探针。

测试示例：

```powershell
$env:AIMA_DB_NAME='aima_ugc_stage12_capacity'
uv run python scripts/performance/benchmark_stage12_historical.py `
  --work-dir .runtime/stage12-capacity/100k `
  --rows 100000 `
  --rows-per-file 100000 `
  --chunk-rows 1000 `
  --max-in-flight 2
```

工作目录必须为空；每个阶梯使用新的目录。报告为 `capacity_report.json`。开发/测试脚本绝不能指向生产数据库，也不授权真实 4000 万写入。

本轮 10 万与 100 万合成“全新、全相关、无冲突”的最大全量新增路径均已通过并逐行对平，本机开发验收上限按业务 Owner 决定固定为 100 万。第一次 500 万尝试在 399.7 万行后因本机磁盘耗尽而中断，并暴露频繁 Checkpoint 风险；第二次重跑在 82.1 万行、0 个失败 Chunk 时由业务 Owner 主动中止。两次均没有完成报告，不得写成 500 万通过。500 万或经业务 Owner 批准的等效比例演练延期到公司服务器生产前执行。合成 Fixture 不能替代公司服务器硬件和真实 Excel 分布复测，也不能单独完成生产 Go/No-Go。

---

# 7. 全量前 Go/No-Go

生产 4000 万开始前必须另行批准，并至少确认：

- 真实输入只读剖析已取得文件大小、行数、平台/ID、重复、过滤、无效和冲突分布；
- 本机 10 万→100 万报告已复核；公司服务器完成 500 万或经业务 Owner 批准的等效比例演练，并用真实分布校正 4000 万时间/存储/WAL 预测；
- PostgreSQL、Artifact、临时盘和 WAL 预计全量后仍保留批准的至少 30% 安全余量；
- 可用备份事实、恢复验证、维护窗口、负责人、暂停条件和失败处置已批准；
- 已有非空字段覆盖数为 0，逐行终态总和与 Manifest 行数相等；
- 普通 Job 没有不可接受的持续饥饿；
- 生产 Release/SHA、配置和 Campaign Manifest 已冻结。

当前完整协调 Backup/Restore 仍未闭环，因此软件功能完成不等于生产迁移 Go。代码回滚只停止新 Campaign/Run，不自动删除已经填入的历史值；任何数据补偿都必须依据 Campaign 账本建立独立 Change。

---

# 8. 排障顺序

Campaign 卡住：

```text
historical_import_campaigns
→ historical_import_campaign_items
→ jobs / job_attempt_events
→ artifacts
→ processing_import_batches
→ processing_import_batch_items
→ worker.log
```

Analysis Run 卡住：

```text
analysis_content_runs
→ analysis_content_run_targets
→ analysis_content_requests / request_items
→ jobs
→ analysis_content_results
→ worker.log / LLM 请求审计
```

不要手工 UPDATE 状态或删账本“解卡”。先确认 Job 的 Lease、Fencing Token、Attempt Deadline、error_code 和 Artifact 完整性，再使用正式取消/重试动作。

---

# 9. 精确事实源

```text
HTTP Contract
→ backend/src/aima_ugc/contracts/http.py
→ contracts/openapi/openapi.json
→ frontend/src/generated/api/client.ts

Schema
→ modules/ingestion/historical_tables.py
→ modules/analysis/tables.py
→ migrations/versions/20260826_0026_stage12_historical_import.py
→ migrations/versions/20260826_0027_stage12_analysis_runs.py

Worker / Repository
→ bootstrap/historical_import_worker.py
→ adapters/persistence/postgres/historical_import.py
→ adapters/persistence/postgres/historical_content.py
→ bootstrap/analysis_worker.py
→ adapters/persistence/postgres/analysis.py

测试
→ tests/**/test_stage12_*.py
→ frontend/e2e/historical-migration.spec.ts
→ frontend/e2e/voice-plaza.spec.ts
```
