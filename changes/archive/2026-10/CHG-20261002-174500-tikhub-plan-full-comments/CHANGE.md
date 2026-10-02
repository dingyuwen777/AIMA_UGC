---
schema: coding-change/v1
id: CHG-20261002-174500-tikhub-plan-full-comments
title: TikHub采集计划产品化与全量评论采集
level: L3
status: done
owner: dingyuwen777
branch: feature/694-tikhub-plan-full-comments
created: 2026-10-02T17:45:00+08:00
updated: 2026-10-02
completion_gate: required
depends_on: []
affected_areas:
  - collection
  - content
  - frontend
  - contracts
  - database
  - docs
affected_paths:
  - backend/src/aima_ugc/contracts
  - backend/src/aima_ugc/modules/collection
  - backend/src/aima_ugc/adapters/persistence/postgres
  - backend/src/aima_ugc/bootstrap
  - backend/src/aima_ugc/modules/system/README.md
  - frontend/src/features/collection-strategy
  - frontend/src/generated/api/client.ts
  - frontend/e2e
  - frontend/e2e-fullstack
  - tests
  - migrations/versions
  - docs
contracts:
  - CollectionPlanCreateRequest
  - CollectionPlanResponse
  - CollectionDecisionPolicyV1
  - CollectionDecisionRequestV1
  - ReplyDecisionRequestV1
  - collection-run-config
data_changes:
  - collection_plans.plan_type
  - collection_content_actions.comment_action
  - collection_plan_decision_policies.policy
  - collection_content_actions.previous_capture_complete
  - ix_comment_thread_coverage_latest_capture
  - ix_comment_coverage_latest_capture
---


# 变更摘要

用户批准36节完整方案（Issue #694），需要把计划从固定TikHub/adaptive配置提升为显式类型与可解释adaptive/full策略；复用现有分页和UI基础，保留历史冻结。风险L3，用户授权分支、commit/push/PR、验证后merge。

# 背景、现状与问题

## 背景
持续监测需要可解释采样，深度采集需要真实全量；未来采集类型有独立领域身份。

## 当前现状
开工基线 main 0a8f6b4c 无 plan_type；Plan/API/Scope 仅 adaptive，创建/编辑共用抽屉。Supplement 已有全量分页及 100 页保护。Final Ready 前已合并远程 main 175b8ff7 的工作台整改、原生归档和共享滚动条提交；双方修改没有 Git 冲突，共享滚动条的实际布局影响已修复并通过原 1 px 容差的几何验收。

## 问题、根因或约束
当前决策仅比较评论数，没有root+thread完整度输入；增量终止写partial；Full不应复制分页或每周期重抓。

## 不修改的后果
用户无法选择全部可获取评论，计划类型与费用行为仍不明确。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Plan固定adaptive | backend/src/aima_ugc/modules/collection/planning.py；contracts/http.py | 扩展显式策略 |
| E2 | 仅Supplement full_capture，已有生产分页 | backend/src/aima_ugc/bootstrap/collection_scope.py | 统一判定并复用 |
| E3 | 本地与origin/main同SHA且干净 | git rev-parse HEAD origin/main；git status --short | 从最新main分支 |

## 推断与待确认
已确认：完整度从 Content Owner 的既有根/线程 coverage 读模型聚合；必要根以 root_comment_id 为空或等于自身 ID 判断，不能用 parent_comment_id 判根。未知数量不能据此标完整，必须持续分页到可审计终止。当前 TikHub 在线可用性、额度及真实生产性能未探测；本次未改 endpoint/排序能力，Provider 专项只沿用既有真实响应 Fixture。

# 目标、成功标准与非目标

## 目标
完成Issue AC1–AC26全部产品能力并为AC27–AC28完成交付。

## 成功标准
- [x] Issue AC1–AC26 的实现、测试和正式文档逐项有直接 Evidence；最终 frozen-head Completion Review/CI 是下方 R27 的合并前交付门禁。
- [x] AC27/AC28 已明确分阶段：Implementation Ready 不宣称 merge 或 post-merge 已发生；Issue 对应 AC 仍未勾选，长期目标保持 active，必须取得平台直接证据后闭环。

## 范围
Plan领域/API/Schema/Repository/Scheduler/Scope/coverage、Frontend Modal/list/detail/store、生成物、测试、正式文档。

## 非目标
不新增第二类型/Provider、预算或endpoint；不改历史Run、依赖、子表名或在用服务；不以编辑触发历史补采。

## 必须保持不变
Adaptive默认、Supplement原语义、Job/Raw/fencing/取消、Owner、生成Client和Secret安全。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 一个writer；完成后独立只读Review | E1/E2及用户要求 | Collection/Content/frontend |
| 接口与契约 | 增量显式plan_type与comment_policy | Issue AC2–AC7 | API/generated |
| 数据与迁移 | 新Alembic、旧Plan回填；历史JSON不改 | AC2/AC5 | PG |
| 错误与失败语义 | 未知类型拒绝、部分不冒充完整 | AC4/AC16 | dispatch/coverage |
| 兼容性 | 旧v2缺类型仅兼容解释；默认adaptive | AC5/AC8 | historical |
| 部署与回滚 | 先Migration后代码；full新工作排空/策略收缩后才回滚 | AC24及Schema约束 | 不操作生产 |

# 修改方案与决策依据

## 最小充分方案
1. 冻结类型/策略Contract与失败测试→Domain/Contract Unit。
2. 新Migration/Repository/Scheduler→隔离PG升级旧Plan、CRUD、snapshot/fail-closed。
3. root/thread聚合与coverage-aware Decision→Unit/Collection Integration；共用Supplement分页→full/partial/incremental/reply refresh。
4. OpenAPI/Orval生成→drift/typecheck。
5. 复用Modal基础改create/edit/list/detail→Unit/Browser/视觉。
6. Real Full-stack→真实API/PG/Scheduler冻结；正式Docs/Completion/独立Review/CI→guarded merge/main-fresh/archive/Closure。

## 证据到决策
| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| 共用生产分页 | E2 | 避免两套恢复/覆盖语义 |
| 显式父类型+当前专属配置 | E1/AC3 | 保持后续类型边界、不预造能力 |

## 备选方案与取舍
A（采用）：显式父类型+类型配置、复用已有表和分页；兼容/迁移面有界。B：只加UI开关和扩大target，无法证明线程完整度和类型分发，不满足AC。C：全面重命名子表/万能executor，迁移维护成本增加且方案禁止。已批准方案A无需重复决策。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 采集策略仍含关键词包和采集计划；采集计划是多类型父概念，当前仅 TikHub；直接点击“新建 TikHub 采集计划”打开配置，UI 统一 TikHub，无类型选择中间层。 | #694 / AC1 | satisfied | TikHubPlanDialog、PlanPanel、CollectionStrategyPage 保留关键词包/计划导航，按钮直接开 TikHub Modal；Browser collection-strategy.spec.ts 的 create/edit/list 断言，最终相关 21 项通过。 |
| R2 | collection_plans 增加非空 plan_type=tikhub 和 Check Constraint；全部既有 Plan 回填 tikhub，既有评论策略保持 adaptive；不重命名关联子表。 | #694 / AC2 | satisfied | Migration 20261002_0079 + database_schema.py 的非空默认及 Check；test_migration_data_lifecycle.py 实际升级旧 Plan 回填 tikhub/adaptive、旧 JSON 不变，未知类型数据库拒绝；upgrade/downgrade/upgrade 通过（migration-01.log）。 |
| R3 | 领域/API 区分通用 Plan 事实与 TikHub 类型配置，类型成为一级事实，不从 provider 推断，不预造未来类型或堆 Optional 字段；当前专属关联受类型约束。 | #694 / AC3 | satisfied | planning.py 的 kw_only TikHubPlanConfig 与通用 Definition/Record；HTTP TikHub 配置基类、显式 Literal 类型；Repository require_tikhub_plan，不从 provider 推断。Domain、API、真实 PG CRUD/复制均通过。 |
| R4 | Scheduler、手动计划运行及执行入口按 plan_type 分发；未知类型 fail closed，不创建或错误执行 TikHub Run/Scope/请求。 | #694 / AC4 | satisfied | Scheduler、execution.create_run 和 Scope 的 require_tikhub_plan/validate_new_run_snapshot；未知类型、空/旧新建格式均在 Repository/Provider 前拒绝。86 项独立 Review 单元通过；scheduled/manual PG 与执行 gateway 实链通过。 |
| R5 | 新 Run 显式冻结 schema_version、plan_type、schedule_version、comment_policy 和一致执行策略；仅旧 collection-run-config.v2 缺类型时解释为 TikHub，不重写历史快照。 | #694 / AC5 | satisfied | scheduler.py、execution.py、tikhub_debug_database.py 新 producer 均冻结 v4/type/policy；绑定 Plan 必须 UUID 及正整数 schedule_version（拒绝 bool/str/缺失），manual ID 必须一致；旧 v2 恢复只解释，既有 Supplement v3 语义保留。Full-stack 两模式及编辑后旧 snapshot 不变通过，F2/F4 均独立复核关闭。 |
| R6 | comment_policy 和 decision_policy.comment_mode 支持 adaptive/full，默认 adaptive，创建/更新单向同步或校验一致，不能出现 full/adaptive 矛盾；编辑仅影响未来 Run，不能启动历史补采。 | #694 / AC6 | satisfied | Plan Service/Repository 同一事务更新 comment_policy 与 Decision policy，并推进 schedule_version/清 cursor；旧请求默认 adaptive，copy 保留 type/policy 且 disabled。真实 Full-stack API 编辑/复制、API 负例及 PG round-trip 通过，无历史补采 Job。 |
| R7 | 新增可审计 fetch_full action 并通过正式 Migration 扩展 Check Constraint；Contract/OpenAPI/JSON Schema/TS Client 从事实源生成且无手工 generated 修改。 | #694 / AC7 | satisfied | models.py fetch_full 枚举；Migration 扩大 action Check；Pydantic 生成 OpenAPI/Decision JSON Schema，Orval 生成 Client。scripts/contracts/generate.py --check 通过；generated 由正式命令产生，未手改。 |
| R8 | Adaptive 回归：30一级目标30、500一级目标50、30回复目标5、评论数无变化通常跳过，未知数按现有 Probe/Detail 规则。 | #694 / AC8 | satisfied | test_stage7_decision.py 和 test_tikhub_plan_full_comments.py：adaptive 根30→30、500→50、回复30→5、无变化跳过。detail_already_fetched 默认 false；真实读完详情仍未知时进入原 probe_first_page 50，初始 defer 和原 Detail 审计保持。 |
| R9 | Full 新内容正数或未知数持续分页；500一级不在50停止、30回复不在5停止、未知数不在第一页停止；零评论跳过并形成正确完整事实。 | #694 / AC9 | satisfied | 真实 PG coverage runtime：500 根跨 5 页不在50停止；30 回复跨页不在5停止；Search/Detail 均未知后评论两页、4次请求并 complete；零根仅 Search/Detail 两次且完整空 coverage。198 项采集集成通过。 |
| R10 | Full 完整度由现有 root/thread coverage 聚合：根 complete 且全部必要回复线程 complete 才完整；根 partial 或任何必要线程 partial/缺失均不完整，不另造完整布尔表。 | #694 / AC10 | satisfied | Postgres content_coverage.py 仅聚合既有 coverage/threads，排除 not_requested 干扰；根 ID 判定修复 F1。真实 PG savepoint 直接证明必要线程 partial 或缺失时 overall false，完整线程恢复后 true，没有新增完整布尔表。 |
| R11 | Full 先前完整且评论数相同跳过；先前不完整即使数量相同也继续补齐，不能把 Adaptive 样本覆盖误作 Full 完整。 | #694 / AC11 | satisfied | Decision 与 previous_from_action 冻结 previous_capture_complete；PG 500 根下一周期仅2次 Search/Detail，无 comments；同数 partial 重新采，Adaptive 样本不误作 Full 完整；恢复从 action 原输入重建而非已写入事实。 |
| R12 | 小红书/B站先前全部完整且数量增加时可靠 newest 增量、整页摄取和稳定 known boundary；证明满足时保持 complete，证据不足时 partial，不丢同页新评论或尚未补齐回复。 | #694 / AC12 | satisfied | xiaohongshu_incremental_comments_runtime.py 验证整页摄取/稳定边界/证据不足；Full reply runtime 对增加根的可靠增量验证 complete 且不重取不变完整线程。Bilibili Decision 可靠 newest、仅已完整可增量的直接单元通过。 |
| R13 | 抖音/微博/快手数量变化时按能力受控全量刷新并 Stable ID 去重、直到 Provider exhausted；不能退回50条自适应。 | #694 / AC13 | satisfied | test_full_count_change_without_reliable_sort_keeps_full_refresh_target 参数覆盖 douyin/weibo/kuaishou，全部 fetch_full、target=None；Scope 统一分页 Stable ID 去重至 exhausted。使用同一生产分发与分页，未退回 Adaptive target。 |
| R14 | Full 二级线程 complete 且 reply_count 未变时跳过；数量改变/未知或线程partial时继续补齐；内容级和线程级均避免重复付费请求。 | #694 / AC14 | satisfied | Full Reply Decision 参数覆盖 complete/同数 skip、变数/未知/partial 继续；真实 PG 30 回复与未知回复都 exhausted，同数第二周期不取回复，增加根但原线程不变不重复 sub_comments。 |
| R15 | Plan Full 与 batch/content/date Supplement 统一全量判定并共用正式 comments/sub_comments 分页、Mapper/Canonical/Ingestion/Coverage；保留补采既有语义、Raw恢复、Fencing/取消。 | #694 / AC15 | satisfied | run_policy.py 共用 is_full_comment_capture；Scope 复用原 comments/sub_comments→Mapper/Canonical/Ingestion/Coverage 生产链。整个 collection 集成含 batch/content/date Supplement、Raw recovery/Provider retry/Worker fence/取消回归通过，没有第二分页引擎。 |
| R16 | 保留根/回复各100页安全上限；page_limit、分页停滞或Provider无法继续时明确partial及stop_reason，不能误标complete；全量仅承诺可获取范围。 | #694 / AC16 | satisfied | MAX_COMMENT_PAGES == MAX_SUB_COMMENT_PAGES == 100 未提高；PG safety boundary 参数分别覆盖根/回复 page_limit 与 stalled，run partial_success、coverage partial、stop_reason 正确。Provider exhausted 只证明可获取范围。 |
| R17 | 创建/编辑复用同一个 TikHubPlanDialog 和 AimaModalContainer；详情继续Drawer；约960×820且受viewport-48约束，固定Header/Footer、Body滚动、低干扰滚动条，无Wizard或第三套Modal基础。 | #694 / AC17 | satisfied | 单一 TikHubPlanDialog 消费 AimaModalContainer，旧 PlanCreateDrawer 删除；详情仍 450px Drawer。几何断言 960×820、viewport-48、24px margin、Header/Footer 固定及 Body 滚动，保留1px容差；仅本 Feature max-width 修复共享滚动条后的4px布局差。 |
| R18 | Modal 基本信息、频率两列；关键词包/品牌两列；“采集渠道”改“目标平台”；五平台卡片大屏双列/窄屏单列，未选择平台不展开参数，保留真实Search能力选项、启用配置。 | #694 / AC18 | satisfied | Modal 基本信息/频率与包/品牌双列、五平台真实 Search capability/provider 配置卡片；未选不展开。宽屏2列/窄屏1列 Browser geometry 和生产 API capability round-trip 通过。 |
| R19 | 评论策略两个Radio Card；Adaptive明确一级≤50尽量完整、>50默认50、回复默认5、无变化/可靠增量；Full说明一级+二级全部可获取、刷新/分页/部分与限制。 | #694 / AC19 | satisfied | TikHubCommentPolicySummary 由 Modal/Drawer 共用，radio 显式 adaptive/full；文案来自真实 Policy 50/5 与 full 无采样上限、可靠增量/全量刷新/partial 规则。策略切换与编辑回显 Unit/Browser 通过。 |
| R20 | Full清晰提示TikHub请求及费用显著增加、当前没有请求或金额预算上限；规则说明与冻结执行参数一致，不作虚假完整或零成本承诺。 | #694 / AC20 | satisfied | Full radio 与详情共用费用提示，明确请求/费用显著增加且无请求/金额预算；代码未添加 Budget Guard，规则显示与冻结 snapshot 一致；Full-stack 验证实际 comment_mode。 |
| R21 | Modal Browser覆盖中央弹窗、Header/Footer/Body、取消/关闭/焦点、编辑回显/保存刷新、保存pending防重复及失败保留草稿。 | #694 / AC21 | satisfied | Browser 相关21项覆盖焦点/中央弹窗/Header/Footer/Body/close/cancel/edit/成功刷新/pending防重与失败保留草稿；组件 Unit 及原295项前端回归通过。几何修复未放宽容差。 |
| R22 | 列表使用名称/类型/状态/采集范围/策略/调度与下次运行/操作；TikHub Badge与adaptive/full策略正确，不把平台作为通用顶层列。 | #694 / AC22 | satisfied | PlanPanel 七列 name/type/status/scope/policy/schedule/action；TikHub Badge 和 adaptive/full 正确，平台仅 scope。Browser 列表/详情与 Unit 断言通过。 |
| R23 | 详情Drawer使用通用壳和TikHub专属配置，显示类型、策略、真实一级/回复/刷新规则、关键词包/品牌/平台/搜索参数；创建/编辑/复制/列表/详情完整round-trip。 | #694 / AC23 | satisfied | PlanDetailDrawer 通用壳 + TikHub type 专属摘要/搜索配置，Modal/Drawer 共用 policy summary；Browser create/edit/pending/list/detail，真实 API copy/update 与 PG round-trip、旧冻结快照不变均通过。 |
| R24 | 本地 Domain/Decision、Contract、PostgreSQL Migration旧数据/CRUD、Scheduler冻结、Collection执行/coverage/replies/安全上限及Adaptive回归均取得直接证据。 | #694 / AC24 | satisfied | backend-final-02.log 2011 passed/16 skipped/12 subtests；pg-final-02.log collection 198 passed；pg-final.log 202 passed 含资源生命周期/Migration；migration-01.log 0079 旧 Plan、Check、降级保护/up-down-up；alembic check 无 drift。所有真实 PG 在任务专属 postgres18.4/5694、aima_ugc_694_v2。 |
| R25 | Frontend Unit/Browser Mock、正式build和少量Real Full-stack Golden Path：浏览器创建计划→真实API→PG→Scheduler Run→冻结快照，覆盖full/adaptive接线；Mock不冒充真实链。 | #694 / AC25 | satisfied | Frontend Unit 295 passed/38 files；全 Browser 初次193 passed+2几何失败，修复后相关21 passed，其余193的无关成功证据有效复用。正式 lint/typecheck/Vite build exit0；最终 Real Full-stack 两模式2 passed，真实 Browser→API→PG→生产Scheduler→v4，编辑/copy/旧Run不变；Mock 未宣称真实Provider执行。 |
| R26 | 同步受影响正式Product/Blueprint/Collection/模块文档与操作/回滚事实，完整保留36节原方案和逐AC追溯；Completion Audit重读上游且反向核对入口/实现/结果，两阶段独立Review无阻塞项。 | #694 / AC26 | satisfied | Product02、Blueprint02/08、Collection/collection/system README、Operations01 已同步当前v4/type/policy/费用/rollback；本 Change 原文附录完整36节，live #694 原文与初始一致（SHA256 E51103752F94AB7B11783250BA3D33CE7D4069A3B08BA3572B0E897E495A2D96）。已重读上游并执行双向审计；独立 Reviewer 需求符合性/代码质量审查 F1–F4 全关闭，本次Repair无新阻塞；Final frozen-head Completion Review 继续作为R27合并门禁。 |
| R27 | 从最新main创建本地任务分支，Issue/Change/首个治理或失败测试提交/首次push/早期PR稳定关联；本地验证和current-head/current-base required CI满足后按用户授权guarded merge远程main，必要管理员权限仅按实际授权规则使用。 | #694 / AC27 | not_applicable | 仅对 pre-merge Implementation Ready 不适用：用户/#694/AC27 明确要求 Ready 后独立最终 Review、current head/base required checks、实时权限及 expected SHA merge。已有 Issue↔Change↔branch↔Draft PR695 和首个push成立，main175b8ff已集成；AC27未勾选，不延期、不降门禁；沿用本仓#692/R51及canonical refs14/23生命周期。 |
| R28 | 合并后main-fresh和原生Change归档/同ID done得到确认，按直接Evidence回写Issue AC并重读关闭、安全清理任务资源；无Release/Deploy/生产Migration授权，未验证边界如实报告。 | #694 / AC28 | not_applicable | 仅对 pre-merge Implementation Ready 不适用：#694/AC28 的 main-fresh、原生同ID archive/done、逐AC Closure/cleanup 必须在merge后发生；native automation 接收active/ready_for_review。Issue AC28和goal保持未完成，无Agent归档提交/PR，无生产Release/Deploy/Migration；沿用本仓#692/R52及canonical refs14/23。 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| contracts/planning/Postgres/Scheduler | 显式类型和full策略/冻结 | 类型/兼容/执行 | R2–R7 |
| Collection Decision/Scope/Content Owner | 聚合coverage、增量、回复刷新、复用分页 | 完整且避免重复 | R8–R16 |
| collection-strategy/shared modal/generated | Modal/list/detail/round-trip | 用户入口与解释 | R17–R23 |
| tests/docs/Migration | 层级证据与正式知识 | 安全交付 | R24–R28 |

- [x] 调查当前实现和上游原文，建立Issue并通过create/live校验。
- [x] 新建本地任务分支，风险与验证矩阵已明确。
- [x] 建立正确 Red→Green；完成所有适用产品要求。
- [x] 同步正式文档与正式命令生成物。
- [x] 开发侧独立 Review 与 Completion Audit 完成，F1–F4 全关闭。
- [ ] 冻结提交后 Final Completion Review、当前 head/base CI、guarded merge 与 post-merge 最终交付。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Decision/Full state/refresh/replies/adaptive，pytest unit collection/content |
| 接口 / 契约 | required | tests/contracts，scripts/contracts/generate.py，Orval drift/TS |
| 集成 / 持久化 / 运行依赖 | required | 专属PG Migration旧Plan/CRUD/Scheduler/Scope/Raw/Fence |
| 用户 / 工作流验收 | required | Frontend Unit/Browser create/edit/list/detail/radio/pending/modal |
| 跨组件关键路径 | required | Browser→真实API→PG→Scheduler Run→Snapshot |
| 外部依赖 / 供应方探测 | not_applicable | 未改endpoint/排序能力，沿用真实fixture；发现新外部事实缺口再追加有界Probe |
| 构建 / 打包 / 运行 | required | npm build、正式后端启动/Contract检查 |
| 文档 / 治理 / 其他 | required | architecture/Owner/secret/docs/change、独立Review/current-head CI |

## 验证计划
目标pytest后扩大相关集合；python scripts/dev/validate_changed.py --base origin/main复用正式分类；Browser/PG独立环境后跑关键Full-stack。Ready前check_change_completion.py --root . --require-active-ready，CI current head/base另取平台证据。

# 风险、兼容性、迁移与回滚

公共接口新增默认字段及full枚举，旧请求保持adaptive；新Run显式类型且历史v2解释有界。Migration新增plan_type和action约束；禁止改旧Migration/JSON。downgrade遇full数据或新快照须阻止丢语义，需先停新任务/恢复adaptive并按数据事实判断。Provider费用可能显著增加，UI说明无预算；无Release/Deploy/生产Migration授权。运行验证只用独占服务端口和专属PG，不修改用户服务。

# 文档、依赖、部署与发布影响

同步采集产品、Blueprint与运行说明，保存批准方案；不升级依赖、不执行生产部署。Migration及旧版本回滚限制须在正式文档描述。

# 完成审计

- [x] upstream_re_read：重新读取live #694与36节方案独立重建完成定义。
- [x] change_coverage：对照全部AC与实现/证据，无遗漏。
- [x] reverse_audit：Frontend入口↔API/Domain及Scheduler/Worker/Coverage；writer→Migration→reader/历史兼容。
- [x] unresolved_cleared：全部适用实现要求满足，Development Review 无阻塞；R27/R28 仅对本阶段不适用，仍为 Issue/goal 的必需交付工作，Final Review/CI/merge/post-merge 按正式 Owner 闭环。

# 完成证据与状态

## 新鲜证据
| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main 0a8f6b4c Windows | git status；fetch；rev-parse | 干净且与origin/main一致 | 起点 |
| V2 | Issue #694 | canonical prepare/validate create、平台live readback/validate | PASS | 完整需求及机器载体成立 |

| V3 | 本任务分支初始实现前 Windows/Python 3.14.7 | .venv/Scripts/python.exe -X utf8 -m pytest tests/unit/collection/test_tikhub_plan_full_comments.py -q | exit 1，2 failed：Contract拒绝full | 原始缺口可复现Red |


## Validation Asset Redundancy

状态：clean。Full Plan 复用 Supplement 分页、Raw/Attempt、Mapper、Ingestion、Owner coverage；生产 policy summary 在 Modal/Drawer 共用，统一 Modal 和全局 scrollbar token 未再造。Full-stack helper 只调正式 Scheduler 并断言冻结事实，不复制 executor/provider；Provider/Mapper 既有真实 Fixture 与 collection 层 Fake 各证明自身边界。全 Browser 的无关193项成功证据与修复后21项相关重跑按失效范围组合，不重复造测试层或掩盖原2项失败。

## Review 记录

独立只读 Reviewer `/root/backend_review` 按 canonical d2802f6 执行需求符合性（A1/A2）与代码质量复核，两次有界 Repair 后 F1根身份、F2新Run格式、F3正式Owner当前格式、F4Plan绑定版本均关闭；最后独立单元86 passed及Full-stack seed门禁1 passed，未写文件/数据库。作者已核对实际diff与原始测试日志。Final Completion Review 必须绑定最终提交及最新main；不得以此开发侧结论代替当前Head/Base CI或合并权限。

## 最终本地执行证据

命令均在仓库根；Python 3.14.7、锁定依赖，Windows任务进程设置 PYTHONUTF8=1，并清除宿主SSLKEYLOGFILE避免系统路径写权限问题（TLS校验不变）。PG执行仅任务专属服务，Browser实际Chrome。

| 命令 / 检查 | 原始日志或平台Owner | 实际结果 / 证明边界 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -X utf8 -m pytest tests/unit tests/contracts tests/api -q` | backend-final-02.log | exit0，2011 passed、16 skipped、12 subtests passed；最终Repair代码 |
| `.venv/Scripts/python.exe -X utf8 -m pytest tests/integration/collection -q` | pg-final-02.log | exit0，198 passed；真实PG全部采集集成 |
| collection + database product resource lifecycle / Migration0079选择集 | pg-final.log / migration-01.log | exit0，202 passed；旧数据/升级降级/Full历史审计保护，后续Repair未改对应Schema机制 |
| `alembic check` | alembic-check-final.log | exit0，No new upgrade operations detected |
| `npm --prefix frontend run test -- --run` | frontend-unit-final-02.log | exit0，295 passed、38 files |
| `npm --prefix frontend run test:e2e` | browser-final.log | 193 passed、2几何失败，保留Red；后续针对失效范围修复重跑 |
| `npm --prefix frontend run test:e2e -- e2e/collection-strategy.spec.ts e2e/collection-strategy-figma-geometry.spec.ts e2e/collection-strategy-figma-projection.spec.ts` | browser-repair-03.log | exit0，21 passed；布局1px容差及交互回归 |
| `npm --prefix frontend run test:e2e:fullstack -- e2e-fullstack/collection-plan-search-config.spec.ts` | fullstack-final-03.log | exit0，2 passed；最终API重启后真实Browser/API/PG/Scheduler adaptive/full |
| `npm --prefix frontend run lint` / `npm --prefix frontend run build` | frontend-lint-final.log / frontend-build-repair-final.log | exit0，ESLint、两种typecheck、正式Vite产物；保留原chunk warning |
| `ruff format --check backend tests scripts migrations` / `ruff check backend tests scripts migrations` / `mypy backend/src/aima_ugc` | 本轮命令输出 | exit0，900 files already formatted、All checks passed、437 source files无问题 |
| `scripts/contracts/generate.py --check` / `npm --prefix frontend run generate:api` | generate-repair-final.log / orval-repair-final-02.log | exit0，当前Schema生成一致；Orval第一次系统文件瞬态UNKNOWN失败已保留，正常重试成功 |
| docs navigation/facts、architecture、table ownership、agent governance | 本轮正式scripts/quality输出 | exit0；正式Owner与机器事实一致、无第二写Owner |
| `python scripts/dev/validate_changed.py --base origin/main` | preflight-final.json | 正式classifier映射，backend/frontend/PG/fullstack impact成立；Windows npm解析以实际npm.cmd执行同一命令，无新mapping |

Red证据：最初full Contract两失败；F1根身份、F2新Run拒绝、F4无效版本17失败、详情后未知根分页1失败均先复现再修复，日志保留；后续相关Green与最终全量集合通过。最后Full-stack首次失败是PG回归清空synthetic Provider配置，重新执行既有opt-in seed后两模式通过，未更改断言或产品能力。

## 未验证内容与剩余风险
产品实现和本地分层证据已完成，仍需 Final current-head/current-base Review/CI 才能 merge。未运行付费 TikHub 在线 Probe，故不证明当前账户额度、线上可用性或真实数据性能；已有真实响应 Fixture/正式 Adapter/Mapper 回归证明当前代码结构。16项单元集合跳过如实保留，不计通过。Vite 现有大 chunk warning 未改阈值。所有 PG 为隔离测试环境，不运行生产 Migration/Release/Deploy。

## 交付状态
首个治理/Red提交4ea78ff已推送并建立Draft PR #695；实现checkpoint1c7244ce及最新main集成49c05beb已在本地。当前Repair与Completion checkpoint待提交并冻结Final Review/head/base，随后更新PR并取得正式CI；merge/main-fresh/archive/Closure/cleanup尚未发生。用户反复明确授权本地验证后自动合并，Human Local Acceptance=USER_WAIVED，不冒称用户人工验收PASSED。

## 备注
当前Source Mode读取canonical d2802f6994b78fcd6defed2bd2952acc54f86a35；文件位于本轮从GitHub直接获取的临时源码目录，仅本轮取得规则，未使用目标安装副本。完整36节原方案保存在本文件末尾原文附录与 live Issue #694；正式知识已迁移到 Product/Blueprint/Collection/Operations Owner，施工方案退出 Live Roadmap。


## 批准方案全文（保持36节细节）

原生归档只移动 CHANGE.md，故将完整方案作为不可变原文附录随同一 Change 归档；验收状态唯一 Owner 仍为 live Issue #694。

````text
# TikHub 采集计划产品化方案

状态：2026-10-02 用户已批准，实施中；验收状态由 [Issue #694](https://github.com/dingyuwen777/AIMA_UGC/issues/694) 的 AC1–AC28 维护。

本文件完整保存用户指定会话《解释评论自适应采集》的最新 36 节方案，避免长任务丢失细节。原文中的“当前”是方案提出时的事实描述，实施前必须与当前代码核验；示例结构为已批准设计意图，不冒充已实现。

上游：会话 `6abf63eb-e0ec-83e8-ab11-7b70807898d7`，用户 2026-10-02 明确要求按方案实施、本地验证后合并远程 main。完整原文同时保留在 Issue 正文。

## 稳定验收索引

<a id="AC1"></a>AC1：采集策略仍含关键词包和采集计划；采集计划是多类型父概念，当前仅 TikHub；直接点击“新建 TikHub 采集计划”打开配置，UI 统一 TikHub，无类型选择中间层。

<a id="AC2"></a>AC2：collection_plans 增加非空 plan_type=tikhub 和 Check Constraint；全部既有 Plan 回填 tikhub，既有评论策略保持 adaptive；不重命名关联子表。

<a id="AC3"></a>AC3：领域/API 区分通用 Plan 事实与 TikHub 类型配置，类型成为一级事实，不从 provider 推断，不预造未来类型或堆 Optional 字段；当前专属关联受类型约束。

<a id="AC4"></a>AC4：Scheduler、手动计划运行及执行入口按 plan_type 分发；未知类型 fail closed，不创建或错误执行 TikHub Run/Scope/请求。

<a id="AC5"></a>AC5：新 Run 显式冻结 schema_version、plan_type、schedule_version、comment_policy 和一致执行策略；仅旧 collection-run-config.v2 缺类型时解释为 TikHub，不重写历史快照。

<a id="AC6"></a>AC6：comment_policy 和 decision_policy.comment_mode 支持 adaptive/full，默认 adaptive，创建/更新单向同步或校验一致，不能出现 full/adaptive 矛盾；编辑仅影响未来 Run，不能启动历史补采。

<a id="AC7"></a>AC7：新增可审计 fetch_full action 并通过正式 Migration 扩展 Check Constraint；Contract/OpenAPI/JSON Schema/TS Client 从事实源生成且无手工 generated 修改。

<a id="AC8"></a>AC8：Adaptive 回归：30一级目标30、500一级目标50、30回复目标5、评论数无变化通常跳过，未知数按现有 Probe/Detail 规则。

<a id="AC9"></a>AC9：Full 新内容正数或未知数持续分页；500一级不在50停止、30回复不在5停止、未知数不在第一页停止；零评论跳过并形成正确完整事实。

<a id="AC10"></a>AC10：Full 完整度由现有 root/thread coverage 聚合：根 complete 且全部必要回复线程 complete 才完整；根 partial 或任何必要线程 partial/缺失均不完整，不另造完整布尔表。

<a id="AC11"></a>AC11：Full 先前完整且评论数相同跳过；先前不完整即使数量相同也继续补齐，不能把 Adaptive 样本覆盖误作 Full 完整。

<a id="AC12"></a>AC12：小红书/B站先前全部完整且数量增加时可靠 newest 增量、整页摄取和稳定 known boundary；证明满足时保持 complete，证据不足时 partial，不丢同页新评论或尚未补齐回复。

<a id="AC13"></a>AC13：抖音/微博/快手数量变化时按能力受控全量刷新并 Stable ID 去重、直到 Provider exhausted；不能退回50条自适应。

<a id="AC14"></a>AC14：Full 二级线程 complete 且 reply_count 未变时跳过；数量改变/未知或线程partial时继续补齐；内容级和线程级均避免重复付费请求。

<a id="AC15"></a>AC15：Plan Full 与 batch/content/date Supplement 统一全量判定并共用正式 comments/sub_comments 分页、Mapper/Canonical/Ingestion/Coverage；保留补采既有语义、Raw恢复、Fencing/取消。

<a id="AC16"></a>AC16：保留根/回复各100页安全上限；page_limit、分页停滞或Provider无法继续时明确partial及stop_reason，不能误标complete；全量仅承诺可获取范围。

<a id="AC17"></a>AC17：创建/编辑复用同一个 TikHubPlanDialog 和 AimaModalContainer；详情继续Drawer；约960×820且受viewport-48约束，固定Header/Footer、Body滚动、低干扰滚动条，无Wizard或第三套Modal基础。

<a id="AC18"></a>AC18：Modal 基本信息、频率两列；关键词包/品牌两列；“采集渠道”改“目标平台”；五平台卡片大屏双列/窄屏单列，未选择平台不展开参数，保留真实Search能力选项、启用配置。

<a id="AC19"></a>AC19：评论策略两个Radio Card；Adaptive明确一级≤50尽量完整、>50默认50、回复默认5、无变化/可靠增量；Full说明一级+二级全部可获取、刷新/分页/部分与限制。

<a id="AC20"></a>AC20：Full清晰提示TikHub请求及费用显著增加、当前没有请求或金额预算上限；规则说明与冻结执行参数一致，不作虚假完整或零成本承诺。

<a id="AC21"></a>AC21：Modal Browser覆盖中央弹窗、Header/Footer/Body、取消/关闭/焦点、编辑回显/保存刷新、保存pending防重复及失败保留草稿。

<a id="AC22"></a>AC22：列表使用名称/类型/状态/采集范围/策略/调度与下次运行/操作；TikHub Badge与adaptive/full策略正确，不把平台作为通用顶层列。

<a id="AC23"></a>AC23：详情Drawer使用通用壳和TikHub专属配置，显示类型、策略、真实一级/回复/刷新规则、关键词包/品牌/平台/搜索参数；创建/编辑/复制/列表/详情完整round-trip。

<a id="AC24"></a>AC24：本地 Domain/Decision、Contract、PostgreSQL Migration旧数据/CRUD、Scheduler冻结、Collection执行/coverage/replies/安全上限及Adaptive回归均取得直接证据。

<a id="AC25"></a>AC25：Frontend Unit/Browser Mock、正式build和少量Real Full-stack Golden Path：浏览器创建计划→真实API→PG→Scheduler Run→冻结快照，覆盖full/adaptive接线；Mock不冒充真实链。

<a id="AC26"></a>AC26：同步受影响正式Product/Blueprint/Collection/模块文档与操作/回滚事实，完整保留36节原方案和逐AC追溯；Completion Audit重读上游且反向核对入口/实现/结果，两阶段独立Review无阻塞项。

<a id="AC27"></a>AC27：从最新main创建本地任务分支，Issue/Change/首个治理或失败测试提交/首次push/早期PR稳定关联；本地验证和current-head/current-base required CI满足后按用户授权guarded merge远程main，必要管理员权限仅按实际授权规则使用。

<a id="AC28"></a>AC28：合并后main-fresh和原生Change归档/同ID done得到确认，按直接Evidence回写Issue AC并重读关闭、安全清理任务资源；无Release/Deploy/生产Migration授权，未验证边界如实报告。

## 已批准方案正文

正文保留全部设计细节；唯一平台缩写规范化为正式标识 `xiaohongshu`，完整逐字原文另保存在 Issue #694。当前实现已有定向补采 v3 快照，因此新计划使用显式类型的 v4，并保留该既有补采兼容边界，不重写历史。

可以。结合前面所有决定，我建议把这次任务定义为一个完整的 **“TikHub 采集计划产品化改造”**，而不是单独改弹窗或评论开关。

核心目标有四个：

1. **“采集计划”成为未来多种采集计划的统一容器**；
2. 当前现有这一类明确命名为 **TikHub 采集计划**；
3. **新建/编辑 TikHub 采集计划改用弹窗，不再使用抽屉**；
4. 评论采集正式支持 **自适应采集 / 全量采集**，并把真实规则告诉用户。

---

# 一、最终产品形态

页面结构保持：

```text
采集策略
├─ 关键词包
└─ 采集计划
```

但“采集计划”从现在开始是一个**上层业务概念**：

```text
采集计划
│
├─ TikHub 采集计划       ← 本次完整实现
│
├─ 未来：其他 API 采集计划
├─ 未来：账号监测计划
├─ 未来：其他数据源采集计划
└─ ...
```

因此右上角当前按钮明确改成：

> **新建 TikHub 采集计划**

UI 文案统一使用官方风格 `TikHub`，不要在界面上写全大写 `TIKHUB`。

目前只有一种计划类型，所以：

```text
点击“新建 TikHub 采集计划”
→ 直接打开 TikHub 计划弹窗
```

**不要现在做一个“请选择采集计划类型”的中间弹窗。**

等第二种真实计划出现后，再把按钮升级为下拉菜单：

```text
+ 新建采集计划
   ├─ TikHub 采集计划
   └─ XXX 采集计划
```

---

# 二、新建/编辑：统一改成弹窗

当前 `PlanCreateDrawer.vue` 不再继续作为创建表单。

当前仓库已经有：

```text
frontend/src/shared/ui/AimaModalContainer.vue
```

它本身就适合复杂配置弹窗：

- 固定 Header；
- 固定 Footer；
- 中间 Body 独立滚动；
- 支持关闭禁用；
- 支持焦点恢复；
- 有统一遮罩；
- 有视口高度限制。

因此**不要再新建第三套 Modal 基础组件**。

建议：

```text
PlanCreateDrawer.vue
        ↓
TikHubPlanDialog.vue
```

使用：

```text
AimaModalContainer
```

而不是 `AimaDrawer`。

---

# 三、创建和编辑都用同一个 Modal

虽然你这次明确说的是“新建不要用抽屉”，但从当前代码来看，创建和编辑使用的是同一套表单字段。

因此最干净的做法是：

```text
新建 TikHub 采集计划
→ TikHubPlanDialog

编辑 TikHub 采集计划
→ 同一个 TikHubPlanDialog
```

通过：

```text
initialPlan == null
→ create

initialPlan != null
→ edit
```

区分。

这样避免以后出现：

```text
创建表单一套
编辑表单另一套
```

逐渐漂移。

而：

> **查看采集计划详情**

仍然保留 Drawer。

最终交互就是：

```text
创建 / 编辑
→ Modal

查看详情
→ Drawer
```

这个职责划分更合理。

---

# 四、TikHub Modal 的尺寸和布局

不建议做成很窄的小弹窗，因为当前配置已经包含：

- 计划名称；
- 关键词包；
- 品牌；
- 五个平台；
- 每个平台 Search 参数；
- 评论策略；
- 执行频率；
- 启用状态。

建议：

```text
width ≈ 960px
height ≈ 820px
```

实际继续由 `AimaModalContainer` 限制为：

```text
min(指定尺寸, viewport - 48px)
```

### 结构

```text
┌──────────────────────────────────────────┐
│ 新建 TikHub 采集计划                ×   │
│ 通过 TikHub 按关键词持续发现并采集内容   │
├──────────────────────────────────────────┤
│                                          │
│  1. 基本信息                             │
│                                          │
│  2. 搜索条件 · 关键词包                  │
│                                          │
│  3. 内容过滤 · 品牌                      │
│                                          │
│  4. 目标平台                             │
│                                          │
│  5. 评论采集策略                         │
│                                          │
│  6. 执行频率                             │
│                                          │
│  7. 创建后启用                           │
│                                          │
│  TikHub费用提示                          │
│                                          │
├──────────────────────────────────────────┤
│                         取消   保存计划  │
└──────────────────────────────────────────┘
```

Header/Footer 固定，中间内容自己滚动。

**不要做 Wizard / 上一步下一步。**

现在字段数量还没复杂到必须分步骤，Wizard 会增加用户修改配置时的操作成本。

---

# 五、Modal 内部布局不要照搬原 Drawer

510px Drawer 是纵向长表单。

改成 960px Modal 后应该利用空间。

## 1. 基本信息

两列：

```text
计划名称                         执行频率
[____________________]          [每6小时 ▼]
```

启用状态放这一组右侧或末尾。

---

## 2. 关键词包和品牌

可以两列布局：

```text
搜索条件 · 关键词包             内容过滤 · 品牌

☑ 品牌词包                     ○ 全部启用品牌
☑ 竞品词包                     ● 指定品牌
                               [爱玛] [雅迪] [...]
```

---

## 3. “采集渠道”改名为“目标平台”

这是前面已经发现的概念问题。

现在：

> 采集渠道 → 小红书 / 抖音 / 微博

这个名称不准确。

真正关系是：

```text
计划类型 / Provider
→ TikHub

目标平台
→ 小红书
→ 抖音
→ 微博
→ B站
→ 快手
```

所以 UI 改成：

> **目标平台**

平台卡片例如：

```text
┌ 小红书 ────────────────────────────────┐
│ ☑ 已启用                               │
│ 排序：[最新]  时间：[一天内] 类型：[全部] │
└────────────────────────────────────────┘
```

五个平台按 2 列排列，大屏两列，小屏退化单列。

未选择的平台不展开参数。

---

# 六、评论采集策略成为正式配置

增加：

## 5. 评论采集策略

使用两个 Radio Card，而不是 Select。

### 自适应采集（推荐）

文案明确告诉用户：

> 适合持续舆情监测，在数据完整度和 TikHub 调用量之间平衡。

并展示：

```text
一级评论：
评论数 ≤ 50 时尽量完整采集；
评论数 > 50 时默认最多采集 50 条。

二级回复：
每条一级评论默认最多采集 5 条。

后续刷新：
评论数没有变化时通常不会重复采集；
支持可靠增量的平台优先只采新增评论。
```

当前已确认：

```text
小红书
B站
```

支持可靠最新评论增量。

---

## 全量采集

文案：

> 尽量采集每个帖子下全部一级评论和二级回复。

说明：

```text
系统会持续翻页，
直到 TikHub / 平台明确返回结束。

已经完整采集且评论没有变化时，
不会每个周期重新全量采集。

出现新增评论后，
系统根据平台能力增量补齐或重新完整刷新。
```

同时展示 Warning：

> 全量采集可能产生显著更多 TikHub 请求和费用。当前系统没有请求次数或金额预算上限。

---

# 七、“全量”必须有准确语义

这里不能给用户错误承诺。

全量的定义应该是：

> **完整度目标 = 全部可获取的一级评论 + 全部可获取的二级回复。**

但受：

```text
TikHub 实际返回范围
平台权限
删除/隐藏评论
分页能力
技术安全上限
```

限制。

因此说明里明确：

> 若达到技术安全上限或 Provider 无法继续分页，系统会记录为“部分采集”，不会误标为完整。

当前：

```text
MAX_COMMENT_PAGES = 100
MAX_SUB_COMMENT_PAGES = 100
```

继续保留。

---

# 八、Plan Type 从现在正式进入领域模型

不能只改 UI 名称。

给：

```text
collection_plans
```

增加：

```text
plan_type
```

当前：

```text
plan_type = "tikhub"
```

即：

```python
CollectionPlanType = Literal["tikhub"]
```

所有现有 Plan Migration 后：

```text
plan_type = tikhub
```

行为不发生变化。

---

# 九、为什么 `plan_type` 不能通过 Provider 推断

以后完全可能出现：

```text
TikHub 关键词监测计划
TikHub 账号监测计划
```

它们 Provider 都可能是：

```text
tikhub
```

但业务计划不是一回事。

所以：

```text
plan_type
```

必须是业务一级事实，而：

```text
provider=tikhub
```

只是执行依赖。

不要写：

```text
if provider == tikhub:
    plan_type = ...
```

这种反推机制。

---

# 十、Collection Plan 成为父模型

最终建议：

```text
CollectionPlan
│
├─ id
├─ plan_type
├─ name
├─ enabled
├─ schedule
├─ schedule_version
├─ next_run_at
├─ created_at
└─ updated_at
       │
       └── type-specific configuration
```

当前：

```text
plan_type=tikhub
        │
        ├─ keyword packs
        ├─ brands
        ├─ platforms
        ├─ provider config
        ├─ search configs
        ├─ detail policy
        └─ comment policy
```

未来新的 plan type 拥有自己的配置。

---

# 十一、不要把所有未来配置塞进一个巨型 Contract

必须避免：

```text
CollectionPlanCreateRequest
├─ keyword_pack_ids?
├─ account_ids?
├─ urls?
├─ tikhub_config?
├─ other_provider_config?
├─ crawler_config?
...
```

最终 Optional 字段越来越多。

建议现在至少在领域/API 层明确：

```text
通用 Plan
+
TikHub Plan Config
```

例如语义上：

```text
CollectionPlanSummaryResponse
→ 通用列表字段

TikHubCollectionPlanResponse
→ TikHub 详细配置
```

详情未来可以自然升级为：

```text
CollectionPlanDetailResponse
= TikHubCollectionPlanResponse
| FutureCollectionPlanResponse
```

以：

```text
plan_type
```

作为 discriminator。

---

# 十二、现有数据库子表暂时不要重命名

当前已有：

```text
collection_plan_platforms
collection_plan_keyword_packs
collection_plan_brands
collection_plan_decision_policies
```

不要为了未来扩展，现在就大规模改名为：

```text
tikhub_collection_...
```

没有必要。

只需要建立约束：

> 当前这些关联配置只适用于 `plan_type=tikhub`。

以后其他 Plan 增加自己的专属表。

这比现在做大规模 Schema 重构更稳。

---

# 十三、Scheduler 必须按 Plan Type 分发

不能让 `plan_type` 只存在于页面。

当前 Scheduler 本质默认所有计划都走现有 TikHub Discovery Pipeline。

需要改成：

```text
Collection Plan
        ↓
plan_type
        ↓
dispatch

tikhub
→ 当前 TikHub Scheduler / Scope / Provider Pipeline

future
→ 对应自己的 executor
```

未知类型：

```text
fail closed
```

不能错误进入 TikHub。

---

# 十四、Run Snapshot 增加 Plan Type

现在 Snapshot 已经冻结：

```text
plan_id
plan_name
schedule_version
detail_policy
comment_policy
decision_policy
platforms
keywords
...
```

增加：

```text
plan_type = tikhub
```

新 Run 必须有：

```text
schema_version
plan_type
plan_id
schedule_version
comment_policy
...
```

---

# 十五、历史 Run 不重写

已经存在的旧：

```text
collection-run-config.v2
```

可能没有：

```text
plan_type
```

不要为了这次改造重写所有历史 JSON Snapshot。

兼容逻辑可以限定为：

```text
旧 v2 snapshot
+ plan_type 缺失
→ legacy interpretation = tikhub
```

仅为了历史兼容。

所有新 Run：

```text
plan_type
```

必须显式存在。

---

# 十六、评论策略 Contract

现状：

```python
comment_policy: Literal["adaptive"]
```

改为：

```python
Literal[
    "adaptive",
    "full",
]
```

默认：

```text
adaptive
```

已有 Plan 全部继续 adaptive。

因此升级不会突然造成大量 TikHub 调用。

---

# 十七、`decision_policy` 与 `comment_policy` 的关系

当前系统同时有：

```text
collection_plans.comment_policy
```

以及：

```text
collection_plan_decision_policies.policy.comment_mode
```

不要再增加第三份规则。

明确：

```text
comment_policy
→ 用户选择的高层业务策略

decision_policy
→ 该策略所使用的执行参数
```

其中必须保证：

```text
comment_policy == decision_policy.comment_mode
```

或者由创建逻辑单向生成。

不能允许它们独立修改后出现：

```text
Plan = full
Policy = adaptive
```

---

# 十八、Comment Action 增加 `fetch_full`

现在：

```text
fetch_adaptive
fetch_incremental
refresh_controlled
probe_first_page
...
```

增加：

```text
fetch_full
```

这样：

```text
Plan = full
→ Decision = fetch_full
```

数据库和排障都能清楚看到为什么进行了大量分页。

同步：

```text
collection_content_actions.comment_action
```

数据库 Check Constraint。

需要正式 Alembic Migration。

---

# 十九、全量采集必须同时考虑一级和二级 Coverage

这是此次不能遗漏的关键点。

“帖子全部评论”不是：

```text
一级评论 complete
```

就够了。

必须满足：

```text
一级评论 coverage = complete

AND

需要采集的二级回复线程全部 complete
```

因此 Full Mode 下一篇内容的完整状态应该由现有 Coverage 数据派生：

```text
FullCommentCaptureState
├─ root_coverage
├─ incomplete_reply_thread_count
└─ full_capture_complete
```

建议**优先从现有 root/thread coverage observation 聚合得到**。

不要一开始就新建一套“complete boolean”表。

只有实际查询性能证明有必要，再做 materialized summary。

---

# 二十、Full Mode 决策矩阵

## 新内容

```text
comment_count = 0
→ skip comments
→ complete
```

```text
comment_count > 0
→ fetch_full
```

---

## 评论数未知

Adaptive：

```text
probe_first_page
```

Full：

```text
fetch_full
→ 持续分页
```

不能第一页之后停止。

---

## 上一次全部完整 + 数量没变

```text
previous count = 300
current count = 300
full_capture_complete = true
```

结果：

```text
skip
```

这保证：

> 全量模式 ≠ 每 6 小时重新全抓。

---

## 上一次不完整 + 数量没变

```text
previous count = 300
current count = 300
full_capture_complete = false
```

结果：

```text
继续补齐
```

不能因为 count 没变化就 skip。

---

# 二十一、小红书 / B站：完整数据后的增量

当前两者：

```text
supports_incremental_comment_sort = true
```

如果：

```text
previous full_capture_complete = true
comment_count 300 → 315
```

可以：

```text
从最新开始
→ ingest 新评论
→ 遇到稳定 known comment boundary
→ 停止
```

这种情况下：

```text
旧 300 完整
+
新增部分完整
=
当前仍完整
```

所以 Full 模式不能像当前普通 incremental 一样一律写：

```text
coverage = partial
```

在满足完整增量证明条件时应该继续：

```text
coverage = complete
```

---

# 二十二、抖音 / 微博 / 快手

当前无法证明可靠 newest-first 增量。

Full Mode：

```text
之前 complete
+
comment_count 改变
        ↓
受控重新分页
        ↓
Stable ID 去重
        ↓
Provider exhausted
```

不能偷偷退回 Adaptive 的 50 条。

---

# 二十三、二级回复也要自适应刷新，不能每次重抓

还有一个容易造成大量费用的问题。

对于 Full Mode：

```text
某一级评论之前：
reply_count = 20
thread coverage = complete

本次：
reply_count = 20
```

即使因为平台不支持一级评论增量而重新遍历到了这条 root comment，也应该：

```text
skip 该 thread
```

不要重新抓 20 个回复。

如果：

```text
reply_count 20 → 24
```

或者：

```text
thread coverage = partial
```

才继续补齐。

所以 Full 模式的优化应该覆盖：

```text
内容级 comment_count
+
root coverage
+
每条 root 的 reply_count
+
thread coverage
```

这才能真正做到：

> **追求完整，但避免重复费用。**

---

# 二十四、复用 Supplement 的 Full Capture

当前代码已有：

```python
full_capture = mode in {
    "batch_supplement",
    "content_supplement",
    "date_supplement",
}
```

不要重新实现一套 Plan Full Loop。

统一为类似：

```text
requires_full_comment_capture(run)
```

判断：

```text
Batch Supplement
→ true

Content Supplement
→ true

Date Supplement
→ true

TikHub Plan + comment_policy=full
→ true

TikHub Plan + comment_policy=adaptive
→ false
```

然后所有模式继续复用：

```text
_fetch_comments
_fetch_sub_comments
advance_comments
advance_sub_comments
Mapper
Canonical
Ingestion
Coverage
```

---

# 二十五、编辑 Full/Adaptive 只影响未来 Run

例如：

```text
Plan 原来 adaptive
→ 用户编辑成 full
```

行为：

```text
未来新创建的 Run
→ full

历史 Run
→ 仍按原 Snapshot解释
```

**不能自动启动历史数据全量补采。**

历史数据补齐继续使用：

```text
声音广场 → 评论补采
日期补采
批次补采
```

这样避免用户只是改配置，却突然产生巨额 TikHub 请求。

---

# 二十六、采集计划列表同步改造

未来这里会放多种 Plan，所以表格不要再过度 TikHub-specific。

建议：

| 列 | 内容 |
|---|---|
| 计划名称 | 名称 + 简要范围 |
| 类型 | `TikHub` Badge |
| 状态 | 已启用 / 已停用 |
| 采集范围 | TikHub 当前显示关键词包、品牌、平台摘要 |
| 采集策略 | 自适应 / 全量 |
| 调度与下次运行 | 每6小时 / 时间 |
| 操作 | 详情 / 启停 |

不要继续把：

> “目标平台”

作为顶层通用列表列。

因为未来其他 Plan 可能根本没有“平台”。

---

# 二十七、计划详情仍然使用 Drawer

详情 Drawer 改成上层通用壳：

```text
PlanDetailDrawer
        │
        └─ plan_type=tikhub
              ↓
          TikHubPlanDetail
```

当前详情展示：

```text
计划类型        TikHub
状态            已启用
执行频率        每6小时
下次运行        ...
```

TikHub 专属：

```text
关键词包
品牌范围
目标平台
搜索参数
评论采集策略
```

---

# 二十八、Full / Adaptive 详情必须写真实行为

Adaptive：

```text
评论策略
自适应采集

一级评论
≤50 尽量完整
>50 默认最多 50 条

二级回复
每条一级评论默认最多 5 条
```

Full：

```text
评论策略
全量采集

一级评论
尽量全部

二级回复
尽量全部

刷新方式
完整且无变化不重复采集；
有新增时按平台能力增量或完整刷新
```

---

# 二十九、Migration

本次至少需要正式 Migration。

## `collection_plans`

新增：

```text
plan_type TEXT NOT NULL
```

迁移：

```text
既有 Plan
→ tikhub
```

然后加：

```text
CHECK plan_type IN ('tikhub')
```

未来新类型通过新 Migration 扩展。

---

## `collection_content_actions`

扩展：

```text
comment_action
```

允许：

```text
fetch_full
```

---

## Decision Policy

允许：

```text
comment_mode:
adaptive | full
```

旧 Plan：

```text
adaptive
```

不改变历史行为。

---

# 三十、前端具体修改范围

至少涉及：

```text
frontend/src/features/collection-strategy/
```

重点：

### `CollectionStrategyPage.vue`

改：

```text
新建采集计划
→ 新建 TikHub 采集计划
```

状态从：

```text
planDrawerOpen
```

改成类似：

```text
tikhubPlanDialogOpen
```

---

### 删除 / 替换

```text
PlanCreateDrawer.vue
```

替换为：

```text
TikHubPlanDialog.vue
```

内部使用：

```text
AimaModalContainer
```

---

### `PlanPanel.vue`

增加：

```text
计划类型
采集策略
```

调整“采集范围”表达。

---

### `PlanDetailDrawer.vue`

改成：

```text
通用 Plan detail shell
+
TikHub-specific detail
```

至少明确显示：

```text
plan_type
comment_policy
```

---

### `store.ts`

支持：

```text
plan_type
comment_policy
```

创建、编辑、复制、列表、详情全部 round-trip。

---

### generated client

必须：

```text
OpenAPI
→ regenerate TS client
```

不能手改 generated 文件。

---

# 三十一、后端主要修改范围

重点包括：

```text
backend/src/aima_ugc/contracts/http.py

backend/src/aima_ugc/contracts/collection/models.py

backend/src/aima_ugc/modules/collection/planning.py

backend/src/aima_ugc/modules/collection/decision.py

backend/src/aima_ugc/modules/collection/tables.py

backend/src/aima_ugc/modules/collection/corrective_tables.py

backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py

backend/src/aima_ugc/bootstrap/collection_strategy_http.py

backend/src/aima_ugc/bootstrap/scheduler.py

backend/src/aima_ugc/bootstrap/collection_scope.py
```

以及对应 Migration、tests 和 generated Contract。

---

# 三十二、不要做的东西

这次不要扩大到：

- 不真正新增第二个采集 Plan 类型；
- 不新增第二个 Provider；
- 不提前设计所有未来采集方式；
- 不重命名全部 Collection 数据表；
- 不创建万能 JSON 配置仓库；
- 不移除 100 页技术安全上限；
- 不修改 TikHub 当前 endpoint；
- 不增加 Budget Account / Cost Guard；
- 不让 Plan 编辑触发历史补采；
- 不复制已有 Supplement 分页逻辑；
- 不在普通 CI 真调用付费 TikHub。

---

# 三十三、Codex 必须覆盖的测试

## A. Plan Type

```text
旧 Plan migration → tikhub

新建 TikHub Plan
→ plan_type=tikhub

Plan List
→ TikHub

Plan Detail
→ TikHub

Run Snapshot
→ tikhub

未知 plan_type
→ fail closed
```

---

## B. Modal

必须 Browser 测：

```text
点击“新建 TikHub 采集计划”
→ 中央 Modal
→ 不再出现右侧 Drawer

Header 固定
Footer 固定
Body 可滚动

保存时不能重复提交
取消正常关闭
编辑正常回显
保存后列表刷新
```

Modal 内滚动继续使用项目统一的低干扰滚动条风格，不产生粗黑滚动条。

---

## C. Adaptive 回归

现有行为不能坏：

```text
30 comments
→ target=30

500 comments
→ target=50

30 replies
→ target=5

comment count unchanged
→ skip
```

---

## D. Full

```text
500 comments
→ 不在 50 停止

30 replies
→ 不在 5 停止

comment_count unknown
→ 不在第一页停止

Provider exhausted
→ complete
```

---

## E. Coverage

```text
root complete
+ all required reply threads complete
→ full_capture_complete=true

root partial
→ false

任意需要的 reply thread partial
→ false
```

---

## F. Refresh

```text
complete + count unchanged
→ skip

partial + count unchanged
→ continue

complete + count increased + xiaohongshu/Bilibili
→ safe incremental

complete + count increased + Douyin/Weibo/Kuaishou
→ controlled full refresh
```

---

## G. Page limit

```text
100 pages reached
→ partial
→ stop_reason=page_limit
```

绝不能标成 complete。

---

# 三十四、验证层次

Codex 最终至少应该取得：

```text
Domain / Decision Unit
→ adaptive/full/coverage/reply refresh

Contract
→ Pydantic
→ OpenAPI
→ generated TS client

PostgreSQL Integration
→ Migration
→ legacy backfill
→ create/read/update

Scheduler Integration
→ plan_type/comment_policy frozen into Run Snapshot

Collection Integration
→ full/adaptive execution decisions

Frontend Unit / Browser Mock
→ Modal
→ create/edit
→ type/comment strategy
→ list/detail

Real Full-stack Golden Path
→ Browser 创建 TikHub Plan
→ API
→ PostgreSQL
→ Scheduler Run
→ Snapshot 正确
```

不需要用真实 TikHub 作为普通 CI 证明。

---

# 三十五、建议 Codex 按这个顺序开发

```text
1. 建立 Requirement / Change
        ↓
2. plan_type Contract
        ↓
3. Migration + Repository
        ↓
4. TikHub Plan Domain
        ↓
5. comment_policy adaptive/full
        ↓
6. Coverage-aware Decision
        ↓
7. 统一 Full Capture
        ↓
8. Scheduler Dispatch + Snapshot
        ↓
9. OpenAPI / generated client
        ↓
10. TikHubPlanDialog Modal
        ↓
11. Plan List / Detail
        ↓
12. Browser + Backend + PostgreSQL 回归
        ↓
13. Full-stack Golden Path
        ↓
14. Docs / Review / PR Ready
```

---

# 三十六、最终完成定义

这次不能以：

> “创建页面已经改成弹窗了”

作为完成。

真正 Done 必须同时满足：

```text
“采集计划”已经成为多类型父概念
+
现有计划明确为 TikHub
+
旧 Plan 全部安全迁移
+
新 Run 明确冻结 plan_type
+
未知类型不会误走 TikHub
+
新建/编辑 TikHub 计划使用 Modal
+
详情仍使用 Drawer
+
UI 明确解释 Adaptive 真实规则
+
用户可选择 Full
+
Full 覆盖一级评论 + 二级回复
+
完整状态考虑 root + reply thread coverage
+
已完整且无变化不会周期性重复抓
+
Partial 即使 count 不变仍继续补齐
+
安全增量不会错误降为 partial
+
Supplement 与 Plan Full 共用生产分页实现
+
达到安全上限明确记录 partial
+
所有历史 Run 语义保持冻结
```

这套方案完成后，你后面再增加其他采集计划时，新增的是一个新的 **`plan_type + 类型专属配置 + executor + 创建 Modal`**；“采集策略 → 采集计划”这个上层结构不需要再次推翻。

````
