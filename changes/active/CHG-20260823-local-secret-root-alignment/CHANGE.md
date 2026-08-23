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

把本地源码开发的 Secret 运行模型与已完成的 Internal V1-A 生产 Compose 对齐：AIMA 内部随机 Secret 与 TikHub/LLM 外部 Secret 使用两个明确的运行时根目录。旧本地 `.runtime/secrets/postgres_password` 不再读取、不迁移、不作为兼容来源；既有本地 PostgreSQL volume 若缺少新内部根对应密码，则明确拒绝猜测，开发者按本地重置流程重建数据库。

# 已确认关键决策

1. 本地运行时继续固定双根：
   - `AIMA_SECRET_DIR=.runtime/internal-secrets`；
   - `AIMA_EXTERNAL_SECRET_DIR=.runtime/secrets`。
2. 旧 `.runtime/secrets/postgres_password` 直接废弃，不做自动迁移兼容。
3. PostgreSQL 密码只是数据库 Role 的认证凭据，不代表一份独立数据；改应用侧密码而不改数据库 Role 密码只会导致认证失败，不会生成另一份数据。
4. 不因为旧密码废弃而自动删除已有 PostgreSQL volume；若已有 volume/container 但新内部密码缺失，launcher fail closed，并要求开发者显式重置本地数据库。
5. 生产 Compose、公共 Contract、Schema/Migration、依赖版本保持不变。

# 成功标准

- [ ] 本地 `AIMA_SECRET_DIR` 指向 `.runtime/internal-secrets`，内部运行 Secret 只从该根读取/生成。
- [ ] 本地 `AIMA_EXTERNAL_SECRET_DIR` 指向 `.runtime/secrets`，TikHub/LLM Secret 只从该根读取。
- [ ] `env.local` 中的 TikHub/LLM Key 仍只作为 launcher 输入，materialize 为外部 Secret File 后不进入正式 API/Worker/Scheduler 子进程普通环境变量。
- [ ] 旧 `.runtime/secrets/postgres_password` 不再迁移或读取；即使文件存在，也不能覆盖或决定新的 `.runtime/internal-secrets/postgres_password`。
- [ ] 空本地 PostgreSQL 状态仍自动生成新的内部 `postgres_password` 和三个 Cursor signing key。
- [ ] 已有 PostgreSQL container/volume 但缺少 `.runtime/internal-secrets/postgres_password` 时 fail closed，不用旧路径密码、不静默生成新密码、不自动删除数据。
- [ ] 本地内部 Secret 文件继续拒绝符号链接。
- [ ] Local Dev Bootstrap 在 Windows/Linux 验证 launcher，并在真实 PostgreSQL smoke 中覆盖双根目录、新密码生成和“旧路径密码存在但已有 volume 时仍拒绝兼容”的行为。
- [ ] 不修改生产 Compose、公共 HTTP Contract、OpenAPI/generated client、Schema/Alembic Migration、Provider endpoint/Mapper 或依赖版本。
- [ ] 环境/安全文档同步为本地与生产一致的双 Secret 根模型，并明确旧本地数据库密码路径已废弃及重置方式。

# 范围与非目标

只修改本地开发 launcher 的 Secret 目录行为、旧密码兼容策略、相关测试/CI 与文档。不改变生产 Compose，不进入 Internal V1-B，不执行真实 TikHub/LLM 请求，不修改业务 API、数据库 Schema 或依赖。

# 必须保持不变

- 本地日常入口仍是 `uv run python scripts/dev/backend.py` + `frontend.py`。
- 本地 PostgreSQL 容器/volume 名称、数据库名、用户和端口保持不变。
- Provider Config 继续只保存 `secret_ref`，数据库不保存真实 API Key。
- 正式子进程继续使用 `PlatformSettings` / Secret File 运行边界。
- launcher 不自动执行破坏性数据库删除；本地旧数据是否重置由开发者显式操作。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地开发把 AIMA 内部 Secret 与外部 Provider/LLM Secret 分成两个运行时根目录，与生产环境统一 | user:local-secret-root-alignment | not_satisfied | 待最终实现与 Local Dev CI 重新验证 |
| R2 | 旧 `.runtime/secrets/postgres_password` 直接废弃，不保持自动迁移兼容 | user:legacy-local-postgres-password-deprecated | not_satisfied | 待删除迁移函数、相关测试/CI 与文档 |
| R3 | 外部 Key 继续只通过 Secret File 进入正式运行时，不作为业务子进程普通环境变量 | docs/blueprint/05-日志安全部署与运维.md | not_satisfied | 待最终 unit/Local Dev smoke 重新验证 |
| R4 | 本地 launcher 保持简洁入口；面对既有 volume + 新内部密码缺失时不得猜测或自动毁数据 | AGENTS.md | not_satisfied | 待 fail-closed 回归与真实 Docker smoke |
| R5 | L3 Change 完成更新后的 Traceability、Completion Audit、两阶段 Review、Ready Check/CI、PR 合并与独立归档 | AGENTS.md | not_satisfied | 待最终门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | launcher unit tests + 真实本地 PostgreSQL bootstrap/migration，覆盖新双根和旧密码废弃后的 fail-closed |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/OpenAPI/generated client |
| Real Full-stack Golden Path | required | Local Dev Bootstrap Ubuntu/Windows launcher + Ubuntu PostgreSQL prepare-only smoke |
| Real Provider Probe | not_applicable | 不修改外部 Provider API，CI 只用 fixture Key |
| Docs / Governance / Other | required | 环境/安全文档、Completion Gate、两阶段 Review、最终永久 CI |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取本轮用户新决定、AGENTS、Blueprint 05、环境运行文档。
- [ ] change_coverage：核对双根目录、旧密码废弃、existing volume fail-closed、子进程环境、文档无遗漏。
- [ ] reverse_audit：从 launcher/CI 反向确认旧 `.runtime/secrets/postgres_password` 不再影响数据库密码选择；外部 TikHub/LLM Secret 仍走外部根。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零，不适用层有事实依据。

# 实施任务

1. [ ] 更新 Red/回归测试：删除“旧密码迁移成功”预期，改为旧路径不参与密码选择、已有 volume + 新内部密码缺失时 fail closed。
2. [ ] 最小修改 `local_runtime.py` / `backend.py`：删除旧内部 Secret 自动迁移机制，保留双根和内部 Secret symlink 防护。
3. [ ] 更新 `local-dev-bootstrap.yml`：真实验证全新双根启动，以及旧路径密码存在时不会兼容既有 volume。
4. [ ] 同步 `docs/环境运行与部署.md` 与 Blueprint 05。
5. [ ] 完成 Completion Audit、Requirement Review、Code Quality Review、Ready Gate 与永久 CI；PR #168 转 Ready 后正常合并。
6. [ ] 合并后创建独立归档 PR，将 Change 标记 `done` 并移动到 archive；归档 PR CI 全绿后正常合并。

# 兼容、Migration、部署与回滚

- HTTP Contract/Schema/Alembic：无变更。
- 依赖/锁文件：无变更。
- 本地状态：旧 `.runtime/secrets/postgres_password` 不再受支持。已有 PostgreSQL volume 若只有旧路径密码，launcher 不迁移也不自动重置数据库；开发者需要显式删除本地开发 container/volume 后重新启动，或自行把与数据库实际 Role 匹配的密码放到新的 `.runtime/internal-secrets/postgres_password`。
- 生产部署：`compose.yaml` / `env.production.example` 无变更。
- 回滚：未改数据库 Schema。若回滚到旧 launcher，旧版本可能再次读取单根目录；本 Change 不承诺对旧本地 Secret 布局做双向兼容。

# PostgreSQL 密码语义

PostgreSQL 数据属于 cluster/database/table，密码属于 Role 认证。一个 cluster 可有多个 Role、每个 Role 使用不同密码，并按授权访问同一或不同数据库对象；“不同密码”不会在同一容器里自动映射成不同数据副本。只改变应用 Secret 而不改变数据库内 Role 密码会导致认证失败；在数据库内修改 Role 密码并同步应用 Secret后，访问的仍是同一份数据。Docker 官方镜像的初始化密码参数只对空数据目录的首次初始化生效，已有 volume 不会因为重新传一个新初始化密码就自动改库内 Role 密码。

# 验证证据

## 历史 Red / Green

前一版兼容方案曾通过 CI 验证旧密码原值迁移；2026-08-23 用户随后明确取消该兼容要求，因此这些证据仅作为历史过程，不再作为最终验收依据。

# 两阶段 Review

## Requirement Review

待按新决定重新执行。

## Code Quality Review

待按新决定重新执行。

# Git / PR

- branch: `feature/local-secret-root-alignment`
- implementation PR: `#168 统一本地与生产 Secret 运行根目录`（Draft；新决定完成并最终 CI 全绿后转 Ready）
- archive PR: 待实施 PR 合并后创建
