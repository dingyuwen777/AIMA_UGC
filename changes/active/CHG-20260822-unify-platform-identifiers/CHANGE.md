---
schema: rvc-change/v1
id: CHG-20260822-unify-platform-identifiers
title: 五平台机器标识统一
level: L3
status: in_progress
owner: chatgpt
branch: refactor/unify-platform-identifiers
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - contracts
  - collection
  - content
  - ingestion
  - frontend
  - migrations
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/contracts/
  - backend/src/aima_ugc/adapters/providers/tikhub/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/system/
  - frontend/src/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - contracts/
  - migrations/versions/
  - tests/
  - docs/blueprint/
  - docs/appendix/
  - docs/collection/
contracts:
  - CollectionPlatform
  - ProviderPlatformCapabilityV1.platform
  - CanonicalContentV1.platform
  - CanonicalCommentV1.platform
data_changes:
  - platform identifiers xhs -> xiaohongshu
---

# 目标

把 AIMA_UGC 当前所有**内部机器平台标识**统一为且仅允许：

```text
xiaohongshu
douyin
weibo
bilibili
kuaishou
```

小红书不再同时存在 `xhs` 与 `xiaohongshu` 两套内部身份。运行时代码、公共 HTTP Contract、generated client、Collection Plan/Run/Scope、TikHub Capability/Mapper、Canonical、Content、前端、测试和正式文档统一使用 `xiaohongshu`。

外部输入中的中文“`小红书`”仍作为源数据映射到 `xiaohongshu`；不再接受 `xhs` / `red` 作为 Excel 机器别名。历史 Change 与旧 Migration 保留当时事实，不改写历史。

# 可观察成功标准

- [ ] `CollectionPlatform` 只允许 `xiaohongshu / douyin / weibo / bilibili / kuaishou`；
- [ ] TikHub 小红书 Capability、Canonical Content/Comment Mapper 输出 `xiaohongshu`；
- [ ] Excel Profile 只把“小红书”与 `xiaohongshu` 映射到 `xiaohongshu`，不再接受 `xhs` / `red`；
- [ ] Collection Plan / Run / Scope / Batch Supplement / Frontend generated client 全部使用 `xiaohongshu`；
- [ ] 删除 `xhs <-> xiaohongshu` 运行时兼容映射，不保留兼容层；
- [ ] 新 Alembic Migration 一次性迁移当前持久化平台字段中的旧 `xhs`；
- [ ] Migration 在会造成业务身份唯一键冲突时 fail closed，不静默删除/合并 Content、Account 或历史来源；
- [ ] Migration downgrade 明确恢复本 Migration 迁移的 `xiaohongshu -> xhs` 数据语义，且仅作为回滚能力存在；
- [ ] 当前源码、generated、测试和正式文档存在永久门禁，禁止重新引入小写机器值 `xhs`（历史 Change、旧 Migration、原始第三方 Fixture 和本 Migration 除外）；
- [ ] OpenAPI / generated client 同步且 drift check 通过；
- [ ] PostgreSQL 空库升级、Migration downgrade/re-upgrade、目标迁移数据测试通过；
- [ ] Backend Unit / Contract / API / Integration 相关测试通过；
- [ ] Frontend lint / TypeScript 7 / Vue typecheck / Unit / build / Mock E2E 通过；
- [ ] Stage 8F 真实 Excel Full-stack Acceptance 继续通过；
- [ ] Blueprint / Appendix / Collection README 与代码一致；
- [ ] 合并前两阶段 Review 无未解决严重/重要问题；
- [ ] PR 合并到 `main` 后 Change 归档。

# 范围

## 修改

1. Pydantic HTTP Contract / OpenAPI / generated client 的平台枚举；
2. TikHub Capability、Mapper、Collection Runtime 和 Frontend 的小红书机器值；
3. Excel Import 平台输入归一化规则；
4. PostgreSQL 中保存平台值的稳定列，以及确实保存平台标识的当前 JSON 快照；
5. 一次性 Alembic Migration；
6. 相关 Unit / Contract / API / PostgreSQL Integration / Browser E2E / Full-stack 测试；
7. 当前正式文档；
8. 永久平台标识一致性门禁。

## 不修改

- TikHub endpoint 路径 `/xiaohongshu/...` 与真实 Provider JSON；
- 第三方 Raw Artifact / 原始 Fixture 内容；
- 外部内容 ID、评论 ID、Provider Operation 名称；
- AI taxonomy / Prompt；
- Job Runtime、Retry、费用策略；
- Docker / Compose / Internal V1-A；
- 历史 `changes/archive/` 与旧 Migration 文件名/内容。

# 已确认上游决定

用户明确要求：

> 系统内部不需要 `xhs/xiaohongshu` 兼容，所有平台字段统一为 `xiaohongshu / douyin / weibo / bilibili / kuaishou`，系统性修改、避免兼容层，并在验证后合并到主分支。

因此本 Change 不设置兼容窗口，也不保留运行时 alias。

# L3 方案比较

## 方案 A：保留 `xhs`，边界转换到 `xiaohongshu`

优点：公共 Contract 变化小。

缺点：永久维护两套平台身份，已经实际造成 Excel Batch 与 Collection 补采断点；与用户“不要兼容层”决定冲突。

结论：拒绝。

## 方案 B：全系统统一 `xiaohongshu` + 一次性 Migration

优点：从 Contract、Canonical、Collection、Content、Frontend 到数据库只剩一套机器身份；后续无需 alias；最容易长期维护和验证。

代价：公共 HTTP Contract 与 persisted data 均变化，需要 Migration、generated client 和完整回归。

结论：**采用**。

## 方案 C：只改代码，不迁移旧数据库

优点：实现最少。

缺点：旧 `xhs` 数据会变成不可见/重复身份，可能继续产生 `(platform, external_content_id)` 双记录。

结论：拒绝。

# 数据兼容与 Migration

## 升级

Migration 从当前 head `20260821_0023` 之后新增 revision，统一旧数据库中的 `xhs` 平台值。

升级前必须检测会造成唯一身份冲突的情况，至少包括：

```text
contents(platform, external_content_id)
accounts(platform, external_account_id)
collection_plan_platforms(plan_id, platform)
collection_scopes(run_id, platform, source_type, source_value, operation_group)
```

发现同一业务身份同时存在 `xhs` 与 `xiaohongshu` 时，Migration 明确失败，要求人工先处理冲突；不得猜测哪条历史应删除，也不得在 Migration 内静默合并 Content Version、Comment、Analysis、Export 或来源链。

无冲突时，Migration 一次性把所有当前正式持久化平台字段更新为 `xiaohongshu`。对 JSONB 只迁移仓库当前真实保存平台字段的固定快照结构，不对任意 JSON 文本做全文替换。

## 回滚

Downgrade 仅作为版本回滚机制，把本 Migration 统一后的正式小红书平台值恢复为旧 `xhs` 语义；它不代表运行时继续兼容旧值。

# 部署顺序

```text
代码 + Migration 同一 Release
→ 停止旧 API/Worker/Scheduler 写入
→ Alembic upgrade head
→ 新 API/Worker/Scheduler 启动
```

不允许新代码连接尚未迁移的旧库，也不允许旧代码继续向升级后的库写 `xhs`。

# 回滚

如果升级阶段因平台身份冲突失败：数据库事务回滚，旧代码保持可运行；先人工处理冲突后重试。

如果新代码上线前需要整体回退：停止新进程 → Alembic downgrade 到 `20260821_0023` → 恢复旧代码。

# 风险

- **数据身份冲突**：以 Migration fail-closed 处理，不静默丢历史；
- **Contract 破坏性变化**：同一 PR 同步 OpenAPI/generated/front-end/tests，不提供兼容值；
- **遗漏机器值**：新增仓库扫描门禁；
- **Raw 证据污染**：历史 Raw/Fixture 不做替换；
- **旧历史被改写**：archive Change / 旧 Migration 不修改。

# 实施任务

1. Red：新增平台 ID 门禁与核心 Contract/Mapper/Migration 期望，确认当前 `xhs` 状态真实失败；
2. 统一 HTTP Contract、Capability、Mapper、Excel Profile、Collection / Frontend 机器值；
3. 删除 Stage 8F 临时 `xhs/xiaohongshu` 兼容映射；
4. 新增 `20260822_0024` 一次性数据 Migration 与 PostgreSQL Integration；
5. 重新生成 OpenAPI / frontend generated client；
6. 更新全部受影响测试和正式文档；
7. 执行目标、相关与全量永久 CI；
8. 两阶段 Review，PR Ready 后合并；
9. 归档 Change。

# 验证计划

至少要求：

```text
uv run ruff format --check backend tests scripts migrations
uv run ruff check backend tests scripts migrations
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run pytest tests/integration/database -q
uv run pytest tests/integration/collection -q
uv run pytest tests/integration/content -q
uv run pytest tests/integration/ingestion -q
uv run alembic upgrade head
uv run alembic check
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run test:e2e:fullstack
```

最终以仓库实际 GitHub Actions 永久 Workflow 为合并门禁。

# 文档影响

至少检查并同步：

- `docs/blueprint/02-采集系统与数据标准化.md`
- `docs/blueprint/03-数据库与文件存储.md`
- `docs/blueprint/07-技术决策与实施门禁.md`
- `docs/blueprint/08-采集策略与平台能力.md`
- `docs/appendix/数据入口与统一入库实现.md`
- `docs/appendix/TikHub五平台真实响应与字段映射.md`
- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`
- `docs/collection/README.md`
- `frontend/README.md`

# Git / PR / 验证证据

开始 main：

```text
091fe8b78c118e31a2491b9477705679d6516058
```

分支：

```text
refactor/unify-platform-identifiers
```

PR、Red/Green、CI、Review、merge 与 archive 证据在实施过程中持续补充。
