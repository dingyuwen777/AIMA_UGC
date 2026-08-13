# AIMA_UGC

AIMA_UGC 是爱玛舆情监控系统的 Greenfield 重构仓库。目标是从零建立一个可长期维护、可验证、支持多人并行开发的多平台舆情系统。

## 当前状态

**Stage 1 工程基线、Stage 2 Platform 基础和 Stage 3A 数据库基础已经建立。** 当前仓库已经具备可安装 Python package、FastAPI/Vue 最小工程、固定 OpenAPI 与生成 TypeScript Client、本地前后端联调、Windows x64 开发环境引导，以及业务无关的 Config、Secret、统一日志、PostgreSQL 连接、`/health/ready`、ArtifactService/ArtifactStore、Local ArtifactStore、Alembic 首条 Revision、Artifact PostgreSQL 元数据 Repository、System Settings 和 Provider 中立 Audit 基础。

仍未进入业务功能批量开发阶段。Stage 0 的页面/角色、五平台能力矩阵、真实 Fixture、隐私/保留、容量/SLO/RPO/RTO 和 Scheduler misfire 等业务事实继续约束后续实现；下一项正式工程工作是 Stage 3B Canonical Contract。

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
- API、Worker、Scheduler、Migration 已有共用 Platform 的最小 bootstrap；Worker/Job 和正式 Scheduler 逻辑尚未实现。

Stage 2 CI 使用隔离 PostgreSQL `18.4` 验证真实连接和 readiness。Stage 3A 另有独立 PostgreSQL 18.4 Job 验证 `upgrade head → alembic check → Repository 集成 → downgrade base → upgrade head → alembic check`。这些仍只是开发/CI 基线，不等于生产镜像 variant 或 Release digest 已批准。

### Stage 3A：数据库与基础持久化

- 根目录 `alembic.ini` + `migrations/` 是 Schema 演进入口，API/Worker/Scheduler 不自动迁移；
- 首条 Revision `20260813_0001` 建立 `artifacts`、`system_settings`、`audit_events`；
- `aima_ugc.database_schema` 注册当前应用 Table，`Table.info['owner']` 是表写 Owner 机器事实；
- `artifacts` Owner=`platform`，`system_settings`/`audit_events` Owner=`system`；
- PostgreSQL Artifact Repository 使用条件更新推进 `pending → stored → linked/error`，非法状态转换关闭失败；
- System Settings 只保存非敏感 JSON 设置；Audit actor 使用 `system/principal` Provider 中立语义；
- 当前仍不实现本地登录、Session、飞书/OIDC、具体 Role/Permission Schema、API 幂等 actor 表或自动 Retention 删除。

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

`tests/integration/platform` 需要隔离 PostgreSQL 18 和对应 `AIMA_*` / Secret 配置，普通本地机器不要在未准备数据库时机械执行。

修改 HTTP Contract 后，先重新生成固定 OpenAPI 和前端 Client，再提交生成物：

```bash
uv run python scripts/contracts/generate.py
npm --prefix frontend run generate:api
```

## 系统目标架构

系统采用模块化单体，API、Worker、Scheduler 和 Migration 分进程运行。核心数据链路固定为：

```text
TikHub / 其他 Provider
→ 不可变 Raw Artifact
→ 平台 Mapper
→ Canonical Contract
→ Ingestion
→ PostgreSQL
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
→ 阶段 3B：Canonical Pydantic / JSON Schema / 固定示例
→ 阶段 4：Job Runtime
→ 阶段 5：TikHub Client 与 Raw
→ 阶段 6：先完成一个平台的端到端纵切
→ 后续阶段按蓝图逐步扩展
```

Stage 0 未全部完成不阻止 Stage 3 中与已确认技术事实直接相关的数据库/系统基础，但任何依赖产品、平台能力、隐私、容量或 Scheduler 策略的设计仍必须等待对应门禁；尤其不得直接批量实现五个平台。

## 多人协作

行为变化、新功能、多文件修改和高风险任务按 Skill 使用 `changes/active/<change-id>/CHANGE.md` 记录 Owner、分支、影响路径、Contract、数据变化和依赖；共享 Contract、Schema、Migration 和数据语义必须有明确 Owner，不允许多个分支分别猜测同一公共语义。

Git 和 CI 的具体要求以 `AGENTS.md`、Skill 和 `06` 为准。没有本轮实际执行的验证证据，不得宣称功能完成、测试通过或可发布。

## Blueprint 导航

所有领域设计入口见 [`docs/blueprint/README.md`](docs/blueprint/README.md)。

唯一初始化版本快照、Stage 1 工具链和 Stage 2 Platform 已验证决策见 [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)。