---
schema: rvc-change/v1
id: CHG-20260813-stage2-platform-foundation
title: Stage 2 Platform 基础能力
level: L3
status: in_progress
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

# 背景与现状

Stage 1 已建立可安装 Python package、FastAPI/Vue 最小工程、本地双服务启动、锁文件和 CI。当前 `main` 还没有 Platform 层的配置、Secret、统一日志、PostgreSQL 连接、ArtifactStore/ArtifactService、readiness 或 Worker/Scheduler/Migration bootstrap。

用户已授权按 Blueprint 进入 Stage 2，并明确本轮先忽略 `main` Branch Protection。

# 目标

建立一个不依赖业务模块的 Platform 基础，使后续 Stage 3/4/5 可以基于稳定的配置、Secret、日志、数据库和文件存储边界继续开发。

# 成功标准

- [ ] 配置从显式 `AIMA_*` 环境变量读取，默认值和类型有测试，运行时不解析 `latest`。
- [ ] Secret 只从只读文件读取；空值、缺失、目录、过大和 NUL 等异常明确失败，Secret 内容不进入异常文本。
- [ ] API/Worker/Scheduler 使用统一结构化日志基础；北京时间毫秒格式、稳定 `event`、控制字符转义、敏感值脱敏、长度限制、20 MiB×10 gzip 轮转可验证。
- [ ] PostgreSQL 使用现有 SQLAlchemy 2 + psycopg 3 同步连接；提供 `ping()`、Session Factory 和 `dispose()`，不自动建表、不自动 Migration。
- [ ] `/health/live` 保持现有 200 Contract；新增 `GET /health/ready`，检查 PostgreSQL、Artifact 目录和日志目录，成功返回 200，依赖不可用返回 503，响应不泄露 Secret/连接串。
- [ ] `ArtifactStore` 只按 `storage_key` 存取字节；Local Store 原子写、路径穿越拒绝、读取/存在检查可独立测试。
- [ ] `ArtifactService` 负责 Artifact ID、元数据和 `pending → stored → linked` 生命周期编排；持久化 Port 用 Fake 验证，PostgreSQL `artifacts` 表留到 Stage 3。
- [ ] 不实现删除/保留策略，因为 Stage 0 的保留与删除规则尚未批准。
- [ ] API、Worker、Scheduler、Migration 四个 entrypoint/bootstrap 模块存在并复用同一 Platform 组件；不伪造 Worker/Scheduler 空循环。
- [ ] CI 增加 PostgreSQL 18.4 隔离集成验证和 Stage 2 Platform 测试；原 Stage 1、Windows bootstrap、Contract、Wheel、前端门禁保持全绿。
- [ ] README、运行文档和受影响 Blueprint 与实际实现一致。

# 范围

- `platform/config`：环境配置模型与加载。
- `platform/security`：Secret 文件读取。
- `platform/logging`：Formatter、脱敏和 Handler 配置。
- `platform/database`：Engine/Session/Ping 基础。
- `platform/storage` + `adapters/storage/local`：Artifact 边界与 Local Store。
- `platform/health`：readiness 检查结果。
- `bootstrap` / `entrypoints`：四进程最小装配入口。
- 单元、API、隔离 PostgreSQL 集成测试和 CI。
- 当前事实文档同步。

# 非目标

- 不创建任何业务表、`artifacts` 表或 Alembic Revision；Schema/Migration 属于 Stage 3。
- 不实现用户、Session、RBAC、API 幂等。
- 不实现 Job 表、Worker claim/lease/fencing、Reaper 或 Scheduler 计划逻辑。
- 不实现 TikHub、Provider、Raw、Mapper、Canonical 或 Ingestion。
- 不实现 Dockerfile、生产 Compose、Release Bundle、备份恢复。
- 不实现 Artifact 删除/保留策略，也不自动清理文件。
- 不新增 Redis、消息队列、Pydantic Settings、structlog 等依赖。
- 本轮按用户要求不配置 Branch Protection。

# 必须保持不变

- 根目录仍是唯一 Python/uv 工程；源码仍在 `backend/src/aima_ugc/`。
- `/health/live` 的路径、200 状态、`{"status":"ok"}` 响应和 `operation_id=healthLive` 保持不变。
- 本地后端仍可在没有 PostgreSQL 时启动并提供 `/health/live`；数据库未就绪时只影响 `/health/ready`。
- 前端生成 Client 继续由 FastAPI OpenAPI → Orval 生成，禁止手改。
- 生产仍是 No-Go；本轮不会把本地开发命令包装成生产部署。
- Secret 不写 Git、日志、Raw、Job Payload 或数据库明文。

# L3 方案比较与决定

## 配置

### 方案 A：Pydantic + 显式环境变量映射（采用）

复用现有 Pydantic，不新增依赖。每个 `AIMA_*` 名称在代码中显式映射，默认值和类型可测试，后续配置变化可被 Review 直接看到。

### 方案 B：新增 `pydantic-settings`

能力完整，但当前只需要少量 Platform 配置，引入额外依赖和隐式来源优先级没有必要。

### 方案 C：纯 `os.environ` + dataclass

依赖最少，但会重复编写类型转换和校验，错误信息也更弱。

## 日志

### 方案 A：标准库 logging + RotatingFileHandler + gzip（采用）

直接满足 Blueprint 05，依赖为零，单服务单写者假设成立。

### 方案 B：structlog / loguru

可读性和结构化能力更强，但当前没有多 sink/trace 等需求，新增依赖缺乏证据。

## 数据库

### 方案 A：同步 SQLAlchemy Engine + psycopg（采用）

与 Blueprint 01 已确认同步路线一致，可供 API/Worker/Scheduler/Migration 共用。

### 方案 B：async SQLAlchemy

当前没有单进程高并发数据库瓶颈证据，会给团队引入同步/异步双模型。

## Artifact

### 方案 A：Service + Metadata Port + Local ArtifactStore（采用）

Service 管 ID/元数据/生命周期，Store 只管字节；Metadata Port 由测试 Fake 验证，Stage 3 再接 PostgreSQL Repository。符合现有边界且不会提前建表。

### 方案 B：Local Store 直接管理 JSON 元数据

会把文件系统变成第二业务事实源，违反 PostgreSQL 唯一业务事实库原则。

### 方案 C：Stage 2 直接创建 `artifacts` 表

会提前进入 Stage 3 Schema/Migration 范围，不采用。

# 配置 Contract

Stage 2 固定以下非敏感环境变量：

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

PostgreSQL 密码不进入环境变量，固定从：

```text
<AIMA_SECRET_DIR>/postgres_password
```

读取。生产未来把 `AIMA_SECRET_DIR` 指向 `/run/secrets`；本地默认 `.runtime/secrets`。

# Artifact Contract

`ArtifactStore` 只负责：

```text
put(storage_key, bytes) -> sha256 + byte_size
read(storage_key) -> bytes
exists(storage_key) -> bool
```

Local Store 必须把 `storage_key` 约束在配置根目录内并原子替换目标文件。

`ArtifactService` 本阶段只实现：

```text
create/store: pending -> stored
link: stored -> linked
```

删除状态保留在长期设计中，但本阶段不提供删除业务动作。

# 实施步骤

[1] 建立 Red
→ 修改范围：`tests/api/test_health.py`
→ 预期结果：新增 `/health/ready` 目标行为测试，在实现前因 404 正确失败
→ 验证方式：PR CI `uv run pytest tests/api -q`

[2] 配置 / Secret / DB
→ 修改范围：`platform/config`、`platform/security`、`platform/database`
→ 预期结果：显式配置、Secret 文件、同步 PostgreSQL runtime 可独立验证
→ 验证方式：Unit + PostgreSQL 18.4 Integration

[3] 日志
→ 修改范围：`platform/logging`
→ 预期结果：格式、脱敏、控制字符、长度和 gzip 轮转符合 Blueprint 05
→ 验证方式：Unit tests + CI 文件检查

[4] Artifact
→ 修改范围：`platform/storage`、`adapters/storage/local`
→ 预期结果：路径安全、原子写和 pending/stored/linked 生命周期通过 Fake Metadata Port 验证
→ 验证方式：Unit tests

[5] Bootstrap / Health
→ 修改范围：`bootstrap/`、四个 `entrypoints/`、API health Contract
→ 预期结果：四进程复用 Platform 装配；API ready 对真实依赖给出 200/503
→ 验证方式：API tests + PostgreSQL Integration + HTTP smoke

[6] CI 与文档
→ 修改范围：`.github/workflows/ci.yml`、`env.local.example`、README、运行文档、Blueprint README/06/07
→ 预期结果：Stage 2 独立 Job 全绿；Stage 2 当前事实有单一落点
→ 验证方式：完整 PR CI、Contract/Client 零漂移、文档检查

[7] Review / 合并 / 归档
→ 修改范围：Change 与 PR
→ 预期结果：两阶段 Review 无严重/重要问题；合并后 `main` CI 全绿，再归档 Change
→ 验证方式：最终 PR head CI + `main` push CI

# 兼容、Migration、部署与回滚

- HTTP：只新增 `/health/ready`；`/health/live` 保持兼容。
- 配置：新增 `AIMA_*` Platform 配置；没有旧生产配置需要迁移。
- 数据：无数据库 Schema/Data 变化，无 Migration。
- 依赖：不新增 Python/npm 依赖。
- 部署：不产生生产 Release；生产状态保持 No-Go。
- 回滚：移除 Stage 2 Platform 模块、`/health/ready`、Stage 2 CI 和对应文档即可；无数据恢复步骤。

# 风险与安全

- 日志 Formatter 必须在最后输出前再次脱敏；业务代码仍禁止主动记录 Secret。
- readiness 不返回连接串、密码路径内容或原始异常文本。
- Local Store 必须拒绝绝对路径、`..`、反斜杠绕过和根目录外的符号链接目标。
- Secret 文件设置最大读取大小，避免误读大文件；只去除尾部换行，不任意 trim 有意义的空格。
- PostgreSQL ping 使用短连接超时，不在健康检查中自动重试或自动修改 Schema。

# Git

- 分支：`feature/stage2-platform-foundation`
- PR：待创建
- 用户已授权实现、提交、PR、合并到 `main`。
- 本轮按用户要求忽略 `main` Branch Protection 配置。
