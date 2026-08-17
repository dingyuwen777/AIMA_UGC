---
schema: rvc-change/v1
id: CHG-20260817-stage1-stage7-audit-correctness
title: 修复 Stage 1-7 审计发现的正确性与恢复缺口
level: L3
status: in_progress
owner: dingyuwen777
branch: fix/stage1-stage7-audit-correctness
created: 2026-08-17
updated: 2026-08-17
depends_on: [CHG-20260817-stage1-stage7-correctness]
affected_areas: [content, collection, platform, provider, database, migration, testing, ci, documentation]
affected_paths: [backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/platform/storage/, backend/src/aima_ugc/adapters/storage/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/entrypoints/, backend/src/aima_ugc/platform/jobs/, migrations/versions/, tests/, scripts/quality/, .github/workflows/, README.md, docs/, backend/src/aima_ugc/modules/system/README.md, backend/src/aima_ugc/modules/collection/README.md, backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml]
contracts: []
data_changes: [accounts, account_external_ids, contents, comments, artifacts]
---

# 背景与现状

当前 `main@fbe7abc28f66d038565993b0ea28c0cdc5ab31f1` 的 Stage 1—7 功能面已经建立，Stage 8 尚未开始。2026-08-17 全面一致性与代码质量审计重新对照代码、Migration、Contract、测试、Blueprint、README 与归档 Change 后确认：上一轮 `CHG-20260817-stage1-stage7-correctness` 已真实修复一批恢复、并发、Coverage 与乱序缺陷，但仍遗漏两个会影响当前阶段正确性的组合边界，以及若干与这些边界直接相关的测试、CI、运行说明和文档事实漂移。

本 Change 不是进入 Stage 8，也不是推翻现有架构；目标是把 Stage 1—7 已批准语义真正闭环到可进入下一阶段的状态。

# 目标

1. 修复稀疏 `observed_fields` 与乱序 Observation 组合下的 Content/Comment/Account Current 字段 freshness，确保较旧 Observation 只能补充尚未被更晚 Observation 建立的字段，不能回滚更晚字段。
2. 修复 Raw 文件已成功落盘但 Artifact Metadata 仍为 `pending` 时的崩溃恢复，使确定性已有 Raw 能重新校验并恢复 `stored`，避免把可确认结果错误降级为 `unknown` 或产生不必要的新 Provider Attempt。
3. 明确并修复 `account_external_ids` 的稳定身份冲突/乱序语义。
4. 对 Worker/Reaper 常驻运行边界、快手 `reply_count` Capability、关键日志、CI path/Secret/Architecture 门禁和正式文档状态做证据驱动的最小闭环；需要真实 Provider 事实时只在现有 Fixture/台账不足后执行受限 TikHub Probe。
5. 不提前实现 Stage 8、Release、认证授权、Docker/Compose、协调 Backup/Restore 或已经撤回的 Budget Runtime。

# 可观察成功标准

- [ ] 新增 PostgreSQL 回归先证明 sparse + out-of-order 会在旧实现失败，并覆盖 Content、Comment、Account 至少各一个关键字段组合；修复后通过。
- [ ] Current 的字段级 freshness 有明确机器事实；更晚 Observation 未观察的字段允许由较旧 Observation 补充，更晚已观察字段（包括允许的显式 null）不得被旧 Observation 回滚。
- [ ] `account_external_ids` 不再被旧 Observation 静默覆盖；稳定 ID 出现冲突时有明确、可测试的处理语义。
- [ ] 新增精确崩溃点回归：Raw 文件已写、metadata=`pending`、Attempt=`dispatching` 时 Recovery 复用有效 Raw，不再次发送同一 Attempt；损坏/缺失文件仍保守收敛。
- [ ] Artifact pending reconciliation 不绕过 gzip、RawEnvelope、lineage、SHA-256、byte_size 和 no-overwrite 安全边界。
- [ ] Worker/Reaper 当前运行边界与代码/文档一致：若现有阶段要求常驻入口则补最小 loop；若仓库明确把常驻服务管理留给 Release，则不提前实现，只修正文档中过强表述。
- [ ] 快手 `supports_reply_count` 只保留真实 Fixture/台账/受限 Probe 能证明且 Mapper 可消费的值；不猜字段。
- [ ] Stage 5 Raw/Dispatch CI 在 Storage Adapter/Platform Storage 变化时能触发关键回归。
- [ ] Secret Scan 覆盖当前真实 Provider Fixture/Change/文档高风险路径且不会把合法脱敏 Fixture 当真实凭据。
- [ ] Architecture/Table Owner 门禁至少自动检查当前 AGENTS 已明确的、可低误报验证的硬边界，不建设通用框架。
- [ ] README、Blueprint、模块 README、部署/测试说明和 Stage 7 Completion metadata 与最终机器事实一致；历史 Archive 过程不被无理由重写。
- [ ] 不新增/升级依赖，不改变五平台主 Operation、Scheduler `latest_only + max_catch_up_runs=0`、Canonical V1、Provider V1、Budget 回撤和 Stage 8/Release 非目标。
- [ ] 最终 PR 完成需求符合性与代码质量两阶段 Review；目标测试、相关 PostgreSQL Integration、Migration round-trip、Ruff、mypy、Contract、Architecture、Table Ownership、Secret、Docs、Frontend/主 CI 按影响范围取得新鲜成功证据。

# 范围

- Content Current/History 的字段级 freshness 与账号稳定 ID 语义。
- Artifact `pending` → 文件已存在的恢复对账。
- Provider Attempt Recovery 与 Raw replay 的相应接线。
- 直接相关 PostgreSQL Migration、Repository、测试和 CI。
- Worker/Reaper 当前阶段边界核对与最小修复/文档同步。
- 快手 reply-count Capability 的证据核对。
- 当前审计确认的 CI/Secret/Architecture/日志/文档一致性缺口。

# 非目标

- 不开始 Stage 8 HTTP CRUD、正式业务页面、认证授权、API 幂等 actor 等能力。
- 不实现 Production Docker/Compose、离线 Release、SBOM/签名、协调 Backup/Restore、维护 epoch 或 advisory write barrier；这些继续属于后续 Release 门禁。
- 不恢复请求次数/金额 Budget、Budget Account、Reservation Ledger 或 dormant Budget 接口。
- 不改变 TikHub 五平台已批准主 Operation，不建立自动 App/Web/Provider fallback。
- 不新增 Redis/Celery/Kafka/工作流引擎或新基础设施。
- 不升级 Python/Node/PostgreSQL/依赖版本。

# 必须保持不变

- 模块化单体与 API/Worker/Scheduler/Migration 分进程基线。
- Provider → immutable Raw → Mapper → Canonical → Ingestion → Owner Repository → PostgreSQL。
- Canonical V1 / Provider V1 公共 Contract 与生成 OpenAPI/Client 当前兼容边界。
- 外部 HTTP 不进入数据库事务；同一 Attempt 不隐藏网络重试。
- 已校验 Raw 存在时禁止再次调用 Provider；真实重发必须新建 Attempt。
- Scheduler 固定 `latest_only + max_catch_up_runs=0`。
- 快手正式 comments/sub-comments 保持 App 主链，Web 仅显式备用，无自动 fallback。
- Secret 只通过 `secret_ref`；TikHub Bearer 只发往批准 Origin。
- Budget Runtime 保持删除状态。
- Stage 8/Release 边界不提前实现。

# 方案比较与已确认决策

## A. 字段 freshness

### 方案 A1：继续使用整行 `last_seen_at` 并增加特殊判断

优点：改动小。

缺点：无法区分“更晚 Observation 未观察该字段”和“更晚已观察该字段”，无法正确处理稀疏事实；继续补条件只会叠加错误。

结论：不采用。

### 方案 A2：为每个 Current 字段增加独立 `*_observed_at` 列

优点：强类型、SQL 查询直观。

缺点：Content/Comment/Account 现有几十个稀疏字段会产生大量伴生列和 Migration 噪音，字段演进成本高；这些时间戳是内部 provenance，而非主要业务查询维度。

结论：可行但不推荐。

### 方案 A3：Current 行增加内部字段级 freshness JSONB（推荐）

为 `accounts/contents/comments` 增加只由 Content Owner 维护的 `field_observed_at` JSONB object，key 限制为该实体当前已批准的稳定字段路径，value 为 UTC ISO-8601 时间。首次写入按 `observed_fields` 建立；后续在行锁内逐字段比较：本次字段时间 >= 已记录时间才允许更新；更晚 Observation 未观察的字段没有该 key，因此允许较旧 Observation 补充。

指标仍保留现有 Metric Observation 历史；JSONB 只负责 Current freshness，不成为第二套业务数据结构。

选择理由：正确表达稀疏语义，改动局部，不改变公共 Contract，不为每个业务字段增加伴生列，且 PostgreSQL JSONB 已是现有依赖。

## B. 备用稳定账号 ID

`account_external_ids` 被正式设计为备用稳定身份。采用 fail-closed：同一 `account_id + id_type` 已存在且值不同，不做覆盖，抛出稳定身份冲突错误；相同值幂等。旧 Observation 因此不能回滚稳定 ID，也不需要为稳定 ID 引入可变历史。

若未来某个平台证明某类 alternate ID 实际可变，应作为新的身份语义 Change 重新设计，而不是当前静默覆盖。

## C. Raw pending crash recovery

采用最小增量 reconcile：保留现有三阶段 Artifact 生命周期，不把文件 I/O 放进 DB 事务；Recovery 找到 deterministic `pending` Raw 时，读取实际文件并执行与 replay 同级的 gzip/Contract/lineage 完整性校验，重算 hash/size 后 CAS `pending → stored`，再走现有 terminal/link 流程。损坏或缺失仍按当前保守 unknown 处理。

不采用“看到文件就直接标 stored”，也不把 `pending` 直接放宽给普通 replay。

# 兼容、Migration、部署与回滚

- 公共 HTTP/Pydantic Contract：目标是不变化。
- 数据库：预计追加一个向前 Revision，为 `accounts/contents/comments` 增加内部 `field_observed_at` JSONB；历史 Revision 不改写。
- 现有历史行迁移：旧行没有可靠字段级时间。Migration 只能用当前 `last_seen_at` 作为保守基线初始化“当前非空/已知字段”的 freshness；对于当前为 null 且历史是否观察过无法可靠推断的字段，不伪造已观察事实。具体 backfill 必须由代码/历史表能力验证后实现，并以测试证明不会让旧 Observation 回滚已知 Current。
- Artifact pending reconciliation 预计不需要 Schema 变化，优先复用现有 `sha256/byte_size/stored_at/storage_status`。
- 部署：本 Change 不建立生产部署流程；数据库升级仍按现有 Alembic 门禁。
- 回滚：代码回滚需与新 Revision 兼容评估；若新增 freshness 列，downgrade 会删除内部 provenance，已有业务 Current 值不应被删除。正式生产回滚仍属于未来 Release 设计。

# 安全、性能与运维风险

- freshness JSONB 只保存字段名与时间，不保存 Secret/Provider Raw。
- 更新在现有 Content Owner 行锁内完成，不增加跨表分布式锁。
- pending Raw reconciliation 必须防路径逃逸、篡改、错误 lineage 和不完整 gzip；不得把任意文件提升为 stored。
- 不因本 Change 打开任意 Base URL、自动 fallback 或隐藏网络 retry。
- 字段 map 大小由固定字段集合约束，当前规模不会形成无界 JSONB。

# 分步计划

[步骤 1：建立 Red]
→ 修改范围：Content/Artifact/Provider Recovery 目标测试、必要 CI
→ 预期结果：旧实现分别因 sparse+out-of-order、pending Raw crash point、alternate ID conflict 的目标行为失败
→ 验证方式：目标 PostgreSQL/Unit Workflow，读取失败数和具体断言

[步骤 2：字段 freshness + Migration]
→ 修改范围：Content tables/Repository、新 Alembic Revision、Content tests
→ 预期结果：逐字段 freshness 正确，旧 Observation 只补缺失字段，不回滚更晚字段
→ 验证方式：Content PostgreSQL 回归、Migration previous→head/base round-trip、alembic check

[步骤 3：稳定 alternate ID]
→ 修改范围：Content Repository/tests/Blueprint
→ 预期结果：相同 ID 幂等，不同 ID fail-closed，乱序不回滚
→ 验证方式：目标 PostgreSQL tests

[步骤 4：pending Raw reconciliation]
→ 修改范围：Artifact metadata/Raw/Provider Recovery/tests
→ 预期结果：已有有效 pending Raw 恢复并 replay；损坏/缺失保守 unknown；同一 Attempt 不重发
→ 验证方式：Unit + PostgreSQL Recovery 回归

[步骤 5：审计直接相关 P2]
→ 修改范围：Worker/Reaper 边界、Kuaishou Capability、CI paths、Secret/Architecture quality、结构化日志
→ 预期结果：只修已证实缺口，不扩大 Stage
→ 验证方式：目标 Unit/Integration/quality tests；必要时受限 TikHub Probe

[步骤 6：长期事实同步]
→ 修改范围：README、Blueprint、模块 README、部署/测试说明、Pricing 注释、Stage7 Completion metadata
→ 预期结果：当前文档与机器事实一致，历史过程保留
→ 验证方式：Docs/Change/Secret 门禁 + 人工三向复核

[步骤 7：两阶段 Review 与集成]
→ 修改范围：完整 PR diff
→ 预期结果：需求符合性与代码质量无未解决 P0/P1/P2 blocker
→ 验证方式：相关完整 CI、PR review、合并后 main 新鲜验证

# 验证计划

目标验证至少包括：

```text
uv run pytest tests/integration/content -q
uv run pytest tests/unit/content -q
uv run pytest tests/unit/platform tests/integration/collection -q
uv run pytest tests/unit/collection tests/unit/jobs -q
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
uv run python scripts/contracts/generate.py --check
uv run python scripts/contracts/check_compatibility.py
```

并按新 Revision 验证上一正式 Revision → head、base → head、downgrade/upgrade。

# 文档影响

预计检查并按最终事实同步：

- `README.md`
- `docs/blueprint/03-数据库与文件存储.md`
- `docs/blueprint/06-开发约束与分阶段实施.md`
- `docs/blueprint/07-技术决策与实施门禁.md`
- `docs/blueprint/README.md`
- `docs/环境运行与部署.md`
- `docs/测试与调试说明.md`
- `backend/src/aima_ugc/modules/content/README.md`
- `backend/src/aima_ugc/modules/collection/README.md`
- `backend/src/aima_ugc/modules/system/README.md`
- `changes/archive/2026-08/CHG-20260815-stage7-completion/CHANGE.md` 的最终 metadata

# Git

- 基线 main：`fbe7abc28f66d038565993b0ea28c0cdc5ab31f1`
- 开发分支：`fix/stage1-stage7-audit-correctness`
- PR：尚未创建
- 合并：尚未执行
- Change：`in_progress`
