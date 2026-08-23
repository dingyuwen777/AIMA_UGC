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

> **当前仓库已经通过 Internal V1-A 实现根 `Dockerfile`、根 `compose.yaml`、`env.production.example`、宿主目录/Secret 准备工具和 Nginx Runtime，并由独立 Compose Golden Path CI 验证空库 Migration、正式进程、持久挂载、只读 Secret、Readiness 与端口边界。它是“仓库级最小可部署环境”，不是完整 Stage 11 Production Release：`compose.production.yaml`、离线 `images.tar`、Manifest、SBOM/签名、协调 Backup/Restore、企业认证/授权与真实生产服务器验收仍待后续正式 Change 完成。**

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

Internal V1-A 已把这些能力装进同一个非 root Backend image；不同服务只使用不同正式 command。前端 Vue SPA 已通过 Frontend build stage 构建静态资源，并由非 root Nginx Runtime 提供，同时同源代理 `/api` 与 `/health`。

当前业务持久依赖：

```text
PostgreSQL 18
Local ArtifactStore（当前默认）
Secret files
应用日志目录
```

因此 Stage 11 不应重新设计业务代码或另造一套运行时，而是在 V1-A 已验证的容器/配置边界上继续完成**不可变、可验证、可恢复的正式 Release**。

---

# 2. 生产服务拓扑

Internal V1-A 已实现并验证：

```text
frontend
api
worker
scheduler
migrate
configure
postgres
```

其中 `configure` 是新环境的一次性非敏感运行配置动作，不是常驻业务服务。长期生产核心服务拓扑仍是：

```text
frontend
api
worker
scheduler
migrate
postgres
```

职责：

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

只负责：

```text
Plan
→ due slot
→ Occurrence
→ Run + Job
```

不直接请求 TikHub。

### `migrate`

一次性发布动作：

```text
alembic upgrade head
```

它不是常驻服务，也不应由每个 API/Worker 实例启动时自动执行。Internal V1-A 已按这个边界运行空库 Migration。

### `postgres`

唯一业务事实库。

---

# 3. 生产宿主机目录

原批准目录设计继续保留，并已成为 Internal V1-A 的实际宿主目录 Contract：

```text
/data/docker
/data/AIMA_UGC/runtime/data
/data/AIMA_UGC/runtime/logs
/data/AIMA_UGC/postgres
/data/AIMA_UGC/backups
/data/AIMA_UGC/releases
/data/AIMA_UGC/shared/env
/data/AIMA_UGC/shared/secrets
```

为什么这样拆：

| 目录 | 用途 | 为什么单独放 |
| --- | --- | --- |
| `/data/docker` | Docker 自身镜像/层/容器元数据 | Docker 清理与业务数据隔离 |
| `/data/AIMA_UGC/postgres` | PostgreSQL 数据 | 不能依赖容器可写层 |
| `/data/AIMA_UGC/runtime/data` | Local ArtifactStore 等业务文件 | 与 Release 解耦，升级不覆盖 |
| `/data/AIMA_UGC/runtime/logs` | API/Worker/Scheduler `.log` | 便于宿主机直接排障和轮转 |
| `/data/AIMA_UGC/backups` | 协调 Backup Set | 不能和在线数据库目录混用 |
| `/data/AIMA_UGC/releases` | 不可变 Release 版本 | 支持切回旧应用版本 |
| `/data/AIMA_UGC/shared/env` | 非 Secret 环境配置 | 多 Release 共享 |
| `/data/AIMA_UGC/shared/secrets` | 只读 Secret 文件 | 不进入 Git/Release 包明文 |

`/data/AIMA_UGC/backups` 与 `/data/AIMA_UGC/releases` 在 V1-A 由宿主准备工具建立边界，但协调 Backup Set 和不可变 Release 内容仍由后续 Stage 实现。

不要把 PostgreSQL、Artifact、日志全部塞进 `/data/docker`。

---

# 4. 容器内目标路径

Internal V1-A 当前实际路径：

```text
/app/data
/app/logs
/run/secrets
/var/lib/postgresql
```

当前锁定 PostgreSQL 为 `18.4`。PostgreSQL 18 官方镜像使用 `/var/lib/postgresql` 作为持久卷挂载点，默认数据库目录位于其下 `18/docker`；因此当前 Compose 把宿主 `/data/AIMA_UGC/postgres` bind mount 到 `/var/lib/postgresql`，而不是复制 17 及以前常见的 `/var/lib/postgresql/data` 约定。

后续真正完成 Stage 11 时仍必须重新验证当时锁定镜像的实际约定，不能把今天的路径无条件套到未来升级版本。

Internal V1-A 已通过 `scripts/deploy/prepare_host.py` 执行/校验：

- 预先创建宿主目录；
- 固定 App/PostgreSQL/Secret group UID/GID；
- 不用 `chmod 777`；
- 不依赖 Docker 自动创建归属不明的业务目录；
- App 与 Frontend 使用非 root 用户运行。

---

# 5. Secret 装配

当前应用已经采用 Secret 文件边界，Internal V1-A 已把它实际接到容器：

```text
宿主机 /data/AIMA_UGC/shared/secrets/<name>
→ read-only bind mount
→ /run/secrets/<name>
→ PlatformSettings / Secret resolver
```

Backend Runtime 通过固定 supplementary group 只读访问 Secret；Secret 目录本身在容器内不可写。PostgreSQL 密码同样通过只读 password file 装配，不复制到应用环境变量。

业务配置表只保存：

```text
secret_ref
```

不得保存真实 Secret 值。Internal V1-A 的隔离 Compose Smoke 已验证 TikHub Provider Config 只保存 `secret_ref=tikhub_api_key`，测试 Secret 原值没有进入 Provider Config 行。

生产 Secret 至少包括按当前 Settings 实际需要的：

- PostgreSQL password；
- TikHub/API Provider Secret；
- LLM API Key；
- Cursor signing keys；
- 未来认证相关 Secret。

当前宿主准备工具只会在缺失时生成 PostgreSQL password 与三个 Cursor signing key；TikHub/LLM 外部凭据必须由管理员显式写入 Secret 目录，不生成、不猜测、不提交。

Secret resolver 必须继续防止：

- root escape；
- symlink；
- 非普通文件；
- 超限；
- 错误信息回显 Secret。

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
- 使用非 root UID `10001`；
- 同一 image 支持 API/Worker/Scheduler/Migration/Configure 不同 command；
- 镜像构建时不写入 Secret。

## Frontend Runtime

已经按以下路径实现：

```text
Node build stage
→ npm ci
→ npm run build
→ 只把 dist 复制到 Nginx runtime
```

生产 Nginx 不包含 `node_modules`，并以非 root 用户运行。

## 镜像事实

V1-A 保持仓库现有锁定版本，不因为实现部署而升级 Python/Node/PostgreSQL/uv。当前 Compose CI 真实构建这些镜像，但 V1-A 仍是 build-from-repository 的最小部署环境。

完整 Stage 11 Release 还必须把最终实际 image digest 写入 Release Manifest，并建立来源/完整性验证；普通代码只保留版本声明。

禁止：

```text
latest
```

作为不可追溯生产事实。

---

# 7. Compose 当前实现与 Stage 11 目标

Internal V1-A 当前只维护一个根 `compose.yaml`，避免在尚无完整 Release Manifest/离线镜像语义时提前制造两套易漂移配置。它已经表达：

- `frontend` 是唯一发布宿主端口的业务入口；
- 默认只绑定 `127.0.0.1:8080`；
- PostgreSQL 没有宿主 published port；
- API 没有宿主 published port；
- `api/worker/scheduler/migrate/configure` 复用同一个 Backend image 和同一组 Runtime facts；
- `migrate`、`configure` 是 tools profile 的一次性动作；
- PostgreSQL、Artifact、日志、Secret 按正式宿主目录映射；
- PostgreSQL 与 API 有真实 health/readiness；
- 常驻服务使用 restart policy；
- Secret 只读挂载。

当前非敏感服务器模板为：

```text
env.production.example
```

真实有效配置建议保存到 `/data/AIMA_UGC/shared/env/aima.env`，不读取 `env.local`，也不写入 Git。

Stage 11 若需要独立生产覆盖，可在正式 Release Change 中增加：

```text
compose.production.yaml
→ 不可变镜像、资源/安全、正式网络/发布覆盖
```

但必须有独立语义和验证，不能只是复制一份根 Compose。

完整 Stage 11 还必须实现：

- 服务器不 build；
- `docker compose up` 只使用已验证、已 load 的固定镜像；
- image digest / Release Manifest；
- 生产 HTTPS/认证/授权；
- 完整 offline/no-pull smoke。

---

# 8. 网络和浏览器安全边界

生产目标继续保留：

- HTTPS；
- 明确允许 Host；
- 前后端默认同源；
- CORS 只允许真实来源；
- 带凭据时不能 `*`；
- HSTS；
- `X-Content-Type-Options`；
- Referrer Policy；
- Content Security Policy；
- Provider 出站 Origin Allowlist；
- 用户输入 URL 不能直接触发服务器任意请求；
- 出站校验覆盖 DNS 解析和 redirect；
- PostgreSQL 默认不暴露公网；
- 备份/管理入口只允许受控主机/网络。

Internal V1-A 只完成最小公司内网部署所需的端口边界与同源 Nginx 代理，不把上述完整 Production Browser Security 目标伪装为已实现。

Nginx 自己产生的 413/502/504 等 `/api/` 错误应尽量保持与 API 错误外形兼容，并保留 `X-Request-ID`，避免前端遇到代理层错误时完全无法关联日志。这仍属于后续 Production hardening，不是 V1-A 已完成项。

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

角色名称还需要业务决策；早期：

```text
admin / operator / analyst / viewer
```

只属于候选，不是当前正式 Contract。

真正实现时需要：

- 身份 Provider 选择；
- 登录协议；
- Session/OIDC/飞书等真实交互；
- 后端 Permission；
- 对象级授权；
- Raw/Export/Provider Config 等敏感权限；
- Session/Cookie/CSRF/nonce/state/PKCE 等与实际协议匹配的安全测试。

没有后端授权时不能因“内网”或“前端隐藏按钮”宣称完整生产上线。

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

## `release-manifest.json`

至少记录：

- Release 版本；
- Git SHA；
- 构建时间；
- target platform；
- image digest；
- Alembic head；
- Canonical/OpenAPI 版本或 hash；
- 最低 Docker/Compose 版本；
- 是否有不兼容 Migration；
- rollback 说明；
- SBOM/扫描/签名信息。

## `migration-manifest.json`

至少让运维知道：

```text
from revision
→ to revision
→ 是否 forward-compatible
→ 是否允许仅切回旧应用
→ 是否需要 Backup Restore
```

---

# 11. 为什么不能只校验 SHA256

`SHA256SUMS` 证明：

```text
文件和清单是否一致
```

但如果攻击者同时替换：

```text
release + SHA256SUMS
```

SHA 本身不能证明来源。

所以生产目标需要：

```text
独立受信签名
或
有身份/完整性证明的 Artifact Registry
```

服务器部署前同时验证来源和内容完整性。

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

禁止：

- `git pull`；
- `npm install`；
- `pip install`；
- Playwright/browser 在线下载；
- 现场 build 一个与 CI 不同的镜像；
- 临时编辑容器内部文件当生产修复。

Internal V1-A 的仓库级部署说明允许在受控验收环境从当前仓库 build 镜像，只用于建立/验证最小部署基础；它不改变上述完整 Production Release 原则。

---

# 13. Release 目录

目标：

```text
/data/AIMA_UGC/releases/
├─ v1.0.0/
├─ v1.0.1/
└─ current -> v1.0.1
```

版本目录只放不可变 Release。

下面内容不能放版本目录：

```text
shared/env
shared/secrets
runtime/data
runtime/logs
postgres
backups
```

否则切换版本会覆盖持久事实。

---

# 14. 发布前为什么必须协调 PostgreSQL 和 Artifact

业务来源链中存在：

```text
content_versions.raw_artifact_id
→ artifacts metadata
→ ArtifactStore bytes
```

如果只备份 PostgreSQL：

```text
metadata 在
bytes 不在
```

如果只备份文件：

```text
bytes 在
业务关系/Job/Content 不在
```

因此目标恢复单位是：

```text
Backup Set
= PostgreSQL + ArtifactStore
```

并且需要证明两者对应同一个业务截止点。

---

# 15. 协调 Backup/Restore 目标机制

原设计的核心机制仍保留为待实现目标：

```text
正常业务写
→ 取得共享 write lock
→ 复核 maintenance epoch
→ 写 PostgreSQL / Artifact 关联
→ commit / rename 完成后释放

备份
→ 进入 maintenance
→ 停止新 Job/Scheduler 写入
→ 取得同一键独占 lock
→ 等所有既有共享 writer 退出
→ 冻结新写
→ pg_dump + Artifact snapshot/manifest
→ 验证
→ 标记 Backup Set 可恢复
→ 释放 lock
```

具体 PostgreSQL advisory lock key、表、状态机和脚本当前尚未实现，进入 Stage 11C 必须用正式 Change 设计并测试。

不能只给两个独立备份文件同一个名字就称作“协调一致”。

---

# 16. 发布顺序

目标完整顺序：

```text
确认目标 SHA / 最新 CI 全绿
→ 获取 Release Bundle
→ 验证签名/来源
→ sha256 校验
→ 检查 Manifest / Migration
→ 检查磁盘、目录、UID/GID、Secret
→ 暂停 Scheduler
→ 进入维护模式，拒绝业务写
→ 停止新 Job claim
→ 等待或受控取消运行中 Job
→ 获取统一独占写屏障
→ 创建协调 PostgreSQL + Artifact Backup Set
→ 验证 Backup Set
→ docker load
→ migrate
→ compose config
→ 启动 PostgreSQL（如果本次需要）
→ 启动 API
→ 启动 Worker/Scheduler
→ 启动 Frontend
→ health/live + ready
→ 关键业务 smoke
→ 恢复 Job claim / Scheduler
→ 持续观察日志、磁盘、失败 Job
```

任何 Backup/Migration 校验失败：

```text
停止继续发布
→ 保持维护态
→ 先确认数据/旧 Release/恢复方案
```

不能“先把新服务起来再说”。

---

# 17. 关键业务 Smoke

生产 Release 至少验证：

### 基础

```text
/health/live
/health/ready
Frontend 首页
数据库连接
Artifact 写/读
日志写入
```

### 业务

在受控测试数据/Provider 范围执行：

```text
Excel Import
→ Content 查询
→ Analysis
→ Excel Export
```

以及受控：

```text
一次 Collection Run
→ Raw
→ Mapper
→ Content
```

真实付费 Provider/LLM smoke 需要显式成本范围，不能普通部署脚本无限调用。

### 恢复

```text
restart api
restart worker
restart scheduler
```

不能造成 Job 重复副作用或 Scheduler 重复 Occurrence。

最终 Stage 11 验收还要做宿主机 reboot。

---

# 18. 回滚

## 18.1 Schema 向后兼容

如果 Migration 不破坏旧应用：

```text
切 current Release
→ 启动旧 image
→ smoke
```

## 18.2 Schema 与旧应用不兼容

不能机械：

```text
alembic downgrade
```

正确方案是：

```text
恢复发布前已验证 Backup Set
或
使用在 Migration 设计时明确的双版本兼容窗口
```

必须说明从 Backup 截止点到回滚时刻可能损失的数据。

## 18.3 回滚验证

- API；
- Worker；
- Scheduler；
- Frontend；
- Content/Comment；
- 一个受控 Collection；
- 日志；
- Artifact 下载；
- 认证/授权。

---

# 19. Backup 策略

具体频率必须等 Stage 0 的 RPO/RTO 批准后冻结。

长期要求：

```text
周期性协调 Backup Set
+ 发布前 Backup Set
+ 定期完整恢复演练
+ 每日检查 Backup 结果
+ 磁盘容量告警
```

原方案提出过 70% WARNING / 85% ERROR 等候选阈值；这些数字可以作为实现参考，但**没有 Stage 0 批准就不是最终生产 Contract**。

Backup “任务成功”不能只看 `pg_dump` 退出码，还要验证：

- PostgreSQL backup 可读/可 restore；
- Artifact manifest/文件完整；
- Backup Set 截止点一致；
- 实际恢复出来的 API/Job/Artifact 可以工作。

---

# 20. Stage 11 应拆成哪些最小开发单元

Internal V1-A 已把 Docker/Compose 的最小运行基础提前实现并验证。Stage 11 不应重复造 Dockerfile/Compose，而应直接复用并加强这套基础。

## Stage 11A：Production Docker/Compose Hardening

基于 V1-A 增量完成：

```text
必要时增加 compose.production.yaml
不可变 image/digest 绑定
生产网络/HTTPS/认证入口
资源/安全覆盖
CI linux/amd64 Release build
no-build/no-pull Compose smoke
```

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

Internal V1-A 已经可以准确描述为：

```text
“仓库已提供 Internal V1-A 最小 Docker Compose 部署栈”
“已在隔离 Linux Runner 验证空库 Migration、正式进程、Readiness、持久挂载和端口边界”
```

但在真正完成后续 Production Change 和验证前，文档/PR 不得说：

```text
“已经完成正式生产部署闭环”
“生产服务器直接拿源码 build 即是正式 Release”
“已经支持完整离线 Release”
“数据库和 Artifact 可一致恢复”
“已经有生产回滚闭环”
“生产认证已经完成”
```

当前正确说法是：

> Internal V1-A 的最小容器部署基础已经实现并验证；完整 Production Release、认证和协调恢复仍属于后续待实现/待验收阶段。
