# AIMA_UGC

AIMA_UGC 是爱玛舆情监控系统的 Greenfield 重构仓库。目标是从零建立一个可长期维护、可验证、支持多人并行开发的多平台舆情系统。

## 当前状态

**Stage 1—7 的工程基线、Platform/数据库/Canonical、PostgreSQL Job Runtime、Provider Request/Attempt + Raw、Collection Run/Scope、五平台 TikHub Operation/Mapper/Ingestion，以及 Scheduler/正式 Worker 主链已经建立。** 当前仓库具备可安装 Python package、FastAPI/Vue 最小工程、固定 OpenAPI 与生成 TypeScript Client、本地前后端联调、Windows x64 开发环境引导、PostgreSQL 18 Schema/Migration、Provider/平台无关 Canonical V1 与 Provider V1 Contract，以及 `Scheduler → Occurrence → Job → Run/Scope → Provider → Raw → Mapper → Canonical → Content Owner` 的持久化执行链。

Stage 8 尚未开始。当前五平台生产实现使用同一 Collection/Content 边界，普通 CI 通过 Fake Transport + 合法脱敏 Fixture 验证，不产生付费 TikHub 请求；真实 Provider Probe 仅在明确授权和请求上限下作为外部兼容证据。当前没有请求/金额 Budget、Budget Account 或 Reservation Ledger。源码仍不能直接视为公网生产交付：Stage 8 业务 API/页面/认证授权，以及 Release 阶段的 Docker/离线发布、协调 Backup/Restore、生产镜像与恢复演练仍需后续正式门禁。

事实源规则：

- 代码、Pydantic Contract、生成 OpenAPI/Client、锁文件和测试是已落地机器事实；
- Blueprint 描述系统长期设计和尚未满足的门禁；
- 文档与机器事实冲突时，必须先判断是实现缺陷、文档过期还是新决策，再在同一任务中修正；
- 不从旧系统、历史聊天或单个文件猜测当前实现。

## 开发前必须读取

任何分析、设计、编码、Review、PR、CI 或交付任务，都从以下入口开始：

1. [`AGENTS.md`](AGENTS.md)：仓库统一开发规范和硬约束；
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](.agents/skills/reliable-vibe-coding/SKILL.md)：任务分级、Change、开发、协作和验证流程；
3. [`docs/blueprint/README.md`](docs/blueprint/README.md)：Blueprint 导航和当前阶段；
4. [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)：已确认决策、初始化版本快照和阶段 Go/No-Go；
5. 再按当前任务读取对应 Blueprint、模块 README、Contract、Migration、依赖、实现和测试。

只读取与当前任务直接相关的内容，不把整套文档机械加载为上下文。

## 已建立的工程事实

### Stage 1：工程与前端工具链

- Python `3.14.7` 由 `.python-version` 固定，uv `0.12.3` 由 `.uv-version` 固定；
- 根目录是唯一 Python/uv 工程，源码固定在 `backend/src/aima_ugc/`；
- `uv_build` 已验证 Wheel 构建、隔离安装和直接 import；
- FastAPI 已提供 `GET /health/live`；Uvicorn 是锁定运行依赖；
- Node/npm、Vue/Vite/Pinia、TypeScript 7 native + Vue SFC compatibility 类型链已锁定；
- Pydantic → FastAPI OpenAPI → Orval Fetch Client 的生成链已建立，生成物禁止手改；
- Windows x64 一键开发环境引导、本地 Uvicorn + Vite 双服务 smoke 和完整 CI 已建立。

### Stage 2：Platform 基础

当前业务无关 Platform 位于 `backend/src/aima_ugc/platform/` 和 `backend/src/aima_ugc/bootstrap/`：

- `Config`：只读取代码明确声明的 `AIMA_*` 环境变量；当前不自动加载 `.env` 或 `env.local.example`；
- `Secret`：PostgreSQL 密码只从 `<AIMA_SECRET_DIR>/postgres_password` 文件读取，不放入环境变量；
- `Logging`：API/Worker/Scheduler 使用统一北京时间毫秒日志、敏感信息脱敏和 `20 MiB × 10` gzip 轮转基础；
- `DatabaseRuntime`：同步 SQLAlchemy 2 + psycopg 3，提供真实 `SELECT 1`、Session Factory 和连接池释放，不自动建表、不自动跑 Migration；
- `GET /health/ready`：检查 PostgreSQL、Artifact 根目录和日志目录；全部可用返回 200，否则返回 503，并且不返回连接串、Secret 或原始异常；
- `ArtifactStore`：只按 `storage_key` 存取字节；Local 实现提供路径逃逸防护、同 key 不覆盖和原子写；
- `ArtifactService`：负责 ID、元数据 Port 以及 `pending → stored → linked`；Stage 3A 已用 PostgreSQL `artifacts` Table/Repository 实现正式元数据持久化；
- API、Worker、Scheduler、Migration 共用 Platform bootstrap；Stage 7 已接通 Scheduler Runtime、正式 Collection Job Registry/JobWorker 与 TikHub Scope 执行链，Worker 进程的常驻服务管理仍属于后续部署/Release 形态。

Stage 2 CI 使用隔离 PostgreSQL `18.4` 验证真实连接和 readiness。Stage 3A 另有独立 PostgreSQL 18.4 Job 验证 `upgrade head → alembic check → Repository 集成 → downgrade base → upgrade head → alembic check`。这些仍只是开发/CI 基线，不等于生产镜像 variant 或 Release digest 已批准。

### Stage 3A：数据库与基础持久化

- 根目录 `alembic.ini` + `migrations/` 是 Schema 演进入口，API/Worker/Scheduler 不自动迁移；
- 首条 Revision `20260813_0001` 建立 `artifacts`、`system_settings`、`audit_events`；
- `aima_ugc.database_schema` 注册当前应用 Table，`Table.info['owner']` 是表写 Owner 机器事实；
- `artifacts` Owner=`platform`，`system_settings`/`audit_events` Owner=`system`；
- PostgreSQL Artifact Repository 使用条件更新推进 `pending → stored → linked/error`，非法状态转换关闭失败；
- System Settings 只保存非敏感 JSON 设置；Audit actor 使用 `system/principal` Provider 中立语义；
- 当前仍不实现本地登录、Session、飞书/OIDC、具体 Role/Permission Schema、API 幂等 actor 表或自动 Retention 删除。

### Stage 3B：Canonical 数据契约 V1

- `backend/src/aima_ugc/contracts/canonical/` 是 Canonical Pydantic 唯一手写事实源；
- `contracts/canonical/` 保存确定性生成的 Content/Comment/Aggregate JSON Schema 和固定脱敏示例；
- 写入原子 Contract 为 `CanonicalContentV1` / `CanonicalCommentV1`，读取完整帖子视图为 `CanonicalContentAggregateV1`；
- TikHub、官方 API、Apify、自建采集器、文件/历史导入等均是 Canonical 之前的 Provider Adapter；
- 已批准作者/评论者方案 B：尽量保留平台明确公开的账号 ID、备用 ID、昵称/handle、主页/头像、简介、认证、地区和公开统计；
- 内容指标覆盖点赞、评论、分享、转发、收藏、浏览/播放、弹幕、投币、下载等；评论覆盖点赞/回复数；`null` 表示未知，`0` 表示明确观察到零；
- 原子 Observation 使用 `observed_fields` 支持稀疏更新；读取 Aggregate 使用 `comment_coverage` 区分评论抓全、部分、未请求和不可用；
- 数据库目标是关系化 Current + Version + Metric Observation；整棵帖子评论树只在 Query/Read Model 层组装，本阶段不创建业务表 Migration。

### Stage 4：PostgreSQL Job Runtime

- `backend/src/aima_ugc/platform/jobs/` 提供版本化 Payload Registry、Job 模型和正式 Worker；
- 第二条 Revision `20260814_0002` 建立 `jobs` 与 `job_attempt_events`，两表 Owner 均为 `platform`；
- `job_type + internal_idempotency_key` 只表达系统内部幂等，同键异 Payload 关闭失败；
- PostgreSQL Repository 支持 queued 原子 Claim、Deadline 前过期 Lease 的同 Attempt takeover、Heartbeat、Fencing、进度、重试、取消和 Reaper；
- Heartbeat 不延长 Attempt Deadline，陈旧 Lease Token 不能续租或提交终态；Attempt 事件只保存 Token SHA-256 指纹；
- Worker Handler 在数据库事务外执行，Fake Handler 通过同一正式 Worker 入口形成独立验证闭环；
- `.github/workflows/stage4-job-runtime.yml` 使用 PostgreSQL 18.4 验证 Job Runtime，以及 `base → head` 和上一正式 Revision → head 两条 Migration 路径。

Stage 4 不实现 Scheduler、Provider Request/Raw、Collection/Content 业务表或最终多级预算 Ledger。后续阶段不得为提前实现预算而建立缺少最终外键的临时表。

### Stage 5A：Provider-neutral Request/Attempt 与 Raw Artifact

- `backend/src/aima_ugc/contracts/provider/` 是 Provider Request、Attempt、费用、安全错误和 Raw Envelope 的 Pydantic V1 事实源；
- `contracts/provider/` 保存确定性生成的 Request、Attempt 和 Raw Envelope JSON Schema；
- `ProviderClient` 每个 Attempt 最多调用一次注入的 `ProviderTransport`，不隐藏自动网络重试；
- `FakeProviderTransport` 可验证成功、HTTP 429/5xx、发送前失败和发送结果未知，不访问网络、不需要 Token；
- `RawArtifactService` 递归脱敏，使用确定性 JSON + gzip，经正式 `ArtifactService + LocalArtifactStore` 保存不可覆盖 Raw，并在回放时重新校验 SHA-256、大小、gzip 和 Contract；
- 网络结果未知固定记录 `unknown` 费用和 `potential_duplicate_charge`，不承诺零重复计费；
- `.github/workflows/stage5a-provider-raw.yml` 提供独立 Provider/Raw Contract、测试与质量门禁。

Stage 5A 没有真实 Provider、平台 Operation、Mapper、Provider/Collection 数据库表、预算、Worker 注册或生产 Probe；它的独立 Raw 测试只推进 Artifact 到 `stored`，Stage 5D 的 terminal 短事务再建立 Attempt 引用并标记 `linked`。

### Stage 5B：Collection Run/Scope 父事实

- 第三条 Revision `20260814_0003` 建立 `collection_runs` 与 `collection_scopes`，两表 Owner 均为 `collection`；
- `collection_runs.job_id` 是 `jobs.id` 的非空唯一外键，一 Job 只能绑定一个 Run；
- 本阶段只支持 `manual/api/backfill`，不创建无父表支撑的 `manual_plan_id/occurrence_id`，也不接受 `scheduled`；
- `CollectionExecutionService` 预检触发类型和 Scope 身份重复，`PostgresCollectionRepository` 在调用方持有的事务中原子创建 queued Run/Scopes；
- Scope 身份由 `(run_id, platform, source_type, source_value, operation_group)` 数据库唯一约束保护；
- `.github/workflows/stage5b-collection-execution.yml` 使用 PostgreSQL 18.4 验证真实 FK/Unique、Repository、第三条 Migration 和双 downgrade/re-upgrade 路径。

Stage 5B 不实现 Plan/Occurrence/Scheduler、Collection Worker/状态转换、Provider 持久化、预算、真实网络、HTTP API 或前端。Blueprint 尚未冻结 Scope 的完整状态枚举，因此当前数据库不擅自增加白名单；创建入口只写 `queued`。

### Stage 5C：Provider 持久化基础

- 第四条 Revision `20260814_0004` 按最终 Blueprint 字段建立 `provider_requests` 与 `provider_request_attempts`；
- `provider_requests.scope_id → collection_scopes.id`、`provider_request_attempts.provider_request_id → provider_requests.id` 和可空 `raw_artifact_id → artifacts.id` 都是真实外键；
- `(scope_id, request_fingerprint)` 保护逻辑 Request 幂等，Repository 校验 Provider Request 的 Run/Platform 与 Scope 父链一致；
- `ProviderPersistenceService → PostgresProviderRepository` 只创建或读取 `pending` Request，并串行分配未发送、不计费的 `reserved` Attempt；同一 Attempt ID 重放不重复递增；
- Repository 保持 caller-owned transaction，不提交事务、不执行 Provider 或 Artifact I/O；数据库触发器冻结 Scope、Request 和 Attempt 的关键来源身份；
- `.github/workflows/stage5c-provider-persistence.yml` 使用 PostgreSQL 18.4 验证最终 FK/Unique/Check/Index/Trigger、并发 Attempt 编号、第四条 Migration 和双 downgrade/re-upgrade 路径。

Stage 5C 不实现 dispatch、网络调用、费用预留或结算、Raw 写入/关联、Artifact `linked`、Job Fencing/CAS、Reconciler、Candidate/Ingestion、HTTP API 或前端。这些执行语义属于 Stage 5D。

### Stage 5D：Provider Dispatch 与崩溃恢复

- `JobExecutionFence` 把当前 Job ID 与 Lease Token 作为内部执行凭证，Token 不进入 Payload、日志或 `repr`；
- `ProviderDispatchService` 先在短事务中验证 Fence 并 CAS `reserved → dispatching`，再于事务外调用一次正式 Provider Client，最后以短事务提交 terminal 结果；
- `completed/unknown` 先由正式 Raw/Artifact 链落盘并校验，再一次性关联 Attempt、推进 Artifact `stored → linked`；
- `ProviderAttemptReconciler` 接管遗留 `dispatching` 时优先恢复确定性路径上的完整 Raw；没有可用 Raw 才保守记为 `unknown`，不复发同一 Attempt；
- 第五条 Revision `20260814_0005` 固定 Request 状态白名单和 terminal Attempt 的一次性 Raw 关联规则；
- `.github/workflows/stage5d-provider-dispatch.yml` 使用 PostgreSQL 18.4 验证 Fencing、一次调用、Raw 恢复、无 Raw Reaper 和迁移路径。

Stage 5D 只使用不计费 Attempt 和 Fake Transport，不访问真实 Provider、不产生费用，也不包含预算 Reservation/Settlement、具体平台 Operation、Collection Job Handler、Candidate/Ingestion、HTTP API 或前端。

### Stage 6：小红书 TikHub App V2 端到端纵切

- `adapters/providers/tikhub/operations/xiaohongshu.py` 唯一定义搜索、图文/视频详情、一级/二级评论 App V2 endpoint、参数和分页停止语义；
- `adapters/providers/tikhub/mappers/xiaohongshu.py` 只把已确认 Raw/上下文映射为 Canonical Content/Comment，不发 HTTP、不读数据库；
- `collection_candidates/collection_candidate_ingestions` 保存逐项来源和每次摄取结果，数据库 Trigger 禁止 UPDATE/DELETE，成功结果必须关联 Canonical 身份和 Content/Comment 目标；
- Content Owner 关系表保存 Account、Content/Comment Current、Version、Metric Observation 与评论覆盖，`observed_fields` 控制稀疏更新，允许 `A → B → A` 形成新版本并记录指标下降；
- `collection.xhs.raw-replay.v1` Job 只接受已完成且 `linked` 的已存 Raw，通过正式 Mapper/Ingestion/Owner Repository 回放，不持有 Provider Client，因而不会为了重试再次调用外部 Provider；
- `20260814_0006`—`20260814_0009` 建立 Stage 6 表和约束；`.github/workflows/stage6-xhs-vertical-slice.yml` 验证空库、Stage 5D、首条 Stage 6 和上一条 Stage 6 Revision 到 `head` 的升级路径。

Stage 6 没有启用真实 HTTP Transport、预算 Reservation/Settlement、公开 HTTP API 或前端。2026-08-14 的受控真实搜索 Probe 只确认当前 HTTP 200 响应包装、分页会话字段和空页停止结构；实时返回项为空，非空字段映射仍以仓库中的合法脱敏 Fixture 和自动化测试为证据，不能据此宣称详情/评论或生产采集已经验收。

### Stage 7：五平台采集、计划调度与正式 Worker

- 小红书、抖音、微博、B站、快手均通过 TikHub 平台 Operation/Extractor/Mapper 进入同一 Canonical/Content Owner，不建立平台专用业务表；
- `provider_configs.secret_ref` 固定 Provider 配置与 Secret 边界，Provider Request/Attempt 保存 Billing/成本快照和潜在重复计费审计事实，但当前没有 Budget 发送门禁；
- Keyword Pack、Collection Plan/Plan Platform、Occurrence 和 `latest_only` Scheduler Runtime 已关系化持久化；
- `collection.run.v1` 正式链路由 JobWorker 驱动 `CollectionRunExecutor → TikHubCollectionScopeExecutor`，支持 Scope durable checkpoint、终态 Scope 跳过、Provider 可重试错误跨 Job Attempt 恢复；
- 遗留 `dispatching` Attempt 先由 Reconciler 校验确定性 Raw：完整 Raw 存在时直接恢复并 replay，禁止因 Worker takeover 再次发送同一 Provider 请求；
- 评论/回复 target 是跨页软目标，当前已经返回的整页全部摄取；评论采集同时记录 complete/partial/not_requested/unavailable Coverage 及 sample/sort/target/stop reason；
- Account/Content/Comment 首次并发插入由 PostgreSQL 唯一约束 + `ON CONFLICT` 收敛；较旧乱序 Observation 不覆盖较新的 Current，但仍可保留合法历史事实。

Stage 7 的真实 Provider 兼容证据由受控 Probe、合法脱敏 Fixture 与 `docs/blueprint/10`—`12` 维护；一次 HTTP 200 不等于长期稳定性承诺。Stage 8 仍是下一正式业务阶段。

## 环境、启动与部署

完整操作说明见 [`docs/环境运行与部署.md`](docs/环境运行与部署.md)。

### Windows x64：推荐一键初始化

首次开发优先直接双击：

```text
scripts\setup_dev_environment.cmd
```

它从仓库机器事实读取 Python / Node / npm / uv 目标版本，在中国大陆开发机固定使用清华 TUNA / npmmirror 国内源，并在工具版本满足后执行锁定依赖安装。旧 Python/Node 的主动卸载会先询问，默认保留；镜像失败不会静默切到境外运行时源。

### Stage 2 本地运行配置

`env.local.example` 是**示例，不会被代码自动加载**。至少需要给后端进程提供对应的 `AIMA_*` 环境变量，并创建：

```text
<AIMA_SECRET_DIR>/postgres_password
```

默认本地目录为：

```text
.runtime/data
.runtime/logs
.runtime/secrets
```

`.runtime/` 已被 Git 忽略。具体 PostgreSQL 准备和 Windows / PowerShell 注入方式见运行文档。

## 本地启动

使用两个终端，均从仓库根执行。

终端 1：

```bash
uv run uvicorn aima_ugc.entrypoints.api_main:app --host 127.0.0.1 --port 8090 --reload --reload-dir backend/src
```

终端 2：

```bash
npm --prefix frontend run dev
```

浏览器入口：

```text
http://127.0.0.1:5173/
```

存活检查不依赖数据库：

```text
http://127.0.0.1:8090/health/live
```

依赖就绪检查：

```text
http://127.0.0.1:8090/health/ready
```

`/health/ready` 只有在 PostgreSQL、Artifact 目录和日志目录都可用时返回 200；否则返回 503。

前端 Vite 继续把 `/health` 与 `/api` 代理到本地 FastAPI。两个服务启动后可以运行：

```bash
uv run python scripts/dev/check_local_stack.py
```

该 smoke 仍只验证 Stage 1 的前后端启动/代理；Stage 2 的 PostgreSQL/readiness 真实验证由 CI 的 `Stage 2 Platform` Job 负责。

## 核心质量检查

```bash
uv lock --check
uv run python -c "import aima_ugc"
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run python scripts/contracts/generate.py --check
uv run python scripts/contracts/check_compatibility.py
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
npm --prefix frontend audit --omit=dev --audit-level=high
npm --prefix frontend audit --audit-level=high
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

Platform 单元测试可独立运行：

```bash
uv run pytest tests/unit/platform -q
```

Job Registry 与正式 Worker 的纯逻辑测试可独立运行：

```bash
uv run pytest tests/unit/jobs -q
```

Provider Client、Fake Transport、Raw Artifact 与 Provider Contract 可独立运行且不需要数据库：

```bash
uv run pytest tests/unit/collection tests/integration/collection/test_raw_artifact.py tests/contracts/test_provider_v1.py -q
uv run pytest tests/unit/content tests/integration/content -q
```

Collection Run/Scope Repository 需要隔离 PostgreSQL 18、对应 `AIMA_*` / Secret 配置和最新 Migration：

```bash
uv run alembic upgrade head
uv run pytest tests/integration/collection/test_collection_repository.py -q
uv run pytest tests/integration/collection/test_provider_repository.py -q
uv run pytest tests/integration/collection/test_provider_dispatch.py -q
```

`tests/integration/collection/test_raw_artifact.py` 使用隔离目录、正式 ArtifactService 和 Local ArtifactStore，不访问网络或数据库；同目录的 Repository/Dispatch 测试和 `tests/integration/content/` 使用真实 PostgreSQL。普通本地机器不要在未准备数据库时机械执行数据库测试。Job Runtime、Collection 父事实、Provider 持久化、Dispatch/恢复、Content/Ingestion、五平台规范化与 Scheduler 的完整回归分别由 Stage 4/5/6/7 正式 Workflow 维护；Collection 恢复、Coverage、Provider retry 和 Content 并发/乱序回归也包含在对应 PostgreSQL Integration 中。统一测试入口见 [`docs/测试与调试说明.md`](docs/测试与调试说明.md)。

修改 HTTP Contract 后，先重新生成固定 OpenAPI 和前端 Client，再提交生成物：

```bash
uv run python scripts/contracts/generate.py
npm --prefix frontend run generate:api
```

## 系统目标架构

系统采用模块化单体，API、Worker、Scheduler 和 Migration 分进程运行。核心数据链路固定为：

```text
TikHub / 官方 API / Apify / 自建采集器 / 文件导入 / 其他 Provider
→ 不可变 Raw Artifact
→ 对应 Mapper
→ Canonical Contract
→ Ingestion Service
→ Owner Repository
→ PostgreSQL
→ Query Repository / Read Model
→ API / Analysis / Monitoring / Reporting
```

主要技术基线：

- Python 3.14 + FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic + psycopg 3；
- 根目录唯一 Python/uv 工程，Python 源码位于 `backend/src/aima_ugc/`；
- PostgreSQL 18 作为业务事实库和当前规模的持久化 Job 基础设施；
- Vue 3 + TypeScript + Vite + Pinia；
- Pydantic → OpenAPI/JSON Schema → TypeScript Client；
- Local ArtifactStore 为默认字节存储，可在真实需求出现后替换为 S3 类实现；
- Docker Compose 离线 Release，生产服务器不现场 `git pull` 或构建。

完整架构与目录目标见 [`docs/blueprint/01-总体架构与技术选型.md`](docs/blueprint/01-总体架构与技术选型.md)。

## 下一阶段

实施顺序由 [`docs/blueprint/06-开发约束与分阶段实施.md`](docs/blueprint/06-开发约束与分阶段实施.md) 和 `07` 的 Go/No-Go 共同约束：

```text
阶段 0：继续补齐产品、页面、五平台能力、真实 Fixture、容量/SLO/RPO/RTO 等业务事实
        ↘ 与不依赖业务选择的工作并行
阶段 1：已完成
阶段 2：Platform 基础已完成
阶段 3A：数据库/Alembic/Artifact Metadata/System/Audit 基础已完成
阶段 3B：Canonical Pydantic / JSON Schema / 固定示例已完成
阶段 4：PostgreSQL Job Runtime 已完成
阶段 5A：Provider-neutral Request/Attempt、Fake Transport 与 Raw Artifact 已建立
阶段 5B：Collection Run/Scope 父事实与第三条 Migration 已建立
阶段 5C：Provider Request/Attempt 最终表、第四条 Migration 与幂等创建已建立
阶段 5D：受 Fencing 约束的 dispatch、Raw 关联和崩溃恢复已建立
阶段 6：小红书 TikHub App V2 端到端纵切已建立
→ 阶段 7：其余平台与 Collection/Scheduler（等待对应业务决策）
→ 后续阶段按蓝图逐步扩展
```

Stage 0 未全部完成不影响已经建立的 Stage 5A—6 基础。小红书 TikHub App V2 的本次 Operation 和脱敏 Fixture 已形成 Stage 6 事实；其余平台、真实付费 Transport/预算、隐私保留、容量或 Scheduler 策略仍必须等待对应门禁，尤其不得用 Fake/空页 Probe 冒充五平台或生产兼容性验收。

## 多人协作

行为变化、新功能、多文件修改和高风险任务按 Skill 使用 `changes/active/<change-id>/CHANGE.md` 记录 Owner、分支、影响路径、Contract、数据变化和依赖；共享 Contract、Schema、Migration 和数据语义必须有明确 Owner，不允许多个分支分别猜测同一公共语义。

Git 和 CI 的具体要求以 `AGENTS.md`、Skill 和 `06` 为准。没有本轮实际执行的验证证据，不得宣称功能完成、测试通过或可发布。

## Blueprint 导航

所有领域设计入口见 [`docs/blueprint/README.md`](docs/blueprint/README.md)。

唯一初始化版本快照、Stage 1 工具链、Stage 2 Platform、Stage 3A 数据库基础、Stage 4 Job Runtime、Stage 5A—5D 和 Stage 6 已确认决策见 [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)。
