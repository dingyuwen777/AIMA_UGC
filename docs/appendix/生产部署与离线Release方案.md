# 生产部署与离线 Release 方案

这篇文档用于后续真正完成 **Stage 11：Production Release**。

它同时记录两类事实：

```text
当前已经实现
→ 可以直接从仓库代码验证

已批准目标 / 待实现
→ 后续必须按 Change 开发，不能现在假装命令已经可用
```

当前结论先写在前面：

> **当前仓库还没有 `Dockerfile`、`compose.yaml`、`compose.production.yaml`、`env.production.example`，所以这篇中的 Docker/Release 部分是已批准的生产目标设计，不是当前可以复制执行的现成脚本。**

生产上线总路线见：

[`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)

当前开发环境操作见：

[`../环境运行与部署.md`](../环境运行与部署.md)

---

# 1. 当前代码已经提供哪些生产进程能力

当前 Python 已有分进程入口：

```text
API
Worker
Scheduler
Migration
```

代码入口：

```text
backend/src/aima_ugc/entrypoints/
backend/src/aima_ugc/bootstrap/
```

前端是 Vue SPA，生产目标仍是构建静态资源后由 Nginx 类前端 Runtime 提供，并与 API 同源代理。

当前业务持久依赖：

```text
PostgreSQL 18
Local ArtifactStore（当前默认）
Secret files
应用日志目录
```

因此 Stage 11 不是重新设计业务代码，而是把这些当前可运行能力**可靠地装进不可变 Release**。

---

# 2. 生产服务拓扑

已批准目标：

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

它不是常驻服务，也不应由每个 API/Worker 实例启动时自动执行。

### `postgres`

唯一业务事实库。

---

# 3. 生产宿主机目录

原批准目录设计继续保留：

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

不要把 PostgreSQL、Artifact、日志全部塞进 `/data/docker`。

---

# 4. 容器内目标路径

原设计目标：

```text
/app/data
/app/logs
/run/secrets
/var/lib/postgresql
```

真正实现 Stage 11 时必须以**选定镜像当时的实际约定**再验证，尤其 PostgreSQL 18 镜像卷目录和默认 `PGDATA`，不能只从历史文档复制旧主版本路径。

生产 bind mount 必须：

- 预先创建宿主目录；
- 校验 UID/GID；
- 不用 `chmod 777`；
- 不依赖 Docker 自动创建归属不明的目录；
- App 使用非 root 用户运行。

---

# 5. Secret 目标装配

当前应用已经采用 Secret 文件边界；Stage 11 需要把它接到容器：

```text
宿主机 /data/AIMA_UGC/shared/secrets/<name>
→ read-only mount / Docker Secret
→ /run/secrets/<name>
→ PlatformSettings / Secret resolver
```

业务配置表只保存：

```text
secret_ref
```

不得保存真实 Secret 值。

生产 Secret 至少包括按当前 Settings 实际需要的：

- PostgreSQL password；
- TikHub/API Provider Secret；
- LLM API Key；
- Cursor signing keys；
- 未来认证相关 Secret。

Secret resolver 必须继续防止：

- root escape；
- symlink；
- 非普通文件；
- 超限；
- 错误信息回显 Secret。

---

# 6. Dockerfile 需要怎样实现

当前不存在 Dockerfile，Stage 11A 实现时遵守：

```text
仓库根 = 唯一 build context
```

目标使用多阶段构建。

## Backend Runtime

应该：

- 按 `uv.lock` 安装锁定依赖；
- 安装项目 package；
- 不包含无关开发缓存；
- 生产运行不再联网 `pip install`；
- 非 root；
- 同一 image 支持 API/Worker/Scheduler/Migration 不同 command；
- 镜像构建时不写入 Secret。

## Frontend Runtime

应该：

```text
Node build stage
→ npm ci
→ npm run build
→ 只把 dist 复制到 Nginx runtime
```

生产 Nginx 不需要 node_modules。

## 镜像事实

普通代码只引用版本声明；正式 Release Manifest 记录实际 image digest。

禁止：

```text
latest
```

作为不可追溯生产事实。

---

# 7. Compose 需要表达什么

建议职责拆分：

```text
compose.yaml
→ 服务拓扑、内部网络、通用 health/dependency

compose.production.yaml
→ 生产 bind mount、restart、资源/日志、安全覆盖

env.production.example
→ 非 Secret 配置模板
```

生产 Compose 要明确：

- `frontend` 暴露唯一业务 HTTP(S) 入口；
- PostgreSQL 不对公网发布端口；
- `api/worker/scheduler` 访问同一 PostgreSQL/Artifact/Secret；
- `migrate` 不常驻；
- 持久目录映射；
- health/readiness；
- restart policy；
- production secret mount；
- 不在服务器 build；
- `docker compose up` 使用已经 load 的固定镜像。

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

Nginx 自己产生的 413/502/504 等 `/api/` 错误应尽量保持与 API 错误外形兼容，并保留 `X-Request-ID`，避免前端遇到代理层错误时完全无法关联日志。

---

# 9. 认证是 Stage 11 前置，而不是部署后再补

当前没有正式企业认证闭环。

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

没有后端授权时不能因“内网”或“前端隐藏按钮”宣称可生产上线。

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

目标服务器只做：

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

为了避免一个 PR 同时写 30 个部署脚本，建议：

## Stage 11A：Docker/Compose 基础

```text
Dockerfile
compose.yaml
compose.production.yaml
env.production.example
宿主目录初始化/检查
health
CI linux/amd64 build
本地隔离 Compose smoke
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

如果认证尚未完成，应在 11E 之前完成认证 Change。

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
Platform Settings / entrypoints / storage / logging / health
migrations/
当前 CI workflows
```

然后只实施当前最小 Release 单元。

---

# 22. 当前禁止误写成已完成

在真正提交 Stage 11 代码和验证前，文档/PR 不得说：

```text
“已经支持 Docker Compose 生产部署”
“服务器直接执行 compose 即可”
“已经支持离线 Release”
“数据库和 Artifact 可一致恢复”
“已经有生产回滚闭环”
“生产认证已经完成”
```

当前正确说法是：

> 生产 Release、认证和协调恢复有明确设计，仍属于待实现/待验收阶段。
