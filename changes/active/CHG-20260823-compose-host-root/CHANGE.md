---
schema: rvc-change/v1
id: CHG-20260823-compose-host-root
title: 统一本地与服务器 Compose 宿主持久根目录配置
level: L3
status: ready_for_review
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
  - .github/workflows/compose-windows-desktop.yml
  - README.md
  - docs/环境运行与部署.md
  - docs/blueprint/05-日志安全部署与运维.md
  - docs/roadmap/生产上线实施路线.md
  - docs/appendix/生产部署与离线Release方案.md
  - docs/guides/Windows Docker Desktop Compose运行.md
contracts: []
data_changes: []
---

# 最终设计结论

本 Change 分两阶段完成同一个目标：

1. PR #170 已把 Linux / WSL / 公司服务器的四个 Host Path 收敛为单一 `AIMA_HOST_ROOT`；
2. PR #171 继续补齐 Windows Docker Desktop 原生 CMD / PowerShell 场景，但不放宽 Linux / Production 权限门禁。

当前运行模型：

```text
源码开发
→ env.local
→ backend.py / frontend.py

Linux / WSL 完整 Docker Runtime
→ env.production + canonical compose.yaml
→ AIMA_HOST_ROOT bind mounts

Windows Docker Desktop 原生
→ 同一个 env.production
→ canonical compose.yaml + compose.windows.yaml
→ Docker-managed named volumes

公司 Linux 服务器 / Production Runtime
→ env.production + canonical compose.yaml
→ AIMA_HOST_ROOT=/data/AIMA_UGC
```

`compose.windows.yaml` 只是 storage-only override，不复制业务 command、environment、depends_on、healthcheck、network、端口或外部 Secret 定义，因此没有形成第二套业务 Runtime。

# 可观察成功标准

- [x] `env.local.example` 继续只服务源码开发，不与 Compose Runtime 配置混用。
- [x] Linux/WSL/服务器 canonical `compose.yaml` 继续从单一 `AIMA_HOST_ROOT` 推导 PostgreSQL、Artifact、日志和内部 Secret bind 路径。
- [x] 服务器继续推荐 `AIMA_HOST_ROOT=/data/AIMA_UGC`，持久状态位于 Release 目录之外。
- [x] Windows Docker Desktop 原生模式不把 PostgreSQL/内部 Secret bind mount 到 NTFS；四类持久状态使用 Docker-managed named volumes。
- [x] Windows storage override 只替换持久 volume source，不分叉业务 Runtime 定义。
- [x] Windows CMD 与 PowerShell 都提供稳定启动入口，继续复用同一个 `env.production`。
- [x] Windows 兼容没有放宽 Linux/Production `chown/chmod`、Secret mode、non-root、端口或 PostgreSQL 密码恢复门禁。
- [x] 永久 CI 验证 canonical Linux bind Golden Path、仓库相对 bind root、Windows merged named-volume Runtime、严格 Secret mode、PostgreSQL/Migration/Readiness、重启持久化和 Windows launcher 参数。
- [x] 不修改数据库 Schema、Migration、公共 Contract、依赖或业务语义。
- [x] 正式文档同步源码开发、Linux/WSL Compose、Windows Docker Desktop、公司服务器和未来不可变 Release 的生命周期边界。
- [x] Completion Audit 与两阶段 Review 已完成；Ready HEAD 的永久 CI / Change Gate 继续作为合并硬门禁。

# 范围与非目标

范围：

- PR #170 的 `AIMA_HOST_ROOT` 单根 Linux bind 模型；
- Windows storage-only Compose override；
- Windows CMD / PowerShell wrapper；
- Linux 与 Windows storage model 的永久 CI；
- 环境、安全、Roadmap、Production Release 与 Windows Guide 文档。

非目标：

- 不把 Windows Docker Desktop 作为正式 Production Server 平台；
- 不删除 `env.local.example` 或源码开发 launcher；
- 不改变 Linux/服务器的 `/data/AIMA_UGC` bind-mount 生产布局；
- 不增加 desktop 弱权限模式，不修改 `prepare_host.py` 的严格 UID/GID/mode、symlink 和密码恢复规则；
- 不实现 Stage 11 的完整离线 Release、固定 digest、SBOM/签名、协调 Backup/Restore 或认证授权；
- 不改变 PostgreSQL 18.4、服务拓扑、Migration 顺序、Provider/LLM 行为。

# 必须保持不变

1. 服务器持久状态与应用 Release 生命周期解耦；`AIMA_HOST_ROOT=/data/AIMA_UGC` 不指向 `/data/AIMA_UGC/releases/<version>`。
2. Linux Production 的 PostgreSQL、Artifact、日志、内部 Secret 继续位于固定 Host Root 子目录。
3. 外部 TikHub/LLM Key 继续由敏感 `env.production` 输入 Compose Secret；业务容器普通环境变量不含 Key 原值。
4. 已有 PostgreSQL 18 数据但 `postgres_password` 丢失时继续 fail closed。
5. 完整 Production 仍要求已验证镜像 `docker load` 后以 `--no-build --pull never` 启动；Windows 本地便利入口不改变发布规范。
6. Windows 兼容不得通过 `chmod 777`、忽略 Secret mode、关闭安全校验或使用容器可写层持久数据库实现。

# L3 方案比较与决定

## 方案 A：NTFS bind mount + 放宽权限检查

拒绝。Windows/NTFS 文件共享层不能可靠承担 Linux PostgreSQL 与内部 Secret 的 UID/GID/mode 语义；放宽 bootstrap 会把本地兼容需求反向传导到 Production 安全边界。

## 方案 B：仅允许 WSL2 Linux 文件系统

可用但不足。它能完全复用 canonical bind 模型，但不能满足用户“直接从 Windows CMD / PowerShell 启动”的明确要求。

## 方案 C：canonical Compose + Windows storage-only override + Docker named volumes

采用。Windows 的 PostgreSQL、Artifact、日志和内部 Secret 使用 Docker-managed named volumes；`prepare_host.py` 仍在 Linux volume 上执行原严格 owner/mode 逻辑。CMD/PowerShell wrapper 隐藏多 Compose 文件参数，Linux/Production canonical 路线不变。

# 兼容、Migration、部署与回滚

- PR #170 配置迁移：旧 `AIMA_HOST_DATA_DIR/AIMA_HOST_LOG_DIR/AIMA_HOST_POSTGRES_DIR/AIMA_HOST_SECRET_DIR` 收敛为 `AIMA_HOST_ROOT`；不迁数据库内容。
- Linux/服务器：`AIMA_HOST_ROOT=/data/AIMA_UGC` 时实际持久路径与 PR #170 前保持一致。
- Linux/WSL 本地：可用 `AIMA_HOST_ROOT=./.runtime/compose`。
- Windows 原生：named volumes 是独立本地 Runtime，不静默迁移 Linux/WSL `.runtime/compose` 数据。
- 普通 Windows `down` 保留 named volumes；`down -v` 是显式破坏性本地重置。
- Linux/Production 回滚不依赖 Windows override；恢复旧应用 image/Compose 时仍映射同一服务器持久数据。
- 无 Schema/Alembic Migration、Contract 或依赖变化。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地完整 Docker 与服务器保持同一 canonical Runtime / env 体系 | user:local-compose-same-entrypoint | satisfied | PR #170 merge `f04f6e8604bd15bc44c9e726da5325df9c54cd74`；canonical `compose.yaml + env.production` 保持唯一业务基线 |
| R2 | 源码开发与容器 Runtime 配置职责清楚 | user:env-role-clarification | satisfied | `env.local` 仅给 dev launcher；`env.production` 给完整 Docker Runtime；环境文档已同步 |
| R3 | Windows 可以直接从 CMD / PowerShell 启动 Docker Runtime | user:windows-cmd-powershell-compose | satisfied | `compose_windows.cmd` / `.ps1`；Windows workflow run `32633482774` 两个 launcher 及参数断言全部 success |
| R4 | Windows 兼容不得牺牲 PostgreSQL/Secret 的 Linux权限与安全语义 | `docs/blueprint/05-日志安全部署与运维.md` | satisfied | `compose.windows.yaml` 使用 named volumes；未修改 `prepare_host.py`；run `32633482774` 验证 `postgres_password=0:11001:440`、PostgreSQL/Migration/Readiness/重启持久化 |
| R5 | 正式服务器持久数据与 Release/镜像生命周期分离 | `docs/appendix/生产部署与离线Release方案.md` | satisfied | Production 继续 `AIMA_HOST_ROOT=/data/AIMA_UGC`，Release 在 `/data/AIMA_UGC/releases/<version>`；Windows override 明确不得用于服务器 |
| R6 | Internal V1-B / Production 不重新造业务部署栈 | `docs/roadmap/生产上线实施路线.md` | satisfied | Internal V1-B 仍是公司 Linux 服务器 + canonical Compose；Windows 只加 local storage adapter |
| R7 | L3 变更执行 Completion Audit、两阶段 Review、Ready Check 与永久 CI | `AGENTS.md` | satisfied | 本节 Completion Audit / 两阶段 Review 已完成；实现 HEAD `df1ec9e...` 的全部永久工作流除预期 in_progress Change Gate 外均 success，Ready HEAD 继续由永久 Gate 约束合并 |

# Validation Matrix

| Layer | Result | Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面、HTTP Contract 或用户业务行为 |
| Backend/API/PostgreSQL Integration | passed | Windows workflow run `32633482774` 真实 Docker Engine merged named-volume stack：bootstrap/PostgreSQL/Migration/API readiness/DB+Artifact+Secret 重启持久化 success；CI `32633482793` Stage 2/3A success |
| Contract / Generated Client | not_applicable | 无 Pydantic/OpenAPI/generated client diff；CI `32633482793` generated drift / contract checks success |
| Real Full-stack Golden Path | passed | Internal V1-A run `32633482813` Linux absolute + repo-relative bind lifecycle success；Windows storage model run `32633482774` named-volume Runtime success |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部 API，不需要付费 Probe |
| Docs / Governance / Other | passed | Windows Runner launcher success；环境/Blueprint/Roadmap/Production Appendix/Windows Guide 已同步；Ready Change Gate 在最终 HEAD 继续作为合并门禁 |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取本轮 Windows CMD/PowerShell 用户要求、目标分支 `AGENTS.md`、Blueprint 05、Roadmap、Production Appendix、环境运行文档和当前实现。
- [x] change_coverage: 上游要求已覆盖 canonical Runtime、同一 env.production、Windows storage adapter、CMD/PowerShell、权限不降级、named-volume 生命周期、服务器 Release/Backup 边界、CI 和正式文档；未发现 requirement omission。
- [x] reverse_audit: 逐个反查 `/app/data`、`/app/logs`、`/run/internal-secrets`、`/var/lib/postgresql`、PostgreSQL `/run/secrets` 与 bootstrap `/host/**` target 均由 Windows override 替换为 volume；反查 CMD/PS 参数均叠加 canonical+Windows override；服务器文档明确不使用 Windows override。
- [x] unresolved_cleared: Requirement Traceability 无 `not_satisfied`；Browser/Contract/Provider 层的不适用均有边界依据；真实个人 Windows Docker Desktop 完整 stack 未在 hosted runner 执行的事实已在文档保留，不冒充已验证。

# 两阶段 Review

## Requirement Review A1：上游要求 → Change

通过，无遗漏。

- 用户要的是 Windows 可从 CMD / PowerShell 直接启动，而不是要求 Production 改成 Windows。
- 同一业务 Runtime / `env.production`、服务器独立持久数据、未来不可变镜像 Release 均继续保留。
- Windows storage 的独立宿主差异已经作为实现约束进入 Change，没有以“本地方便”为由降低 Secret/PostgreSQL 权限。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。

- `compose.windows.yaml` 只覆盖 storage source，merged config 机器断言保证对应 target 都是 named volume。
- CMD / PowerShell wrapper 真实在 Windows Runner 执行，默认参数和子命令透传均通过。
- merged Windows storage model 在真实 Docker Engine 运行并通过 Readiness、Secret mode、PostgreSQL/Artifact/Secret 重启持久化。
- canonical Linux Internal V1-A Golden Path 保持全绿。
- 环境、安全、Roadmap、Production Release 与 Windows Guide 对当前实现和未来上线边界一致。

## Code Quality Review

通过，无 Serious / Important finding。

- 未修改 `prepare_host.py`，没有 desktop 弱权限分支、`chmod 777`、跳过 Secret 校验或关闭 PostgreSQL 恢复门禁。
- Windows override 不复制业务 command/environment/health/network，降低长期漂移风险。
- named volume 普通 `down` 持久、`down -v` 破坏性语义有真实回归和明确文档。
- PowerShell 5.1 首轮 UTF-8 no-BOM 解析失败已按根因修正为 ASCII-compatible 脚本；最新 Windows Runner 通过。
- 无依赖、Schema、Migration、公共 Contract 或业务语义变化。

# 当前验证证据

实现稳定 HEAD：`df1ec9e69ddb17ac833c9f46c2ebf2cd827b83c7`

- Windows Docker Desktop Compose Compatibility run `32633482774`: success；CMD/PowerShell Launchers success；Named-volume Runtime Model success。
- Internal V1-A Deployable Stack run `32633482813`: success；Linux absolute/repo-relative bind Golden Path success。
- CI run `32633482793`: success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部 success。
- Local Dev Bootstrap run `32633482901`: success。
- Stage 8F run `32633482792`: success。
- Stage 6 run `32633482834`: success。
- Stage 7 Keyword Packs `32633482857`、Scheduler Runtime `32633482794`、Provider Config Routing `32633482769`、Plan Occurrence `32633482742`: 全部 success。
- Change Completion Gate run `32633482745`: failure，原因仅为实现 HEAD 时 Change 仍为 `in_progress`；这是预期门禁行为，不是代码回归。当前 Ready commit 将重新触发最终 Gate。

# 剩余验证边界

GitHub Hosted Windows Runner 实际证明了 CMD/PowerShell wrapper；真实 merged named-volume Runtime 由 Ubuntu Docker Engine 证明。Hosted Windows Runner 不提供本任务可依赖的 Docker Desktop Linux-container Runtime，因此本 Change **不声称**已经在某台真实个人 Windows Docker Desktop 上执行完整业务栈。

首次在具体 Windows 开发机使用时仍建议执行：

```powershell
.\scripts\dev\compose_windows.ps1
curl.exe -f http://127.0.0.1:8080/health/ready
```

若出现 Docker Desktop 特有问题，应以真实错误继续修复，不能通过降低 Linux/Production 门禁处理。

# Git / 交付

- 第一阶段 implementation PR: #170，已正常合并；merge `f04f6e8604bd15bc44c9e726da5325df9c54cd74`。
- continuation branch: `feature/compose-windows-desktop`
- continuation PR: #171 `增加 Windows Docker Desktop Compose 兼容`，当前 Draft，待最终 Ready HEAD 全部 CI 绿色后转 Ready 并正常合并。
- Change archive: PR #171 合并后标记 `done`，通过独立 Archive PR 移至 `changes/archive/2026-08/`。
