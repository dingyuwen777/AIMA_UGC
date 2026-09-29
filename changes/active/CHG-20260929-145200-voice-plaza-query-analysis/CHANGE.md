---
schema: coding-change/v1
id: CHG-20260929-145200-voice-plaza-query-analysis
title: 声音广场 AI 分析支持当前筛选结果全集
level: L3
status: proposed
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
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - tests/contracts/test_stage12_analysis_run_http.py
  - tests/api/test_analysis_all_scope.py
  - tests/unit/content/test_stage12_analysis_planner.py
  - tests/integration/content/test_stage12_analysis_runs.py
  - frontend/tests/analysis-all-scope.spec.ts
  - frontend/tests/voice-plaza.spec.ts
  - docs/appendix/07_AI舆情打标与分析实现.md
contracts:
  - AnalysisRunTargetSelection
  - AnalysisContentRunPreviewRequest
  - AnalysisContentRunCreateRequest
data_changes: []
---

# 变更摘要

- 要解决的问题：声音广场已有完整筛选能力，但 AI 分析只能处理显式已选内容或全部系统内容，无法直接处理当前筛选结果全集。
- 拟议修改：把新 Analysis Run 目标扩展为 selected / query / all；query 复用现有 ContentFilterSnapshot，并由 Planner 有界冻结目标后复用现有 Shard / Worker。
- 预期结果：用户可以对跨分页、超过 1000 条的当前筛选结果执行后台 AI 打标，同时保持大数据量、Content Version、取消、并发与幂等边界。

# 背景、现状与问题

## 背景

Requirement Source 为 #660。当前用户明确要求按已确认方案修改并合并到主分支。

## 当前现状

- AnalysisRunTargetSelection 公开只支持 selected / all；selected 最多 1000 个 ID。
- 声音广场 filterSnapshot() 已统一生成列表、Count 与 query Export 使用的 ContentFilterSnapshot。
- Analysis 数据库 Run 已有 scope=query|selected 与 filter_snapshot，公开 all 通过 query + 内部 all marker 持久化。
- Planner 已对 all 使用 UUID keyset + 10,000 批量有界冻结；普通 query 兼容路径仍通过单次 INSERT ... SELECT 冻结。
- analysis_content_run_targets 已保存 run_id + target_ordinal + content_id + content_version，无需新增 Schema。
- 当前弹窗对不同失败统一展示“AI 分析请求未完成，请稍后重试”。

## 问题、根因或约束

能力缺口来自公开 Analysis Run Contract / Planner / Voice Plaza 接线未把现有 query 筛选模型作为正式 Scope 暴露；若只在前端收集当前页 ID，会丢失跨分页结果；若直接复用一次性 query 冻结，在大结果集下会形成超大事务。由于筛选条件可包含 Analysis 结果维度，执行期间不能持续动态查询，必须先冻结 Content ID + Version。

## 不修改的后果

用户只能手工勾选不超过 1000 条或对全部系统内容执行 AI 分析，无法安全地对业务筛选集合批量重新打标。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Voice Plaza Store 已有统一 filterSnapshot()，query Export 直接复用 | frontend/src/features/voice-plaza/store.ts | query Analysis 应复用同一筛选事实，不建立第二套转换 |
| E2 | Analysis Run 表已存 scope 和 filter_snapshot，scope 机器约束是 query/selected | backend/src/aima_ugc/modules/analysis/tables.py | 无需 Migration；公开 query 可映射既有持久模型 |
| E3 | all 已通过专用内部 marker + 有界 Planner 冻结目标 | content_http.py、analysis_high_throughput_planner.py | query 大集合应沿用同一有界冻结框架 |
| E4 | freeze_target_statement(filters=...) 已保证 Query 与 Content Read Model 使用同一筛选语义 | content_queries.py | 不复制查询 SQL |
| E5 | selected / all Preview/Create 已冻结 Provider Snapshot、expected target count 与 configuration hash | content_http.py | query 必须保持现有 optimistic confirmation / identity 语义 |
| E6 | analysis_content_run_targets 已冻结 Content Version | modules/analysis/tables.py | AI 结果改变筛选字段时仍可保持 Run 目标稳定 |

## 推断与待确认

无阻塞项。真实生产量吞吐不从 CI 推断，本任务只要求代码路径保持有界事务。

# 目标、成功标准与非目标

## 目标

让声音广场 AI Analysis Run 支持当前已应用筛选结果全集，且对大规模 query 使用可恢复的有界目标冻结。

## 成功标准

- [ ] selected / query / all 三 Scope Contract 完整。
- [ ] query 复用 applied ContentFilterSnapshot，不受分页和排序影响。
- [ ] query 无 selected 1000 上限；selected / all 原行为不回归。
- [ ] query Planner 有界冻结 ID + Version，完成冻结后再调度 Shard。
- [ ] Preview/Create 目标变化与配置变化 fail closed。
- [ ] 前端提供三范围、正确默认值与可区分错误反馈。
- [ ] OpenAPI/generated client、文档与分层测试同步。

## 范围

- Analysis HTTP Contract、Content HTTP Service、Planner 与 Content Query Repository。
- Voice Plaza Store/Dialog/Page 的 Analysis Range 交互。
- 生成 Contract、相关测试与 AI Analysis 实现文档。

## 非目标

- 不改 Prompt、Taxonomy、Scheme。
- 不增 Schema/Migration/队列/进程/依赖。
- 不新增持续自动分析策略，不做评论 AI。
- 不执行生产部署、Release 或生产数据操作。

## 必须保持不变

- selected 1–1000 条、显式 ID 语义。
- all 忽略声音广场筛选并覆盖全部仍有有效来源的 Content Current。
- Analysis Provider Snapshot / max_concurrency / max_rps / Retry / cancel / progress / stale / Fencing。
- 列表排序不进入 Analysis target identity。
- legacy query Run / 历史 filter snapshot 可继续恢复。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 复用 analysis/content/voice-plaza 现有 Owner | E1-E6 / #660 | 不创建新业务模块 |
| 接口与契约 | AnalysisRunTargetSelection additive 增加 query + filters | #660 / AC4 | OpenAPI 与 TS Client 需重新生成 |
| 数据与迁移 | 不改 Schema / Migration | E2,E6 | 复用现有 Run/Target 表 |
| 错误与失败语义 | 保持 target_changed / configuration conflict；前端区分空集/配置/冲突/普通失败 | #660 / AC6,AC9 | 不静默改变任务范围 |
| 兼容性 | selected/all 与历史 query snapshot 保持 | #660 / AC3,AC8 | 旧调用方继续合法 |
| 部署与回滚 | 普通源码回滚，无数据恢复 | 无 Schema/依赖变化 | 不增加发布步骤 |

# 修改方案与决策依据

## 最小充分方案

1. Contract：AnalysisRunTargetSelection 增加 query 与 filters，三种 Scope 互斥校验；生成 OpenAPI / Client。
2. HTTP Preview/Create：query 按冻结筛选快照计算权威 target_count 并持久化 filter_snapshot。
3. Query Repository / Planner：提供稳定 UUID keyset 的 filtered target batch；Planner 对 query 与 all 都分批冻结并在最终重新核对 target_count。
4. Frontend：analysisTargetSelection() 复用 filterSnapshot()；弹窗三范围，无显式选择默认 query；显示服务端 Preview 数量与具体错误。
5. Tests/Docs：Contract、Unit/PG、Frontend 与关键路径回归；同步 Analysis 实现文档。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 不让前端枚举筛选结果 ID | E1,E4 | 避免分页/内存/1000 上限并保持单一查询事实 |
| D2 query 先冻结再执行 | E6 | 防止 AI 结果改变筛选字段造成目标集合漂移 |
| D3 query 复用有界 Planner | E3 | 避免大结果集单事务冻结 |
| D4 无 Migration | E2,E6 | 现有表已经能完整承载 query Run |

## 备选方案与取舍

- 前端循环分页收集 ID：不采用，会把服务端查询语义复制到浏览器并受 1000 ID Contract 限制。
- 直接公开旧一次性 query freeze：不采用，功能虽可用但无法满足大结果集事务边界。
- 新建 Query Job/队列：不采用；现有 Planner/Shard/Job Runtime 已覆盖所需能力。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 三范围 UI 与默认行为 | #660 / AC1 | not_satisfied | 尚未实现 |
| R2 | query 复用完整 applied filters，跨分页且不受排序影响 | #660 / AC2 | not_satisfied | 尚未实现 |
| R3 | query 无 1000 上限；selected/all 不回归 | #660 / AC3 | not_satisfied | 尚未实现 |
| R4 | HTTP Contract 与 generated client 完整 | #660 / AC4 | not_satisfied | 尚未实现 |
| R5 | query 有界冻结 Content ID + Version | #660 / AC5 | not_satisfied | 尚未实现 |
| R6 | Preview/Create/Planner 目标变化 fail closed | #660 / AC6 | not_satisfied | 尚未实现 |
| R7 | 标签 legacy compatibility 与现有查询语义一致 | #660 / AC7 | not_satisfied | 尚未实现 |
| R8 | 复用现有 Analysis Runtime，无 Migration | #660 / AC8 | not_satisfied | 尚未实现 |
| R9 | 用户可区分主要失败类型 | #660 / AC9 | not_satisfied | 尚未实现 |
| R10 | 分层验证与关键路径证据 | #660 / AC10 | not_satisfied | 尚未验证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| backend/src/aima_ugc/contracts/http.py | query Scope Contract | 公开表达筛选目标 | R2-R4 |
| backend/src/aima_ugc/bootstrap/content_http.py | query Preview/Create | 权威 Count / Snapshot | R2,R6 |
| backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py | filtered keyset target batch | 有界冻结 | R5,R7 |
| backend/src/aima_ugc/bootstrap/analysis_high_throughput_planner.py | query 分批冻结 | 大集合事务边界 | R5,R6 |
| frontend/src/features/voice-plaza/* | 三范围与错误反馈 | 用户入口 | R1-R3,R9 |
| OpenAPI / generated client | 正式生成 | Contract 单一事实 | R4 |
| tests / docs | 回归与当前事实同步 | 完成证据 | R1-R10 |

执行状态：

- [x] 调查当前实现和事实源
- [x] 建立验证矩阵
- [x] 行为变化建立首个失败 Contract 测试
- [ ] 完成最小实现
- [ ] 同步受影响长期文档
- [ ] 取得覆盖当前实现的新鲜证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Planner batching、Voice Plaza Store/Dialog |
| 接口 / 契约 | required | AnalysisRunTargetSelection、OpenAPI、generated client |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL filter target freeze / resume / target changed |
| 用户 / 工作流验收 | required | 三范围、默认 query、Preview 与错误反馈 |
| 跨组件关键路径 | required | Voice Plaza filter → query Preview/Create → Planner target |
| 外部依赖 / 供应方探测 | not_applicable | 不需要确认第三方 Provider 当前事实 |
| 构建 / 打包 / 运行 | required | Frontend typecheck/build；Backend Ruff/mypy 受影响范围 |
| 文档 / 治理 / 其他 | required | Change、OpenAPI/generated、Analysis 文档、PR/CI |

## 验证计划

- 目标测试：Contract query Scope；Planner query batch；Voice Plaza query Preview。
- 相关回归：all/selected Analysis tests、Voice Plaza tests。
- 静态检查或构建：Ruff、mypy、frontend lint/typecheck/build。
- 专项真实边界：PostgreSQL Analysis Run integration。
- 就绪检查：python scripts/quality/check_change_completion.py --root . --require-active-ready + PR CI。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 动态筛选条件在 AI 执行期间自我改变；大 query 长事务 | 先冻结 ID+Version；query 有界 keyset batch |
| 兼容性 | additive | selected/all 与历史 query snapshot 保留 |
| 数据 / Migration | 不适用 | 无 Schema 变化 |
| 部署 / 运行 | 无新增进程/配置 | 复用当前 API/Worker |
| 回滚 / 恢复 | 可直接回滚源码 | 无不可逆数据变化 |

# 文档、依赖、部署与发布影响

- 长期文档：targeted 更新 docs/appendix/07_AI舆情打标与分析实现.md 的 Scope / Planner 说明。
- 依赖 / Runtime：不新增、不升级。
- 配置 / Secret：不改变。
- 部署 / Release：不新增 Migration 或额外步骤；本任务不执行生产 Deploy。
- 兼容 / 消费方通知：generated client 同步新 query Scope；旧 selected/all 兼容。

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V0 | first implementation branch | pytest tests/contracts/test_stage12_analysis_run_http.py -q | 预期 Red：query 尚未被 Contract 接受 | TDD 目标已锁定 |

## 未验证内容与剩余风险

当前为实施前 Red 阶段，尚不能声明功能完成或可合并。

## 交付状态

- 提交：首个 Change + Red test 提交。
- 拉取请求：待创建。
- CI：待执行。
- 合并：待所有门禁绿色后执行。
- Change 归档：merge 后由正式流程处理。
- 发布 / 部署：不适用。

## 备注

无。
