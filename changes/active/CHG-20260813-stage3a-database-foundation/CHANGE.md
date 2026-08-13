---
schema: rvc-change/v1
id: CHG-20260813-stage3a-database-foundation
title: Stage 3A 数据库、Alembic 与基础持久化
level: L3
status: in_progress
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

# 目标

建立 Stage 3A 的数据库事实基线，使后续模块只能通过 Alembic 演进 Schema，并让 Stage 2 的 ArtifactMetadataPort 获得正式 PostgreSQL 实现；同时建立最小 System Settings 和 Provider 中立 Audit 持久化，以及可执行的表写 Owner 门禁。

# 成功标准

- [ ] 根目录建立可执行 Alembic 配置与 `migrations/`，API/普通进程不自动建表或自动迁移。
- [ ] 第一条 Revision 从空 PostgreSQL 18.4 建立 `artifacts`、`system_settings`、`audit_events`，并能 downgrade 到 base 后再次 upgrade 到 head。
- [ ] `artifacts` Schema 与现有 Stage 2 生命周期模型一致；不实现删除/保留 Job，不写死尚未批准的保留期限。
- [ ] PostgreSQL Artifact Metadata Repository 实现现有 `ArtifactMetadataPort` 的 pending/stored/linked/error 状态转换，并验证非法状态转换关闭失败。
- [ ] `system_settings` 只保存非敏感数据库设置；Secret 不进入该表。
- [ ] `audit_events` actor 保持 Provider 中立，可表达 system/principal，不绑定飞书私有 ID 或本地 users。
- [ ] 每张已建立表具有唯一 Owner，质量门禁不再以 `TABLE_OWNER_RULE_NOT_READY` 失败。
- [ ] CI 使用真实 PostgreSQL 18.4 验证 Migration、Repository 和表 Owner；Stage 1/2/Windows 既有门禁继续全绿。
- [ ] 受影响 README/Blueprint 同步当前事实，并清理与 Blueprint 1.7 冲突的旧本地登录/未经批准保留期表述。

# 范围

## 本次实现

- Alembic 配置、env、首条 Revision；
- 共享 SQLAlchemy MetaData；
- `artifacts`、`system_settings`、`audit_events` Table 定义；
- PostgreSQL Artifact Metadata、System Settings、Audit Repository；
- Stage 3A PostgreSQL 集成测试；
- 表 Owner 检查；
- Migration 运行/开发文档。

## 非目标

- Canonical Contract（Stage 3B）；
- 登录、本地密码、Session、CSRF、登录限流、MFA、飞书/OIDC 回调；
- Role/Permission/Principal 具体 Schema；
- `api_idempotency_records` actor 语义；
- Job Runtime、TikHub、Raw 采集；
- 自动 Artifact 删除、Retention Job 或具体 Raw/Audit 保留期限；
- 生产 Docker/Compose/Release。

# 方案比较

## A. 只在 Alembic Revision 写 DDL，运行时代码手写 SQL

不采用。Schema 会在 Migration 和 Repository 中形成两套难以校验的字段事实，后续 Owner/Repository 测试更容易漂移。

## B. 现在建立完整 ORM Base、Generic Repository、UnitOfWork

不采用。Stage 3A 只有三张共享基础表，完整 ORM/UoW 会提前引入 Stage 3D 的事务抽象和不必要的通用层。

## C. SQLAlchemy Core Table + Owner Repository + Alembic（采用）

共享 MetaData 只承担命名/Schema 注册；各 Owner 定义自己的 Table；PostgreSQL Adapter 使用 Core SQL 实现 Port/Repository；Alembic Revision显式创建/删除表。边界最少、可测试，且不会把业务模型绑定 ORM。

# 已确认关键决策

- PostgreSQL 18、SQLAlchemy 2、psycopg 3、Alembic 1.19.1 均复用当前锁定版本，不升级依赖。
- 当前第一版登录能力已明确延期；本 Change 不创建本地 Auth Schema。
- Artifact 保留/删除策略仍是用户决策门禁；本 Change 仅保留 `retention_class`/可空 `expires_at` 能力，不自动删除。
- Audit actor 使用 Provider 中立语义；未来第三方身份先映射内部 Principal 再写审计。

# Migration、部署与回滚

- 初始 Revision `down_revision = None`；空库 `upgrade head` 后必须可 `downgrade base` 再 `upgrade head`。
- API/Worker/Scheduler 启动不调用 Alembic；Migration 作为独立进程/命令运行。
- 当前无生产数据，因此不存在数据回填；生产 Release 仍为 No-Go。
- downgrade 仅作为开发/CI 验证，不替代未来生产备份回滚。

# 验证计划

按 Red → Green：先加入表达 Stage 3A Schema/Repository 的失败测试并观察缺失实现失败；再最小实现。最终执行目标测试、真实 PostgreSQL Migration/Repository 集成、Ruff、mypy、架构/Owner/Secret/文档检查和完整 CI。

# Git

- 基线 main：`1b1f21b214902922f3979523f642888773bb889c`
- 分支：`migration/stage3a-database-foundation`
- PR/CI/合并：实施后记录。
