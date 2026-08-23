---
schema: rvc-change/v1
id: CHG-20260823-compose-host-root
title: 统一本地与服务器 Compose 宿主持久根目录配置
level: L3
status: done
owner: chatgpt
branch: archive/compose-host-root
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

# 最终结论

本 Change 已通过两个正常 PR 完成并进入归档：

1. PR #170 将 Linux / WSL / 公司服务器的四个宿主持久目录变量收敛为单一 `AIMA_HOST_ROOT`；
2. PR #171 在不降低 Linux / Production 权限门禁的前提下，补齐 Windows Docker Desktop 原生 CMD / PowerShell 完整容器启动，并使用 storage-only Compose override + Docker named volumes 适配 Windows 宿主存储语义。

最终运行模型：

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

`compose.windows.yaml` 只覆盖持久 storage source，不复制业务 command、environment、depends_on、healthcheck、network、端口或外部 Secret 定义，因此没有形成第二套业务 Runtime。

# 成功标准

- [x] `env.local.example` 继续只服务源码开发；`env.production.example` 服务完整 Docker Runtime。
- [x] canonical `compose.yaml` 使用单一 `AIMA_HOST_ROOT` 推导 Linux/WSL/服务器 PostgreSQL、Artifact、日志和内部 Secret bind 路径。
- [x] 公司服务器继续 `AIMA_HOST_ROOT=/data/AIMA_UGC`，持久状态与 `/data/AIMA_UGC/releases/<version>` 分离。
- [x] Windows Docker Desktop 原生模式使用 Docker-managed named volumes，不把 PostgreSQL/内部 Secret bind mount 到 NTFS。
- [x] Windows CMD 与 PowerShell 都可通过仓库 wrapper 启动并透传 Compose 子命令。
- [x] Windows 兼容没有修改 `prepare_host.py`，没有放宽 `chown/chmod`、Secret mode、non-root、端口或 PostgreSQL 密码恢复门禁。
- [x] Windows merged Runtime 验证严格 Secret mode、PostgreSQL/Migration/Readiness 和 `down` 后 PostgreSQL/Artifact/Secret 重启持久化。
- [x] Linux Internal V1-A absolute/repo-relative bind Golden Path 保持全绿。
- [x] 无数据库 Schema、Alembic Migration、公共 Contract、依赖或业务语义变化。
- [x] 环境、安全、Roadmap、Production Release 和 Windows Guide 已同步。
- [x] Completion Audit、两阶段 Review、Ready Check、全部永久 CI、PR 合并已完成。

# 已确认关键决策

1. 不把 Docker Compose 与 Production 画等号；`env.production` 是完整容器 Runtime 配置输入，本地和服务器共用业务配置字段。
2. Linux/WSL/公司服务器保持 canonical `compose.yaml + AIMA_HOST_ROOT`。
3. Windows Docker Desktop 原生使用 storage-only `compose.windows.yaml`，把 PostgreSQL、Artifact、日志、内部 Secret 适配为 Docker managed named volumes。
4. Windows 支持不得通过降低 Linux/Production 权限检查实现。
5. 普通 Windows `down` 保留 named volumes；`down -v` 是显式破坏性本地重置。
6. Production 服务器不使用 `compose.windows.yaml`，仍使用固定 `/data/AIMA_UGC` 持久根。
7. 完整 Production Release 仍要求已验证不可变镜像、`docker load`、`--no-build --pull never`、后续完整 Release/Backup/Restore/认证门禁。

# L3 方案比较

- **NTFS bind + 放宽权限检查：拒绝。** 会让本地兼容需求降低 PostgreSQL/Secret 的 Linux 安全语义。
- **只允许 WSL2：可选但不足。** 能复用 canonical bind model，但不满足直接 CMD / PowerShell 启动要求。
- **canonical Compose + Windows storage-only override + named volumes：采用。** 业务 Runtime 不分叉，Windows 存储适配与 Production Linux 边界清楚。

# 兼容、Migration、部署与回滚

- 配置迁移：PR #170 将四个旧 Host Path 环境变量一次性收敛为 `AIMA_HOST_ROOT`；这是部署配置迁移，不是数据 Migration。
- 数据迁移：无。Linux 服务器 `AIMA_HOST_ROOT=/data/AIMA_UGC` 时实际四类持久路径保持原位置。
- Windows named volumes 是独立本地 Runtime，不静默迁移 Linux/WSL `.runtime/compose` 数据。
- Linux/Production 回滚继续复用固定持久根，不依赖 Windows override。
- Windows override/launcher 可移除而不影响服务器；普通 `down` 不删本地 volume，`down -v` 明确为破坏性本地 reset。
- 无依赖升级、Schema/Migration/Contract 兼容动作。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地完整 Docker 与服务器保持同一 canonical Runtime / env 体系 | user:local-compose-same-entrypoint | satisfied | PR #170 merge `f04f6e8604bd15bc44c9e726da5325df9c54cd74`；canonical `compose.yaml + env.production` 为唯一业务基线 |
| R2 | 源码开发与容器 Runtime 配置职责清楚 | user:env-role-clarification | satisfied | `env.local` 仅供 dev launcher；`env.production` 供完整 Docker Runtime；正式环境文档已同步 |
| R3 | Windows 可以直接从 CMD / PowerShell 启动 Docker Runtime | user:windows-cmd-powershell-compose | satisfied | `compose_windows.cmd/.ps1`；Ready run `32633697741` Windows launcher job success |
| R4 | Windows 兼容不得牺牲 PostgreSQL/Secret 的 Linux 权限与安全语义 | `docs/blueprint/05_日志安全部署与运维.md` | satisfied | named-volume override；未修改 `prepare_host.py`；Ready run `32633697741` 验证 `postgres_password=0:11001:440`、PostgreSQL/Migration/Readiness/重启持久化 |
| R5 | 正式服务器持久数据与 Release/镜像生命周期分离 | `docs/appendix/11_生产部署与离线Release方案.md` | satisfied | Production 继续 `AIMA_HOST_ROOT=/data/AIMA_UGC`，Release 位于 `/data/AIMA_UGC/releases/<version>`；Windows override 不用于服务器 |
| R6 | Internal V1-B / Production 不重新造业务部署栈 | `docs/roadmap/02_生产上线实施路线.md` | satisfied | Internal V1-B 仍是公司 Linux 服务器 + canonical Compose；Windows 只是 local storage adapter |
| R7 | L3 变更执行 Completion Audit、两阶段 Review、Ready Check、永久 CI 和正常 PR 合并 | `AGENTS.md` | satisfied | Completion Gate `32633697727` 与全部 Ready HEAD 工作流 success；PR #171 正常 merge `09a3dd641a6da34b20d8b3a22fbfee561f7e3246` |

# Validation Matrix

| Layer | Result | Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面、HTTP Contract 或用户业务行为 |
| Backend/API/PostgreSQL Integration | passed | Windows Ready run `32633697741` 真实 Docker Engine merged stack；CI `32633697782` Stage 2/3A success |
| Contract / Generated Client | not_applicable | 无 Contract/generated diff；CI `32633697782` drift checks success |
| Real Full-stack Golden Path | passed | Internal V1-A `32633697792` Linux absolute/repo-relative bind lifecycle success；Windows `32633697741` named-volume Runtime success |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 外部 API，不需要付费 Probe |
| Docs / Governance / Other | passed | Completion Gate `32633697727`；Windows Runner wrapper；环境/Blueprint/Roadmap/Release/Guide 同步 |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取用户 Windows CMD/PowerShell 要求、目标分支 AGENTS、Blueprint 05、Roadmap、Production Appendix、环境运行文档和当前实现；实施合并后再次读取 main AGENTS 再执行归档。
- [x] change_coverage: canonical Runtime、同一 env.production、Windows storage adapter、CMD/PowerShell、权限不降级、named-volume 生命周期、服务器 Release/Backup 边界、CI 和正式文档均覆盖，未发现 requirement omission。
- [x] reverse_audit: Windows `/app/data`、`/app/logs`、`/run/internal-secrets`、`/var/lib/postgresql`、PostgreSQL `/run/secrets` 和 bootstrap `/host/**` 均由 override 替换为 volume；CMD/PS 都叠加 canonical + Windows override；服务器路径明确不使用 override。
- [x] unresolved_cleared: Traceability 无未满足项；不适用测试层有真实依据；Hosted Windows Runner 未执行真实个人 Docker Desktop 完整 stack 的边界已明确保留，没有夸大验证结论。

# 两阶段 Review

## Requirement Review

A1/A2 均通过，无遗漏。用户要求的 Windows CMD/PowerShell 原生启动、同一业务 Runtime、Production 不降级与未来上线边界均映射到实现、测试和文档。

## Code Quality Review

通过，无 Serious / Important finding。

- `compose.windows.yaml` 不复制业务 command/environment/health/network。
- `prepare_host.py` 未修改，没有 desktop 弱权限分支或 `chmod 777`。
- Windows named-volume `down`/`down -v` 生命周期有自动测试和文档。
- PowerShell 5.1 首轮编码解析问题按根因修复，Ready Windows Runner 成功。
- 无依赖、Schema、Migration、公共 Contract 或业务语义变化。

# 最终实现验证证据

Ready HEAD：`3d13d8cd4c0e366322c758a8b31ce9b7a4b4eb7e`

- Change Completion Gate run `32633697727`: success。
- Windows Docker Desktop Compose Compatibility run `32633697741`: success；CMD/PowerShell Launchers 与 Named-volume Runtime Model 均 success。
- Internal V1-A Deployable Stack run `32633697792`: success。
- CI run `32633697782`: success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部 success。
- Local Dev Bootstrap run `32633697726`: success。
- Stage 8F `32633697791`、Stage 6 `32633697730`、Stage 7 Keyword Packs `32633697753`、Scheduler `32633697760`、Provider Config `32633697736`、Plan Occurrence `32633697725`: 全部 success。

# 验证边界

GitHub Hosted Windows Runner 实际执行并证明 CMD/PowerShell wrapper；真实 merged named-volume Runtime 由 Ubuntu Docker Engine 证明。Hosted Windows Runner 不提供本任务可依赖的 Docker Desktop Linux-container Runtime，所以本 Change不声称已经在某台真实个人 Windows Docker Desktop 上执行完整业务栈。首次具体 Windows 开发机仍应做 `/health/ready` smoke；如发现 Desktop 特有问题，以实际错误继续修复，不降低 Linux/Production 门禁。

# Git / 交付

- PR #170：正常合并，merge `f04f6e8604bd15bc44c9e726da5325df9c54cd74`。
- PR #171：正常合并，merge `09a3dd641a6da34b20d8b3a22fbfee561f7e3246`。
- archive branch: `archive/compose-host-root`
- archive PR: 本文件所在独立归档 PR；其永久 CI 通过后正常合并并清理 Active Change。
