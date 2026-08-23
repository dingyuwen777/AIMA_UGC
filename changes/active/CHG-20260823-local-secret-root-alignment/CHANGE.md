---
schema: rvc-change/v1
id: CHG-20260823-local-secret-root-alignment
title: 统一本地与生产 Secret 运行根目录
level: L3
status: in_progress
owner: chatgpt
branch: feature/local-secret-root-alignment
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - local-development
  - configuration
  - security
  - ci
affected_paths:
  - scripts/dev/local_runtime.py
  - scripts/dev/backend.py
  - tests/unit/platform/test_local_dev_runtime.py
  - .github/workflows/local-dev-bootstrap.yml
  - docs/环境运行与部署.md
  - docs/blueprint/05-日志安全部署与运维.md
contracts: []
data_changes: []
---

# 目标

把本地源码开发的 Secret 运行模型与已完成的 Internal V1-A 生产 Compose 对齐：AIMA 内部随机 Secret 与 TikHub/LLM 外部 Secret 使用两个明确的运行时根目录，同时保持现有本地 PostgreSQL volume、已有 Secret 值、`env.local` 操作入口和业务行为兼容。

# 成功标准

- [ ] 本地 `AIMA_SECRET_DIR` 指向 `.runtime/internal-secrets`，只存放 `postgres_password` 和三个 Cursor signing key。
- [ ] 本地 `AIMA_EXTERNAL_SECRET_DIR` 指向 `.runtime/secrets`，只承载 TikHub/LLM Provider Secret。
- [ ] `env.local` 中的 TikHub/LLM Key 仍只作为 launcher 输入，materialize 为外部 Secret File 后不进入正式 API/Worker/Scheduler 子进程普通环境变量。
- [ ] 旧本地 `.runtime/secrets/` 中的四个内部 Secret 自动迁移到 `.runtime/internal-secrets/`，保留原字节值，避免既有 PostgreSQL volume 因密码变化失联。
- [ ] 新旧目录同时存在同名内部 Secret 时：值相同可安全收敛为新内部根；值不同必须 fail closed，不猜测、不覆盖、不轮换。
- [ ] 新环境仍能自动生成缺失的四个内部 Secret；外部 TikHub/LLM Secret 只写外部根。
- [ ] Local Dev Bootstrap 的 Windows/Linux launcher 验证和真实 PostgreSQL bootstrap smoke 覆盖双根目录及旧状态迁移。
- [ ] 不修改生产 Compose、公共 HTTP Contract、OpenAPI/generated client、Schema/Alembic Migration、Provider endpoint/Mapper 或依赖版本。
- [ ] 环境/安全文档同步为本地与生产一致的双 Secret 根模型。

# 范围与非目标

只修改本地开发 launcher 的 Secret 目录、旧状态兼容迁移、相关测试/CI 与文档。不改变生产 Compose，不进入 Internal V1-B，不执行真实 TikHub/LLM 请求，不修改业务 API、数据库 Schema 或依赖。

# 必须保持不变

- 本地日常入口仍是 `uv run python scripts/dev/backend.py` + `frontend.py`。
- 本地 PostgreSQL 容器/volume 名称、数据库名、用户、端口和已有数据继续复用。
- 已有 `postgres_password` 必须保持原值；不得因目录重构生成新密码。
- Provider Config 继续只保存 `secret_ref`，数据库不保存真实 API Key。
- 正式子进程继续使用 `PlatformSettings` / Secret File 运行边界。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地开发也把 AIMA 内部 Secret 与外部 Provider/LLM Secret 分成两个运行时根目录，与生产环境统一 | user:local-secret-root-alignment | not_satisfied | 待实现与 Local Dev CI |
| R2 | Secret 值继续通过只读/文件边界进入正式运行时，外部 Key 不作为业务子进程普通环境变量 | docs/blueprint/05-日志安全部署与运维.md | not_satisfied | 待 launcher/测试验证 |
| R3 | 本地开发保持简洁 launcher 入口，TikHub/LLM 由 env.local 输入并 materialize 为 Secret File | docs/环境运行与部署.md | not_satisfied | 待实现与文档同步 |
| R4 | 默认保持合法既有行为和兼容性，不能破坏已有本地 PostgreSQL 数据/密码事实 | AGENTS.md | not_satisfied | 待旧 Secret 迁移测试与 PostgreSQL smoke |
| R5 | L3 Change 完成 Traceability、Completion Audit、两阶段 Review、Ready Check/CI 和正常 PR 交付 | AGENTS.md | not_satisfied | 待最终门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | launcher unit tests + 真实本地 PostgreSQL bootstrap/migration，验证密码兼容 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/OpenAPI/generated client |
| Real Full-stack Golden Path | required | Local Dev Bootstrap Ubuntu/Windows launcher + Ubuntu PostgreSQL prepare-only smoke |
| Real Provider Probe | not_applicable | 不修改外部 Provider API，CI 只用假 Key |
| Docs / Governance / Other | required | 环境/安全文档、Completion Gate、两阶段 Review |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取本轮用户决定、AGENTS、Blueprint 05、环境运行文档。
- [ ] change_coverage：核对双根目录、旧 Secret 迁移、冲突 fail closed、子进程环境、PostgreSQL 兼容、文档无遗漏。
- [ ] reverse_audit：从最终 launcher/CI 反向审计内部/外部 Secret 文件流向和旧状态恢复边界。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零，不适用层有事实依据。

# 实施任务

1. Red：扩展 `test_local_dev_runtime.py`，锁定双根目录、内部 Secret 迁移和冲突 fail closed 行为。
2. Green：最小修改 `local_runtime.py` / `backend.py`，统一双根目录并安全迁移旧状态。
3. 更新 `local-dev-bootstrap.yml`，真实验证新目录和已有 PostgreSQL 密码兼容。
4. 同步 `docs/环境运行与部署.md` 与 Blueprint 05。
5. 完成 Completion Audit、Requirement Review、Code Quality Review、Ready Gate 与永久 CI；正常合并。
6. 合并后独立归档 Change，跑永久 CI 后正常合并。

# 兼容、Migration、部署与回滚

- HTTP Contract/Schema/Alembic：无变更。
- 依赖/锁文件：无变更。
- 本地状态迁移：仅文件系统 Secret 目录迁移；内部 Secret 原值保留。若旧/新同名 Secret 值冲突则拒绝启动并要求人工确认，不静默覆盖。
- 生产部署：无变更。
- 回滚：未改数据库 Schema；若回滚旧 launcher，需要把内部 Secret 放回旧 `.runtime/secrets/`，尤其必须保持与既有 PostgreSQL volume 匹配的 `postgres_password` 原值。

# 验证证据

## Red

待执行。

## Green

待执行。

# 两阶段 Review

## Requirement Review

待 Ready 前执行。

## Code Quality Review

待 Ready 前执行。

# Git / PR

- branch: `feature/local-secret-root-alignment`
- implementation PR: 待创建
- archive PR: 待实施 PR 合并后创建
