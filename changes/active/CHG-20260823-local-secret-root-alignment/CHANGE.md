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

把本地源码开发的 Secret 运行模型与已完成的 Internal V1-A 生产 Compose 对齐：AIMA 内部随机 Secret 与 TikHub/LLM 外部 Secret 使用两个明确的运行时根目录，同时保持现有本地 PostgreSQL volume、已有 Secret 值、`env.local` 操作入口和业务行为兼容。

# 成功标准

- [x] 本地 `AIMA_SECRET_DIR` 指向 `.runtime/internal-secrets`，只存放 `postgres_password` 和三个 Cursor signing key。
- [x] 本地 `AIMA_EXTERNAL_SECRET_DIR` 指向 `.runtime/secrets`，只承载 TikHub/LLM Provider Secret。
- [x] `env.local` 中的 TikHub/LLM Key 仍只作为 launcher 输入，materialize 为外部 Secret File 后不进入正式 API/Worker/Scheduler 子进程普通环境变量。
- [x] 旧本地 `.runtime/secrets/` 中的四个内部 Secret 自动迁移到 `.runtime/internal-secrets/`，保留原字节值，避免既有 PostgreSQL volume 因密码变化失联。
- [x] 新旧目录同时存在同名内部 Secret 时：值相同可安全收敛为新内部根；值不同必须 fail closed，不猜测、不覆盖、不轮换。
- [x] 新环境仍能自动生成缺失的四个内部 Secret；外部 TikHub/LLM Secret 只写外部根。
- [x] 本地内部 Secret 文件拒绝符号链接，避免目录迁移后随机 Secret 写入跟随链接。
- [x] Local Dev Bootstrap 的 Windows/Linux launcher 验证和真实 PostgreSQL bootstrap smoke 覆盖双根目录及旧状态迁移。
- [x] 不修改生产 Compose、公共 HTTP Contract、OpenAPI/generated client、Schema/Alembic Migration、Provider endpoint/Mapper 或依赖版本。
- [x] 环境/安全文档同步为本地与生产一致的双 Secret 根模型。

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
| R1 | 本地开发也把 AIMA 内部 Secret 与外部 Provider/LLM Secret 分成两个运行时根目录，与生产环境统一 | user:local-secret-root-alignment | satisfied | `RuntimePaths` + `build_runtime_environment()` 显式设置 `.runtime/internal-secrets` / `.runtime/secrets` 与 `AIMA_SECRET_DIR` / `AIMA_EXTERNAL_SECRET_DIR`；Local Dev Run 32628718247 通过 |
| R2 | Secret 值继续通过文件边界进入正式运行时，外部 Key 不作为业务子进程普通环境变量 | docs/blueprint/05-日志安全部署与运维.md | satisfied | `build_runtime_environment()` 先移除本地明文 Key，再 materialize TikHub/LLM 外部 Secret File；unit regression + Local Dev PostgreSQL smoke 验证 Provider Config 只保存 `secret_ref` |
| R3 | 本地开发保持简洁 launcher 入口，TikHub/LLM 由 env.local 输入并 materialize 为 Secret File | docs/环境运行与部署.md | satisfied | `backend.py` 原入口不变，只在准备阶段增加内部 Secret 迁移；Windows/Ubuntu launcher Jobs 均成功 |
| R4 | 默认保持合法既有行为和兼容性，不能破坏已有本地 PostgreSQL 数据/密码事实 | AGENTS.md | satisfied | `migrate_legacy_internal_secrets()` 保留原值、冲突/符号链接 fail closed；Run 32628718247 的 existing-volume smoke 删除容器但保留 volume，把密码放回旧目录后仍成功 migrate/check |
| R5 | L3 Change 完成 Traceability、Completion Audit、两阶段 Review、Ready Check/CI 和正常 PR 交付 | AGENTS.md | satisfied | Traceability/Matrix/Audit/两阶段 Review 已完成；PR #168 保持 Draft；状态提交将触发最终 Completion Gate 与永久 CI，全部绿色后才转 Ready/合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | CI Run 32628718254 / Stage 2 Platform Job 97168041318 成功；unit tests 覆盖双根、迁移、冲突、symlink；真实 PostgreSQL 由 Local Dev smoke 覆盖 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/OpenAPI/generated client；总 CI generated contract 漂移检查保持通过 |
| Real Full-stack Golden Path | required | Local Dev Run 32628718247：Ubuntu launcher、Windows launcher、PostgreSQL bootstrap smoke 全部成功；existing-volume 迁移路径真实验证 |
| Real Provider Probe | not_applicable | 不修改外部 Provider API；CI 只用假 TikHub Key，不发真实付费请求 |
| Docs / Governance / Other | required | `docs/环境运行与部署.md` 与 Blueprint 05 已同步；final Ready Commit 重新跑 Completion Gate/永久 CI |

# Completion Audit

- [x] upstream_re_read：2026-08-23 在实现稳定后重新读取本轮用户决定、当前分支 `AGENTS.md`、Blueprint 05 与环境运行文档；本任务只是本地运行边界统一，不改变 Internal V1-B 的 Roadmap 状态。
- [x] change_coverage：逐项核对双根目录、旧 Secret 原值迁移、同名冲突 fail closed、symlink 拒绝、子进程环境、已有 PostgreSQL volume 兼容和文档，没有发现遗漏。
- [x] reverse_audit：从 `backend.py → local_runtime.py → PlatformSettings/Worker/LLM` 以及 Local Dev CI 反向检查内部/外部 Secret 流向；搜索确认仓库无剩余 `paths.secrets` 调用；生产 `compose.yaml` 未修改。
- [x] unresolved_cleared：所有 Requirement 已满足；Browser/Contract/Real Provider 三层不适用均有当前任务范围依据，没有提前进入 Internal V1-B 或真实付费调用。

# 实施任务

1. [x] Red：扩展 `test_local_dev_runtime.py`，锁定双根目录、内部 Secret 迁移和冲突 fail closed 行为。
2. [x] Green：最小修改 `local_runtime.py` / `backend.py`，统一双根目录并安全迁移旧状态。
3. [x] 更新 `local-dev-bootstrap.yml`，真实验证新目录和已有 PostgreSQL 密码兼容。
4. [x] 同步 `docs/环境运行与部署.md` 与 Blueprint 05。
5. [x] 完成 Completion Audit、Requirement Review 与 Code Quality Review；最终 Ready Gate/永久 CI 由本次状态提交触发。
6. [ ] 合并后独立归档 Change，跑永久 CI 后正常合并。

# 兼容、Migration、部署与回滚

- HTTP Contract/Schema/Alembic：无变更。
- 依赖/锁文件：无变更。
- 本地状态迁移：仅文件系统 Secret 目录迁移；四个内部 Secret 原值保留。若旧/新同名 Secret 值冲突则拒绝启动并要求人工确认，不静默覆盖；同名内部 Secret 符号链接同样拒绝。
- 生产部署：`compose.yaml` / `env.production.example` 无变更。
- 回滚：未改数据库 Schema；若回滚旧 launcher，需要把内部 Secret 放回旧 `.runtime/secrets/`，尤其必须保持与既有 PostgreSQL volume 匹配的 `postgres_password` 原值。

# 文档影响

- `docs/环境运行与部署.md`：本地首次启动、升级迁移、目录布局、重置数据库与常见问题切换为双根语义。
- `docs/blueprint/05-日志安全部署与运维.md`：本地与生产统一使用 `AIMA_SECRET_DIR` / `AIMA_EXTERNAL_SECRET_DIR` 分类；保留 `PlatformSettings` fallback 作为底层兼容而非正常 launcher 路径。
- Roadmap：无阶段状态变化，不修改；Internal V1-B 仍是下一正式开发单元。

# 验证证据

## Red

CI Run `32628265270` / Stage 2 Platform Job `97166921705`：目标测试 **3 failed / 102 passed**。三个失败分别证明旧实现缺少 `internal_secrets`、`external_secrets` 与 `migrate_legacy_internal_secrets()`；PostgreSQL 18.4 服务正常，因此 Red 是目标能力缺失而非环境失败。

## Green

- Local Dev Bootstrap Run `32628718247`：Ubuntu launcher、Windows launcher、PostgreSQL bootstrap smoke 全部 success。
- PostgreSQL smoke 首轮把旧 `.runtime/secrets` 四个内部 Secret 原值迁到 `.runtime/internal-secrets`，TikHub fixture Key 留在 `.runtime/secrets`，Migration current/check 成功。
- existing-volume smoke 删除本地 PostgreSQL container 但保留 named volume，把原 `postgres_password` 临时放回旧目录，再运行同一 launcher；密码原值迁回新目录且 Alembic current/check 成功，证明不会造成已有数据库密码漂移。
- CI Run `32628718254` / Stage 2 Platform Job `97168041318`：success，包含 unit/PostgreSQL integration/readiness；总 CI final 状态在 Ready commit 后重新取证。
- 未执行真实 TikHub/LLM 请求；只使用非生产 fixture Key。

# 两阶段 Review

## Requirement Review

2026-08-23 完成：

- A1 上游要求 → Change：用户要求的“本地也拆内部/外部两个运行根并与生产统一”已直接进入 R1；仓库安全边界、launcher 简洁性和既有 PostgreSQL 密码兼容分别进入 R2—R4，无遗漏需要新 Contract/Schema/Roadmap 决策的事项。
- A2 Change → 实现/测试/文档：双根目录、子进程环境、旧状态原值迁移、同值收敛/异值拒绝、existing-volume 真实 smoke、文档均有对应证据。生产 Compose 与业务接口没有被扩展。
- 结论：无未满足 requirement。

## Code Quality Review

2026-08-23 完成：

- `RuntimePaths` 只拆目录，不引入第二套配置模型；正式子进程继续由 `PlatformSettings` 解析两个既有环境变量。
- 旧内部 Secret 使用同文件系统 `Path.replace()` 迁移，避免读出后重新生成；新旧双份用 constant-time `compare_digest()` 比较，同值才删除旧副本，异值 fail closed。
- Review 发现“新内部路径自身为 symlink 且旧副本不存在”可能绕过迁移检查；已补回归测试并在迁移/随机生成入口统一拒绝内部 Secret symlink。
- TikHub/LLM 文件名不在内部迁移白名单，不会被错误搬入内部根；原 `env.local` 明文 Key 继续从正式子进程环境中移除。
- 搜索确认没有遗留 `paths.secrets` 调用；变更仅 7 个任务相关文件，无生产 Compose、依赖、Contract、Migration 变化。
- 结论：没有未解决 serious/important 问题。

# Git / PR

- branch: `feature/local-secret-root-alignment`
- implementation PR: `#168 统一本地与生产 Secret 运行根目录`（Draft，最终 CI 全绿后转 Ready）
- archive PR: 待实施 PR 合并后创建
