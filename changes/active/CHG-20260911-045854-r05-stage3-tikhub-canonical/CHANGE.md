---
schema: coding-change/v1
id: CHG-20260911-045854-r05-stage3-tikhub-canonical
title: Roadmap 05 Stage 3 TikHub 持久 Canonical
level: L3
status: in_progress
owner: dingyuwen777
branch: feat/r05-stage3-tikhub-canonical
created: 2026-09-11
updated: 2026-09-11
completion_gate: required
depends_on:
  - CHG-20260911-015500-r05-stage1-canonical-artifact
affected_areas:
  - collection
  - platform
  - storage
  - database
  - jobs
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py
  - backend/src/aima_ugc/platform/storage/
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/
  - tests/
  - docs/blueprint/02_采集系统与数据标准化.md
  - docs/blueprint/03_数据库与文件存储.md
  - docs/appendix/02_TikHub五平台真实响应与字段映射.md
  - docs/roadmap/05_可重放数据底座与监测重分类实施路线.md
  - changes/active/CHG-20260911-045854-r05-stage3-tikhub-canonical/CHANGE.md
contracts:
  - TikHub Discovery final Canonical persistence boundary
  - Canonical Artifact provider-attempt parent uniqueness
data_changes:
  - enforce one Canonical Artifact per TikHub search Provider Attempt
---

# 变更摘要

- **问题**：TikHub Discovery 已持久化 Provider Request/Attempt、Raw 与 Candidate，但最终用于 Brand/Vehicle Filter 的合法 Canonical 仍只存在于 Worker 内存，无法作为后续 Replay 的可靠输入。
- **目标**：每个有界 Search Provider Attempt 把该页所有最终 Filter 输入写成唯一 linked `canonical-content.v1` JSONL.gz；共享 Reader 完整预检后，现有 Filter/Ingestion 才消费这些记录。
- **边界**：只实现 Roadmap 05 Stage 3；不实现 Replay/Backfill、UI/API、生产动作或依赖升级，不调用真实付费 TikHub。

# 已确认事实与设计决定

| 编号 | 事实 / 决定 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | Stage 1 已提供共享流式 Writer/Reader、完整性校验和 Scope/Provider Attempt 父级关系 | 当前 `platform/storage/canonical.py`、`canonical_artifact_links` 与 Stage 1 archive | 复用现有 Artifact 生命周期，不建第二套 Dataset |
| E2 | 当前 Discovery 以一个 Search Provider Attempt 返回一个有界页面，并逐条执行 Mapper、必要 Detail fallback、Filter、Ingestion | `bootstrap/collection_scope.py` 与 TikHub runtime | Search 页面是现有最小稳定 Chunk；不改变分页或 Provider 请求身份 |
| E3 | 最终 Filter 输入可能来自 Search，也可能来自 Detail；Canonical 自身 Source 保留实际 Attempt/Raw/Candidate locator | 当前 Canonical Contract 与 Mapper | Artifact 绑定页面 Search Attempt，逐行 Source 保留 Detail 来源，形成 Run/Scope/Search Attempt/实际 Raw/Candidate 全链 |
| E4 | Provider Attempt 父级当前未实施唯一约束，无法安全收敛 Worker 重试/接管后的同页 Artifact | 当前表、Migration 0048/0049 与 repository | Stage 3 增加最小 partial unique index和失败关闭 Migration |
| E5 | Filter 必须实际消费共享 Reader 输出，而不是只旁路存档 | Issue #444 AC1–AC4、Roadmap 05 Stage 3 | Writer 完成 linked 且 Reader 全文件预检后才允许 Resolver/Filter/Ingestion |
| E6 | 开工基线是 `origin/main@7ca035fc456cb0753420b5795cd06a701e260399` | 本轮 Git fetch/status | 从最新 main 的本地任务分支施工 |

# 目标、范围与非目标

## 成功标准

- [ ] Search match、Search miss→Detail match、Search miss→Detail miss 都先形成可重用 linked Canonical Artifact，再进入最终 Filter。
- [ ] 一个 Search Attempt 对应一个有界 Artifact；Writer 竞争、崩溃重试、取消与接管均重读胜出 Artifact并校验内容完全一致。
- [ ] filtered、重复 identity、多 Brand/Vehicle 的合法 final observation 均保留；invalid 只保留 Raw/Candidate/error 事实。
- [ ] Provider 请求次数、计费、Raw、Candidate、分页、Detail fallback、Filter、Dedup 与 Content Owner 业务语义不变。
- [ ] 本地分层验证、Completion Audit、独立两阶段 Review、PR/main/归档/Roadmap/Issue 生命周期闭环。

## 非目标

- 不实现 Roadmap 05 Stage 4 Replay、历史 Backfill 或新用户入口。
- 不新增 Monitoring Membership、Filter History、Platform Registry、第二数据库、消息系统或平行 Ingestion。
- 不修改公共 HTTP/OpenAPI、`CanonicalContentV1`、Filter 业务语义、Content identity/Owner。
- 不调用真实付费 Provider，不部署或迁移生产，不升级依赖。

## 必须保持不变

- PostgreSQL 18、Python 3.14、根 uv 工程与单一 Durable Job Runtime。
- Provider Request/Attempt 幂等、Raw replay、Candidate-before-Mapper、Search→Detail fallback、分页、费用与恢复边界。
- Artifact 字节 I/O 不放入长数据库事务；业务写入继续受当前 Job Fence 与取消门禁保护。

# 实施计划

1. **Red：Artifact 接线、父级唯一性与恢复行为**
   → 修改范围：Collection Unit/Integration、Schema/Migration、Worker wiring tests
   → 预期结果：现状因 Filter 仍直接消费内存 Canonical、Provider Attempt 不唯一而失败
   → 验证：目标 pytest 与静态 Schema/Migration 检查
2. **Green：Search Attempt 有界 Canonical Chunk**
   → 修改范围：`collection_scope.py`、Worker Artifact 装配、Artifact repository/schema/Migration
   → 预期结果：先完成当前 Search/Detail final 选择，再写入或复用唯一 Artifact；Reader 全预检且与确定性 Mapper 输出一致后交给 Filter
   → 验证：Search/Detail/filtered/duplicate/multi-evidence/invalid 与请求计数
3. **Green：恢复、取消、接管与损坏数据 fail-closed**
   → 修改范围：Collection Runtime/PostgreSQL workflow tests
   → 预期结果：Raw/Canonical 均复用，竞争收敛，不产生重复 Content；损坏 Artifact 不产生部分 Filter/Ingestion
   → 验证：retry/recovery/cancel/takeover/corruption 场景
4. **文档、完整验证与交付**
   → 修改范围：Blueprint/Appendix/Change 与交付对象
   → 预期结果：长期事实同步；Review、CI、merge、main fresh、native archive、Roadmap/Issue 闭环
   → 验证：目标→模块→Contract/DB/Migration→Full-stack→构建/治理

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Discovery 固定为 Raw/Candidate/Mapper/Detail final→Artifact→Reader→Filter→Existing Ingestion | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC1 | not_satisfied | 待实现与测试 |
| R2 | Search match 与 Detail match 保存正确 final Canonical | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC2,AC3 | not_satisfied | 待实现与测试 |
| R3 | Detail miss filtered、重复 identity 与多 Brand/Vehicle 的合法 observation 仍保留 | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC4,AC5,AC6 | not_satisfied | 待实现与测试 |
| R4 | retry/recovery/cancel/takeover 复用唯一 linked Artifact，保持 Fence 与 Content 幂等 | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC7 | not_satisfied | 待实现与测试 |
| R5 | invalid 不伪造 Canonical，Raw/Candidate/error ledger 保持可追溯 | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC8 | not_satisfied | 待实现与测试 |
| R6 | 不改变 Provider/费用/Raw/分页/Candidate/Detail 决策，且不增加真实请求 | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC9 | not_satisfied | 待实现与回归 |
| R7 | 复用真实 Collection 父级、共享 Artifact 生命周期，不建立第二套系统 | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC10 | not_satisfied | 待实现、Schema/Migration 与架构审查 |
| R8 | 分层验证、Review、PR/main/archive/Roadmap/Issue 完整闭环，且不执行非目标 | https://github.com/dingyuwen777/AIMA_UGC/issues/444#AC11,AC12 | not_satisfied | 待生命周期完成 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / Unit / Component | required | final 选择、Writer/Reader 接线、Filter、invalid、duplicate、多 Evidence |
| 接口 / 契约 | required | Canonical 文件 Contract、Provider/Job/HTTP/OpenAPI 不漂移 |
| 集成 / 持久化 / 运行时依赖 | required | PostgreSQL 18 唯一关系、Migration、Artifact/Raw/Candidate/Content |
| 用户 / 工作流验收 | required | TikHub Discovery Search/Detail/filtered 完整工作流（Fake Transport） |
| 跨组件 Golden Path | required | API/DB/Worker/Content 既有 Full-stack 回归；无新 UI |
| 外部依赖 / Provider Probe | not_applicable | Fixture/Fake Transport 足以验证正式生产链；本任务禁止付费调用 |
| 构建 / 打包 / 运行 | required | Ruff、mypy、wheel、migration upgrade/check/downgrade/upgrade |
| 文档 / 治理 / 其他 | required | Blueprint/Appendix/Roadmap、Owner/Secret/Change、Review/CI/Git |

# 风险、兼容、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| Artifact 竞争 | 同页重试/接管可能并发生成副本 | Provider Attempt partial unique index + 先查/冲突重读 + Reader 与确定性 Mapper 输出逐行等值校验 |
| 损坏 Artifact | 不能产生部分 Filter 或业务写入 | Reader 在首条输出前完成 SHA/size/gzip/JSON/Contract 全文件预检 |
| Detail lineage | 页面 Artifact 可包含 Detail-derived final Canonical | 父级绑定 Search Attempt，Canonical Source 保留实际 Detail Attempt/Raw/item locator；测试反向验证全链 |
| 兼容 | 内部持久关系增强，无公共 Contract 变化 | 既有 Provider/Filter/Ingestion 行为与生成 Contract 保持；Migration 对冲突旧关系失败关闭 |
| 部署 | 正常应用+Migration 发布边界 | 本任务不执行生产部署/迁移；先升级 DB 后启动新 Worker |
| 回滚 | 新 Canonical 关系开始写入后旧应用可忽略新 Artifact | 应用可回滚；Schema downgrade 仅在确认无依赖数据后执行，生产方案不在本任务执行 |

# 文档影响

Docs Impact 为 `targeted`：同步 Blueprint 02/03 与 TikHub 实现 Appendix 的当前链路、Artifact/lineage/recovery 事实；Roadmap 状态只在 implementation merge 与 main fresh 证据后单独收口。公共 API 与用户能力不变。

# 执行清单

- [x] 读取项目规则、canonical Agent_Skills Source、Roadmap/Blueprint 与当前机器事实
- [x] 创建并复核 Issue #444、最新 main 与本地任务分支
- [x] 建立 Change、Requirement Traceability、验证矩阵和迁移/回滚边界
- [ ] Red 失败测试
- [ ] Green/Refactor 实现与目标回归
- [ ] 分层验证、Completion Audit 与独立 Review
- [ ] PR CI、guarded merge、main 新鲜验证、归档、Roadmap/Issue/分支收口

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 两阶段 Review

- 待实现候选形成后独立重建 Issue/Roadmap 完成定义并审查 diff、测试、Migration、文档与恢复风险。

# 完成证据与状态

当前为开工记录；尚未宣称实现、测试、Review 或交付完成。
