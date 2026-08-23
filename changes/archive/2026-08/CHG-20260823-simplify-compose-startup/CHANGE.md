---
schema: rvc-change/v1
id: CHG-20260823-simplify-compose-startup
title: 简化 Internal V1 Compose 启动与 Secret 配置
level: L3
status: done
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

每个运维步骤显式，但管理员需要运行宿主脚本、手工 Secret 文件、migrate/configure 和多次 Compose 命令，和当前内网 V1 的单服务器目标不匹配。

## 方案 B：所有 Secret 直接作为业务容器环境变量

操作最短，但增加环境/诊断泄漏风险，并破坏仓库现有 Secret File 边界，不采用。

## 方案 C：一个 `env.production` + Compose 内部编排 + Secret File（采用）

管理员只维护 `env.production`；外部 API Key 由 Compose Secret 转成文件，内部 PostgreSQL/Cursor Secret 自动生成并持久化；Compose 自动编排 bootstrap/Migration/configure/正式服务。用户明确批准方案 C，并授权实现、验证、PR 与正常合并到 `main`。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 管理员只编辑 `env.production`，一条 Compose `up -d --build --wait` 完成正式栈启动 | user:single-compose-startup | satisfied | `env.production.example` + `compose.yaml`；最终 Internal V1-A Run 32627321814 成功 |
| R2 | 外部 TikHub/LLM Key 可写在 `env.production`，但业务容器继续使用 Secret File，不把 Key 放进业务容器普通环境 | user:single-compose-startup | satisfied | `AIMA_EXTERNAL_SECRET_DIR` + Compose top-level secrets；Golden Path 验证 `Config.Env` 无 API Key，且 Secret 只授予需要的服务 |
| R3 | PostgreSQL 密码无需管理员配置，自动生成并与应用匹配；已有 DB 丢 Secret 时禁止重新生成 | user:postgres-password-policy | satisfied | `prepare_host.py` guard + regression；Golden Path 验证二次启动 hash 不变、丢 Secret fail closed、恢复原 Secret 后可恢复 |
| R4 | PostgreSQL/Artifact/log 持久化、Secret 边界、Migration 独立进程、PostgreSQL/API 不发布宿主端口继续保留 | docs/roadmap/内网V1上线实施计划.md | satisfied | `compose.yaml` + 最终 Internal V1-A Golden Path |
| R5 | V1-A 部署基础继续服务 Internal V1-B，不能把本次 UX 收敛误写成完整 Production Go-Live | docs/roadmap/生产上线实施路线.md | satisfied | 两份 Roadmap + Production Appendix 保留 V1-B 与完整 Production 未完成边界 |
| R6 | 真实 `env.production` 不进 Git，Secret 不进 Git/镜像/页面/日志/数据库明文 | docs/blueprint/05-日志安全部署与运维.md | satisfied | `.gitignore` + Compose/CI 假 Key + DB/Config.Env/内部 Secret 目录无明文泄漏断言 |
| R7 | L3 Change 需要 Traceability、Completion Audit、两阶段 Review、Ready Check/CI，正常 PR 合并且不绕过门禁 | AGENTS.md | satisfied | Completion Gate Run 32627321768 成功；PR #166 final HEAD 全部永久 CI 成功并正常合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互；部署入口由 Compose/HTTP readiness 证明 |
| Backend/API/PostgreSQL Integration | required | 单元测试覆盖 Settings/Secret 根兼容/PG 密码恢复保护；真实 PostgreSQL 18 与 Migration 由 Compose Golden Path 覆盖 |
| Contract / Generated Client | not_applicable | 不修改公共 HTTP/Pydantic/OpenAPI/generated client；总 CI generated/contract 漂移门禁通过 |
| Real Full-stack Golden Path | required | final Internal V1-A Run 32627321814；从空宿主一条 Compose 命令启动真实栈并验证 readiness、持久化、Secret 与恢复 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部接口事实；CI 仅用假 Key，不发真实付费请求 |
| Docs / Governance / Other | required | env 模板、环境部署、Production Appendix、Roadmap、Blueprint 已同步；Completion Gate 与最终永久 CI 全绿 |

# Completion Audit

- [x] upstream_re_read：实现稳定后重新读取用户决定、`AGENTS.md`、两份 Roadmap、Blueprint 05/07、Production Appendix；实施合并后又重新读取新 `main` 的 `AGENTS.md`。
- [x] change_coverage：一命令启动、env/Secret、DB 密码恢复保护、Migration、持久化、端口、兼容和文档要求均有实现与验证。
- [x] reverse_audit：从最终 Compose/Settings/Worker/Analysis/prepare_host/CI 反向检查 Secret 流向、服务授权、容器环境、启动依赖、root 生命周期、持久化和失败边界。
- [x] unresolved_cleared：所有 Requirement 已满足；不适用层均有真实范围依据；没有把 Internal V1-B 或完整 Production 误写为已完成。

# 实施任务

1. [x] Red：补部署回归测试并取得目标失败证据。
2. [x] Green：实现 Compose bootstrap 和安全内部 Secret 生命周期。
3. [x] Green：分离内部/外部 Secret 根并自动编排 Migration/configure/正式服务。
4. [x] 收敛 `env.production.example`，Golden Path 改成一条 Compose 启动并验证无泄漏、幂等、持久化和密码恢复保护。
5. [x] 同步环境部署、Production Appendix、Roadmap 与过期 Blueprint 当前事实。
6. [x] 完成 Completion Audit、Requirement Review、Code Quality Review、Ready Gate 和全部永久 PR CI。
7. [x] PR #166 正常合并到 `main`；创建独立归档 PR 完成 Change 归档。

# 兼容、Migration、部署与回滚

- HTTP Contract/Schema/Alembic Migration：无变更。
- 依赖/锁文件：无升级。
- Local Dev：`AIMA_EXTERNAL_SECRET_DIR` 未设置时回退 `AIMA_SECRET_DIR`，现有 `env.local` / `.runtime/secrets` 行为保持。
- 部署配置：旧的手工 V1-A 操作入口被新的单命令入口替代；既有 `/data/AIMA_UGC` PostgreSQL/Artifact/log/内部 Secret 持久目录继续复用。
- 外部 Key：旧宿主 `shared/secrets/tikhub_api_key|llm_api_key` 不再作为生产 Compose 的隐式 fallback；管理员需把外部 Key 配在真实 `env.production`，避免两套来源漂移。
- 回滚：未改 Schema，可切回旧 Compose/Dockerfile；不得删除既有 PostgreSQL/Artifact/log/内部 Secret。若回滚到旧 V1-A，需要按旧方式恢复外部 Secret 文件。

# 验证证据

## Red

- HEAD `2713bc227c3bd0cbec41833ce02e884f30a34f77`：CI Run `32625725287` / Stage 2 Platform Job `97160668331`，**3 failed / 98 passed**；失败对应 env 模板、Compose bootstrap 编排和已有 PG 数据丢密码保护。

## Green / 根因修复

- Run `32625978378` / Job `97161294625`：`.dockerignore` 排除生产 bootstrap 脚本，修为只放行 `scripts/deploy/prepare_host.py`。
- Run `32626042795` / Job `97161454616`：Compose 创建阶段无法预绑定尚未生成的单个 password file，改为 PostgreSQL 只读挂载内部 Secret 目录。
- Run `32626158672` / Job `97161734667`：外部 Compose Secret 与 `/run/secrets` 只读父 bind 冲突，改为内部 `/run/internal-secrets`、外部 `/run/secrets` 双根，并保留 Local Dev 回退兼容。
- Code Quality Review 发现早期 bootstrap 长期 `sleep infinity` 会留下 root + RW 宿主挂载容器，已改成 `network_mode: none` 的真正 one-shot，成功后退出 0。
- Run `32626698068` / Job `97163011331`：one-shot 最终设计完整 Golden Path 成功。

## Final feature HEAD

`de6d6549d8c3601b23b6668b4bb0c79f7d12f842`

最终永久 PR CI 全部成功：

- Change Completion Gate `32627321768`
- CI `32627321818`
- Internal V1-A Deployable Stack `32627321814`
- Stage 8F Full-stack Acceptance `32627321785`
- Stage 1-7 Audit Correctness `32627321776`
- Stage 4 Job Runtime `32627321758`
- Stage 6 `32627321770`
- Stage 7 Plan Snapshot `32627321764`
- Stage 7 Scheduler `32627321792`
- Stage 7 Provider Config `32627321777`
- Stage 7 Keyword Packs `32627321837`
- Local Dev Bootstrap `32627321750`

未执行真实 TikHub/LLM 请求；普通 CI 只使用明确的假 Key，不产生 Provider/LLM 费用。

# 两阶段 Review

## Requirement Review

- A1 上游 → Change：用户的一命令启动、单 env 输入、外部 API Key Secret File、PostgreSQL 密码自动生成/丢失保护全部覆盖；Roadmap 持久化/网络/阶段边界与 AGENTS 治理无遗漏。
- A2 Change → 实现/测试/文档：R1-R7 均有机器实现/CI/文档或治理证据。
- 不修改前端业务行为、公共 Contract/Schema/Provider endpoint，因此未制造不适用的 Browser/Contract/Real Provider 测试。

结论：无未满足业务/部署 Requirement；Internal V1-B/完整 Production 范围未被静默扩大。

## Code Quality Review

- Secret 授权最小化：configure 获取 TikHub+LLM；worker 获取 TikHub+LLM；api 只获取 LLM；scheduler 不获取外部 Secret。
- 外部 Key 不在业务容器普通环境；内部持久 Secret 对正常 Runtime 只读；Provider Config 仅 `secret_ref`。
- `bootstrap` 是唯一 root 服务，`network_mode: none`、one-shot、`restart: no`，成功后不常驻。
- 已有 PostgreSQL 数据丢密码 Secret 时 fail closed，避免应用/数据库凭据漂移。
- Migration/configure 保持 one-shot 独立边界；Local Dev 回退兼容已由常规 CI 验证。
- PR 无未解决 Review thread；未发现未解决 serious / important 问题。

# Git / PR

- implementation branch: `feature/simplify-compose-startup`
- implementation PR: `#166`，Ready 后正常合并
- implementation merge commit: `b19029bd708a527a184549cd37bf7205f19da697`
- post-merge `main` 已确认指向上述 merge commit
- archive branch: `chore/archive-simplify-compose-startup`
- archive PR: 由本归档提交创建并在永久 CI 全绿后正常合并

# 后续

当前下一最小正式开发单元仍是 **Internal V1-B：公司服务器真实部署验收**。完整 Production Release、认证授权、协调 Backup/Restore 等仍属于后续阶段，不能因本 Change 完成而提前声明闭环。
