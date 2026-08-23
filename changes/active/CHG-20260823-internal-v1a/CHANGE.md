---
schema: rvc-change/v1
id: CHG-20260823-internal-v1a
title: 建立 Internal V1-A 最小可部署环境
level: L3
status: in_progress
owner: chatgpt
branch: feature/internal-v1a-deployable-stack
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - runtime
  - configuration
  - security
  - provider-config
  - ci
affected_paths:
  - Dockerfile
  - .dockerignore
  - compose.yaml
  - env.production.example
  - deploy/
  - scripts/deploy/
  - backend/src/aima_ugc/bootstrap/internal_v1.py
  - backend/src/aima_ugc/entrypoints/internal_v1_configure_main.py
  - tests/unit/platform/test_internal_v1_deployment.py
  - .github/workflows/internal-v1a.yml
  - docs/环境运行与部署.md
  - docs/appendix/生产部署与离线Release方案.md
  - docs/roadmap/内网V1上线实施计划.md
  - docs/roadmap/生产上线实施路线.md
contracts: []
data_changes: []
---

# 目标

把当前已存在的 API、Worker、Scheduler、Migration、PostgreSQL、Local ArtifactStore、日志和 Secret File 能力装配成 Internal V1 的最小可部署容器栈，使一台已安装 Docker/Compose 的 Linux 主机可以在不读取 `env.local`、不把 Secret 写入 Git/数据库、也不依赖手工 SQL 的前提下启动真实 AIMA_UGC 运行时。

# 成功标准

- [ ] 仓库根目录提供唯一 Docker build context，并由一个多阶段 `Dockerfile` 产出 Backend Runtime 与 Frontend/Nginx Runtime。
- [ ] `compose.yaml` 至少包含 `frontend`、`api`、`worker`、`scheduler`、`migrate`、`postgres`，API/Worker/Scheduler/Migration 复用同一个 Backend image、使用不同正式命令。
- [ ] Frontend 只提供编译后的 Vue 静态资源，并同源反向代理 `/api` 与 `/health` 到 API；只有 Frontend 发布宿主 HTTP 端口。
- [ ] PostgreSQL 18.4 使用 PostgreSQL 18 正式持久卷路径，数据落到宿主持久目录；PostgreSQL 不发布宿主端口。
- [ ] Local ArtifactStore 与 `.log` 分别落到宿主持久目录；业务事实不依赖容器可写层保存。
- [ ] Secret 目录只读挂载到 `/run/secrets`；PostgreSQL、Cursor、TikHub、LLM 继续复用现有 Secret File/`secret_ref` 边界。
- [ ] 正式服务器配置模板只包含非敏感配置和宿主路径；生产运行不读取本地 `env.local`。
- [ ] 宿主准备工具建立/校验 `/data/AIMA_UGC` 目录、必要权限及基础 Secret，不使用 `chmod 777`，不覆盖既有 Secret。
- [ ] 空 PostgreSQL 目录能够通过正式 `migrate` 一次性动作升级到 Alembic head。
- [ ] 新环境 TikHub Provider Config 可通过正式一次性配置入口幂等 create/update/disable，数据库只保存 `secret_ref`；不依赖手工 SQL。
- [ ] `/health/ready` 在容器中真实检查 PostgreSQL、ArtifactStore、日志目录；Compose Smoke 通过 Frontend 同源入口获得 ready。
- [ ] 隔离 Compose Smoke 证明 build、空库 migration、正式进程启动、Frontend→API 接线、PostgreSQL/Artifact/log 持久目录和 Secret 只读挂载成立，并确认 PostgreSQL 没有 published port。
- [ ] 现有 HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Job/Collection/Analysis/Reporting 业务语义保持不变。
- [ ] Internal V1 Roadmap 更新为 V1-A 已闭环、下一单元为 Internal V1-B；完整离线 Release、认证、协调 Backup/Restore 继续留在后续正式阶段。

# 范围

- 根 Dockerfile、Docker build ignore、Frontend Nginx runtime 配置。
- Internal V1 Compose 拓扑、正式 env 模板、宿主目录与 Secret 准备工具。
- 新环境 TikHub Provider Config 的正式一次性幂等装配；LLM 继续使用现有 `AIMA_LLM_* + /run/secrets/llm_api_key`。
- Internal V1-A 专项 Unit/Compose Smoke CI。
- 与当前真实部署能力相关的运行文档、Production Appendix 与 Roadmap 同步。

# 非目标

- 不实现 Internal V1-B 的真实公司服务器验收、长时间稳定性、重启/整机重启验收或真实 TikHub/LLM 业务 Smoke。
- 不实现完整离线 Release Bundle、`images.tar`、Manifest、SBOM、签名、镜像 Digest 固化或服务器 `docker load` 发布链。
- 不实现企业认证/授权、HTTPS 终止、正式域名、角色权限。
- 不实现 PostgreSQL + Artifact 同时点协调 Backup/Restore、维护写屏障或灾备演练。
- 不新增数据库表、Migration、HTTP API、Generated Client 或前端业务页面。
- 不自动创建 Keyword Pack、Global Relevance、Collection Plan 等业务配置。
- 不把 TikHub/LLM API Key 写入 env 模板、日志、数据库或镜像。

# 必须保持不变

- PostgreSQL 18 继续是唯一业务事实库，Local ArtifactStore 继续通过 `AIMA_DATA_DIR/artifacts` 保存字节。
- API、Worker、Scheduler、Migration 的现有职责和正式 Python 入口不被重写；Migration 仍是显式发布动作，不在 API 启动时隐式执行。
- `PlatformSettings`、`DatabaseRuntime`、Secret resolver、Readiness 继续作为运行时事实源；本 Change 不建立第二套密码/Secret 读取机制。
- Provider Config 继续只存非敏感 `base_url + secret_ref + enabled`；Provider API Key 只存在 Secret File。
- `env.local` 与 `scripts/dev/*` 仍只属于本地源码开发，不成为生产 Contract。
- Pydantic → OpenAPI → Orval generated client、Canonical、Schema/Migration、Job Runtime 和五平台身份语义保持不变。
- 用户已批准的 Internal V1 范围继续显式延期完整认证、离线 Release 与协调 Backup/Restore，不因旧 Production Appendix 的长期目标而提前扩展本 Change。

# 关键决策

## 方案比较

### 方案 A：一个参数化 Compose + 根多阶段 Dockerfile（采用）

根目录是唯一 build context；Dockerfile 提供 `backend`/`frontend` target；一个 `compose.yaml` 通过 `--env-file` 注入宿主目录和非敏感配置。优点是机制最少，直接覆盖 V1-A，CI 与服务器使用同一 Compose 语义；后续完整 Release 可以在此基础上增加不可变镜像/Manifest。缺点是当前还不是最终离线 Release 形态。

### 方案 B：立即拆 `compose.yaml + compose.production.yaml + release compose`

优点是可提前表达生产覆盖；缺点是 V1-A 尚未建立 Release Manifest/image digest/离线 bundle，过早拆多套 Compose 会制造尚无独立语义的配置漂移。延期到完整 Production Release Change。

### 方案 C：Docker named volume + 环境变量 Secret

优点是开发方便；缺点是无法满足已批准的 `/data/AIMA_UGC/*` 可维护宿主目录和只读 Secret File 边界，也不利于后续备份/迁移。拒绝。

## 镜像与 PostgreSQL 18 路径

- 保持仓库锁定版本：Python `3.14.7`、Node `24.19.0`、PostgreSQL `18.4`，不因当前上游已有新 patch 版本而升级。
- Frontend Runtime 采用已核验的 Docker Official Image `nginx:1.30.4-alpine3.24`，用于静态资源与同源反代；这是 V1-A 已批准 Nginx 类 Runtime 的最小实现。
- PostgreSQL 18 官方镜像从 18 起定义 `PGDATA=/var/lib/postgresql/18/docker`，并把持久卷挂载点改为 `/var/lib/postgresql`；Compose 按该 18+ 规则挂载宿主 PostgreSQL 目录。

## 配置与 Secret

- Compose 只把运行时路径固定到容器内 `/app/data`、`/app/logs`、`/run/secrets`，数据库 Host 固定到 Compose service `postgres`；其余非敏感配置从 `env.production` 类文件注入。
- Secret 目录整体只读挂载；应用继续按既有文件名读取 `postgres_password`、三个 Cursor key、`llm_api_key`，TikHub Provider Config 使用 `secret_ref` 指向同一目录下文件。
- 宿主准备工具只生成数据库密码和 Cursor signing key 等系统基础 Secret；TikHub/LLM 外部凭据必须由管理员显式放入 Secret 目录，不生成、不猜测、不提交。
- TikHub 是否启用由非敏感部署配置显式决定；启用但 Secret 不存在时配置动作 fail closed，避免产生表面 enabled、实际不可执行的 Provider Config。

## Migration、部署与回滚

- 部署顺序：prepare host → build/load image（V1-A CI 直接 build）→ start PostgreSQL → run `migrate` one-shot → run Internal V1 config one-shot → start API/Worker/Scheduler/Frontend → readiness/smoke。
- V1-A 不把 `migrate` 变成常驻服务，也不让 API 自动迁移。
- 回滚应用：停止当前应用容器并切回前一个可用 image/Compose；本 Change 不修改 Schema，因此应用回滚不需要数据库反向 Migration。
- PostgreSQL/Artifact/log/Secret 都位于版本目录之外的宿主路径，容器重建不删除这些事实。

## 安全与运维风险

- 只有 Frontend 发布 HTTP 端口；PostgreSQL、API、Worker、Scheduler 都只在 Compose 网络内可见。
- Backend 与 Frontend Runtime 使用非 root 用户；宿主准备脚本为固定容器 UID/GID 建立最小权限，不使用 world-writable。
- V1-A 仍不是完整 Production Security 闭环：HTTPS、企业认证、Release 签名/SBOM、协调 Backup/Restore 按 Roadmap 后续完成，不在本 Change 中伪装为已完成。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Internal V1-A 是当前下一最小正式单元，并建立 Dockerfile/Compose/服务器配置模板/宿主目录检查/Healthcheck/隔离 Smoke | docs/roadmap/生产上线实施路线.md | not_satisfied | 开发中 |
| R2 | Compose 至少包含 frontend/api/worker/scheduler/migrate/postgres，Migration 为一次性发布动作 | docs/roadmap/内网V1上线实施计划.md | not_satisfied | 开发中 |
| R3 | 根目录是唯一 build context，Backend/Frontend 多阶段构建，同一 Backend image 支撑 API/Worker/Scheduler/Migration | docs/roadmap/生产上线实施路线.md | not_satisfied | 开发中 |
| R4 | PostgreSQL、Artifact、`.log` 持久化，Secret 只读装配，PostgreSQL 不向普通公司网络发布 | docs/roadmap/内网V1上线实施计划.md | not_satisfied | 开发中 |
| R5 | 空库 Migration 到 head，Health/Readiness 检查关键本地依赖，API/Worker/Scheduler 使用同一配置事实 | docs/roadmap/内网V1上线实施计划.md | not_satisfied | 开发中 |
| R6 | 新环境 TikHub/LLM 不读取 `env.local`、不依赖手工 SQL；Provider Config 只保存非敏感配置和 `secret_ref` | docs/roadmap/内网V1上线实施计划.md | not_satisfied | 开发中 |
| R7 | 保留 `/data/AIMA_UGC` 已批准宿主目录模型，PostgreSQL/Artifact/log/Secret 与 Release 解耦 | docs/appendix/生产部署与离线Release方案.md | not_satisfied | 开发中 |
| R8 | V1-A 不提前实现 Internal V1-B 真实服务器验收、完整离线 Release、认证或协调 Backup/Restore | user:internal-v1a-implementation + docs/roadmap/内网V1上线实施计划.md | not_satisfied | 开发中；范围已锁定 |
| R9 | 完成后执行仓库 L3 Requirement/Completion/Review/CI 门禁并正常合并 main | user:internal-v1a-implementation + AGENTS.md | not_satisfied | 开发中 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本 Change 不改变页面业务行为或用户可见状态，部署接线由真实 Compose Golden Path 验证 |
| Backend/API/PostgreSQL Integration | required | 新环境 Provider Config one-shot、真实 PostgreSQL 18.4、Migration、Readiness 与持久目录边界 |
| Contract / Generated Client | not_applicable | 不新增/修改公共 HTTP Contract、OpenAPI 或 generated client；主 CI drift check 作为回归证据但不是独立新语义 |
| Real Full-stack Golden Path | required | Docker Compose build → PostgreSQL → migrate/configure → API/Worker/Scheduler → Nginx Frontend → `/health/ready`，并验证持久挂载/网络边界 |
| Real Provider Probe | not_applicable | 不修改 TikHub endpoint/字段/分页/Capability；V1-B 才执行有界真实 Provider Smoke，本 Change 不产生付费请求 |
| Docs / Governance / Other | required | Docker/Compose 静态校验、Secret scan、宿主准备工具测试、Roadmap/部署文档同步、Ready Check 与两阶段 Review |

# Completion Audit

- [ ] upstream_re_read：已重新读取全部上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行部署拓扑/配置/持久化/Secret/网络的反向边界审计并复核 Validation Matrix。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [x] 调查当前实现、AGENTS/Skill、Roadmap、Production Appendix、配置/Secret/Runtime/进程入口与 CI 事实。
- [ ] 建立失败测试并取得 Red 证据。
- [ ] 实现正式 Internal V1 Provider Config one-shot 与宿主目录/Secret 准备工具。
- [ ] 实现根 Dockerfile、Nginx 配置、Compose 与生产 env 模板。
- [ ] 建立 Internal V1-A Compose Smoke CI，覆盖空库 Migration、真实进程、readiness、持久挂载和 PostgreSQL 非发布端口。
- [ ] 同步受影响文档与 Roadmap。
- [ ] 运行目标测试、相关 CI、静态检查/构建并记录新鲜证据。
- [ ] 执行 Requirement Traceability、Completion Audit、L3 两阶段 Review 与 Ready Check。
- [ ] PR Ready、最新 HEAD 永久 CI 全绿后正常合并 main，并在独立归档 Change 中归档本 Change。

# 验证

## 计划

- Red/Unit：`uv run pytest tests/unit/platform/test_internal_v1_deployment.py -q`
- Repository：`uv run ruff format --check backend tests scripts && uv run ruff check backend tests scripts && uv run mypy backend/src`
- Backend：`uv run pytest tests/unit -q && uv run pytest tests/contracts -q && uv run pytest tests/api -q`
- Frontend：`npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run test -- --run && npm --prefix frontend run build`
- Compose static：`docker compose --env-file <isolated-env> config`
- Compose Golden Path：`.github/workflows/internal-v1a.yml`
- Governance：`uv run python scripts/quality/scan_secrets.py && uv run python scripts/quality/check_docs.py`
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- 尚未执行实现后的验证。

# 文档影响

- `docs/环境运行与部署.md`：新增 Internal V1-A 服务器最小部署入口，同时保留本地 dev 与生产边界。
- `docs/appendix/生产部署与离线Release方案.md`：把 Docker/Compose 部分从“待实现”更新为 V1-A 已实现事实，并继续区分完整离线 Release/认证/Backup Restore 未完成。
- `docs/roadmap/内网V1上线实施计划.md`、`docs/roadmap/生产上线实施路线.md`：完成后只推进 V1-A 状态，下一单元为 V1-B，不提前勾选后续 Stage。

# 交付

- Commit：开发中
- PR：开发中
- 发布：Internal V1-A 只完成仓库可部署环境，不等同于 V1-B 公司服务器实际发布验收
