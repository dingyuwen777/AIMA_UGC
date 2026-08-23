---
schema: rvc-change/v1
id: CHG-20260823-compose-host-root
title: 统一本地与服务器 Compose 宿主持久根目录配置
level: L3
status: ready_for_review
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
  - README.md
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

- [x] `env.local.example` 继续只服务源码开发，不与 Compose 配置混用。
- [x] `env.production.example` 继续作为完整容器 Runtime 配置模板，本地 Docker 与服务器 Docker 共用同一字段结构。
- [x] 四个宿主目录变量收敛为单一 `AIMA_HOST_ROOT`；Compose 从根目录推导 PostgreSQL、Artifact、日志和内部 Secret 路径。
- [x] 服务器推荐 `AIMA_HOST_ROOT=/data/AIMA_UGC`，持久状态继续位于 Release 目录之外。
- [x] 本地 Compose 可以将 `AIMA_HOST_ROOT=./.runtime/compose`，且 `.runtime/` 保持 Git ignore / Docker build context ignore。
- [x] Linux CI 同时验证生产式绝对 Host Root 与本地式仓库相对 Host Root 的 Compose 解析/真实启动。
- [x] 不修改数据库 Schema、Migration、公共 Contract、依赖或业务语义。
- [x] 正式文档同步源码开发、本地 Compose、服务器 Compose、未来不可变 Release 四种生命周期边界。
- [x] L3 Completion Audit 与两阶段 Review 已完成；Ready Check / 最终永久 CI 必须继续作为合并前硬门禁。

# 范围

- `compose.yaml` 的宿主 bind source 配置。
- `env.production.example` 的宿主持久化配置模型。
- Internal V1-A Compose Golden Path。
- 根 README、部署/环境/安全/Roadmap/Release 文档中的当前状态与配置说明。

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

- 服务器若误把 `AIMA_HOST_ROOT` 指向 Release 版本目录，会重新绑定持久数据生命周期；正式文档明确禁止这种配置。
- 相对 Host Root 只用于本地容器 Runtime；生产仍推荐绝对 `/data/AIMA_UGC`。
- Windows Docker Desktop 的宿主 bind 权限语义不同于 Linux；本 Change 的永久真实 Compose Golden Path 以 Linux/WSL 风格文件系统为证明边界，Windows 原生宿主文件系统若出现 UID/GID 权限问题需要单独事实验证，不伪造已覆盖结论，也不放宽服务器权限门禁。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地也可使用 Docker Compose，且不需要维护另一套 Compose/频繁改配置 | user:local-compose-same-entrypoint | satisfied | `compose.yaml` / `env.production.example` 单根化；Internal V1-A run `32631979589` 的 `Repository-relative host root smoke` 真实启动同一 Compose 并验证 readiness/persistence |
| R2 | 源码开发与容器运行职责清楚，两个 env example 只按运行方式分工 | user:env-role-clarification | satisfied | `env.production.example`、`docs/环境运行与部署.md`、README 已同步；`env.local.example` 未改且仍由 dev launcher 使用 |
| R3 | 正式服务器持久数据与 Release/镜像生命周期分离，升级回滚不丢数据 | `docs/appendix/生产部署与离线Release方案.md` | satisfied | 服务器 `AIMA_HOST_ROOT=/data/AIMA_UGC`，Release 继续位于 `/data/AIMA_UGC/releases/<version>`，两者明确不得等同；物理数据子路径不变 |
| R4 | Internal V1-B 继续复用 V1-A 同一 Compose 入口，不重新造部署栈 | `docs/roadmap/生产上线实施路线.md` | satisfied | Roadmap 保持 Internal V1-B 为下一单元，并固定同一 `env.production + compose.yaml`、服务器 Host Root `/data/AIMA_UGC` |
| R5 | Secret、PostgreSQL 密码恢复和端口边界不因本次配置收敛降低 | `docs/blueprint/05-日志安全部署与运维.md` | satisfied | Internal V1-A run `32631979589` 原完整 lifecycle smoke 通过：Secret 不泄露、非 root、端口边界、内部 Secret 幂等、已有 DB 丢密码 fail closed、恢复原 Secret 后可恢复 |
| R6 | L3 变更执行 Completion Audit、两阶段 Review、Ready Check 与永久 CI | `AGENTS.md` | satisfied | Completion Audit/两阶段 Review 已完成；pre-ready CI run `32631979667` 与永久专项均绿；本提交进入 `ready_for_review`，最终 Change Completion Gate/永久 CI 继续作为合并硬门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面、用户业务交互或 HTTP Contract |
| Backend/API/PostgreSQL Integration | required | Internal V1-A run `32631979589`：真实 PostgreSQL、Migration、API readiness、持久化、Secret fail-closed 与恢复全部成功；CI run `32631979667` Stage 2/3A 全绿 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client；CI run `32631979667` `Verify generated contracts and client` 成功 |
| Real Full-stack Golden Path | required | Internal V1-A run `32631979589`：绝对 production root 完整 lifecycle + 仓库相对 root 的同一 Compose startup/readiness/persistence 均成功；Stage 8F run `32631979638` 成功 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部接口；没有执行或产生真实付费请求 |
| Docs / Governance / Other | required | README、环境、Blueprint 05、Roadmap、Production Appendix 已同步；pre-ready CI run `32631979667` 成功；最终 Completion Gate 待 ready commit 复核 |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取目标分支 AGENTS、Roadmap、Blueprint 05 与 Production Release Appendix，并独立重建本轮完成定义。
- [x] change_coverage: 上游要求已逐项覆盖到 Change、Compose/env、专项 CI 和正式文档，没有发现 Requirement omission。
- [x] reverse_audit: 已反向核对 Host Root 到四类持久挂载、Secret/端口/密码恢复、Local/Server Runtime 与 Production Release 生命周期，Validation Matrix 证据层级匹配风险。
- [x] unresolved_cleared: R1-R6 无 not_satisfied；Windows 原生 NTFS bind 明确记录为未宣称支持的验证边界，不降低 Linux/服务器权限门禁。

## Completion Audit 证据

### upstream_re_read

Ready 前重新读取目标分支 `AGENTS.md`、当前 Roadmap Internal V1-A/V1-B/Stage 11、Blueprint 05 Secret/Compose 边界和 Production Release Appendix。重新得到的上游完成定义与本 Change 一致：同一 Compose Runtime、本地/服务器单一 Host Root、服务器持久数据与 Release 分离、Internal V1-B 仍是下一正式单元、完整 Production 仍要求不可变镜像/no-build/no-pull/恢复门禁。

### change_coverage

上游要求逐项映射到 `compose.yaml`、`env.production.example`、Internal V1-A workflow、README、环境文档、Blueprint 05、Roadmap 和 Production Appendix。没有 Schema/Migration/Contract/依赖变化，因此这些边界不制造额外改动。

### reverse_audit

- `compose.yaml` 的 PostgreSQL、Artifact、log、internal Secret 全部从同一个 `AIMA_HOST_ROOT` 推导，未留下第二套正式 Host Path 配置入口。
- 服务器 root `/data/AIMA_UGC` 推导出的四个物理路径与改动前完全一致，不移动现有数据。
- 本地 `.runtime/compose` 由 Git ignore / Docker build ignore 隔离，并由真实 Linux Compose smoke 证明。
- 原生产式 Golden Path 的 Secret、端口、non-root、密码恢复和重复启动断言保持且重新通过。
- Release 方向仍是 `/data/AIMA_UGC/releases/<version>` + 固定持久 Host Root；没有把本地便利性反向写成生产现场 build 规范。
- 本 Change 不涉及前后端公共行为，不存在需要补 Browser/Contract 反向接线的能力。

### unresolved_cleared

没有 `not_satisfied` Requirement。Windows Docker Desktop 原生 NTFS bind mount 没有被本轮 CI 证明，已明确记为平台验证边界，并给出 WSL2 Linux 文件系统路径；本轮没有宣称原生 NTFS 已正式支持，也没有为了它降低服务器权限门禁。

# 任务

1. [x] 收敛 `compose.yaml` / `env.production.example` 到 `AIMA_HOST_ROOT`。
2. [x] 调整 Internal V1-A CI，保留绝对 production root 并增加相对 local root 证据。
3. [x] 同步 README、运行、Blueprint、Roadmap 与 Production Release 文档。
4. [x] 完成目标测试/永久 CI并处理回归；pre-ready 实现 HEAD 除预期的 in-progress Completion Gate 外全部永久流程全绿。
5. [x] 重新读取上游要求并完成 Completion Audit、Requirement Review、Code Quality Review。
6. [ ] 最终 ready HEAD 的 Change Completion Gate / 永久 CI 全绿后，把 PR #170 转 Ready 并正常合并；随后独立归档 Change。

# 验证证据

pre-ready implementation HEAD `c3dccdcfd76b55125c5b1dff07496e78dabf3816`：

- Internal V1-A Deployable Stack #71 / run `32631979589`：success。
  - `Validate Compose topology without exposing Secret values`：success。
  - `One-command startup and lifecycle smoke`：success。
  - `Repository-relative host root smoke`：success。
- CI #2308 / run `32631979667`：success。
  - Stage 1：success。
  - Stage 2 Platform：success。
  - Stage 3A Database：success。
  - Windows bootstrap：success。
- Local Dev Bootstrap #131 / run `32631979647`：success。
- Stage 8F Full-stack Acceptance #435 / run `32631979638`：success。
- Stage 6 Xiaohongshu Vertical Slice #305 / run `32631979674`：success。
- Stage 7 Keyword Packs #1917 / run `32631979627`：success。
- Stage 7 Provider Config Routing #2030 / run `32631979658`：success。
- Stage 7 Scheduler Runtime #2257 / run `32631979654`：success。
- Stage 7 Plan Occurrence Run Snapshot #1915 / run `32631979604`：success。
- Change Completion Gate #154 / run `32631979610`：failure，原因是该 HEAD 的 Change 仍为 `in_progress`，属于进入 Ready 前的预期门禁结果，不作为实现失败。
- Ready commit `88a7d206a8172c5c676d4fb8bff1ff529318885a` 的 Change Completion Gate #155 / run `32632222589` 首次失败：Completion Audit 四项虽然勾选，但缺少机器 parser 要求的 `: 有效说明` 格式；语义 Audit 本身已完成。本提交只修正文档机器格式，必须重新触发并通过，不绕过 Gate。

# 两阶段 Review

## Requirement Review

结论：通过，无 Serious/Important 遗漏。

- A1 上游 → Change：用户确认的本地 Compose 简化诉求、两个 env 文件职责、服务器 Release/持久化要求、Roadmap V1-B 继承和 AGENTS L3 门禁均已进入 R1-R6。
- A2 Change → 实现：每个成功标准都有对应代码/CI/文档；没有把“本地相对目录”误扩张成“生产数据放版本目录”，也没有删除源码开发入口。
- 非目标保持：完整 Stage 11 Release/Backup/Auth 未提前伪实现。

## Code Quality Review

结论：通过，无 Serious/Important finding。

- `compose.yaml` 只做宿主 bind source 的单根收敛，服务拓扑、容器内路径、Secret grants、healthcheck、depends_on、端口和 restart 语义不变。
- 服务器默认仍为 `/data/AIMA_UGC`，因此标准现有物理路径不发生数据迁移。
- 新 CI 在原完整 lifecycle smoke 后复用相同镜像，以第二个隔离相对 Host Root 真启动系统，而不是只做字符串/Mock 验证。
- `.runtime` 已同时被 Git 与 Docker build context 排除；测试后清理隔离目录。
- 未升级依赖、未改 Migration、未改公共 Contract、未执行真实 Provider 付费调用。
- 旧四变量属于一次性部署配置迁移，Change/文档已明确；回滚只需恢复映射，不涉及业务数据 rollback。

# Git / 交付

- branch: `feature/compose-host-root`
- implementation PR: `#170 统一 Docker Compose 宿主持久根目录`（当前 Draft；最终 Ready Gate 通过后转 Ready）
- archive PR: 实现合并后独立创建
