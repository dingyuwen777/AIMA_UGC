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

> **当前仓库已经通过 Internal V1-A 实现根 `Dockerfile`、canonical `compose.yaml`、`env.production.example`、宿主 bootstrap 与 Nginx Runtime。Linux/WSL 与公司服务器使用单一 `AIMA_HOST_ROOT` bind-mount 模型；Windows Docker Desktop 原生 CMD/PowerShell 仅叠加 `compose.windows.yaml` 把持久 storage source 替换为 Docker-managed named volumes，不形成第二套业务 Runtime，也不降低 Linux/Production 权限门禁。内部 PostgreSQL/Cursor Secret 仍由系统自动生成并持久保存，TikHub/LLM Key 由 `env.production` 进入 Compose Secret File，不作为业务容器环境变量。它仍不是完整 Stage 11 Production Release：离线 `images.tar`、Manifest、固定 digest、SBOM/签名、协调 Backup/Restore、企业认证/授权与真实生产服务器验收仍待后续正式 Change 完成。**

生产上线总路线见：

[`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

当前运行操作见：

- [`../02_环境运行与部署.md`](../02_环境运行与部署.md)
- [`../guides/03_Windows Docker Desktop Compose运行.md`](../guides/03_03_Windows%20Docker%20Desktop%20Compose运行.md)

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

当前部署还增加一个一次性 `bootstrap` 服务。它不是业务进程，也不常驻：只在 Compose 启动阶段以 root 准备持久目录/volume、生成或校验内部 Secret，成功后退出 0；PostgreSQL 只在 bootstrap 成功后启动。

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

canonical Compose 拓扑：

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

canonical Compose 从该根固定推导：

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

Linux / WSL 开发机可以把 Host Root 设为：

```dotenv
AIMA_HOST_ROOT=./.runtime/compose
```

这只是开发机的 canonical bind-mount Runtime 根，不改变生产服务器目录设计。

## 3.1 Windows Docker Desktop 不是 Production Host Root 模型

Windows 原生 CMD / PowerShell 为了避免 NTFS/Windows 文件共享层承担 PostgreSQL 与内部 Secret 的 Linux UID/GID/mode 语义，叠加 `compose.windows.yaml`，将四类持久 source 替换成 Docker-managed named volumes：

```text
windows_runtime_data
windows_runtime_logs
windows_postgres
windows_internal_secrets
```

这里没有把 `AIMA_HOST_ROOT` 改成另一个 Windows 路径，也没有新增 Production 目录规范。Windows named volumes 是**本地开发存储适配**，不能当作公司服务器 Backup/Restore、Release 或生产宿主目录方案。

---

# 4. 容器内目标路径

无论 Linux bind 还是 Windows named-volume override，容器内目标路径保持一致：

```text
/app/data
/app/logs
/run/internal-secrets   # Backend 内部随机 Secret
/run/secrets            # Compose 外部 Provider/LLM Secret；PostgreSQL 容器中用于 password file
/var/lib/postgresql
```

当前锁定 PostgreSQL 为 `18.4`。PostgreSQL 18 官方镜像使用 `/var/lib/postgresql` 作为持久卷挂载点，默认数据库目录位于其下 `18/docker`；canonical Linux Compose 把 `${AIMA_HOST_ROOT}/postgres` bind mount 到 `/var/lib/postgresql`，Windows override 则把 `windows_postgres` named volume 挂到同一 target。

后续真正完成 Stage 11 时仍必须重新验证当时锁定镜像的实际约定，不能把今天的路径无条件套到未来升级版本。

`bootstrap`/`scripts/deploy/prepare_host.py` 会：

- 建立/校验运行所需目录；
- 固定 App/PostgreSQL/Secret group UID/GID；
- 不用 `chmod 777`；
- 首次生成内部随机 Secret；
- 已有内部 Secret 只校验/收紧权限，不静默轮换；
- 已有 PostgreSQL 18 数据但密码 Secret 丢失时 fail closed；
- App 与 Frontend 继续使用非 root 用户运行。

Windows 支持**没有新增弱权限模式**。named volume 由 Linux Docker Runtime 管理，因此 bootstrap 仍执行同一严格 owner/mode 逻辑。

---

# 5. Secret 装配

## 5.1 内部随机 Secret

```text
postgres_password
import_batch_cursor_signing_key
content_cursor_signing_key
collection_runtime_cursor_signing_key
```

Linux / 公司服务器：

```text
首次空环境
→ bootstrap 随机生成
→ ${AIMA_HOST_ROOT}/shared/secrets 持久保存
→ root:11001 / 0440
→ Backend 只读挂载 /run/internal-secrets
```

Windows Docker Desktop：

```text
首次空环境
→ bootstrap 随机生成
→ windows_internal_secrets named volume
→ root:11001 / 0440
→ Backend 只读挂载 /run/internal-secrets
```

PostgreSQL 容器读取同一份 `postgres_password`。

关键恢复不变量在两种 storage source 中完全一致：

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

Windows `down -v` 会同时删除本地 PostgreSQL volume 和内部 Secret volume，因此属于显式破坏性本地重置；这不等同于 Production 恢复流程。

## 5.2 外部 TikHub / LLM Secret

管理员/开发者维护的真实 `env.production` 可以包含：

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

业务容器普通 `Config.Env` 不包含 API Key 原值。Provider Config 继续只保存 `secret_ref`。

Windows storage override 不修改外部 Secret 的 Compose 语义。

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

`.dockerignore` 不把源码开发脚本、`.runtime` 或真实 env 文件塞入运行镜像；Windows launcher/override 是宿主启动辅助，不改变镜像内容。

## Frontend Runtime

```text
Node build stage
→ npm ci
→ npm run build
→ 只把 dist 复制到 Nginx runtime
```

生产 Nginx 不包含 `node_modules`，并以非 root 用户运行。

V1-A 保持仓库现有锁定版本。完整 Stage 11 仍必须把最终实际 image digest 写入 Release Manifest，并建立来源/完整性验证；禁止把 `latest` 当不可追溯生产事实。

---

# 7. Compose 当前实现与 Stage 11 目标

## 7.1 canonical Compose

业务 Runtime 唯一基线是根：

```text
compose.yaml
```

它定义服务 command、environment、depends_on、Health、network、端口、外部 Secret 和 Linux/Production 持久 target。

Linux/WSL/Internal V1 管理员入口：

```bash
cp env.production.example env.production
chmod 0600 env.production
# 编辑 env.production
docker compose --env-file env.production up -d --build --wait
```

## 7.2 Windows storage-only override

Windows Docker Desktop 原生 CMD / PowerShell 使用：

```text
compose.yaml
+ compose.windows.yaml
+ 同一个 env.production
```

`compose.windows.yaml` 只替换以下 target 的 source：

```text
/app/data
/app/logs
/run/internal-secrets
/var/lib/postgresql
/run/secrets（PostgreSQL 内部密码目录）
/host/runtime/data
/host/runtime/logs
/host/postgres
/host/shared/secrets
```

对应 source 全部是 Docker named volume。禁止在 Windows override 中复制或单独演进业务 command/环境/Health/网络；否则会形成第二套 Runtime 漂移。

Windows wrapper：

```cmd
scripts\dev\compose_windows.cmd
```

```powershell
.\scripts\dev\compose_windows.ps1
```

它们只是隐藏 Compose 文件组合参数。

## 7.3 永久验证边界

- Internal V1-A workflow：真实 Linux bind-mount absolute/repo-relative Golden Path；
- Windows Runner：真实 CMD/PowerShell wrapper 参数和透传；
- Docker Engine：真实 `compose.yaml + compose.windows.yaml` named-volume startup、严格 Secret mode、PostgreSQL/Migration/Readiness 和 `down` 后重启持久化；
- Hosted Windows Runner 本身不作为真实 Docker Desktop Linux-container Runtime，因此首次个人 Windows 开发机仍要本机 smoke。

完整 Stage 11 若需要独立生产覆盖，可在正式 Release Change 中增加有独立语义的 `compose.production.yaml`，但不能只是复制根 Compose，也不能从 `compose.windows.yaml` 演化 Production 逻辑。

完整 Stage 11 仍必须实现：服务器不现场 build、固定镜像/digest/Manifest、离线 load、正式 HTTPS/认证授权、完整 offline/no-pull smoke 等。

---

# 8. 网络和浏览器安全边界

生产长期目标继续保留 HTTPS、明确 Host、同源、严格 CORS、HSTS、CSP、出站 Origin Allowlist 等要求。Internal V1-A 只完成最小公司内网部署所需的端口边界与同源 Nginx 代理；Windows 本地运行不改变 Production Browser Security 目标。

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

长期目标结构示例：

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

`v1.0.0` 只是结构示例；正式版本号在 Release Change 中确定。

`release-manifest.json` 至少记录 Release 版本、Git SHA、构建时间、target platform、image digest、Alembic head、Contract/OpenAPI hash、最低 Docker/Compose 版本、Migration 兼容/rollback 边界、SBOM/签名信息。

Production Bundle **不得携带当前生产 PostgreSQL、Artifact、日志或内部 Secret 内容**；它们继续位于固定 `AIMA_HOST_ROOT=/data/AIMA_UGC`。

`compose.windows.yaml` 属于本地开发辅助；是否随 Release Bundle 附带由 Stage 11B 的实际交付需求决定，但即使附带也不能成为服务器部署文件或生产持久化事实源。

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
→ canonical/production Compose up --no-build --pull never
```

禁止 `git pull`、现场 `npm install` / `pip install`、浏览器在线下载、现场 build 与 CI 不同镜像、临时编辑容器内部文件。

目标 Runtime 使用服务器自身受保护的：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

**生产服务器不使用 `compose.windows.yaml`。** Windows storage adapter 与服务器 Release/Backup/Restore 生命周期没有关系。

Internal V1-A/B 当前仓库级内网验收仍允许 `--build`，用于建立/验证最小部署基础；它不改变正式不可变 Release 原则。

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

Windows named volumes 只是开发机持久状态，不是 Production Backup Set。

---

# 15. 协调 Backup/Restore 目标机制

原设计核心机制仍是待实现目标：正常业务写使用共享 write lock；备份进入 maintenance、停止新 Job/Scheduler 写、取得独占 lock、等待 writer 退出、冻结新写、捕获 PostgreSQL + Artifact、验证 Backup Set 后释放。

具体 advisory lock key、表、状态机和脚本当前尚未实现，进入 Stage 11C 必须用正式 Change 设计并测试。不能只给两个独立备份文件同一个名字就称作“协调一致”。

---

# 16. 发布顺序

完整 Production 目标顺序仍是：确认目标 SHA/CI → 获取并验证 Release → 检查 Manifest/Migration/磁盘/Secret → 维护态/停止新写 → 协调 Backup Set → docker load → migrate → canonical/production compose start → health/smoke → 恢复 Scheduler/Worker → 观察日志/磁盘/失败 Job。

任何 Backup/Migration 校验失败必须停止继续发布，不能“先把新服务起来再说”。

---

# 17. 关键业务 Smoke

正式 Release 至少验证 `/health/live`、`/health/ready`、Frontend、数据库、Artifact、日志，以及 Excel Import → Content → Analysis → Excel Export，并在受控范围执行一次 Collection Run。真实付费 Provider/LLM smoke 必须限制请求和费用。

最终 Stage 11 验收还要做进程/容器重启与宿主机 reboot，并确认升级/回滚前后 `${AIMA_HOST_ROOT}` 中的持久状态保持。

Windows 本地 smoke 只能证明开发机兼容，不能代替这里的 Linux 生产验收。

---

# 18. 回滚

Schema 向后兼容时可切回旧应用 image 并 smoke；固定 `AIMA_HOST_ROOT` 不跟随应用版本回滚，因此 PostgreSQL/Artifact/内部 Secret 保持原位。

Schema 与旧应用不兼容时不能机械 `alembic downgrade`，应恢复发布前已验证 Backup Set 或使用 Migration 设计时明确的双版本兼容窗口，并说明数据损失窗口。

---

# 19. Backup 策略

具体频率必须等 RPO/RTO 批准后冻结。长期要求仍是周期性协调 Backup Set + 发布前 Backup Set + 定期完整恢复演练 + 每日检查 Backup 结果 + 磁盘容量告警。

---

# 20. Stage 11 应拆成哪些最小开发单元

Internal V1-A 已把 Docker/Compose 的最小运行基础提前实现并验证。Stage 11 不应重复造 Dockerfile/业务 Compose，而应直接复用并加强 canonical Linux 基础。

## Stage 11A：Production Docker/Compose Hardening

基于 V1-A 增量完成不可变 image/digest、必要且有独立语义的 `compose.production.yaml`、生产 HTTPS/认证入口、资源/安全覆盖、CI linux/amd64 Release build 和 no-build/no-pull smoke。现有单一 `AIMA_HOST_ROOT` Linux 模型继续复用。

Windows `compose.windows.yaml` 不进入 Stage 11A Production 逻辑。

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
全新 Linux 服务器初始化
离线部署
容器重启 / 宿主机 reboot
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
docs/roadmap/02_生产上线实施路线.md
docs/blueprint/01_总体架构与技术选型.md
docs/blueprint/03_数据库与文件存储.md
docs/blueprint/05_日志安全部署与运维.md
docs/blueprint/06_开发约束与分阶段实施.md
docs/blueprint/07_技术决策与实施门禁.md
本附录
docs/02_环境运行与部署.md
Dockerfile / compose.yaml / env.production.example
scripts/deploy/prepare_host.py
Platform Settings / entrypoints / storage / logging / health
migrations/
当前 CI workflows
```

Windows 本地兼容相关时额外读：

```text
compose.windows.yaml
scripts/dev/compose_windows.cmd
scripts/dev/compose_windows.ps1
docs/guides/03_Windows Docker Desktop Compose运行.md
.github/workflows/compose-windows-desktop.yml
```

然后只实施当前最小 Release 单元。

---

# 22. 当前禁止误写成已完成

当前可以准确描述为：

```text
“仓库已提供一条 canonical Compose 命令启动的 Internal V1 最小部署栈”
“Linux/WSL 本地与服务器复用同一 Runtime Schema 和单一 AIMA_HOST_ROOT”
“Windows Docker Desktop 原生 CMD/PowerShell 可复用同一业务 Runtime，并通过 storage-only named-volume override 兼容本地文件系统”
“Windows 支持未放宽 Linux/Production Secret/PostgreSQL 权限门禁”
“PostgreSQL/Cursor 内部 Secret 自动生成并持久保存”
“外部 TikHub/LLM Key 经 Compose Secret File 装配，不进入业务容器普通环境变量”
```

但在后续 Production Change 和真实环境验收完成前，不得说：

```text
“已经完成正式生产部署闭环”
“生产服务器直接拿源码 build 即是正式 Release”
“已经支持完整离线 Release”
“Windows Docker Desktop 本地通过等于公司服务器已验收”
“数据库和 Artifact 可一致恢复”
“已经有生产回滚闭环”
“生产认证已经完成”
```

当前正确说法是：

> Internal V1-A 的 canonical 容器部署基础、本地跨宿主适配和启动体验已逐步闭环；完整 Production Release、认证和协调恢复仍属于后续待实现/待验收阶段。
