---
schema: rvc-change/v1
id: CHG-20260823-internal-v1a
title: 建立 Internal V1-A 最小可部署环境
level: L3
status: ready_for_review
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
  - .gitignore
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

- [x] 仓库根目录提供唯一 Docker build context，并由一个多阶段 `Dockerfile` 产出 Backend Runtime 与 Frontend/Nginx Runtime。
- [x] `compose.yaml` 至少包含 `frontend`、`api`、`worker`、`scheduler`、`migrate`、`postgres`，API/Worker/Scheduler/Migration 复用同一个 Backend image、使用不同正式命令；另提供一次性 `configure` tools profile。
- [x] Frontend 只提供编译后的 Vue 静态资源，并同源反向代理 `/api` 与 `/health` 到 API；只有 Frontend 发布宿主 HTTP 端口。
- [x] PostgreSQL 18.4 使用 PostgreSQL 18 正式持久卷路径，数据落到宿主持久目录；PostgreSQL 不发布宿主端口。
- [x] Local ArtifactStore 与 `.log` 分别落到宿主持久目录；业务事实不依赖容器可写层保存。
- [x] Secret 目录只读挂载到 `/run/secrets`；PostgreSQL、Cursor、TikHub、LLM 继续复用现有 Secret File/`secret_ref` 边界。
- [x] 正式服务器配置模板只包含非敏感配置和宿主路径；生产运行不读取本地 `env.local`；真实 `env.production` 已加入 Git ignore。
- [x] 宿主准备工具建立/校验 `/data/AIMA_UGC` 目录、必要权限及基础 Secret，不使用 `chmod 777`，不覆盖既有 Secret，并拒绝相对/符号链接宿主根目录。
- [x] 空 PostgreSQL 目录能够通过正式 `migrate` 一次性动作升级到 Alembic head。
- [x] 新环境 TikHub Provider Config 可通过正式一次性配置入口幂等 create/update/disable，数据库只保存 `secret_ref`；不依赖手工 SQL。
- [x] `/health/ready` 在容器中真实检查 PostgreSQL、ArtifactStore、日志目录；Compose Smoke 通过 Frontend 同源入口获得 ready。
- [x] 隔离 Compose Smoke 证明 build、空库 migration、正式进程启动、Frontend→API 接线、PostgreSQL/Artifact/log 持久目录和 Secret 只读挂载成立，并确认 PostgreSQL/API 没有宿主 PortBindings。
- [x] 现有 HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Job/Collection/Analysis/Reporting 业务语义保持不变。
- [x] Internal V1 Roadmap 更新为 V1-A 已闭环、下一单元为 Internal V1-B；完整离线 Release、认证、协调 Backup/Restore 继续留在后续正式阶段。

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
- 已批准的 Internal V1 范围继续显式延期完整认证、离线 Release 与协调 Backup/Restore，不因旧 Production Appendix 的长期目标而提前扩展本 Change。

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
- TikHub 是否启用由非敏感部署配置显式决定；启用但 Secret 不存在时配置动作 fail closed；LLM 半配置或缺 Secret 同样 fail closed。

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
| R1 | Internal V1-A 是当前下一最小正式单元，并建立 Dockerfile/Compose/服务器配置模板/宿主目录检查/Healthcheck/隔离 Smoke | docs/roadmap/生产上线实施路线.md | satisfied | `Dockerfile`、`compose.yaml`、`env.production.example`、`scripts/deploy/prepare_host.py`、`.github/workflows/internal-v1a.yml`；Internal V1-A Run #16 (`32622016122`) success |
| R2 | Compose 至少包含 frontend/api/worker/scheduler/migrate/postgres，Migration 为一次性发布动作 | docs/roadmap/内网V1上线实施计划.md | satisfied | `compose.yaml` 包含六个要求服务并新增一次性 `configure`；`migrate/configure` 仅在 `tools` profile；Run #16 真实执行 `run --rm migrate/configure` success |
| R3 | 根目录是唯一 build context，Backend/Frontend 多阶段构建，同一 Backend image 支撑 API/Worker/Scheduler/Migration | docs/roadmap/生产上线实施路线.md | satisfied | 根 `Dockerfile`；Compose 所有 build `context: .`；Run #16 `Build pinned runtime images` success，正式进程均成功启动 |
| R4 | PostgreSQL、Artifact、`.log` 持久化，Secret 只读装配，PostgreSQL 不向普通公司网络发布 | docs/roadmap/内网V1上线实施计划.md | satisfied | Run #16 验证 PG 容器删除/重建后 Provider Config 存在、Artifact marker 跨 API recreate 存在、宿主 `api.log` 存在、`/run/secrets` RO、PG/API `PortBindings={}` |
| R5 | 空库 Migration 到 head，Health/Readiness 检查关键本地依赖，API/Worker/Scheduler 使用同一配置事实 | docs/roadmap/内网V1上线实施计划.md | satisfied | Run #16 从空 PostgreSQL 18.4 执行 Alembic `upgrade head`；Nginx `/health/ready` 返回 database/artifact_store/log_directory=`ok`；Compose 共用同一 `x-backend-environment` |
| R6 | 新环境 TikHub/LLM 不读取 `env.local`、不依赖手工 SQL；Provider Config 只保存非敏感配置和 `secret_ref` | docs/roadmap/内网V1上线实施计划.md | satisfied | `internal_v1.py` + configure entrypoint；Run #16 连续 configure、disable、re-enable 均成功且数据库只见 `tikhub_api_key` ref；Unit 覆盖 LLM absent/partial/missing-secret/configured；生产 Compose 不引用 `env.local` |
| R7 | 保留 `/data/AIMA_UGC` 已批准宿主目录模型，PostgreSQL/Artifact/log/Secret 与 Release 解耦 | docs/appendix/生产部署与离线Release方案.md | satisfied | `prepare_host.py` 与 `env.production.example` 固定批准目录；Run #16 验证 bind source/target 与宿主持久事实；相对/符号链接 root 回归测试已加入 |
| R8 | V1-A 不提前实现 Internal V1-B 真实服务器验收、完整离线 Release、认证或协调 Backup/Restore | docs/roadmap/内网V1上线实施计划.md + docs/blueprint/07-技术决策与实施门禁.md | satisfied | 两份 Roadmap 与 Production Appendix 均明确 V1-B 为下一单元、完整 Release/Auth/协调恢复仍待后续；本 PR 未新增相关 Contract/Schema/业务功能 |
| R9 | 合并前执行仓库 L3 Requirement/Completion/Review/CI 门禁，不绕过 PR/CI/Branch Protection | AGENTS.md + .agents/skills/reliable-vibe-coding/SKILL.md | satisfied | Requirement Review 与 Code Quality Review 已执行；最新实现 HEAD `72e54549` 的 CI #2253、Internal V1-A #16、Stage 8F #380、Stage 6 #250、Stage 7/Audit/Local Dev 均 success；本次状态提交交由 Change Completion Gate 再验证后才转 PR Ready/合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本 Change 不改变页面业务行为或用户可见业务状态；Stage 8F #380 作为既有浏览器业务回归仍 success |
| Backend/API/PostgreSQL Integration | required | CI #2253 Stage 2 Platform + Stage 3A Database success；Internal V1-A #16 真实 PostgreSQL 18.4、空库 Migration、Provider Config、Readiness、持久化均 success |
| Contract / Generated Client | not_applicable | 无公共 HTTP Contract/OpenAPI/generated client 变更；CI #2253 `Verify generated contracts and client` success，证明无 drift |
| Real Full-stack Golden Path | required | Internal V1-A #16：Docker build → PostgreSQL → migrate/configure → API/Worker/Scheduler → Nginx Frontend → `/health/ready` → mount/port/persistence assertions 全部 success |
| Real Provider Probe | not_applicable | 本 Change 未修改 TikHub endpoint/字段/分页/Capability；真实付费 Provider/LLM Smoke 正式归属 V1-B，本 Change 没有发起真实 Provider 请求 |
| Docs / Governance / Other | required | CI #2253 Backend/repository checks success；文档/Secret/静态门禁包含在总 CI；Roadmap/部署文档已同步；Change Completion Gate 在本次 `ready_for_review` 状态提交后作为最后治理门禁 |

# Completion Audit

- [x] upstream_re_read：代码稳定后重新读取 `docs/roadmap/生产上线实施路线.md`、`docs/roadmap/内网V1上线实施计划.md`、`docs/blueprint/07-技术决策与实施门禁.md` 与 Production Appendix，独立重建 V1-A 完成定义；没有以本 Change 自身作为需求全集。
- [x] change_coverage：逐项对照 Docker/Compose/Config/宿主目录/Secret/Migration/Provider Config/Readiness/网络/持久化/文档要求，均有实现和新鲜 CI 证据；未发现需修改公共 Contract/Schema 的缺口。
- [x] reverse_audit：从实际 diff 反向审查部署拓扑、配置流、Secret 读取、宿主路径、PortBindings、PostgreSQL 18 初始化/持久化、非 root Runtime 和回滚边界；Validation Matrix 已复核。
- [x] unresolved_cleared：所有 V1-A `not_satisfied` 已清零；真实公司服务器/Provider/LLM/reboot、完整离线 Release、认证和协调 Backup/Restore 均有正式 Roadmap 延期依据，不伪装成已完成。

# 两阶段 Review

## Requirement Review

结论：通过。

- V1-A 的全部上游要求均可追踪到实际实现和永久验证；没有发现缺失的业务 Contract、Schema/Migration 或前端业务能力。
- 范围保持在“仓库级最小可部署环境”；没有静默进入 V1-B、完整 Production Release、认证或 DR。
- Roadmap 已推进到 V1-B，但没有把“公司内网 V1 已上线”或“完整 Production 已完成”写成事实。

## Code Quality Review

结论：通过，审查中发现的问题均已修复并重新验证。

1. PostgreSQL 官方镜像初始化阶段会临时启动 Unix-socket server；原 `pg_isready` 未指定 host，可能把临时 server 误判 ready。修正为 `-h 127.0.0.1`，只接受最终 TCP server，并由后续 Golden Path 验证。
2. `docker compose port` 对仅 `expose` 的服务可能返回 `:0`，不能作为“是否发布宿主端口”的安全事实。验收改读 Docker `HostConfig.PortBindings`，严格要求 PG/API `{}`、Frontend 唯一批准绑定。
3. 宿主准备脚本原先先 `resolve()` 再判断绝对路径，显式相对 `--root` 会被静默接受；同时 broken symlink Secret 的错误路径不够稳定。已增加 `_resolve_host_root()`、显式 symlink 校验和回归测试。
4. 增补 LLM absent/partial/missing-secret/configured 边界，以及 Provider Config 重复执行/disable/re-enable 的幂等 Golden Path，避免只证明首次成功。
5. PR 当前无 review thread、无未解决 review；未发现需要扩大范围的严重/重要问题。

# 任务

- [x] 调查当前实现、AGENTS/Skill、Roadmap、Production Appendix、配置/Secret/Runtime/进程入口与 CI 事实。
- [x] 建立失败测试并取得 Red 证据。
- [x] 实现正式 Internal V1 Provider Config one-shot 与宿主目录/Secret 准备工具。
- [x] 实现根 Dockerfile、Nginx 配置、Compose 与生产 env 模板。
- [x] 建立 Internal V1-A Compose Smoke CI，覆盖空库 Migration、真实进程、readiness、持久挂载和 PostgreSQL/API 非发布端口。
- [x] 同步受影响文档与 Roadmap。
- [x] 运行目标测试、相关 CI、静态检查/构建并记录新鲜证据。
- [x] 执行 Requirement Traceability、Completion Audit 与 L3 两阶段 Review。
- [ ] 本次 `ready_for_review` 状态提交通过 Change Completion Gate 后，将 PR #164 转 Ready；最新 PR HEAD 所有永久 CI 全绿后正常合并 main。
- [ ] 合并后从最新 main 创建独立归档 Change，把本 Active Change 移入 `changes/archive/2026-08/`、标记 `done`，再通过归档 PR/CI 正常合并。

# 验证

## Red 证据

- CI #2236 / Run `32620834668`：`tests/unit/platform/test_internal_v1_deployment.py` 收集阶段因 `ModuleNotFoundError: aima_ugc.bootstrap.internal_v1` 失败；同轮 PostgreSQL 18.4 正常，证明失败来自目标能力尚不存在。

## Green / 回归证据（实现 HEAD `72e54549907c2a174e9f7fae203881d0d97f5643`）

- Internal V1-A Deployable Stack #16 / Run `32622016122`：success。真实执行宿主准备、Compose config、Backend/Frontend build、空库 Migration、configure 幂等/disable/re-enable、PG 重建持久化、四个常驻进程、Nginx readiness、UID/mount/PortBindings、Artifact/日志/PG 宿主事实验证。
- CI #2253 / Run `32622016148`：success。Windows bootstrap、Stage 3A Database、Stage 2 Platform、Stage 1 Backend/repository/Wheel/Frontend 全部 success。
- Stage 8F Full-stack #380 / Run `32622016181`：success。
- Stage 6 Xiaohongshu Vertical Slice #250 / Run `32622016110`：success。
- Stage 7 Provider Config #1975、Keyword Packs #1862、Scheduler Runtime #2202、Plan Snapshot #1860：success。
- Stage 1-7 Audit Correctness #1077：success。
- Local Dev Bootstrap #76：success。
- Change Completion Gate #99 在上一 HEAD 唯一失败原因是 Active Change 仍为 `in_progress`；其 RVC governance unit tests 14/14 success。该预期失败由本次状态提交消除，必须等待新 run success 后才转 PR Ready。

# 文档影响

- `docs/环境运行与部署.md`：加入 V1-A 实际服务器最小部署顺序、生产 Secret/Config 边界，并明确仍不是完整 Production Release。
- `docs/appendix/生产部署与离线Release方案.md`：把 Docker/Compose 基础更新为 V1-A 已实现事实；Stage 11 改为直接复用/加强该基础，不重复造部署栈；完整离线 Release/Auth/Backup Restore 继续待实现。
- `docs/roadmap/内网V1上线实施计划.md`：V1-A 标为已完成，Internal V1-B 成为下一最小正式开发单元。
- `docs/roadmap/生产上线实施路线.md`：同步相同阶段状态和完成证据，同时保持完整 Production No-Go。

# 兼容、依赖、迁移与回滚

- 公共 HTTP API、OpenAPI/generated client、Canonical、数据库 Schema/Migration、Job/Collection/Analysis/Reporting 语义：无变更。
- Python/uv/Node/npm/PostgreSQL 版本：保持仓库锁定版本，无升级/降级；新增 Nginx Runtime 仅用于 Frontend 静态服务/反代。
- 数据迁移：无新 Migration；V1-A 只把现有 `alembic upgrade head` 装成显式 one-shot。
- 应用回滚：本 Change 不改变 Schema，可切回前一可用应用镜像/Compose；PostgreSQL、Artifact、日志、Secret 与 Release 目录解耦。
- 完整离线 Release rollback、协调数据库+Artifact 恢复仍未实现，继续按后续 Production Change 执行。

# 交付

- Branch：`feature/internal-v1a-deployable-stack`
- PR：#164（当前 Draft；本状态提交通过 Completion Gate 后转 Ready）
- 已验证实现 HEAD：`72e54549907c2a174e9f7fae203881d0d97f5643`
- 发布定义：Internal V1-A 只完成仓库级可部署环境，不等同于 V1-B 公司服务器实际发布验收，也不等同于完整 Production Go-Live。
