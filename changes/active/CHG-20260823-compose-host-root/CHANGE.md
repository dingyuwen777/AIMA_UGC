---
schema: rvc-change/v1
id: CHG-20260823-compose-host-root
title: 统一本地与服务器 Compose 宿主持久根目录配置
level: L3
status: in_progress
owner: chatgpt
branch: feature/compose-windows-desktop
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - docker-compose
  - local-development
  - windows-docker-desktop
  - production-release
  - ci
affected_paths:
  - compose.yaml
  - compose.windows.yaml
  - env.production.example
  - scripts/dev/compose_windows.cmd
  - scripts/dev/compose_windows.ps1
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

让 AIMA_UGC 的完整 Docker Runtime 在 Linux/WSL、公司 Linux 服务器和 Windows Docker Desktop 上都有明确、稳定的启动路径，同时保持一个 canonical `compose.yaml`、一个 `env.production` 配置体系，以及完整 Production 的不可变镜像、独立持久数据、升级/回滚和恢复边界。

本 Change 第一阶段已经通过 PR #170 合并 `AIMA_HOST_ROOT` 单根配置；本轮用户进一步要求 Windows 可以直接从 CMD / PowerShell 启动，因此 Change 在归档前回到 `in_progress`，继续补齐 Windows Docker Desktop 原生宿主场景。

# 可观察成功标准

- [x] `env.local.example` 继续只服务源码开发，不与 Compose Runtime 配置混用。
- [x] Linux/WSL/服务器 canonical `compose.yaml` 继续从单一 `AIMA_HOST_ROOT` 推导 PostgreSQL、Artifact、日志和内部 Secret bind 路径。
- [x] 服务器继续推荐 `AIMA_HOST_ROOT=/data/AIMA_UGC`，持久状态位于 Release 目录之外。
- [ ] Windows Docker Desktop 原生 Windows 文件系统不直接承载 PostgreSQL/内部 Secret bind mount；使用 Docker-managed named volumes，避免 NTFS 权限语义影响数据库与 Secret。
- [ ] Windows storage override 只覆盖 volume source，不复制业务服务 command、environment、depends_on、healthcheck、network、Secret 分类或端口规则。
- [ ] Windows CMD 与 PowerShell 都提供一条稳定启动入口，复用同一个 `env.production`，不要求开发者手工切换多套业务配置。
- [ ] Windows 兼容不通过放宽 Linux/Production `chown/chmod`、Secret mode、non-root 或 PostgreSQL 密码恢复门禁实现。
- [ ] 永久 CI 验证 canonical Linux bind-mount Golden Path、仓库相对 bind root、Windows named-volume merged Compose、named-volume 重启持久化，以及 Windows launcher 参数。
- [x] 不修改数据库 Schema、Migration、公共 Contract、依赖或业务语义。
- [ ] 正式文档同步源码开发、Linux/WSL Compose、Windows Docker Desktop Compose、公司服务器、未来不可变 Release 五类运行边界。
- [ ] 重新执行 Completion Audit、两阶段 Review、Ready Check 与最终永久 CI 后再合并/归档。

# 范围

- 新增一个**仅存储层差异**的 Windows Compose override；canonical `compose.yaml` 仍是业务 Runtime 唯一基线。
- Windows CMD / PowerShell 启动包装器。
- Internal V1-A CI 对 merged Compose 与 named-volume 持久化的验证。
- `env.production.example` 和正式运行/部署/安全/Roadmap/Release 文档说明。

# 非目标

- 不把 Windows Docker Desktop 作为正式 Production Server 平台。
- 不删除 `env.local.example` 或源码开发 launcher。
- 不改变 Linux/服务器的 `AIMA_HOST_ROOT` bind-mount 生产布局。
- 不放宽 `scripts/deploy/prepare_host.py` 对 Linux UID/GID/mode、Secret、symlink 或数据库密码恢复的严格校验。
- 不在本 Change 实现完整 Stage 11 离线 Release、固定 digest、SBOM/签名、协调 Backup/Restore 或认证授权。
- 不改变 PostgreSQL 18.4、服务拓扑、Migration 顺序、Provider/LLM 行为。

# 必须保持不变

1. 服务器持久状态必须与应用 Release 生命周期解耦。
2. Linux Production 的 PostgreSQL、Artifact、log、internal secrets 继续位于 `AIMA_HOST_ROOT=/data/AIMA_UGC` 的固定子目录。
3. 外部 TikHub/LLM Key 继续由敏感 `env.production` 输入并转成 Compose Secret File；业务容器普通环境变量不含 Key 原值。
4. 已有 PostgreSQL 18 数据但 `postgres_password` 丢失时继续 fail closed。
5. 正式 Production 目标仍是服务器 `docker load` 已验证镜像后 `--no-build --pull never`；Windows 本地便利入口不能改变发布规范。
6. Windows 兼容不得通过 `chmod 777`、忽略 Secret mode 或把 PostgreSQL/Secret 放进容器可写层实现。

# 已确认关键决策

1. 保留 `env.local.example`：源码开发/热更新入口。
2. 保留 `env.production.example`：完整 Docker Runtime 的统一配置输入，本地与服务器继续共用业务配置字段。
3. Linux/WSL/服务器继续使用 canonical `compose.yaml + AIMA_HOST_ROOT` bind mounts。
4. Windows Docker Desktop 原生 Windows 文件系统场景使用 Docker-managed named volumes 保存 PostgreSQL、Artifact、log 和内部 Secret；不要求 NTFS 模拟 Linux owner/mode。
5. Windows 只增加 storage-only override；业务 Runtime 仍来自 canonical `compose.yaml`。
6. CMD/PowerShell 启动包装器负责自动组合 `compose.yaml + compose.windows.yaml`，开发者不需要记 `-f` 组合参数。
7. Windows named volumes 默认随 `docker compose down` 保留，只有显式 `down -v` 才销毁；文档必须把它标为破坏性重置。
8. Production Release 继续只使用 Linux canonical/production Compose 路线；Windows override 不成为服务器 Release 前置。

# L3 方案比较

## 方案 A：Windows NTFS bind mount + 放宽 bootstrap 权限校验

优点：看起来仍只有一个 Compose 文件。缺点：Docker Desktop 官方明确建议数据库等非代码数据使用 Docker volume；NTFS/文件共享层不能可靠表达 Linux UID/GID/mode，放宽 bootstrap 也不能保证 PostgreSQL 自身权限语义。会把本地兼容需求反向降低 Production 安全门禁。

结论：拒绝。

## 方案 B：强制 Windows 用户把仓库放进 WSL2 Linux 文件系统

优点：完全复用 canonical bind-mount 模型，权限与 Linux 一致。缺点：不能满足用户“从 Windows CMD / PowerShell 原生启动”的明确诉求，只能作为可选高性能开发路径。

结论：保留为可选路径，不作为唯一 Windows 方案。

## 方案 C：canonical Compose + Windows storage-only override + Docker named volumes（采用）

优点：

- canonical `compose.yaml` 的业务服务定义不分叉；
- Windows 使用 Docker VM 内 Linux filesystem 的 named volumes，适合 PostgreSQL/Secret；
- `prepare_host.py` 继续在 named volume 上执行原严格 Linux owner/mode，不需要 desktop 弱化模式；
- Linux/Production bind-mount 与 Release/Backup 设计完全不变；
- CMD/PowerShell 可用包装器隐藏 Compose 文件组合细节。

代价：仓库增加一个很薄的 Windows storage override，但它不是第二套业务 Compose；只覆盖同 target 的 volume source。

# 兼容、Migration、部署与回滚

- PR #170 已将四个 `AIMA_HOST_*_DIR` 收敛为 `AIMA_HOST_ROOT`，Linux/服务器配置迁移保持不变。
- Windows 新路径不迁移现有 Linux/WSL `.runtime/compose` bind 数据；Windows named volumes 是独立本地开发 Runtime。需要迁移本地开发数据时必须显式导出/导入，不静默复制数据库目录。
- Windows launcher 使用现有 `env.production` 的端口、TikHub、LLM、DB 名称等配置；storage override 只替换持久 mount source。
- Linux/服务器回滚：不受本轮影响，可继续恢复 PR #170 前/后的 canonical Compose 映射。
- Windows 回滚：停止 stack 后移除 Windows override/launcher 即可；named volumes 不会因普通 `down` 自动删除。

# 安全与运维风险

- Windows named volumes 由 Docker Desktop 管理，宿主文件系统上不再直接显示 PostgreSQL/Secret 文件；本地排障通过 Docker Desktop / `docker volume` / 容器日志和应用页面完成。
- `docker compose ... down -v` 会破坏性删除 Windows 本地数据库、Artifact、日志和内部 Secret；必须在文档明确警告。
- GitHub hosted Windows runner 不提供可依赖的 Linux Docker Desktop Runtime，因此永久 CI 可以在 Windows runner 验证 CMD/PowerShell launcher，在 Ubuntu Docker Engine 真实运行 merged Windows named-volume stack；不能把该组合证据夸大成“真实 Windows Docker Desktop 已运行”。首次真实 Windows Desktop 启动仍需开发机 smoke。
- Production Linux 权限与目录校验不因 Windows 支持降低。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地完整 Docker 与服务器保持同一 canonical Runtime / env 体系 | user:local-compose-same-entrypoint | satisfied | PR #170 merge `f04f6e8604bd15bc44c9e726da5325df9c54cd74` 已建立 `compose.yaml + env.production + AIMA_HOST_ROOT` |
| R2 | 源码开发和容器 Runtime 配置职责清楚 | user:env-role-clarification | satisfied | `env.local` 仍仅用于 dev launcher；`env.production` 用于 Compose Runtime |
| R3 | Windows 可以直接从 CMD / PowerShell 启动 Docker Compose Runtime | user:windows-cmd-powershell-compose | not_satisfied | 本轮新增 Windows storage override 与 CMD/PowerShell launcher 后补证据 |
| R4 | Windows 兼容不得牺牲 PostgreSQL/Secret 的 Linux 权限与安全语义 | `docs/blueprint/05-日志安全部署与运维.md` | not_satisfied | 采用 named volumes，不修改 `prepare_host.py` 严格权限逻辑；待 CI 证明 merged stack |
| R5 | 正式服务器持久数据与 Release/镜像生命周期分离 | `docs/appendix/生产部署与离线Release方案.md` | satisfied | Linux Production 继续 `AIMA_HOST_ROOT=/data/AIMA_UGC`，Release 位于 `/data/AIMA_UGC/releases/<version>` |
| R6 | Internal V1-B / Production 不重新造业务部署栈 | `docs/roadmap/生产上线实施路线.md` | satisfied | Windows 只加 local storage override；服务器仍复用 canonical Compose |
| R7 | L3 变更执行 Completion Audit、两阶段 Review、Ready Check 与永久 CI | `AGENTS.md` | not_satisfied | 本轮范围变化后必须重新完成审计与最终门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面、HTTP Contract 或用户业务行为 |
| Backend/API/PostgreSQL Integration | required | 真实 Docker Engine 启动 Windows merged named-volume stack，验证 PostgreSQL、Migration、API readiness、持久化、内部 Secret |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client；总 CI drift check 作为回归证据 |
| Real Full-stack Golden Path | required | canonical Linux bind Golden Path 保持；Windows merged named-volume stack完成 startup/readiness/restart-persistence |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部接口，不执行真实付费 Probe |
| Docs / Governance / Other | required | Windows CMD/PowerShell launcher 在 Windows runner 验证参数；运行/安全/Roadmap/Release 文档同步；Completion Gate |

# Completion Audit

- [ ] upstream_re_read: Windows scope 完成后重新读取用户要求、AGENTS、Docker/部署上游事实和正式 Roadmap。
- [ ] change_coverage: 比较 Windows CMD/PowerShell、storage 安全、canonical Production、文档与 CI 是否全部覆盖。
- [ ] reverse_audit: 反向检查每个 Windows mount target、launcher 参数、named-volume 生命周期与 Production 不变项。
- [ ] unresolved_cleared: R3/R4/R7 清零，实际未验证边界必须如实保留。

# 任务

1. [ ] 新增 `compose.windows.yaml`，只把四类持久 storage target 改为 Docker named volumes。
2. [ ] 新增 CMD / PowerShell Windows Compose launcher，复用同一个 `env.production`。
3. [ ] 扩展 Internal V1-A CI：验证 Compose merge、named-volume strict bootstrap、启动/readiness/重启持久化。
4. [ ] 增加 Windows runner 对 CMD/PowerShell launcher 命令参数的非破坏验证。
5. [ ] 同步 README、环境、Blueprint 05、Roadmap、Production Release 文档和 env example 注释。
6. [ ] 重新执行 Completion Audit、Requirement Review、Code Quality Review、Ready Gate 和全部永久 CI。
7. [ ] 正常 PR 合并后，将本 Change 标记 done 并通过独立归档 PR 归档。

# 验证计划

- Linux canonical：现有 Internal V1-A bind-mount lifecycle smoke 全部继续通过。
- Windows override model：`docker compose -f compose.yaml -f compose.windows.yaml --env-file <fixture> config --format json`，确认同 target volume 被替换为 `type: volume`。
- Windows named-volume Runtime：真实 `up --no-build --wait`、`/health/ready`、写入 Artifact marker、记录内部 Secret hash、`down` 后重启并验证数据/Secret 未丢。
- Windows launcher：Windows runner 使用 fake Docker CLI 捕获参数，分别执行 `.cmd` 与 `.ps1`，确认自动带 `-f compose.yaml -f compose.windows.yaml --env-file env.production`。
- 总 CI / Change Completion Gate。

# 两阶段 Review

## Requirement Review

本轮 Windows scope 完成后重新执行，不能复用 PR #170 的旧 Review 结论。

## Code Quality Review

Requirement Review 通过后重新执行，重点检查 Compose merge、volume 生命周期、Secret/DB 安全、Windows quoting、Production 不变项和破坏性 reset 文档。

# Git / 交付

- 第一阶段 implementation PR: #170，已合并，merge `f04f6e8604bd15bc44c9e726da5325df9c54cd74`。
- 当前 continuation branch: `feature/compose-windows-desktop`
- 当前 continuation PR: 待创建
- Change archive: Windows scope 合并完成后独立归档
