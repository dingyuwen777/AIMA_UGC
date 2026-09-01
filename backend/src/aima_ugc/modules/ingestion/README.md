# Ingestion 模块

Ingestion 模块当前负责**文件导入的业务父事实、Data Import Campaign / 兼容 Import Batch、版本化 Import Job、XLSX 输入安全和导入来源账本**。

这里容易和 `content.ingestion` 混淆，所以先区分：

```text
modules/ingestion/
→ “这次文件导入从哪里来、属于哪个 Campaign/Batch、输入 Artifact/Chunk 是谁、Job 是谁、处理到哪一步、每行结果/冲突是什么”

modules/content/ingestion.py
→ “一条 Canonical Content/Comment 怎样真正写入 Current/Version/Metric”
```

文件导入最终写 `contents/comments` 仍通过 Content Owner，不在本模块另写一套业务 SQL。

当前页面主导入工作流已经是**统一 Data Import Campaign**；旧 `/api/v1/import-batches` 和 `/api/v1/historical-import-*` 继续作为兼容 Contract 保留，不能再把旧单文件 Import 写成当前唯一正式主链。

---

## 1. 当前页面主链：统一 Data Import Campaign

采集运行中心只有一个“导入数据”入口，但保留两种受控来源和两种独立写入策略：

```text
source_kind
→ local_upload：浏览器显式多选文件或选择文件夹
→ server_path：管理员批准的只读服务器目录

ingestion_policy
→ standard_observation：普通字段观测/新鲜度语义
→ historical_fill_only：只补空、不覆盖非空、差异留冲突账本
```

这两维正交：来源只决定文件如何形成 Artifact，策略只决定进入 Content Owner 后怎样写。不能因为“来自服务器”就自动变成历史补空，也不能因为“本地上传”就禁止用户显式选择历史补空。

当前主链：

```text
本地浏览器显式选择多文件/文件夹
→ 冻结安全相对路径 + byte_size 清单
→ 逐 Source Item 流式上传

或

管理员批准的只读服务器相对路径
→ 安全目录枚举 / Discover

两种来源
→ Data Import Campaign
→ Source Artifact + SHA-256
→ Snapshot / XLSX Preflight
→ 有界 Chunk Artifact
→ 全部预检成功后 ready
→ 用户显式 start
→ 低优先级、有界 Chunk Job
→ Excel Reader / Mapper
→ Canonical
→ 冻结 Keyword Pack Relevance
→ Content Owner 按 standard_observation / historical_fill_only 写入
→ 逐行终态账本 + 稀疏冲突账本
→ PostgreSQL
```

当前 HTTP/Worker：

- [`backend/src/aima_ugc/bootstrap/historical_import_http.py`](../../bootstrap/historical_import_http.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_worker.py`](../../bootstrap/historical_import_worker.py)

当前领域实现：

- [`backend/src/aima_ugc/modules/ingestion/historical_directory.py`](historical_directory.py)
- [`backend/src/aima_ugc/modules/ingestion/historical_chunk.py`](historical_chunk.py)
- [`backend/src/aima_ugc/modules/ingestion/historical_http.py`](historical_http.py)
- [`backend/src/aima_ugc/modules/ingestion/historical_jobs.py`](historical_jobs.py)
- [`backend/src/aima_ugc/modules/ingestion/historical_tables.py`](historical_tables.py)


当前 PostgreSQL：

- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py`](../../adapters/persistence/postgres/historical_import.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py`](../../adapters/persistence/postgres/historical_content.py)

当前页面：

- [`frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue`](../../../../../frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue)

完整跨模块链路：

- [`docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../../../../../docs/roadmap/03_4000万历史数据迁移实施方案.md)

---

## 2. 当前 Data Import Job

真实 Worker Registry 以：

- [`backend/src/aima_ugc/bootstrap/worker.py`](../../bootstrap/worker.py)

为准。

当前 Data Import Campaign 使用：

```text
ingestion.historical-discover.v1
→ 服务器来源目录/文件发现与 Campaign Source Item 建立

ingestion.historical-snapshot.v1
→ Source Artifact、SHA-256、XLSX 预检和有界 Chunk 冻结

ingestion.historical-import-chunk.v1
→ 真正执行一个冻结 Chunk 的业务导入并提交逐行结果
```

这些物理 Job type 沿用 `historical_*` 名称是 Stage 12 的兼容选择，不代表当前页面还有第二套“历史导入”入口。

Job 领域入口：

- [`backend/src/aima_ugc/modules/ingestion/historical_jobs.py`](historical_jobs.py)

执行器：

- [`backend/src/aima_ugc/bootstrap/historical_import_worker.py`](../../bootstrap/historical_import_worker.py)

所有 Job 继续复用公共 PostgreSQL Durable Job Runtime 的：

```text
Payload Version
幂等
Lease
Fencing Token
Heartbeat
Attempt Deadline
Cancel
Retry
Progress
Result/Error
```

历史/统一导入 Job 使用低优先级和 Campaign 冻结的有界 in-flight 窗口，不能饿死普通业务 Job。

---

## 3. Campaign、Item、Batch 与表 Owner

当前 Ingestion Owner 相关表：

```text
processing_import_batches
historical_import_campaigns
historical_import_campaign_items
processing_import_batch_identities
processing_import_batch_items
processing_import_batch_item_conflicts
```

精确定义：

```text
backend/src/aima_ugc/modules/ingestion/tables.py
backend/src/aima_ugc/modules/ingestion/historical_tables.py
migrations/versions/
```

主要职责：

```text
historical_import_campaigns
→ 一次统一导入的父事实；冻结 source_kind / ingestion_policy / 配置 / 状态 / 汇总

historical_import_campaign_items
→ source_file / chunk 等不可变执行项及 Artifact/Job/状态/行数

processing_import_batches
→ 一个实际处理 Batch；兼容单文件 Import 和 Campaign Chunk 都可形成 Batch 事实

processing_import_batch_identities
→ 本批已提交稳定身份集合，用于重试/跨 Chunk duplicate 语义

processing_import_batch_items
→ 逐行终态账本

processing_import_batch_item_conflicts
→ 仅保存必要冲突字段/哈希的稀疏冲突事实
```

这些表不拥有 Content Current。真正 Content/Author/Version/Metric 写入仍由 Content Owner 完成。

---

## 4. 服务器目录与本地上传安全边界

### 4.1 服务器来源

服务器目录能力只能访问管理员配置的批准根目录：

```text
AIMA_HISTORICAL_IMPORT_ROOT
```

HTTP 只收发批准根内相对路径；实现拒绝：

- 绝对路径；
- `..` / 根目录逃逸；
- UNC / 设备路径；
- 混合路径分隔；
- Symlink / Junction / Reparse Point；
- 把该能力扩成删除、移动、改名、下载的通用文件管理器。

目录 Cursor 只分页响应；当前单层枚举仍会收集并排序该层直接子项，因此批准根目录应层级清晰、单目录子项有界，不应直接挂海量平铺文件的通用共享盘根。

### 4.2 本地来源

浏览器只提交用户显式选择的文件/文件夹清单：

```text
safe POSIX relative path
byte_size
文件字节
```

不会取得/提交用户本机绝对路径；用户只选择一个文件时也不能扫描其父目录。

重复文件 PUT 必须和已冻结 Source Item 的文件名、大小、SHA-256 身份一致，不能借重试替换成另一份字节。

---

## 5. 不可变 Artifact、预检和 Chunk

Campaign 在业务写入前先冻结输入：

```text
Source Item
→ 原文件 Artifact
→ SHA-256
→ XLSX 安全/结构预检
→ 有界 Chunk Artifact
```

关键不变量：

- 后续业务导入只读冻结 Artifact/Chunk，不继续依赖原服务器文件或浏览器选择；
- Source Item 与 Artifact `linked` 关系按当前事务边界提交；
- 未被 Campaign Item 引用的 Source/Chunk Artifact 才进入当前孤儿生命周期清理；已引用快照不能被普通孤儿规则删除；
- 全部预检完成并满足状态门禁后 Campaign 才进入 `ready`，页面才能 start；
- 不把整个工作簿、全部 Canonical 或全部身份集合一次性放进 Python 内存。

XLSX 本身是 ZIP，仍受：

- [`backend/src/aima_ugc/modules/ingestion/xlsx_security.py`](xlsx_security.py)

保护，包括文件/请求大小、ZIP member、解压总量、单 member、压缩比和基本结构安全。具体阈值看当前代码/配置，不在 README 固化第二份数字。

---

## 6. `standard_observation` 与 `historical_fill_only`

### 6.1 `standard_observation`

继续复用：

```text
ContentIngestionService
+ PostgresCompleteContentRepository
```

普通字段级 Observation/新鲜度、Current/Version/Metric 语义。

### 6.2 `historical_fill_only`

历史补空长期规则：

```text
新身份
→ 正常创建 Current + 初始 Version

已有身份
→ Current 字段为空且历史值非空：允许填充
→ Current 非空且相同：不改 Current、不推进 freshness/last_seen_at
→ Current 非空且不同：保留 Current，记录 conflict
→ 历史值为空：不得清空 Current
```

没有可信历史观测时间时，Content 和 Author Metric 不更新 Current，也不生成伪造的“当前 Observation”。Author 粉丝数、关注数、作品数、获赞数等 Metric 不得绕过这条规则变成普通补空字段。

Historical Fill-Only 的集合式写入：

- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py`](../../adapters/persistence/postgres/historical_content.py)

不能退回逐行“先 SELECT 再 UPDATE”的 4000 万实现，也不能用外部 SQL/COPY 绕过 Mapper/Canonical/Content Owner。

当前 4000 万容量门禁只覆盖：

```text
server_path + historical_fill_only
```

不能把统一入口误写成所有来源/策略组合都通过相同规模吞吐验证。

---

## 7. 逐行账本、Duplicate、Conflict 与重试

当前已进入业务处理的行由数据库稳定身份约束终态幂等。

适用 outcome：

```text
created
filled
updated
unchanged
conflict
filtered
duplicate
invalid
failed
```

其中 `updated` 只适用于普通 `standard_observation` 等合法更新语义；历史补空不允许通过 `updated` 覆盖已有非空事实。

重要恢复规则：

- 已进入业务事务的每行 outcome 唯一约束负责重试幂等；
- 结构失败/取消但尚未逐行进入业务事务的整段行，由冻结 Chunk 行范围/row_count 形成可对账失败/取消事实，不制造海量伪行账本；
- 人工 retry 的新 Batch 使用当前集合式数据库逻辑继承前一 Batch 已提交身份集合，失败 Chunk 中跨 Chunk 重复行仍稳定为 `duplicate`；
- 同一文件按当前调度只执行最早 ready Chunk，保证跨 Chunk 身份的稳定首行胜出；不同文件可以利用有界窗口并行；
- 排队 Chunk 取消时同步收敛 Item/Batch/Campaign 终态和行数汇总，不依赖不会发生的 Worker 回调；
- 不同 Chunk 的来源 Request/Attempt 按不可变 Chunk Artifact 区分。

---

## 8. Relevance 在统一导入链哪里发生

这里的 Relevance 是**规则/关键词相关性清洗**，不是 AI Semantic Relevance。

主链：

```text
Excel Mapper
→ Canonical
→ Campaign/Batch 冻结 Keyword Pack 选择
→ effective_keywords
→ title/text OR 匹配
→ Dedup
→ Content Owner
```

关键词父事实来自 System：

```text
keyword_packs
keywords
keyword_pack_items
```

创建时冻结所选 Pack/版本/有效关键词；Worker 不在执行中途读取变化后的实时词包改变已创建 Campaign/Batch。

AI `relevance = relevant/irrelevant` 属于 Analysis Domain，导入不会自动创建 AI Job。

---

## 9. 兼容单文件 Import：`/api/v1/import-batches`

旧单文件 Import 仍是合法兼容能力，但不是当前页面主工作流。

兼容链：

```text
POST /api/v1/import-batches
→ multipart XLSX + 1—20 个 Keyword Pack
→ Input Artifact
→ processing_import_batches
→ ingestion.import-excel.v1
→ Worker
→ Excel Reader / Mapper
→ Canonical
→ 冻结关键词 Relevance
→ ContentIngestionService
→ Content Owner
→ PostgreSQL
```

生产 HTTP/Worker：

- [`backend/src/aima_ugc/bootstrap/import_http.py`](../../bootstrap/import_http.py)
- [`backend/src/aima_ugc/bootstrap/import_worker.py`](../../bootstrap/import_worker.py)

Job 领域入口：

- [`backend/src/aima_ugc/modules/ingestion/import_job.py`](import_job.py)

`ImportKeywordSelectionSnapshot` 冻结多词包执行输入；当前新建/执行 Payload 要求 `keyword_selection`，不提供旧 `relevance` 单词包 Payload 兼容字段。Worker 校验 Batch `stats.keyword_selection` 与 Job Payload 一致，不一致时关闭失败。

当前兼容 HTTP：

```text
POST /api/v1/import-batches
GET  /api/v1/import-batches
GET  /api/v1/import-batches/summary
GET  /api/v1/import-batches/{batch_id}
GET  /api/v1/jobs/{job_id}
```

Batch Cursor 与查询条件绑定，前端只原样回传 `next_cursor`。

---

## 10. 为什么文件导入不伪造 Collection Run/Scope/Candidate

TikHub 采集天然有：

```text
Run
→ Scope
→ Provider Request / Attempt
```

文件导入没有“搜索平台关键词”这种真实 Scope。

兼容单文件 Import 使用：

```text
Input Artifact
→ Processing Import Batch
→ import-parent Provider Request / Attempt
```

统一 Campaign 使用自己的：

```text
Campaign
→ Source Item / Chunk
→ Artifact / Job / Batch / Row Ledger
```

两者都不为了表结构对称伪造 Collection Run/Scope/Candidate。

兼容 `provider_requests` 的来源父级仍遵守当前数据库约束：Collection 来源与 Import Batch 来源按精确 Schema/Migration 保持互斥。统一 Campaign 的来源追溯使用 Campaign/Item/Chunk 真实关系，不强行塞进假的 Collection 父级。

---

## 11. 和 Content 模块的关系

Ingestion 不直接：

```sql
INSERT INTO contents ...
```

真正标准业务摄取入口：

```text
backend/src/aima_ugc/modules/content/ingestion.py
ContentIngestionService
```

历史批量补空同样通过 Content Owner 暴露的正式写边界，由 Postgres Historical Content 实现协调，不把 Ingestion 变成第二 Content Owner。

因此 TikHub、普通文件导入和历史补空最终继续共享：

```text
Content = (platform, external_content_id)
Comment = (content_id, external_comment_id)
```

以及 Current/Version/Metric/freshness/source lineage 的统一业务身份和所有权边界。

---

## 12. 和 `imports_test` 的关系

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/
```

默认离线模式可以：

```text
Excel
→ Canonical JSONL
→ 规则相关性
→ Dedup
→ 可选 AI
→ 共享 Excel
→ 可选 Report
```

不要求 PostgreSQL。只有显式数据库模式才进入正式数据库主链。

原则：调试入口可以方便，但不能复制生产 Reader/Mapper/AI/Exporter/Content Writer。

---

## 13. 当前文件地图

| 文件 | 作用 | 常见修改场景 |
| --- | --- | --- |
| [`backend/src/aima_ugc/modules/ingestion/tables.py`](tables.py) | 兼容 Import Batch 与 import-parent 关系 | 改 Batch Schema/来源父级约束 |
| [`backend/src/aima_ugc/modules/ingestion/import_job.py`](import_job.py) | `ingestion.import-excel.v1` Payload/Handler | 改兼容 Import Job 语义 |
| [`backend/src/aima_ugc/modules/ingestion/http.py`](http.py) | Import Batch HTTP Port/领域异常 | 改兼容入口应用层边界 |
| [`backend/src/aima_ugc/modules/ingestion/query.py`](query.py) | Import Batch Read Model | 改兼容 Batch 列表/摘要 |
| [`backend/src/aima_ugc/modules/ingestion/import_batch_cursor.py`](import_batch_cursor.py) | Import Batch Cursor | 改兼容分页安全/过期语义 |
| [`backend/src/aima_ugc/modules/ingestion/xlsx_security.py`](xlsx_security.py) | XLSX 资源安全 | 改上传/ZIP 安全边界 |
| [`backend/src/aima_ugc/modules/ingestion/historical_tables.py`](historical_tables.py) | Campaign/Item/Row/Conflict 等 Stage 12 数据事实 | 改统一导入 Schema/状态/约束 |
| [`backend/src/aima_ugc/modules/ingestion/historical_http.py`](historical_http.py) | Data Import Campaign HTTP Port/模型边界 | 改统一导入应用接口 |
| [`backend/src/aima_ugc/modules/ingestion/historical_jobs.py`](historical_jobs.py) | Discover/Snapshot/Import-Chunk Job | 改 Campaign Job Payload/Handler |
| [`backend/src/aima_ugc/modules/ingestion/historical_directory.py`](historical_directory.py) | 批准服务器目录安全访问 | 改目录枚举/路径安全 |
| [`backend/src/aima_ugc/modules/ingestion/historical_chunk.py`](historical_chunk.py) | Chunk 内部格式/冻结边界 | 改 Chunk 读写/版本 |

跨目录生产实现：

- [`backend/src/aima_ugc/bootstrap/import_http.py`](../../bootstrap/import_http.py)
- [`backend/src/aima_ugc/bootstrap/import_worker.py`](../../bootstrap/import_worker.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_http.py`](../../bootstrap/historical_import_http.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_worker.py`](../../bootstrap/historical_import_worker.py)
- [`backend/src/aima_ugc/bootstrap/manual_ingestion.py`](../../bootstrap/manual_ingestion.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py`](../../adapters/persistence/postgres/historical_import.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py`](../../adapters/persistence/postgres/historical_content.py)

---

## 14. 修改场景

### 改统一 Data Import Campaign

```text
先恢复当前 Pydantic/Schema/Job/Frontend 事实
→ historical_tables/http/jobs/directory/chunk
→ Bootstrap HTTP/Worker
→ PostgreSQL historical_import/historical_content
→ Contract/OpenAPI/generated Client（公开行为变化时）
→ Browser/API/PostgreSQL/Full-stack tests
→ Appendix/Roadmap（语义或生产门禁变化时）
```

### 增加兼容 Import Batch 字段

```text
先确认确实属于 Batch 父事实
→ tables.py
→ 新 Migration
→ Postgres Import Repository / Query
→ HTTP Contract（如果公开）
→ API/Integration Test
```

不要把 Content 业务字段塞进 Batch。

### 修改 Excel Reader/Mapper

不要从 `modules/ingestion/` 猜。沿当前生产执行器找到真实 Reader/Mapper，再修改对应 Fixture/Test。

### 修改数据库去重/Current/Version

去 Content Owner：

```text
modules/content/ingestion.py
Content PostgreSQL Repository
historical_content.py（历史批量补空专用实现）
```

不要在 Campaign/Batch 里再做第二套 Content 身份/Upsert。

### 修改 4000 万容量承诺

先看：

```text
docs/roadmap/03_4000万历史数据迁移实施方案.md
docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md
```

当前 Stage 12 **软件能力已完成**；公司服务器 500 万或经批准等效比例容量门禁、生产 4000 万实际执行/对账尚未完成。不能把代码修改和生产授权混在一起。

---

## 15. 调试

### 兼容单文件 Import

推荐查：

```text
artifacts
→ processing_import_batches
→ jobs
→ provider_requests / attempts
→ contents / content_versions
```

### Data Import Campaign

推荐查：

```text
historical_import_campaigns
→ historical_import_campaign_items
→ artifacts
→ jobs
→ processing_import_batches
→ processing_import_batch_identities
→ processing_import_batch_items
→ processing_import_batch_item_conflicts
→ contents / content_versions / metrics
```

如果页面进度/终态异常，先看 Campaign/Item/Job 持久事实，不在前端猜状态。

SQL：

[`docs/appendix/01_PostgreSQL查询与调试实战.md`](../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md)

---

## 16. 测试重点

兼容 Import：

- 非 XLSX / 损坏 ZIP / Zip Bomb 关闭失败；
- Input Artifact + Batch + Job 同事务；
- Provider Request 父级约束；
- `keyword_selection` 冻结与多词包 OR；
- Worker retry 不产生第二个业务 Content；
- Cursor 与查询条件绑定。

统一 Campaign：

- 本地/服务器来源路径安全；
- Source Artifact/SHA-256/重复上传身份；
- Campaign/Item/Chunk 状态机；
- 全量预检后才能 start；
- `source_kind` 与 `ingestion_policy` 独立；
- Historical Fill-Only 不覆盖非空 Current/Author/稳定扩展事实；
- 无可信历史时间不更新 Metric；
- 逐行账本/冲突/duplicate 幂等；
- Lease/Fencing/Cancel/Retry/低优先级有界窗口；
- Campaign 真进度；
- Browser→API→PostgreSQL→Worker→Content/Voice Plaza 的真实 Full-stack；
- Migration old→head 和实际 PostgreSQL 行为。

主要入口：

```text
tests/unit/
tests/api/
tests/integration/
frontend/e2e/
frontend/e2e-fullstack/stage12-historical-analysis.spec.ts
```

---

## 17. 深入阅读

- [`docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../../../../../docs/roadmap/03_4000万历史数据迁移实施方案.md)
- [`docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md`](../../../../../docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md)
- [`docs/appendix/06_Excel统一数据导出与离线调试.md`](../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md)
- [`docs/blueprint/02_采集系统与数据标准化.md`](../../../../../docs/blueprint/02_采集系统与数据标准化.md)
- [`docs/blueprint/03_数据库与文件存储.md`](../../../../../docs/blueprint/03_数据库与文件存储.md)
- [`docs/blueprint/04_后端任务API与前端.md`](../../../../../docs/blueprint/04_后端任务API与前端.md)
