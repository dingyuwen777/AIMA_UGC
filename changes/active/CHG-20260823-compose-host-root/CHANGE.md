---
schema: rvc-change/v1
id: CHG-20260823-compose-host-root
title: 统一本地与服务器 Compose 宿主持久根目录配置
level: L3
status: in_progress
owner: chatgpt
branch: feature/compose-host-root
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - docker-compose
  - local-development
  - production-release
  - ci
affected_paths:
  - compose.yaml
  - env.production.example
  - .github/workflows/internal-v1a.yml
  - docs/环境运行与部署.md
  - docs/blueprint/05-日志安全部署与运维.md
  - docs/roadmap/生产上线实施路线.md
  - docs/appendix/生产部署与离线Release方案.md
contracts: []
data_changes: []
---

# 目标

让同一套 `compose.yaml + env.production` 同时适用于本地完整容器运行和服务器运行，同时保持正式 Production Release 的不可变镜像、独立持久数据、升级/回滚和恢复边界。

# 可观察成功标准

- [ ] `env.local.example` 继续只服务源码开发，不与 Compose 配置混用。
- [ ] `env.production.example` 继续作为完整容器 Runtime 配置模板，本地 Docker 与服务器 Docker 共用同一字段结构。
- [ ] 四个宿主目录变量收敛为单一 `AIMA_HOST_ROOT`；Compose 从根目录推导 PostgreSQL、Artifact、日志和内部 Secret 路径。
- [ ] 服务器推荐 `AIMA_HOST_ROOT=/data/AIMA_UGC`，持久状态继续位于 Release 目录之外。
- [ ] 本地 Compose 可以将 `AIMA_HOST_ROOT=./.runtime/compose`，且 `.runtime/` 保持 Git ignore / Docker build context ignore。
- [ ] Linux CI 同时验证生产式绝对 Host Root 与本地式仓库相对 Host Root 的 Compose 解析/真实启动。
- [ ] 不修改数据库 Schema、Migration、公共 Contract、依赖或业务语义。
- [ ] 正式文档同步源码开发、本地 Compose、服务器 Compose、未来不可变 Release 四种生命周期边界。
- [ ] L3 Completion Audit、两阶段 Review、Ready Check 与永久 CI 通过后才进入 Ready/合并。

# 范围

- `compose.yaml` 的宿主 bind source 配置。
- `env.production.example` 的宿主持久化配置模型。
- Internal V1-A Compose Golden Path。
- 部署/环境/安全/Roadmap/Release 文档中的配置说明。

# 非目标

- 不删除 `env.local.example` 或源码开发 launcher。
- 不把生产数据放入版本化 Release 目录。
- 不在本 Change 实现完整 Stage 11 离线 Release、固定 digest、SBOM/签名、协调 Backup/Restore 或认证授权。
- 不改变 PostgreSQL 18.4、容器服务拓扑、Secret 分类、Migration 顺序、Provider/LLM 行为。
- 不引入第二套 Compose 文件或 local/production 分叉配置。

# 必须保持不变

1. 服务器持久状态必须与应用 Release 生命周期解耦。
2. `PostgreSQL + Artifact + log + internal secrets` 不进入镜像，不进入 Git，不因容器/应用版本切换丢失。
3. 外部 TikHub/LLM Key 继续由敏感 `env.production` 输入并转成 Compose Secret File；业务容器普通环境变量不含 Key 原值。
4. 已有 PostgreSQL 18 数据但 `postgres_password` 丢失时继续 fail closed。
5. 正式 Production 目标仍是服务器 `docker load` 已验证镜像后 `--no-build --pull never`；Internal V1-A/B 的 `--build` 不升级为完整 Production Release。

# 已确认关键决策

1. 保留 `env.local.example`：仅源码开发、热更新入口使用。
2. 保留 `env.production.example`：完整 Docker Compose Runtime 使用，本地与服务器共用同一配置结构。
3. 不改名为 `env.compose.example`，避免与当前 Production Release 文档和运维心智模型制造第二套名称。
4. 宿主持久目录配置收敛为一个 `AIMA_HOST_ROOT`。
5. 本地 Docker 每台机器首次配置一次 `AIMA_HOST_ROOT=./.runtime/compose`；服务器首次配置一次 `AIMA_HOST_ROOT=/data/AIMA_UGC`，日常不来回修改。
6. Release 版本目录与持久 Host Root 分离；未来镜像发布只替换应用镜像/Release，不替换数据库、Artifact、日志和内部 Secret。

# L3 方案比较

## 方案 A：保留四个独立 Host Path

优点：当前行为无需迁移。缺点：本地/服务器需要维护四个重复路径，容易配置漂移，不能满足本轮简化目标。

## 方案 B：单一 `AIMA_HOST_ROOT` 推导四类持久路径（采用）

优点：只保留一个环境差异点；同一 Compose/配置 Schema 可用于本地与服务器；服务器仍保持持久状态与 Release 解耦；回滚简单。缺点：旧 `AIMA_HOST_*_DIR` 配置需要一次性迁移到根目录变量。

## 方案 C：本地 named volumes、服务器 bind mounts / 两套 Compose

优点：可规避部分桌面文件系统差异。缺点：引入两套持久化模型/Compose 组合，长期更容易漂移，不符合用户“同一 Compose、不改来改去”的目标，当前无必要证据支持增加复杂度。

# 兼容、Migration、部署与回滚

- 配置兼容：`AIMA_HOST_DATA_DIR`、`AIMA_HOST_LOG_DIR`、`AIMA_HOST_POSTGRES_DIR`、`AIMA_HOST_SECRET_DIR` 从正式模板/Compose 移除；管理员现有 `env.production` 需一次性改为 `AIMA_HOST_ROOT`。这是部署配置迁移，不是数据 Migration。
- 数据迁移：无。只要 `AIMA_HOST_ROOT` 指向现有 `/data/AIMA_UGC`，服务器实际四类持久路径保持完全相同。
- 本地新路径：`.runtime/compose/...` 是新的 Compose 隔离运行根，不复用源码 launcher 的 `.runtime/data` / Secret 目录，避免两种运行方式争用同一 PostgreSQL/Secret 生命周期。
- 部署：Internal V1 使用同一 Compose 命令；未来 Production Release 继续使用已加载不可变镜像 + `--no-build --pull never`。
- 回滚：若配置收敛出现问题，可恢复旧 Compose/env 模板并把同一四类现有目录重新映射；数据库和 Artifact 内容不需要回滚。

# 安全与运维风险

- 服务器若误把 `AIMA_HOST_ROOT` 指向 Release 版本目录，会重新绑定持久数据生命周期；文档和 CI 必须明确禁止。
- 相对 Host Root 只用于本地容器 Runtime；生产仍推荐绝对 `/data/AIMA_UGC`。
- Windows Docker Desktop 的宿主 bind 权限语义不同于 Linux；本 Change 的永久真实 Compose Golden Path 以 Linux 为证明边界，Windows 原生宿主文件系统若出现 UID/GID 权限问题需要单独事实验证，不伪造已覆盖结论。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地也可使用 Docker Compose，且不需要维护另一套 Compose/频繁改配置 | user:local-compose-same-entrypoint | not_satisfied | 待实现单根配置与本地式 Golden Path |
| R2 | 源码开发与容器运行职责清楚，两个 env example 只按运行方式分工 | user:env-role-clarification | not_satisfied | 待同步模板与运行文档 |
| R3 | 正式服务器持久数据与 Release/镜像生命周期分离，升级回滚不丢数据 | `docs/appendix/生产部署与离线Release方案.md` | not_satisfied | 待保持 `/data/AIMA_UGC` 布局并同步文档/CI |
| R4 | Internal V1-B 继续复用 V1-A 同一 Compose 入口，不重新造部署栈 | `docs/roadmap/生产上线实施路线.md` | not_satisfied | 待保持 Compose 拓扑并更新配置说明 |
| R5 | Secret、PostgreSQL 密码恢复和端口边界不因本次配置收敛降低 | `docs/blueprint/05-日志安全部署与运维.md` | not_satisfied | 待由 Compose Golden Path 回归证明 |
| R6 | L3 变更执行 Completion Audit、两阶段 Review、Ready Check 与永久 CI | `AGENTS.md` | not_satisfied | 待完成治理闭环 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面、用户业务交互或 HTTP Contract |
| Backend/API/PostgreSQL Integration | required | Compose Golden Path 真实 PostgreSQL、Migration、API readiness、持久化与 Secret 恢复回归 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client；由总 CI drift 检查确认无意外变化 |
| Real Full-stack Golden Path | required | Internal V1-A 真实 Compose 启动；生产式绝对 root 保持，新增仓库相对 root 启动/解析证据 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部接口，不需要产生付费请求 |
| Docs / Governance / Other | required | Compose config、Change Completion Gate、部署/Blueprint/Roadmap/Release 文档一致性 |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

1. [ ] 收敛 `compose.yaml` / `env.production.example` 到 `AIMA_HOST_ROOT`。
2. [ ] 调整 Internal V1-A CI，保留绝对 production root 并增加相对 local root 证据。
3. [ ] 同步运行、Blueprint、Roadmap 与 Production Release 文档。
4. [ ] 完成目标测试/永久 CI，处理真实回归。
5. [ ] 重新读取上游要求并完成 Completion Audit、Requirement Review、Code Quality Review。
6. [ ] 更新 Change 为 `ready_for_review`，运行 Ready Gate，正常 PR 合并；随后独立归档 Change。

# 验证计划

- `docker compose --env-file <production-env> config`
- `docker compose --env-file <local-relative-env> config`
- Internal V1-A Compose Golden Path：真实 build / bootstrap / PostgreSQL / migrate / configure / API / worker / scheduler / frontend / persistence / Secret fail-closed + restore。
- 新增本地式相对 Host Root 的无二次 Compose 文件验证。
- 仓库永久 CI / Change Completion Gate。

# 两阶段 Review

## Requirement Review

待 Ready 前执行。

## Code Quality Review

待 Requirement Review 通过后执行。

# Git / 交付

- branch: `feature/compose-host-root`
- implementation PR: 待创建
- archive PR: 实现合并后独立创建
