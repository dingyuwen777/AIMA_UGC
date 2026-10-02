---
schema: coding-change/v1
id: CHG-20261003-001137-account-discovery-five-platforms
title: 五平台按账号补采正式集成与完整分页核验
level: L3
status: done
owner: codex
branch: codex/account-discovery-five-platforms
created: 2026-10-03
updated: 2026-10-03
completion_gate: required
depends_on: []
affected_areas:
  - collection
  - providers
  - contracts
  - content
  - frontend
  - docs
affected_paths:
  - backend/src/aima_ugc/contracts
  - backend/src/aima_ugc/adapters/providers/tikhub
  - backend/src/aima_ugc/adapters/providers/tikhub_test
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - backend/src/aima_ugc/modules/collection
  - backend/src/aima_ugc/adapters/persistence/postgres/collection.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_provider_execution.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_run_execution.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/jobs.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - tests/fullstack
  - frontend/src/features/collection-supplement
  - frontend/src/features/import-batches
  - frontend/src/generated
  - contracts
  - tests
  - frontend/tests
  - frontend/e2e
  - frontend/e2e-fullstack
  - docs
contracts:
  - CollectionRunCreateRequest
  - CollectionAccountDiscoverySelection
  - CollectionAccountTargetRequest
  - CollectionCapabilityResponse
  - CollectionScopeResponse
  - CollectionRuntimeRecordType
data_changes: []
---

# 变更摘要

当前账号采集只有人工文件入口，缺少持久业务入库和前端。将账号 Discovery 作为既有 Collection 的新来源，复用后续内容、评论、回复和 Owner，修复真实探测发现的分页偏差，交付五平台按账号补采。

# 背景、现状与问题

## 背景

用户要求依次实施两阶段。第一阶段 #696/#697 已真实合并并完成 main-fresh、原生 Archive、Closure 和分支清理；本阶段以上游 #698 为唯一 Acceptance Owner。

## 当前现状

基线 624d3178（产品实现 809afe10）；account_runtime.py 已有五平台账号 Builder/Extractor/Pagination，人工 Runner 禁止写库；HTTP 仅 discovery/batch_supplement/content_supplement，公开 Capability 无账号；新 Run 为 v4。

## 问题、根因或约束

账号身份解析和作品页尚未进入正式 Request/Raw/Job，现有关键词品牌准入不能用于明确账号；微博生产分页把空 since_id 当作耗尽，但真实同 endpoint 第二页返回不同作品。快手搜索上游 400 的根因尚未确认，不能用数字 ID 成功替代高级路径验证。

## 不修改的后果

账号数据无法直接供声音广场和分析使用；直接搬 Runner 会绕过持久恢复、来源、Pricing 与单一 Owner；错误耗尽会漏采作品。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 五平台账号生产 Operation 已存在，公开入口和持久账号 Scope 不存在 | account_runtime.py、contracts/http.py、collection_scope.py | 正式提升发现来源，复用后续链 |
| E2 | collection_scopes 身份为文本列，快照和分页为 JSONB | modules/collection/tables.py、当前 Migration/schema | 预计无需 Migration，继续核验 |
| E3 | 微博两页各 20、ID 零交集，生产均误判耗尽 | 本机脱敏 account-pagination.sanitized.json | 空 since_id 不能独立结束非空页 |
| E4 | 五平台主作品接口有可映射真实结构；快手搜索 400 未闭合 | 本机有界探测及当前官方 TikHub SDK | 全链路与高级身份继续验证 |
| E5 | 10 个新账号 endpoint 官方价格已核验 | 本机 get_endpoint_info 脱敏结果 | 只登记采用的主生产路径 |

## 推断与待确认

实际没有新增账号表、列或 Migration。五平台本机主账号/代表性作品与评论链已经取得新鲜证据；具体样本的历史分页中断、上游 HTTP400 及可访问评论低于详情数均保留。快手高级身份没有通过开放门禁；不将可访问采集能力等同于平台所有历史/不可见数据保证。

# 目标、成功标准与非目标

## 目标

五平台多个账号在指定北京时间范围发现作品、持久采详情及全部可访问评论/回复；用户可观察每账号状态和结果，失败隔离。

## 成功标准

- [x] #698 AC1–AC12 的实现、分层技术验收与文档全部有直接证据；最终交付结果按下方独立门禁继续跟踪。
- [ ] 当前 head/base Review/CI 和完整交付收尾通过。

## 范围

账号 Contract/Capability/Pricing、v5 快照/Scope、持久身份/分页、不同来源准入、共用内容/评论链、生成物、第三 Tab、运行类型/账号进度、分层验收和正式文档。

## 非目标

不新增账号事实表、Runner 或调度系统，不自动分析或跨 family fallback，不升级依赖，不改预算、不部署生产。

## 必须保持不变

Raw/Canonical/Owner、Job Fencing/恢复、业务身份/来源、历史快照、北京时间、生成 Client、100 页评论/回复保护和 Pricing fail closed。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 根 Agent 单一写入，独立只读 Review | #698 | 账号来源复用现有 Owner |
| 接口与契约 | 兼容新增账号模式与元数据，消费生成物 | AC1/AC8/AC9 | HTTP 与 UI |
| 数据与迁移 | 无新业务表，v5 仅新账号 Run | E2/AC3 | 历史解释保留 |
| 错误与失败语义 | 身份失败关闭、覆盖率真实 partial、账号隔离 | AC2/AC4/AC5/AC7 | 不伪造成功 |
| 兼容性 | 既有三种模式和周期策略保留 | AC3 | 无静默变更旧任务 |
| 部署与回滚 | 只合并 main；代码回滚保留事实 | 用户授权 | 无生产迁移/删除 |

# 修改方案与决策依据

## 最小充分方案

1. 账号公共 Contract 和 Capability → HTTP/生产能力/生成物 → 创建验证和 v5 冻结 → Contract Red/Green、真实 PG。
2. 五平台身份与分页 Owner → 生产 Adapter、Debug 复用 → 唯一身份、正确终止 → Fixture 与有界实测。
3. 持久解析与账号发现 → 现有 Scope/Request/Raw/Candidate → 账号+日期准入、品牌 Evidence 补充 → PG 四 Scope、恢复/去重/隔离/500/30。
4. 第三个 Tab 与账号进度 → 同 Feature 和生成 Client → 输入校验、运行查询、详情结果 → Vitest、Browser、真实 Full-stack。
5. 正式文档和完成审计 → 原上游重读和反向能力审计 → 独立两阶段 Review、最新 main 集成、CI/merge/原生 Archive/main-fresh/Closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E2 | 只新增发现来源，不制造第二事实库 |
| D2 | E3/E4 | 实测修复分页，不能用第一页成功代替完整性 |
| D3 | E5 | 开放前核价与响应验证，未知 endpoint 不发送 |

## 备选方案与取舍

调用人工脚本/Excel 再导入会绕开持久请求和来源，拒绝；复制评论 Runner 产生平行 Owner，拒绝；正式来源接入既有引擎满足恢复和产品结果。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 公共账号模式与非法输入 | #698 / AC1 | satisfied | contracts/http.py、collection/accounts.py、test_collection_account_discovery Contract 与 API；生成 OpenAPI/Client check PASS |
| R2 | 五平台稳定唯一身份与真实路径 | #698 / AC2 | satisfied | account_identity/account_runtime、Capability/Pricing；本机主路径探测及 docs/appendix/04。快手仅数字 user_id，高级输入按上游条件门禁未开放，不计成功 |
| R3 | 独立 Scope 与 v5 冻结历史兼容 | #698 / AC3 | satisfied | collection_http/run_policy/execution；真实 PG four_accounts 独立4 Scope，历史 Contract 回归 |
| R4 | 持久请求、Raw 恢复与 Job | #698 / AC4 | satisfied | 生产 Request/Attempt/Raw、Fenced Gateway/Writer、共享 Job 重试/取消/Reaper；PG 正常/失败恢复和6个提交后终态边界通过 |
| R5 | 全作品分页、身份和日期准入 | #698 / AC5 | satisfied | account_discovery 纯准入、生产 Pagination；微博空 since_id、空/重复/保护、作者与北京时间边界回归；真实 B站5页正常结束，其他样本边界如实记录 |
| R6 | 无品牌词入库与单一身份/来源 | #698 / AC6 | satisfied | 五平台无品牌词正式 Worker 入库；关键词/账号跨来源2个 PG 场景，Content/Comment身份与版本一份、来源可查询 |
| R7 | 默认 Full、500/30、真实 partial | #698 / AC7 | satisfied | v5冻结 Full；五平台真实 PG Full500/30及回复恢复；一级+回复合计覆盖差额保留 partial，100页保护沿用生产Owner |
| R8 | 账号运行类型、进度、失败隔离 | #698 / AC8 | satisfied | runtime queries/cursor、HTTP、运行列表/详情生成Client；PG 持续503后健康账号完成、人工重试只重开失败Scope、取消/超时 durable计数 |
| R9 | 第三 Tab 多账号和确认交互 | #698 / AC9 | satisfied | TikHubSupplementDialog、collection-supplement Feature、Vitest/Browser；用户最新并列入口指示已核对，原两个入口保留，平台/账号数量与日期/费用确认，无付费Preview |
| R10 | 声音广场/详情/导出/报告/工作台及主动分析 | #698 / AC10 | satisfied | 正式Full-stack账号4Scope Journey：源Run筛选4内容/8评论、详情、解析Excel4条/8评论、报告预检、主动AI4条/工作台4条；按既有资格/品牌筛选，无自动AI |
| R11 | 本机真实 Provider 证据及边界 | #698 / AC11 | satisfied | 五平台本机有界真实响应/生产Mapper；小红书40、快手46评论合计相符，微博官方非空10回复正确映射；其他差额/网络未知/HTTP400明确 partial，无Secret入Git |
| R12 | 分层验收、文档、Review 与交付 | #698 / AC12 | satisfied | 分层技术验收/文档/完成审计及独立两阶段返修复核已满足提交评审的完成定义：后端2044、前端305、Browser199、Full-stack18、PG731/2skip；当前head/base最终审查、required CI、merge与收尾仍是下方强制交付门禁。本状态不宣称尚未发生的交付动作已完成 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| contracts、capabilities、pricing、生成物 | 新模式与账号 metadata | 公开唯一事实 | R1/R2/R3 |
| account_runtime、operations、必要 identity helper、Debug 消费者 | 身份与分页生产 Owner | 完整性和不反向依赖 | R2/R5/R11 |
| collection_http、scope、run_policy、runtime queries | 创建、执行和查询账号 Scope | 持久链和真实状态 | R3–R8/R10 |
| collection-supplement/import-batches 与 tests | 输入、进度和结果 | 产品闭环 | R8/R9/R10 |
| 分层 tests 和 docs | 直接证据与长期事实同步 | 验收 | R11/R12 |

- [x] 调查当前实现和事实源
- [x] 建立任务路由和验证矩阵
- [x] 行为变化建立失败证据
- [x] 完成最小充分实现
- [x] 同步受影响长期文档
- [x] 取得当前版本验证证据
- [x] 完成需求追溯、完成审计和适用复核；最终head/base增量Review另绑定本次metadata提交

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 五平台身份、分页、日期、准入和表单 |
| 接口 / 契约 | required | 模式/输入、Capability、生成物、历史 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PG 4 Scope、Raw 恢复、去重/隔离/500/30 |
| 用户 / 工作流验收 | required | 表单、运行类型、账号进度与结果 |
| 跨组件关键路径 | required | 正式 API/Job/Worker/DB/Browser Journey |
| 外部依赖 / 供应方探测 | required | 五平台真实主账号和代表性评论链，费用上限/脱敏 |
| 构建 / 打包 / 运行 | required | 静态、生成、构建与 Compose |
| 文档 / 治理 / 其他 | required | Docs/Completion/两阶段 Review/CI |

## 验证计划

pytest unit/contracts/api、目标真实 PG、frontend test/lint/typecheck/build、Browser/Full-stack、generate.py --check、mypy/ruff/docs、validate_changed.py --base origin/main、check_change_completion.py --require-active-ready；付费真实 Probe 仅本机安全 Secret，独立硬限制且无隐藏重试，不进 CI。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 全量增加费用/时长、Provider 限制 | 费用提示、硬页保护和真实 partial |
| 兼容性 | 新增模式/字段，历史保留 | AC1/AC3 |
| 数据 / Migration | 不适用，无新表列或 Migration | E2，最终审计 |
| 部署 / 运行 | 无部署，本机隔离验收 | 用户授权 |
| 回滚 / 恢复 | 回滚代码，保留业务和快照 | 不进行生产删除 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 Product 采集入口、Blueprint 账号来源、TikHub Appendix 主路径和真实验证台账。
- **依赖 / Runtime**：不新增或升级，使用锁定环境。
- **配置 / Secret**：冻结既有 Provider revision，Secret 只引用，不输出。
- **部署 / Release**：不适用，用户要求合并 main。
- **兼容 / 消费方通知**：生成 Client、运行类型与账号 metadata 同步消费者。

# 完成审计

- [x] upstream_re_read：2026-10-03 重新读取 live #698 AC1–AC12、用户第三入口并列指示，以及已取得引用方案正文1–48节/49节片段；与当前正式Product/Blueprint/Provider/Contract/Schema/Job/CI逐项交叉核对。未取得尾部不冒充已读取。
- [x] change_coverage：AC1–AC12逐项对应实现、分层测试与正式文档；完整PG已取得。交付生命周期CI/merge/main-fresh/Archive/Closure/cleanup继续在交付状态独立跟踪，未执行项保持未完成，禁止以Requirement表状态代替这些门禁。
- [x] reverse_audit：后端能力→前端动作→任务→入库→声音广场/评论/导出/报告/工作台；基础内容按既有读模型与筛选读取，AI 派生统计必须经过用户主动 Analysis Run，不强制无品牌 Evidence 的内容进入爱玛默认筛选。
- [x] unresolved_cleared：实现及技术验收的not_satisfied清零，未扩大范围或无依据延期。所有独立Finding已关闭；当前metadata最终Review及远程required CI/交付收尾仍必须真实取得后才能声称整体交付。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 基线 624d3178，本机安全 Secret | 五平台有界官方价格与账号结构探测 | 主作品结构可映射，微博分页偏差，快手搜索失败 | 进入正式实现前事实，非最终验收 |
| V2 | 624d3178 + 新 Contract/分页测试，本地 Python 3.14.7 | pytest tests/contracts/test_collection_account_discovery.py tests/unit/collection/test_account_discovery_pagination.py -q | 10 failed、10 passed | 正式模式/字段不存在；微博非空页空 since_id 错误结束，Red 可复现 |
| V3 | 当前 WIP，隔离 PostgreSQL 18.4 | test_collection_account_discovery + test_stage8e_collection_http_runtime | 111 passed；后续人工重试和取消定向回归通过 | 五平台 Full 500/30、Raw 恢复、正常/重试第二页、账号失败隔离；不是最终 current-head 全量验收 |
| V4 | 当前 WIP，本机 API/Fixture Worker/PG/Chrome | 第三个账号入口四 Scope Full-stack Journey | 1 passed | XHS2/DY1/WB1 实际执行、根/回复、Source筛选、无自动AI、主动分析4条成功、导出4条、报告预检4条/8评论、工作台4条 |
| V5 | 当前 WIP | backend unit/contracts、frontend lint/typecheck/unit、CollectionRuntime browser | 1938 passed/16 skipped/12 subtests；305 frontend passed；20 browser passed | 公共行为、原入口保留和第三并列账号入口；后续修复仍须受影响复跑 |
| V6 | 当前 WIP，确定性 PG | 完成提交窗口取消；人工重试详情失败账号 | Red 取消 status/stage 冲突、部分账号 Canonical 不一致；修复后 3 passed | Job 终态统一取消裁决；账号作品与详情各自不可变，成功 Raw 不重复发送，失败详情新 Attempt |

| V7 | 当前返修工作树，Python3.14.7 / Node24.19.0 | pytest unit/contracts/api；frontend test/lint/typecheck/build；全量Browser workers1 | 2044 passed/16 skipped/12 subtests；305前端；199Browser | 账号公共行为及原并列入口、平台计数确认；没有提高timeout/减少断言 |
| V8 | 当前返修工作树，本机隔离PG/API/正式FixtureWorker/FakeLLM/Chrome | 全套e2e-fullstack，解析下载Excel包/工作表/实际4内容8评论 | 18 passed | 完整账号4Scope、旧5平台日期补采及主动分析/导出/报告/工作台流程；FakeLLM计数按输入身份隔离，旧流程重复分析断言保留 |
| V9 | 当前返修工作树，隔离PostgreSQL | terminal_counts 的6个场景 × 内容/一级/回复提交后 Cancel/Deadline；取消/重试回归 | Red6 failed；Green18 passed | 旧统计checkpoint漏计已复现；Job终态事务复用既有durable计数Owner，健康Scope/分页保留，无新请求或旧Fence写入 |
| V10 | 当前返修工作树 / base624d3178 | 独立两阶段StageA/StageB→REPAIR_VERIFY | F01/F02/F03/F04/F05、A2平台数量/跨来源缺口、B01终态计数均CLOSED；NO_FINDINGS_WITHIN_SCOPE | 根因机制已复核；该结论不代替最终提交/base复核与远程CI |
| V11 | 当前返修工作树，锁定工具链 | mypy backend/src；CI范围ruff/format；generate/check_compatibility；Docs/DocsFacts/Architecture/TableOwner/SecretScan；validate_changed --base origin/main | 440 source PASS；913 formatted；其余PASS；73 changed paths/full profile | 生成物与真实代码一致，无依赖/Migration变更；唯一CI分类结果，非伪造已执行全部CI |
| V12 | 当前工作树构建wheel / 本机正式启动进程 | uv build、隔离venv锁定依赖安装、wheel导入account_runtime/HTTP账号Contract；正式check_local_stack --require-ready | PASS | wheel内真实模块/Contract可用，Backend/Frontend/PostgreSQL readiness与Vite代理通过；最后生产返修仍须远程当前head构建 |

| V13 | 实现head d94769badd53b92c3114232b7bc4b943db2fb460 / base624d3178e8d0fde43066c142f5f9c3a5b5e16c00；一次性本机PostgreSQL18.4 | 按CI逐组独立pytest与正式清库边界：platform/database/jobs/collection/content/ingestion/vehicles；专用55437报告库 | 56+120+22+237+171+111+5+9=731 passed；2 skipped | 全部业务集成Green。报告原55434端口10skip不作通过证据，转符合门禁的55437/aima_report_test后9PASS/1专用浏览器skip；另1为平台进程条件skip，不改安全判断/断言 |
| V14 | d94769ba / 另一独立临时空库 | upgrade head → verify_migration_compatibility.py | PASS；head20261002_0079、alembic check无新upgrade | 历史迁移兼容与当前Schema无新增Migration；原始空库直接downgrade错误为未满足前置步骤，记录后按正式CI顺序重跑 |
| V15 | d94769ba / base624d3178 | 独立提交一致性、上游完成定义与反向审计增量复核 | NO_FINDINGS_WITHIN_SCOPE | 所有返修进入提交且与先前审查工作树一致；R1–R11无需求遗漏；R12全PG完成后本次仅更新审计metadata，最终head另复核 |

验证资产冗余检查：clean。生产身份/分页/Mapper/Raw/计数Owner没有在Probe或测试重新实现；Contract、纯行为、真实PG、Browser与Full-stack分别证明不同边界。新增取消/超时场景复用生产Writer/Job/Reaper，跨来源场景区分完整线程复用与新增回复观察，不为测试制造重发；全栈解析真实下载文件。没有放宽断言/预算/timeout或依赖升级。

## 未验证内容与剩余风险

本 Change 实现和返修已通过完整本机分层验证。远程Draft阶段edited事件只运行轻量治理，因Draft/未Ready状态失败不作产品验收；本次metadata最终Review后触发正式Ready事件，必须取得当前head/base全部required CI后才能merge。main-fresh、原生Archive、IssueClosure与cleanup随后继续执行，当前未取得，不声称整体交付。Human Local Acceptance 为 USER_WAIVED，依据本范围用户明确“所有平台都检查和修复…你自己测试功能没问题之后直接合并”，不冒充 PASSED；仍完成技术验收和全部交付门禁。

## 交付状态

- 提交：治理/Red247a1ac3、实现ae2f7b58；本次返修/完成审计形成后续checkpoint。
- 拉取请求：#699，关联#698；本次达到本地技术Ready，最终metadata Review后提交正式评审并触发全量CI。
- CI：最终实现当前head/base的正式全量CI未取得；先前Draft轻量治理失败不冒充产品Green。
- 合并：未合并。
- Change 归档：合并后原生 Workflow。
- 发布 / 部署：不适用，无生产操作。

## 备注

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/698。canonical Source 当前 main d2802f69 已重核；前阶段归档不是本阶段完成依据。
