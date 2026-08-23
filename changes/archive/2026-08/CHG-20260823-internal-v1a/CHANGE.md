---
schema: rvc-change/v1
id: CHG-20260823-internal-v1a
title: 建立 Internal V1-A 最小可部署环境
level: L3
status: done
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
  - AGENTS.md
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

把现有 API、Worker、Scheduler、Migration、PostgreSQL、Local ArtifactStore、日志和 Secret File 能力装配成 Internal V1 的最小可部署容器栈，使已安装 Docker/Compose 的 Linux 主机可以在不读取 `env.local`、不把 Secret 写入 Git/数据库、也不依赖手工 SQL 的前提下启动真实 AIMA_UGC Runtime。

# 成功标准

- [x] 根目录是唯一 Docker build context；一个多阶段 `Dockerfile` 产出 Backend 与 Frontend/Nginx Runtime。
- [x] `compose.yaml` 包含 `frontend/api/worker/scheduler/migrate/postgres`，并增加一次性 `configure`；Backend 进程复用同一 image、使用不同正式命令。
- [x] Frontend 只服务 Vue production build，并同源反代 `/api`、`/health`；只有 Frontend 发布宿主 HTTP 端口。
- [x] PostgreSQL 18.4 使用 PostgreSQL 18 的 `/var/lib/postgresql` 持久卷边界；PostgreSQL 不发布宿主端口。
- [x] PostgreSQL、Local ArtifactStore、`.log` 分别落到宿主持久目录；业务事实不依赖容器可写层。
- [x] Secret 只读挂载到 `/run/secrets`；PostgreSQL、Cursor、TikHub、LLM 继续复用既有 Secret File / `secret_ref` 边界。
- [x] `env.production.example` 只包含非敏感配置；生产 Compose 不读取本地 `env.local`；真实 `env.production` 被 Git ignore。
- [x] `prepare_host.py` 建立/校验 `/data/AIMA_UGC` 目录、UID/GID、最小权限和基础 Secret，不使用 `chmod 777`，不覆盖已有 Secret，并拒绝相对/符号链接宿主根目录。
- [x] 空 PostgreSQL 能通过显式 `migrate` one-shot 升级到 Alembic head。
- [x] TikHub Provider Config 可通过正式 one-shot 幂等 create/update/disable，数据库只保存 `secret_ref`；LLM 半配置/缺 Secret fail closed。
- [x] `/health/ready` 在容器中真实检查 PostgreSQL、ArtifactStore、日志目录；Frontend 同源入口可读到 ready。
- [x] 隔离 Compose Golden Path 真实证明 build、Migration、正式进程、持久化、RO Secret、非 root Runtime 与 PortBindings。
- [x] HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Job/Collection/Analysis/Reporting 业务语义保持不变。
- [x] Roadmap 推进到 Internal V1-B；完整离线 Release、认证、协调 Backup/Restore 继续延期。
- [x] 根 `AGENTS.md` 已同步为 V1-A 已存在 Dockerfile/Compose 的当前事实，不再保留相反的旧基线说明。

# 范围与非目标

本 Change 只实现 Dockerfile/Compose/Nginx、生产非敏感配置、宿主目录与 Secret 准备、Provider Config one-shot、V1-A Unit/Compose CI 及受影响文档。

明确不实现：Internal V1-B 真实公司服务器/浏览器/Provider/LLM/reboot 验收；完整离线 Release Bundle、Manifest/SBOM/签名/Digest；企业认证授权/HTTPS；PostgreSQL+Artifact 协调 Backup/Restore；新业务 Contract/Schema/页面；自动创建 Keyword Pack/Relevance/Collection Plan；任何真实 TikHub/LLM Key 入库、入镜像或入 Git。

# 必须保持不变

- PostgreSQL 18 仍是唯一业务事实库；Local ArtifactStore 仍由 `AIMA_DATA_DIR/artifacts` 保存字节。
- API/Worker/Scheduler/Migration 现有职责不重写；Migration 仍是显式发布动作。
- `PlatformSettings`、`DatabaseRuntime`、Secret resolver、Readiness 是唯一 Runtime 事实源。
- Provider Config 只保存 `base_url + secret_ref + enabled`；真实 Key 只存在 Secret File。
- `env.local` 与 `scripts/dev/*` 仍只属于源码开发。
- Pydantic → OpenAPI → Orval、Canonical、Schema/Migration、Job Runtime 与五平台身份语义不变。

# 关键决策

采用“一个参数化根 Compose + 一个根多阶段 Dockerfile”。当前没有 Release Manifest/image digest/离线 bundle，因此不提前复制 `compose.production.yaml`；Stage 11 再基于 V1-A 增量 hardening。

保持仓库锁定版本 Python `3.14.7`、uv `0.12.3`、Node `24.19.0`、PostgreSQL `18.4`，不升级依赖。Frontend Runtime 使用核验过的 `nginx:1.30.4-alpine3.24`。PostgreSQL 18 官方镜像持久卷按 `/var/lib/postgresql` 装配，默认 PGDATA 位于其下 `18/docker`。

Secret 目录整体 RO；应用以 supplementary group 读取，PostgreSQL password 也通过只读文件而不是环境变量。宿主准备工具只生成 PostgreSQL password 与三个 Cursor signing key；TikHub/LLM 外部凭据必须由管理员显式提供。

部署顺序固定为：prepare host → build/load image → PostgreSQL → migrate → configure → API/Worker/Scheduler/Frontend → readiness。V1-A 不让 API 隐式 Migration。本 Change 无 Schema 变更，应用层可通过切回旧 image/Compose 回滚；协调数据恢复仍属于后续 Production Change。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 建立 V1-A Dockerfile/Compose/服务器配置/宿主检查/Health/隔离 Smoke | docs/roadmap/02_生产上线实施路线.md | satisfied | `Dockerfile`、`compose.yaml`、`env.production.example`、`prepare_host.py`、`internal-v1a.yml`；最终 V1-A PR Run `32623566835` success |
| R2 | Compose 至少包含 frontend/api/worker/scheduler/migrate/postgres，Migration 为一次性动作 | docs/roadmap/01_内网V1上线实施计划.md | satisfied | `compose.yaml` 包含全部要求服务；`migrate/configure` 位于 tools profile；最终 V1-A Run `32623566835` 真实 Golden Path success |
| R3 | 根 build context、多阶段 Backend/Frontend、同一 Backend image 支撑正式进程 | docs/roadmap/02_生产上线实施路线.md | satisfied | 根 `Dockerfile` + Compose `context: .`；最终 V1-A Run `32623566835` build/start success |
| R4 | PostgreSQL/Artifact/log 持久化、Secret RO、PostgreSQL 不发布到普通客户端网络 | docs/roadmap/01_内网V1上线实施计划.md | satisfied | Golden Path 验证 PG recreate、Artifact marker、宿主 `api.log`、Secret mount `RW=false`、PG/API `PortBindings={}` |
| R5 | 空库 Migration、真实 readiness、API/Worker/Scheduler 共用配置事实 | docs/roadmap/01_内网V1上线实施计划.md | satisfied | 空 PG18.4 `alembic upgrade head`；Nginx `/health/ready` 三项 `ok`；Compose 共用 `x-backend-environment` |
| R6 | 生产不读 `env.local`；TikHub/LLM 不依赖手工 SQL；Provider Config 只保存非敏感配置和 `secret_ref` | docs/roadmap/01_内网V1上线实施计划.md | satisfied | configure 连续执行/disable/re-enable 通过；DB 只保存 `tikhub_api_key` ref；Unit 覆盖 LLM absent/partial/missing-secret/configured |
| R7 | 保留 `/data/AIMA_UGC` 宿主模型并与 Release 解耦 | docs/appendix/11_生产部署与离线Release方案.md | satisfied | `prepare_host.py`/env 模板固定批准目录；Golden Path 验证实际 bind source/target 与持久事实 |
| R8 | 不提前进入 V1-B、完整离线 Release、认证或协调 Backup/Restore | docs/roadmap/01_内网V1上线实施计划.md | satisfied | Roadmap 明确 V1-B 为下一单元且后续能力继续延期；实现 PR 无相关 Contract/Schema/业务扩展 |
| R9 | 合并前执行 L3 Requirement/Completion/Review/CI 门禁，不绕过 PR/CI/Branch Protection | AGENTS.md | satisfied | Requirement Review + Code Quality Review 完成；最终实现 HEAD `3eb388c2a9e9cfa4b8dd36cafc722cfbf5f452b4` 的全部永久 PR workflow success；PR #164 正常合并为 main `2429419f58aa31939d9bbdaf50d5e0b97198c547` |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 无页面业务行为变更；最终 Stage 8F Run `32623566821` success |
| Backend/API/PostgreSQL Integration | required | 最终 CI Run `32623566843` Stage2/3A success；V1-A `32623566835` 真实 PG18.4、Migration、Provider Config、Readiness、持久化 success |
| Contract / Generated Client | not_applicable | 无公共 Contract 变更；最终 CI `32623566843` generated contract/client drift check success |
| Real Full-stack Golden Path | required | 最终 V1-A `32623566835`：Docker build → PG → migrate/configure → API/Worker/Scheduler → Nginx → readiness → mount/port/persistence assertions success |
| Real Provider Probe | not_applicable | 未修改 TikHub endpoint/字段/分页/Capability；真实付费 Provider/LLM Smoke 正式归属 V1-B，本 Change 未发起真实 Provider 请求 |
| Docs / Governance / Other | required | 最终 CI `32623566843`、Completion Gate `32623566851`、Audit `32623566863` success；Roadmap/部署文档/AGENTS 已同步 |

# Completion Audit

- [x] upstream_re_read：实现稳定后重新读取生产 Roadmap、内网 V1 Roadmap、Blueprint 07 与 Production Appendix，从上游独立重建完成定义，没有把本 Change 当需求全集。
- [x] change_coverage：逐项对照 Docker/Compose/Config/宿主/Secret/Migration/Provider/Readiness/网络/持久化/文档要求，均有实现与新鲜证据；未发现需修改公共 Contract/Schema 的缺口。
- [x] reverse_audit：从实际 diff 反向审查配置流、Secret、路径、PortBindings、PG18 初始化/持久化、非 root Runtime、回滚边界，并复核 Validation Matrix。
- [x] unresolved_cleared：V1-A 所有 `not_satisfied` 已清零；V1-B、完整 Release、认证、协调恢复均有 Roadmap 延期依据，不伪装成已完成。

# 两阶段 Review

## Requirement Review

通过。全部上游 V1-A 要求可追踪到实际实现和永久验证；没有缺失的业务 Contract/Schema/前端业务能力；范围没有静默扩展到 V1-B 或完整 Production。

## Code Quality Review

通过，审查中发现并修复：

1. PostgreSQL 初始化临时 Unix-socket server 可能被未指定 host 的 `pg_isready` 误判 ready；改成 `-h 127.0.0.1`，只接受最终 TCP server。
2. `docker compose port` 对仅 `expose` 的服务可能返回 `:0`；安全断言改读 Docker `HostConfig.PortBindings`。
3. `prepare_host.py` 原先会静默接受相对 `--root`，且 symlink 边界不完整；增加显式绝对路径/符号链接校验和回归测试。
4. 补充 LLM fail-closed 与 Provider Config 重复/disable/re-enable 幂等验证。
5. 合并前复核发现根 `AGENTS.md` 仍有“当前没有 Dockerfile/Compose”的旧机器事实说明；在同一实现 PR 中同步为 V1-A 已建立最小容器基础，并重新跑最终 HEAD 全套 PR CI。
6. PR 合并前无未解决 review thread；未发现未解决的严重/重要问题。

# 验证证据

## Red

- CI #2236 / Run `32620834668`：新增目标测试因 `ModuleNotFoundError: aima_ugc.bootstrap.internal_v1` 失败；同轮 PostgreSQL 正常，证明失败来自目标能力不存在。

## 最终 Green（PR HEAD `3eb388c2a9e9cfa4b8dd36cafc722cfbf5f452b4`）

- Change Completion Gate #102 / Run `32623566851`：success。
- CI #2256 / Run `32623566843`：success；Windows bootstrap、Stage3A Database、Stage2 Platform、Stage1 repository checks/Wheel/Frontend checks 全部 success。
- Internal V1-A #19 / Run `32623566835`：success；覆盖宿主准备、Compose config、真实 build、空库 Migration、configure 幂等/disable/re-enable、PG 重建持久化、正式进程、Nginx readiness、UID/mount/PortBindings、Artifact/log/PG 宿主事实。
- Stage8F #383 / Run `32623566821`：success。
- Stage6 #253 / Run `32623566868`：success；PostgreSQL、Quality、Unit 三个 Job 全部 success。
- Stage7 Provider Config #1978 / `32623566859`、Keyword Packs #1865 / `32623566831`、Scheduler #2205 / `32623566826`、Plan Snapshot #1863 / `32623566827`：success。
- Stage1-7 Audit #1080 / Run `32623566863`：success。
- Local Dev #79 / Run `32623566830`：success。
- GitHub PR #164 从 Draft 转 Ready 后，按 expected head `3eb388c2a9e9cfa4b8dd36cafc722cfbf5f452b4` 正常 merge；merge commit `2429419f58aa31939d9bbdaf50d5e0b97198c547`，随后确认 `main` 指向该 commit。

# 文档同步

- `AGENTS.md`：同步 V1-A 已存在根 Dockerfile/Compose 的当前系统基线，同时明确完整离线 Release、Digest/SBOM/签名和协调 Backup-Restore 仍未完成。
- `docs/环境运行与部署.md`：新增实际 V1-A 部署顺序、Secret/Config 边界，并明确不是完整 Production Release。
- `docs/appendix/生产部署与离线Release方案.md`：Docker/Compose 基础更新为已实现；Stage11 改为直接复用/加强 V1-A；完整离线 Release/Auth/Backup Restore 保持待实现。
- `docs/roadmap/内网V1上线实施计划.md`：V1-A 已完成，Internal V1-B 为下一正式单元。
- `docs/roadmap/生产上线实施路线.md`：同步阶段状态，同时保持完整 Production No-Go。

# 兼容、依赖、迁移与回滚

- 公共 HTTP API/OpenAPI/generated client、Canonical、Schema/Migration、Job/Collection/Analysis/Reporting：无变更。
- Python/uv/Node/npm/PostgreSQL：保持仓库锁定版本，无升级/降级；新增 Nginx Runtime 只承载静态资源/反代。
- 无新 Migration；只把现有 `alembic upgrade head` 装成显式 one-shot。
- 本 Change 无 Schema 变更，应用可切回前一可用 image/Compose；PostgreSQL、Artifact、日志、Secret 与 Release 解耦。
- 完整离线 Release rollback 与协调 PG+Artifact 恢复仍未实现。

# 交付状态

- 实现 Branch：`feature/internal-v1a-deployable-stack`
- 实现 PR：#164，已正常合并到 `main`。
- 最终实现 HEAD：`3eb388c2a9e9cfa4b8dd36cafc722cfbf5f452b4`。
- Main merge commit：`2429419f58aa31939d9bbdaf50d5e0b97198c547`。
- 归档 Branch：`chore/archive-internal-v1a`，只负责把本 Change 从 `changes/active/` 移入 `changes/archive/2026-08/` 并保持本文件为 `done`。
- Roadmap 下一最小正式单元：Internal V1-B。

发布定义：Internal V1-A 只完成仓库级最小可部署环境，不等同于 V1-B 公司服务器验收，也不等同于完整 Production Go-Live。
