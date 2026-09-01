# Reporting 模块

`modules/reporting` 当前负责**正式 PostgreSQL 驱动的 Excel 数据导出**。

先区分两个容易混淆的能力：

```text
modules/reporting/
→ 正式 HTTP + Job + PostgreSQL Export
→ 生成统一数据明细 Excel

platform/reporting/
→ 离线 Markdown / Word 舆情报告
→ 当前不是同一个 PostgreSQL Export Job
```

如果要改声音广场“导出 Excel”，先看本 README；如果要改横向 A4 Word 报告，去：

[`../../../../../docs/appendix/10_Word舆情报告生成与排版实现.md`](../../../../../docs/appendix/10_Word舆情报告生成与排版实现.md)

---

## 1. 当前正式 Export 主链

```text
POST /api/v1/data-exports
→ 按查询/选择冻结 Content ID + Content Version
→ reporting_data_exports
→ reporting_data_export_items
→ reporting.content-export-excel.v1 Job
→ Worker 分页读取冻结版本
→ UnifiedDataExcelV1
→ platform/export/excel.py
→ XLSX
→ ArtifactService / ArtifactStore
→ Export 关联 Artifact
→ GET /download
```

HTTP：

- [`backend/src/aima_ugc/bootstrap/reporting_http.py`](../../bootstrap/reporting_http.py)

Worker：

- [`backend/src/aima_ugc/bootstrap/export_worker.py`](../../bootstrap/export_worker.py)

PostgreSQL Repository：

- [`backend/src/aima_ugc/adapters/persistence/postgres/reporting.py`](../../adapters/persistence/postgres/reporting.py)

共享 Excel Renderer：

- [`backend/src/aima_ugc/platform/export/excel.py`](../../platform/export/excel.py)

---

## 2. 为什么 Export 要先冻结 Content Version

假设用户 10:00 点击导出：

```text
content A current_version = 3
content B current_version = 7
```

Worker 10:05 才真正开始生成 Excel，期间 A 可能已经变成 version 4。

如果 Worker 再去读“当前版本”，最终文件就不是用户 10:00 提交时选择的数据。

所以创建 Export 时会冻结：

```text
content_id
content_version
ordinal
```

到：

```text
reporting_data_export_items
```

Worker 后续严格按这些版本读取。

这和 Analysis Request 冻结 Content Version 是同一类原则：**长任务不能在执行时重新解释已经变化的业务选择。**

---

## 3. 当前数据库表

定义：

- [`backend/src/aima_ugc/modules/reporting/tables.py`](tables.py)

### `reporting_data_exports`

保存 Export 父事实：

```text
id
job_id
artifact_id
format
request_snapshot
stats
created_at
completed_at
```

精确 FK、Check、Unique 直接看 `tables.py`。

### `reporting_data_export_items`

保存冻结的目标：

```text
export_id
content_id
content_version
ordinal
```

这里不复制标题、正文、AI 标签，因为这些事实已经由 Content / Analysis Owner 保存。

---

## 4. 当前 Job

Job 类型：

```text
reporting.content-export-excel.v1
```

定义：

- [`backend/src/aima_ugc/modules/reporting/data_export_job.py`](data_export_job.py)

Worker Registry：

- [`backend/src/aima_ugc/bootstrap/worker.py`](../../bootstrap/worker.py)

执行器：

- [`backend/src/aima_ugc/bootstrap/export_worker.py`](../../bootstrap/export_worker.py)

当前 Worker 会：

1. 先检查 Export 是否已经有 Artifact；有则直接返回已有结果；
2. 分页加载冻结记录；
3. 每页组装 `UnifiedDataExcelV1`；
4. 交给共享 Excel Exporter；
5. 将 XLSX 作为 `content-export.xlsx` Artifact 保存；
6. 在验证当前 `JobExecutionFence` 后把 Artifact 和 stats 关联到 Export；
7. 标记 Artifact linked；
8. 返回 Job Result。

这使 retry/takeover 不会轻易重复发布第二个业务 Export 结果。

---

## 5. Worker 为什么分页读，而不是一次把所有数据加载进内存

当前执行器使用固定分页：

```text
_EXPORT_PAGE_SIZE = 100
```

代码：

```text
PostgresDataExportJobExecutor._iter_records()
```

流程：

```text
ordinal > after_ordinal
→ load 100 records
→ yield 到 Excel Exporter
→ heartbeat progress
→ 下一页
```

这样大量内容导出时不会一次把所有 Content + Comments + Analysis 全部加载到内存。

具体页大小属于实现事实，以 [`export_worker.py`](../../bootstrap/export_worker.py) 为准，不把它当公共 Contract。

---

## 6. `PostgresDataExportRepository` 实际投影什么

文件：

- [`backend/src/aima_ugc/adapters/persistence/postgres/reporting.py`](../../adapters/persistence/postgres/reporting.py)

它不是简单读取 `contents` Current。

每个冻结 Content 会组合：

```text
指定 content_version 的正文/作者/URL
+ Content Current 的互动指标
+ 对应来源 Provider/Raw
+ 指定版本下当前 Analysis Identity 匹配的 Analysis
+ Comments
+ Comment Coverage
→ UnifiedDataExcelV1
```

这意味着导出同时复用多个 Owner 的**只读事实**，但只由 Reporting Owner 写 `reporting_data_*` 表。

---

## 7. Analysis 怎样进入导出

当前 Export Repository 会按当前配置身份筛选 Analysis：

```text
prompt_version
prompt_sha256
taxonomy_sha256
model_provider
model
```

只读取：

```text
content_id + 冻结 content_version
```

下与当前 Analysis Identity 匹配的最新结果。

如果：

- 当前版本从未分析；
- 只有旧 Content Version Analysis；
- Prompt/Taxonomy/Model 已变化，旧 Analysis 不再匹配；

那么该 Content 仍可以导出，但 AI 字段为空，并计入：

```text
unanalyzed_count
```

而不是偷偷使用 stale Analysis。

---

## 8. 当前 Export Stats

Worker 完成后记录：

```text
content_count
analyzed_count
unanalyzed_count
comment_count
```

这些 stats 位于 `reporting_data_exports.stats`，并进入 Job Result。

它们是本次 Export 的执行/产物统计，不是全系统 KPI 表。

---

## 9. Artifact 怎样关联

Worker 先通过：

```text
ArtifactService.store_stream(...)
```

保存文件，再在数据库事务里：

```text
PostgresDataExportRepository.attach_artifact(...)
→ 验证 JobExecutionFence
→ 设置 export.artifact_id / stats / completed_at

PostgresArtifactMetadataRepository.mark_linked(...)
```

为什么需要 Fence：

如果旧 Worker Lease 已失效，新 Worker 已接管，同一个旧进程不能继续把自己的文件关联成最终结果。

---

## 10. 当前 HTTP API

```text
POST /api/v1/data-exports
GET  /api/v1/data-exports
GET  /api/v1/data-exports/{export_id}
GET  /api/v1/data-exports/{export_id}/download
```

Route：

- [`backend/src/aima_ugc/bootstrap/api.py`](../../bootstrap/api.py)

Application Service：

- [`backend/src/aima_ugc/bootstrap/reporting_http.py`](../../bootstrap/reporting_http.py)

精确 Request/Response：

- [`backend/src/aima_ugc/contracts/http.py`](../../contracts/http.py)
- [`contracts/openapi/openapi.json`](../../../../../contracts/openapi/openapi.json)

### 下载边界

如果：

```text
artifact_id is null
```

说明 Export 尚未就绪，下载返回业务 409，而不是 200 + 空文件。

---

## 11. 和共享 Excel Exporter 的关系

真正生成 Workbook 的公共实现：

- [`backend/src/aima_ugc/platform/export/excel.py`](../../platform/export/excel.py)

它也被离线 `imports_test` 复用。

因此：

- 正式 Export 不复制 Workbook 样式；
- `imports_test` 不维护第二套字段/Sheet；
- Formula Injection、防 URL/ID 格式、Sheet/列布局等公共逻辑只有一套。

详细 Excel 数据契约：

[`../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md`](../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md)

---

## 12. 当前模块文件地图

| 文件 | 职责 | 常见修改 |
| --- | --- | --- |
| `tables.py` | Export / Export Items 表 | 改持久化父事实或冻结目标结构 |
| `models.py` | Reporting 内部记录模型 | 改内部 Service/Repository 返回对象 |
| [`data_export_job.py`](data_export_job.py) | Job Payload / Handler / 上限 | 改 Job 版本、失败分类、Artifact 上限 |
| `http.py` | Reporting HTTP Port/异常 | 改应用 Service 契约边界 |

生产跨目录：

- [`bootstrap/reporting_http.py`](../../bootstrap/reporting_http.py)
- [`bootstrap/export_worker.py`](../../bootstrap/export_worker.py)
- [`adapters/persistence/postgres/reporting.py`](../../adapters/persistence/postgres/reporting.py)
- [`platform/export/excel.py`](../../platform/export/excel.py)

---

## 13. 修改场景

### 增加 Excel 列

通常不要先改 Reporting 表。

先判断列来自哪里：

```text
Content 字段
→ Canonical / Content / Export Contract

Analysis 字段
→ Analysis Contract / Export Projection

纯展示列
→ platform/export/excel.py
```

如果只是 Workbook 展示变化，不应该给 `reporting_data_exports` 加列。

### 改导出筛选

```text
ContentFilterSnapshot / DataExportSubmitRequest
→ reporting_http.py 冻结 targets
→ request_snapshot
→ API Test
→ generated Client
```

### 改 Worker 重试/恢复

先看：

```text
export_worker.py
platform/jobs/
PostgresDataExportRepository.attach_artifact()
```

不要自己新增一套锁字段。

### 改 Artifact 文件大小限制

```text
data_export_job.py
→ MAX_EXPORT_ARTIFACT_BYTES
→ Worker Test
→ API/用户说明（如果可观察）
```

---

## 14. 调试一条 Export

SQL 顺序：

```text
1. reporting_data_exports
2. reporting_data_export_items
3. jobs
4. artifacts
```

如果 Export `succeeded` 但下载失败：

```text
检查 export.artifact_id
→ artifacts metadata
→ ArtifactStore 文件是否存在/校验
```

如果 AI 列为空：

```text
检查 export item 的 content_version
→ analysis_content_results 是否同 version
→ Prompt/Taxonomy/Provider/Model identity 是否匹配
```

SQL 示例：

[`../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md`](../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md)

---

## 15. 测试重点

- Export 创建时目标非空；
- Content Version 正确冻结；
- Retry 不重复发布不一致 Artifact；
- Fencing 拒绝旧 Worker；
- 大文件超过上限关闭失败；
- stale Analysis 不进入当前 AI 列；
- Comments/Coverage 正确投影；
- 下载未就绪返回 409；
- shared Excel Exporter 行为一致。

主要测试分布在：

```text
tests/unit/
tests/api/
tests/integration/
```

最终以 PR 最新 HEAD CI 为准。

---

## 16. 当前不属于本模块的能力

当前不要把这些写进 `modules/reporting`：

```text
Word Report 的页面排版和词云
→ platform/reporting/

Analysis taxonomy
→ modules/analysis/Prompt

Content Current/Version
→ modules/content/

Artifact bytes 存取
→ platform/storage/
```

模块职责越清楚，后面修改 Excel、AI、Word 时越不容易互相污染。
