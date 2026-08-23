---
schema: rvc-change/v1
id: CHG-20260823-unify-windows-compose-cli
title: Windows Docker Compose 标准命令统一
level: L3
status: done
owner: chatgpt
branch: archive/unify-windows-compose-cli
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - local-development
  - windows-docker-desktop
  - documentation
  - ci
affected_paths:
  - scripts/dev/compose_windows.cmd
  - scripts/dev/compose_windows.ps1
  - .github/workflows/compose-windows-desktop.yml
  - env.production.example
  - docs/02_环境运行与部署.md
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/guides/04_Docker国内构建源与本地重置.md
  - docs/blueprint/05_日志安全部署与运维.md
  - docs/roadmap/02_生产上线实施路线.md
contracts: []
data_changes: []
---

# 目标

Windows Docker Desktop 本地完整容器 Runtime 不再维护 CMD / PowerShell wrapper。管理员与开发者直接使用标准 Docker Compose CLI，继续叠加 canonical `compose.yaml` 与 storage-only `compose.windows.yaml`。

正式 Windows 启动命令：

```text
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

日常停止并删除容器/网络但保留 named-volume 数据：

```text
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down
```

首次机器若不存在 `env.production`，由用户显式从 `env.production.example` 复制一次并编辑。

# 可观察成功标准

- [x] 删除 `scripts/dev/compose_windows.cmd` 与 `scripts/dev/compose_windows.ps1`。
- [x] Windows CMD / PowerShell 的正式完整容器启动入口只保留标准 Compose CLI。
- [x] 文档补齐普通停止 `down`、查看 `ps`、日志 `logs`、破坏性重置 `down -v --remove-orphans --rmi all` 的标准 Compose 命令。
- [x] `down` 明确保留 Windows Docker named volumes；`down -v` 明确删除 PostgreSQL/Artifact/log/internal Secret。
- [x] 首次 `env.production` 初始化改为显式复制 example，不依赖 wrapper 自动创建。
- [x] Windows 永久 CI 不再测试 wrapper，而是在 Windows Runner 上直接验证 Compose CLI，并继续通过 Linux Docker Engine 验证完整 named-volume Runtime。
- [x] Roadmap / Blueprint / Guide / 环境文档不再把已删除 wrapper 写成当前机器事实。
- [x] Linux/WSL/公司服务器 canonical Compose、Production Release、Secret、PostgreSQL、Migration、端口、持久化语义不变。
- [x] PR #179 经 Final Ready HEAD 全量永久 CI 后正常合并到 `main`。

# 范围

- 删除 Windows Compose wrapper。
- 统一 Windows Docker Desktop 启动/停止/查看/日志/重置命令。
- 更新 Windows Compose CI 与直接相关正式文档。

# 非目标

- 不删除 `compose.windows.yaml`；它仍是 Windows Docker Desktop 的必要 storage-only override。
- 不把 Windows named volumes 改回 NTFS bind mount。
- 不改变 Linux/WSL/服务器 `AIMA_HOST_ROOT` 模型。
- 不修改 Dockerfile、镜像版本、国内镜像源、依赖版本、Schema、Migration、HTTP Contract 或业务 Runtime。
- 不实现完整 Stage 11 不可变 Production Release。

# 必须保持不变

1. Windows 仍运行 `compose.yaml + compose.windows.yaml`，业务服务定义只来自 canonical `compose.yaml`。
2. Windows PostgreSQL/Artifact/log/internal Secret 继续使用 Docker-managed named volumes。
3. 普通 `down` 不删除 named volumes；只有显式 `down -v` 才是破坏性重置。
4. Linux/WSL/服务器仍使用 canonical `compose.yaml` 与 `AIMA_HOST_ROOT` bind mounts。
5. `env.production` 继续是完整 Docker Runtime 的唯一敏感配置文件。
6. Production Server 最终仍使用不可变镜像 + `--no-build --pull never`，本地命令简化不改变上线设计。

# 已确认关键决策

1. 用户明确要求 Windows 本地完整 Docker Runtime 不再使用 `scripts/dev/compose_windows.cmd` / `.ps1`，统一直接执行标准 Docker Compose 命令。
2. 用户要求补充本地 Docker Compose 停止命令，并允许删除无用 wrapper。
3. 仓库原两个 wrapper 只做 `env.production` 自动复制、默认参数和参数转发，没有额外 Runtime/安全/存储逻辑，因此删除不会丢失容器能力。
4. Windows 仍保留 `compose.windows.yaml`，因为它承载 Docker named-volume storage 适配，而不是启动器包装逻辑。

# L3 方案比较

## 方案 A：继续保留 CMD / PowerShell wrapper

优点：首次可自动复制 `env.production`，命令短。缺点：维护两套额外入口、CI 需要验证参数转发、文档同时存在 wrapper 与真实 Compose 命令，容易形成多套心智模型。

结论：不采用。

## 方案 B：只保留一个跨平台 wrapper

可以减少一个脚本，但仍多维护一层无业务价值的命令转发，并不能比标准 Compose CLI 提供新的安全或兼容能力。

结论：不采用。

## 方案 C：直接使用标准 Docker Compose CLI（采用）

Windows、文档与 CI 直接表达真实运行命令；只保留真正必要的 `compose.windows.yaml` storage override。首次配置通过显式复制 `env.production.example` 完成。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无变化。
- Windows 命令兼容：删除两个旧 wrapper 是显式启动接口清理；文档与 CI 同步切换到标准 CLI，不保留长期兼容别名。
- 数据兼容：普通 `down` 保留现有 named volumes，因此已有 Windows PostgreSQL/Artifact/Secret 可继续使用。
- 部署：Windows 从仓库根执行标准 Compose 命令；Linux/服务器命令不变。
- 回滚：恢复两个 wrapper 与旧文档/CI 即可；数据和数据库不需要迁移或回滚。

# 安全、性能与运维风险

- 删除 wrapper 未放宽 Linux/Windows Secret 权限、端口或持久化门禁。
- 用户必须从仓库根执行命令，确保相对 Compose 文件路径明确。
- `down -v` 仍是破坏性操作，正式文档已与普通 `down` 明确区分。
- `env.production` 可能含外部 API Key，继续 Git ignore；显式复制 example 后仍需人工填写敏感值，不能提交 Git。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Windows 本地 Compose 统一为一条标准启动命令 | user:windows-compose-cli | satisfied | 两个 wrapper 已删除；当前正式文档与 env template 统一为直接 Compose CLI；Final Ready Windows run `32644737900` 的 CMD/PowerShell direct Compose CLI job success |
| R2 | 增加明确的本地 Compose 停止命令 | user:windows-compose-stop | satisfied | `docs/02_环境运行与部署.md`、Guide 03/04、`env.production.example` 固化标准 `down`，并明确 named-volume 保留语义 |
| R3 | 删除无用 CMD / PowerShell wrapper | user:remove-wrappers | satisfied | `scripts/dev/` 已无两个 wrapper；PR #179 diff 两文件 removed，已合并到 main |
| R4 | 保持 Windows named-volume 与 Linux/Production 部署规范 | docs/roadmap/02_生产上线实施路线.md | satisfied | Final Ready Windows Runtime `32644737900` success；Internal V1-A `32644737868` success；`compose.yaml` / `compose.windows.yaml` 未修改 |
| R5 | L3 Completion Audit、Review、Ready/CI 门禁 | AGENTS.md | satisfied | Final Ready HEAD `688d28b6af516bbe9466c76958d10849eb8097c1` 的 11 个永久工作流全部 success；PR #179 merge `be31e05c6e9136e98f5651dc46446f1e77806bfa`；本归档 PR 继续作为最后门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改业务页面或用户业务行为 |
| Backend/API/PostgreSQL Integration | required | Final Ready Windows Runtime `32644737900` 与 Internal V1-A `32644737868` success，覆盖 PostgreSQL、Migration、Readiness、Secret、persistence |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；总 CI `32644737889` success |
| Real Full-stack Golden Path | required | Stage 8F `32644737881` success；Windows merged Runtime 与 Linux canonical Runtime 均通过 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 行为或外部字段 |
| Docs / Governance / Other | required | Windows direct CLI `32644737900` success；Completion Gate `32644737858` success；当前机器事实文档已同步 |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取本轮用户要求、`AGENTS.md`、RVC Skill、Blueprint README/07、Roadmap 与 verification-review；实现合并后再次读取最新 main 的 AGENTS 进入归档。
- [x] change_coverage: R1-R5 覆盖直接启动、停止命令、wrapper 删除、Windows/Linux/Production 不变量和 L3 交付；未发现 requirement omission。
- [x] reverse_audit: `scripts/dev/` 无两个 wrapper；Roadmap 机器事实不再列出它们；环境文档/Blueprint/Guide 均直接使用 Compose CLI；`compose.yaml` / `compose.windows.yaml` 无 diff，named-volume、Secret、端口和 Production Release 语义保持。
- [x] unresolved_cleared: R1-R5 无 `not_satisfied`；Final Ready HEAD 全部永久 CI success。

# 两阶段 Review

## Requirement Review A1：上游要求 → Change

通过。用户要求的 wrapper 删除、统一 Windows 标准启动命令、普通停止命令、`compose.windows.yaml` 保留、Linux/Production 边界和 L3 门禁全部覆盖。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过：两个 wrapper 物理删除；env 首次复制改为显式一步；启动/down/stop/ps/logs/reset 全部直接使用标准 Compose CLI；Windows CMD/PowerShell direct CLI、named-volume Runtime、Linux Internal V1-A、总 CI、Stage 8F 全部通过；当前正式文档均已同步。

## Code Quality Review

通过，无 Serious/Important finding。删除的是纯参数转发/模板复制 wrapper；`compose.windows.yaml` 保持 storage-only；普通 `down` 与破坏性 `down -v` 分离；无依赖升级、Schema/Contract/Migration/Secret/端口/业务行为变化。

# 最终验证证据

Final Ready HEAD: `688d28b6af516bbe9466c76958d10849eb8097c1`

- Change Completion Gate `32644737858`: success
- Windows Docker Desktop Compose Compatibility `32644737900`: success
- Internal V1-A Deployable Stack `32644737868`: success
- CI `32644737889`: success
- Stage 8F Full-stack Acceptance `32644737881`: success
- Stage 6 / Stage 7 / Local Dev: 同一 HEAD 全部 success

# Git / 交付

- Implementation PR: #179
- Implementation Ready HEAD: `688d28b6af516bbe9466c76958d10849eb8097c1`
- Implementation merge SHA: `be31e05c6e9136e98f5651dc46446f1e77806bfa`
- Archive branch: `archive/unify-windows-compose-cli`
- Archive PR: 创建后记录
