---
schema: coding-change/v1
id: CHG-20261009-143436-supplement-result-consistency
title: 补采后品牌车型与分析结果一致性修复
level: L3
status: in_progress
owner: maintainer
branch: fix/supplement-result-consistency
created: 2026-10-09T14:34:36+08:00
updated: 2026-10-09T14:34:36+08:00
completion_gate: required
depends_on: []
affected_areas:
  - content
  - vehicles
  - collection
  - analysis
  - reporting
  - workbench
affected_paths:
  - backend/src/aima_ugc
  - migrations/versions
  - tests
  - frontend/e2e-fullstack
  - docs
contracts:
  - CanonicalContentV1
  - BrandVehicleCatalogSnapshot
  - analysis.content-label.v1
data_changes:
  - content_versions.author_snapshot
  - analysis_content_version_reuses
  - voice_plaza_content_projection
---

# 变更摘要

补采成功后，按合并后的完整 Current 原子维护当前版本品牌/车型 Evidence；通过生产输入 Hash 证明等价时引用真实历史 AI Result，保留有效人工审核。输入变化或历史协议不明时保持 stale，补采不创建 AI Run。本轮只开发和本地验证，等待用户本地验收，不 push、不建 PR、不合并、不部署、不操作生产数据。

# 背景、现状与问题

## 背景

上游是用户在本会话提供并批准的《Codex 开发任务书：补采后品牌车型识别与 AI 打标结果一致性修复》，包含 AC01–AC22。引用会话为 chatgpt-conversation://6ac87f50-c62c-83e8-a2b9-7a7343b6d0e8；正式要求以用户粘贴正文及本轮本地交付指令为准。

## 当前现状

起点为 main caf06ae1be1d243545d21a71fcbfe72640d0bd5f。已 fetch origin/main，仍为同一提交，工作区起始无修改。新本地分支为 fix/supplement-result-consistency。

## 问题、根因或约束

补采创建路径返回空 filter_snapshot；Fenced Writer 仅在传入目录和 Resolution 时维护 Evidence，且前置拒绝 unmatched。版本作者快照直接采用稀疏 Observation；AI 查询主要只接受当前版本直接 Result，尚无正式等价复用关系。需要先由 PostgreSQL 回归确认失败。

## 不修改的后果

非 AI 输入字段补齐也可能使当前结果 stale；新 Content Version 的品牌/车型 Evidence 与当前完整正文不一致，人工纠正可能失效。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 补采 Run 未冻结目录 | backend/src/aima_ugc/bootstrap/collection_http.py / _build_scopes | 新补采必须冻结全量有效目录 |
| E2 | Evidence 写入前置 matched 且依赖可选参数 | backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py / ingest_content | 分开接受内容与分类命中 |
| E3 | 已有完整 Current 与人工审核统一解析入口 | backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle_classification.py | 复用生产 Resolver、锁序和 Evidence Owner |
| E4 | 已有生产输入 Hash | backend/src/aima_ugc/modules/analysis/content_labeling.py / content_labeling_input_hash | 不增加相似度机制或 LLM 请求 |
| E5 | 版本作者快照取稀疏 Observation | backend/src/aima_ugc/adapters/persistence/postgres/content.py / _append_content_version | 先保证不可变输入快照一致 |

## 推断与待确认

数据库回归、投影/消费者边界和历史修复运行状态尚需验证，不把代码调查当作执行证据。

# 目标、成功标准与非目标

## 目标

品牌/车型/竞品、有效 AI 结果、人工审核、列表/详情/筛选/导出/报告在补采和恢复后保持一致。

## 成功标准

- [ ] AC01–AC22 均有直接证据或正式不适用依据。
- [ ] Schema、Migration、Owner、Contract、文档及必要真实浏览器链验证闭环。
- [ ] 独立 Review 无 blocking Finding，完成到本地待用户验收。

## 范围

Content 合并/版本作者快照、补采冻结目录及原子 Evidence、Analysis 等价关联及统一读取、人工审核、查询投影与消费者、有界恢复任务、相关测试和正式文档。

## 非目标

不改 Prompt/标签体系、TikHub 评论分页、Job Runtime、依赖、生产数据；不伪造模型或人工执行历史；不合并远程 main。

## 必须保持不变

既有直接 Result/Run 顺序、历史 Run 冻结语义、人工锁及显式解锁、品牌先行 v2、竞品角色推导、表 Owner、Fencing、Source 账本和不在数据库事务内发 HTTP。声音广场不引入全局 active Prompt 失效；工作台保留其已测试的 active Scheme 范围。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 同一事务跨 Owner 编排，业务表仍由原 Repository 写入 | 用户任务书 §3、§7 | Content/Vehicles/Analysis |
| 接口与契约 | 尽量保持 HTTP 响应兼容，若增管理能力则正常生成 Contract | 用户任务书 §6、§8 | API/generated consumer |
| 数据与迁移 | 新 Migration 增加真实 Result 引用关系，不扫描全量 Content | 用户任务书 §4、§8 | Analysis Owner 与投影 |
| 错误与失败语义 | 不能证明等价就 stale；从未分析 pending；事务失败回滚 | 用户任务书 §4、§7 | Writer 与消费者 |
| 兼容性 | 新补采冻结全量目录；历史 Run 按原协议 | 用户任务书 §3.3 | Snapshot/Worker |
| 部署与回滚 | 先升级 DDL 再启动新 Worker；回滚前排空新协议任务 | 用户任务书 §11 | 本轮仅隔离本地验证 |

# 修改方案与决策依据

## 最小充分方案

1. PostgreSQL 回归复现补采缺 Evidence、稀疏作者快照与非输入变更 stale，建立 Red。
2. Content Owner 正确冻结合并作者输入；新补采冻结全量 Catalog，Fenced Writer 合并后重解析并原子维护 Evidence。
3. Analysis Owner 增加轻量等价关系；生产 Hash、可信历史协议、成功 Result、Content 锁共同保护复用。
4. 统一有效结果/人工来源选择，更新声音广场投影、查询、导出、报告、工作台和写资格。
5. 同一规则支持 Dry-run 与有界持久修复；测试 Retry/Fence/并发/回滚和一条真实 UI 补采刷新路径。
6. 同步正式文档，按 changed-scope 检查，重读上游逐 AC 审计与独立 Review。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1–E3 | 复用既有完整 Current 解析和人工锁语义，避免平行识别器 |
| D2 | E4–E5 | 输入先冻结一致，再用 Hash 证明等价，不能靠业务版本或相似度 |

## 备选方案与取舍

历史 Result 原地改版本或复制成新 Result 会污染模型执行历史，用户明确禁止。只在前端显示 completed 不能统一服务端消费者，用户明确禁止。采用用户推荐的独立关联表，最小表达目标版本到真实成功结果的引用和人工继承来源。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 评论/回复/互动不破坏版本及分析 | user:supplement-consistency#AC01 | not_satisfied | 待验证 |
| R2 | URL/发布时间等非输入变更复用 AI | user:supplement-consistency#AC02 | not_satisfied | 待验证 |
| R3 | 稀疏 Detail 保留正文并按完整 Current 分类 | user:supplement-consistency#AC03 | not_satisfied | 待验证 |
| R4 | 新品牌全部命中 | user:supplement-consistency#AC04 | not_satisfied | 待验证 |
| R5 | 删除旧品牌撤销自动命中 | user:supplement-consistency#AC05 | not_satisfied | 待验证 |
| R6 | 多品牌车型归属正确 | user:supplement-consistency#AC06 | not_satisfied | 待验证 |
| R7 | 无品牌仍补采成功 | user:supplement-consistency#AC07 | not_satisfied | 待验证 |
| R8 | 人工品牌车型锁继承 | user:supplement-consistency#AC08 | not_satisfied | 待验证 |
| R9 | 同输入跨版本零 LLM 复用 | user:supplement-consistency#AC09 | not_satisfied | 待验证 |
| R10 | 任一输入字段不同保持 stale | user:supplement-consistency#AC10 | not_satisfied | 待验证 |
| R11 | 未知协议/失败结果不猜测继承 | user:supplement-consistency#AC11 | not_satisfied | 待验证 |
| R12 | 等价输入保留情感标签发声人工修正 | user:supplement-consistency#AC12 | not_satisfied | 待验证 |
| R13 | 人工相关性及 inherit_ai 正确 | user:supplement-consistency#AC13 | not_satisfied | 待验证 |
| R14 | 主动新 Run 执行且直接 Result 优先 | user:supplement-consistency#AC14 | not_satisfied | 待验证 |
| R15 | A→B→A 可引用原始结果 | user:supplement-consistency#AC15 | not_satisfied | 待验证 |
| R16 | 补采/AI/审核并发无错误覆盖 | user:supplement-consistency#AC16 | not_satisfied | 待验证 |
| R17 | 事务中途异常完整回滚 | user:supplement-consistency#AC17 | not_satisfied | 待验证 |
| R18 | Retry/Fence/接管幂等 | user:supplement-consistency#AC18 | not_satisfied | 待验证 |
| R19 | List/Count/详情/筛选一致 | user:supplement-consistency#AC19 | not_satisfied | 待验证 |
| R20 | 导出/工作台/报告/历史冻结一致 | user:supplement-consistency#AC20 | not_satisfied | 待验证 |
| R21 | 历史修复有界恢复且重复运行幂等 | user:supplement-consistency#AC21 | not_satisfied | 待验证 |
| R22 | 批量投影无明显 N+1 或全表扫描 | user:supplement-consistency#AC22 | not_satisfied | 待验证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Content/Collection/Vehicles Repository 与 bootstrap | 合并、冻结及 Evidence 原子收敛 | 当前 Writer 缺口 | R1–R8、E1–E5 |
| Analysis tables/Repository 与 Migration | 正式复用、有效结果/人工来源 | 保留真实历史 | R9–R18 |
| Content projection/query、Reporting/Workbench | 消费统一有效结果 | 端到端一致 | R19–R20 |
| 既有 Job/管理接线、tests、frontend/e2e-fullstack | 历史修复与回归 | 有界恢复和真实接线 | R21–R22 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Hash、解析、作者合并和持久任务规则 |
| 接口 / 契约 | required | Schema/Migration、生成物及管理入口兼容 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL：事务、约束、并发、Fencing、人工与消费者 |
| 用户 / 工作流验收 | required | 声音广场/采集中心补采刷新及本地用户验收 |
| 跨组件关键路径 | required | 真实 Vue/API/DB/Worker，外部 Provider 用受控 Fake |
| 外部依赖 / 供应方探测 | not_applicable | 确定性修复无需付费 TikHub/LLM 当前事实 |
| 构建 / 打包 / 运行 | required | 前端 Build、隔离 Migration/服务启动 |
| 文档 / 治理 / 其他 | required | changed-scope、Owner、架构、Secret、文档与完成检查 |

## 验证计划

目标命令在隔离 PostgreSQL 环境执行 pytest 新回归及相关 content/collection/vehicles/analysis 集成套件；使用 python scripts/dev/validate_changed.py --base origin/main 取得 CI 同源范围，执行所需本地静态、Contract、前端和真实 Full-stack 验证。完成前运行 python scripts/quality/check_change_completion.py --root . --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 作者快照、人工来源和投影跨层一致性 | 锁保护、统一选择与 PostgreSQL 回归 |
| 兼容性 | 历史 Run/Result/Prompt 不变 | 只新增引用事实，直接结果优先 |
| 数据 / Migration | 新 DDL，无自动全量回填 | 历史修复独立有界 Job |
| 部署 / 运行 | 本轮仅隔离本地 | 不迁移用户在用库，不调用付费接口 |
| 回滚 / 恢复 | 排空新协议任务后回退代码 | 保留历史 Result，关联可审计，不自动生产执行 |

# 文档、依赖、部署与发布影响

同步相关 Blueprint、Analysis/Content README、历史修复操作说明。依赖/Runtime 保持锁定版本。无 Secret/Provider 变更。本轮不发布部署；迁移仅用于隔离测试库。

# 完成审计

- [ ] upstream_re_read：重读用户完整任务书与当前正式规则。
- [ ] change_coverage：逐 AC01–AC22 覆盖。
- [ ] reverse_audit：Writer/Migration/Reader/人工入口/冻结消费者双向核对。
- [ ] unresolved_cleared：未满足项清零后再进入 Ready。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V0 | caf06ae1 / Windows | git fetch origin main、git status --short、git switch -c fix/supplement-result-consistency origin/main | 成功；起始工作区干净 | 本地开发基线 |

## 未验证内容与剩余风险

当前处于开发前调查，行为验证和独立 Review 尚未执行，不能声明完成或 Ready。

## 交付状态

- 提交：未提交。
- 拉取请求：未创建；等待用户本地验收。
- CI：远程未触发。
- 合并：未执行。
- Change 归档：未归档。
- 发布 / 部署：未执行；用户只要求本地开发验证。

## 备注

同一 checkout 只有一个生产代码 Writer；独立 Explorer/Reviewer 只读。当前无用户未提交修改。开发前 preflight 必须完成后才修改生产代码。
