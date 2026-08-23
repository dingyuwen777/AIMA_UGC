# PostgreSQL 查询与调试实战

这篇文档的目的很简单：**页面、Job、导入、采集或 AI 结果看起来不对时，可以直接去 PostgreSQL 核对真实业务事实，并能顺着表回到对应 Owner 代码。**

它不是第二份数据库 Schema。精确结构始终以：

```text
backend/src/aima_ugc/database_schema.py
backend/src/aima_ugc/**/tables.py
migrations/versions/
数据库实际 \d+ 结果
```

为准。

如果不知道某张表为什么存在、由谁写，先看：

- [`../blueprint/03-数据库与文件存储.md`](../blueprint/03-数据库与文件存储.md)
- [`../代码结构与修改导航.md`](../代码结构与修改导航.md)

## 1. 先理解数据库负责什么

AIMA_UGC 把 PostgreSQL 当作唯一业务事实库：

```text
外部 Provider / Excel
→ Raw / Input Artifact
→ Mapper
→ Canonical
→ 各模块 Service / Owner
→ PostgreSQL
```

数据库主要保存：

- 账号、内容、评论 Current；
- 内容/评论版本和指标历史；
- Collection Plan、Run、Scope、Provider Request/Attempt；
- Processing Import Batch；
- 持久化 Job；
- AI Analysis Result；
- Excel Export 任务；
- Artifact 元数据、系统配置和审计事实。

真正的大文件，例如 Provider Raw、输入/导出 Excel、Word 报告，默认由 ArtifactStore/文件系统保存；数据库保存它们的身份、状态和业务关系。

### 1.1 当前表 Owner 快速地图

```text
Content
→ backend/src/aima_ugc/modules/content/tables.py
→ backend/src/aima_ugc/adapters/persistence/postgres/

Collection
→ backend/src/aima_ugc/modules/collection/*tables.py
→ backend/src/aima_ugc/adapters/persistence/postgres/collection*.py

Ingestion
→ backend/src/aima_ugc/modules/ingestion/tables.py

Analysis
→ backend/src/aima_ugc/modules/analysis/tables.py
→ backend/src/aima_ugc/adapters/persistence/postgres/analysis.py

Reporting Export
→ backend/src/aima_ugc/modules/reporting/tables.py
→ backend/src/aima_ugc/adapters/persistence/postgres/reporting.py

Job / Artifact
→ backend/src/aima_ugc/platform/jobs/
→ backend/src/aima_ugc/platform/storage/
```

正常业务写入优先走这些 Owner 的 Service/Repository，不把本附录 SQL 当第二套写接口。

## 2. 连接 PostgreSQL

本地非敏感配置以根目录 `env.local.example` 和当前 `PlatformSettings` 为准。当前变量映射代码：

```text
backend/src/aima_ugc/platform/config/settings.py
```

常用变量：

```text
AIMA_DB_HOST
AIMA_DB_PORT
AIMA_DB_NAME
AIMA_DB_USER
AIMA_SECRET_DIR
```

数据库密码文件：

```text
<AIMA_SECRET_DIR>/postgres_password
```

不要把密码写进 Git、Issue、截图或命令脚本。

### Bash / Linux / macOS

```bash
export PGPASSWORD="$(cat "$AIMA_SECRET_DIR/postgres_password")"
psql \
  -h "${AIMA_DB_HOST:-127.0.0.1}" \
  -p "${AIMA_DB_PORT:-5432}" \
  -U "${AIMA_DB_USER:-aima_ugc}" \
  -d "${AIMA_DB_NAME:-aima_ugc}"
unset PGPASSWORD
```

### PowerShell

```powershell
$env:PGPASSWORD = (Get-Content "$env:AIMA_SECRET_DIR\postgres_password" -Raw).Trim()
psql `
  -h $(if ($env:AIMA_DB_HOST) { $env:AIMA_DB_HOST } else { "127.0.0.1" }) `
  -p $(if ($env:AIMA_DB_PORT) { $env:AIMA_DB_PORT } else { "5432" }) `
  -U $(if ($env:AIMA_DB_USER) { $env:AIMA_DB_USER } else { "aima_ugc" }) `
  -d $(if ($env:AIMA_DB_NAME) { $env:AIMA_DB_NAME } else { "aima_ugc" })
Remove-Item Env:PGPASSWORD
```

生产排障优先使用只读账号。

## 3. 进入 psql 后先确认自己连的是哪一个库

```sql
\conninfo
SELECT current_database(), current_user, now();
```

常用 psql 命令：

```text
\dt                  列出表
\d+ contents         查看表的当前真实列、约束、索引
\di                  列出索引
\x on                宽记录纵向显示
\timing on           显示 SQL 执行时间
\q                   退出
```

**第一次操作任何表，都先 `\d+ 表名`。** 文档可能落后，数据库本身不会因为文档写错而改变。

## 4. 看最近内容有没有入库

当前内容表：`contents`。

内容稳定身份由 `(platform, external_content_id)` 唯一收敛。

```sql
SELECT
    id,
    platform,
    external_content_id,
    content_type,
    title,
    published_at,
    current_version,
    current_like_count,
    current_comment_count,
    current_share_count,
    current_view_count,
    first_seen_at,
    last_seen_at,
    updated_at
FROM contents
ORDER BY last_seen_at DESC
LIMIT 20;
```

按平台和外部 ID 查一条：

```sql
SELECT *
FROM contents
WHERE platform = 'xiaohongshu'
  AND external_content_id = '这里填真实外部ID';
```

当前 `contents` 表**没有** `is_relevant` 或 `relevance_score` 这类 AI 相关性列。AI 相关性在 Analysis Result 中查询，见后文。

## 5. 看内容为什么变成当前值

### 5.1 正文/稳定业务字段历史

```sql
SELECT
    version_no,
    content_type,
    title,
    text,
    provider_attempt_id,
    raw_artifact_id,
    observed_at
FROM content_versions
WHERE content_id = '这里填 contents.id'
ORDER BY version_no;
```

### 5.2 点赞、评论等指标历史

```sql
SELECT
    reason,
    business_date,
    observation_key,
    like_count,
    comment_count,
    share_count,
    repost_count,
    favorite_count,
    view_count,
    play_count,
    observed_at
FROM content_metric_observations
WHERE content_id = '这里填 contents.id'
ORDER BY observed_at;
```

白话理解：

```text
正文变了
→ content_versions

正文没变，点赞/评论等数字变了
→ content_metric_observations
```

如果怀疑“旧数据把新字段覆盖了”，还应检查 `contents.field_observed_at`，并回到 `modules/content/ingestion.py` 看字段 freshness 规则。

## 6. 看评论

```sql
SELECT
    id,
    content_id,
    external_comment_id,
    root_comment_id,
    parent_comment_id,
    text,
    is_by_content_author,
    current_like_count,
    current_reply_count,
    current_version,
    published_at,
    last_seen_at
FROM comments
WHERE content_id = '这里填 contents.id'
ORDER BY published_at NULLS LAST, id
LIMIT 100;
```

评论正文历史：`comment_versions`。

评论指标历史：`comment_metric_observations`。

评论抓取完整度：`comment_coverage_observations` 及 thread coverage 相关表。

## 7. 看采集链：Plan → Run → Scope → Request → Attempt

### 7.1 Collection Plan

```sql
SELECT
    id,
    name,
    enabled,
    schedule_expr,
    timezone,
    schedule_version,
    misfire_policy,
    max_catch_up_runs,
    next_run_at,
    last_scheduled_at,
    updated_at
FROM collection_plans
ORDER BY updated_at DESC;
```

### 7.2 最近 Collection Run

```sql
SELECT
    r.id AS run_id,
    r.trigger_type,
    r.status AS run_status,
    r.import_batch_id,
    r.requested_count,
    r.succeeded_count,
    r.failed_count,
    r.content_count,
    r.comment_count,
    r.created_at,
    r.started_at,
    r.finished_at,
    j.id AS job_id,
    j.status AS job_status,
    j.attempt,
    j.progress,
    j.error_code
FROM collection_runs AS r
JOIN jobs AS j ON j.id = r.job_id
ORDER BY r.created_at DESC
LIMIT 30;
```

### 7.3 一个 Run 的 Scope

```sql
SELECT
    id,
    platform,
    source_type,
    source_value,
    operation_group,
    status,
    progress,
    stop_reason,
    stats,
    started_at,
    finished_at
FROM collection_scopes
WHERE run_id = '这里填 collection_runs.id'
ORDER BY platform, source_type, source_value, operation_group;
```

### 7.4 Provider Request

当前 `provider_requests` 的父级恰好一个：

```text
Collection → scope_id
File Import → import_batch_id
```

先用 `\d+ provider_requests` 确认实际数据库已经升级到当前 Revision。

```sql
SELECT
    id,
    scope_id,
    import_batch_id,
    provider_config_id,
    provider,
    operation,
    status,
    attempt_count,
    estimated_cost,
    actual_cost,
    cost_currency,
    created_at,
    completed_at,
    error_code
FROM provider_requests
ORDER BY created_at DESC
LIMIT 50;
```

### 7.5 Provider Attempt

```sql
SELECT
    id,
    provider_request_id,
    attempt_no,
    dispatch_status,
    http_status,
    external_request_id,
    raw_artifact_id,
    billing_status,
    estimated_cost,
    actual_cost,
    cost_currency,
    potential_duplicate_charge,
    error_code,
    created_at,
    completed_at
FROM provider_request_attempts
WHERE provider_request_id = '这里填 provider_requests.id'
ORDER BY attempt_no;
```

如果 `dispatch_status='unknown'`，不要直接“再发一次”。它表示外部结果可能不确定，系统会保留潜在重复计费事实。

## 8. 看 Scheduler 有没有漏跑或重复跑

```sql
SELECT
    plan_id,
    schedule_version,
    scheduled_for,
    status,
    skip_reason,
    job_id,
    created_at
FROM collection_schedule_occurrences
ORDER BY scheduled_for DESC
LIMIT 50;
```

当前 `latest_only` 策略下，停机跨过多个周期后，更早的到期点会明确记录：

```text
skipped / misfire_superseded
```

只把最新到期点入队。看到 `skipped` 不等于 Scheduler 丢任务。

详细解释见 [`Scheduler调度执行与停机恢复.md`](Scheduler调度执行与停机恢复.md)。

## 9. 看 Excel Import Batch

当前表：`processing_import_batches`。

```sql
SELECT
    id,
    input_artifact_id,
    job_id,
    status,
    stats,
    error_summary,
    created_at,
    started_at,
    finished_at
FROM processing_import_batches
ORDER BY created_at DESC
LIMIT 30;
```

Import Batch 是文件导入父事实，不伪造 Collection Run/Scope。

来源反查可以继续：

```text
processing_import_batches.id
→ provider_requests.import_batch_id
→ provider_request_attempts
→ content_versions.provider_attempt_id
→ contents
```

详细链路见 [`数据入口与统一入库实现.md`](数据入口与统一入库实现.md)。

## 10. 看持久化 Job

### 最近 Job

```sql
SELECT
    id,
    job_type,
    payload_version,
    status,
    attempt,
    lease_takeover_count,
    max_attempts,
    progress,
    available_at,
    lease_owner,
    heartbeat_at,
    lease_expires_at,
    attempt_deadline_at,
    error_code,
    created_at,
    updated_at
FROM jobs
ORDER BY created_at DESC
LIMIT 50;
```

### 正在运行

```sql
SELECT
    id,
    job_type,
    attempt,
    lease_takeover_count,
    lease_owner,
    heartbeat_at,
    lease_expires_at,
    attempt_deadline_at,
    progress
FROM jobs
WHERE status = 'running'
ORDER BY updated_at DESC;
```

### Attempt 事件历史

```sql
SELECT
    event_seq,
    attempt,
    lease_takeover_count,
    event_type,
    worker_id,
    reason_code,
    safe_detail,
    happened_at
FROM job_attempt_events
WHERE job_id = '这里填 jobs.id'
ORDER BY event_seq;
```

如果 Job 一直 `running`，不要只看 `heartbeat_at`；还要看 `lease_expires_at`、`attempt_deadline_at` 和 Reaper/Worker 日志，Heartbeat 不能无限延长 Attempt Deadline。

## 11. 看 AI Analysis

当前正式结果表：

```text
analysis_content_results
```

### 最近分析结果

```sql
SELECT
    id,
    content_id,
    content_version,
    job_id,
    schema_version,
    relevance,
    voice_type,
    sentiment,
    prompt_version,
    prompt_sha256,
    taxonomy_sha256,
    model_provider,
    model,
    analyzed_at,
    created_at
FROM analysis_content_results
ORDER BY created_at DESC
LIMIT 30;
```

当前 `voice_type` 合法机器值：

```text
user_voice
creator_marketing
brand_official
dealer_promotion
media_information
other_organization
unknown
```

真实用户发声：

```text
voice_type = 'user_voice'
```

查 AI 判定为无关：

```sql
SELECT
    id,
    content_id,
    content_version,
    voice_type,
    analyzed_at
FROM analysis_content_results
WHERE relevance = 'irrelevant'
ORDER BY analyzed_at DESC;
```

注意：这是 Analysis Result，不是 `contents.is_relevant`。

### 一个结果的标签

```sql
SELECT
    ordinal,
    primary_label,
    secondary_label
FROM analysis_content_label_pairs
WHERE analysis_result_id = '这里填 analysis_content_results.id'
ORDER BY ordinal;
```

### 一次正式 Analysis 请求

```text
analysis_content_requests
→ 请求父事实

analysis_content_request_items
→ 冻结 content_id + content_version + ordinal
```

第一次排障先：

```sql
\d+ analysis_content_requests
\d+ analysis_content_request_items
```

再按当前真实列查询。

### 当前没有什么

`analysis_content_results` 当前**没有**：

```text
input_tokens
output_tokens
cost_amount
cost_currency
```

运行/离线调用能统计 token/cost，不等于 Result 表已经持久化成本。

完整 AI 实现见 [`AI舆情打标与分析实现.md`](AI舆情打标与分析实现.md)。

## 12. 看正式 Excel Export

当前表：

```text
reporting_data_exports
reporting_data_export_items
```

### 最近导出

```sql
SELECT
    id,
    job_id,
    artifact_id,
    format,
    request_snapshot,
    stats,
    created_at,
    completed_at
FROM reporting_data_exports
ORDER BY created_at DESC
LIMIT 30;
```

### 本次冻结了哪些 Content 版本

```sql
SELECT
    ordinal,
    content_id,
    content_version
FROM reporting_data_export_items
WHERE export_id = '这里填 reporting_data_exports.id'
ORDER BY ordinal;
```

当前正式 Job 类型：

```text
reporting.content-export-excel.v1
```

如果 Job succeeded 但无法下载，继续查：

```text
reporting_data_exports.artifact_id
→ artifacts
→ ArtifactStore 对应 storage_key
```

正式 Export 实现见 `backend/src/aima_ugc/modules/reporting/README.md`。

## 13. 看数据库和索引大小

最大的业务表：

```sql
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;
```

查看 `contents` 当前索引：

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'contents'
ORDER BY indexname;
```

当前连接：

```sql
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    wait_event_type,
    wait_event,
    query_start
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY query_start NULLS LAST;
```

长事务：

```sql
SELECT
    pid,
    usename,
    state,
    xact_start,
    now() - xact_start AS xact_age,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
ORDER BY xact_start;
```

## 14. 查询慢时先用 EXPLAIN

先看执行计划，不真正执行：

```sql
EXPLAIN
SELECT id, title, last_seen_at
FROM contents
WHERE platform = 'xiaohongshu'
ORDER BY last_seen_at DESC
LIMIT 20;
```

确认是测试/只读查询并且可以实际运行后：

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, last_seen_at
FROM contents
WHERE platform = 'xiaohongshu'
ORDER BY last_seen_at DESC
LIMIT 20;
```

`ANALYZE` 会真正执行 SQL。不要随手对 `UPDATE/DELETE` 使用。

## 15. INSERT / UPDATE 为什么默认不建议直接改业务表

AIMA_UGC 的一条业务写入往往同时影响：

```text
来源 Attempt / Artifact
→ Content Current
→ Version
→ Metric Observation
→ 来源账本
→ 必要的下游 Job
```

直接 SQL 很容易绕过 Owner、幂等、版本、Fencing 或来源约束。

因此：

- 正常业务数据：优先正式 Service / Repository / API / 调试入口；
- 数据库排障：优先 `SELECT`；
- 必须人工改数据：先备份、确认 Owner/Migration/约束，并在隔离环境验证。

### 15.1 安全练习模板

如果只是学习 SQL，可以在事务里操作后回滚：

```sql
BEGIN;

\d+ 目标表

-- 下面只是 SQL 语法模板，不是 AIMA 某张业务表的固定 Contract
INSERT INTO 目标表 (字段1, 字段2)
VALUES ('值1', '值2')
RETURNING *;

UPDATE 目标表
SET 字段2 = '新值'
WHERE 主键字段 = '明确的一条记录ID'
RETURNING *;

ROLLBACK;
```

不要把模板字段直接复制到生产库。

### 15.2 高风险语句

以下操作不能用“试一下”的方式在生产库执行：

```text
UPDATE ... 没有 WHERE
DELETE ... 没有 WHERE
TRUNCATE
DROP TABLE / DROP DATABASE
ALTER TABLE
```

Migration 管理的 Schema 不应靠手工 `ALTER TABLE` 演进。

## 16. Alembic：确认数据库版本

从仓库根运行：

```bash
uv run alembic current
uv run alembic heads
uv run alembic history
```

升级：

```bash
uv run alembic upgrade head
```

模型与 Migration 一致性：

```bash
uv run alembic check
```

`downgrade` 只在明确允许的隔离测试库使用。某些 Revision 在存在新业务事实后会故意拒绝危险 downgrade，不能为了让命令成功而绕过保护。

## 17. 常见排障顺序

### 页面没有内容

```text
1. 查 contents 是否有目标数据
2. 查 HTTP Query 参数/筛选条件
3. 查当前 Analysis Identity / analysis_content_results
4. 看 content_queries.py 是否默认排除了 current irrelevant
5. 再查 API
6. 最后查前端 Feature / generated Client
```

当前声音广场查询：

```text
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
```

### Excel 导入一直处理中

```text
1. processing_import_batches
2. jobs
3. job_attempt_events
4. provider_requests / provider_request_attempts
5. worker.log
```

### TikHub 有 Run 但没有 Content

```text
1. collection_runs
2. collection_scopes
3. provider_requests
4. provider_request_attempts / raw_artifact_id
5. collection_candidates / candidate ingestions
6. Mapper
7. Rule Relevance / Decision
8. Content Ingestion
```

### AI 页面没有标签

```text
1. contents 是否存在目标 Content
2. analysis_content_requests / items 是否创建
3. 对应 Job 是否成功
4. analysis_content_results 是否有当前版本结果
5. 当前 Prompt/Taxonomy/Model identity 是否匹配
6. relevance 是否 irrelevant
7. analysis_content_label_pairs 是否存在
```

### Scheduler 到点没跑

```text
1. collection_plans.next_run_at
2. collection_schedule_occurrences
3. collection_runs
4. jobs
5. collection_scopes
```

如果已有 enqueued Occurrence + Job，Scheduler 已完成职责，应继续查 Worker。

## 18. 精确事实去哪里看

- 数据表注册：`backend/src/aima_ugc/database_schema.py`
- Content：`backend/src/aima_ugc/modules/content/tables.py`、`extended_tables.py`
- Collection：`backend/src/aima_ugc/modules/collection/*tables.py`
- Import Batch：`backend/src/aima_ugc/modules/ingestion/tables.py`
- Analysis：`backend/src/aima_ugc/modules/analysis/tables.py`
- Reporting：`backend/src/aima_ugc/modules/reporting/tables.py`
- Job：`backend/src/aima_ugc/platform/jobs/tables.py`
- Migration：`migrations/versions/`
- 运行配置：`backend/src/aima_ugc/platform/config/settings.py`
- 本地配置示例：`env.local.example`
- 数据架构原则：[`../blueprint/03-数据库与文件存储.md`](../blueprint/03-数据库与文件存储.md)

数据库结构发生变化时，应先改代码/Migration/测试，再同步本文中受影响的 SQL 示例；不能反过来让附录成为 Schema 事实源。
