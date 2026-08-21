# Ingestion 模块

Ingestion 模块当前最重要的职责是：**把一个上传的 Excel 文件变成一次可追踪、可恢复的正式 Import Batch。**

这里的 `ingestion` 不等于 Content Owner 里的“把 Canonical 写进内容表”。它主要拥有 File Import 的父事实和正式 `ingestion.import-excel.v1` Job；真正的帖子/评论 Current、Version、Metric 最终仍由 Content Owner 写入。

## 1. 为什么 Excel 导入需要单独的 Import Batch

TikHub 正式采集天然有：

```text
Run
→ Scope
→ Provider Request / Attempt
```

Excel 文件没有真实的“搜索 Run/Scope”。如果为了复用表结构硬造一个假的 Collection Run，会让来源追溯变得不真实。

所以当前 File Import 使用：

```text
Input Artifact
→ Processing Import Batch
→ import-parent Provider Request / Attempt
→ Excel Reader / Mapper
→ Canonical
→ Relevance
→ Content Ingestion / Owner
→ PostgreSQL
```

## 2. 当前数据库父事实

表：

```text
processing_import_batches
```

当前字段只包括这类父级信息：

- `input_artifact_id`：用户上传的原始 Excel Artifact；
- `job_id`：正式 Import Job；
- `status`；
- `stats`：运行统计 JSONB；
- `error_summary`；
- 创建/开始/完成时间。

精确字段以 `tables.py` 和 `migrations/versions/20260820_0019_stage8a_manual_ingestion.py` 为准。

不要在 README 里再维护一份完整 DDL。

## 3. Provider Request 为什么也可以属于 Import Batch

Stage 8A Migration 让 `provider_requests` 的来源父级变成“恰好一个”：

```text
Collection 来源
→ scope_id 有值
→ import_batch_id 为空

File Import 来源
→ scope_id 为空
→ import_batch_id 有值
```

这样 File Import 可以复用 Request/Attempt/Artifact 来源账本，同时不伪造 Collection Scope。

## 4. 正式 Job

当前 Job 类型：

```text
ingestion.import-excel.v1
```

主要代码：

```text
import_job.py
```

Job 由 API 创建后交给 Worker 执行。Router 不在上传 HTTP 请求里同步处理整个 Excel。

白话流程：

```text
用户上传 .xlsx
→ API 校验文件和资源限制
→ 保存 Input Artifact
→ 创建 Import Batch + Job
→ 202 返回
→ Worker 后台读文件/映射/入库
→ 更新 Batch stats / status
```

## 5. XLSX 安全为什么单独做

`.xlsx` 本质上是 ZIP 包。一个看起来很小的文件，解压后可能非常大，也可能包含异常数量的成员。

当前 `xlsx_security.py` 会限制：

- multipart body 大小；
- Excel 文件大小；
- ZIP member 数量；
- 单 member 解压大小；
- 总解压大小；
- 压缩比。

这些限制是为了防止超大上传和 Zip Bomb，不是普通业务字段校验。

具体阈值以代码为准，README 不复制一份容易过期的数字表。

## 6. Batch 查询和 Cursor

当前模块已有：

```text
query.py
import_batch_cursor.py
http.py
```

Import Batch 可以通过正式 HTTP 查询列表、摘要和详情；列表 Cursor 使用查询绑定的签名语义，前端只原样保存/回传，不自己解析业务内容。

精确 URL 和 Response 字段见：

- `docs/API接口说明.md`；
- `contracts/openapi/openapi.json`；
- 生成 TypeScript Client。

## 7. 和 `imports_test` 的关系

`imports_test` 是人工/离线调试入口。

默认可以只做：

```text
Excel 读取
→ 清洗/去重
→ 可选 AI
→ Excel/报告
```

而不连接 PostgreSQL。

显式数据库模式才进入正式 Import Batch / Provider Request/Attempt / Content Ingestion 主链。

原则：

> 调试入口复用生产实现，但默认不产生生产副作用。

## 8. 和 Content 模块的关系

Ingestion 模块不直接拥有 `contents` / `comments`。

```text
Excel Reader / Mapper
→ Canonical
→ Relevance
→ Content Ingestion Service
→ Content Owner Repository
```

因此：

- Excel 不自己写一套 `INSERT contents`；
- File Import 和 TikHub 最终共享稳定 `(platform, external_content_id)` 内容身份；
- Current/Version/Metric 的规则只维护一套。

## 9. 当前代码入口

| 能力 | 文件 |
| --- | --- |
| Import Batch 领域记录 | `__init__.py` |
| HTTP 边界 | `http.py` |
| Batch Cursor | `import_batch_cursor.py` |
| Job Payload/Handler | `import_job.py` |
| Query 模型/服务 | `query.py` |
| PostgreSQL Table | `tables.py` |
| XLSX 资源安全 | `xlsx_security.py` |

正式 PostgreSQL Repository、API 装配和 Worker Executor 还会跨到 `adapters/persistence/postgres/`、`bootstrap/api.py`、`bootstrap/worker.py` 等位置；修改时按调用链继续读取，不要只看本目录。

## 10. 测试重点

- 非 `.xlsx` / 损坏 ZIP / 资源上限拒绝；
- Input Artifact 与 Batch/Job 原子关系；
- `provider_requests` 恰好一个来源父级；
- Import Job retry/恢复不重复产生业务副作用；
- Relevance 与 TikHub 使用同一正式服务；
- 同一外部内容跨 Excel/TikHub 最终收敛到同一 Content Current；
- Batch Cursor 与查询条件绑定；
- Migration 0019 old→head / downgrade 安全边界。

## 11. 深入阅读

- 统一入口：[`../../../../../docs/appendix/数据入口与统一入库.md`](../../../../../docs/appendix/数据入口与统一入库.md)
- Excel 离线处理：[`../../../../../docs/appendix/Excel导入导出与离线处理.md`](../../../../../docs/appendix/Excel导入导出与离线处理.md)
- 数据主链：[`../../../../../docs/blueprint/02-采集系统与数据标准化.md`](../../../../../docs/blueprint/02-采集系统与数据标准化.md)
- 数据库：[`../../../../../docs/blueprint/03-数据库与文件存储.md`](../../../../../docs/blueprint/03-数据库与文件存储.md)
- API/Job：[`../../../../../docs/blueprint/04-后端任务API与前端.md`](../../../../../docs/blueprint/04-后端任务API与前端.md)
