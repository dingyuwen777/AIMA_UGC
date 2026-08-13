---
schema: rvc-change/v1
id: CHG-20260813-stage2-platform-foundation
title: Stage 2 Platform 基础能力
level: L3
status: done
owner: dingyuwen777
branch: feature/stage2-platform-foundation
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [platform, api, toolchain, developer-experience]
affected_paths: [backend/src/aima_ugc/platform/, backend/src/aima_ugc/bootstrap/, backend/src/aima_ugc/entrypoints/, backend/src/aima_ugc/adapters/storage/local/, tests/unit/platform/, tests/integration/platform/, tests/api/test_health.py, .github/workflows/ci.yml, env.local.example, README.md, docs/环境运行与部署.md, docs/blueprint/README.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md]
contracts: [GET /health/ready]
data_changes: []
---

# 结果

Stage 2 Platform 已完成并合并到 `main`。建立了后续 Stage 3/4/5 共用的业务无关运行基础：

- 显式 `AIMA_*` Config；
- PostgreSQL Secret 只读文件边界；
- API/Worker/Scheduler 统一北京时间毫秒 `.log`、脱敏和 `20 MiB × 10` gzip 轮转；
- 同步 SQLAlchemy 2 + psycopg 3 `DatabaseRuntime`；
- `GET /health/ready`；
- `ArtifactService` / `ArtifactMetadataPort` / `ArtifactStore` 与 Local ArtifactStore；
- API、Worker、Scheduler、Migration 共用的最小 Platform bootstrap；
- 隔离 PostgreSQL 18.4 的 Stage 2 CI。

按用户要求，本 Change **没有处理 `main` Branch Protection**。

# 固定边界

## Config / Secret

```text
AIMA_DATA_DIR=.runtime/data
AIMA_LOG_DIR=.runtime/logs
AIMA_SECRET_DIR=.runtime/secrets
AIMA_LOG_LEVEL=INFO
AIMA_LOG_MAX_BYTES=20971520
AIMA_LOG_BACKUP_COUNT=10
AIMA_LOG_COMPRESS=true
AIMA_DB_HOST=127.0.0.1
AIMA_DB_PORT=5432
AIMA_DB_NAME=aima_ugc
AIMA_DB_USER=aima_ugc
AIMA_DB_CONNECT_TIMEOUT_SECONDS=3
```

`env.local.example` 只是示例，不自动加载。PostgreSQL 密码固定从 `<AIMA_SECRET_DIR>/postgres_password` 读取；Secret Reader 限制普通文件、大小、UTF-8、NUL 和空值，异常不回显 Secret 内容。

## Database / readiness

- 同步 SQLAlchemy Engine + psycopg；Engine 惰性创建；
- `ping()` 真实执行 `SELECT 1`；提供同步 Session Factory 和 `dispose()`；
- Stage 2 不自动建表、不自动执行 Alembic；
- `/health/live` 保持既有 Contract；
- `/health/ready` 使用稳定 `operation_id=healthReady`，PostgreSQL、Artifact 根目录、日志目录全部就绪返回 200，否则 503；响应只暴露组件 `ok/error`。

## Artifact

```text
ArtifactService
→ 管 Artifact ID / 元数据 / pending → stored → linked

ArtifactMetadataPort
→ Stage 2 用 Fake 验证
→ PostgreSQL Repository/Table 留到 Stage 3

ArtifactStore
→ 只按 storage_key put/read/exists
→ 不知道 Artifact UUID，不反查数据库
```

Local Store 拒绝绝对路径、`..`、反斜杠和符号链接逃逸；同 key 不覆盖；同目录临时文件 + fsync + hard-link 原子 no-overwrite 发布。Artifact 删除/保留动作继续等待 Stage 0 规则。

# 非目标确认

本 Change 没有创建业务表、`artifacts` 表或 Alembic Revision；没有 User/Session/RBAC、API 幂等、Job Runtime、正式 Scheduler、TikHub/Raw/Mapper/Canonical/Ingestion、Artifact 删除、Docker/生产 Compose/Release。没有新增 Python/npm 依赖。生产仍为 No-Go。

# TDD 与验证证据

- Red：Run `31688263120` / job `94409359710`，`/health/ready` 尚未实现时按 404 正确失败，`/health/live` 正常。
- Contract bootstrap：Run `31689094676`，冻结工具链生成 OpenAPI 与 Orval Client；临时写权限 workflow 随后删除。
- 严格质量迭代依次修正 Ruff format、Ruff lint 和 mypy 边界，没有降低门禁或使用 `type: ignore` 绕过。
- Run `31689773340`：Stage 1 + Windows bootstrap 全绿，证明 Platform 实现未破坏 Stage 1 基线。
- CI 表达式问题：Run `31690114115` 因 job 级 `${{ runner.temp }}` 在调度前不可用而 0 Job；修复为独立 `Stage 2 Platform` Job + `.runtime/ci-stage2`，不是应用/数据库失败。
- 开发期间 `main` 前进到 `e0f1e0e349f615572b69392893e96e5bfadc5d55`；复核无语义冲突后通过普通双父 merge `fec25aacc2a7e1feb250fac875321bfdc3c345c0` 合入特性分支，没有 force/rebase，保留并发修改。
- Run `31690779819`：Stage 1 / Stage 2 Platform / Windows bootstrap 首次三 Job 全绿。
- 文档同步后 Run `31691578448`：临时文档工具删除后的正式分支三 Job 全绿。
- Review 找到 Local Store `os.replace` 的竞争覆盖窗口，修正为 hard-link 原子 no-overwrite 并增加竞争写测试；同时增加真实缺 PostgreSQL Secret 的 fail-closed readiness 测试。
- Review-fix Run `31691841817`：三 Job 全绿；Stage 2 unit `17 passed`、PostgreSQL integration `1 passed`，真实 `/health/ready` HTTP smoke 成功，测试密码 `stage2-ci` 未进入 `api.log`。
- Blueprint 07 的 Artifact 原子发布描述同步后，最终 PR head `1a64cec9455f64f6e94cc43f2aaff8d75f974d79` 的 Run `31692247897` 三 Job全部 success。
- PR #5 已 squash merge，合并提交：`4917e30cf99b5c3443f2b08c1ee417e5c0c1c314`。
- 合并后 `main` CI Run `31692446342`：Stage 1、Stage 2 Platform、Windows bootstrap 三 Job全部 success。

# 两阶段 Review

需求符合性：最终差异只覆盖 Stage 2 Platform、`/health/ready` Contract/生成物、测试、CI、运行示例和受影响文档；没有越界到 Stage 3/4/5/11。并发进入 main 的开发规范与 `.gitignore` 修改已保留。

代码质量与安全：Config 来源显式；Secret 不进入错误/health/log；数据库不做 DDL/Migration；日志真实验证 gzip 轮转和脱敏；Local Store 路径、符号链接、不可变 key 和竞争 no-overwrite 已验证；readiness 成功与 fail-closed 路径均有测试；Worker/Scheduler/Migration 只提供 Platform bootstrap。Review 修复后未发现严重或重要问题。

# 文档同步

- `README.md`：Stage 2 状态、最短配置/启动/readiness 和下一阶段；
- `docs/环境运行与部署.md`：Stage 2 `AIMA_*`、Secret、PostgreSQL/readiness 本地操作；
- `docs/blueprint/README.md`：Stage 2 已完成，下一阶段 Stage 3；
- `docs/blueprint/06-开发约束与分阶段实施.md`：Stage 2 验收改为日志/Secret/Local Store/隔离 PostgreSQL/readiness；生产 Compose 留到 Stage 11；
- `docs/blueprint/07-技术决策与实施门禁.md`：1.5 → 1.6，固化 Stage 2 Platform 决策和 Go/No-Go。

# Git / 数据 / 回滚

- 开发 PR：#5 `建立 Stage 2 Platform 基础能力`，已 squash merge；
- 合并提交：`4917e30cf99b5c3443f2b08c1ee417e5c0c1c314`；
- 合并后 main CI：Run `31692446342` 三 Job 全绿；
- Migration / 数据变化：无；
- 生产发布：不适用；
- 回滚不涉及 Schema/Data 恢复，只需回退 Stage 2 Platform、Contract/生成物、CI 和对应文档。
