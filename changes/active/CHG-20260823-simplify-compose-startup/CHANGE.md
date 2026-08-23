---
schema: rvc-change/v1
id: CHG-20260823-simplify-compose-startup
title: 简化 Internal V1 Compose 启动与 Secret 配置
level: L3
status: ready_for_review
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
  - .dockerignore
  - .github/workflows/internal-v1a.yml
  - Dockerfile
  - compose.yaml
  - env.production.example
  - backend/src/aima_ugc/platform/config/settings.py
  - backend/src/aima_ugc/bootstrap/internal_v1.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/bootstrap/analysis_worker.py
  - scripts/deploy/prepare_host.py
  - tests/unit/platform/test_internal_v1_deployment.py
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

把 Internal V1-A 已验证但偏运维化的启动流程收敛成：管理员复制并编辑仓库根 `env.production`，随后用一条 `docker compose --env-file env.production up -d --build --wait` 完成宿主运行目录/内部 Secret 准备、PostgreSQL、Migration、Internal V1 configure、API、Worker、Scheduler 和 Frontend 启动；同时继续保持 Secret File、独立 Migration、非 root Runtime、持久化和端口安全边界。

# 成功标准

- [x] `env.production.example` 成为唯一人工生产配置模板：包含 HTTP、宿主持久目录、日志、TikHub/LLM 外部凭据；真实 `env.production` 继续被 Git ignore，并明确视为敏感文件。
- [x] TikHub/LLM API Key 可以由 `env.production` 提供，但不作为业务容器普通环境变量；Compose 将其以 `/run/secrets/*` Secret File 只授予需要的服务。
- [x] PostgreSQL password 与三个 Cursor signing key 不要求管理员填写；首次启动自动生成并持久保存，后续启动保持不变。
- [x] 已初始化 PostgreSQL 18 数据存在但 `postgres_password` 丢失时 fail closed，禁止自动生成新密码造成数据库/应用密码漂移。
- [x] 默认 Compose 启动路径自动完成 bootstrap → postgres healthy → migrate completed → configure completed → api/worker/scheduler → frontend healthy；Migration 仍是独立一次性进程，不塞进 API 启动。
- [x] 普通管理员不再需要手工执行 `prepare_host.py`、创建 TikHub/LLM Secret 文件、逐个运行 migrate/configure/业务服务；`prepare_host.py` 仅保留为可选诊断/运维入口并复用相同规则。
- [x] Internal V1-A Golden Path 从空宿主状态只靠一个 `docker compose ... up -d --build --wait` 启动，并真实验证 Secret、Migration、Readiness、端口和持久化。
- [x] 二次启动保持 PostgreSQL password、Cursor key 和业务数据；外部 API Key 不进入业务容器 `Config.Env`、Provider Config 数据库行或宿主内部 Secret 目录。
- [x] 不改变公共 HTTP Contract、OpenAPI/generated client、Schema/Migration、业务语义、Provider endpoint/Mapper，也不升级依赖。
- [x] 正式文档同步为当前一键 Compose 入口；Internal V1-B 继续是下一正式开发单元，完整 Production Release/认证/协调 Backup-Restore 仍未完成。
- [x] 修正 Blueprint 中仍声称仓库没有 `Dockerfile`/`compose.yaml`/`env.production.example` 的过期事实。

# 范围与非目标

本 Change 只修改 Internal V1 部署 UX、Compose 编排、生产配置/Secret 装配、宿主准备安全规则、对应 CI 与正式文档。

明确不实现：Internal V1-B 的真实公司服务器/浏览器/真实 TikHub/LLM/reboot 验收；完整离线 Release Bundle、image digest、SBOM/签名；认证授权/HTTPS；协调 Backup/Restore；新 API/Schema/页面；Provider endpoint 或计费策略变化；任何真实外部 API Key 进入 Git、镜像、日志或普通 CI。

# 必须保持不变

- PostgreSQL 18 仍是唯一业务事实库，当前 PG18 bind mount 语义不变。
- API/Worker/Scheduler/Migration 分进程；Migration 仍由 Alembic 独立进程执行。
- 内部 PostgreSQL/Cursor Secret 继续通过 `AIMA_SECRET_DIR` + `read_secret_file()`；生产 Compose 新增 `AIMA_EXTERNAL_SECRET_DIR` 只用于 Provider/LLM 外部 Secret，未配置时回退到 `secret_dir`，因此 Local Dev 单 Secret 根保持兼容。
- 数据库 Provider Config 只保存 `secret_ref`，不保存真实 API Key。
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
| R1 | 管理员只编辑 `env.production`，一条 Compose `up -d --build --wait` 完成正式栈启动 | user:single-compose-startup | satisfied | `env.production.example` + `compose.yaml`；Internal V1-A Run 32626698068 / Job 97163011331 从空宿主仅用该启动命令成功 |
| R2 | 外部 TikHub/LLM Key 可写在 `env.production`，但业务容器继续使用 Secret File，不把 Key 放进业务容器普通环境 | user:single-compose-startup | satisfied | `AIMA_EXTERNAL_SECRET_DIR` + Compose top-level secrets；Golden Path 断言业务容器 `Config.Env` 无 API Key，Worker 可读批准 Secret，API 无 TikHub Secret |
| R3 | PostgreSQL 密码无需管理员配置，自动生成并与应用匹配；已有 DB 丢 Secret 时禁止重新生成 | user:postgres-password-policy | satisfied | `prepare_host.py` recovery guard + unit regression；Golden Path 二次启动 hash 不变、丢 Secret fail closed、恢复原 Secret 后可恢复 |
| R4 | PostgreSQL/Artifact/log 持久化、Secret 边界、Migration 独立进程、PostgreSQL/API 不发布宿主端口继续保留 | docs/roadmap/内网V1上线实施计划.md | satisfied | `compose.yaml`；Run 32626698068 验证持久挂载、one-shot migrate、RO internal secret、PortBindings 与 readiness |
| R5 | V1-A 部署基础继续服务 Internal V1-B，不能把本次 UX 收敛误写成完整 Production Go-Live | docs/roadmap/生产上线实施路线.md | satisfied | 两份 Roadmap + Production Appendix 均保留 Internal V1-B 与完整 Production 未完成边界 |
| R6 | 真实 `env.production` 不进 Git，Secret 不进 Git/镜像/页面/日志/数据库明文 | docs/blueprint/05-日志安全部署与运维.md | satisfied | `.gitignore` 既有 `env.production`；Compose/CI 只使用假 Key；Golden Path 验证 DB/Config.Env/内部 Secret 目录无假 Key；业务日志仍走既有脱敏体系 |
| R7 | L3 Change 需要 Traceability、Completion Audit、两阶段 Review、Ready Check/CI，正常 PR 合并且不绕过门禁 | AGENTS.md | satisfied | 本 Change Traceability/Matrix/Audit/Review 已完成；PR #166 保持 Draft 至 Ready Gate，当前永久 CI 除 in_progress Gate 外均已成功，改为 ready_for_review 后重新取最终证据 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互；部署入口由 Compose/HTTP readiness 证明 |
| Backend/API/PostgreSQL Integration | required | 单元测试覆盖设置/Secret 根兼容/PG 密码恢复保护；真实 PostgreSQL 18 与 Migration 由 Compose Golden Path 覆盖 |
| Contract / Generated Client | not_applicable | 不修改公共 HTTP/Pydantic/OpenAPI/generated client；常规 CI 的 generated/contract 漂移门禁仍通过 |
| Real Full-stack Golden Path | required | Run 32626698068 / Job 97163011331 从空宿主一条 Compose 命令启动真实 frontend/api/worker/scheduler/postgres/migrate/configure/bootstrap 并通过 readiness、持久化、Secret 与恢复断言 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部接口事实；CI 只用假 Key，不发真实付费请求 |
| Docs / Governance / Other | required | env 模板、环境部署、Production Appendix、Roadmap、Blueprint 当前事实已同步；最终 Ready Gate/CI 在 final HEAD 再取证 |

# Completion Audit

- [x] upstream_re_read：2026-08-23 在实现稳定后重新读取本轮用户决定、`AGENTS.md`、两份 Roadmap、Blueprint 05/07、Production Appendix，独立重建完成定义；下一阶段仍是 Internal V1-B。
- [x] change_coverage：逐项核对一命令启动、env/Secret、DB 密码恢复保护、Migration、持久化、端口、兼容和文档要求，没有发现遗漏 Requirement。
- [x] reverse_audit：从最终 Compose/Settings/Worker/Analysis/prepare_host/CI 反向检查 Secret 流向、服务授权、容器环境、启动依赖、root 生命周期、持久化和失败边界；Validation Matrix 证据等级匹配风险。
- [x] unresolved_cleared：所有 Requirement 已满足；Browser/Contract/Real Provider 三层不适用均有当前任务边界依据，没有把 Internal V1-B 或完整 Production 能力伪装成已完成。

# 实施任务

1. [x] Red：补部署回归测试并取得目标失败证据。
2. [x] Green：修改 `prepare_host.py` / Dockerfile，提供 Compose bootstrap 和安全内部 Secret 生命周期。
3. [x] Green：重构 Compose，分离内部/外部 Secret 根并自动编排 Migration/configure/正式服务。
4. [x] 收敛 `env.production.example`，Golden Path 改成一条 Compose 启动并验证无泄漏、幂等、持久化和密码恢复保护。
5. [x] 同步环境部署、Production Appendix、Roadmap 与过期 Blueprint 当前事实。
6. [x] 完成 Completion Audit、Requirement Review 与 Code Quality Review；最终 Ready Check/永久 CI 由本次状态提交触发。
7. [ ] 合并后创建独立归档 PR，将 Change 标记 `done` 移入 `changes/archive/2026-08/`，跑永久 CI 后正常合并。

# 兼容、Migration、部署与回滚

- HTTP Contract/Schema/Alembic Migration：无变更。
- 依赖/锁文件：无升级。
- Local Dev：`AIMA_EXTERNAL_SECRET_DIR` 未设置时回退到现有 `AIMA_SECRET_DIR`，现有 `env.local` / `.runtime/secrets` 行为保持。
- 部署配置：旧的手工 V1-A 操作入口被新的单命令入口替代；既有 `/data/AIMA_UGC` PostgreSQL/Artifact/log/内部 Secret 持久目录继续复用。
- 外部 Key：从旧宿主 `shared/secrets/tikhub_api_key|llm_api_key` 人工文件迁移为 `env.production` → Compose Secret；旧外部 Key 文件不作为隐式 fallback，避免两套来源漂移。
- 回滚：未改 Schema，可切回旧 Compose/Dockerfile；不得删除既有 PostgreSQL/Artifact/log/内部 Secret。若回滚到旧 V1-A，管理员需按旧方式恢复外部 Secret 文件。
- 风险重点：Compose Secret 与 `--env-file`、one-shot 依赖、PG 已初始化但 Secret 丢失、二次启动 Secret/数据持久性均已由 Linux Golden Path覆盖。

# 文档影响

已同步 `docs/环境运行与部署.md`、Production Appendix、两份 Roadmap、Blueprint README/05。`AGENTS.md` 当前已正确描述 V1-A 已存在 Dockerfile/Compose，无需复制操作手册。

# 验证证据

## Red

- PR #166 早期 HEAD `2713bc227c3bd0cbec41833ce02e884f30a34f77`：CI Run `32625725287`，Stage 2 Platform Job `97160668331`，结果 **3 failed / 98 passed**；三项失败分别证明 env 模板、Compose bootstrap 编排和已有 PG 数据丢密码保护尚未实现。

## Green / 根因修复

- Run `32625978378` / Job `97161294625`：发现 `.dockerignore` 把 `scripts/` 排除，导致 Dockerfile 无法 COPY bootstrap 脚本；修为只放行 `scripts/deploy/prepare_host.py`。
- Run `32626042795` / Job `97161454616`：发现 Compose 会先创建所有容器，不能预绑定“稍后由 bootstrap 创建”的单一密码文件；改为 PostgreSQL 只读挂载内部 Secret 目录。
- Run `32626158672` / Job `97161734667`：发现 Compose Secret 不能挂到已只读 bind 的 `/run/secrets` 子路径；将内部 Secret 根改为 `/run/internal-secrets`，外部 Compose Secret 保持 `/run/secrets`，并给 Settings 增加向后兼容回退。
- Code Quality reverse audit 发现早期 bootstrap 使用 `sleep infinity` 会留下长期 root + RW 宿主挂载容器；已改成真正 one-shot，成功即退出 0，PostgreSQL 依赖 `service_completed_successfully`。
- Internal V1-A Run `32626698068` / Compose Golden Path Job `97163011331`：上述最终 one-shot 设计完整成功。
- 当前实现 HEAD `4bed19aee6b74d0a11202dc40b205a0a554c106e`：CI Run `32626954213`、Internal V1-A Run `32626954162`、Stage 8F Run `32626954137` 及 Stage 6/7/Audit/Local Dev 等永久工作流均成功；Change Completion Gate Run `32626954165` 唯一失败原因为本 Change 当时仍是 `in_progress`，本提交将状态正式切到 `ready_for_review` 后重新验证。
- 未执行真实 TikHub/LLM 请求，普通 CI 仅使用明确的假 Key，不产生 Provider/LLM 费用。

# 两阶段 Review

## Requirement Review

2026-08-23 已完成 A1/A2：

- A1 上游 → Change：用户确认的一命令启动、单 env 输入、外部 API Key Secret File、PostgreSQL 密码自动生成/丢失保护全部进入 R1-R3；Roadmap 持久化/网络/阶段边界和 AGENTS 治理进入 R4-R7，没有发现遗漏。
- A2 Change → 实现/测试/文档：R1-R6 均有机器实现和对应单元/真实 Compose 证据；R7 的语义 Review 已完成，机器 Ready Gate/最终 PR CI 由 `ready_for_review` 提交重新触发。
- 不修改前端业务行为、公共 Contract/Schema/Provider endpoint，因此没有人为制造 Browser/Contract/Real Provider 测试层。

结论：无未满足业务/部署 Requirement；Internal V1-B/完整 Production 范围未被静默扩大或提前宣称完成。

## Code Quality Review

2026-08-23 已完成：

- Secret 授权最小化：configure 拿 TikHub+LLM；worker 拿 TikHub+LLM；api 只拿 LLM；scheduler 不拿外部 Secret。
- 外部 Key 不在业务容器环境；内部持久 Secret 对正常 Runtime 只读；Provider Config 仅 `secret_ref`。
- `bootstrap` 唯一 root 服务且 `network_mode: none`、one-shot、`restart: no`，成功后不常驻高权限容器。
- PostgreSQL password 与数据库数据生命周期绑定；已有数据丢 Secret 时 fail closed，避免“生成新文件但数据库仍使用旧密码”的恢复陷阱。
- Migration/configure 保持 one-shot 独立边界；API/Worker/Scheduler 只在 configure 成功后启动。
- Local Dev 兼容：新增 external root 为可选配置，缺省回退原 secret root；常规 Local Dev CI 已通过。
- 未发现未解决的 serious / important 代码、安全、事务、数据一致性或兼容问题。

# Git / PR

- branch: `feature/simplify-compose-startup`
- implementation PR: `#166`（Draft，待最终 Ready Gate/CI 后转 Ready）
- archive PR: 实现 PR 合并后创建
