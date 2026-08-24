---
schema: rvc-change/v1
id: CHG-20260824-windows-host-root-runtime-files
title: Windows Docker Desktop 运行文件落到 AIMA_HOST_ROOT
level: L3
status: done
owner: aima
branch: docs/archive-windows-host-root-runtime-files
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - platform
  - documentation
affected_paths:
  - compose.windows.yaml
  - scripts/deploy/prepare_host.py
  - tests/unit/test_prepare_host.py
  - .github/workflows/compose-windows-desktop.yml
  - env.production.example
  - docs/02_环境运行与部署.md
  - docs/blueprint/05_日志安全部署与运维.md
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/roadmap/02_生产上线实施路线.md
contracts: []
data_changes: []
---

# 目标

Windows Docker Desktop 使用 `compose.yaml + compose.windows.yaml` 时，让 Artifact 与应用 `.log` 文件实际落到 `AIMA_HOST_ROOT` 可见目录；PostgreSQL 与 AIMA 内部 Secret 继续保存在 Docker-managed named volumes，保持 Linux 权限语义与数据库安全边界。

# 成功标准

- [x] Windows merged Compose 的 `/app/data` 与 `/app/logs` 使用 `${AIMA_HOST_ROOT}/runtime/data`、`${AIMA_HOST_ROOT}/runtime/logs` bind mount。
- [x] `bootstrap` 对 `/host/runtime/data`、`/host/runtime/logs` 使用同一 Host Root bind mount，Windows 文件共享不因严格 POSIX owner/mode 回读阻塞启动。
- [x] PostgreSQL 与内部 Secret 继续使用 `windows_postgres`、`windows_internal_secrets` named volume，并保持 Secret 严格权限校验。
- [x] 真实 Compose smoke 能写入 host-visible Artifact/日志目录，并在正常 `down` / 再次 `up` 后保持；数据库和内部 Secret 也保持。
- [x] Linux/WSL canonical `compose.yaml` 的现有 bind mount 与严格权限行为不变。
- [x] Windows 运行与 reset 文档准确说明：`down -v` 只删除 named volumes，不删除 `AIMA_HOST_ROOT` 下的 Artifact/日志文件。

# 范围与非目标

范围：Windows storage-only Compose override、bootstrap 对 Windows data/log bind mount 的最小权限兼容、Windows Compose 永久 CI，以及受影响的环境/部署/日志/Guide/Roadmap 文档。

非目标：不把 PostgreSQL 或内部 Secret bind 到 Windows NTFS；不修改 Linux/WSL/服务器 canonical Compose；不修改业务 API、Schema、Artifact Contract、日志格式/轮转；不新增依赖。

# 必须保持不变

- `AIMA_DATA_DIR=/app/data`、`AIMA_LOG_DIR=/app/logs` 容器内 Contract；
- Linux/WSL/服务器 canonical `compose.yaml` 与 `AIMA_HOST_ROOT` 全量 bind 语义；
- PostgreSQL 18、Migration、API/Worker/Scheduler/Frontend 拓扑与 Health/depends_on；
- 内部 Secret `root:11001 / 0440` 和 existing-secret fail-closed；
- 普通 `docker compose ... down` 保留持久状态。

# 关键决策

1. Windows 采用混合存储：Artifact/日志使用 `AIMA_HOST_ROOT` bind，PostgreSQL/内部 Secret 保持 named volume。
2. bind-compatible 权限模式只作用于 `runtime/data` 与 `runtime/logs`：结构与 symlink 检查仍保留；仅对 Windows bind 无法可靠表达的精确 UID/GID/mode 失败容忍。PostgreSQL 与 Secret 不进入例外。
3. Windows 继续复用 canonical Host Root 布局；`AIMA_HOST_ROOT=./.runtime` 时文件位于 `.runtime/runtime/data` 与 `.runtime/runtime/logs`。
4. `down -v` 只删除 PostgreSQL/内部 Secret named volumes；Host Root Artifact/日志需显式删除才会丢失。
5. 旧 `windows_runtime_data/windows_runtime_logs` 不自动迁移或删除，避免破坏用户已有本地数据。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Windows 本地 `AIMA_HOST_ROOT` 能直接看到 Runtime 文件 | user:2026-08-24-current-request | satisfied | Final Ready Windows run `32691310232`, hybrid job `97325365899`：真实 data/log Host Root bind、宿主 marker 与 `.log` 文件可见 |
| R2 | 应用日志仍作为 `.log` 写入正式 `AIMA_LOG_DIR` | docs/blueprint/05_日志安全部署与运维.md | satisfied | Final Ready Windows hybrid job `97325365899` 验证 `api.log` / `worker.log` / `scheduler.log` 位于 Host Root 并跨 down/up 保持 |
| R3 | PostgreSQL 与内部 Secret 保持安全的 Linux 存储/权限边界 | docs/blueprint/05_日志安全部署与运维.md | satisfied | Final Ready Windows hybrid job `97325365899` 验证 DB/Secret 为 volume、`postgres_password=0:11001:440`，DB marker 与 Secret hash 跨重启保持 |
| R4 | Windows 只适配宿主存储，不复制第二套业务 Runtime；Linux canonical 不变 | docs/02_环境运行与部署.md | satisfied | Windows CLI job `97325365824` 成功；Final Ready Internal V1-A run `32691310291`, job `97325365718` 通过 canonical Linux 绝对/相对 Host Root 生命周期 |
| R5 | Windows reset / persistence 文档与实际混合存储一致 | docs/guides/03_Windows Docker Desktop Compose运行.md | satisfied | Windows hybrid job `97325365899` 验证 `down -v` 后 bind data/log 保留；环境、Blueprint、Guide、Roadmap、env template 全部同步 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不改变页面或浏览器行为 |
| Backend/API/PostgreSQL Integration | required | Final Ready Windows `32691310232/97325365899` + Internal V1-A `32691310291/97325365718` |
| Contract / Generated Client | not_applicable | 无 Contract 变化；总 CI 仍验证 generated contract 未漂移 |
| Real Full-stack Golden Path | required | Windows hybrid job 真实启动 bootstrap → postgres → migrate → configure → api/worker/scheduler → frontend，并验证 readiness/mount/restart |
| Real Provider Probe | not_applicable | 不改变 TikHub/LLM Provider，无付费请求必要 |
| Docs / Governance / Other | required | TDD、总 CI、Windows CLI、Completion Gate、L3 Review 与文档同步 |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取用户决定、`AGENTS.md`、Skill、Blueprint README/05/07、环境文档、Roadmap、Windows Guide、Compose/bootstrap/tests/workflow。
- [x] change_coverage：覆盖 Host Root 可见性、权限边界、DB/Secret 隔离、持久化/reset、旧 volume 不自动迁移、Linux canonical 不变。
- [x] reverse_audit：Host Root ↔ bootstrap/backend mount、容器 `/app/data`/`/app/logs` ↔ 宿主路径、DB/Secret ↔ named-volume/权限全部有机器断言。
- [x] unresolved_cleared：R1–R5 全部 satisfied；required Validation Matrix 都有新鲜证据。

# TDD 与验证证据

## Red

Workflow run `32689906933`，Stage 1 job `97321617178`：Ruff/mypy 先通过，随后 `pytest tests/unit -q` 得到 `2 failed, 613 passed, 1 warning`。两个失败分别是旧实现缺少 `runtime_bind_compatible` 与 `strict_permissions`，证明测试因目标行为缺失而失败。

## Final Ready

Final Ready HEAD：`5ebd7f41835e4b172d0bd5258d2191b057c32924`。

11 个永久 workflow 全部 success：

- Change Completion Gate `32691310261`
- CI `32691310240`
- Windows Docker Desktop Compose Compatibility `32691310232`
- Internal V1-A `32691310291`
- Stage 8F `32691310352`
- Local Dev Bootstrap `32691310298`
- Stage 6 `32691310235`
- Stage 7 Plan Occurrence `32691310439`
- Stage 7 Keyword Packs `32691310494`
- Stage 7 Scheduler `32691310273`
- Stage 7 Provider Config `32691310297`

其中总 CI 的 Stage 1、Stage 2、Stage 3A、Windows bootstrap 全部 success；Windows hybrid 与 canonical Linux 两条真实容器路径全部 success。

# Review

## Requirement Review

通过。上游目标是“Windows 本地 `AIMA_HOST_ROOT` 真正能看到运行文件”，实现没有把该目标扩大为 PostgreSQL/Secret NTFS bind，也没有改变 Linux/服务器部署路线。Host Root 可见性、日志、持久化、reset 和旧 volume 迁移风险均已进入 Change 与正式文档。

## Code Quality / Security / Compatibility Review

通过，无 Serious/Important finding。`runtime_bind_compatible` 只允许 `runtime_only`，且白名单仅 `runtime/data`、`runtime/logs`；non-strict 路径仍执行 symlink/目录类型检查。Secret/PostgreSQL 不进入例外，真实 runtime 重新验证 Secret `0440`。无依赖、Schema、Migration、API、镜像版本变化；并行合入的 Docker mirror production probe 也在 Windows workflow 中完整保留。

# 文档影响

已同步：

- `env.production.example`
- `docs/02_环境运行与部署.md`
- `docs/blueprint/05_日志安全部署与运维.md`
- `docs/guides/03_Windows Docker Desktop Compose运行.md`
- `docs/roadmap/02_生产上线实施路线.md`

# 兼容、部署与回滚

- 无 Schema/Migration、API、依赖或镜像版本变化。
- Windows 旧 `windows_runtime_data/windows_runtime_logs` 不再挂载，新版本不自动迁移或删除旧内容。
- `down -v` 只删除 DB/内部 Secret named volume；Host Root Artifact/日志仍保留。
- Linux/WSL/服务器 canonical Compose 未改变并由 Final Ready Internal V1-A 再验证。
- 回滚只需恢复本 Change 的 Compose/bootstrap/CI/文档；已落到 Host Root 的文件不会自动删除。

# 验证边界

GitHub Hosted Windows Runner 真实验证 CMD/PowerShell Compose CLI，但不提供本仓库可依赖的 Docker Desktop Linux-container Runtime；mixed-storage 容器 Golden Path 在 Ubuntu Docker Engine 上验证 merged Compose。具体个人 Windows Docker Desktop 首次升级后仍应执行本机 smoke 并直接检查 `${AIMA_HOST_ROOT}/runtime/data`、`${AIMA_HOST_ROOT}/runtime/logs`。

# Git / 交付

- Implementation branch: `fix/windows-host-root-runtime-files`
- Implementation PR: #196
- Final Ready HEAD: `5ebd7f41835e4b172d0bd5258d2191b057c32924`
- Implementation merge commit: `cf5fd80e7301892ff23d2f883a9f281ff43c9557`
- Archive branch: `docs/archive-windows-host-root-runtime-files`
- PR #196 已按正常 merge 合入 `main`；本文件通过独立归档 PR 移入 `changes/archive/2026-08/`，归档 PR 自身必须通过永久 CI 后再合并。