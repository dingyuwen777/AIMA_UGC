---
schema: rvc-change/v1
id: CHG-20260824-windows-host-root-runtime-files
title: Windows Docker Desktop 运行文件落到 AIMA_HOST_ROOT
level: L3
status: in_progress
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
contracts: []
data_changes: []
---

# 目标

Windows Docker Desktop 使用 `compose.yaml + compose.windows.yaml` 时，让 Artifact 与应用 `.log` 文件实际落到 `AIMA_HOST_ROOT` 可见目录；PostgreSQL 与 AIMA 内部 Secret 继续保存在 Docker-managed named volumes，保持 Linux 权限语义与数据库安全边界。

# 成功标准

- [ ] Windows merged Compose 的 `/app/data` 与 `/app/logs` 使用 `${AIMA_HOST_ROOT}/runtime/data`、`${AIMA_HOST_ROOT}/runtime/logs` bind mount。
- [ ] `bootstrap` 对应的 `/host/runtime/data`、`/host/runtime/logs` 使用同一 Host Root bind mount，且 Windows 文件共享不因严格 POSIX owner/mode 校验阻塞启动。
- [ ] PostgreSQL 与内部 Secret 继续使用 `windows_postgres`、`windows_internal_secrets` named volume，并保持 Secret 严格权限校验。
- [ ] 真实 Compose smoke 能写入 host-visible Artifact/日志目录，并在正常 `down` / 再次 `up` 后保持；数据库和内部 Secret 也保持。
- [ ] Linux/WSL canonical `compose.yaml` 的现有 bind mount 与严格权限行为不变。
- [ ] Windows 运行与 reset 文档准确说明：`down -v` 只删除 named volumes，不删除 `AIMA_HOST_ROOT` 下的 Artifact/日志文件。

# 范围

- Windows storage-only Compose override。
- Bootstrap 对 Windows data/log bind mount 的最小兼容权限处理。
- Windows Compose 永久 CI 的 merged-model、启动、写入与持久化验证。
- 受影响的生产环境模板说明、环境运行、日志部署和 Windows Docker Desktop 指南。

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
| R1 | Windows 本地 `AIMA_HOST_ROOT` 能直接看到 Runtime 文件 | user:2026-08-24-current-request | not_satisfied | 待实现 merged Compose bind mount 与真实写入验证 |
| R2 | 应用日志仍作为 `.log` 文件写入正式 `AIMA_LOG_DIR` | docs/blueprint/05_日志安全部署与运维.md | not_satisfied | 待验证 `/app/logs` bind 到 Host Root 且产生日志文件 |
| R3 | PostgreSQL 与内部 Secret 保持安全的 Linux 存储/权限边界 | docs/blueprint/05_日志安全部署与运维.md | not_satisfied | 待验证两个 named volume 与 Secret 0440 权限 |
| R4 | Windows 与 canonical Runtime 只适配宿主存储，不复制第二套业务 Runtime | docs/02_环境运行与部署.md | not_satisfied | 待 merged-model 与 canonical Compose 回归验证 |
| R5 | Windows reset / persistence 文档必须与实际混合存储一致 | docs/guides/03_Windows Docker Desktop Compose运行.md | not_satisfied | 待文档同步及 CI persistence 验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不改变任何页面、浏览器请求或用户界面行为 |
| Backend/API/PostgreSQL Integration | required | Compose smoke 验证 PostgreSQL 启动、Migration、Readiness、DB/Secret 持久化及 host-visible data/log 写入 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client |
| Real Full-stack Golden Path | required | `compose.yaml + compose.windows.yaml` 启动完整容器栈并访问 `/health/ready`；验证实际 mount type 与持久化 |
| Real Provider Probe | not_applicable | 不改变 TikHub/LLM Provider 行为且无需付费外部请求 |
| Docs / Governance / Other | required | 单元测试覆盖 bootstrap bind-compatible 权限边界；Windows runner 验证标准 Compose CLI 解析；运行文档同步；Completion Gate/Ready Check |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取用户决定及全部受影响正式事实源。
- [ ] change_coverage：确认 Host Root 可见性、权限边界、持久化/reset、Linux canonical 不变全部覆盖。
- [ ] reverse_audit：从 Host Root 路径反查 bootstrap/container mount，从容器 `/app/data` `/app/logs` 反查宿主路径，并复核 named volume 安全边界。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零且 required Validation Matrix 均有新鲜证据。

# 任务

- [x] 调查当前实现和事实源
- [ ] 建立失败测试并确认因旧 Windows 全 named-volume 模型正确失败
- [x] 建立 Validation Matrix
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- 目标单元测试：`uv run pytest tests/unit/test_prepare_host.py -q`
- Windows Compose 模型：Windows Runner 的 CMD/PowerShell `docker compose ... config` + Ubuntu Docker Engine merged-model 断言。
- Real Full-stack：永久 `Windows Docker Desktop Compose Compatibility` workflow 真实 `up -d --build --wait`、`/health/ready`、mount inspection、host-visible write/persistence、PostgreSQL/Secret persistence。
- 相关门禁：仓库永久 CI + `python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`。

## 新鲜证据

- 尚未执行。

# 文档影响

- `env.production.example`：说明 Windows 下 Host Root 控制 Artifact/日志，PostgreSQL/Secret 仍为 named volume。
- `docs/02_环境运行与部署.md`：同步 Windows 混合存储路径、查看和 reset 语义。
- `docs/blueprint/05_日志安全部署与运维.md`：收窄 Windows named-volume 安全理由到 PostgreSQL/内部 Secret。
- `docs/guides/03_Windows Docker Desktop Compose运行.md`：更新日常查看、持久化与彻底重置步骤。

# 兼容、部署与回滚

- 无 Schema/Migration、API、依赖或镜像版本变化。
- Windows 行为变化：旧 `windows_runtime_data/windows_runtime_logs` named volume 不再被新 Compose 挂载；旧内容不会自动迁移到 `AIMA_HOST_ROOT`。本任务不自动删除旧 volume，避免数据破坏。
- `down -v` 语义变化：只删除 PostgreSQL/内部 Secret named volume；Host Root 下 Artifact/日志仍保留。
- Linux/WSL/服务器 canonical Compose 不变。
- 回滚：恢复本 Change 的 Compose/bootstrap/CI/文档即可；Host Root 中已生成的 Artifact/日志不会被回滚自动删除。

# 交付

- 分支：`fix/windows-host-root-runtime-files`
- Commit：待实现
- PR：待创建
- 合并：永久 CI 与 L3 Review 通过后执行正常 PR 合并。