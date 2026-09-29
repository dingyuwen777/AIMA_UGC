---
schema: coding-change/v1
id: CHG-20260929-145200-voice-plaza-query-analysis
title: 声音广场 AI 分析支持当前筛选结果全集
level: L3
status: done
owner: codex
branch: feature/660-voice-plaza-query-analysis
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - content
  - frontend
  - contracts
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/analysis_high_throughput_planner.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/modules/analysis/content_analysis_job.py
  - backend/src/aima_ugc/modules/analysis/README.md
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/tests/analysis-all-scope.spec.ts
  - frontend/tests/voice-plaza.spec.ts
  - frontend/e2e/voice-plaza.spec.ts
  - tests/contracts/test_stage12_analysis_run_http.py
  - tests/api/test_analysis_all_scope.py
  - tests/integration/content/test_stage12_analysis_runs.py
  - tests/unit/content/test_stage12_analysis_planner.py
  - docs/product/02_当前产品能力与用户流程.md
  - docs/appendix/07_AI舆情打标与分析实现.md
contracts:
  - AnalysisRunTargetSelection
  - AnalysisContentRunPreviewRequest
  - AnalysisContentRunCreateRequest
data_changes: []
---

# 变更摘要

- **要解决的问题**：声音广场已有完整筛选能力，但 AI 分析只能处理显式已选内容或全部系统内容，无法直接处理当前筛选结果全集。
- **拟议修改**：把 Analysis Run 公开目标扩展为 `selected / query / all`；`query` 复用现有 `ContentFilterSnapshot`，由服务端 Preview、Create 和 Planner 完成权威计数与有界目标冻结。
- **预期结果**：用户可对跨分页、超过 1000 条的当前筛选结果执行后台 AI 打标；不需要浏览器搬运全量 ID，不改变现有 Provider/Shard/Retry/Cancel/Content Version 语义。

# 背景、现状与问题

## 背景

Requirement Source 为 #660。用户确认按系统方案实施，并要求完成后合并主分支。

## 当前现状

- 变更前 `AnalysisRunTargetSelection` 只公开 `selected / all`，其中 selected 最多 1000 个显式 ID。
- 声音广场已经用统一 `filterSnapshot()` 表达当前已应用筛选；列表、Count 与 query Export 共用同一查询事实。
- `analysis_content_runs` 已可持久化 `scope=query|selected` 和 `filter_snapshot`；`analysis_content_run_targets` 已冻结 `content_id + content_version`。
- 既有 all Scope 已通过 Planner 使用 UUID keyset 分批冻结目标；普通 query 兼容路径此前仍是一次性冻结。
- 前端此前把 Analysis 失败统一展示为固定“请稍后重试”，无法区分目标变化、空结果与 Provider 配置问题。

## 问题、根因或约束

真正能力缺口是公共 Analysis Run Contract、Planner 与 Voice Plaza UI 没有把既有 query 筛选事实接成正式 Scope。只在前端收集当前页 ID 会丢失跨页数据；直接一次冻结全部 query 会把大筛选集合变成长事务。由于筛选条件可以包含情感、相关性、标签等会被 Analysis 结果改变的维度，Run 不能在执行过程中动态重算目标，必须先冻结 ID + Version。

## 不修改的后果

用户仍只能手工勾选最多 1000 条，或选择全部系统内容；无法安全地对业务筛选结果全集重打标。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Voice Plaza Store 已有统一 `filterSnapshot()`，query Export 直接复用 | `frontend/src/features/voice-plaza/store.ts` | query Analysis 必须复用同一已应用筛选事实 |
| E2 | Run 表已有 `scope` / `filter_snapshot`，Target 表已有 ID + Version | `modules/analysis/tables.py` | 无需新增 Schema/Migration |
| E3 | all Scope 已有高吞吐 Planner、有界批次与最终数量核对 | `analysis_high_throughput_planner.py` | query 应沿用同一有界冻结框架 |
| E4 | Content Query Repository 已统一 projection/fallback 筛选语义 | `content_queries.py` | 不复制第二套 query SQL |
| E5 | Preview/Create 已冻结 Provider Snapshot、configuration hash 与 expected target count | `content_http.py` | query 必须保持现有确认和幂等边界 |
| E6 | 指纹增强前的完整产品基线 `ca8bcc0` 已通过 CI / Runtime / Tooling；当前新增同数量成员漂移护栏需由最终 current-head CI 再证明 | CI 6171、Runtime 3123、Tooling 1540 + current-head PR CI | 保留已验证基线，同时要求新增关键路径取得新鲜证据 |

## 推断与待确认

- 无阻塞推断。
- 分批冻结不持有跨批次长 MVCC 事务。新 query Run 在成功 Create 时用一个 PostgreSQL Statement Snapshot 对 `content_id + current_version` 全集生成双哈希集合指纹；Planner 最终冻结集合必须匹配该指纹，否则 fail closed。内部指纹不是安全签名，理论上仍存在极低哈希碰撞概率。

# 目标、成功标准与非目标

## 目标

让声音广场可以把当前已应用筛选结果全集作为正式 Analysis Run 目标，并在大规模结果下保持有界数据库事务和现有后台执行模型。

## 成功标准

- [x] 弹窗提供“已选内容 / 当前筛选结果 / 全部系统内容”三范围；无有效显式选择时默认 query。
- [x] query 使用当前已应用 `ContentFilterSnapshot`，不受分页、已加载条数和排序影响。
- [x] query 不受 selected 1000 条上限；selected/all 原语义保持。
- [x] HTTP Contract 对 selected/query/all 的 filters/content_ids 组合 fail closed，并同步 OpenAPI/generated client。
- [x] query Planner 使用稳定 UUID keyset 分批冻结 ID + Version，全部冻结后才调度 Shard。
- [x] Preview → Create 目标数变化返回 target-changed；成功 Create 同时固化确认时目标集合指纹；Planner 连同同数量成员替换一起校验，前端冲突后重新 Preview 且必须再次确认。
- [x] 标签多选与 legacy compatibility 继续复用当前查询事实。
- [x] 不新增 Schema、Migration、第二任务系统或新的 LLM 并发/RPS 语义。
- [x] 空目标、Provider 配置、冲突和普通请求失败由现有错误 Contract 提供可区分反馈。
- [x] Contract、真实 PostgreSQL、前端 Browser Mock、Runtime/Tooling/Build 门禁取得当前代码证据。

## 范围

- Analysis HTTP Contract、Content HTTP Service、Query Repository 与 High-throughput Planner。
- Voice Plaza Store / Analysis Dialog / Page。
- OpenAPI / generated TypeScript client。
- 直接相关 Contract、PostgreSQL、Frontend 与 Browser 回归。
- 当前产品能力与 Analysis 实现文档。

## 非目标

- 不修改 Prompt、Taxonomy、Analysis Scheme。
- 不新增表、列、Migration、Redis/Kafka/Celery 等任务系统。
- 不新增持续自动 Analysis Policy。
- 不对评论执行 AI 打标。
- 不执行生产 Release、Deploy 或生产数据操作。

## 必须保持不变

- selected 继续限制 1–1000 个显式 Content ID。
- all 继续忽略声音广场筛选并覆盖全部仍有有效来源的 Content Current。
- Provider Snapshot、`max_concurrency`、`max_rps`、Retry、Cancel、Fencing、Shard 和 stale 语义。
- 排序只影响浏览，不进入 Analysis Target identity。
- legacy query Run/filter snapshot 仍可恢复。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 复用现有 analysis/content/voice-plaza Owner | E1–E5 / #660 | 不创建新业务模块 |
| 接口与契约 | `AnalysisRunTargetSelection` additive 增加 query + filters | #660 / AC4 | OpenAPI 与 generated client 同步 |
| 数据与迁移 | 不改 Schema/Migration | E2 | 复用现有 Run/Target 表 |
| 错误与失败语义 | target/config 变化 fail closed；前端重新 Preview 后人工再次确认 | #660 / AC6, AC9 | 不静默扩大或缩小任务 |
| 兼容性 | selected/all、历史 query snapshot 保持 | #660 / AC3, AC8 | 旧行为继续合法 |
| 部署与回滚 | 普通源码回滚，无数据恢复步骤 | 无 Schema/依赖变化 | 无新增发布顺序 |

# 修改方案与决策依据

## 最小充分方案

1. Contract：新增 `query + filters`，三 Scope 严格互斥校验；更新 OpenAPI/generated client。
2. Preview/Create：query 按同一 Filter Snapshot 统计权威目标；Create 对 query/all 再核对 target count。
3. Query Repository：增加 filtered target count 和 UUID keyset batch 读取，复用 projection/fallback 筛选逻辑。
4. Planner：query 与 all 均分批冻结目标并最终核对数量，selected 继续短路径。
5. Frontend：三范围；query 直接复用 `filterSnapshot()`；409 自动重预览但不自动提交；提交期间锁定 Scope。
6. Tests/Docs：补 Contract、PG bounded freeze、Frontend/Browser、产品事实与 Analysis 文档。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 不让浏览器枚举筛选结果 ID | E1,E4 | 避免分页、内存和 1000 ID 限制，保持单一查询事实 |
| D2 query 先冻结再执行 | E2,E5 | 防止 Analysis 自己改变筛选字段后目标集合漂移 |
| D3 query 复用有界 Planner | E3 | 控制大结果集事务规模 |
| D4 不新增 Migration | E2 | 当前持久模型已能完整承载 query Run |
| D5 409 后重 Preview 但不自动重提 | #660 / AC6 | 目标/费用变化需要用户再次确认 |

## 备选方案与取舍

- 前端分页拉取全部 ID：不采用；会复制服务端查询、受分页/1000 ID 限制且放大浏览器内存。
- 直接公开旧一次 `INSERT ... SELECT` query freeze：不采用；大结果集形成长事务。
- 新建第二套 Query Job/Queue：不采用；既有 Planner/Shard/PostgreSQL Job Runtime 已覆盖所需能力。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 三范围 UI 与默认行为 | #660 / AC1 | satisfied | `AnalysisSubmitDialog.vue` + Browser/Frontend CI |
| R2 | query 复用 applied filters，跨分页且不受排序影响 | #660 / AC2 | satisfied | Store query payload + `analysis-all-scope.spec.ts` + Browser query test |
| R3 | query 无 1000 上限；selected/all 不回归 | #660 / AC3 | satisfied | Contract validator + all/selected regressions |
| R4 | HTTP Contract 与 generated client 完整 | #660 / AC4 | satisfied | OpenAPI generation drift gate success |
| R5 | query 有界冻结 Content ID + Version | #660 / AC5 | satisfied | PG integration 用 `freeze_batch_size=1` 证明分批路径；Create 只保存 Filter + 集合指纹，不搬运全量 ID |
| R6 | Preview/Create/Planner 目标变化 fail closed | #660 / AC6 | satisfied | Create count + target fingerprint；Planner frozen fingerprint；新增同数量成员替换 PG 回归；frontend 409 re-preview test |
| R7 | 标签 legacy compatibility 与现有查询语义一致 | #660 / AC7 | satisfied | query 直接复用 `filterSnapshot()` / `_effective_base_statement()` |
| R8 | 复用现有 Analysis Runtime，无 Migration | #660 / AC8 | satisfied | 现有 Run/Target/Shard/Worker；Runtime Acceptance green |
| R9 | 用户可区分主要失败类型 | #660 / AC9 | satisfied | Dialog 展示实际 API error；现有 422/503/409 Contract 保持 |
| R10 | 分层验证与关键路径证据 | #660 / AC10 | satisfied | CI 6171 + Runtime 3123 + Tooling 1540 全绿 |

# 计划改动

| 文件 / 模块 / 资产 | 实际修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `contracts/http.py` | selected/query/all Contract | 公开筛选目标 | R2–R4 |
| `content_http.py` | query Preview/Create、target changed 核对 | 权威确认语义 | R2,R6 |
| `content_queries.py` | filtered count/keyset batch + Create/Frozen 集合指纹 | 有界冻结且捕获确认时成员集合 | R5,R6,R7 |
| Planner | query 分批冻结并校验 Frozen Target 指纹 | 大集合事务边界与成员一致性 | R5,R6 |
| `content_analysis_job.py` | 内部 query filter/fingerprint 快照包装与 legacy 恢复 | 无 Migration 保存确认事实 | R6,R8 |
| Voice Plaza Store/Dialog/Page | 三范围、默认 query、错误/重新确认 | 用户入口 | R1–R3,R9 |
| OpenAPI/generated client | 正式生成 | Contract 单一事实 | R4 |
| tests | Contract/PG/Frontend/Browser 回归 | 证明关键边界 | R1–R10 |
| product/analysis docs | 同步当前行为与一致性边界 | 长期事实一致 | R1,R2,R5,R6 |

执行状态：

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据：CI run 36533546458 中 query Contract Red
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响长期文档
- [x] 取得仍覆盖当前代码的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Contract、Planner、Voice Plaza Store/Dialog；CI 6171 |
| 接口 / 契约 | required | AnalysisRunTargetSelection + OpenAPI/generated drift；CI 6171 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL query bounded freeze / existing selected/all；PostgreSQL Integration success |
| 用户 / 工作流验收 | required | 当前筛选结果默认范围、跨页 payload、冲突重新确认；Browser Full-stack success |
| 跨组件关键路径 | required | Voice Plaza filter → Preview/Create → Planner target → Shard |
| 外部依赖 / 供应方探测 | not_applicable | 不依赖第三方 Provider 当前在线事实；Fake LLM 足以证明本次接线 |
| 构建 / 打包 / 运行 | required | Frontend build、Runtime Compose、Linux/Windows Tooling 全绿 |
| 文档 / 治理 / 其他 | required | docs、generated、Requirement Source、CI Gate 通过 |

## 验证计划

- 目标测试：query Contract、query bounded Planner、Voice Plaza query/409 行为。
- 相关回归：selected/all Analysis、Voice Plaza Browser。
- 静态检查或构建：Ruff、mypy、frontend lint/typecheck/build。
- 专项真实边界：PostgreSQL Integration。
- 就绪检查：项目 Change Ready Gate + PR required CI。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | Query 大集合事务；动态筛选条件自我变化；同数量成员替换 | UUID keyset 分批冻结 + Create target fingerprint + Planner frozen fingerprint + Content Version |
| 兼容性 | additive | selected/all 与历史 query snapshot 保留 |
| 数据 / Migration | 不适用 | 无 Schema 变化，无历史回填 |
| 部署 / 运行 | 无新增进程/配置 | 复用 API/Planner/Worker/PostgreSQL Job Runtime |
| 回滚 / 恢复 | 可回滚源码 | 无不可逆数据变更 |

# 文档、依赖、部署与发布影响

- **长期文档**：已同步 `docs/product/02_当前产品能力与用户流程.md`、`docs/appendix/07_AI舆情打标与分析实现.md`、Analysis README。
- **依赖 / Runtime**：不新增、不删除、不升级依赖；不新增 Runtime 进程。
- **配置 / Secret**：不改变。
- **部署 / Release**：不新增 Migration、停机或发布步骤；本任务不执行生产 Deploy。
- **兼容 / 消费方通知**：公共 Contract additive 增加 query；generated client 已同步；selected/all 保持。

# 完成审计

- [x] upstream_re_read：已重新读取 #660 AC1–AC10、当前 main、Voice Plaza Store/Contract/Query/Planner 与 Analysis 文档。
- [x] change_coverage：AC1–AC10 均映射到实现与当前 PR 证据；没有用前端按钮替代服务端 Query/Planner 语义。
- [x] reverse_audit：从 UI Scope → applied Filter Snapshot → Preview → Create count/fingerprint → DB Run Snapshot → keyset target freeze → frozen fingerprint → Shard 回查；另从 selected/all/legacy query 反查兼容行为。
- [x] unresolved_cleared：无 not_satisfied / 未批准延期；无 Schema/Migration/Provider Probe 缺口。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V0 | PR #661 predecessor / CI run 36533546458 | Unit/Contract/API | Red：query scope 被旧 Contract 拒绝，1 failed / 111 passed | TDD 失败边界真实存在 |
| V1 | product head `ca8bcc0` merged-with-main / CI run 6171 | Requirement/Generated/Ruff/mypy/Unit/Contract/API/Frontend/PostgreSQL/Full-stack/CI Gate | 全部 required jobs success | 当前实现、Contract、真实 PG 与浏览器关键路径通过 |
| V2 | product head `ca8bcc0` / Runtime Acceptance 3123 | Compose Golden Path | success | Runtime 组装、启动、持久化与安全路径无回退 |
| V3 | product head `ca8bcc0` / Developer Tooling 1540 | Linux + Windows Tooling | 两个 Tooling jobs success | 开发/Compose 工具链无回退 |
| V4 | PR #661 branch sync commit `7e23ec2` | compare main...feature | behind 0 / clean merge | 分支已吸收当前 main，不通过规则 bypass 合并 |
| V5 | current head `290e7945` / CI 6190 | Requirement Audit + Ruff/mypy + Unit/Contract/API + PostgreSQL Integration + Browser Full-stack + CI Gate | required jobs 全部 success；PostgreSQL Integration success | 直接覆盖 query bounded freeze、同数量成员替换、selected/all 短事务及跨组件关键路径 |

## 未验证内容与剩余风险

- 未执行真实付费 LLM Provider Probe；本变更不依赖 Provider 在线事实，且 Requirement #660 明确不要求新增该探测。
- 不做生产规模吞吐承诺；实现保证有界冻结事务，生产吞吐仍由真实数据分布、PostgreSQL 和 Provider 容量决定。
- 分批冻结不提供跨所有批次的单一 MVCC 时点；新 query Run 通过 Create 集合指纹与 Planner frozen fingerprint 核对同数量成员替换。双 64-bit PostgreSQL 哈希聚合再经 SHA-256 编码属于一致性护栏，不是密码学集合承诺，保留极低碰撞风险。

## 交付状态

- 提交：产品实现已在 `feature/660-voice-plaza-query-analysis`。
- 拉取请求：#661，ready for review。
- CI：current head `290e7945` 的 CI 6190、Runtime Acceptance 3142、Developer Tooling 1558 均已绿色；required contexts `Requirement Traceability and Completion Audit`、`CI Gate`、`Compose Golden Path` 均 success。
- 合并：current head 已满足实现与验证门禁；本提交只更新最终 Evidence，待其自身 required checks 绿色后按用户授权合并 main。
- Change 归档：merge 后按仓库自动归档流程核验。
- 发布 / 部署：不适用；用户未要求 Release/Deploy，且无 Migration。

## 备注

首轮完成复核发现 count-only 无法识别“总数不变但成员替换”的同根投影，已在同一 Repair Batch 中升级为 Create/Frozen 集合指纹闭环；不新增 Schema/Migration。
