---
schema: coding-change/v1
id: CHG-20260911-045854-r05-stage3-tikhub-canonical
title: Roadmap 05 Stage 3 TikHub 持久 Canonical
level: L3
status: ready_for_review
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
| R1 | Discovery 固定为 Raw/Candidate/Mapper/Detail final→Artifact→Reader→Filter→Existing Ingestion | #444 / AC1 | satisfied | `collection_scope.py` 先完成页面 Search Mapper 与必要 Detail fallback，再调用共享 Writer/Reader；`_process_search_content()` 只接收 Reader 返回且与确定性 Mapper 输出相等的 final Canonical。 |
| R2 | Search match 保存 Search-derived final Canonical，Filter 消费 Reader 输出 | #444 / AC2 | satisfied | 参数化 PostgreSQL 工作流的“脱敏”场景断言两条重复行均保留 Search Attempt Source；目标 Unit 证明 Filter 输入来自 Writer 后的 Reader 返回值。 |
| R3 | Search miss→Detail match 保存 Detail-derived final Canonical并保持 Content 收敛 | #444 / AC3 | satisfied | 参数化工作流的“图文”场景断言 Artifact 行保留实际 Detail Attempt Source；Decision Bridge 证明 Search 与全部 Detail Candidate 仍收敛为同一 Content。 |
| R4 | Detail miss 的 final Canonical 仍持久化，随后 filtered 且不进入 Content | #444 / AC4 | satisfied | Detail miss Unit 证明 final Canonical 形成后才记录 Search/Detail Candidate filtered；同一 final 输入通过共用页面 Writer/Reader 边界。 |
| R5 | 多 Brand/Vehicle Evidence 保持冻结 Snapshot、Brand role 与 Filter 语义 | #444 / AC5 | satisfied | 新层只序列化/反序列化同一 Canonical，仍把同一冻结 Snapshot 与完整 `BrandVehicleResolution` 交给 Content Owner；现有多品牌 Resolver 回归在完整 Unit 中通过。 |
| R6 | 重复 Content identity 的合法 observation 保留，Existing Dedup 继续幂等收敛 | #444 / AC6 | satisfied | PostgreSQL 工作流为同一 Search identity 放入两行并断言 Artifact 两行都存在、最终 Content 只有一个。 |
| R7 | retry/recovery/cancel/takeover 复用唯一 linked Artifact，保持 Fence 与 Content 幂等 | #444 / AC7 | satisfied | Provider Attempt partial unique index + 先查/竞争后重读；目标 Unit 证明匹配 Artifact 直接复用、漂移失败关闭；现有 Raw takeover、取消、Fence、Content 幂等回归保留且所有 Executor 装配已接入共享 Store。竞争产生的未绑定 stored 副本沿用既有 orphan cleanup。 |
| R8 | Mapper invalid 不伪造 Canonical，Raw/Candidate/error ledger 保持可追溯 | #444 / AC8 | satisfied | Search/Detail Mapper 的 `record_candidate_failure(... result="invalid")` 边界未移动，Writer 只接受已构造的 `CanonicalContentV1`；既有 Mapper/Candidate 失败回归继续通过。 |
| R9 | 不改变 Provider/费用/Raw/分页/Candidate/Detail 决策，且不增加真实请求 | #444 / AC9 | satisfied | 实现只拆分 prepare/process 并在两者间接入 Artifact；Provider dispatch/operation/pricing/Raw/pagination 未改。工作流固定断言 Search+Detail 仍为 2 次 Request/Attempt/Transport 调用，重复 Search identity 未增加 Detail 请求。 |
| R10 | 复用真实 Collection 父级、共享 Artifact 生命周期，不建立第二套系统 | #444 / AC10 | satisfied | 复用 `CanonicalArtifactWriter/Reader`、`ArtifactService/Store` 和 `canonical_artifact_links`；Artifact 绑定真实 Search Provider Attempt，Migration `0050` 在含糊旧关系上失败关闭后建立唯一索引，无新 Run/Dataset/Filter/Ingestion。 |
| R11 | 完成相称验证、两阶段 Review、Completion Audit、PR/main 交付且不执行非目标 | #444 / AC11 | explicitly_deferred | 本地分层验证、Completion Audit 与 Review 已完成；真实 PostgreSQL 18、exact-head CI、guarded merge 与 main fresh 必须在本 Ready 提交后依次执行。未调用付费 Provider、未部署或迁移生产、未升级依赖。 |
| R12 | Change 原生归档、Roadmap Stage 3/4 状态收口并关闭 Issue | #444 / AC12 | explicitly_deferred | 原生归档、Roadmap closure PR/main fresh、Issue 验收关闭与分支清理只能在实现 PR 合并后执行，不能在当前记录预先冒充。 |

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
- [x] Red 失败测试
- [x] Green/Refactor 实现与目标回归
- [x] 分层验证、Completion Audit 与独立 Review
- [ ] PR CI、guarded merge、main 新鲜验证、归档、Roadmap/Issue/分支收口

# 完成审计

- [x] upstream_re_read：2026-09-11 Ready 前重读 Issue #444、Roadmap 05 Stage 3、Blueprint 02/03、当前 TikHub Runtime、Canonical/Artifact Contract、Schema/Migration、CI 与 `origin/main@7ca035fc`；main 未漂移，Issue/PR 仍 open。
- [x] change_coverage：从 Issue AC1–AC12 与 Roadmap Stage 3 必须完成/退出条件逐条反查 Change、实现、测试和文档；R1–R10 已有直接实现或测试证据，R11–R12 仅保留必须发生在 Ready 后的外部生命周期，`not_satisfied` 已清零。
- [x] reverse_audit：从 Search/Detail final Canonical、Provider Attempt 父级、Artifact Reader、冻结 Resolver、Candidate/Decision、Content Owner 反向检查；又从 Worker 构造、全部 Scope Runtime 测试、唯一索引/Migration、orphan cleanup 与无新 HTTP/UI 消费者反查，未发现绕过完整性预检或第二套写入路径。
- [x] unresolved_cleared：首轮 Review 发现集成测试把已命中 Search 的行误判为 Detail Source；已参数化为 Search/Detail 两条来源场景并 re-review。当前无 blocker/high/medium Finding；本机无 PostgreSQL/Docker 的限制明确交给 PR CI，未冒充通过。

# 两阶段 Review

- **需求与风险重建**：Review Target 为 `7ca035fc...e20f7b96`。从 Issue #444、Roadmap 05 Stage 3 与当前 Provider/Raw/Candidate/Mapper/Detail/Filter/Content/Artifact 事实独立重建 R1–R12，没有使用本 Change 充当上游需求全集。
- **实现与证据对照**：逐项审查页面有界边界、Search/Detail final 选择、Reader 前置、重复与 filtered 保留、Provider 调用计数、Source lineage、唯一关系、Migration、竞争恢复、取消/Fence、invalid 和文档。发现一项测试证据错误：Search Fixture 已命中“脱敏”，原断言却要求 Detail Source；已改为参数化 Search match 与 Detail match 并 re-review，生产实现无需绕过正确来源。未发现剩余 blocker/high/medium Finding。
- **测试充分性结论**：Red 为 3 个预期失败；Green 目标 357 passed，Contract/API 171 passed，完整 Unit 除既有 POSIX 专用文件外 935 passed/8 skipped；Ruff、mypy、Contract 生成/兼容、Wheel、Docs、Architecture、Owner、Secret 与 lock 均通过。本机完整 Unit 另 3 个测试仅因 Windows 没有 `os.geteuid/os.chown` 失败；本机无 PostgreSQL 18 服务且 Docker daemon 未运行，真实 Migration/PostgreSQL/Full-stack 由 Ready exact-head PR CI 验证。

# 完成证据与状态

实现候选 `e20f7b9614bf0106cbdfa491c33ffa20bc23e710` 已完成本地验证、Completion Audit 与两阶段 Review，Change 进入 `ready_for_review`。PR #445 的早期 Completion Audit 失败是未 Ready 阶段的预期门禁；下一提交发布本记录后触发 exact-head CI。生产部署、生产 Migration、付费 Provider 和业务数据写入均未执行。
