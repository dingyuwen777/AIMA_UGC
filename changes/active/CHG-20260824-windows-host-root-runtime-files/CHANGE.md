---
schema: rvc-change/v1
id: CHG-20260824-windows-host-root-runtime-files
title: Windows Docker Desktop 运行文件落到 AIMA_HOST_ROOT
level: L3
status: ready_for_review
owner: aima
branch: fix/windows-host-root-runtime-files
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
- [x] `bootstrap` 对应的 `/host/runtime/data`、`/host/runtime/logs` 使用同一 Host Root bind mount，且 Windows 文件共享不因严格 POSIX owner/mode 校验阻塞启动。
- [x] PostgreSQL 与内部 Secret 继续使用 `windows_postgres`、`windows_internal_secrets` named volume，并保持 Secret 严格权限校验。
- [x] 真实 Compose smoke 能写入 host-visible Artifact/日志目录，并在正常 `down` / 再次 `up` 后保持；数据库和内部 Secret 也保持。
- [x] Linux/WSL canonical `compose.yaml` 的现有 bind mount 与严格权限行为不变。
- [x] Windows 运行与 reset 文档准确说明：`down -v` 只删除 named volumes，不删除 `AIMA_HOST_ROOT` 下的 Artifact/日志文件。

# 范围

- Windows storage-only Compose override。
- Bootstrap 对 Windows data/log bind mount 的最小兼容权限处理。
- Windows Compose 永久 CI 的 merged-model、启动、写入与持久化验证。
- 受影响的生产环境模板说明、环境运行、日志部署、Roadmap 和 Windows Docker Desktop 指南。

# 非目标

- 不把 PostgreSQL 数据目录 bind 到 Windows NTFS。
- 不把 AIMA 内部 Secret bind 到 Windows NTFS，也不降低 Secret owner/mode 要求。
- 不修改 Linux/WSL/服务器 canonical Compose 存储布局。
- 不修改业务 API、数据库 Schema、Artifact Contract、日志格式或日志轮转策略。
- 不新增依赖。

# 必须保持不变

- `AIMA_DATA_DIR=/app/data`、`AIMA_LOG_DIR=/app/logs` 等容器内 Runtime Contract。
- Linux/WSL/公司服务器由 canonical `compose.yaml` 使用 `AIMA_HOST_ROOT` 全量 bind mount 的既有语义。
- PostgreSQL 18、Migration、API/Worker/Scheduler/Frontend 拓扑与 Health/depends_on。
- 内部 Secret `root:11001 / 0440` 严格权限语义及 existing-secret fail-closed 行为。
- `docker compose ... down` 默认保留全部持久状态。

# 关键决策

1. Windows 采用混合存储：Artifact/日志使用 `AIMA_HOST_ROOT` bind mount，PostgreSQL/内部 Secret 保持 named volume。这样满足本地直接查看文件，同时不让 NTFS 承担数据库与 Secret 的 POSIX 权限语义。
2. Bootstrap 只对 `runtime/data` 与 `runtime/logs` 使用 bind-compatible 权限模式：仍检查路径存在、目录类型与 symlink 边界，并尽力设置现有 UID/GID/mode；Windows 文件共享不支持精确 POSIX 属性时不以 owner/mode 不一致失败。PostgreSQL 与 Secret 不进入该例外。
3. Windows `AIMA_HOST_ROOT` 继续复用 canonical 相对布局；例如 `AIMA_HOST_ROOT=./.runtime` 时文件位于 `.runtime/runtime/data` 与 `.runtime/runtime/logs`，不建立第二套目录约定。
4. `down -v` 删除 Windows PostgreSQL/内部 Secret named volumes，但不会删除 bind-mounted Artifact/日志；需要完全清空时必须另外显式删除 Host Root 下对应目录，避免把 Compose reset 误写成全量文件删除。
5. 回滚应整体恢复 Windows override、bootstrap 兼容模式、CI 与文档；无数据迁移步骤，但从旧 named volume 切换后旧 `windows_runtime_data/windows_runtime_logs` 内容不会自动复制到 Host Root。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Windows 本地 `AIMA_HOST_ROOT` 能直接看到 Runtime 文件 | user:2026-08-24-current-request | satisfied | Workflow run `32690948327`, job `97324380557`: merged model + real runtime 验证 `/app/data`、`/app/logs` 为 Host Root bind，宿主直接读取 marker 与 `.log` 文件 |
| R2 | 应用日志仍作为 `.log` 文件写入正式 `AIMA_LOG_DIR` | docs/blueprint/05_日志安全部署与运维.md | satisfied | Workflow run `32690948327`, job `97324380557`: `api.log` / `worker.log` / `scheduler.log` 均在 `${AIMA_HOST_ROOT}/runtime/logs` 存在并跨 `down/up` 保持 |
| R3 | PostgreSQL 与内部 Secret 保持安全的 Linux 存储/权限边界 | docs/blueprint/05_日志安全部署与运维.md | satisfied | Workflow run `32690948327`, job `97324380557`: PostgreSQL/Secret mount type 为 volume，`postgres_password` 为 `0:11001:440`，DB marker 与 Secret hash 跨重启保持 |
| R4 | Windows 与 canonical Runtime 只适配宿主存储，不复制第二套业务 Runtime | docs/02_环境运行与部署.md | satisfied | Windows CLI job `97324380636` 通过 CMD/PowerShell merged Compose；Internal V1-A run `32690948239`, job `97324380263` 通过 canonical Linux 绝对/相对 Host Root 生命周期 |
| R5 | Windows reset / persistence 文档必须与实际混合存储一致 | docs/guides/03_Windows Docker Desktop Compose运行.md | satisfied | Workflow run `32690948327`, job `97324380557` 验证 `down -v` 后 bind-mounted data/log 仍存在；环境、Blueprint、Guide、Roadmap 与 env template 已同步 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不改变任何页面、浏览器请求或用户界面行为 |
| Backend/API/PostgreSQL Integration | required | `32690948327/97324380557` 验证 PostgreSQL、Migration、Readiness、DB/Secret 持久化与 host-visible data/log；`32690948239/97324380263` 验证 canonical Linux 回归 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client；总 CI 仍验证 generated contract 未漂移 |
| Real Full-stack Golden Path | required | `32690948327/97324380557` 真实启动 bootstrap → postgres → migrate → configure → api/worker/scheduler → frontend，并验证 `/health/ready`、实际 mount 与重启生命周期 |
| Real Provider Probe | not_applicable | 不改变 TikHub/LLM Provider 行为且无需付费外部请求 |
| Docs / Governance / Other | required | TDD 单测 + 总 CI `32690948394/97324381116` + Windows CLI `32690948327/97324380636`；受影响文档全部同步；最终 Ready HEAD 再由 Completion Gate 验证结构 |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取用户决定、`AGENTS.md`、Skill、Blueprint README/05/07、环境运行文档、Roadmap、Windows Guide、当前 Compose/bootstrap/tests/workflow；没有发现新的上游冲突。
- [x] change_coverage：已覆盖 Host Root 可见性、bind-compatible 权限边界、PostgreSQL/Secret 严格边界、持久化/reset、旧 Windows runtime volume 不自动迁移以及 Linux canonical 不变。
- [x] reverse_audit：从 `${AIMA_HOST_ROOT}/runtime/{data,logs}` 反查 bootstrap 与 backend mount；从容器 `/app/data`、`/app/logs` 反查宿主路径；从 PostgreSQL/Secret 反查 named-volume 与权限要求，均有 workflow 机器断言。
- [x] unresolved_cleared：R1–R5 全部 `satisfied`；required Validation Matrix 均有本轮新鲜证据；无隐藏延期项。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试并确认因旧 Windows 全 named-volume 模型正确失败
- [x] 建立 Validation Matrix
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit

# 验证

## Red

Workflow run `32689906933`，Stage 1 job `97321617178`：

```text
Ruff format: 471 files already formatted
Ruff check: All checks passed!
mypy: Success: no issues found in 237 source files
pytest tests/unit -q: 2 failed, 613 passed, 1 warning
```

两个失败均因旧生产实现缺少本需求所需参数：

```text
prepare_host() got an unexpected keyword argument 'runtime_bind_compatible'
_ensure_directory() got an unexpected keyword argument 'strict_permissions'
```

此前有一次测试提交先被 Ruff 格式门禁拦截，未执行到行为测试，因此未作为 Red 证据。

## Green

最终实现候选 HEAD `0a8f213a62db822f9abf074fef2b746634889fda` 的新鲜证据：

1. General CI run `32690948394`，Stage 1 job `97324381116`：
   - `uv lock --check` / `uv sync --locked`：通过；
   - Ruff format：`471 files already formatted`；
   - Ruff check：`All checks passed!`；
   - mypy：`Success: no issues found in 237 source files`；
   - unit tests：`616 passed, 1 warning`；
   - frontend type-check：通过；
   - frontend unit tests：`16 files / 77 tests passed`；
   - frontend build：通过；
   - job conclusion：success。
2. Windows Compose workflow run `32690948327`：
   - Windows Compose CLI job `97324380636`：success；mirror production probe、CMD/PowerShell Compose 解析均通过；
   - Windows Hybrid Storage Runtime Model job `97324380557`：success；真实启动完整容器栈，验证 data/log Host Root bind、宿主可见文件、PostgreSQL/Secret named volume、Secret `0:11001:440`、数据库/Secret/Host file 重启持久化及 `down -v` 生命周期边界。
3. Internal V1-A run `32690948239`，job `97324380263`：success；canonical Linux Compose topology、绝对 Host Root 生命周期和 repository-relative Host Root smoke 全部通过，证明 Windows 适配未破坏 Linux/服务器基线。
4. 同一候选 HEAD 的 Stage 2 Platform、Stage 3A Database、Stage 8F Full-stack、Scheduler、Provider Config、Keyword Packs、Local Dev Bootstrap 等永久 workflows 已通过。Change Completion Gate 当时唯一预期失败原因是本 Change 仍为 `in_progress`；切换到本 Ready HEAD 后必须重新通过才可交付。

## 仍需最终 Ready HEAD 证据

- Change Completion Gate / Ready Check；
- 合入最新 `main` 后永久 CI 无回归；
- L3 两阶段 Review。

# 文档影响

- `env.production.example`：Windows 推荐 `AIMA_HOST_ROOT=./.runtime`；明确 Artifact/日志与 DB/Secret 的物理边界。
- `docs/02_环境运行与部署.md`：同步 Windows 混合存储、查看、持久化、旧 volume 与 reset 语义。
- `docs/blueprint/05_日志安全部署与运维.md`：把 Windows named-volume 安全理由收敛到 PostgreSQL/内部 Secret，并限定 bind-compatible 权限例外只作用于 data/log。
- `docs/guides/03_Windows Docker Desktop Compose运行.md`：更新启动、宿主查看、`down` / `down -v`、完全重置和旧 volume 迁移提示。
- `docs/roadmap/02_生产上线实施路线.md`：固化 Windows mixed-storage 只是本地适配，不改变 Internal V1-B/Production Linux 路线。

# 兼容、部署与回滚

- 无 Schema/Migration、API、依赖或镜像版本变化。
- Windows 行为变化：旧 `windows_runtime_data/windows_runtime_logs` named volume 不再被新 Compose 挂载；旧内容不会自动迁移到 `AIMA_HOST_ROOT`。本 Change 不自动删除旧 volume，避免数据破坏。
- `down -v` 语义变化：只删除 PostgreSQL/内部 Secret named volume；Host Root 下 Artifact/日志仍保留。
- Linux/WSL/服务器 canonical Compose 不变，并由 Internal V1-A 永久 workflow 重新验证。
- 回滚：恢复本 Change 的 Compose/bootstrap/CI/文档即可；Host Root 中已生成的 Artifact/日志不会被回滚自动删除。

# 已知验证边界

GitHub Hosted Windows Runner 能真实验证 Windows PowerShell/CMD Compose CLI，但不提供本仓库可依赖的 Docker Desktop Linux-container Runtime；因此真实 mixed-storage 容器 Golden Path 在 Ubuntu Docker Engine 上验证 merged Compose 语义。具体个人 Windows Docker Desktop 首次升级后仍应执行一次本机 smoke：启动后直接检查 `${AIMA_HOST_ROOT}/runtime/data` 与 `${AIMA_HOST_ROOT}/runtime/logs`。这不是当前机器证据缺失的静默替代，文档已明确该边界。

# 交付

- 分支：`fix/windows-host-root-runtime-files`
- PR：`#196`
- 合并：待最终 Ready HEAD Completion Gate、永久 CI 与 L3 两阶段 Review 全部通过后正常合并，不绕过保护规则。