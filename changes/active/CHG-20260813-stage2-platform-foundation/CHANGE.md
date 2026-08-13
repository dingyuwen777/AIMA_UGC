---
schema: rvc-change/v1
id: CHG-20260813-stage2-platform-foundation
title: Stage 2 Platform 基础能力
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/stage2-platform-foundation
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [platform, api, toolchain, developer-experience]
affected_paths: [backend/src/aima_ugc/platform/, backend/src/aima_ugc/bootstrap/, backend/src/aima_ugc/entrypoints/, backend/src/aima_ugc/adapters/storage/local/, tests/unit/platform/, tests/integration/platform/, tests/api/test_health.py, .github/workflows/ci.yml, env.local.example, README.md, docs/环境运行与部署.md, docs/blueprint/README.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, changes/active/CHG-20260813-stage2-platform-foundation/CHANGE.md]
contracts: [GET /health/ready]
data_changes: []
---

# 目标与结果

Stage 2 已建立不依赖业务模块的 Platform 基础，使后续 Stage 3/4/5 可以复用同一套配置、Secret、日志、数据库和 Artifact 边界：

- 显式 `AIMA_*` Config；
- Secret 只读文件；
- API/Worker/Scheduler 统一 `.log` 基础；
- 同步 SQLAlchemy 2 + psycopg 3 PostgreSQL Runtime；
- `GET /health/ready`；
- `ArtifactService` / `ArtifactStore` / Local ArtifactStore；
- API、Worker、Scheduler、Migration 最小 Platform bootstrap；
- 隔离 PostgreSQL 18.4 的 Stage 2 CI。

用户明确要求本轮忽略 `main` Branch Protection；本 Change 未修改任何 Branch Protection 设置。

# 成功标准

- [x] Config 只读取代码显式声明的 `AIMA_*`；默认值、类型和相对路径解析有测试；不自动加载 `.env` / `env.local.example`。
- [x] Secret 只从普通文件读取；限制大小/UTF-8/NUL/空值，只移除尾部换行，异常不回显 Secret 内容。
- [x] API/Worker/Scheduler 统一北京时间毫秒日志、稳定 `event`、控制字符转义、敏感值脱敏、长度限制和 `20 MiB × 10` gzip 轮转；真实轮转有单元测试。
- [x] PostgreSQL 使用现有同步 SQLAlchemy 2 + psycopg 3；提供 `ping()`、Session Factory、`dispose()`；没有自动建表或 Migration。
- [x] `/health/live` 保持既有 200 Contract；新增 `GET /health/ready`，依赖就绪返回 200，不可用返回 503，响应不泄露 Secret、连接串或原始异常。
- [x] Local ArtifactStore 只按 `storage_key` 存取字节；拒绝路径穿越/反斜杠/符号链接逃逸；同 key 不覆盖；同目录临时文件 + fsync + hard-link 原子 no-overwrite 发布；竞争写测试已覆盖。
- [x] `ArtifactService` 负责 ID、元数据 Port 和 `pending → stored → linked`；PostgreSQL `artifacts` Table/Repository 留到 Stage 3。
- [x] 未实现 Artifact 删除/保留策略，继续等待 Stage 0 规则。
- [x] API、Worker、Scheduler、Migration 四个 entrypoint/bootstrap 复用同一 Platform 组件；未伪造 Worker Job 循环或 Scheduler 计划循环。
- [x] CI 使用 `postgres:18.4` 做真实连接、Platform unit/integration、`/health/ready` HTTP smoke，并检查测试密码不进入 `api.log`。
- [x] 原 Stage 1、Windows bootstrap、OpenAPI/Client、Wheel、前端门禁保持全绿。
- [x] README、运行文档、Blueprint README、06、07 与最终实现同步；Blueprint 07 已升至 1.6。

# 最终技术决定

## Config

采用现有 Pydantic + 显式环境变量映射，不新增 `pydantic-settings`。当前非敏感 Contract：

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

`env.local.example` 只是示例，代码不会自动加载。PostgreSQL 密码固定从 `<AIMA_SECRET_DIR>/postgres_password` 读取。

## Logging

采用标准库 `logging + RotatingFileHandler + gzip`，不新增第三方日志依赖。Formatter 在最终输出层再次脱敏；业务代码仍禁止主动记录 Secret。

## Database

采用已批准的同步 SQLAlchemy Engine + psycopg。Engine 惰性创建，readiness 执行真实 `SELECT 1`，不自动重试、建表或运行 Alembic。

## Artifact

采用 `ArtifactService + ArtifactMetadataPort + ArtifactStore`：

```text
ArtifactService
→ 管 Artifact ID / 元数据 / pending → stored → linked

ArtifactMetadataPort
→ Stage 2 用 Fake 验证
→ Stage 3 再实现 PostgreSQL Repository

ArtifactStore
→ put/read/exists(storage_key)
→ 不知道 Artifact UUID，不反查数据库
```

Local Store 的最终发布使用 hard-link 的原子 no-overwrite 语义；若同 key 已存在或并发竞争者先发布，当前写入明确失败，不覆盖不可变 Artifact。

# 非目标与保持不变

- 没有业务表、`artifacts` 表、Alembic Revision 或数据 Migration。
- 没有 User/Session/RBAC、API 幂等。
- 没有 Job 表、claim/lease/fencing/Reaper 或正式 Scheduler。
- 没有 TikHub、Provider、Raw、Mapper、Canonical、Ingestion。
- 没有 Dockerfile、生产 Compose、Release Bundle 或备份恢复。
- 没有 Artifact 删除/保留动作。
- 没有新增 Python/npm 依赖。
- `/health/live` 路径、200、`{"status":"ok"}` 和 `operation_id=healthLive` 不变。
- 前端 Client 仍由固定 OpenAPI → Orval 生成，生成物未手改。
- 生产仍为 No-Go。
- Branch Protection 按用户要求未处理。

# TDD / 实际验证证据

## Red

- PR Run `31688263120` / Stage 1 job `94409359710`：新增 `/health/ready` 目标测试后，实现尚不存在，实际返回 404、预期 503；`/health/live` 和前置工具链正常，因此是正确 Red。

## Contract / Green 迭代

- Contract bootstrap Run `31689094676`：冻结 Python/Node/uv/npm 环境成功生成固定 OpenAPI 和 Orval Client；临时写权限 workflow 随后删除。
- 第一轮 Green 先被 Ruff format 阻断；按冻结 Python 3.14 / Ruff 的实际格式结果修正，没有修改行为。
- 第二轮只剩 Ruff lint 的机械问题；修正后继续推进。
- 第三轮 mypy 暴露 SQLAlchemy scalar、readiness Literal、FastAPI lifespan 三类严格类型边界；通过补准确类型修复，没有 `type: ignore`。
- Run `31689773340`：在新增 Stage 2 PostgreSQL Job 前，原 Stage 1 + Windows bootstrap 已全绿，证明 Platform 实现没有破坏 Stage 1 基线。

## Stage 2 CI

- Run `31690114115`：第一次把 `${{ runner.temp }}` 放在 job 级 `env`，GitHub workflow 在调度前校验失败并产生 0 Job；这是 CI 表达式作用域错误，不是应用/数据库失败。最终改为独立 `Stage 2 Platform` Job + 已忽略的 `.runtime/ci-stage2` 相对目录。
- Git-data ref 更新未产生 PR synchronize 事件；通过 PR close/reopen 触发标准 `pull_request` reopened 事件，仅用于让当前 head 执行 CI，没有改代码历史或绕过门禁。
- 开发过程中 `main` 前进到 `e0f1e0e349f615572b69392893e96e5bfadc5d55`；复核只涉及函数组织规范和 `.gitignore` OS/IDE 忽略项，与 Stage 2 无语义冲突。通过普通双父 merge `fec25aacc2a7e1feb250fac875321bfdc3c345c0` 合入特性分支，没有 force/rebase/覆盖用户修改。
- Run `31690779819`：合并最新 main 后，`Stage 1`、`Stage 2 Platform`、`Windows bootstrap` 三个 Job 首次全部 success。
- 文档精确迁移 Run `31691508009`：脚本要求每段旧文本唯一匹配后才更新运行文档/06/07；临时 workflow/脚本随后删除。
- Run `31691578448`：临时文档工具删除后的正式分支，三个 Job 再次全部 success。

## Review 修复

Review 找到两个需要补强的边界：

1. Local Store 原实现用 `os.replace`，在“存在检查后、发布前”的极窄竞争窗口可能覆盖同 key；改成 hard-link 原子 no-overwrite，并新增模拟竞争写测试。
2. API 503 已用注入结果测试，但真实“缺 PostgreSQL Secret”的 fail-closed 路径缺直接测试；已增加真实 PlatformRuntime 测试，确认 database=`error`、Artifact/log=`ok`、ready=false。

- Review-fix Run `31691841817`：`Stage 1`、`Stage 2 Platform`、`Windows bootstrap` 三 Job 全部 success。
- 其中 Stage 2 job `94420674666` 使用 PostgreSQL 18.4；Platform unit `17 passed`，PostgreSQL integration `1 passed`，真实 Uvicorn `/health/ready` 返回 database/artifact_store/log_directory 全部 `ok`，并检查测试密码 `stage2-ci` 没有进入 `api.log`。
- Review 后 Blueprint 07 Artifact 描述同步为 hard-link 原子 no-overwrite；Run `31691949384` 成功完成精确文档修正，临时 workflow/脚本随后再次删除。

# 两阶段 Review

## 需求符合性

复核 `main...feature/stage2-platform-foundation`：最终差异只覆盖 Stage 2 Platform、`/health/ready` Contract/生成物、测试、CI、运行示例和受影响文档。没有进入 Stage 3 Schema/Auth、Stage 4 Job Runtime、Stage 5 TikHub/Raw 或 Stage 11 Release。用户并发进入 main 的开发规范和 `.gitignore` 修改已保留。

## 代码质量与安全

- Config 来源显式，没有隐式 `.env` 优先级。
- Secret 只读文件，异常/health/log 不回显内容。
- PostgreSQL Runtime 不做 DDL/Migration，真实 PostgreSQL 18.4 已验证。
- 日志实际验证 gzip 轮转、控制字符转义和敏感信息脱敏。
- Local Store 路径/符号链接安全、不可变同 key 和竞争写 no-overwrite 已验证。
- Artifact Service/Store 边界没有把文件系统变成第二业务事实源。
- readiness fail closed，真实成功与真实缺 Secret 失败路径均有测试。
- Worker/Scheduler/Migration 仅提供 Platform bootstrap，没有伪造后续阶段逻辑。
- 生产仍明确 No-Go。

Review 修复后未发现严重或重要问题。

# 文档同步

- `README.md`：Stage 2 当前状态、最短配置/启动/readiness 入口与下一阶段。
- `docs/环境运行与部署.md`：Stage 2 `AIMA_*`、Secret 文件、PostgreSQL/readiness 本地操作；生产仍 No-Go。
- `docs/blueprint/README.md`：Stage 2 已完成，下一阶段切到 Stage 3。
- `docs/blueprint/06-开发约束与分阶段实施.md`：Stage 2 验收明确为日志/Secret/Local Store/隔离 PostgreSQL/readiness；生产 Compose 健康留到 Stage 11。
- `docs/blueprint/07-技术决策与实施门禁.md`：1.5 → 1.6，固化 Stage 2 Platform 决策、版本验证状态和 Go/No-Go。
- `01/03/05` 复核后长期架构未被实现推翻，没有为了形式重复改写。

# Git / 发布 / 回滚

- 开发分支：`feature/stage2-platform-foundation`
- PR：#5 `建立 Stage 2 Platform 基础能力`。
- Migration / 数据变化：无。
- 生产发布：不适用，生产仍为 No-Go。
- 回滚：移除 Stage 2 Platform 模块、`/health/ready`、Stage 2 CI 和对应生成物/文档即可；无 Schema/Data 恢复步骤。
- 合并前要求：当前 `ready_for_review` head 的 Stage 1 / Stage 2 Platform / Windows bootstrap 全绿。
- 合并后要求：`main` merge commit 的三个 Job再次全绿后才能归档本 Change。
