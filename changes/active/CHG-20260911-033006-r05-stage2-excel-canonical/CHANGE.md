---
schema: coding-change/v1
id: CHG-20260911-033006-r05-stage2-excel-canonical
title: Roadmap 05 Stage 2 Excel 持久 Canonical
level: L3
status: in_progress
owner: dingyuwen777
branch: feat/r05-stage2-excel-canonical
created: 2026-09-11
updated: 2026-09-11
completion_gate: required
depends_on:
  - CHG-20260911-015500-r05-stage1-canonical-artifact
affected_areas:
  - ingestion
  - platform
  - storage
  - database
  - jobs
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/adapters/providers/imports/historical_chunk.py
  - backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/platform/storage/
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/
  - tests/
  - docs/blueprint/02_采集系统与数据标准化.md
  - docs/blueprint/03_数据库与文件存储.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/roadmap/05_可重放数据底座与监测重分类实施路线.md
  - changes/active/CHG-20260911-033006-r05-stage2-excel-canonical/CHANGE.md
contracts:
  - Canonical Artifact JSONL.gz file contract
  - Excel import job persistence and recovery contract
  - Historical/Data Import pure Canonical chunk contract
data_changes:
  - enforce one Canonical Artifact per Stage 2 parent
  - reject unsafe legacy Historical Chunk or active Job rows during migration
---

# 变更摘要

- **问题**：两个正式 Excel 入口仍在临时文件或带 Filter outcome 的旧 Historical Chunk 上执行，Stage 1 的 Canonical Artifact 尚未成为 Filter 的持久输入。
- **目标**：单文件 Import 与 Data Import Campaign 都固定为 `Mapper → linked Canonical Artifact → Filter → Dedup/row ledger → Content Owner`，并在重试、接管与取消时复用同一 Artifact。
- **边界**：只实现 Roadmap 05 Stage 2；不实现 TikHub、Replay/Backfill、UI、Provider 请求、生产部署或依赖升级。

# 已确认事实与决策

| 编号 | 事实 / 决策 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | Stage 1 已提供共享 Writer/Reader、完整性校验和 `canonical_artifact_links` | `changes/archive/2026-09/CHG-20260911-015500-r05-stage1-canonical-artifact/CHANGE.md` 与当前代码 | 复用既有能力，不建第二套 Artifact 生命周期 |
| E2 | 单文件 Import 当前从临时 `contents.jsonl` 直接 Filter | `backend/src/aima_ugc/bootstrap/import_worker.py` | 持久 Artifact 必须在 Filter 前 linked，Filter 只读 Reader 输出 |
| E3 | Historical converter 当前把 Mapper 与 Filter 合并并输出 `candidate/filtered/invalid` | `backend/src/aima_ugc/adapters/providers/imports/historical_chunk.py` | 新 Chunk 只保存合法 Canonical；Filter 移到消费阶段 |
| E4 | 用户已明确批准干净切换，不保留旧 Historical Chunk/Payload 兼容 | https://github.com/dingyuwen777/AIMA_UGC/issues/441 | Migration 发现不安全旧存量时失败关闭，不静默误读 |
| E5 | 本机 Docker/PostgreSQL 不可用；仓库无旧 Chunk Fixture/业务数据证据 | 本轮 `docker compose ps`、仓库搜索 | 本地不冒充真实数据库验证；PR PostgreSQL 18 CI 提供新鲜证据 |
| E6 | 开工基线是 `origin/main@ac0b66f89db0ac62091325061c51ffb51774c4e8` | 本轮 Git fetch/status | 从最新 main 的本地任务分支施工 |

# 目标、范围与非目标

## 成功标准

- [ ] 两个 Excel 入口的全部合法 Mapper 输出先成为 linked Canonical Artifact，再进入 Filter。
- [ ] matched、filtered 和后续 duplicate 的合法 observation 均保留在 Artifact；invalid 不伪造 Canonical且仍可对账。
- [ ] Filter/Dedup/Content Owner 与 `historical_fill_only` / `standard_observation` 业务结果保持不变。
- [ ] 重试、接管、取消复用唯一 Artifact，不产生平行副本、重复 Content 或失联 Artifact。
- [ ] 干净切换 Migration、Schema、Artifact、Job 与分层验证闭环。
- [ ] Review、PR CI、合并、main 新鲜验证、归档、Roadmap 与 Issue Closure 完成。

## 非目标

- 不实现 Roadmap 05 Stage 3 TikHub 或 Stage 4 Replay/Backfill。
- 不新增 Monitoring Membership、Filter History、Platform Registry、第二数据库或消息系统。
- 不修改公共 HTTP/OpenAPI、CanonicalContentV1、Brand/Vehicle Filter 业务语义、Content identity/Owner。
- 不调用真实 Provider，不部署或迁移生产，不升级依赖。

## 必须保持不变

- PostgreSQL 18、Python 3.14、根 uv 工程与单一 Durable Job Runtime。
- Source XLSX、Campaign/Item/Batch、逐行账本、Provider import lineage 与 Artifact 生命周期边界。
- Artifact I/O 不置于长数据库事务；业务可见提交继续受 Job Fence/取消门禁保护。

# 实施计划

1. **Red：持久 Artifact 与恢复语义**
   → 修改范围：目标 Unit/Integration/Schema/Migration tests
   → 预期结果：现状因 Filter 仍读临时文件、Historical Chunk 仍带 outcome、父级不唯一而失败
   → 验证：目标 pytest 与静态 Schema/Migration 检查
2. **Green：单文件 Import**
   → 修改范围：Artifact repository/query、Import Worker
   → 预期结果：Mapping 后创建或复用唯一 linked Artifact；Reader 完整预检后才向 Filter 提供本地输入
   → 验证：成功、filtered、retry/takeover/cancel、损坏 Artifact 与 Content 幂等
3. **Green：Data Import Campaign**
   → 修改范围：Historical converter/worker/repository/job/schema
   → 预期结果：Pure Canonical Chunk + 独立 invalid facts；消费阶段执行冻结 Filter 并保持两种 policy/ledger
   → 验证：matched/filtered/duplicate/invalid、重试/接管/取消、来源与 Artifact 完整性
4. **迁移、文档、完整验证与交付**
   → 修改范围：Migration、Blueprint/Appendix/Roadmap/README、Change
   → 预期结果：旧活跃任务/Chunk 失败关闭；长期事实同步；Review/CI/merge/main/archive/Issue 闭环
   → 验证：目标→模块→Contract/API→PostgreSQL/Migration→Full-stack→构建/治理

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 单文件 Import 先持久并复用唯一 linked Canonical Artifact，Filter 只读完整性校验后的 Artifact | https://github.com/dingyuwen777/AIMA_UGC/issues/441 | not_satisfied | 待 Red/Green 与恢复测试 |
| R2 | Data Import Campaign 生成 Pure Canonical Chunk，合法 observation 全保存，Filter 移到消费阶段 | https://github.com/dingyuwen777/AIMA_UGC/issues/441 | not_satisfied | 待 Red/Green 与 Chunk/Worker 测试 |
| R3 | invalid 保留可对账事实，既有 row ledger、来源链、Dedup、两种 policy 与 Content Owner 语义不变 | https://github.com/dingyuwen777/AIMA_UGC/issues/441 | not_satisfied | 待集成/反向能力审计 |
| R4 | 重试、接管与取消不产生平行 Artifact、重复 Content 或失联 Artifact | https://github.com/dingyuwen777/AIMA_UGC/issues/441 | not_satisfied | 待 Job/Artifact/PostgreSQL 测试 |
| R5 | 干净切换，不保留旧 Historical Chunk/Payload 兼容；不安全存量 Migration 失败关闭 | https://github.com/dingyuwen777/AIMA_UGC/issues/441 | not_satisfied | 待 Migration/registry/schema 证据 |
| R6 | 不扩大到 Stage 3/4、非目标、公共 HTTP/Canonical/依赖/生产动作 | `docs/roadmap/05_可重放数据底座与监测重分类实施路线.md` | not_satisfied | 待 diff/Contract/lock/Provider 反查 |
| R7 | 完成相称验证、独立 Review、PR/merge/main/archive/Roadmap/Issue 闭环 | https://github.com/dingyuwen777/AIMA_UGC/issues/441 | not_satisfied | 待交付生命周期证据 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Writer/Reader 接线、pure chunk、Filter、invalid、retry/cancel/takeover |
| 接口 / 契约 | required | Canonical 文件 Contract、Job Payload/registry、HTTP/OpenAPI 不漂移 |
| 集成 / 持久化 / 运行时依赖 | required | PostgreSQL 18 唯一关系、Migration、Artifact/Job/ledger/Content |
| 用户 / 工作流验收 | required | 单文件与 Campaign 两条完整 Excel 工作流 |
| 跨组件 Golden Path | required | API/DB/Worker/Content 既有 Full-stack 回归；无新 UI |
| 外部依赖 / Provider Probe | not_applicable | 文件导入不需要真实 Provider，本任务禁止外部付费调用 |
| 构建 / 打包 / 运行 | required | Ruff、mypy、wheel、migration upgrade/check/downgrade/upgrade |
| 文档 / 治理 / 其他 | required | Blueprint/Appendix/README/Roadmap、Owner/Secret/Change、Review/CI/Git |

# 风险、兼容、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| Artifact 竞争 | 同一父级并发创建可能产生平行副本 | PostgreSQL 唯一约束 + 先查/冲突失败关闭 + 重试复用 |
| 损坏 Artifact | 不能产生部分业务写入 | Reader 在首条输出前完成 SHA/size/gzip/JSON/Contract 全文件预检 |
| Historical invalid | Pure Canonical 不携带 invalid 行 | Chunk Item stats 保存行级最小 invalid facts并在消费阶段重建逐行终态 |
| 兼容 | 用户批准干净切换 | Job/Chunk 内部版本整体切换；Migration 对旧活跃存量 fail closed |
| 部署 | 仅正常应用+Migration 发布边界 | 本任务不执行生产部署/迁移；先升级 DB 后启动新 Worker |
| 回滚 | 新数据开始写入后不能简单运行旧 Worker | 应用回滚需同时恢复对应 DB/schema 与停止新 Job；生产方案不在本任务执行 |

# 文档影响

Docs Impact 为 `targeted`：同步 Blueprint 02/03、Appendix 08、Ingestion README 与 Roadmap 05 的当前实现事实；公共 API 无变化，不改用户产品能力说明。

# 执行清单

- [x] 读取项目规则、canonical Agent_Skills Source、Roadmap/Blueprint 与当前机器事实
- [x] 创建并复核 Issue #441、最新 main 与本地任务分支
- [x] 建立 Change、Requirement Traceability、验证矩阵和迁移/回滚边界
- [ ] Red 失败测试
- [ ] Green/Refactor 实现与目标回归
- [ ] 分层验证、Completion Audit 与独立 Review
- [ ] PR CI、guarded merge、main 新鲜验证、归档、Roadmap/Issue/分支收口

# 完成审计

- [ ] upstream_re_read：Ready 前重读 Issue、Roadmap Stage 2、当前代码/Contract/Schema/Migration 与最新 main。
- [ ] change_coverage：逐条比较上游要求→Change→实现/测试/文档，`not_satisfied` 清零。
- [ ] reverse_audit：从两类父级、Filter consumer、row ledger、Content Owner、retry/cancel/takeover 反向检查。
- [ ] unresolved_cleared：Review/CI/Issue/PR 未决项与临时验证资产清零。

# 两阶段 Review

待实现后由独立复核阶段从上游需求与风险重新建立检查表，再对 diff、测试、文档与证据逐项核对。
