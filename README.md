# AIMA_UGC

AIMA_UGC 是爱玛 UGC 舆情采集、统一入库、AI 分析、查询和导出的实现仓库。

如果第一次接触项目，先不要从某个页面或某个脚本开始猜系统。先记住当前生产主链：

```text
TikHub / Excel
→ 保存 Raw 或 Input Artifact
→ Reader / Operation / Mapper
→ CanonicalContentV1 / CanonicalCommentV1
→ Relevance
→ ContentIngestionService
→ PostgreSQL Content Owner
→ Current / Version / Metric / Coverage
→ Analysis / Query / Excel Export / 离线 Word Report
→ Vue 业务页面
```

这条链路的代码导航见：

- [`docs/代码结构与修改导航.md`](docs/代码结构与修改导航.md)
- [`docs/blueprint/01-总体架构与技术选型.md`](docs/blueprint/01-总体架构与技术选型.md)

---

## 1. 当前代码真实包含哪些模块

后端当前业务模块目录：

```text
backend/src/aima_ugc/modules/
├─ system/
├─ collection/
├─ content/
├─ ingestion/
├─ analysis/
└─ reporting/
```

当前代码**没有** `monitoring/`、`dashboard/` 业务模块。它们可以是后续方向，但不能在当前文档里写成已经实现。

公共基础能力主要位于：

```text
backend/src/aima_ugc/platform/
├─ config/
├─ database/
├─ jobs/
├─ logging/
├─ security/
├─ storage/
├─ export/
└─ reporting/
```

外部实现位于：

```text
backend/src/aima_ugc/adapters/
├─ providers/tikhub/
├─ providers/imports_test/
├─ persistence/postgres/
├─ llm/
└─ storage/
```

---

## 2. 当前四个正式进程

| 进程 | 启动入口 | 真实装配 |
| --- | --- | --- |
| API | `backend/src/aima_ugc/entrypoints/api_main.py` | `backend/src/aima_ugc/bootstrap/api.py` |
| Worker | `backend/src/aima_ugc/entrypoints/worker_main.py` | `backend/src/aima_ugc/bootstrap/worker.py` |
| Scheduler | `backend/src/aima_ugc/entrypoints/scheduler_main.py` | `backend/src/aima_ugc/bootstrap/scheduler.py` |
| Migration | `backend/src/aima_ugc/entrypoints/migrate_main.py` | `backend/src/aima_ugc/bootstrap/migration.py` |

职责边界：

```text
API
→ 接收 HTTP、做短查询、创建 Job

Worker
→ 执行 Collection / Import / Analysis / Export 等长任务

Scheduler
→ 把到期 Plan 转成 Occurrence / Run / Job

Migration
→ 独立执行 Alembic Schema 升级
```

Scheduler 不直接请求 TikHub；API 不在 HTTP 请求里跑长时间采集或批量 AI。

---

## 3. 当前 Worker 注册了哪些长任务

真实注册代码：

```text
backend/src/aima_ugc/bootstrap/worker.py
```

当前正式 Job 类型：

```text
collection.run.v1
ingestion.import-excel.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

对应生产执行器：

```text
Collection
→ modules/collection/collection_run_job.py
→ bootstrap/collection_scope.py

Excel Import
→ modules/ingestion/import_job.py
→ bootstrap/import_worker.py

AI Analysis
→ modules/analysis/content_analysis_job.py
→ bootstrap/analysis_worker.py

Excel Export
→ modules/reporting/data_export_job.py
→ bootstrap/export_worker.py
```

Job Runtime 的 Lease、Heartbeat、Deadline、Fencing、Retry 等公共语义位于：

```text
backend/src/aima_ugc/platform/jobs/
```

---

## 4. TikHub 当前怎么接入

TikHub 当前正式支持五个平台：

```text
xhs
 douyin
weibo
bilibili
kuaishou
```

每个平台的请求构造和分页逻辑在：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/
```

Provider JSON → Canonical 的字段映射在：

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/
```

HTTP 发送边界：

```text
backend/src/aima_ugc/adapters/providers/tikhub/transport.py
```

Capability / Runtime：

```text
backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
backend/src/aima_ugc/adapters/providers/tikhub/runtime.py
```

真实响应字段和验证证据：

- [`docs/appendix/TikHub五平台真实响应与字段映射.md`](docs/appendix/TikHub五平台真实响应与字段映射.md)
- [`docs/appendix/TikHub多接口验证与备用策略.md`](docs/appendix/TikHub多接口验证与备用策略.md)
- [`docs/appendix/TikHub接口选型与真实验证台账.md`](docs/appendix/TikHub接口选型与真实验证台账.md)
- `tests/fixtures/providers/tikhub/`

---

## 5. Excel 导入为什么和 TikHub 能共用一套业务数据

Excel 的正式主链：

```text
POST /api/v1/import-batches
→ Input Artifact
→ processing_import_batches
→ ingestion.import-excel.v1 Job
→ Import Worker
→ Excel Reader / Mapper
→ Canonical
→ Relevance
→ ContentIngestionService
→ PostgreSQL Content Owner
```

关键代码：

```text
backend/src/aima_ugc/bootstrap/import_http.py
backend/src/aima_ugc/bootstrap/import_worker.py
backend/src/aima_ugc/bootstrap/manual_ingestion.py
backend/src/aima_ugc/modules/ingestion/
backend/src/aima_ugc/modules/content/ingestion.py
```

TikHub 和 Excel 在 Canonical 之后复用同一 Content Ingestion，因此最终跨批次、跨来源去重不靠各入口各写一套 SQL。

详细实现：

- [`docs/appendix/数据入口与统一入库实现.md`](docs/appendix/数据入口与统一入库实现.md)

人工离线调试入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/
backend/src/aima_ugc/adapters/providers/tikhub_test/
```

这些入口必须复用生产 Reader、Mapper、Ingestion、AI、Exporter，不得复制业务实现。

---

## 6. Content 当前如何保存历史

Content 领域入口：

```text
backend/src/aima_ugc/modules/content/ingestion.py
```

核心类：

```text
ContentIngestionService
```

表定义主要位于：

```text
backend/src/aima_ugc/modules/content/tables.py
backend/src/aima_ugc/modules/content/extended_tables.py
```

核心业务身份：

```text
Content
= (platform, external_content_id)

Comment
= (content_id, external_comment_id)
```

主要事实层：

```text
Current
→ contents / comments

正文和稳定业务字段历史
→ content_versions / comment_versions

点赞、评论、播放等变化
→ content_metric_observations / comment_metric_observations

评论采集完整度
→ comment_coverage_observations 等 Coverage 表
```

不要把“本次 Provider 没返回字段”理解成“字段值为 0”。字段 freshness 和 `observed_fields` 负责防止旧/稀疏 Observation 错误覆盖 Current。

数据库设计与调试：

- [`docs/blueprint/03-数据库与文件存储.md`](docs/blueprint/03-数据库与文件存储.md)
- [`docs/appendix/PostgreSQL查询与调试实战.md`](docs/appendix/PostgreSQL查询与调试实战.md)

---

## 7. AI 当前怎么实现

AI 业务代码：

```text
backend/src/aima_ugc/modules/analysis/
```

唯一 Prompt / taxonomy 业务事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

核心 Service：

```text
backend/src/aima_ugc/modules/analysis/content_labeling.py
```

当前 V3 一条分析结果包含：

```text
relevance
voice_type
sentiment
labels[]
```

`voice_type` 当前合法机器值由 Contract、Prompt、Validator 和数据库约束共同保护：

```text
user_voice
creator_marketing
brand_official
dealer_promotion
media_information
other_organization
unknown
```

真实用户发声的唯一业务判断：

```text
voice_type = user_voice
```

正式持久化表定义：

```text
backend/src/aima_ugc/modules/analysis/tables.py
```

当前正式表：

```text
analysis_content_results
analysis_content_requests
analysis_content_request_items
analysis_content_label_pairs
```

AI Semantic Relevance 保存在 `analysis_content_results.relevance`。当前 `contents` 表没有平行的 `is_relevant` AI 列。

详细实现：

- [`docs/appendix/AI舆情打标与分析实现.md`](docs/appendix/AI舆情打标与分析实现.md)
- [`backend/src/aima_ugc/modules/analysis/README.md`](backend/src/aima_ugc/modules/analysis/README.md)

---

## 8. 当前查询和前端实际做到哪里

后端 Content 查询入口：

```text
backend/src/aima_ugc/bootstrap/content_http.py
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
```

这里把：

```text
Content Current
+ 当前匹配的 Analysis
+ 来源链
```

投影给声音广场和 Analysis 目标冻结。

默认列表行为会排除当前 AI Analysis 明确判定为 `irrelevant` 的内容；单条详情读取可以用于审计查看。精确行为以 `content_queries.py` 为准。

当前 Vue Router：

```text
frontend/src/app/routes.ts
```

当前实际注册的业务路由：

```text
/
/voice-plaza
/collection-runtime
/collection-strategy
```

当前正式业务 Feature 目录：

```text
frontend/src/features/voice-plaza/
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
```

因此不能把后端已经存在的 Analysis / Export / Job API 自动写成“已有独立 Vue 页面”。

前端修改导航：

- [`docs/guides/Figma与前端设计开发工作流.md`](docs/guides/Figma与前端设计开发工作流.md)
- [`docs/代码结构与修改导航.md`](docs/代码结构与修改导航.md)

---

## 9. Excel Export 和 Word Report 是两套不同能力

### 正式 PostgreSQL Excel Export

```text
HTTP
→ bootstrap/reporting_http.py
→ reporting.content-export-excel.v1 Job
→ bootstrap/export_worker.py
→ platform/export/excel.py
→ Artifact
```

正式表：

```text
reporting_data_exports
reporting_data_export_items
```

详情见：

- [`docs/appendix/Excel统一数据导出与离线调试.md`](docs/appendix/Excel统一数据导出与离线调试.md)

### 离线 Markdown / Word 舆情报告

实现目录：

```text
backend/src/aima_ugc/platform/reporting/
```

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/generate_report.py
```

详情见：

- [`docs/appendix/Word舆情报告生成与排版实现.md`](docs/appendix/Word舆情报告生成与排版实现.md)
- [`backend/src/aima_ugc/platform/reporting/README.md`](backend/src/aima_ugc/platform/reporting/README.md)

---

## 10. 技术版本事实

当前运行版本不要从文档中的历史数字猜，优先看锁定文件。

当前仓库：

```text
Python: .python-version = 3.14.7
Node:   .node-version   = 24.19.0
uv:     .uv-version     = 0.12.3
```

Python 依赖：

```text
pyproject.toml
uv.lock
```

前端依赖：

```text
frontend/package.json
frontend/package-lock.json
```

发现上游新版本不等于本项目应该立即升级；依赖升级需要单独任务和完整兼容验证。

---

## 11. 文档怎么读

### 第一次接触代码

推荐顺序：

1. [`AGENTS.md`](AGENTS.md)
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](.agents/skills/reliable-vibe-coding/SKILL.md)
3. [`docs/代码结构与修改导航.md`](docs/代码结构与修改导航.md)
4. [`docs/blueprint/README.md`](docs/blueprint/README.md)
5. [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)
6. 再读目标模块 README、Contract、Migration、实现和测试

### 文档职责

```text
docs/blueprint/
→ 长期架构、为什么这样设计、哪些边界不能随便改

模块 README
→ 当前模块代码结构、主要类/函数、修改入口

docs/appendix/
→ 具体专题实现、真实字段、SQL、状态机、调试和操作

docs/guides/
→ 开发流程，例如 Figma → Frontend

docs/collection/
→ 五个平台当前采集能力、Operation、Mapper、Fixture 入口

docs/代码结构与修改导航.md
→ 常见开发任务应该改哪些文件、跑哪些测试

代码 / Contract / Migration / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 历史为什么这样改
```

---

## 12. 当前明确不要写成“已经完成”的能力

当前代码事实不能证明以下能力已经完整闭环：

- 企业登录 / 正式认证授权；
- 完整离线生产 Release 流程；
- PostgreSQL + Artifact 协调 Backup/Restore 写屏障；
- `monitoring` 领域的告警、VOC、工单等正式模块；
- 独立 `dashboard` 业务模块。

如果后续实现这些能力，必须用当时的代码、Contract、Migration 和测试同步文档。

---

## 13. 常用验证入口

后端常用：

```bash
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
python scripts/quality/check_architecture.py
python scripts/quality/check_table_ownership.py
python scripts/quality/scan_secrets.py
python scripts/quality/check_docs.py
```

前端准确命令以 `frontend/package.json` 为准。

数据库 Migration 测试和 PostgreSQL Integration 不使用 SQLite 冒充真实行为。

所有“已修复、已完成、可合并”的结论，都要基于当前分支最新 HEAD 的新鲜验证和 CI。
