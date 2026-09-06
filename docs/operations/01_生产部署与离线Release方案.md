# 生产部署与离线 Release 方案

本文维护 AIMA_UGC **当前已经存在的部署与离线 Release 能力、服务器运行方法，以及尚未闭环的 Production 操作边界**。

本文不是施工阶段记录。历史上 Internal V1、Release 建设过程和当时的 CI/PR 证据由 [`changes/archive/`](../../changes/archive/) 与 Git 历史承载；完整 Production 尚未完成的目标统一由 [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md) 维护。

## 1. 当前结论

当前仓库已经具备：

- 根 [`Dockerfile`](../../Dockerfile) 与 canonical [`compose.yaml`](../../compose.yaml)；
- [`env.production.example`](../../env.production.example) 作为服务器配置模板；
- API / Worker / Scheduler / Migration 分进程；
- 一次性 bootstrap 与 configure；
- PostgreSQL 18、Local ArtifactStore、应用日志和内部 Secret 的持久化边界；
- Linux/WSL/公司服务器统一 `AIMA_HOST_ROOT`；
- Windows Docker Desktop 的 storage-only [`compose.windows.yaml`](../../compose.windows.yaml)；
- [`.github/workflows/release.yml`](../../.github/workflows/release.yml) 的 GitHub 离线 Release 基础；
- `linux/amd64` Backend/Frontend 镜像与固定 `postgres:18.4`；
- `images.tar`、`release-manifest.json`、`migration-manifest.json`、`SHA256SUMS`、`DEPLOY.md`；
- PR Release dry-run 的离线重放；
- 正式手工 Release 的 GHCR digest、Git Tag 和 GitHub Release 基础；
- 服务器侧 `docker load` 后以 `--no-build --pull never` 启动已验证镜像的能力。

因此不能再把 Dockerfile、Compose、离线 Bundle 或 no-build/no-pull 重放整体描述成“尚未实现”。

完整 Production 仍是 **No-Go**。当前未闭环项包括企业 Authentication、HTTPS/浏览器安全、协调 PostgreSQL + Artifact Backup/Restore、SBOM/独立签名/provenance、正式服务器发布/回滚闭环，以及真实生产安全、容量、Soak 和恢复验收。详见 [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)。

日常源码/本地运行见 [`docs/02_环境运行与部署.md`](../02_环境运行与部署.md)；Windows Docker Desktop 见 [`docs/guides/03_Windows Docker Desktop Compose运行.md`](../guides/03_Windows%20Docker%20Desktop%20Compose运行.md)。

---

## 2. 运行拓扑

canonical Compose 的启动关系是：

```text
bootstrap（一次性）
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

长期业务进程职责：

| 服务 | 职责 |
| --- | --- |
| `frontend` | Vue 静态资源 + Nginx，同源代理 `/api` 与 `/health` |
| `api` | HTTP 查询、短事务、创建持久 Job；不执行分钟级长任务 |
| `worker` | 执行 Collection / Import / Analysis / Export 等 PostgreSQL Durable Job |
| `scheduler` | 将到期 Plan 转成 Occurrence / Run / Job，不直接请求 TikHub |
| `migrate` | 独立执行 `alembic upgrade head`，完成后退出 |
| `postgres` | 唯一业务事实库 |

`bootstrap` 与 `configure` 都是部署装配动作，不是常驻业务服务。Worker 当前实际注册内容以 [`backend/src/aima_ugc/bootstrap/worker.py`](../../backend/src/aima_ugc/bootstrap/worker.py) 为机器事实。

---

## 3. 服务器 Host Root 与持久数据

公司 Linux 服务器长期使用一个稳定业务根：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

canonical Compose 从它派生：

```text
/data/AIMA_UGC/postgres
/data/AIMA_UGC/runtime/data
/data/AIMA_UGC/runtime/logs
/data/AIMA_UGC/shared/secrets
```

推荐长期运维目录还包括：

```text
/data/docker
/data/AIMA_UGC/backups
/data/AIMA_UGC/releases
/data/AIMA_UGC/shared/env
```

边界固定为：

- `/data/docker`：Docker 自身镜像、层和容器元数据；
- `/data/AIMA_UGC/postgres`：PostgreSQL 数据；
- `/data/AIMA_UGC/runtime/data`：Local ArtifactStore 文件；
- `/data/AIMA_UGC/runtime/logs`：API/Worker/Scheduler 应用日志；
- `/data/AIMA_UGC/shared/secrets`：AIMA 内部随机 Secret；
- `/data/AIMA_UGC/releases`：不可变应用 Release，不承载在线业务数据；
- `/data/AIMA_UGC/backups`：未来正式协调 Backup Set 的存放边界。

`AIMA_HOST_ROOT` 不能指向某个 `/releases/<version>`。应用版本可以切换，业务持久根不能随版本切换。

Linux / WSL 开发机可以使用仓库相对 Host Root；这只是开发环境路径差异，不改变服务器持久化语义。

---

## 4. Secret 装配与恢复边界

### 4.1 内部随机 Secret

当前内部 Secret 包括 PostgreSQL password 和多个 Cursor signing key。Linux/公司服务器由 bootstrap 首次生成并保存到 `${AIMA_HOST_ROOT}/shared/secrets`，Backend 只读挂载到 `/run/internal-secrets`。

必须保持：

```text
空数据库 + password 不存在
→ 可以首次生成

已有 PostgreSQL 数据 + password 存在
→ 复用原 Secret

已有 PostgreSQL 数据 + password 不存在
→ fail closed
→ 恢复原 Secret
→ 禁止猜测或静默生成新密码
```

### 4.2 外部 Provider / LLM Secret

真实 `env.production` 可以输入 TikHub/LLM API Key，因此它本身是敏感文件：必须 Git ignore、限制宿主文件权限，不得提交、打印或打入镜像/Release 明文。

运行边界：

```text
env.production
→ Compose Secret
→ /run/secrets
→ AIMA_EXTERNAL_SECRET_DIR
→ Secret resolver
```

Provider Config 只保存 `secret_ref`。业务容器普通环境变量、日志、Raw、Job Payload、Export 和 Release Bundle 都不能包含 Secret 原值。

---

## 5. Docker 与 Compose 的单一运行基线

业务 Runtime 唯一基线是根 [`Dockerfile`](../../Dockerfile) 与 [`compose.yaml`](../../compose.yaml)。Docker build context 固定为仓库根；Backend 与 Frontend 通过不同 target 构建，不形成第二套工程根。

当前 Runtime 关键不变量：

- Backend/Frontend 正式常驻进程非 root；
- Migration 保持独立一次性进程；
- bootstrap 只在初始化阶段以所需权限运行并退出；
- PostgreSQL/API 不向普通宿主客户端发布业务端口；
- Frontend/Nginx 是正常浏览器入口；
- PostgreSQL、Artifact、日志和 Secret 不依赖容器可写层；
- 镜像构建与 Runtime 不把真实 Secret 写入镜像。

未来只有出现真正独立的生产语义时才考虑增加最小 Production override；不能为了目录对称复制一份 canonical Compose。

---

## 6. Windows Docker Desktop 的边界

Windows 原生 CMD/PowerShell 叠加 [`compose.windows.yaml`](../../compose.windows.yaml)，但只改变持久 storage source：

```text
Artifact / 应用日志
→ AIMA_HOST_ROOT bind mount

PostgreSQL / 内部 Secret
→ Docker-managed named volumes
```

API、Worker、Scheduler、Migration、Health、网络、端口、外部 Secret 和业务配置仍来自 canonical Compose。

因此 Windows mixed storage 是**开发机存储适配**，不是 Production Host Root、Backup/Restore 或服务器 Release 模型。Production Bundle 不携带 `compose.windows.yaml`。

---

## 7. Release Workflow 当前做什么

正式机器入口：

- [`.github/workflows/release.yml`](../../.github/workflows/release.yml)

PR 触发时执行 Release dry-run，不推送 GHCR、不创建 Tag/Release。正式 `workflow_dispatch` 从默认分支执行，版本使用标准 SemVer，并校验当前发布 SHA 仍是远端 `main` 最新 SHA及所需主分支门禁。

当前 GitHub Release 构建使用明确的官方上游下载源，避免把开发机/公司网络的镜像加速配置变成发布来源事实；这不会修改本地 Dockerfile/Compose 中的镜像身份或 lockfile。

构建和发布链：

```text
main / PR candidate
→ 构建 linux/amd64 Backend + Frontend
→ 固定 postgres:18.4
→ 生成离线 Bundle
→ PR: 删除候选运行镜像后从 images.tar 重新 docker load
→ canonical Compose --no-build --pull never --wait
→ Migration / Readiness / 持久目录 smoke
→ 正式 workflow_dispatch: 推送 GHCR 并记录 digest
→ 创建 Git Tag / GitHub Release
```

禁止使用 `latest` 作为正式发布身份。

---

## 8. 当前离线 Bundle

GitHub Release 当前发布资产包括：

```text
AIMA_UGC-vX.Y.Z-deploy.tar.gz
release-manifest.json
migration-manifest.json
SHA256SUMS
```

部署压缩包内部包括：

```text
images.tar
compose.yaml
env.production.example
release-manifest.json
migration-manifest.json
SHA256SUMS
DEPLOY.md
```

`images.tar` 包含当前版本 Backend/Frontend 镜像和固定 PostgreSQL 镜像。`release-manifest.json` 记录版本、Git SHA、构建时间、`linux/amd64`、镜像身份、Alembic head、OpenAPI SHA256 和当前发布能力边界；正式发布路径额外记录应用 registry digest。

`migration-manifest.json` 记录 Alembic head、正式 upgrade 动作和当前没有自动 Schema rollback / 协调 Backup/Restore 的事实。

Bundle **不得包含**：

- 生产 PostgreSQL 数据；
- Artifact/日志；
- 真实 `env.production`；
- 内部或外部 Secret。

---

## 9. 服务器离线部署

正式服务器取得已经验证的 Bundle 后，运行原则是：

```text
校验 SHA256SUMS
→ docker load -i images.tar
→ 使用服务器自己的受保护 env.production
→ docker compose config --quiet
→ docker compose up --no-build --pull never --wait
→ health / business smoke
```

禁止把正式 Release 变成：

- `git pull` 后现场构建；
- 服务器现场 `pip install` / `npm install`；
- 临时编辑容器内部文件；
- 使用与 CI 不同的镜像身份；
- 为了部署方便绕过 Migration/Readiness/Secret 门禁。

服务器继续使用稳定 `AIMA_HOST_ROOT=/data/AIMA_UGC`，Release 目录只保存应用版本。

---

## 10. 发布前检查

每次正式部署至少确认：

1. Release/Tag/SHA 与批准版本一致；
2. Bundle `SHA256SUMS` 校验通过；
3. `release-manifest.json` 与目标平台、镜像身份一致；
4. `migration-manifest.json` 与当前数据库升级路径一致；
5. `env.production` 与 Secret 文件已在目标机按权限准备；
6. Host Root、磁盘和数据库状态满足本次操作要求；
7. 若本次 Migration/写操作存在不可逆风险，已经具备本次批准的恢复边界；
8. 当前 Production Roadmap 中与本次部署相关的认证、安全、Backup/Restore 或验收前置条件没有被跳过。

没有独立供应链签名/provenance 之前，`SHA256SUMS` 只能证明文件集合内部一致，不能单独证明发布来源。

---

## 11. Smoke 与运行证据

Release dry-run 目前证明的是候选 Bundle 可以离线加载并启动 canonical Runtime，不等于真实生产环境已经验收。

正式服务器至少检查：

```text
/health/live
/health/ready
Frontend
PostgreSQL
ArtifactStore
应用日志
Migration 状态
关键业务入口
```

生产候选环境还应根据实际发布影响运行高价值业务 Smoke，例如：

```text
Excel Import
→ Content
→ Voice Plaza
→ Analysis
→ Excel Export
```

需要真实 TikHub/LLM 时必须显式控制请求数、费用和数据范围。GitHub Runner、开发机 Docker 或 Browser Mock 都不能替代真实生产候选环境的安全/恢复/容量证据。

---

## 12. Backup / Restore 边界

AIMA 的持久业务事实不只在 PostgreSQL。Content 来源链可能同时依赖：

```text
PostgreSQL metadata / business rows
+
ArtifactStore bytes
```

因此完整 Production 的恢复单位必须是协调的：

```text
Backup Set = PostgreSQL + ArtifactStore
```

当前完整协调 Backup/Restore **尚未实现**。不能把独立数据库 dump、独立文件拷贝或 Release Bundle 称为已经验证的一致性 Backup Set。

正式实现目标包括：维护/写屏障、一致性点、PostgreSQL 捕获、Artifact manifest/snapshot、校验和、Restore、数据库↔Artifact reconciliation、RPO/RTO 和恢复演练。具体实施属于 [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md) 中独立高风险工作。

---

## 13. 回滚

应用回滚和数据恢复必须区分。

### 应用版本可兼容当前 Schema

```text
切换到已验证旧镜像
→ 使用同一 AIMA_HOST_ROOT
→ 启动 / health / smoke
```

PostgreSQL、Artifact、日志和 Secret 不随应用版本目录切换。

### Schema 与旧应用不兼容

不能机械执行 `alembic downgrade`。应按该 Migration 的真实兼容策略处理；若没有安全 downgrade，则需要恢复发布前批准并验证的 Backup Set，或使用事先设计的双版本兼容窗口。

代码回滚本身不删除已经写入的业务数据，也不能替代数据补偿方案。

---

## 14. 尚未完成的 Production 强化

当前剩余工作按风险拆分，不重新造第二套 Runtime：

### 企业 Authentication 与正式 Authorization 验收

接入真实企业身份提供方、Claims/Session 生命周期、Principal 映射、撤销/过期、对象级授权和审计身份。

### HTTPS 与浏览器安全

完成 TLS、Cookie/Session（如适用）、CORS/同源、CSRF/重放（按认证方式）、安全响应头、反向代理和敏感对象授权验收。

### 协调 Backup/Restore

实现并演练 PostgreSQL + Artifact 的一致恢复；冻结经业务批准的 RPO/RTO 和 Retention。

### Release 供应链强化

补充 SBOM、独立签名/来源验证、provenance、兼容矩阵及正式验证流程。

### 生产发布/回滚闭环

形成可重复的 preflight → backup → import release → migrate → start → smoke → observation → rollback/recovery 流程。

### 真实生产验收

在目标基础设施完成安全、容量、Soak、进程/容器/宿主重启、Restore Drill、Release/Rollback 和关键业务 Smoke。

这些都是 Active Production Roadmap 的工作，不在本 Operations 文档伪装成已实现命令。

---

## 15. 排障与事实源

遇到部署或 Release 问题，按事实层次定位：

```text
Release identity / Workflow
→ Bundle / Manifest / checksum
→ Compose config
→ bootstrap / migrate / configure
→ service readiness
→ PostgreSQL / Artifact / logs
→ business smoke
```

优先读取：

- [`.github/workflows/release.yml`](../../.github/workflows/release.yml)：Release 构建与发布机器事实；
- [`Dockerfile`](../../Dockerfile)：镜像构建事实；
- [`compose.yaml`](../../compose.yaml)：canonical Runtime；
- [`compose.windows.yaml`](../../compose.windows.yaml)：Windows storage-only override；
- [`env.production.example`](../../env.production.example)：服务器配置 Schema；
- [`scripts/deploy/prepare_host.py`](../../scripts/deploy/prepare_host.py)：Host Root/权限初始化；
- [`backend/src/aima_ugc/bootstrap/worker.py`](../../backend/src/aima_ugc/bootstrap/worker.py)：Worker Registry；
- [`docs/blueprint/05_日志安全部署与运维.md`](../blueprint/05_日志安全部署与运维.md)：长期运行、安全和恢复边界；
- [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)：尚未完成的 Production 门禁。

不要用历史 Stage 编号、旧 PR 日志或单次 CI 结果代替当前代码、Workflow、Manifest 和目标服务器证据。
