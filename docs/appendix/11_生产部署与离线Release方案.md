# 生产部署与离线 Release 方案

这篇文档用于持续完成 **Stage 11：Production Release**，并记录 Internal V1 与 GitHub 离线 Release 已经落地、后续 Production 强化必须直接复用的部署基础。

它同时记录两类事实：

```text
当前已经实现
→ 可以直接从仓库代码和永久 Workflow 验证

已批准目标 / 待实现
→ 后续必须按 Change 开发，不能现在假装已经完成
```

当前结论先写在前面：

> **当前仓库已经通过 Internal V1-A 实现根 `Dockerfile`、canonical `compose.yaml`、`env.production.example`、宿主 bootstrap 与 Nginx Runtime，并新增 `.github/workflows/release.yml` 建立 GitHub 一键离线 Release 基础。Release Workflow 在 GitHub Hosted Linux Runner 内显式使用 Docker Hub / Debian / PyPI / npm 官方上游构建 Linux/AMD64 Backend/Frontend，固定官方 `postgres:18.4`，生成 `images.tar`、release/migration manifest、`SHA256SUMS` 与 `DEPLOY.md`，并在 PR dry-run 中删除候选运行镜像后从 `images.tar` 重新 load，以 canonical Compose 的 `--no-build --pull never` 完成真实启动回放。正式 `workflow_dispatch` 路径只允许当前 `main` 最新 SHA，具备推送 GHCR、记录应用 digest、创建 Git Tag 与 GitHub Release 的能力；正式业务版本仍由用户在合并后手工触发。Linux/WSL 与公司服务器继续使用单一 `AIMA_HOST_ROOT`，Windows Docker Desktop 仍只叠加 storage-only `compose.windows.yaml`。当前仍不是完整 Production Go-Live：协调 Backup/Restore、企业认证/授权、HTTPS、SBOM/独立来源签名/provenance、生产服务器发布/回滚与真实生产验收仍待后续正式 Change。**

生产上线总路线见：

[`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

当前运行操作见：

- [`../02_环境运行与部署.md`](../02_环境运行与部署.md)
- [`../guides/03_Windows Docker Desktop Compose运行.md`](../guides/03_Windows%20Docker%20Desktop%20Compose运行.md)

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

因此 Stage 11 不应重新设计业务代码或另造一套运行时，而是在 V1-A 已验证的容器/配置边界和当前 GitHub Release 基础上继续完成**不可变、可验证、可恢复的正式 Production Release**。

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
| `/data/AIMA_UGC/releases` | 不可变 Release 版本 | 支持保留/切换应用版本，不承载持久业务数据 |
| `/data/AIMA_UGC/shared/env` | 可选共享配置目录 | 不能当作 Secret Manager；真实 env 文件本身需按敏感文件保护 |
| `/data/AIMA_UGC/shared/secrets` | AIMA 内部随机 Secret | 与 PostgreSQL 数据一起持久保护 |

不要把 PostgreSQL、Artifact、日志全部塞进 `/data/docker`，也不要把 `AIMA_HOST_ROOT` 指向 `/data/AIMA_UGC/releases/<version>`。

Linux / WSL 开发机可以把 Host Root 设为：

```dotenv
AIMA_HOST_ROOT=./.runtime/compose
```

这只是开发机的 canonical bind-mount Runtime 根，不改变生产服务器目录设计。

## 3.1 Windows Docker Desktop 不是 Production Host Root 模型

Windows 原生 CMD / PowerShell 为了避免 NTFS/Windows 文件共享层承担 PostgreSQL 与内部 Secret 的 Linux UID/GID/mode 语义，叠加 `compose.windows.yaml`。当前混合存储是：

```text
AIMA_HOST_ROOT/runtime/data
→ Artifact bind mount

AIMA_HOST_ROOT/runtime/logs
→ 应用日志 bind mount

windows_postgres
→ PostgreSQL named volume

windows_internal_secrets
→ 内部 Secret named volume
```

这里没有把 `AIMA_HOST_ROOT` 改成另一个生产路径，也没有新增 Production 目录规范。Windows mixed storage 是**本地开发存储适配**，不能当作公司服务器 Backup/Restore、Release 或生产宿主目录方案。

---

# 4. 容器内目标路径

无论 Linux bind 还是 Windows storage-only override，容器内目标路径保持一致：

```text
/app/data
/app/logs
/run/internal-secrets   # Backend 内部随机 Secret
/run/secrets            # Compose 外部 Provider/LLM Secret；PostgreSQL 容器中用于 password file
/var/lib/postgresql
```

当前锁定 PostgreSQL 为 `18.4`。PostgreSQL 18 官方镜像使用 `/var/lib/postgresql` 作为持久卷挂载点，默认数据库目录位于其下 `18/docker`；canonical Linux Compose 把 `${AIMA_HOST_ROOT}/postgres` bind mount 到 `/var/lib/postgresql`，Windows override 则把 `windows_postgres` named volume 挂到同一 target。

未来升级 PostgreSQL 时仍必须重新验证当时锁定镜像的实际约定，不能把当前路径无条件套到未来主版本。

`bootstrap`/`scripts/deploy/prepare_host.py` 会：

- 建立/校验运行所需目录；
- 固定 App/PostgreSQL/Secret group UID/GID；
- 不用 `chmod 777`；
- 首次生成内部随机 Secret；
- 已有内部 Secret 只校验/收紧权限，不静默轮换；
- 已有 PostgreSQL 18 数据但密码 Secret 丢失时 fail closed；
- App 与 Frontend 继续使用非 root 用户运行。

Windows bind-compatible 支持只作用于 Artifact/日志目录；PostgreSQL 与内部 Secret 仍由 Linux Docker Runtime 管理并执行严格权限边界。

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

Windows `down -v` 会删除本地 PostgreSQL volume 和内部 Secret volume，因此属于显式破坏性本地重置；它不会自动删除 bind-mounted Artifact/日志，也不等同于 Production 恢复流程。

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

GitHub Release PR dry-run 不读取真实 TikHub/LLM Secret，正式 Release 构建也只构建/打包镜像，不把这些 Secret 写入镜像或 Bundle。

---

# 6. Dockerfile 当前实现与 Release 构建源

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

## Release Runner 与本地源隔离

`Dockerfile`、`compose.yaml`、`env.production.example` 继续保留面向国内本地/公司环境的默认 Debian/PyPI/npm 下载源；Docker Hub 下载加速仍由宿主 Docker Engine mirror 负责。

`.github/workflows/release.yml` 只在 GitHub Hosted Linux Runner 内显式通过 build args 覆盖为：

```text
Docker 基础镜像 / PostgreSQL → Docker Hub canonical reference
Debian                       → http://deb.debian.org/debian
Debian Security              → http://deb.debian.org/debian-security
PyPI                         → https://pypi.org/simple
npm                          → https://registry.npmjs.org
```

因此 Release 的海外下载源**不会修改或影响本地 Windows/Linux 的默认构建源**；二者只改变下载路径，不改变锁定版本、lockfile、镜像 tag 或业务 Runtime Contract。

当前 Release Workflow 固定构建 `linux/amd64`。正式 `workflow_dispatch` 推送 Backend/Frontend 到 GHCR，并在 manifest 记录实际 registry digest；PostgreSQL 固定记录官方 `postgres:18.4` repo digest。禁止使用 `latest` 作为发布事实。

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

GitHub Release Bundle 同样直接携带 canonical `compose.yaml`，不为“一键 Release”复制第二套 Runtime。只有未来确实出现独立生产语义时，才新增最小 `compose.production.yaml` 覆盖。

## 7.2 Windows storage-only override

Windows Docker Desktop 原生 CMD / PowerShell 使用：

```text
compose.yaml
+ compose.windows.yaml
+ 同一个 env.production
```

当前 Windows override 只替换/适配持久 storage source；Artifact/日志仍落到 `AIMA_HOST_ROOT` 可见目录，PostgreSQL/内部 Secret 使用 Docker named volume。禁止在 Windows override 中复制或单独演进业务 command/环境/Health/网络；否则会形成第二套 Runtime 漂移。

CMD / PowerShell 直接执行标准 Docker Compose CLI：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

不再维护额外 Compose wrapper。

## 7.3 永久验证边界

- Internal V1-A workflow：真实 Linux bind-mount absolute/repo-relative Golden Path；
- Windows Runner：真实 CMD/PowerShell 标准 Compose CLI 参数；
- Docker Engine：真实 `compose.yaml + compose.windows.yaml` hybrid startup、Host Root Artifact/log、严格 Secret mode、PostgreSQL/Migration/Readiness 和持久化生命周期；
- Release PR dry-run：真实 GitHub Hosted Linux Runner build → `images.tar` → 删除本地候选运行镜像 tag → `docker load` → canonical Compose `--no-build --pull never --wait` → Migration/Readiness/持久目录；
- Hosted Windows Runner 本身不作为真实 Docker Desktop Linux-container Runtime，因此首次个人 Windows 开发机仍要本机 smoke。

完整 Stage 11 若需要独立生产覆盖，可在正式 Production Change 中增加有独立语义的 `compose.production.yaml`，但不能只是复制根 Compose，也不能从 `compose.windows.yaml` 演化 Production 逻辑。

---

# 8. 网络和浏览器安全边界

生产长期目标继续保留 HTTPS、明确 Host、同源、严格 CORS、HSTS、CSP、出站 Origin Allowlist 等要求。Internal V1-A 只完成最小公司内网部署所需的端口边界与同源 Nginx 代理；GitHub Release Workflow 只解决不可变交付，不自动补齐浏览器安全或认证。

---

# 9. 认证是完整 Production 前置，而不是发布脚本完成后就消失

当前没有正式企业认证闭环。经批准的 Internal V1 路线把认证明确延期到完整 Production 阶段，因此 Internal V1-A/V1-B 的受控公司内网验收和 GitHub Release Bundle 都不能被描述成最终生产安全闭环。

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

# 10. 当前 Release Workflow 与 Bundle 结构

## 10.1 Actions 手工发布入口

正式发布从默认分支执行：

```text
GitHub → Actions → Release → Run workflow
Branch: main
version: vMAJOR.MINOR.PATCH
```

Workflow 会拒绝：

- 非 `main` 手工发布；
- 当前 Workflow SHA 已不是远端 `main` 最新 SHA；
- 非标准 SemVer；
- 已存在的 Tag/Release；
- 要求的 `main` CI 门禁不为 success。

PR 只运行 dry-run，不推 GHCR、不创建 Tag/Release，因此开发验证不会污染正式版本历史。

## 10.2 当前实际 Bundle

当前正式资产结构为：

```text
GitHub Release
├─ AIMA_UGC-vX.Y.Z-deploy.tar.gz
├─ release-manifest.json
├─ migration-manifest.json
└─ SHA256SUMS
```

部署压缩包内部：

```text
AIMA_UGC-vX.Y.Z-deploy.tar.gz
├─ images.tar
├─ compose.yaml
├─ env.production.example
├─ release-manifest.json
├─ migration-manifest.json
├─ SHA256SUMS
└─ DEPLOY.md
```

`images.tar` 包含：

```text
aima-ugc-backend:vX.Y.Z
aima-ugc-frontend:vX.Y.Z
postgres:18.4
```

`release-manifest.json` 当前记录 Release 版本、Git SHA、构建时间、`linux/amd64`、构建上游、镜像身份、Alembic head、OpenAPI SHA256、发布方式以及当前 SBOM/独立签名尚未包含的事实。正式 `workflow_dispatch` 还记录 GHCR Backend/Frontend repo digest；PostgreSQL 始终记录官方 repo digest。

`migration-manifest.json` 当前记录 Alembic head、`alembic upgrade head`、独立 migrate service，以及“没有自动 Schema rollback / 没有协调 Backup/Restore”的真实边界。

Production Bundle **不得携带当前生产 PostgreSQL、Artifact、日志、真实 `env.production` 或内部/外部 Secret 内容**；它们继续位于固定 `AIMA_HOST_ROOT=/data/AIMA_UGC`。

`compose.windows.yaml` 不进入服务器 Release Bundle。

## 10.3 长期完整 Production Bundle 仍需补什么

后续完整 Production 治理仍要增加：

```text
SBOM/
SIGNATURES/ 或等价独立来源签名/provenance
最低 Docker/Compose 兼容事实与机器验证
完整 Migration compatibility / rollback 治理
协调 Backup/Restore 关联信息
```

如果未来出现真实独立生产 Compose 语义，再把最小 `compose.production.yaml` 纳入 Bundle；不能为了目录看起来完整而复制一份 canonical Compose。

---

# 11. 为什么不能只校验 SHA256

当前 `SHA256SUMS` 已用于 Bundle 文件完整性校验，但它只能证明文件和清单一致；如果攻击者同时替换 release 与 SHA 文件，不能独立证明来源。因此完整 Production 目标仍需要独立受信签名或有身份/完整性证明的 Artifact Registry/provenance。

GHCR digest 提供不可变镜像身份审计价值，但不能自动替代所有 Release 资产的独立签名。

---

# 12. 服务器离线部署原则

GitHub Release Bundle 已把正式服务器的目标路径落成：

```text
获取已验证 Release
→ sha256sum -c
→ docker load -i images.tar
→ 准备服务器自己的 env.production
→ docker compose config --quiet
→ docker compose up --no-build --pull never --wait
→ health / smoke
```

禁止 `git pull`、现场 `npm install` / `pip install`、浏览器在线下载、现场 build 与 CI 不同镜像、临时编辑容器内部文件。

目标 Runtime 使用服务器自身受保护的：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

**生产服务器不使用 `compose.windows.yaml`。** Windows storage adapter 与服务器 Release/Backup/Restore 生命周期没有关系。

Internal V1-A/B 仍允许仓库源码 `--build` 以完成当前公司内网服务器验证；一旦使用 GitHub Release 资产，则应走 `docker load + --no-build --pull never`，不能把现场 build 当作同一个 Release。

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

GitHub Release Workflow 不包含业务数据，因此不会替代 Backup Set。重新拉取/加载 `postgres:18.4` 镜像也不会备份或删除 `${AIMA_HOST_ROOT}/postgres`；镜像和数据生命周期必须继续分开。

Windows named volumes 只是开发机持久状态，不是 Production Backup Set。

---

# 15. 协调 Backup/Restore 目标机制

原设计核心机制仍是待实现目标：正常业务写使用共享 write lock；备份进入 maintenance、停止新 Job/Scheduler 写、取得独占 lock、等待 writer 退出、冻结新写、捕获 PostgreSQL + Artifact、验证 Backup Set 后释放。

具体 advisory lock key、表、状态机和脚本当前尚未实现，进入 Stage 11C 必须用正式 Change 设计并测试。不能只给两个独立备份文件同一个名字就称作“协调一致”。

---

# 16. 发布顺序

## 16.1 当前一键 Release 已完成的 GitHub 侧顺序

```text
确认 main 最新 SHA / SemVer / Tag-Release 不重复 / 必要 CI
→ GitHub Runner 使用官方上游构建 linux/amd64 Backend/Frontend
→ 拉取并固定 postgres:18.4 digest
→ 生成 images.tar + manifest + SHA256 + DEPLOY
→ 删除 Runner 上本地候选运行镜像 tag
→ 从 images.tar 重新 docker load
→ canonical Compose --no-build --pull never
→ Migration / Readiness / 持久目录 smoke
→ 正式 workflow_dispatch 的 publish job 复用已回放候选，推送 GHCR 版本/SHA tag 并记录 digest
→ 创建 Git Tag + GitHub Release
```

PR 模式完整执行构建、Bundle 和离线回放，但跳过 GHCR publish 与 Tag/Release。

## 16.2 完整 Production 服务器侧顺序仍待闭环

完整 Production 目标顺序仍是：获取并验证 Release → 检查 Manifest/Migration/磁盘/Secret → 维护态/停止新写 → 协调 Backup Set → docker load → migrate → canonical/production compose start → health/smoke → 恢复 Scheduler/Worker → 观察日志/磁盘/失败 Job。

任何 Backup/Migration 校验失败必须停止继续发布，不能“先把新服务起来再说”。当前 GitHub Release Workflow 没有自动执行服务器维护态或协调 Backup，因此不能把 GitHub Release 成功等同于生产发布闭环成功。

---

# 17. 关键业务 Smoke

Release PR dry-run 当前验证基础运行 Golden Path：bootstrap、PostgreSQL、Migration、configure、API/Worker/Scheduler/Frontend readiness，以及 Host Root PostgreSQL/日志目录。

正式 Production Release 还至少要验证 `/health/live`、`/health/ready`、Frontend、数据库、Artifact、日志，以及 Excel Import → Content → Analysis → Excel Export，并在受控范围执行一次 Collection Run。真实付费 Provider/LLM smoke 必须限制请求和费用。

最终 Stage 11 验收还要做进程/容器重启与宿主机 reboot，并确认升级/回滚前后 `${AIMA_HOST_ROOT}` 中的持久状态保持。

GitHub Hosted Runner 和 Windows 本地 smoke 都不能代替真实 Linux 生产/公司服务器验收。

---

# 18. 回滚

Schema 向后兼容时可切回旧应用 image 并 smoke；固定 `AIMA_HOST_ROOT` 不跟随应用版本回滚，因此 PostgreSQL/Artifact/内部 Secret 保持原位。

Schema 与旧应用不兼容时不能机械 `alembic downgrade`，应恢复发布前已验证 Backup Set 或使用 Migration 设计时明确的双版本兼容窗口，并说明数据损失窗口。

GitHub Release Workflow 当前不会覆盖或删除已有 Tag/Release，也不提供数据库自动回滚；这种保守边界是刻意的。

---

# 19. Backup 策略

具体频率必须等 RPO/RTO 批准后冻结。长期要求仍是周期性协调 Backup Set + 发布前 Backup Set + 定期完整恢复演练 + 每日检查 Backup 结果 + 磁盘容量告警。

---

# 20. Stage 11 应拆成哪些最小开发单元

Internal V1-A 已把 Docker/Compose 的最小运行基础提前实现并验证；GitHub 一键离线 Release 又完成了可重复构建、Bundle 和 no-build/no-pull 回放基础。Stage 11 不应重复造 Dockerfile/业务 Compose，而应直接复用并加强 canonical Linux 基础。

## Stage 11A：Production Docker/Compose Hardening

当前已具备：canonical Docker/Compose 基础、linux/amd64 Release build、正式 GHCR digest 路径、官方 PostgreSQL digest、no-build/no-pull smoke。

后续增量：只有存在独立生产语义时才增加 `compose.production.yaml`；完成生产 HTTPS/认证入口、Host/浏览器安全、资源/安全覆盖和完整 provenance 约束。

Windows `compose.windows.yaml` 不进入 Stage 11A Production 逻辑。

## Stage 11B：离线 Release 构建

当前基础已实现：

```text
images.tar
release/migration manifest
SHA256
DEPLOY.md
no-build/no-pull smoke
GitHub Tag/Release 正式发布路径
GHCR 应用镜像正式发布路径
```

仍待生产治理：

```text
SBOM
signature/独立来源验证/provenance
最低 Docker/Compose 兼容矩阵
完整 Migration compatibility/rollback 元数据
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

## Stage 11D：生产发布/回滚自动化

GitHub 侧构建/发布已经建立；服务器侧仍需：

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
.github/workflows/release.yml
scripts/deploy/prepare_host.py
Platform Settings / entrypoints / storage / logging / health
migrations/
当前 CI workflows
```

Windows 本地兼容相关时额外读：

```text
compose.windows.yaml
docs/guides/03_Windows Docker Desktop Compose运行.md
.github/workflows/compose-windows-desktop.yml
```

然后只实施当前最小 Release 单元。

---

# 22. 当前可以和禁止怎样描述

当前可以准确描述为：

```text
“仓库已提供一条 canonical Compose 命令启动的 Internal V1 最小部署栈”
“Linux/WSL 本地与服务器复用同一 Runtime Schema 和单一 AIMA_HOST_ROOT”
“Windows Docker Desktop 原生 CMD/PowerShell 可复用同一业务 Runtime，并通过 storage-only mixed storage 兼容本地文件系统”
“Windows 支持未放宽 Linux/Production Secret/PostgreSQL 权限门禁”
“PostgreSQL/Cursor 内部 Secret 自动生成并持久保存”
“外部 TikHub/LLM Key 经 Compose Secret File 装配，不进入业务容器普通环境变量”
“GitHub Release Workflow 已建立 Linux/AMD64 一键离线 Release 基础，并在 PR 中验证 images.tar 可独立 no-build/no-pull 回放”
“GitHub Release 构建官方海外上游只作用于 Workflow，本地国内默认源不变”
```

但在后续 Production Change 和真实环境验收完成前，不得说：

```text
“已经完成正式生产部署闭环”
“GitHub Release 成功等于生产服务器已发布成功”
“已经有协调 PostgreSQL + Artifact Backup/Restore”
“已经有数据库自动回滚闭环”
“已经有 SBOM + 独立来源签名/provenance 完整闭环”
“Windows Docker Desktop 或 GitHub Hosted Runner 通过等于公司/生产服务器已验收”
“生产认证/HTTPS 已经完成”
```

当前正确说法是：

> Internal V1-A 的 canonical 容器部署基础、Windows 本地存储适配和 GitHub 一键离线 Release 基础已经建立；完整 Production Security、协调恢复、来源证明、服务器侧发布/回滚与真实生产验收仍属于后续待实现/待验收阶段。
