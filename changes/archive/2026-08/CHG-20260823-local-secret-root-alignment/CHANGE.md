---
schema: rvc-change/v1
id: CHG-20260823-local-secret-root-alignment
title: 统一本地与生产 Secret 运行根目录
level: L3
status: done
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

# 最终结论

本 Change 已完成并通过 L3 Completion Gate、两阶段 Review、永久 CI 与正常 PR 合并。

本地源码开发与生产 Compose 现在使用一致的 Secret 分类语义：

```text
AIMA 内部随机 Secret
→ AIMA_SECRET_DIR
→ 本地 .runtime/internal-secrets

外部 Provider / LLM Secret
→ AIMA_EXTERNAL_SECRET_DIR
→ 本地 .runtime/secrets
```

旧本地 `.runtime/secrets/postgres_password` 已正式废弃：launcher 不读取、不迁移，也不用它决定当前 PostgreSQL 密码。

# 已确认关键决策

1. 本地 `AIMA_SECRET_DIR=.runtime/internal-secrets`。
2. 本地 `AIMA_EXTERNAL_SECRET_DIR=.runtime/secrets`。
3. 旧 `.runtime/secrets/postgres_password` 不提供自动迁移兼容。
4. 已有本地 PostgreSQL volume/container 但新内部密码缺失时 fail closed，不读取旧路径密码、不生成无法匹配既有数据库的新密码、不自动删除数据。
5. 本地开发数据可以显式重置；需要保留旧数据时，开发者自行确认数据库 Role 的真实密码并写入新的内部路径。
6. PostgreSQL 密码属于 Role 认证，不代表数据副本；不同密码不会在同一个 PostgreSQL cluster/container 中自动对应不同数据。
7. 生产 Compose、公共 Contract、Schema/Migration、依赖和锁文件均未改变；生产 PostgreSQL 密码恢复策略保持不变。

# 成功标准

- [x] `AIMA_SECRET_DIR` 指向 `.runtime/internal-secrets`，内部 Secret 只从该根读取/生成。
- [x] `AIMA_EXTERNAL_SECRET_DIR` 指向 `.runtime/secrets`，TikHub/LLM Secret 只从该根读取。
- [x] `env.local` 中的 TikHub/LLM Key 仅作为 launcher 输入，materialize 为外部 Secret File 后不进入正式业务子进程普通环境变量。
- [x] 旧 `.runtime/secrets/postgres_password` 不再迁移或读取。
- [x] 空本地 PostgreSQL 状态自动生成新的内部 `postgres_password` 和三个 Cursor signing key。
- [x] 已有 PostgreSQL container/volume + 新内部密码缺失时 fail closed，不猜测、不自动清库。
- [x] 本地内部 Secret 文件拒绝符号链接。
- [x] Windows / Ubuntu launcher 与真实 PostgreSQL smoke 覆盖最终行为。
- [x] 环境运行文档与 Blueprint 05 已同步。
- [x] 无生产 Compose、Contract、OpenAPI/generated client、Migration、依赖/锁文件变更。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地开发使用内部 Secret 根与外部 Provider/LLM Secret 根，并与生产语义统一 | user:local-secret-root-alignment | satisfied | `local_runtime.py`、unit、Local Dev Bootstrap #120 |
| R2 | 旧 `.runtime/secrets/postgres_password` 直接废弃，不自动迁移兼容 | user:legacy-local-postgres-password-deprecated | satisfied | 旧迁移逻辑不存在；真实 Docker smoke 验证旧路径存在仍拒绝兼容 |
| R3 | 外部 Key 仅通过 Secret File 进入正式运行时 | `docs/blueprint/05-日志安全部署与运维.md` | satisfied | 双根环境、unit、Provider Config 只保存 `secret_ref` |
| R4 | 已有本地数据状态不得被 launcher 静默破坏 | `AGENTS.md` | satisfied | existing volume + missing internal password fail closed；显式 reset 独立验证 |
| R5 | L3 Change 完成 Completion Audit、两阶段 Review、Ready Gate、永久 CI 与正常 PR 合并 | `AGENTS.md` | satisfied | Completion Gate #143、CI #2297、PR #168 merge |

# Validation Matrix

| Layer | Result | Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或业务交互 |
| Backend/API/PostgreSQL Integration | passed | CI #2297 Stage 2 Platform / Stage 3A Database；Local Dev #120 PostgreSQL smoke |
| Contract / Generated Client | not_applicable | 无 Contract/OpenAPI/generated client diff；CI drift check 成功 |
| Real Full-stack Golden Path | passed | Local Dev #120；Internal V1-A #60 Compose Golden Path |
| Real Provider Probe | not_applicable | 不修改 Provider 外部 API；仅 fixture Key |
| Docs / Governance / Other | passed | Completion Gate #143；环境运行文档与 Blueprint 05 同步 |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取用户最终决定、目标分支 `AGENTS.md`、Blueprint 05 与环境运行文档。
- [x] change_coverage：双根、旧密码废弃、existing volume fail-closed、外部 Key 文件流向、symlink 防护、显式 reset、文档全部覆盖。
- [x] reverse_audit：旧路径不参与密码选择；TikHub/LLM 只进入外部根；本任务无页面能力，页面反向审计不适用。
- [x] unresolved_cleared：Requirement Traceability 无未满足项，不适用验证层均有范围依据。

# 两阶段 Review

## Requirement Review

通过，无遗漏。用户最终决定、`AGENTS.md`、Blueprint 05 与环境运行文档均已映射到 Change，并由实现、测试和文档闭环。

## Code Quality Review

通过，无 Serious / Important finding。

- 旧密码迁移 helper 不存在。
- 旧路径只用于明确拒绝、测试和文档说明，不参与当前密码选择。
- existing volume + missing internal password fail closed。
- 新数据库内部随机 Secret 安全生成；symlink 被拒绝。
- 外部 TikHub/LLM Key 不进入业务子进程普通环境变量。
- 变更仅涉及 7 个预期文件，无无关重构。

# PostgreSQL 密码语义

PostgreSQL 数据属于 cluster/database/table，密码属于 Role 认证。一个 cluster 可以存在多个 Role，每个 Role 有不同密码和权限；这些 Role 可以访问同一份或不同范围的数据库对象。不同密码本身不会创建、选择或映射不同的数据副本。

只修改应用侧 Secret 而不修改数据库内 Role 密码，会导致认证失败；如果在 PostgreSQL 内修改 Role 密码，并同步更新应用 Secret，访问的仍然是同一份数据。Docker 官方 PostgreSQL 镜像的初始化密码只对空数据目录首次初始化生效，已有 volume 不会因为重新提供一个初始化密码就自动修改数据库内 Role 密码。

# 最终验证证据

Ready commit：`637c2d21e38e8159f0566962cc7cee1ad15fb4db`

- Change Completion Gate #143 / run `32629799101`: success。
- CI #2297 / run `32629799158`: success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全绿。
- Local Dev Bootstrap #120 / run `32629799121`: success；Windows、Ubuntu、真实 PostgreSQL bootstrap smoke 全绿。
- Internal V1-A Deployable Stack #60 / run `32629799087`: success。
- Stage 8F #424、Stage 6 #294、Stage 7 Keyword Packs #1906、Provider Config Routing #2019、Scheduler Runtime #2246、Plan Occurrence #1904、Audit Correctness #1115：全部 success。
- PR #168：Ready 后正常合并。
- implementation merge commit：`874fd88d3b324bce706128c1f26aaee8a9f66195`。

# Git / 交付

- implementation branch: `feature/local-secret-root-alignment`
- implementation PR: `#168 统一本地与生产 Secret 运行根目录`
- implementation merge: `874fd88d3b324bce706128c1f26aaee8a9f66195`
- archive delivery: 本文件通过独立归档 PR 进入 `main`
