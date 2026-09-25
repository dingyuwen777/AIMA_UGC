---
schema: coding-change/v1
id: CHG-20260925-095824-replay-revocation-impact
title: 校正采集运行全类型计数与数据导入撤销影响
level: L3
status: ready_for_review
owner: yuwen.ding
branch: fix/603-replay-revocation-impact
created: 2026-09-25T09:58:24+08:00
updated: 2026-09-25
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - collection
  - frontend
affected_paths:
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_revocation.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_lifecycle.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/collection/runtime_query.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CanonicalReplayDetailDrawer.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRunDetailDrawer.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeKpiCards.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportBatchDetailDrawer.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeTable.vue
  - frontend/src/features/task-center/store.ts
  - tests/integration/ingestion/test_import_campaign_revocation_postgres.py
  - frontend/tests/collection-runtime-design.spec.ts
  - frontend/tests/collection-runtime-release2.spec.ts
  - frontend/tests/task-center.spec.ts
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/product/02_当前产品能力与用户流程.md
  - docs/guides/07_采集运行中心Figma开发基线.md
contracts:
  - CollectionRuntimeItemResponse.revocation_recomputed_content_count
data_changes: []
---

# 变更摘要

本机 2026-09-25 的第二次全历史重筛新增入库为 0，但三个子任务分别收敛 16,469、22,780、1,055 条既有内容。采集运行与任务中心只显示“入库 0”，导致用户误以为没有处理。第四次本地导入 66,139 行全部过滤，但同 Campaign 后续重筛形成 6,757 条来源贡献、涉及 5,747 个 Content；撤销预览按原导入逐行账本显示影响 0，实际 Worker 重组 5,747 个 Content。

目标是让预览与真实贡献账本、执行进度一致，逐类核对采集运行的列表、详情及总览数字，并根据日志拆分慢阶段后验证可行优化。保持不可变历史审计事实、既有公共 API 字段语义、Schema、依赖和用户现有数据不变；只增加兼容的可选只读字段。生产部署与改写既有审计不在范围内。

# 背景、现状与问题

六条现场记录由四条 Campaign 和两条 Replay 组成。导入规则使四条 Campaign 的原始行全部过滤，但冻结的 Canonical 后来经 Replay 形成来源贡献；旧预览只看原导入行与在线补采，因此把应重组的 5,747 个 Content 预估为零。第二次 Replay 新建 Content 为零，列表也只显示零，掩盖了大量已有记录处理。保持现状会继续产生错误撤销确认和“没有处理数据”的误解。

# 事实与证据

- `historical_revocation._affected_content_ids` 只合并原导入行账本与在线补采账本，漏掉重筛沿原 Campaign 来源写入的 `content_source_contributions`。
- 撤销 Worker 的 `content_lifecycle._campaign_contributions_query` 已按 Campaign 关联读取上述贡献，故实际撤销数量大于预览。
- 第二次重筛的 `rows_ingested` 确为 0，`existing_convergence` 合计 40,304 次输入记录处理、`duplicates_removed` 为 6,875；撤回账本涉及 39,189 个不同 Content。不能把这两个计数相加或互换。
- 当前运行中心 API 返回六条记录：四条 Campaign、两条 Replay。四条 Campaign 处理行数分别为 202,168、168,792、66,139、66,139，均全部过滤；后两条撤销的实际重组量分别为 5,747 个不同 Content。其余三种记录类型使用隔离数据库/前端测试覆盖。
- Collection 的 `content_count`/`comment_count` 是每个 Scope 内去重、再按 Scope 累计的目标数，包含已有内容；`filtered_count` 是品牌车型过滤。Excel 的 `rows_ingested` 是本次处理行数，Campaign 同名投影仅累计新建/补空/更新。顶部 `contents_ingested_today` 是各类任务原有入库口径的相加，并非去重 Content 总数。
- 最大子任务的 `fallback_ms` 为 95,544 毫秒。3000 行隔离重筛把此阶段细分后，Content 更新约 3,938 毫秒，占第二轮重复重筛的主要数据库时间；集合 UPDATE 将该阶段缩短至约 1,870 毫秒。这个对照是单次本机实验，不声称所有服务器均有相同比例。

证据来源：本机 `.runtime/compose/runtime/logs/worker-*.log` 和 `api.log`、当前六条运行记录 API、只读 PostgreSQL 贡献/撤销请求查询、`content_lifecycle.py` 与 `historical_revocation.py` 的同源归属查询、隔离 PostgreSQL 集成测试及基准日志。

# 目标、成功标准与非目标

- 成功：撤销预览与贡献账本及 Worker 实际处理对象对齐；五类列表和详情使用与真实计数单位一致的标签；旧错误预估明确显示差异；第二次重筛的已有处理量可见；单机隔离实验在结果不变的条件下减少重复重筛耗时。
- 范围：导入撤销预览、采集运行只读投影、前端统计文案与组件、重筛聚合计时、既有 Content 批量更新、测试和相关正式文档。
- 非目标：改写已提交撤销审计、改变重筛/导入的持久语义、重新设计全库唯一 Content KPI、生产部署或完整重筛撤回性能专项。
- 保持：历史文件与来源账本、Job Fencing/Checkpoint、用户数据、既有 API 字段和失败语义、无外部 Provider 调用。

# 约束与意图决策

| 维度 | 决策与依据 |
| --- | --- |
| Contract | 仅新增可选只读字段，旧客户端与既有统计字段语义不变；生成 OpenAPI/Client 同步。 |
| 数据与迁移 | 撤销事实不可变，终态展示 Worker 已提交实绩；无 Schema/Migration。 |
| 性能与正确性 | 更新已锁定的不同 Content，按相同列集合分组并以 500 行集合 SQL 提交；不改变来源、版本与观测字段规则。 |
| 兼容与回滚 | API、Worker、Frontend 可按正常镜像回滚；历史预估留存，新增可选响应字段无需数据回填。 |

# 修改方案与决策依据

1. 从 Content Owner 的 Campaign 贡献查询复用归属条件，合并到撤销预览的受影响 Content 集合；用真实 Campaign→Replay→撤销路径验证。
2. 运行中心按五种类型分别呈现输入、过滤、重复、处理、撤销实绩；给 Campaign 增加只读实绩字段；用现场六条记录和组件测试对账。
3. 在已有低频 Replay 完成日志拆分 Content、证据与账本阶段；确认 Content 为慢段后采用有界集合 UPDATE；用隔离数据库回归和重复基准验证。

# 备选方案与取舍

- 直接改写旧撤销影响审计会丢失“当时系统预估为何错误”的事实，故保留旧值并在终态展示实际重组量。
- 用统一的“入库条数”概括全部五种任务会混合输入记录次数、按 Scope 累计目标与不同 Content，故保留各来源原始语义并在界面标明计数单位。
- 提高全局批大小没有证据能解决重复重筛的 Content UPDATE 往返，且可能增加事务资源压力；选择局部 500 行集合更新并保持运行时资源约束。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 过滤行后经重筛产生贡献时，撤销预览与实际撤销数量及进度口径一致 | #603 / AC1 | satisfied | PostgreSQL 真实 Campaign→Replay→预览→撤销集成测试；现场只读账本与 Worker 5,747 对账 |
| R2 | 第二次重筛新增 0 时显示已有记录处理量，不误称无处理 | #603 / AC2 | satisfied | 运行列表、任务中心渲染测试；现场 0/40,304/6,875 对账 |
| R3 | 分析全链路日志和贡献归属，拆分关键慢阶段并以实验决定优化 | #603 / AC3 | satisfied | 新增聚合分段日志；隔离数据库 3,000 行两轮实验及 Content 更新回归 |
| R4 | 六条现场记录与五种类型的列表/详情/总览计数和标签对齐真实统计对象，旧预估漏算时可见实际量 | #603 / AC4 | satisfied | 六条现场 API/数据库只读对账；五类型列表测试、旧预估差异详情 SSR、汇总语义文案 |
| R5 | 回归、文档和 Review 保持数据正确性；PR CI 作为独立合并门禁 | #603 / AC5 | satisfied | PostgreSQL 95 测试、前端 233 测试、构建、lint、类型、Contract/架构/Owner/文档检查；CI 待 PR Head 提交后验证 |

# 计划改动

| 步骤 | 修改范围 | 可观察结果与验证 |
| --- | --- | --- |
| 来源对齐 | 撤销影响查询、贡献查询、PostgreSQL 集成测试 | 预览受影响数量等于实际处理的独立 Content 数，普通/补采场景不回退 |
| 口径修正 | 采集运行只读投影、列表/详情/总览、任务中心及其测试 | 六条现场记录和五种类型的数字能对账；区分任务处理次数、范围累计和不同 Content；旧撤销记录展示实际处理量 |
| 性能取证 | 重筛 Worker 聚合阶段日志、Content 批量更新、隔离数据库实验 | 找到慢阶段，实测同数据结果不变且第二轮重筛加快 |
| 完成检查 | 文档、测试、Review、CI | 需求与结果逐项对齐，不改写旧审计事实 |

# 验证矩阵

| 层 | 要求 | 证据 |
| --- | --- | --- |
| PostgreSQL / Worker | required | 隔离 PostgreSQL 95 个相关回归通过（Content、Replay、Campaign 撤销、运行查询） |
| 前端行为 | required | 全量 Vitest 233 个通过；渲染五类记录与旧预估差异；lint、类型检查及生产构建通过 |
| 静态检查与生成一致性 | required | Ruff format/check、mypy、生成 Contract check/兼容检查、架构/表 Owner、文档检查通过；CI 待新 Head |
| 当前日志与隔离性能实验 | required | 现场 6 记录与 Worker 日志对账；3,000 行重复重筛改动前 6.744s、改动后 4.620s/4.326s（单机样本） |
| 外部 Provider | not_applicable | 当前链路不发送外部请求 |

# 完成审计

重新读取 #603 的 AC1–AC5、当前手写 Contract、生成 OpenAPI、采集运行只读 UNION、Content/撤销 Owner、页面五类型分支及本轮 diff。上游→实现：AC1 由来源贡献统一查询和预览覆盖；AC2 由 Replay 列表及任务中心覆盖；AC3 由聚合分段日志和 500 行集合 UPDATE 覆盖；AC4 由五类型列表/详情、可选撤销实绩字段及汇总口径提示覆盖；AC5 由测试、文档和 PR 门禁覆盖。实现→测试：新增字段经真实 PostgreSQL API 与前端类型/渲染验证，批量 UPDATE 经 Content 并发/Replay 集成回归及隔离基准验证。无新 Job 类型、迁移、依赖、配置或 Provider 网络调用。新增后端字段为可选只读字段，旧客户端兼容；生成文件已从事实源重新生成。

反向能力审计：列表五类型都有对应 API 只读分支；Replay 撤回与 Campaign 撤销的终态实绩分别来自持久请求计数，不能以原导入行统计或旧预估替代。历史已提交的旧预估不改写，终态仅提示预估差异并展示后台事实。顶部入库量继续采用既有混合任务统计，只明确标注为任务累计、可能重复；它不承诺“全库去重内容数”。

- [x] upstream_re_read：已重新读取用户问题、追加的全类型记录要求、Issue #603 AC1–AC5 和当前 Contract/调用链。
- [x] change_coverage：R1–R5 均与上游稳定验收对应；当前 Change 未充当自身的需求来源。
- [x] reverse_audit：五类型 API 投影→列表/详情、撤销/撤回请求→持久实绩→UI、Content 批量写→版本/贡献及测试均已反查。
- [x] unresolved_cleared：本 Change 没有 `not_satisfied`；PR CI、合并和归档保留为独立交付门禁，不冒充已完成。

# 两阶段 Review

第一阶段按用户要求和 #603 独立核对六条现场记录：4 条 Campaign 全部过滤，2 条 Replay 分别新增 39,189/0，第二条处理已有记录 40,304 次、去重 6,875 次，撤回重组 39,189 个 Content；后两条 Campaign 各重组 5,747 个 Content。检查 SQL 来源、状态、不同计数单位，发现并修正“相关性过滤”误称品牌车型过滤、Collection 跨 Scope 累计与 Excel/Campaign `rows_ingested` 语义混同。

第二阶段审查最终 diff、事务与索引边界、测试证据：500 行 `UPDATE ... FROM VALUES` 保留不同 `observed_fields` 的列集合，原行按稳定 ID 加锁且批次拒绝重复身份；贡献预览与 Worker 使用同一 Campaign 归属条件；API 增加可选只读字段无迁移；前端旧版预估差异通过真实组件 SSR 验证。隔离 PostgreSQL 覆盖数据事实，前端测试覆盖渲染；尚未在用户 Compose 或不同规格服务器上重放本次大型 XLSX，性能百分比不能外推。未发现本轮范围内的确定性阻塞问题；旧重筛撤回现场 39,189 个 Content 用时 151.7 秒仍是独立可优化瓶颈，不以这次 3,000 行实验声称已解决。

# 风险、兼容性、迁移与回滚

无 Schema/Migration/依赖或既有公共字段语义变动；新增可选只读 `revocation_recomputed_content_count` 并同步生成 Contract。历史已落地的错误撤销预估是不可变审计事实，本轮不追溯改写；终态展示实际重组量及预估差异。顶部入库量仍是不同任务原计数的累计，不代表全库不同 Content 数。

集合 UPDATE 的主要风险是列集分组、JSONB/时间戳类型及并发锁语义漂移；PostgreSQL Content 并发与 Replay 集成回归覆盖该边界。回滚为恢复原版本 API/Worker/Frontend 镜像；无迁移需要逆转。当前用户 Compose 未部署此提交，也未改变其数据库。

# 文档、依赖、部署与发布影响

同步 `docs/product/02_当前产品能力与用户流程.md` 的五类运行计数语义、`docs/appendix/08_数据入口与统一入库实现.md` 的 Replay/撤销单位，以及运行中心设计基线的 KPI 与表宽。未新增、删除或升级依赖、Runtime、配置、Secret；正常镜像更新即可应用代码，无额外 Migration/Release 操作。本轮没有执行部署。

# 完成证据与状态

| 证据 | 环境与命令 | 结果与边界 |
| --- | --- | --- |
| V1 | Windows 隔离 PostgreSQL 18；`uv run --no-sync pytest` 的 Content/Replay/撤销/运行查询相关集成集 | 95 passed，证明当前代码的真实持久化路径；不等于用户 Compose 重放。 |
| V2 | `npm run test -- --run`、`npm run lint`、`npm run build` | 233 passed、lint 及生产构建通过，覆盖列表五类型及旧预估终态 SSR。 |
| V3 | Ruff format/check、mypy、Contract 生成/兼容、架构/Owner、文档和 Change 检查 | 本地通过；PR #604 首轮 CI 的 Change 文档结构门禁失败，正在补齐正式章节后重新运行。 |
| V4 | 现场日志/API/只读 SQL 与隔离 3,000 行 Replay 基准 | 现场六条数字对账；本机样本第二轮由 6.744s 降至 4.620s/4.326s。 |

未验证：本次大型 XLSX 在更新后的 Compose 上重放、不同服务器配置下的性能增益和旧重筛撤回 151.7 秒瓶颈的专项优化。PR #604 分支 `fix/603-replay-revocation-impact` 首个实现提交为 `4dd76bc4`；后续补齐 Change 模板、CI、merge、main-fresh、归档、Issue Closure 与分支清理仍待执行。本任务未实施 Release 或生产部署。
