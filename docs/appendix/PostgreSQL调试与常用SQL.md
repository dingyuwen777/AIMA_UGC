# PostgreSQL 调试与常用 SQL

这篇文档的目的很简单：**当页面、Job、导入或 AI 结果看起来不对时，可以直接去 PostgreSQL 验证事实。**

它不是第二份数据库设计文档。精确表结构仍以 `backend/src/aima_ugc/**/tables.py`、`migrations/versions/` 和数据库实际 `\d+` 结果为准。

## 1. 先理解数据库在系统里负责什么

AIMA_UGC 把 PostgreSQL 当作业务事实库：

```text
外部 Provider / Excel
→ Raw / Input Artifact
→ Mapper
→ Canonical
→ Ingestion / 各模块 Owner
→ PostgreSQL
```

数据库里保存的是：

- 当前内容、评论、账号；
- 内容/评论版本和指标历史；
- 采集 Plan、Run、Scope、Provider Request/Attempt；
- Excel Import Batch；
- 持久化 Job；
- AI 分析结果；
- Excel Export 任务；
- Artifact 元数据、系统配置和审计事实。

真正的大文件，例如 Raw、导出文件和报告，默认放文件系统；数据库保存它们的 Artifact 元数据和关系。

## 2. 连接前先做安全确认

默认本地非敏感配置见仓库根 `env.local.example`：

```text
AIMA_DB_HOST=127.0.0.1
AIMA_DB_PORT=5432
AIMA_DB_NAME=aima_ugc
AIMA_DB_USER=aima_ugc
```

密码不写在该文件，而是放在：

```text
<AIMA_SECRET_DIR>/postgres_password
```

### 2.1 Bash / Linux / macOS

```bash
export PGPASSWORD="$(cat "$AIMA_SECRET_DIR/postgres_password")"
psql \
  -h "${AIMA_DB_HOST:-127.0.0.1}" \
  -p "${AIMA_DB_PORT:-5432}" \
  -U "${AIMA_DB_USER:-aima_ugc}" \
  -d "${AIMA_DB_NAME:-aima_ugc}"
unset PGPASSWORD
```

### 2.2 PowerShell

```powershell
$env:PGPASSWORD = (Get-Content "$env:AIMA_SECRET_DIR\postgres_password" -Raw).Trim()
psql `
  -h $(if ($env:AIMA_DB_HOST) { $env:AIMA_DB_HOST } else { "127.0.0.1" }) `
  -p $(if ($env:AIMA_DB_PORT) { $env:AIMA_DB_PORT } else { "5432" }) `
  -U $(if ($env:AIMA_DB_USER) { $env:AIMA_DB_USER } else { "aima_ugc" }) `
  -d $(if ($env:AIMA_DB_NAME) { $env:AIMA_DB_NAME } else { "aima_ugc" })
Remove-Item Env:PGPASSWORD
```

如果只是排障，优先使用只读账号；不要把生产数据库密码复制进命令历史、截图、Issue 或日志。

## 3. 进入 psql 后先确认自己连的是哪一个库

```sql
\conninfo
SELECT current_database(), current_user, now();
```

常用 psql 命令：

```text
\dt                  列表
\d+ contents         看 contents 当前真实结构
\di                   看索引
\x on                 宽记录改成纵向显示
\timing on            显示 SQL 执行时间
\q                    退出
```

第一次接触某张表时，**先 `\d+ 表名`，再写 SQL**。不要只凭本文猜字段。

## 4. 最常用：看最近内容有没有真正入库

当前内容表是 `contents`。平台内容身份由 `(platform, external_content_id)` 唯一收敛。

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
    is_relevant,
    relevance_score,
    last_seen_at
FROM contents
ORDER BY last_seen_at DESC
LIMIT 20;
```

`is_relevant` 等相关性列由当前 Migration 链加入 `contents`。如果你连接的是未升级到当前 head 的旧数据库，应先执行 `\d+ contents` 和 Alembic 检查，而不是认为应用代码有问题。

按平台查一条内容：

```sql
SELECT *
FROM contents
WHERE platform = 'xhs'
  AND external_content_id = '这里填真实外部ID';
```

只看默认业务应该展示的相关内容：

```sql
SELECT id, platform, external_content_id, title, published_at
FROM contents
WHERE is_relevant = true
ORDER BY published_at DESC NULLS LAST, id DESC
LIMIT 50;
```

> 应用查询层默认过滤无关内容。数据库仍保留必要审计事实，因此排障时可以显式查看 `is_relevant = false`。

## 5. 看“当前值为什么变成这样”：内容版本与指标历史

内容正文或稳定业务字段变化时，会产生 `content_versions`；点赞、评论等指标观察写 `content_metric_observations`。

```sql
SELECT
    version_no,
    title,
    text,
    provider_attempt_id,
    raw_artifact_id,
    observed_at
FROM content_versions
WHERE content_id = '这里填 contents.id'
ORDER BY version_no;
```

```sql
SELECT
    reason,
    business_date,
    like_count,
    comment_count,
    share_count,
    view_count,
    observed_at
FROM content_metric_observations
WHERE content_id = '这里填 contents.id'
ORDER BY observed_at;
```

这两张历史表非常重要：它们能区分“内容正文变了”和“只是互动数字变了”。

## 6. 看评论

```sql
SELECT
    id,
    content_id,
    external_comment_id,
    root_comment_id,
    parent_comment_id,
    text,
    current_like_count,
    current_reply_count,
    published_at,
    last_seen_at
FROM comments
WHERE content_id = '这里填 contents.id'
ORDER BY published_at, id
LIMIT 100;
```

评论正文历史看 `comment_versions`，指标历史看 `comment_metric_observations`。

## 7. 看采集链：Plan → Run → Scope → Provider Request → Attempt

### 7.1 计划

```sql
SELECT
    id,
    name,
    enabled,
    schedule_expr,
    timezone,
    schedule_version,
    next_run_at,
    last_scheduled_at
FROM collection_plans
ORDER BY updated_at DESC;
```

### 7.2 最近运行

```sql
SELECT
    r.id AS run_id,
    r.trigger_type,
    r.status AS run_status,
    r.import_batch_id,
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
    stats
FROM collection_scopes
WHERE run_id = '这里填 collection_runs.id'
ORDER BY platform, source_type, source_value;
```

### 7.4 Provider 请求和真实 Attempt

`provider_requests` 是“一个逻辑请求”；`provider_request_attempts` 是“实际发送/读取的一次尝试”。重试时 Request 可以不变，但会增加 Attempt。

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
    created_at,
    completed_at,
    error_code
FROM provider_requests
ORDER BY created_at DESC
LIMIT 50;
```

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
    actual_cost,
    potential_duplicate_charge,
    error_code,
    created_at,
    completed_at
FROM provider_request_attempts
WHERE provider_request_id = '这里填 provider_requests.id'
ORDER BY attempt_no;
```

如果 `dispatch_status='unknown'`，不要简单理解为“失败后再发一次就行”。这表示外部结果可能不确定，代码会保守处理潜在重复计费。

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

当前策略是 `latest_only`：停机跨过多个周期后，更早到期点会记录 `skipped / misfire_superseded`，只把最新到期点入队。看到 skipped 不等于 Scheduler 丢数据。

详细解释见 [`Scheduler运行与恢复.md`](Scheduler运行与恢复.md)。

## 9. 看 Excel Import Batch

当前表名：`processing_import_batches`。

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

它是文件导入的父事实。Excel 导入不需要伪造 Collection Run/Scope；来源关系通过 Import Batch → Provider Request/Attempt → Artifact → Ingestion 保留。

## 10. 看持久化 Job

```sql
SELECT
    id,
    job_type,
    status,
    attempt,
    max_attempts,
    progress,
    available_at,
    lease_owner,
    lease_expires_at,
    attempt_deadline_at,
    error_code,
    created_at,
    updated_at
FROM jobs
ORDER BY created_at DESC
LIMIT 50;
```

只看正在运行：

```sql
SELECT
    id,
    job_type,
    attempt,
    lease_owner,
    heartbeat_at,
    lease_expires_at,
    attempt_deadline_at,
    progress
FROM jobs
WHERE status = 'running'
ORDER BY updated_at DESC;
```

看某个 Job 的 Attempt 历史：

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

## 11. 看 AI 分析结果

当前 AI 结果不是只存在 Excel/JSONL；正式分析会写 `analysis_results`，标签对写 `analysis_label_pairs`。

```sql
SELECT
    id,
    content_id,
    schema_version,
    status,
    model_provider,
    model_name,
    prompt_version,
    voice_type,
    sentiment,
    input_tokens,
    output_tokens,
    cost_amount,
    cost_currency,
    completed_at,
    created_at
FROM analysis_results
ORDER BY created_at DESC
LIMIT 30;
```

当前 `voice_type` 的合法业务值是：

```text
professional_media
influencer_self_media
ordinary_user
```

它是“发声类型”的唯一业务事实，不再另存一个重复的“是否真实用户发声”布尔字段。

看一个结果的标签：

```sql
SELECT
    position,
    primary_label,
    secondary_label
FROM analysis_label_pairs
WHERE analysis_result_id = '这里填 analysis_results.id'
ORDER BY position;
```

精确 taxonomy 不在数据库附录复制，唯一业务事实见：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

## 12. 看正式 Excel Export

```sql
SELECT
    id,
    job_id,
    export_type,
    source_type,
    status,
    total_items,
    exported_items,
    artifact_id,
    error_code,
    created_at,
    finished_at
FROM reporting_exports
ORDER BY created_at DESC
LIMIT 30;
```

一个导出任务冻结了哪些内容：

```sql
SELECT position, content_id
FROM reporting_export_items
WHERE export_id = '这里填 reporting_exports.id'
ORDER BY position;
```

## 13. 看表、索引和数据库大小

最大的表：

```sql
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;
```

某张表的索引：

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

## 14. EXPLAIN：查询慢时先看数据库准备怎么执行

先用不真正执行的版本：

```sql
EXPLAIN
SELECT id, title
FROM contents
WHERE platform = 'xhs'
  AND is_relevant = true
ORDER BY last_seen_at DESC
LIMIT 20;
```

确认在测试/只读环境可接受后，再用：

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title
FROM contents
WHERE platform = 'xhs'
  AND is_relevant = true
ORDER BY last_seen_at DESC
LIMIT 20;
```

`ANALYZE` 会真实执行 SQL。对 `UPDATE/DELETE` 不要随手使用。

## 15. INSERT / UPDATE：为什么默认不建议直接改业务表

AIMA_UGC 的业务写入通常不只是“一张表插一行”。例如一条内容入库可能同时涉及：

```text
来源 Attempt/Artifact
→ 内容 Current
→ Version
→ Metric Observation
→ 来源账本
→ 下游 Job
```

直接 SQL 很容易绕过 Owner、幂等、版本、Fencing 或来源校验。所以：

- 正常业务数据：优先调用正式 Service/Repository/API/调试入口；
- 数据库排障：优先 `SELECT`；
- 必须人工改数据：先备份、确认 Owner/Migration/约束，并在隔离环境验证。

### 15.1 安全练习模板

如果只是学习 SQL，可以在事务里操作后回滚：

```sql
BEGIN;

-- 先查看真实结构
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

### 15.2 修改前至少先做这三步

```sql
-- 1. 精确确认目标
SELECT * FROM 目标表 WHERE 主键字段 = '明确ID';

-- 2. 开事务
BEGIN;

-- 3. 修改并看 RETURNING；不确定就 ROLLBACK
```

以下语句属于高风险：

```text
UPDATE ... 没有 WHERE
DELETE ... 没有 WHERE
TRUNCATE
DROP TABLE / DROP DATABASE
ALTER TABLE
```

生产环境不要把“试一下”当调试方法。

## 16. Alembic：确认数据库版本

从仓库根目录运行：

```bash
uv run alembic current
uv run alembic heads
uv run alembic history
```

升级到当前仓库 head：

```bash
uv run alembic upgrade head
```

新增 Migration 后检查模型与 Migration 是否一致：

```bash
uv run alembic check
```

`downgrade` 只在明确允许的隔离测试库按对应 Migration 规则使用。某些 Revision 在存在新业务事实后会故意拒绝安全 downgrade，不能为了让命令成功而绕过保护。

## 17. 常见排障顺序

### 页面没有数据

```text
1. 查 contents / 对应业务表是否有数据
2. 查 is_relevant 等默认过滤条件
3. 查 API/Query Repository 的查询条件
4. 再查前端 Feature API / Store
```

### Excel 导入一直处理中

```text
1. 查 processing_import_batches
2. 查关联 jobs
3. 查 job_attempt_events
4. 查 provider_requests / provider_request_attempts
5. 查 worker.log
```

### TikHub 采集有 Run 但没有内容

```text
1. 查 collection_runs
2. 查 collection_scopes
3. 查 provider_requests
4. 查 provider_request_attempts.raw_artifact_id
5. 查 Candidate / Ingestion 账本
6. 再看 Mapper / relevance 过滤
```

### AI 页面没有标签

```text
1. 查 contents 是否存在且默认相关
2. 查 analysis_results 是否 succeeded
3. 查 voice_type / sentiment
4. 查 analysis_label_pairs
5. 查对应 Job 与 worker.log
```

## 18. 精确事实去哪里看

- 数据表注册入口：`backend/src/aima_ugc/database_schema.py`
- Content 表：`backend/src/aima_ugc/modules/content/tables.py`
- Collection 表：`backend/src/aima_ugc/modules/collection/*.py`
- Import Batch：`backend/src/aima_ugc/modules/ingestion/tables.py`
- Analysis：`backend/src/aima_ugc/modules/analysis/tables.py`
- Reporting：`backend/src/aima_ugc/modules/reporting/tables.py`
- Job：`backend/src/aima_ugc/platform/jobs/tables.py`
- Migration：`migrations/versions/`
- 本地数据库配置示例：`env.local.example`
- 架构原则：[`../blueprint/03-数据库与文件存储.md`](../blueprint/03-数据库与文件存储.md)

数据库结构发生变化时，应先改代码/Migration/测试，再同步本文中受影响的调试示例；不能反过来让本文成为 Schema 事实源。
