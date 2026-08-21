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
→ multipart XLSX 安全校验
→ Input Artifact
→ processing_import_batches
→ ingestion.import-excel.v1 Job
→ Worker
→ Excel Reader / Mapper
→ Canonical
→ Relevance
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

[`../../../../../docs/appendix/数据入口与统一入库实现.md`](../../../../../docs/appendix/数据入口与统一入库实现.md)

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
→ 行数等运行统计

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
用户上传 Excel
→ API 保存 Input Artifact
→ 同事务创建 Batch + Job
→ 202 Accepted
→ Worker 根据 job_id 反查唯一 Batch
→ 读取 Batch 的 input_artifact_id
→ 执行正式导入
→ 更新 Batch stats / status
→ Job 进入终态
```

Job Payload 不需要复制文件路径、Secret 或所有 Batch 字段；业务关系由数据库 FK 维护。

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

列表 Cursor 会绑定查询条件，前端只原样回传 `next_cursor`，不解析内部结构。

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
→ 全局 Relevance Snapshot
→ 匹配/过滤
→ Dedup
→ Content Ingestion
```

全局配置来自 System 的：

```text
global_relevance_config
keyword_packs / keywords / keyword_pack_items
```

Import 创建时冻结实际 Pack/Config/有效关键词，不让 Worker 运行到一半读取到一套新配置。

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

[`../../../../../docs/appendix/PostgreSQL查询与调试实战.md`](../../../../../docs/appendix/PostgreSQL查询与调试实战.md)

如果文件阶段成功但数据库没内容，重点看：

```text
Batch stats
→ Request/Attempt
→ Relevance 是否过滤
→ Dedup
→ Content Ingestion
```

---

## 14. 测试重点

- 非 XLSX / 损坏 ZIP / Zip Bomb 关闭失败；
- Input Artifact + Batch + Job 同事务关系；
- `provider_requests` 来源父级恰好一个；
- Worker retry 不产生第二个业务 Content；
- Rule Relevance 使用冻结 Snapshot；
- Excel/TikHub 同身份最终收敛；
- Cursor 与查询条件绑定；
- Migration old→head / downgrade-upgrade（适用时）。

主要测试入口：

```text
tests/unit/
tests/api/
tests/integration/
```

---

## 15. 深入阅读

- [`../../../../../docs/appendix/数据入口与统一入库实现.md`](../../../../../docs/appendix/数据入口与统一入库实现.md)
- [`../../../../../docs/appendix/Excel统一数据导出与离线调试.md`](../../../../../docs/appendix/Excel统一数据导出与离线调试.md)
- [`../../../../../docs/blueprint/02-采集系统与数据标准化.md`](../../../../../docs/blueprint/02-采集系统与数据标准化.md)
- [`../../../../../docs/blueprint/03-数据库与文件存储.md`](../../../../../docs/blueprint/03-数据库与文件存储.md)
- [`../../../../../docs/blueprint/04-后端任务API与前端.md`](../../../../../docs/blueprint/04-后端任务API与前端.md)
