# Reporting 模块

`modules/reporting` 负责正式 PostgreSQL 驱动的 Excel 数据导出，以及管理员数据库报告的持久业务事实。两者共用统一数据投影、通用 Job Runtime 与 Artifact 存储，报告的统计和排版由 `platform/reporting/` 提供。

先区分两个容易混淆的能力：

```text
modules/reporting/
→ 正式 HTTP + Job + PostgreSQL Export
→ 生成统一数据明细 Excel

modules/reporting/report_tables.py
→ ReportRun + 冻结本期/上期数据 + 报告文件关联
→ 独立生成与飞书发布 Job

platform/reporting/
→ 共用 Markdown / Word 统计与排版
→ 接受冻结 Dataset；也保留离线 Excel 入口
```

如果要改声音广场“导出 Excel”，先看本 README；如果要改横向 A4 Word 报告，去：

[`docs/appendix/10_Word舆情报告生成与排版实现.md`](../../../../../docs/appendix/10_Word舆情报告生成与排版实现.md)

---

## 数据库报告与恢复

管理员在“报告生成”选择品牌、可选车型及北京时间自然日范围。预检不调用模型；创建时在一致读事务中冻结本期和紧邻等长上期的正文版本、评论、指标、实际分析身份及人工修订，并原子创建生成 Job。Worker 从冻结数据生成 Word、统一数据 Excel、Markdown、可编辑图表工作簿和图片，完整产物集合提交后才开放下载。

正式报告的“命中关键词”采用数据库中该 Content Version 已保存且有效的品牌、车型证据，复用统一投影的标准名称；别名归并为同一名称，车型沿用现有目录合并映射。每条内容内的重复来源或重复名称只计一次，关键词内容占比以本期全部内容为分母，保留官方、商业等发声的全量统计口径。创建时同时冻结本期/上期的名称、命中结果和口径说明，之后目录改名、证据停用或重试不改变历史报告。Markdown/Word 的关键词章说明来源；数据 Excel 在“命中关键词”表头批注和文件属性中保存同一说明。报告不重新扫描正文，也不读取当前采集词包；旧离线 Excel 仍直接使用文件原有的命中字段，普通声音广场导出的字段语义不随本次报告改动。

报告的模型配置、安全 Secret 引用、配置修订、规则与提示词摘要在创建时冻结。数据库 Provider 在冻结事务内由 System Owner 加行锁，与归档/删除协调；已经进入报告历史的配置禁止永久删除，尚未接管数据库配置时保留既有环境回退。代表性筛选和行动建议使用该模型；已分析内容沿用各自历史结果，不重新打标。粉丝、点赞、评论和分享指标进入筛选输入。模型输出不合法则失败关闭；过载、限流及暂时网络故障交给持久 Job 安排有界退避，成功模型输出跨重试复用。

飞书发布通过独立 Job 读取已保存文件，不重新统计或调用模型。发布原始 Word、数据 Excel、原生文档、可编辑图表 Sheet 和代表性外表/内嵌表，复用现有双向镜像。发布失败保留下载；重试复用已确认外部资源。每次外部发送前检查取消与当前 Job fence，但已经发送且结果未知的请求不能承诺远端零重复。`AIMA_FEISHU_DRY_RUN=true` 时真实发布入口关闭；管理员仍可生成和下载。

`AIMA_REPORT_ARTIFACT_RETENTION_DAYS` 默认 60 天，范围 1–3650 天，在报告创建时冻结；期限从完整产物提交开始计算。已有 Scheduler 清理器删除到期文件，保留报告历史和依据。文件写入中途失败留下的无关联 `report.output` 文件沿用一天孤儿清理窗口；有报告关联的完整文件不进入该窗口。

实现定位：

- [backend/src/aima_ugc/contracts/reports.py](../../contracts/reports.py)：管理员请求、报告历史、文件下载与模型依据契约。
- [backend/src/aima_ugc/bootstrap/report_runs_http.py](../../bootstrap/report_runs_http.py)：预检、范围校验、一致读冻结、取消和恢复。
- [backend/src/aima_ugc/adapters/persistence/postgres/report_runs.py](../../adapters/persistence/postgres/report_runs.py)：报告唯一写 Owner，保存数据、断点与文件关联。
- [backend/src/aima_ugc/bootstrap/report_runs_worker.py](../../bootstrap/report_runs_worker.py)：生成和独立发布的生产装配。
- [backend/src/aima_ugc/modules/reporting/report_jobs.py](report_jobs.py)：版本化 Payload、超时与重试注册。
- [backend/src/aima_ugc/modules/reporting/report_tables.py](report_tables.py)：ReportRun、冻结数据及报告文件关联表。
- [tests/integration/reporting/test_database_reports.py](../../../../../tests/integration/reporting/test_database_reports.py)：专用 PostgreSQL 下的完整流程、过载、取消、孤儿和过期验证；真实浏览器验收必须显式开启。

排障先通过 ReportRun ID、生成/发布 Job ID 和 request ID 关联应用 `.log`：`report.snapshot.created` 记录冻结规模，`report.llm.started/completed` 记录模型与耗时，`report.generated` / `report.published` 记录完成，`report.retry_requested` / `report.failed` 记录失败类别，通用 `job.*` 记录尝试次数及计划恢复。日志不输出 Secret、正文或原始模型响应。

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
→ GET /api/v1/data-exports/{export_id}/download
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

受理时复用 Content Query 的目标选择语句，在同一个 PostgreSQL 事务中用
`INSERT ... SELECT` 写入这些冻结项，并取得目标数量；API 不先把全部候选
加载为 Python 对象。显式选择中不可用的 Content 会被过滤，剩余项仍按
请求顺序连续编号。空选择会回滚 Export 与 Job，维持原有错误语义。

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

精确 FK、Check、Unique 直接看 [`backend/src/aima_ugc/modules/reporting/tables.py`](tables.py)。

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

具体页大小属于实现事实，以 [`backend/src/aima_ugc/bootstrap/export_worker.py`](../../bootstrap/export_worker.py) 为准，不把它当公共 Contract。

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
+ 指定版本的直接成功或合法等价 Analysis 及人工效果
+ 指定版本的有效 Brand Evidence 与派生竞品范围
+ 指定版本的有效 Vehicle Evidence
+ Comments
+ Comment Coverage
→ UnifiedDataExcelV1
```

这意味着导出同时复用多个 Owner 的**只读事实**，但只由 Reporting Owner 写 `reporting_data_*` 表。

Brand 与 Vehicle 都按 Export Item 冻结的 `content_version` 读取，不在 Worker 执行时改读 Content Current。Brand 名称稳定去重后输出，Brand Role 及 `competition_scope` 由同一批 Evidence 派生；Vehicle 名称仍按当前合并后的有效车型展示。品牌、品牌角色、竞品范围、车型是 Column Catalog v2 的可选列，未选择时不改变既有默认 Excel 表头。

---

## 7. Analysis 怎样进入导出

Export Repository 批量读取明确冻结的目标：

```text
content_id + 冻结 content_version
```

先选择该版本最新直接成功 Result；没有直接结果时读取合法输入等价引用，并使用该目标版本有效的人工相关性和维度纠正。模型、Prompt、Scheme 与分析时间仍属于真实来源 Result，不冒充当前配置执行。完整选择规则由 [`backend/src/aima_ugc/modules/analysis/README.md`](../analysis/README.md#6-analysis-为什么绑定-content-version) 维护。

如果：

- 冻结版本从未分析且没有有效引用；
- 只有旧版本 Analysis，输入变化或历史协议无法证明等价；

那么该 Content 仍可以导出，但 AI 字段为空，并计入：

```text
unanalyzed_count
```

而不是偷偷使用 stale Analysis。

报告的数据与生成依据也按同一冻结目标选择来源，分别保留目标版本和真实 Result/人工来源。后续 Current 变化、目录修改或重试不会把另一个版本的标签混入已冻结报告。

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

[`docs/appendix/06_Excel统一数据导出与离线调试.md`](../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md)

---

## 12. 当前模块文件地图

| 文件 | 职责 | 常见修改 |
| --- | --- | --- |
| [`backend/src/aima_ugc/modules/reporting/tables.py`](tables.py) | Export / Export Items 表 | 改持久化父事实或冻结目标结构 |
| [`backend/src/aima_ugc/modules/reporting/models.py`](models.py) | Reporting 内部记录模型 | 改内部 Service/Repository 返回对象 |
| [`backend/src/aima_ugc/modules/reporting/data_export_job.py`](data_export_job.py) | Job Payload / Handler / 上限 | 改 Job 版本、失败分类、Artifact 上限 |
| [`backend/src/aima_ugc/modules/reporting/http.py`](http.py) | Reporting HTTP Port/异常 | 改应用 Service 契约边界 |

生产跨目录：

- [`backend/src/aima_ugc/bootstrap/reporting_http.py`](../../bootstrap/reporting_http.py)
- [`backend/src/aima_ugc/bootstrap/export_worker.py`](../../bootstrap/export_worker.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/reporting.py`](../../adapters/persistence/postgres/reporting.py)
- [`backend/src/aima_ugc/platform/export/excel.py`](../../platform/export/excel.py)

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
→ reporting_http.py 取得共享目标选择语句
→ PostgresDataExportRepository.create() 集合冻结 ID、Version、Ordinal
→ request_snapshot
→ API Test
→ generated Client
```

Brand、Vehicle 与竞品范围筛选复用 Content Query 的同一过滤实现；因此 List、Count、Analysis query target 和 Export query target 不允许各自解释一套命中规则。

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

[`docs/appendix/01_PostgreSQL查询与调试实战.md`](../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md)

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
