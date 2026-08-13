---
schema: rvc-change/v1
id: CHG-20260813-stage3a-database-foundation
title: Stage 3A 数据库、Alembic 与基础持久化
level: L3
status: done
owner: dingyuwen777
branch: migration/stage3a-database-foundation
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [database, platform, system, migration, ci]
affected_paths: [migrations/, alembic.ini, backend/src/aima_ugc/platform/database/, backend/src/aima_ugc/platform/storage/, backend/src/aima_ugc/modules/system/, backend/src/aima_ugc/adapters/persistence/postgres/, tests/, scripts/quality/check_table_ownership.py, .github/workflows/ci.yml, README.md, docs/blueprint/]
contracts: []
data_changes: [artifacts, system_settings, audit_events]
---

# 结果

Stage 3A 已完成并合并到 `main`：

- 根 `alembic.ini` + `migrations/`，首条 Revision `20260813_0001`；
- `aima_ugc.database_schema` + SQLAlchemy Core `MetaData` 机器注册入口；
- `artifacts`（Owner=`platform`）、`system_settings` / `audit_events`（Owner=`system`）；
- PostgreSQL Artifact Metadata、System Settings、Provider 中立 Audit Repository；
- `Table.info['owner']` + `check_table_ownership.py` 唯一 Owner 门禁；
- 独立 `Stage 3A Database` CI：PostgreSQL 18.4 Migration、drift、Repository、downgrade/re-upgrade；
- README、环境运行文档和 Blueprint 03/06/07/导航同步，Blueprint 07 为 1.8。

# 成功标准

- [x] 根目录建立可执行 Alembic 配置与 `migrations/`，API/普通进程不自动建表或自动迁移。
- [x] 第一条 Revision 从空 PostgreSQL 18.4 建立 `artifacts`、`system_settings`、`audit_events`，并能 downgrade 到 base 后再次 upgrade 到 head。
- [x] `artifacts` Schema 与 Stage 2 生命周期一致；不实现删除/保留 Job，不写死尚未批准的保留期限。
- [x] PostgreSQL Artifact Metadata Repository 支持 pending/stored/linked/error 状态转换，并验证非法转换关闭失败。
- [x] `system_settings` 定位为非敏感数据库设置；Secret 继续位于 Secret 边界。
- [x] `audit_events` actor Provider 中立，可表达 system/principal，不绑定飞书私有 ID 或本地 users。
- [x] 每张已建立表具有唯一 Owner，质量门禁不再使用 `TABLE_OWNER_RULE_NOT_READY` 占位失败。
- [x] 真实 PostgreSQL 18.4 已验证 Migration、Repository、Owner；Stage 1/2/Windows 既有门禁继续通过。
- [x] README/运行文档/Blueprint 已同步，并删除旧本地 Auth 与未批准固定保留期残留。

# 最终方案

采用 **SQLAlchemy Core Table + Owner Repository + Alembic**：共享 MetaData 负责机器 Schema 注册，各 Owner 定义自己的 Table，PostgreSQL Adapter 使用 Core SQL，Revision 显式冻结已批准 Schema，`alembic check` 校验运行时 Table 与 Migration 不漂移。

未采用：

1. 只在 Alembic Revision 写 DDL、Repository 再维护另一套字段 SQL；
2. 当前阶段提前建立完整 ORM Base、Generic Repository、UnitOfWork。

# 关键边界

- 不升级依赖；继续使用锁定 PostgreSQL 18 / SQLAlchemy 2 / psycopg 3 / Alembic 1.19.1。
- 不创建本地 `users/sessions/auth_login_attempts`，不实现登录、Session、飞书/OIDC、Role/Permission/Principal。
- 不创建 actor-bound `api_idempotency_records`。
- Artifact `retention_class` / 可空 `expires_at` 只预留表达能力；具体保留/删除期限仍走用户决策门禁。
- `PostgresArtifactMetadataRepository` 是 session-bound Owner Repository；调用方必须为各元数据阶段使用短事务，不能把 ArtifactStore 文件 I/O 包进同一长事务。跨业务 `linked`/UoW 协调属于后续事务编排阶段。
- Audit Repository 只提供 append；actor 仅使用 Provider 中立 `system/principal` 语义。
- API/Worker/Scheduler 启动不调用 Alembic；Migration 仍是独立进程/命令。

# TDD 与验证

## Red

PR #9 Red Run `31699937100`：`tests/unit/database/test_stage3a_schema.py` 在实现前因 `ModuleNotFoundError: No module named 'aima_ugc.database_schema'` 正确失败；锁定环境、本地双服务 smoke 和 Contract 前置正常。

## Green

最终 PR 候选 head `df5260a2936029e872f88bc8f4b93e6769c738b0`，PR CI Run `31705679434`：

- `Stage 1` success；
- `Stage 2 Platform` success；
- `Stage 3A Database` success；
- `Windows bootstrap` success。

`Stage 3A Database` 实际验证：

```text
Schema/Owner
→ alembic upgrade head
→ alembic current
→ alembic check
→ Repository Integration
→ alembic downgrade base
→ 验证三张应用表已移除
→ alembic upgrade head
→ alembic check
```

PR #9 已 squash merge，合并提交 `8f0b763dc33702d66e918f324eef84f1e883a0e6`。

合并后 `main` CI Run `31705968179` 在该提交上再次验证：

- `Stage 1` success；
- `Stage 2 Platform` success；
- `Stage 3A Database` success；
- `Windows bootstrap` success。

# 两阶段 Review

## 需求符合性

最终差异只覆盖 Stage 3A：Schema/Alembic/三张基础表/Repository/Owner/CI/文档；没有进入 Canonical、Job Runtime、TikHub、认证、自动 Retention 或生产 Release，也没有写入任何未批准的保留期限。

## 代码质量

Review 修复：

1. Stage 3A 单元测试只要求三张基础表存在且 Owner 正确，不禁止后续阶段扩表；
2. PostgreSQL Artifact Repository 明确为 session-bound / caller-owned short transaction，禁止把文件 I/O 包进同一数据库事务；跨业务 UoW 留后续阶段。

Migration 与运行时 Table 已由 `alembic check` 验证零漂移；Repository 不自行 commit；Artifact 状态更新使用当前状态条件防止非法/竞争转换。未发现剩余严重或重要问题。

# 文档

- `README.md`：Stage 3A 当前事实、独立 CI、下一步 Stage 3B；
- `docs/环境运行与部署.md`：本地 Migration 命令、downgrade 风险、生产仍 No-Go；
- Blueprint 03：三张基础表、Owner、Migration、ArtifactStore 接口、未决 Retention；
- Blueprint 06：Stage 3A 已完成，下一步 Stage 3B；
- Blueprint 07：1.7 → 1.8，固化 Stage 3A 技术事实和 Go/No-Go；
- Blueprint README：当前状态与 Stage 3B 路线。

# Migration、部署与回滚

- 初始 Revision `down_revision=None`；已验证空库 `base → head → base → head`。
- 当前无生产数据，无数据回填。
- `downgrade base` 只作为隔离开发/CI 可逆性证据；未来生产回滚必须依赖 Release/Backup Set，不机械 downgrade。
- 生产 Release 仍 No-Go。

# Git

- 基线 main：`1b1f21b214902922f3979523f642888773bb889c`
- 开发分支：`migration/stage3a-database-foundation`
- PR：#9 `建立 Stage 3A 数据库与 Alembic 基线`，已合并。
- 代码合并提交：`8f0b763dc33702d66e918f324eef84f1e883a0e6`。
- 合并后 main CI：Run `31705968179`，四 Job 全部 success。
