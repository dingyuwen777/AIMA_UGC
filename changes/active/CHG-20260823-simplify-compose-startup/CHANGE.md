---
schema: rvc-change/v1
id: CHG-20260823-simplify-compose-startup
title: 简化 Internal V1 Compose 启动与 Secret 配置
level: L3
status: in_progress
owner: chatgpt
branch: feature/simplify-compose-startup
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - configuration
  - security
  - runtime
  - ci
affected_paths:
  - Dockerfile
  - compose.yaml
  - env.production.example
  - scripts/deploy/prepare_host.py
  - tests/unit/platform/test_internal_v1_deployment.py
  - .github/workflows/internal-v1a.yml
  - docs/环境运行与部署.md
  - docs/appendix/生产部署与离线Release方案.md
  - docs/roadmap/内网V1上线实施计划.md
  - docs/roadmap/生产上线实施路线.md
  - docs/blueprint/README.md
  - docs/blueprint/05-日志安全部署与运维.md
contracts: []
data_changes: []
---

# 目标

把 Internal V1-A 已验证但偏运维化的启动流程收敛成：管理员复制并编辑仓库根 `env.production`，随后用一条 `docker compose --env-file env.production up -d --build --wait` 完成宿主目录/内部 Secret 准备、PostgreSQL、Migration、Internal V1 configure、API、Worker、Scheduler 和 Frontend 启动；同时继续保持现有 Secret File、独立 Migration、非 root Runtime、持久化和端口安全边界。

# 成功标准

- [ ] `env.production.example` 成为唯一人工生产配置模板：包含 HTTP、宿主持久目录、日志、TikHub/LLM 外部凭据；真实 `env.production` 继续被 Git ignore，并明确视为敏感文件。
- [ ] TikHub/LLM API Key 可以由 `env.production` 提供，但不作为业务容器环境变量；Compose 将其以 `/run/secrets/*` Secret File 只授予需要的服务。
- [ ] PostgreSQL password 与三个 Cursor signing key 不要求管理员填写；首次启动自动生成并持久保存，后续启动保持不变。
- [ ] 已初始化 PostgreSQL 18 数据存在但 `postgres_password` 丢失时必须 fail closed，禁止自动生成新密码造成数据库/应用密码漂移。
- [ ] 默认 Compose 启动路径自动完成 bootstrap → postgres healthy → migrate completed → configure completed → api/worker/scheduler → frontend healthy；Migration 仍是独立一次性进程，不塞进 API 启动。
- [ ] 普通管理员不再需要手工执行 `prepare_host.py`、创建 TikHub/LLM Secret 文件、逐个运行 migrate/configure/业务服务；`prepare_host.py` 仅保留为可选诊断/运维入口并复用相同规则。
- [ ] Internal V1-A Golden Path 从空宿主状态只靠一个 `docker compose ... up -d --build --wait` 启动，并真实验证 Secret、Migration、Readiness、端口和持久化。
- [ ] 二次启动/容器重建保持 PostgreSQL password、Cursor key 和业务数据；外部 API Key 不进入业务容器 `Config.Env`、数据库或日志。
- [ ] 不改变公共 HTTP Contract、OpenAPI/generated client、Schema/Migration、业务语义、Provider endpoint/Mapper，也不升级依赖。
- [ ] 正式文档同步为当前一键 Compose 入口；Internal V1-B 继续是下一正式开发单元，完整 Production Release/认证/协调 Backup-Restore 仍未完成。
- [ ] 修正 Blueprint 中仍声称仓库没有 `Dockerfile`/`compose.yaml`/`env.production.example` 的过期描述。

# 范围与非目标

本 Change 只修改 Internal V1 部署 UX、Compose 编排、生产配置/Secret 装配、宿主准备安全规则、对应 CI 与正式文档。

明确不实现：Internal V1-B 的真实公司服务器/浏览器/真实 TikHub/LLM/reboot 验收；完整离线 Release Bundle、image digest、SBOM/签名；认证授权/HTTPS；协调 Backup/Restore；新 API/Schema/页面；Provider endpoint 或计费策略变化；任何真实外部 API Key 进入 Git、镜像、日志或普通 CI。

# 必须保持不变

- PostgreSQL 18 仍是唯一业务事实库，当前 PG18 bind mount 语义不变。
- API/Worker/Scheduler/Migration 分进程；Migration 仍由 Alembic 独立进程执行。
- 应用继续通过 `AIMA_SECRET_DIR` + `read_secret_file()` 读取 Secret；数据库 Provider Config 只保存 `secret_ref`。
- Local ArtifactStore、应用 `.log`、PostgreSQL 数据继续落宿主持久目录。
- Frontend 是唯一发布宿主 HTTP 端口的服务；PostgreSQL/API 不发布普通宿主端口。
- 本地源码开发 `env.local` / `scripts/dev/*` 不改成本次生产入口。

# L3 方案比较与已确认决定

## 方案 A：保留 V1-A 手工拆分流程

优点是每个运维步骤显式；缺点是管理员需要运行宿主脚本、手工 Secret 文件、migrate/configure 和多次 Compose 命令，和当前内网 V1 的单服务器目标不匹配。

## 方案 B：所有 Secret 直接作为业务容器环境变量

操作最短，但 API Key/数据库密码更容易通过容器环境、诊断输出或错误处理泄露，并破坏仓库现有 Secret File 边界，不采用。

## 方案 C：一个 `env.production` + Compose 内部编排 + Secret File（采用）

管理员只维护 `env.production`；外部 API Key 由 Compose Secret 转成文件，内部 PostgreSQL/Cursor Secret 自动生成并持久化；Compose 自动编排 bootstrap/Migration/configure/正式服务。该方案满足用户确认的一命令目标，同时保留当前安全/架构边界。

用户已明确批准方案 C，并授权实现、验证、PR 与正常合并到 `main`。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 管理员只编辑 `env.production`，一条 Compose `up -d --build --wait` 完成正式栈启动 | user:single-compose-startup | not_satisfied | 实现与 Golden Path 待完成 |
| R2 | 外部 TikHub/LLM Key 可写在 `env.production`，但业务容器继续使用 Secret File，不把 Key 放进业务容器环境 | user:single-compose-startup | not_satisfied | Compose Secret 与泄漏断言待完成 |
| R3 | PostgreSQL 密码无需管理员配置，自动生成并与应用匹配；已有 DB 丢 Secret 时禁止重新生成 | user:postgres-password-policy | not_satisfied | 安全 guard 与回归测试待完成 |
| R4 | PostgreSQL/Artifact/log 持久化、Secret 边界、Migration 独立进程、PostgreSQL/API 不发布宿主端口继续保留 | docs/roadmap/内网V1上线实施计划.md | not_satisfied | Compose Golden Path 待回归 |
| R5 | V1-A 部署基础继续服务 Internal V1-B，不能把本次 UX 收敛误写成完整 Production Go-Live | docs/roadmap/生产上线实施路线.md | not_satisfied | Roadmap/部署文档待同步 |
| R6 | 真实 `env.production` 不进 Git，Secret 不进 Git/镜像/页面/日志/数据库明文 | docs/blueprint/05-日志安全部署与运维.md | not_satisfied | `.gitignore` 既有事实 + 新 CI/文档待验证 |
| R7 | L3 Change 需要 Traceability、Completion Audit、两阶段 Review、Ready Check/CI，正常 PR 合并且不绕过门禁 | AGENTS.md | not_satisfied | Ready/CI/Review/PR 待完成 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互；部署入口由 Compose/HTTP readiness 证明 |
| Backend/API/PostgreSQL Integration | required | PostgreSQL 18、Migration、配置、内部 Secret 生命周期、Readiness、持久化与端口边界 |
| Contract / Generated Client | not_applicable | 不修改公共 HTTP/Pydantic/OpenAPI/generated client；常规 CI 负责漂移回归 |
| Real Full-stack Golden Path | required | 从空宿主状态一条 Compose 命令启动真实 frontend/api/worker/scheduler/postgres/migrate/configure/bootstrap 并通过 readiness |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部接口事实；CI 只用假 Key，不发真实付费请求 |
| Docs / Governance / Other | required | env 模板、部署文档、Roadmap、Blueprint 当前事实、Ready Gate 与两阶段 Review |

# Completion Audit

- [ ] upstream_re_read：实现稳定后重新读取本轮用户决定、Roadmap、Blueprint 05/07 和 Production Appendix，独立重建完成定义。
- [ ] change_coverage：逐项核对一命令启动、env/Secret、DB 密码恢复保护、Migration、持久化、端口、文档要求没有遗漏。
- [ ] reverse_audit：从最终 Compose/脚本/CI 反向检查 Secret 流向、容器环境、启动依赖、重启/持久化与失败边界；复核 Validation Matrix。
- [ ] unresolved_cleared：Ready 前所有 `not_satisfied` 清零；不适用/延期均有正式依据。

# 实施任务

1. Red：补部署回归测试，锁定 env 模板、一命令拓扑与“已有数据库 + 丢 PostgreSQL Secret 必须拒绝”的行为，并取得目标失败证据。
2. Green：修改 `prepare_host.py` 与 `Dockerfile`，提供 Compose 内部 bootstrap/健康检查和安全的内部 Secret 生命周期。
3. Green：重构 `compose.yaml`，使用 Compose Secret 装配外部 Key，并通过 `service_healthy` / `service_completed_successfully` 自动编排 Migration/configure/正式服务。
4. 把 `env.production.example` 收敛为唯一人工入口，更新 Internal V1-A Golden Path 为单条 Compose 启动并验证无 Secret 泄漏、幂等与持久化。
5. 同步环境部署、Production Appendix、Roadmap 与两处过期 Blueprint 当前事实。
6. 完成 Completion Audit、Requirement Review、Code Quality Review、Ready Check 和全部永久 PR CI；无严重/重要问题后转 Ready 并正常合并。
7. 合并后创建独立归档 PR，将 Change 标记 `done` 移入 `changes/archive/2026-08/`，跑永久 CI 后正常合并。

# 兼容、Migration、部署与回滚

- HTTP Contract/Schema/Alembic Migration：无变更。
- 依赖/锁文件：不升级。
- 部署配置：旧的手工 V1-A 操作入口被新的单命令入口替代；既有 `/data/AIMA_UGC` 持久数据与内部 Secret 文件继续复用。
- 外部 Key：从旧宿主 `shared/secrets/tikhub_api_key|llm_api_key` 人工文件迁移为 `env.production` → Compose Secret；旧文件不得成为隐式 fallback。
- 回滚：在未改 Schema 的前提下可切回旧 Compose/Dockerfile；既有 PostgreSQL/Artifact/log/内部 Secret 持久目录不删除。若回滚到旧 V1-A，管理员需按旧方式恢复外部 Secret 文件。
- 风险重点：Compose Secret 与 `--env-file` 兼容、one-shot 依赖在 `up --wait` 下的行为、PG 已初始化但 Secret 丢失、重启时 Secret/数据持久性；全部由 Linux Compose Golden Path 覆盖。

# 文档影响

同步：`docs/环境运行与部署.md`、Production Appendix、两份 Roadmap、Blueprint README/05。`AGENTS.md` 当前已正确描述 V1-A 存在 Dockerfile/Compose，无需为一条启动命令复制操作手册。

# 验证证据

## Red

待执行。

## Green

待执行。

# 两阶段 Review

## Requirement Review

待 Ready 前执行。

## Code Quality Review

待 Ready 前执行。

# Git / PR

- branch: `feature/simplify-compose-startup`
- implementation PR: 待创建
- archive PR: 待实现合并后创建
