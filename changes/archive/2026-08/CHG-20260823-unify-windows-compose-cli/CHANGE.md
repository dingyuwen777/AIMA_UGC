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

Windows Docker Desktop 本地完整容器 Runtime 不再维护 CMD / PowerShell wrapper，统一直接使用标准 Docker Compose CLI，同时继续叠加 canonical `compose.yaml` 与 storage-only `compose.windows.yaml`。

正式启动：

```text
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

日常停止并保留 named-volume 数据：

```text
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down
```

首次机器若不存在 `env.production`，显式从 `env.production.example` 复制一次并编辑。

# 可观察成功标准

- [x] 删除 `scripts/dev/compose_windows.cmd` 与 `scripts/dev/compose_windows.ps1`。
- [x] Windows CMD / PowerShell 只保留标准 Compose CLI 作为完整容器正式入口。
- [x] 文档补齐 `up`、`down`、`ps`、`logs`、`down -v --remove-orphans --rmi all`。
- [x] 普通 `down` 保留 Windows named volumes；`down -v` 明确为破坏性重置。
- [x] 首次 `env.production` 初始化改为显式复制 example。
- [x] Windows CI 直接验证 CMD / PowerShell Compose CLI，并继续验证完整 named-volume Runtime。
- [x] Roadmap / Blueprint / Guide / 环境文档不再把 wrapper 写成当前机器事实。
- [x] Linux/WSL/公司服务器 canonical Compose、Production Release、Secret、PostgreSQL、Migration、端口、持久化语义保持不变。
- [x] PR #179 正常合并到 `main`。

# 范围与非目标

范围：删除 Windows Compose wrapper；统一 Windows 启动、停止、查看、日志、重置命令；同步 CI 与直接相关文档。

非目标：不删除 `compose.windows.yaml`；不改 Windows named-volume storage；不改 Linux/WSL/服务器 `AIMA_HOST_ROOT`；不改 Dockerfile、镜像/依赖版本、Schema、Migration、HTTP Contract 或业务 Runtime；不提前实现完整 Stage 11 Production Release。

# 必须保持不变

1. Windows 仍运行 `compose.yaml + compose.windows.yaml`，业务服务定义只来自 canonical `compose.yaml`。
2. Windows PostgreSQL/Artifact/log/internal Secret 继续使用 Docker-managed named volumes。
3. 普通 `down` 不删除 named volumes；只有显式 `down -v` 才破坏性删除。
4. Linux/WSL/服务器继续使用 canonical `compose.yaml` 与 `AIMA_HOST_ROOT` bind mounts。
5. `env.production` 继续是完整 Docker Runtime 的敏感配置文件。
6. Production Server 最终继续使用不可变镜像 + `--no-build --pull never`。

# 已确认关键决策

1. 用户明确要求 Windows 本地完整 Docker Runtime 不再使用两个 wrapper，直接执行标准 Docker Compose CLI。
2. 用户要求补充标准停止命令，并允许删除无用脚本。
3. 原 wrapper 只负责 `env.production` 复制、默认参数与转发，没有额外 Runtime/安全/存储逻辑。
4. `compose.windows.yaml` 继续保留，因为它承载 Windows named-volume storage 适配。

# L3 方案比较

- 方案 A：继续两个 wrapper。命令短，但增加维护层和文档/CI 双口径；不采用。
- 方案 B：保留一个跨平台 wrapper。仍是无业务价值的转发层；不采用。
- 方案 C：直接使用标准 Compose CLI。最少机制、最接近真实运行事实；采用。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无变化。
- Windows 启动接口：两个旧 wrapper 被明确删除，不保留长期兼容别名。
- 数据兼容：普通 `down` 保留已有 named volumes，因此原 Windows PostgreSQL/Artifact/Secret 可继续使用。
- Linux/服务器命令：无变化。
- 回滚：恢复两个 wrapper 和旧 CI/文档即可；不涉及数据迁移。

# 安全、性能与运维风险

- 删除 wrapper 未放宽 Secret 权限、端口或持久化门禁。
- 标准命令必须从仓库根执行，以明确相对 Compose 文件路径。
- `down -v` 继续明确为破坏性操作。
- `env.production` 继续 Git ignore，可能包含外部 API Key，不得提交 Git。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Windows 本地 Compose 统一为标准启动命令 | user:windows-compose-cli | satisfied | 两个 wrapper 删除；Windows Runner final run `32644737900` 的 CMD/PowerShell direct Compose CLI 均 success |
| R2 | 增加本地 Compose 停止命令 | user:windows-compose-stop | satisfied | 环境文档、Guide 03/04、env example 固化标准 `down` 与数据保留语义 |
| R3 | 删除无用 CMD / PowerShell wrapper | user:remove-wrappers | satisfied | PR #179 删除两个脚本；最终实现已合并 |
| R4 | 保持 Windows named-volume 与 Linux/Production 部署规范 | docs/roadmap/02_生产上线实施路线.md | satisfied | Windows final run `32644737900`、Internal V1-A final run `32644737868` success；`compose.yaml` / `compose.windows.yaml` 未修改 |
| R5 | L3 Completion Audit、Review、Ready/CI、合并与归档 | AGENTS.md | satisfied | Final Ready HEAD `688d28b6af516bbe9466c76958d10849eb8097c1` 的 11 个永久工作流全部 success；PR #179 merge `be31e05c6e9136e98f5651dc46446f1e77806bfa`；本归档 PR继续作为最后门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改业务页面或用户业务行为 |
| Backend/API/PostgreSQL Integration | required | Windows named-volume Runtime `32644737900`、Internal V1-A `32644737868` success，覆盖 PostgreSQL、Migration、Readiness、Secret、persistence |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；总 CI `32644737889` success |
| Real Full-stack Golden Path | required | Stage 8F `32644737881` success；Windows merged Runtime 与 Linux canonical Runtime 均通过 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider |
| Docs / Governance / Other | required | Completion Gate `32644737858` success；Windows Runner 直接 CLI success；当前事实文档已同步 |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取用户要求、`AGENTS.md`、RVC Skill、Blueprint README/07、Roadmap 与 verification-review；实现合并后又重新读取最新 `main` 的 `AGENTS.md` 进入归档。
- [x] change_coverage: R1-R5 覆盖直接启动、停止命令、wrapper 删除、Windows/Linux/Production 不变量和 L3 交付，无遗漏。
- [x] reverse_audit: 已核对 `scripts/dev/` 无两个 wrapper；当前环境文档/Blueprint/Guide/Roadmap 均直接使用 Compose CLI；`compose.yaml` / `compose.windows.yaml` 无 diff，named-volume、Secret、端口和 Production Release 语义保持。
- [x] unresolved_cleared: R1-R5 无 `not_satisfied`；适用验证层都有 final Ready HEAD 新鲜证据。

# 两阶段 Review

## Requirement Review A1：上游要求 → Change

通过。用户的直接 CLI、停止命令、删除 wrapper 与仓库的 Windows storage / Linux Production 边界均已进入 Change，没有 requirement omission。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。两个 wrapper 物理删除；首次配置、启动、停止、查看、日志、重置全部改为标准 Compose CLI；Windows CMD/PowerShell 和 named-volume Runtime、Internal V1-A、总 CI、Stage 8F 均在 Final Ready HEAD 通过；相关当前事实文档同步完成。

## Code Quality Review

通过，无 Serious/Important finding。删除的是纯转发层；没有依赖升级、Schema/Contract/Migration/Secret/端口/业务行为变化，也没有新兼容层或第二套 Compose Runtime。

# 最终验证证据

Final Ready HEAD: `688d28b6af516bbe9466c76958d10849eb8097c1`

- Change Completion Gate `32644737858`: success
- Windows Docker Desktop Compose Compatibility `32644737900`: success
- Internal V1-A Deployable Stack `32644737868`: success
- CI `32644737889`: success
- Stage 8F Full-stack Acceptance `32644737881`: success
- Stage 6 / Stage 7 / Local Dev：同一 HEAD 全部 success

# Git / 交付

- Implementation PR: #179
- Implementation Ready HEAD: `688d28b6af516bbe9466c76958d10849eb8097c1`
- Implementation merge SHA: `be31e05c6e9136e98f5651dc46446f1e77806bfa`
- Archive branch: `archive/unify-windows-compose-cli`
- Archive PR: 创建后记录
