---
schema: rvc-change/v1
id: CHG-20260823-local-secret-root-alignment
title: 统一本地与生产 Secret 运行根目录
level: L3
status: ready_for_review
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

把本地源码开发的 Secret 运行模型与已完成的 Internal V1-A 生产 Compose 对齐：AIMA 内部随机 Secret 与 TikHub/LLM 外部 Secret 使用两个明确的运行时根目录。旧本地 `.runtime/secrets/postgres_password` 不再读取、不迁移、不作为兼容来源；既有本地 PostgreSQL volume 若缺少新内部根对应密码，则明确拒绝猜测，由开发者显式决定重置本地数据库或提供与数据库 Role 匹配的真实密码。

# 已确认关键决策

1. 本地运行时固定双根：
   - `AIMA_SECRET_DIR=.runtime/internal-secrets`；
   - `AIMA_EXTERNAL_SECRET_DIR=.runtime/secrets`。
2. 旧 `.runtime/secrets/postgres_password` 直接废弃，不做自动迁移兼容。
3. PostgreSQL 密码只是数据库 Role 的认证凭据，不代表一份独立数据；改应用侧密码而不改数据库 Role 密码只会导致认证失败，不会生成另一份数据。
4. 不因为旧密码废弃而自动删除已有 PostgreSQL volume；若已有 volume/container 但新内部密码缺失，launcher fail closed，由开发者显式决定是否重置本地数据库。
5. 生产 Compose、公共 Contract、Schema/Migration、依赖版本保持不变。

# 成功标准

- [x] 本地 `AIMA_SECRET_DIR` 指向 `.runtime/internal-secrets`，内部运行 Secret 只从该根读取/生成。
- [x] 本地 `AIMA_EXTERNAL_SECRET_DIR` 指向 `.runtime/secrets`，TikHub/LLM Secret 只从该根读取。
- [x] `env.local` 中的 TikHub/LLM Key 仍只作为 launcher 输入，materialize 为外部 Secret File 后不进入正式 API/Worker/Scheduler 子进程普通环境变量。
- [x] 旧 `.runtime/secrets/postgres_password` 不再迁移或读取；即使文件存在，也不能覆盖或决定新的 `.runtime/internal-secrets/postgres_password`。
- [x] 空本地 PostgreSQL 状态仍自动生成新的内部 `postgres_password` 和三个 Cursor signing key。
- [x] 已有 PostgreSQL container/volume 但缺少 `.runtime/internal-secrets/postgres_password` 时 fail closed，不用旧路径密码、不静默生成新密码、不自动删除数据。
- [x] 本地内部 Secret 文件继续拒绝符号链接。
- [x] Local Dev Bootstrap 在 Windows/Linux 验证 launcher，并在真实 PostgreSQL smoke 中覆盖双根目录、新密码生成和“旧路径密码存在但已有 volume 时仍拒绝兼容”的行为。
- [x] 未修改生产 Compose、公共 HTTP Contract、OpenAPI/generated client、Schema/Alembic Migration、Provider endpoint/Mapper 或依赖版本。
- [x] 环境/安全文档已同步为本地与生产一致的双 Secret 根模型，并明确旧本地数据库密码路径已废弃及重置方式。

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
| R1 | 本地开发把 AIMA 内部 Secret 与外部 Provider/LLM Secret 分成两个运行时根目录，与生产环境统一 | user:local-secret-root-alignment | satisfied | `local_runtime.py` 双根；unit；Local Dev Bootstrap #119 |
| R2 | 旧 `.runtime/secrets/postgres_password` 直接废弃，不保持自动迁移兼容 | user:legacy-local-postgres-password-deprecated | satisfied | 旧迁移逻辑不存在；真实 PostgreSQL smoke 验证旧路径密码存在时仍拒绝兼容，并在显式 reset 后生成新内部密码 |
| R3 | 外部 Key 继续只通过 Secret File 进入正式运行时，不作为业务子进程普通环境变量 | `docs/blueprint/05-日志安全部署与运维.md` | satisfied | `build_runtime_environment()` 移除明文 Key；unit；Provider Config smoke 只保存 `secret_ref` |
| R4 | 本地 launcher 保持简洁入口；面对既有 volume + 新内部密码缺失时不得猜测或自动毁数据 | `AGENTS.md` | satisfied | `ensure_postgres_container()` fail closed；Local Dev Bootstrap #119 真实 Docker 验证；环境运行文档记录显式 reset |
| R5 | L3 Change 在 Ready 前完成 Traceability、Completion Audit、两阶段 Review 与永久实现 CI 验证 | `AGENTS.md` | satisfied | 本 Change 审计；CI #2296；Local Dev #119；Internal V1-A #59；其余永久工作流均成功 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | CI #2296 Stage 2 Platform / Stage 3A Database 全绿；Local Dev #119 真实 PostgreSQL bootstrap/migration 全绿 |
| Contract / Generated Client | not_applicable | 没有 Contract/OpenAPI/generated client diff；CI #2296 Contract drift check 成功 |
| Real Full-stack Golden Path | required | Local Dev #119：Ubuntu/Windows launcher + PostgreSQL smoke 全绿；Internal V1-A #59 生产 Compose Golden Path 成功 |
| Real Provider Probe | not_applicable | 不修改 Provider 外部 API；只用 fixture Key，未产生真实付费调用 |
| Docs / Governance / Other | required | Blueprint 05 + 环境运行文档同步；Audit Correctness #1114、Stage 6 #293、Stage 7/8F 永久工作流均成功 |

# Completion Audit

- [x] upstream_re_read：2026-08-23 Ready 前重新读取本轮用户最终决定、当前分支 `AGENTS.md`、Blueprint 05 与环境运行文档；上游要求与本 Change 一致。
- [x] change_coverage：双根目录、旧密码废弃、existing volume fail-closed、外部 Key 文件流向、symlink 防护、真实 Docker reset、文档均有实现/验证；没有 Contract/Schema/依赖/生产 Compose 变更。
- [x] reverse_audit：从最终 launcher/CI 反向确认旧 `.runtime/secrets/postgres_password` 不再影响数据库密码选择；TikHub/LLM 仍仅进入外部根；任务不涉及前端页面能力，页面反向审计不适用。
- [x] unresolved_cleared：Requirement Traceability 无 `not_satisfied`；不适用验证层均有范围依据。

# 实施任务

1. [x] 更新回归测试：旧路径不参与密码选择，内部 Secret symlink fail closed。
2. [x] 最小修改 `local_runtime.py` / `backend.py`：双根生效，删除旧密码自动迁移机制。
3. [x] 更新 `local-dev-bootstrap.yml`：真实验证全新双根启动、旧路径密码拒绝兼容、显式 reset 后新内部密码生成。
4. [x] 同步 `docs/环境运行与部署.md` 与 Blueprint 05。
5. [x] 完成 Completion Audit、Requirement Review、Code Quality Review 与实现 HEAD 永久 CI。

合并后按仓库 Change 管理规则创建独立归档 PR，将本 Change 标记 `done` 并移动到 `changes/archive/2026-08/`；归档 PR 自身通过永久 CI 后再合并。

# 兼容、Migration、部署与回滚

- HTTP Contract/Schema/Alembic：无变更。
- 依赖/锁文件：无变更。
- 本地状态：旧 `.runtime/secrets/postgres_password` 不再受支持。已有 PostgreSQL volume 若只有旧路径密码，launcher 不迁移也不自动重置数据库；开发者显式删除本地开发 container/volume 后重新启动，或自行把与数据库实际 Role 匹配的密码放到新的 `.runtime/internal-secrets/postgres_password`。
- 生产部署：`compose.yaml` / `env.production.example` 无变更；生产数据库密码恢复策略不变。
- 回滚：未改数据库 Schema。若回滚到旧 launcher，旧版本可能再次读取单根目录；本 Change 不承诺对旧本地 Secret 布局做双向兼容。

# PostgreSQL 密码语义

PostgreSQL 数据属于 cluster/database/table，密码属于 Role 认证。一个 cluster 可有多个 Role、每个 Role 使用不同密码，并按授权访问同一或不同数据库对象；“不同密码”不会在同一容器里自动映射成不同数据副本。只改变应用 Secret 而不改变数据库内 Role 密码会导致认证失败；在数据库内修改 Role 密码并同步应用 Secret 后，访问的仍是同一份数据。Docker 官方镜像的初始化密码参数只对空数据目录的首次初始化生效，已有 volume 不会因为重新传一个新初始化密码就自动改库内 Role 密码。

# 验证证据

## Final Green

实现 HEAD：`bfbfd55aaef3fe612e716c54d6a90a12e5669db5`

- CI #2296 / run `32629622382`: success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全绿。
- Local Dev Bootstrap #119 / run `32629622371`: success；Windows、Ubuntu、PostgreSQL bootstrap smoke 全绿。
- Internal V1-A Deployable Stack #59 / run `32629622438`: success；Compose Golden Path 全绿。
- Stage 8F #423、Stage 6 #293、Stage 7 Keyword Packs #1905、Provider Config Routing #2018、Scheduler Runtime #2245、Plan Occurrence #1903、Audit Correctness #1114：success。
- `compare_commits(main@5d4dcb6..HEAD)` 只有 7 个预期文件；无生产 Compose、Contract、Migration、依赖/锁文件变更。
- Change Completion Gate #142 的 failure 发生在本 Change 仍为 `in_progress` 时，属于状态门禁预期行为；本次 `ready_for_review` 提交必须重新触发并通过该 Gate。

# 两阶段 Review

## Requirement Review

结论：通过，无遗漏。

- A1 上游 → Change：用户最终“双 Secret 根 + 废弃旧本地 PostgreSQL 密码路径”决定、`AGENTS.md` 的安全/兼容/Completion Gate 要求、Blueprint 05 的 Secret File 边界、环境运行文档的 launcher 边界均已映射到 R1-R5。
- A2 Change → 实现/测试/文档：R1-R4 分别由 `local_runtime.py`、unit、Local Dev 真实 Docker smoke、Blueprint/环境文档覆盖；R5 由 Completion Audit、Review 与最终永久实现 CI 覆盖。
- 不适用项：没有页面、公共 Contract、Schema/Migration 或真实 Provider API 变化，因此没有制造额外前端/迁移/付费 Probe 机制。

## Code Quality Review

结论：通过，无 Serious / Important finding。

- 旧密码迁移 helper 已不存在；旧路径只用于明确拒绝、测试和文档说明，不参与当前密码选择。
- 已有 volume + 新内部密码缺失时 fail closed；不会自动删除数据或生成无法匹配既有数据库的新密码。
- 全新数据库仍由内部根安全生成随机密码；内部 Secret symlink 被拒绝。
- TikHub/LLM Key 仍 materialize 到外部根，并从正式子进程普通环境变量移除；Provider Config 仅保存 `secret_ref`。
- 改动局限于 7 个预期文件，没有无关重构、生产 Compose、Schema、Contract、依赖或锁文件变化。

# Git / PR

- branch: `feature/local-secret-root-alignment`
- implementation PR: `#168 统一本地与生产 Secret 运行根目录`（Draft；本次 ready commit 的 Completion Gate / 永久 CI 全绿后转 Ready 并合并）
- archive delivery: 实施 PR 合并后使用独立归档 PR
