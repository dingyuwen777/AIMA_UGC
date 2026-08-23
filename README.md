# AIMA_UGC

AIMA_UGC 是爱玛 UGC 舆情采集、统一入库、AI 分析、查询、导出和后续监控/报告能力的实现仓库。

第一次接触项目，不要从某个页面或某个脚本开始猜系统。先理解当前已经打通的主链：

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

最重要的三个导航：

- [`docs/代码结构与修改导航.md`](docs/代码结构与修改导航.md)：准备改代码时从这里找文件；
- [`docs/blueprint/README.md`](docs/blueprint/README.md)：理解核心长期架构和技术边界；
- [`docs/roadmap/生产上线实施路线.md`](docs/roadmap/生产上线实施路线.md)：看当前做到哪里、还要怎么开发直到生产服务器上线。

---

## 1. 当前代码真实包含哪些模块

后端当前业务模块：

```text
backend/src/aima_ugc/modules/
├─ system/
├─ collection/
├─ content/
├─ ingestion/
├─ analysis/
└─ reporting/
```

当前代码没有正式：

```text
monitoring/
alerts/
voc/
tickets/
dashboard/
```

这些仍可以是后续 Stage 的产品方向，但不能写成已经实现。

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

外部实现主要位于：

```text
backend/src/aima_ugc/adapters/
├─ providers/tikhub/
├─ providers/imports_test/
├─ providers/tikhub_test/
├─ persistence/postgres/
├─ llm/
└─ storage/
```

---

## 2. 当前四个正式 Python 进程

| 进程 | 启动入口 | 真实装配 |
| --- | --- | --- |
| API | `backend/src/aima_ugc/entrypoints/api_main.py` | `backend/src/aima_ugc/bootstrap/api.py` |
| Worker | `backend/src/aima_ugc/entrypoints/worker_main.py` | `backend/src/aima_ugc/bootstrap/worker.py` |
| Scheduler | `backend/src/aima_ugc/entrypoints/scheduler_main.py` | `backend/src/aima_ugc/bootstrap/scheduler.py` |
| Migration | `backend/src/aima_ugc/entrypoints/migrate_main.py` | `backend/src/aima_ugc/bootstrap/migration.py` |

职责：

```text
API
→ 接收 HTTP、做短查询、创建持久 Job

Worker
→ 执行 Collection / Import / Analysis / Export 等长任务

Scheduler
→ 把到期 Plan 转成 Occurrence / Run / Job

Migration
→ 独立执行 Alembic Schema 升级
```

Scheduler 不直接请求 TikHub；API 不在 HTTP 请求中同步跑分钟级采集或大批量 AI。

---

## 3. 当前 Worker 注册了哪些长任务

真实 Registry：

```text
backend/src/aima_ugc/bootstrap/worker.py
```

当前正式 Job：

```text
collection.run.v1
ingestion.import-excel.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

主要执行器：

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

公共 Lease、Heartbeat、Deadline、Fencing、Retry、Cancel 等语义位于：

```text
backend/src/aima_ugc/platform/jobs/
```

后续新增长任务必须复用这套 Runtime，不新建第二套 task queue。

---

## 4. TikHub 当前怎么接入

正式支持五个平台：

```text
xiaohongshu
douyin
weibo
bilibili
kuaishou
```

请求构造/分页：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/
```

Provider JSON → Canonical：

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/
```

HTTP 发送：

```text
backend/src/aima_ugc/adapters/providers/tikhub/transport.py
```

Capability / Runtime：

```text
backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
backend/src/aima_ugc/adapters/providers/tikhub/runtime.py
```

真实响应与验证：

- [`docs/collection/README.md`](docs/collection/README.md)
- [`docs/appendix/TikHub五平台真实响应与字段映射.md`](docs/appendix/TikHub五平台真实响应与字段映射.md)
- [`docs/appendix/TikHub多接口验证与备用策略.md`](docs/appendix/TikHub多接口验证与备用策略.md)
- [`docs/appendix/TikHub接口选型与真实验证台账.md`](docs/appendix/TikHub接口选型与真实验证台账.md)
- `tests/fixtures/providers/tikhub/`

这类 Provider 细节已经从核心 Blueprint 下沉到 Appendix/Collection 文档，避免 Blueprint 随平台实现无限增长。

---

## 5. Excel 导入为什么和 TikHub 能共用同一套业务数据

正式 Excel 主链：

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

TikHub 和 Excel 在 Canonical 后复用 Content Owner，所以最终去重、Current/Version/Metric 和来源追溯不由两个入口各写一套数据库逻辑。

详细：

- [`docs/appendix/数据入口与统一入库实现.md`](docs/appendix/数据入口与统一入库实现.md)

人工调试：

```text
backend/src/aima_ugc/adapters/providers/imports_test/
backend/src/aima_ugc/adapters/providers/tikhub_test/
```

这些人工入口必须复用生产 Reader、Mapper、Decision、Ingestion、AI、Exporter，不复制生产逻辑。

---

## 6. Content 当前如何保存历史

领域入口：

```text
backend/src/aima_ugc/modules/content/ingestion.py
```

核心 Service：

```text
ContentIngestionService
```

主要表定义：

```text
backend/src/aima_ugc/modules/content/tables.py
backend/src/aima_ugc/modules/content/extended_tables.py
backend/src/aima_ugc/modules/content/account_tables.py
```

业务身份：

```text
Content = (platform, external_content_id)
Comment = (content_id, external_comment_id)
```

事实层：

```text
Current
→ contents / comments

稳定业务字段历史
→ content_versions / comment_versions

互动指标变化
→ content_metric_observations / comment_metric_observations

评论采集完整度
→ Coverage Observations
```

`observed_fields + field_observed_at` 防止旧 Observation 或 Search 稀疏字段错误清空新 Detail 数据。

详细：

- [`docs/blueprint/03-数据库与文件存储.md`](docs/blueprint/03-数据库与文件存储.md)
- [`backend/src/aima_ugc/modules/content/README.md`](backend/src/aima_ugc/modules/content/README.md)
- [`docs/appendix/PostgreSQL查询与调试实战.md`](docs/appendix/PostgreSQL查询与调试实战.md)

---

## 7. AI 当前怎么实现

业务代码：

```text
backend/src/aima_ugc/modules/analysis/
```

Prompt / taxonomy 唯一业务事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

当前 V3 输出：

```text
relevance
voice_type
sentiment
labels[]
```

当前 `voice_type` 机器值：

```text
user_voice
creator_marketing
brand_official
dealer_promotion
media_information
other_organization
unknown
```

真实用户发声唯一业务判断：

```text
voice_type == user_voice
```

Analysis 正式表定义：

```text
backend/src/aima_ugc/modules/analysis/tables.py
```

AI Semantic Relevance 在：

```text
analysis_content_results.relevance
```

当前 `contents` 没有平行 `is_relevant` AI 列。

详细：

- [`docs/appendix/AI舆情打标与分析实现.md`](docs/appendix/AI舆情打标与分析实现.md)
- [`backend/src/aima_ugc/modules/analysis/README.md`](backend/src/aima_ugc/modules/analysis/README.md)

---

## 8. 当前查询和前端做到哪里

后端 Content Query：

```text
backend/src/aima_ugc/bootstrap/content_http.py
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
```

它把：

```text
Content Current
+ 当前匹配 Analysis
+ 来源链
```

投影给声音广场和 Analysis 目标冻结。

当前 Vue Router：

```text
frontend/src/app/routes.ts
```

真实路由：

```text
/
/voice-plaza
/collection-runtime
/collection-strategy
```

正式 Feature：

```text
frontend/src/features/voice-plaza/
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
```

当前没有独立 Analysis/Report/Job/Settings/Dashboard 页面。后端有 API 不等于已经有独立 Vue 页面。

前端入口：

- [`frontend/README.md`](frontend/README.md)
- [`docs/guides/Figma与前端设计开发工作流.md`](docs/guides/Figma与前端设计开发工作流.md)

---

## 9. Excel Export 和 Word Report 是两套不同能力

### 正式 PostgreSQL Excel Export

```text
HTTP
→ reporting.content-export-excel.v1
→ Worker
→ platform/export/excel.py
→ Artifact
```

Owner：

```text
backend/src/aima_ugc/modules/reporting/
```

详细：

- [`docs/appendix/Excel统一数据导出与离线调试.md`](docs/appendix/Excel统一数据导出与离线调试.md)

### 离线 Markdown / Word Report

实现：

```text
backend/src/aima_ugc/platform/reporting/
```

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/generate_report.py
```

详细：

- [`docs/appendix/Word舆情报告生成与排版实现.md`](docs/appendix/Word舆情报告生成与排版实现.md)
- [`backend/src/aima_ugc/platform/reporting/README.md`](backend/src/aima_ugc/platform/reporting/README.md)

当前离线 Word Renderer 尚不是一个独立 durable Report Job/前端报告中心；是否产品化见 Roadmap Stage 10。

---

## 10. 技术版本事实

不要从历史聊天或旧文档数字猜版本。

当前工具版本事实：

```text
Python → .python-version
Node   → .node-version
uv     → .uv-version
npm    → frontend/package.json
```

依赖：

```text
Python → pyproject.toml + uv.lock
Frontend → frontend/package.json + frontend/package-lock.json
```

普通功能任务不自动升级依赖。

---

## 11. 文档怎么读

第一次进入仓库：

1. [`AGENTS.md`](AGENTS.md)
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](.agents/skills/reliable-vibe-coding/SKILL.md)
3. [`docs/代码结构与修改导航.md`](docs/代码结构与修改导航.md)
4. [`docs/blueprint/README.md`](docs/blueprint/README.md)
5. [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)
6. [`docs/roadmap/生产上线实施路线.md`](docs/roadmap/生产上线实施路线.md)
7. 再读当前模块 README、Appendix/Guide、Contract、Migration、代码和测试

文档职责：

```text
docs/blueprint/
→ README + 01—08 核心长期架构

docs/roadmap/
→ 未完成阶段、下一步、生产上线

模块 README
→ 当前实现/Owner/修改入口

docs/appendix/
→ 专题实现、字段、SQL、状态机、调试、生产部署细节

docs/guides/
→ 开发流程

docs/collection/
→ 五平台实现导航

代码 / Contract / Migration / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 已完成阶段/Change 的历史原因和验证证据
```

原 Blueprint 09—17 的当前有效内容已经由 Appendix/Guide/README 承接，历史阶段过程由 `changes/archive/` 追溯，不再作为核心 Blueprint 长期维护。

---

## 12. 当前生产上线状态

当前仓库已经具备 Internal V1-A 的最小可部署容器基础，但**完整 Production Release 仍是 No-Go**。

根目录当前已经存在：

```text
Dockerfile
compose.yaml
env.production.example
```

完整容器 Runtime 使用：

```text
env.production + compose.yaml
AIMA_HOST_ROOT
→ 本地完整 Docker：./.runtime/compose
→ 公司服务器：/data/AIMA_UGC
```

源码开发继续使用：

```text
env.local
→ scripts/dev/backend.py / frontend.py
```

Internal V1-A 已验证 bootstrap、PostgreSQL 18.4、Migration、configure、API/Worker/Scheduler、Nginx、Readiness、持久挂载、Secret File、数据库密码丢失 fail closed 与 Linux Compose Golden Path。当前下一正式单元是 **Internal V1-B：公司服务器部署与真实业务 Smoke**。

完整 Production 仍尚未闭环：

- 企业认证/后端授权与正式 HTTPS/浏览器安全入口；
- 不可变离线 Release Bundle / `images.tar`；
- 固定生产镜像 digest、Manifest、SBOM、签名/来源验证；
- PostgreSQL + Artifact 协调 Backup/Restore；
- 正式发布前 Backup、恢复与应用回滚自动化/演练；
- 生产服务器完整 Smoke/Soak/容量/安全验收。

长期生产必须保持：持久 `AIMA_HOST_ROOT=/data/AIMA_UGC` 与 `/data/AIMA_UGC/releases/<version>` 分离；服务器最终加载已验证镜像并以 `--no-build --pull never` 启动，而不是把源码现场 build 当成正式 Release。

详细路线：

- [`docs/roadmap/生产上线实施路线.md`](docs/roadmap/生产上线实施路线.md)
- [`docs/appendix/生产部署与离线Release方案.md`](docs/appendix/生产部署与离线Release方案.md)
- [`docs/环境运行与部署.md`](docs/环境运行与部署.md)

Stage 9 Monitoring/告警/VOC/工单和 Stage 10 Word 报告产品化当前不阻塞受控公司内网 V1；完整 Production 的认证、Release 完整性、持久化恢复和回滚门禁不能跳过。

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

前端准确命令看 `frontend/package.json`。

数据库 Integration 和 Migration 使用真实 PostgreSQL，不用 SQLite 冒充。

任何“已完成、可合并、可上线”的结论，都必须基于当前目标 HEAD 的新鲜验证证据；“Roadmap 写了完成”本身不是完成证明。
