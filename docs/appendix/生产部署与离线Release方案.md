# 生产部署与离线 Release 方案

这篇文档用于后续真正完成 **Stage 11：Production Release**，并记录 Internal V1 已经落地、后续 Stage 11 必须直接复用的部署基础。

它同时记录两类事实：

```text
当前已经实现
→ 可以直接从仓库代码验证

已批准目标 / 待实现
→ 后续必须按 Change 开发，不能现在假装命令已经可用
```

当前结论先写在前面：

> **当前仓库已经通过 Internal V1-A 实现根 `Dockerfile`、根 `compose.yaml`、`env.production.example`、宿主 bootstrap 与 Nginx Runtime，并把完整容器 Runtime 收敛为“一个敏感 `env.production` + 一个 `AIMA_HOST_ROOT` + 一条 Docker Compose 启动命令”。本地完整 Docker 与公司服务器复用同一配置 Schema；本地可把 Host Root 设为 `./.runtime/compose`，服务器固定为 `/data/AIMA_UGC`。内部 PostgreSQL/Cursor Secret 仍由系统自动生成并持久保存，TikHub/LLM Key 由 `env.production` 进入 Compose Secret File，不作为业务容器环境变量。永久 Compose Golden Path 验证空库 Migration、正式进程、Secret 生命周期、Readiness、绝对/相对 Host Root、持久挂载与端口边界。它仍不是完整 Stage 11 Production Release：离线 `images.tar`、Manifest、固定 digest、SBOM/签名、协调 Backup/Restore、企业认证/授权与真实生产服务器验收仍待后续正式 Change 完成。**

生产上线总路线见：

[`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)

当前开发与 Internal V1-A 操作见：

[`../环境运行与部署.md`](../环境运行与部署.md)

---

# 1. 当前代码已经提供哪些生产进程能力

当前 Python 已有分进程入口：

```text
API
Worker
Scheduler
Migration
Internal V1 configure（一次性运行配置装配）
```

代码入口：

```text
backend/src/aima_ugc/entrypoints/
backend/src/aima_ugc/bootstrap/
```

Internal V1-A 已把这些能力装进同一个非 root Backend image；不同服务只使用不同正式 command。前端 Vue SPA 通过 Frontend build stage 构建静态资源，并由非 root Nginx Runtime 提供，同时同源代理 `/api` 与 `/health`。

当前部署还增加一个一次性 `bootstrap` 服务。它不是业务进程，也不常驻：只在 Compose 启动阶段以 root 准备宿主持久目录、生成/校验内部 Secret，成功后退出 0；PostgreSQL 只在 bootstrap 成功后启动。

当前业务持久依赖：

```text
PostgreSQL 18
Local ArtifactStore（当前默认）
内部 Secret files
应用日志目录
```

因此 Stage 11 不应重新设计业务代码或另造一套运行时，而是在 V1-A 已验证的容器/配置边界上继续完成**不可变、可验证、可恢复的正式 Release**。

---

# 2. 生产服务拓扑

Internal V1-A 当前实际 Compose 拓扑：

```text
bootstrap（一次性初始化）
↓
postgres
↓
migrate（一次性）
↓
configure（一次性）
↓
api / worker / scheduler
↓
frontend
```

长期生产核心业务服务仍是：

```text
frontend
api
worker
scheduler
migrate
postgres
```

`bootstrap` 与 `configure` 都属于部署/启动装配，不是常驻业务服务。

### `frontend`

```text
Vue build 输出
+ Nginx 静态文件
+ /api 与 /health 反向代理
```

### `api`

只服务 HTTP，请求不能在 API 进程里同步执行分钟级采集/Analysis/Export。

### `worker`

消费 PostgreSQL durable Job：

```text
collection.run.v1
ingestion.import-excel.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

### `scheduler`

只负责 `Plan → due slot → Occurrence → Run + Job`，不直接请求 TikHub。

### `migrate`

一次性发布动作：

```text
alembic upgrade head
```

它不是常驻服务，也不由 API/Worker 启动时隐式执行。Compose 自动编排它，只是减少人工步骤，不改变“Migration 独立进程”这个架构边界。

### `postgres`

唯一业务事实库。

---

# 3. 生产宿主机目录

生产服务器长期只配置一个持久根：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

Compose 从该根固定推导当前运行所需目录：

```text
/data/AIMA_UGC/runtime/data
/data/AIMA_UGC/runtime/logs
/data/AIMA_UGC/postgres
/data/AIMA_UGC/shared/secrets
```

长期运维目录仍包括：

```text
/data/docker
/data/AIMA_UGC/backups
/data/AIMA_UGC/releases
/data/AIMA_UGC/shared/env
```

其中 `/data/AIMA_UGC/backups`、`releases`、`shared/env` 不由当前 Compose 自动创建/管理完整生命周期；完整协调 Backup Set、不可变 Release 内容及共享配置策略由后续 Stage 实现。

| 目录 | 用途 | 为什么单独放 |
| --- | --- | --- |
| `/data/docker` | Docker 自身镜像/层/容器元数据 | Docker 清理与业务数据隔离 |
| `/data/AIMA_UGC/postgres` | PostgreSQL 数据 | 不能依赖容器可写层，也不能放版本 Release 目录 |
| `/data/AIMA_UGC/runtime/data` | Local ArtifactStore 等业务文件 | 与 Release 解耦，升级不覆盖 |
| `/data/AIMA_UGC/runtime/logs` | API/Worker/Scheduler `.log` | 便于宿主机直接排障和轮转 |
| `/data/AIMA_UGC/backups` | 未来协调 Backup Set | 不能和在线数据库目录混用 |
| `/data/AIMA_UGC/releases` | 未来不可变 Release 版本 | 支持切回旧应用版本，不承载持久业务数据 |
| `/data/AIMA_UGC/shared/env` | 可选共享配置目录 | 不能当作 Secret Manager；真实 env 文件本身需按敏感文件保护 |
| `/data/AIMA_UGC/shared/secrets` | AIMA 内部随机 Secret | 与 PostgreSQL 数据一起持久保护 |

不要把 PostgreSQL、Artifact、日志全部塞进 `/data/docker`，也不要把 `AIMA_HOST_ROOT` 指向 `/data/AIMA_UGC/releases/<version>`。

本地完整 Docker Compose 可以复用完全相同的子目录结构，只把一次性机器配置改为：

```dotenv
AIMA_HOST_ROOT=./.runtime/compose
```

这只是开发机的容器 Runtime 根，不改变生产服务器目录设计。

---

# 4. 容器内目标路径

Internal V1-A 当前实际路径：

```text
/app/data
/app/logs
/run/internal-secrets   # Backend 内部随机 Secret
/run/secrets            # Compose 外部 Provider/LLM Secret；PostgreSQL 容器中用于 password file
/var/lib/postgresql
```

当前锁定 PostgreSQL 为 `18.4`。PostgreSQL 18 官方镜像使用 `/var/lib/postgresql` 作为持久卷挂载点，默认数据库目录位于其下 `18/docker`；因此当前 Compose 把 `${AIMA_HOST_ROOT}/postgres` bind mount 到 `/var/lib/postgresql`。

后续真正完成 Stage 11 时仍必须重新验证当时锁定镜像的实际约定，不能把今天的路径无条件套到未来升级版本。

宿主 `bootstrap`/`scripts/deploy/prepare_host.py` 会：

- 建立/校验运行所需宿主目录；
- 固定 App/PostgreSQL/Secret group UID/GID；
- 不用 `chmod 777`；
- 首次生成内部随机 Secret；
- 已有内部 Secret 只校验/收紧权限，不静默轮换；
- 已有 PostgreSQL 18 数据但密码 Secret 丢失时 fail closed；
- App 与 Frontend 继续使用非 root 用户运行。

Linux/WSL 风格文件系统是当前严格 UID/GID/mode 语义的证明边界。Windows Docker Desktop 原生 Windows 文件系统 bind mount 不应成为放宽生产权限检查的理由。

---

# 5. Secret 装配

当前应用的 Secret File 边界保留，但为了把管理员操作收敛成一个 `env.production`，内部与外部 Secret 明确分层。

## 5.1 内部随机 Secret

```text
postgres_password
import_batch_cursor_signing_key
content_cursor_signing_key
collection_runtime_cursor_signing_key
```

流程：

```text
首次空环境
→ bootstrap 随机生成
→ ${AIMA_HOST_ROOT}/shared/secrets 持久保存
→ root:11001 / 0440
→ Backend 只读挂载 /run/internal-secrets
```

PostgreSQL 容器也只读挂载同一宿主内部 Secret 目录，并使用 `POSTGRES_PASSWORD_FILE` 读取 `postgres_password`。

关键恢复不变量：

```text
空数据库 + password 不存在
→ 自动生成

已有 PostgreSQL 18 数据 + password 存在
→ 复用

已有 PostgreSQL 18 数据 + password 不存在
→ 启动失败
→ 要求恢复原 Secret
→ 禁止生成新值
```

原因是 PostgreSQL 初始化密码不会因为容器重启时出现一个新 password file 就自动改写既有数据库账户密码；随意新建只会造成数据库和应用凭据漂移。

## 5.2 外部 TikHub / LLM Secret

管理员维护的真实 `env.production` 可以包含：

```text
AIMA_TIKHUB_API_KEY
AIMA_LLM_API_KEY
```

因此 `env.production` 本身属于**敏感文件**，必须被 Git ignore、限制文件权限，不得提交、打印或打入镜像/Release 明文。

运行链：

```text
env.production
→ Compose top-level secret `environment:` source
→ 只授予需要该 Secret 的 service
→ /run/secrets/tikhub_api_key 或 /run/secrets/llm_api_key
→ AIMA_EXTERNAL_SECRET_DIR
→ 现有 Secret resolver
```

业务容器的普通 `Config.Env` 不包含 API Key 原值。Provider Config 继续只保存：

```text
secret_ref
```

不得保存真实 Secret 值。

源码开发 launcher 使用已经分离的双根：

```text
AIMA_SECRET_DIR=.runtime/internal-secrets
AIMA_EXTERNAL_SECRET_DIR=.runtime/secrets
```

`PlatformSettings.external_secret_root` 在调用方未显式配置外部根时仍可回退到 `AIMA_SECRET_DIR`，但正常源码 launcher 与 Compose 都显式分离内部/外部根，不依赖 fallback 作为正式运行方式。

Secret resolver 必须继续防止 root escape、symlink、非普通文件、超限和错误信息回显 Secret。

---

# 6. Dockerfile 当前实现与长期要求

Internal V1-A 已建立根 `Dockerfile`，并固定：

```text
仓库根 = 唯一 build context
```

当前使用多阶段构建。

## Backend Runtime

已经：

- 按 `uv.lock` 安装锁定依赖；
- 安装项目 package；
- 不包含无关开发缓存；
- Runtime 启动不再联网 `pip install`；
- 正式 API/Worker/Scheduler 使用非 root UID `10001`；
- 同一 image 支持 API/Worker/Scheduler/Migration/Configure/Bootstrap 不同 command；
- 只有一次性 bootstrap 显式覆盖为 root，完成后退出；
- 镜像构建时不写入 Secret。

`.dockerignore` 只放行 `scripts/deploy/prepare_host.py` 进入 Backend build context，不把整个开发脚本目录塞入运行镜像；`.runtime` 与真实 env 文件同样不进入 build context。

## Frontend Runtime

```text
Node build stage
→ npm ci
→ npm run build
→ 只把 dist 复制到 Nginx runtime
```

生产 Nginx 不包含 `node_modules`，并以非 root 用户运行。

V1-A 保持仓库现有锁定版本，不因为部署体验收敛而升级 Python/Node/PostgreSQL/uv。完整 Stage 11 仍必须把最终实际 image digest 写入 Release Manifest，并建立来源/完整性验证；禁止把 `latest` 当不可追溯生产事实。

---

# 7. Compose 当前实现与 Stage 11 目标

Internal V1-A 当前只维护一个根 `compose.yaml`，避免在尚无完整 Release Manifest/离线镜像语义时制造两套易漂移配置。

运行入口按使用方式分工：

```text
源码热更新
→ env.local + scripts/dev/backend.py / frontend.py

完整容器 Runtime
→ env.production + compose.yaml
→ 本地 Docker、公司服务器、后续 Production Runtime 共用同一字段结构
```

Compose 唯一宿主持久配置：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

本地完整容器只需在本机 `env.production` 中一次性改为：

```dotenv
AIMA_HOST_ROOT=./.runtime/compose
```

管理员/Internal V1 标准入口：

```bash
cp env.production.example env.production
chmod 0600 env.production
# 编辑 env.production
docker compose --env-file env.production up -d --build --wait
```

同一命令同时适用于首次空环境和后续幂等启动。Compose 内部依赖链：

```text
bootstrap completed successfully
→ postgres healthy
→ migrate completed successfully
→ configure completed successfully
→ api / worker / scheduler
→ frontend healthy
```

当前 Compose 还保证：

- `frontend` 是唯一发布宿主端口的业务入口；
- 默认只绑定 `127.0.0.1:8080`；
- PostgreSQL/API 没有宿主 published port；
- `api/worker/scheduler/migrate/configure/bootstrap` 复用同一个 Backend image；
- PostgreSQL、Artifact、日志、内部 Secret 从单一 `AIMA_HOST_ROOT` 推导固定宿主目录；
- PostgreSQL 与 API 有真实 health/readiness；
- 外部 TikHub/LLM Secret 通过 Compose Secret File 装配；
- 内部随机 Secret 与业务数据在二次启动/容器重建时保持；
- `bootstrap`、`migrate`、`configure` 都是 one-shot，不保留高权限初始化容器常驻；
- Linux 永久 Golden Path 同时验证生产式绝对 Host Root 和仓库相对 Host Root。

完整 Stage 11 若需要独立生产覆盖，可在正式 Release Change 中增加有独立语义的 `compose.production.yaml`，但不能只是复制根 Compose。

完整 Stage 11 仍必须实现：服务器不现场 build、固定镜像/digest/Manifest、离线 load、正式 HTTPS/认证授权、完整 offline/no-pull smoke 等。Host Root 的统一只消除配置重复，不改变不可变 Production Release 原则。

---

# 8. 网络和浏览器安全边界

生产长期目标继续保留 HTTPS、明确 Host、同源、严格 CORS、HSTS、CSP、出站 Origin Allowlist 等要求。Internal V1-A 只完成最小公司内网部署所需的端口边界与同源 Nginx 代理，不把完整 Production Browser Security 目标伪装为已实现。

---

# 9. 认证是完整 Stage 11 前置，而不是生产部署后再补

当前没有正式企业认证闭环。经批准的 Internal V1 路线把认证明确延期到完整 Production 阶段，因此 Internal V1-A/V1-B 的受控公司内网验收不能被描述成最终生产安全闭环。

目标边界：

```text
External Identity Provider
→ Authentication Adapter
→ Principal / AuthContext
→ Authorization
→ 业务 Service
```

Provider-specific 用户 ID/Token 不应成为普通业务模块公共身份 Contract。

---

# 10. Release Bundle 结构

原方案继续保留：

```text
AIMA_UGC-v1.0.0-deploy.tar.gz
├─ images.tar
├─ compose.yaml
├─ compose.production.yaml
├─ env.production.example
├─ release-manifest.json
├─ migration-manifest.json
├─ SHA256SUMS
├─ SBOM/
├─ SIGNATURES/
└─ DEPLOY.md
```

正式版本号规则在 Release Change 中确定；上面的 `v1.0.0` 只是结构示例。

`release-manifest.json` 至少记录 Release 版本、Git SHA、构建时间、target platform、image digest、Alembic head、Contract/OpenAPI hash、最低 Docker/Compose 版本、Migration 兼容/rollback 边界、SBOM/签名信息。

Release Bundle 可以携带 Runtime Compose/模板，但**不得携带当前生产 PostgreSQL、Artifact、日志或内部 Secret 内容**。它们继续位于服务器固定 `AIMA_HOST_ROOT=/data/AIMA_UGC` 下。

---

# 11. 为什么不能只校验 SHA256

`SHA256SUMS` 只能证明文件和清单一致；如果攻击者同时替换 release 与 SHA 文件，不能证明来源。所以生产目标需要独立受信签名或有身份/完整性证明的 Artifact Registry。

---

# 12. 生产服务器部署原则

完整 Stage 11 的目标服务器只做：

```text
获取已验证 Release
→ verify
→ docker load
→ migrate
→ compose up --no-build --pull never
```

禁止 `git pull`、现场 `npm install` / `pip install`、浏览器在线下载、现场 build 与 CI 不同镜像、临时编辑容器内部文件。

目标 Runtime 仍使用服务器自身受保护的 `env.production` 和：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

因此应用 Release 与持久数据解耦。Internal V1-A/B 当前的仓库级内网验收入口仍允许 `--build`，用于建立/验证最小部署基础；它不改变正式不可变 Release 原则。

---

# 13. Release 目录

目标：

```text
/data/AIMA_UGC/releases/
├─ v1.0.0/
├─ v1.0.1/
└─ current -> v1.0.1
```

版本目录只放不可变 Release。共享配置/Secret、runtime data/log、postgres、backups 不能放版本目录，否则切换版本会覆盖持久事实。

必须保持：

```text
AIMA_HOST_ROOT=/data/AIMA_UGC
≠ /data/AIMA_UGC/releases/v1.0.1
```

Release 可以切换，Host Root 不随应用版本切换。

---

# 14. 发布前为什么必须协调 PostgreSQL 和 Artifact

业务来源链中存在 `content_versions.raw_artifact_id → artifacts metadata → ArtifactStore bytes`。只备份数据库可能丢 bytes，只备份文件会丢业务关系/Job/Content，所以目标恢复单位是：

```text
Backup Set = PostgreSQL + ArtifactStore
```

并且需要证明两者对应同一个业务截止点。

---

# 15. 协调 Backup/Restore 目标机制

原设计核心机制仍是待实现目标：正常业务写使用共享 write lock；备份进入 maintenance、停止新 Job/Scheduler 写、取得独占 lock、等待 writer 退出、冻结新写、捕获 PostgreSQL + Artifact、验证 Backup Set 后释放。

具体 advisory lock key、表、状态机和脚本当前尚未实现，进入 Stage 11C 必须用正式 Change 设计并测试。不能只给两个独立备份文件同一个名字就称作“协调一致”。

---

# 16. 发布顺序

完整 Production 目标顺序仍是：确认目标 SHA/CI → 获取并验证 Release → 检查 Manifest/Migration/磁盘/Secret → 维护态/停止新写 → 协调 Backup Set → docker load → migrate → compose start → health/smoke → 恢复 Scheduler/Worker → 观察日志/磁盘/失败 Job。

任何 Backup/Migration 校验失败必须停止继续发布，不能“先把新服务起来再说”。

---

# 17. 关键业务 Smoke

正式 Release 至少验证 `/health/live`、`/health/ready`、Frontend、数据库、Artifact、日志，以及 Excel Import → Content → Analysis → Excel Export，并在受控范围执行一次 Collection Run。真实付费 Provider/LLM smoke 必须限制请求和费用。

最终 Stage 11 验收还要做进程/容器重启与宿主机 reboot，并确认升级/回滚前后 `${AIMA_HOST_ROOT}` 中的持久状态保持。

---

# 18. 回滚

Schema 向后兼容时可切回旧应用 image 并 smoke；固定 `AIMA_HOST_ROOT` 不跟随应用版本回滚，因此 PostgreSQL/Artifact/内部 Secret 保持原位。

Schema 与旧应用不兼容时不能机械 `alembic downgrade`，应恢复发布前已验证 Backup Set 或使用 Migration 设计时明确的双版本兼容窗口，并说明数据损失窗口。

---

# 19. Backup 策略

具体频率必须等 RPO/RTO 批准后冻结。长期要求仍是周期性协调 Backup Set + 发布前 Backup Set + 定期完整恢复演练 + 每日检查 Backup 结果 + 磁盘容量告警。

---

# 20. Stage 11 应拆成哪些最小开发单元

Internal V1-A 已把 Docker/Compose 的最小运行基础提前实现并验证。Stage 11 不应重复造 Dockerfile/Compose，而应直接复用并加强这套基础。

## Stage 11A：Production Docker/Compose Hardening

基于 V1-A 增量完成不可变 image/digest、必要且有独立语义的 `compose.production.yaml`、生产 HTTPS/认证入口、资源/安全覆盖、CI linux/amd64 Release build 和 no-build/no-pull smoke。现有单一 `AIMA_HOST_ROOT` 模型继续复用，不重新拆回四个 Host Path。

## Stage 11B：离线 Release 构建

```text
images.tar
manifest
SHA256
SBOM
signature/来源验证
DEPLOY.md
no-build/no-pull smoke
```

## Stage 11C：协调 Backup/Restore

```text
maintenance/write barrier
Backup Set metadata
PostgreSQL dump
Artifact manifest/snapshot
restore
orphan reconciliation
RPO/RTO exercise
```

## Stage 11D：生产发布/回滚脚本

```text
preflight
backup
migrate
start
smoke
rollback
logs
```

## Stage 11E：真实生产服务器验收

```text
全新服务器初始化
离线部署
重启/重启机
受控业务 smoke
Backup restore
Rollback
安全/权限
持续观察
```

认证必须在完整 Production Release 对外/对组织开放前完成；Internal V1 的受控内网试运行不替代这个门禁。

---

# 21. 开发 Stage 11 时先读什么

```text
AGENTS.md
docs/roadmap/生产上线实施路线.md
docs/blueprint/01-总体架构与技术选型.md
docs/blueprint/03-数据库与文件存储.md
docs/blueprint/05-日志安全部署与运维.md
docs/blueprint/06-开发约束与分阶段实施.md
docs/blueprint/07-技术决策与实施门禁.md
本附录
docs/环境运行与部署.md
Dockerfile / compose.yaml / env.production.example
scripts/deploy/prepare_host.py
Platform Settings / entrypoints / storage / logging / health
migrations/
当前 CI workflows
```

然后只实施当前最小 Release 单元。

---

# 22. 当前禁止误写成已完成

Internal V1-A 可以准确描述为：

```text
“仓库已提供一条 Compose 命令启动的 Internal V1 最小部署栈”
“本地完整 Compose 与服务器 Compose 使用同一 Runtime Schema 和单一 AIMA_HOST_ROOT”
“PostgreSQL/Cursor 内部 Secret 自动生成并持久保存”
“外部 TikHub/LLM Key 经 Compose Secret File 装配，不进入业务容器普通环境变量”
“已在隔离 Linux Runner 验证空库 Migration、正式进程、Readiness、Secret 生命周期、绝对/相对 Host Root、持久挂载和端口边界”
```

但在后续 Production Change 和真实环境验收完成前，不得说：

```text
“已经完成正式生产部署闭环”
“生产服务器直接拿源码 build 即是正式 Release”
“已经支持完整离线 Release”
“数据库和 Artifact 可一致恢复”
“已经有生产回滚闭环”
“生产认证已经完成”
```

当前正确说法是：

> Internal V1-A 的最小容器部署基础、统一 Host Root 和启动体验已经闭环；完整 Production Release、认证和协调恢复仍属于后续待实现/待验收阶段。
