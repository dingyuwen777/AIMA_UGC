# Ingestion 模块

Ingestion 模块当前负责**文件导入的业务父事实、Import Job 和 XLSX 输入边界**。

这里容易和 `content.ingestion` 混淆，所以先区分：

```text
modules/ingestion/
→ “这次 Excel 导入是什么、输入文件是谁、Job 是谁、处理到哪一步”

modules/content/ingestion.py
→ “一条 Canonical Content/Comment 怎样真正写入 Current/Version/Metric”
```

Excel 最终写 `contents/comments` 仍通过 Content Owner，不在本模块另写一套业务 SQL。

---

## 1. 当前正式 Excel 主链

```text
POST /api/v1/import-batches
→ multipart XLSX + Keyword Pack 选择安全校验
→ Input Artifact
→ processing_import_batches
→ ingestion.import-excel.v1 Job
→ Worker
→ Excel Reader / Mapper
→ Canonical
→ 冻结关键词选择 Relevance
→ ContentIngestionService
→ Content Owner Repository
→ PostgreSQL
```

生产 HTTP：

```text
backend/src/aima_ugc/bootstrap/import_http.py
```

生产 Worker：

```text
backend/src/aima_ugc/bootstrap/import_worker.py
```

手工复用装配：

```text
backend/src/aima_ugc/bootstrap/manual_ingestion.py
```

详细跨模块链路：

[`../../../../../docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)

---

## 2. 为什么 Excel 需要 Import Batch，而不是假 Collection Run

TikHub 采集天然有：

```text
Run
→ Scope
→ Provider Request / Attempt
```

Excel 没有“搜索一个平台关键词”这种真实 Scope。如果为了复用 Collection 表而硬造一个假的 Run/Scope，会让来源事实失真。

因此当前 File Import 使用：

```text
Input Artifact
→ Processing Import Batch
→ import-parent Provider Request / Attempt
→ Excel Reader / Mapper
→ Canonical
→ Content Ingestion
```

这让 Excel 也能复用 Provider Request/Attempt/Artifact 的来源追溯，但不会伪造 Collection 行为。

---

## 3. `processing_import_batches` 当前保存什么

表定义：

```text
backend/src/aima_ugc/modules/ingestion/tables.py
```

当前字段职责：

```text
id
→ Batch 身份

input_artifact_id
→ 原始 XLSX Artifact

job_id
→ 正式 Import Job；同步人工入口允许为空

status
→ processing / succeeded / failed 的数据库父事实

stats JSONB
→ 行数等运行统计，以及本批冻结的关键词选择快照

error_summary
→ 安全错误摘要

created_at / started_at / finished_at
→ 生命周期时间
```

精确列、FK、Check Constraint 直接看 `tables.py` 和对应 Migration，不在 README 复制第二套 DDL。

当前 `processing_import_batches` 不保存：

- 标题/正文；
- 平台内容 ID；
- AI 标签；
- 每条内容的 Current；
- TikHub Run/Scope 的平行副本。

---

## 4. Provider Request 如何同时支持 Collection 和 File Import

`provider_requests` 当前来源父级恰好一个：

```text
Collection 来源
→ scope_id IS NOT NULL
→ import_batch_id IS NULL

File Import 来源
→ scope_id IS NULL
→ import_batch_id IS NOT NULL
```

这个约束由：

```text
backend/src/aima_ugc/modules/ingestion/tables.py
```

在当前 metadata 中注册，并由 Migration 建立数据库事实。

这样可以追溯：

```text
Content Version
→ Provider Attempt
→ Provider Request
→ Import Batch
→ Input Artifact
```

而不用制造假的 Collection Scope。

---

## 5. 正式 `ingestion.import-excel.v1` Job

Job 领域入口：

```text
backend/src/aima_ugc/modules/ingestion/import_job.py
```

Worker Registry 接线：

```text
backend/src/aima_ugc/bootstrap/worker.py
```

执行器：

```text
backend/src/aima_ugc/bootstrap/import_worker.py
```

白话流程：

```text
用户上传 Excel + 选择 1—20 个 Keyword Pack
→ API 冻结 pack id/version 与 effective_keywords
→ API 保存 Input Artifact
→ 同事务创建 Batch + Job
→ 202 Accepted
→ Worker 根据 job_id 反查唯一 Batch
→ 读取 Batch 的 input_artifact_id 与冻结关键词选择
→ 执行正式导入
→ 更新 Batch stats / status
→ Job 进入终态
```

当前新建和执行的 Job Payload 都要求 `keyword_selection`，并使用 `ImportKeywordSelectionSnapshot` 冻结多词包执行输入；当前 Payload 不提供旧 `relevance` 单词包兼容字段。Worker 还会校验 Batch `stats.keyword_selection` 与 Job Payload 完全一致，不一致时关闭失败。Job Payload 不复制文件路径、Secret 或所有 Batch 字段；业务关系由数据库 FK 维护。

---

## 6. XLSX 安全边界

`.xlsx` 本质是 ZIP。看起来只有几十 MB 的恶意文件，解压后可能膨胀到非常大。

当前安全实现：

```text
backend/src/aima_ugc/modules/ingestion/xlsx_security.py
```

保护包括：

- multipart/body 上限；
- XLSX 文件大小；
- ZIP member 数量；
- 单 member 解压大小；
- 总解压大小；
- 压缩比；
- 基本 XLSX 结构合法性。

具体阈值直接看代码，因为这类数字可能随安全策略调整；文档重点记录为什么存在和修改入口。

修改这些上限时必须同步：

```text
xlsx_security.py
bootstrap/api.py 的 multipart 接收边界
API Test
环境/运维文档（如果影响用户上传限制）
```

---

## 7. Import Batch 查询和 Cursor

领域/HTTP 边界：

```text
http.py
query.py
import_batch_cursor.py
```

生产 Service：

```text
backend/src/aima_ugc/bootstrap/import_http.py
```

当前 HTTP：

```text
POST /api/v1/import-batches
GET  /api/v1/import-batches
GET  /api/v1/import-batches/summary
GET  /api/v1/import-batches/{batch_id}
GET  /api/v1/jobs/{job_id}
```

`POST /api/v1/import-batches` 的 multipart 必须包含一个 `file`，以及重复字段形式提交的 1—20 个不重复 `keyword_pack_ids`。列表 Cursor 会绑定查询条件，前端只原样回传 `next_cursor`，不解析内部结构。

精确字段：

```text
backend/src/aima_ugc/contracts/http.py
contracts/openapi/openapi.json
```

---

## 8. Relevance 在导入链哪里发生

这里的 Relevance 是**规则/关键词相关性清洗**，不是 AI Semantic Relevance。

正式主链：

```text
Excel Mapper
→ Canonical
→ 用户选择 1—20 个已启用 Keyword Pack
→ API 冻结每个 pack id/version
→ 合并并按现有 Relevance 匹配身份去重 effective_keywords
→ title/text 任一关键词 OR 匹配
→ Dedup
→ Content Ingestion
```

关键词父事实来自 System 的：

```text
keyword_packs / keywords / keyword_pack_items
```

Import 创建时冻结本次实际选择的 Pack 版本和有效关键词；后续即使管理员修改词包，已排队 Worker 也继续按创建时快照执行。Excel Import 不再从 `global_relevance_config` 推导本次筛选词包；全局 Relevance 配置仍服务于其现有 Collection 等语义，不因本次导入选择而被改写。

AI 的 `relevance = relevant/irrelevant` 属于 `analysis_content_results`，不要和这里混在一起。

---

## 9. 和 `imports_test` 的关系

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

不要求 PostgreSQL。

只有显式数据库模式才进入正式数据库主链。

原则：

> 调试入口可以方便，但不能复制生产 Reader/Mapper/AI/Exporter/Content Writer。

`imports_test/README.md` 是人工运行的详细说明；系统长期数据边界仍以本 README + Appendix + 生产代码为准。

---

## 10. 和 Content 模块的关系

本模块不会自己写：

```sql
INSERT INTO contents ...
```

真正业务摄取入口：

```text
backend/src/aima_ugc/modules/content/ingestion.py
ContentIngestionService
```

因此 Excel 与 TikHub 最终共享：

```text
(platform, external_content_id)
```

的 Content 身份，以及同一套：

```text
Current
Version
Metric Observation
field freshness
source lineage
```

规则。

---

## 11. 当前文件地图

| 文件 | 作用 | 常见修改场景 |
| --- | --- | --- |
| `tables.py` | Import Batch + import-parent Provider Request 结构 | 改 Batch Schema/来源父级约束 |
| `import_job.py` | Job Payload/Handler | 改 Import Job 版本或 Handler 语义 |
| `http.py` | HTTP Port/领域异常 | 改应用层接口边界 |
| `query.py` | Batch Read Model | 改列表/摘要领域投影 |
| `import_batch_cursor.py` | Batch Cursor 编解码 | 改分页安全/过期语义 |
| `xlsx_security.py` | XLSX 资源安全 | 改上传/ZIP 安全边界 |

跨目录生产实现：

```text
bootstrap/import_http.py
bootstrap/import_worker.py
bootstrap/manual_ingestion.py
adapters/persistence/postgres/
```

---

## 12. 修改场景

### 增加 Import Batch 字段

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

不要从 `modules/ingestion/` 猜。先沿生产执行器找到实际 Reader/Mapper，再修改对应 Fixture/Test。

### 修改数据库去重

去 Content Owner：

```text
modules/content/ingestion.py
Content PostgreSQL Repository
```

不是在 Import Batch 里做第二套跨批次 Upsert。

---

## 13. 调试一批 Excel

推荐查：

```text
1. artifacts              → 输入文件是否保存
2. processing_import_batches
3. jobs
4. provider_requests       → import_batch_id
5. provider_request_attempts
6. contents / content_versions
```

SQL：

[`../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md`](../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md)

如果文件阶段成功但数据库没内容，重点看：

```text
Batch stats.keyword_selection
→ Request/Attempt
→ Rule Relevance 是否过滤
→ Dedup
→ Content Ingestion
```

---

## 14. 测试重点

- 非 XLSX / 损坏 ZIP / Zip Bomb 关闭失败；
- Input Artifact + Batch + Job 同事务关系；
- `provider_requests` 来源父级恰好一个；
- Worker retry 不产生第二个业务 Content；
- Rule Relevance 使用冻结的多词包 Selection Snapshot；
- 多个所选词包按有效关键词并集执行 title/text OR 匹配；
- 当前 Job Payload 拒绝缺少 `keyword_selection` 或携带旧 `relevance` 字段的 Payload；
- Excel/TikHub 同身份最终收敛；
- Cursor 与查询条件绑定；
- Migration old→head / downgrade-upgrade（适用时）。

主要测试入口：

```text
tests/unit/
tests/api/
tests/integration/
frontend/e2e-fullstack/
```

---

## 15. 深入阅读

- [`../../../../../docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md`](../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md)
- [`../../../../../docs/blueprint/02_采集系统与数据标准化.md`](../../../../../docs/blueprint/02_采集系统与数据标准化.md)
- [`../../../../../docs/blueprint/03_数据库与文件存储.md`](../../../../../docs/blueprint/03_数据库与文件存储.md)
- [`../../../../../docs/blueprint/04_后端任务API与前端.md`](../../../../../docs/blueprint/04_后端任务API与前端.md)

---

## 16. 统一数据导入 Campaign

采集运行中心只有一个“导入数据”入口，但保留两种受控来源和两种独立写入策略：

```text
本地浏览器显式选择多文件/文件夹
→ 冻结相对路径 + byte_size 清单
→ 逐 Item 流式上传

管理员批准的只读服务器相对路径
→ Worker 枚举与快照

两种来源
→ Data Import Campaign（物理表沿用 historical_import_* 名称）
→ 原文件 Artifact + SHA-256
→ 流式 XLSX 转有界 Chunk Artifact
→ 全部预检后 ready
→ 用户显式 start
→ 低优先级有界 Chunk Job
→ Content Owner 按 Campaign 冻结的 standard_observation / historical_fill_only 执行
→ 逐行终态与稀疏冲突账本
```

相关模块：

```text
historical_http.py / historical_jobs.py / historical_tables.py
historical_directory.py / historical_chunk.py
bootstrap/historical_import_http.py
bootstrap/historical_import_worker.py
adapters/persistence/postgres/historical_import.py
adapters/persistence/postgres/historical_content.py
```

服务器目录 HTTP 只收发相对路径；目录实现拒绝路径逃逸和所有链接组件。本地清单同样只接受安全 POSIX 相对路径，不接收本机绝对路径；重复文件 PUT 必须与已冻结 Artifact 的文件名、大小和 SHA-256 一致。Source Item 绑定和 Artifact `linked` 状态同事务提交。页面可在刷新后从 Campaign 历史重新进入详情；若本地上传中断，可直接取消 `uploading` Campaign，尚未预检的 Source Item 与 Campaign 会在同一事务进入 `cancelled`，不等待 Worker。源文件通过 Manifest/SHA-256 校验后，Source Artifact 会在流式解析前绑定 source_file Item；同一技术 Job 重试复用它。未建立 Campaign Item 引用的 Source/Chunk Artifact 按 1 天孤儿规则回收，已引用快照不会被该规则删除。历史 Job 的 priority 为低优先级，in-flight 窗口由 Campaign 创建时冻结；不同文件可以占用窗口并行，同一文件只调度最早的一个 ready Chunk，保证跨 Chunk 重复身份仍由稳定首行胜出。已进入业务事务的每行 outcome 唯一约束负责重试幂等；结构失败或取消、尚未进入事务的整段行由不可变 Chunk 的冻结行范围作为终态并计入 `failed`，不生成无意义的大量伪账本。人工重试的新 Batch 用集合式 `INSERT ... SELECT` 继承前一 Batch 已提交的身份集合，保证失败 Chunk 中的跨 Chunk 重复行仍为 `duplicate`。不同 Chunk 的来源 Request/Attempt 按不可变 Chunk Artifact 区分。排队 Chunk 取消时会同步收敛 Item/Batch/Campaign 终态和行数汇总，不依赖不会发生的 Worker 回调。

目录 Cursor 只对响应分页；当前单次目录读取仍先收集并排序该层的全部直接子项。部署时应给历史迁移配置专用、层级清晰且单目录子项有界的批准根目录，不应直接挂载拥有海量直接子项的通用共享盘根。source_file 另有 `campaign_id + relative_path + manifest_identity` 条件唯一索引，避免 `ordinal IS NULL` 使普通唯一约束失效后在并发重试中产生重复源文件事实。

没有可信历史观测时间时，Content 和 Author Metric 都不会更新 Current 或生成 Observation。Author 的粉丝数、关注数、作品数和获赞数会在历史 Canonical 输入进入 Fill-Only 前剥离，不能绕过 Metric 规则变成普通字段。

`standard_observation` 继续复用 `ContentIngestionService + PostgresCompleteContentRepository` 的普通业务语义；`historical_fill_only` 使用集合式批量路径。当前 4000 万容量门禁只覆盖服务器来源的历史补空组合，不能把标准观测组合写成已经通过相同规模验证。旧 `/api/v1/import-batches` 和 `/api/v1/historical-import-*` 只作为兼容 Contract 保留，前端主入口使用 `/api/v1/data-import-*`。

完整运行、容量和 Go/No-Go 见：

[`../../../../../docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md`](../../../../../docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md)
