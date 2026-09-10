---
schema: coding-change/v1
id: CHG-20260911-063418-r05-stage4-canonical-replay
title: Roadmap 05 Stage 4 Canonical Replay 与 clean break 收口
level: L3
status: in_progress
owner: dingyuwen777
branch: feat/r05-stage4-canonical-replay
created: 2026-09-11
updated: 2026-09-11
completion_gate: required
depends_on:
  - CHG-20260911-045854-r05-stage3-tikhub-canonical
affected_areas:
  - ingestion
  - content
  - platform
  - storage
  - database
  - jobs
  - api
  - frontend-contract
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/database_schema.py
  - backend/src/aima_ugc/platform/storage/tables.py
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - tests/
  - docs/
  - changes/active/CHG-20260911-063418-r05-stage4-canonical-replay/CHANGE.md
contracts:
  - Canonical Replay HTTP API
  - Canonical Replay Job payload/result
  - Canonical Replay persistent run/checkpoint
data_changes:
  - add canonical replay run, selected-artifact and per-run seen-content relations
  - reject unsupported legacy canonical lineage during migration
---

# 变更摘要

- **问题**：Stage 1—3 已把当前 Excel、Data Import Campaign 与 TikHub Discovery 接入 Persistent Canonical，但还没有正式入口把一个或多个旧 Canonical Artifact 按新冻结 Brand/Vehicle 目录重新过滤并幂等补入 Content。
- **目标**：提供管理员可操作的 Replay API 和 PostgreSQL Durable Job；全部输入先 fail-closed 预检，再按有界批次复用当前 Resolver、Content identity/Owner 和 Brand/Vehicle Evidence 写入，并留下可恢复检查点与统计。
- **历史补齐决定**：仓库与本轮可访问环境没有需要提升的真实 legacy 存量；按用户已批准 clean break，只接受 Stage 1—3 当前三种父级关系，旧 Job/outcome、Scope-only 或含糊来源失败关闭，不重新调用 TikHub、不改写旧账本。

# 已确认事实与设计决定

| 编号 | 事实 / 决定 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | Stage 1—3 已提供 `canonical-content.v1`、唯一父级 link、共享 Writer/Reader 与当前三条生产写入链 | 当前代码、Migration 0048—0050、Roadmap 05 | Replay 只消费现有 linked Artifact，不建第二套 Dataset |
| E2 | Excel Canonical 在持久层内保留入口 Source，但 Provider Attempt/Raw 由正式 Import Ingestion 在业务写入时确定性补齐 | Import Mapper、`manual_ingestion.py`、Historical Worker | Replay 必须按父级恢复当前 Import lineage 后再进 Content Owner |
| E3 | TikHub Canonical 自身已保存真实 Provider Attempt/Raw/locator | Canonical Contract、Collection Scope Runtime | Replay 校验并保持原来源，不发送 Provider 请求 |
| E4 | Content Owner 的 `(platform, external_content_id)`、版本/指标/来源贡献与 Evidence Owner 已提供幂等收敛 | Content/Brand/Vehicle repositories | 不复制 Content SQL 或平行 Dedup |
| E5 | Durable Job 已提供 Lease/Fence/Heartbeat/Deadline/Cancel/Retry/Reaper | Platform Jobs 与 Worker | Run 只保存输入、冻结快照、检查点和累计统计；Payload 只携带 run_id |
| E6 | 开工基线为 `origin/main@9f88537d0364765264123aef249d4cce5a688aae`，Issue #447 已 live reread | 本轮 Git/GitHub 证据 | 从最新 main 本地分支施工并建立早期 PR |

# 目标、范围与非目标

## 成功标准

- [x] 管理员可创建、读取、取消 Replay；幂等键稳定，全部选中 Artifact 与 Filter Snapshot 冻结。
- [x] 所有 Artifact 在首个 Content 写入前完成全量完整性/Contract 预检；任一坏输入零写入。
- [x] 有界批次、当前 Fence、可恢复 checkpoint、统计与 Content/Evidence 在同一事务推进。
- [x] 新 Alias/Brand/Vehicle 可从旧 Canonical 补入新命中；相同输入重跑无重复 Content。
- [x] 当前 Excel v2、Pure Canonical Campaign Chunk、TikHub Search Attempt 三类 lineage 均可用；旧结构 fail-closed。
- [ ] Contract/Schema/Migration/生成 Client、长期文档、测试、Review、CI、merge、main fresh、归档与 Roadmap/Issue/分支全部闭环。

## 非目标

- 不新增 Monitoring Membership、Filter History、退出监测、Platform Registry、第二数据库、消息系统或复杂 Replay 页面。
- 不重新 Mapper 当前已有 Canonical，不调用 TikHub/LLM/Embedding，不执行生产部署/Migration/业务写入。
- 不支持已经淘汰且本轮确认无真实存量的 `ingestion.import-excel.v1`、Historical outcome Chunk 或无法证明 lineage 的 Artifact。
- 不升级依赖、不改变 Canonical V1、Content identity、Filter 业务语义或已有消费者。

## 必须保持不变

- Python 3.14.7、PostgreSQL 18、根 uv 工程、单一 Durable Job Runtime 与 Pydantic→OpenAPI→Orval 链。
- ArtifactStore I/O 不进入长数据库事务；Canonical 字节不进 PostgreSQL 宽表。
- Replay filtered 不删除/隐藏旧 Content；不自动触发 AI/Export/Report。

# 实施计划

1. **Red：Job/Run/HTTP/Schema 与失败关闭 Contract**
   → 修改范围：Unit/API/Schema/Migration 测试与当前 Change
   → 预期结果：现状缺少 Replay 类型、路由、表和迁移而按预期失败
   → 验证：目标 pytest、Change validator
2. **Green：持久父事实、来源验证与正式 API**
   → 修改范围：Ingestion domain/table、PostgreSQL repository、HTTP service/route、Contract/生成物
   → 预期结果：管理员在短事务冻结合法 Artifact 列表与 BrandVehicleFilterSnapshot，并创建 Job；查询/取消复用统一状态
   → 验证：Unit/API/PostgreSQL Contract 与授权/幂等/lineage 负向测试
3. **Green：全输入预检与有界 Fenced Replay**
   → 修改范围：Replay executor、Worker registry、Content/Evidence 协调
   → 预期结果：先预检全部输入，再逐批 Filter→Dedup→Content Owner，检查点/统计可恢复，坏 Artifact 零写入
   → 验证：Artifact/Job/PostgreSQL workflow、retry/cancel/takeover/stale-fence/idempotency
4. **Clean break、文档与完整交付**
   → 修改范围：Migration、Blueprint/Appendix/Operations/Product/README、Roadmap/Change 与 GitHub 生命周期
   → 预期结果：旧结构明确失败关闭，长期事实同步，Roadmap 05 退出 live docs
   → 验证：Migration round-trip、full official gates、Completion Audit、独立两阶段 Review、exact-head CI、main fresh

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 创建持久 Replay Run/Job、冻结有序 Artifact 与幂等请求 | #447 / AC1 | satisfied | Repository enqueue、Run/Input 表、事务 advisory lock；顺序/并发同键与参数漂移集成测试 |
| R2 | 冻结 all_active/selected BrandVehicleFilterSnapshot 并拒绝非法目录 | #447 / AC2 | satisfied | enqueue snapshot；selected 精确快照集成测试；未归属 active 车型失败关闭 |
| R3 | 全部 Artifact 预检先于任何 Content 写入，坏输入零写入 | #447 / AC3 | satisfied | Worker `_preflight_all`；损坏第二 Artifact 时 Content/seen 均为 0 的集成测试 |
| R4 | 复用 Reader→当前 Resolver/Filter→Content identity/Owner | #447 / AC4 | satisfied | CanonicalArtifactReader、`resolve_canonical_brand_vehicle`、ContentIngestionService 调用链 |
| R5 | 精确累计 seen/matched/filtered/dedup/ingested/existing 统计 | #447 / AC5 | satisfied | Run 对账约束、持久 seen identity、重复/重跑统计集成断言 |
| R6 | 新目录补入、重跑幂等和冻结 Evidence | #447 / AC6 | satisfied | 新 Alias 后 Replay、二次 Replay、Brand Evidence/catalog_version 集成断言 |
| R7 | 不删除旧 Content、不触发 AI/Export/Report | #447 / AC7 | satisfied | Replay Evidence merge 不停用其它 Brand；selected 范围外证据保留回归；Job 无下游 enqueue；迁移无 Content 删除 |
| R8 | Lease/Fence/Heartbeat/Deadline/Cancel/Retry/Recovery | #447 / AC8 | satisfied | 统一 Job Runtime；Replay handler/cancel API；首批提交后 running cancel、takeover 续跑、stale fence 与每 Artifact 线性 Reader 次数集成测试 |
| R9 | 当前三类 Artifact lineage 可用，任意/含糊父级拒绝 | #447 / AC9 | satisfied | Repository 三来源分类；TikHub 同 Scope Search/Detail 正向及 Request/Attempt/Raw/platform/operation/completed/cross-Scope 负向 PostgreSQL 回归 |
| R10 | 零 legacy clean break；旧结构失败关闭且无外部重取/历史篡改 | #447 / AC10 | satisfied | Migration 0051 gate + Scope DB check；Replay 无 Provider transport；当前 lineage 创建/复用 |
| R11 | 正式管理员 API 创建/查询/取消，无复杂页面 | #447 / AC11 | satisfied | FastAPI API/授权/404/409/422/审计测试；无页面变更 |
| R12 | Schema/Contract/生成物/文档/容量恢复/兼容边界同步且不越界 | #447 / AC12 | satisfied | Migration/metadata、OpenAPI/Orval、Product/Blueprint/Appendix/Operations/README；线性读取与接管成本边界；本地生成/文档门禁通过 |
| R13 | 分层验证、Completion Audit、独立 Review、exact-head CI/main fresh | #447 / AC13 | not_satisfied | 交付待完成 |
| R14 | Change/Roadmap/Issue/分支完整收口 | #447 / AC14 | not_satisfied | merge 后完成 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Payload/Handler、Snapshot、全输入预检、过滤/统计/恢复 |
| 接口 / 契约 | required | Pydantic、FastAPI/OpenAPI、Orval、授权/幂等/错误 |
| 集成 / 持久化 / 运行时依赖 | required | PostgreSQL 18、Schema/Migration、三类 lineage、Content/Evidence、Fence |
| 用户 / 工作流验收 | required | API→DB→Worker→Job/Run→新命中 Content、取消与重跑 |
| 跨组件 Golden Path | required | 既有 Import/Collection/Voice Plaza/Analysis/Export 回归不受影响 |
| 外部依赖 / Provider Probe | not_applicable | 用户禁止外部付费调用；当前 Fixture/Raw/Canonical 已是正式边界 |
| 构建 / 打包 / 运行 | required | Ruff、mypy、wheel、前端 lint/typecheck/test/build、Migration 往返 |
| 文档 / 治理 / 其他 | required | Product/Blueprint/Appendix/Operations/README、Change/Secret/Owner/Docs checks |

# 风险、兼容、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 后续 Artifact 损坏造成部分写 | 高风险 | 每次执行/接管先预检完整有序输入集，任一失败前零写入 |
| gzip 中段恢复成本 | 可接受但需说明 | 按 Artifact ordinal + 行号 checkpoint；接管会顺序跳过已提交行，保持 O(单批) 内存，不声称 O(1) seek |
| 来源补齐 | Excel 需确定性非计费 lineage | 按当前父级、Source/Chunk Artifact 与现有 Provider persistence 语义创建/复用；TikHub 保持原 Attempt/Raw |
| Existing Content 统计 | Content Owner 是最终去重门禁 | `version_no == 1 && version_created` 计新建，否则计 existing convergence；不绕过唯一身份 |
| legacy | 无真实存量，不值得引入兼容层 | Migration 与创建入口对旧/含糊关系失败关闭，不静默转换 |
| 回滚 | 新 API/Job/表是新增能力 | 停止创建/Worker 后可回滚应用；Schema downgrade 前须确认无 Replay Run 依赖，生产动作不在本任务 |

# 文档影响

Docs Impact 为 `full`：Roadmap 05 总退出要求把 Replay、来源、失败、恢复、容量和 clean-break 事实同步到 Product/Blueprint/Appendix/Operations/模块 README；实现合并和 main fresh 后删除 live Roadmap 05 并更新依赖导航。

# 执行清单

- [x] 读取项目规则、canonical Agent_Skills Source、Roadmap/Blueprint 与当前机器事实
- [x] 创建并 live reread Issue #447、最新 main 与本地任务分支
- [x] 建立 Change、Requirement Traceability、验证矩阵和 clean-break/迁移/回滚边界
- [x] Red 失败测试与首个本地提交/首次 push/早期 PR（`45af1a57`，PR #448）
- [ ] Green/Refactor、分层验证、Completion Audit 与独立 Review
- [ ] exact-head CI、guarded merge、main fresh、归档、Roadmap/Issue/分支收口

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 两阶段 Review

- **需求与风险重建**：独立 Reviewer 已从 Issue #447、Roadmap 05 Stage 4/总退出与当前机器事实重建，未以本 Change 自证。
- **实现与证据对照**：首轮审查发现四项阻断：每批从头 Reader 导致近似 O(N²)、并发同幂等键可能 409、selected Replay 覆盖范围外 Brand Evidence、TikHub 同 Run 跨 Scope 来源可混入；已分别改为每 Artifact 一次连续流式执行、事务 advisory lock、仅 merge 本次确认品牌证据、逐行同 Scope/Request/Attempt/Raw/platform/operation 校验。首次 re-review 确认前三项闭环，但发现 TikHub SQL 误从无 `platform` 列的 Provider Request 取值；现已改为真实 `Collection Scope.platform`，并新增同 Scope Search/Detail、字段漂移、未完成 Attempt、running cancel、同 Brand 旧证据替换与人工锁回归。最终 re-review 尚待执行。

# 完成证据与状态

实现与长期文档已完成第二轮修正候选，Red commit 与早期 PR #448 已建立。R1—R12 已由代码和本地测试证据满足；独立 Review 发现的四项原始阻断和首次 re-review 的错误列阻断均已修复，但最终 re-review 尚待执行。PostgreSQL 18 集成、完整 CI、Completion Audit、merge/main fresh、native archive、Roadmap/Issue/分支收口仍待完成，因此 Change 继续保持 `in_progress`，R13—R14 不满足。

本轮本地新鲜证据：Ruff format/check、mypy（332 个源码文件）、Unit（939 passed, 8 skipped；Windows 排除 3 个 POSIX-only host preparation case）、Contract（111 passed）、API（68 passed）、OpenAPI/Orval generate-check-compat、npm ci、文档/架构/表 Owner 门禁均通过；新 PostgreSQL 测试已成功 collect。本机缺少 `.runtime/secrets/postgres_password` 且 Docker daemon 不可用，未伪造 PostgreSQL 执行结果，交由 PR exact-head CI 验证。
