---
schema: coding-change/v1
id: CHG-20261002-174500-tikhub-plan-full-comments
title: TikHub采集计划产品化与全量评论采集
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/694-tikhub-plan-full-comments
created: 2026-10-02T17:45:00+08:00
updated: 2026-10-02T17:45:00+08:00
completion_gate: required
depends_on: []
affected_areas: [collection, content, frontend, contracts, database, docs]
affected_paths: [backend/src/aima_ugc/contracts, backend/src/aima_ugc/modules/collection, backend/src/aima_ugc/adapters/persistence/postgres, backend/src/aima_ugc/bootstrap, frontend/src/features/collection-strategy, frontend/src/generated/api/client, frontend/e2e, frontend/fullstack, tests, migrations/versions, docs]
contracts: [CollectionPlanCreateRequest, CollectionPlanResponse, CollectionDecisionPolicyV1, CollectionDecisionRequestV1, ReplyDecisionRequestV1, collection-run-config]
data_changes: [collection_plans.plan_type, collection_content_actions.comment_action, collection_plan_decision_policies.policy]
---


# 变更摘要

用户批准36节完整方案（Issue #694），需要把计划从固定TikHub/adaptive配置提升为显式类型与可解释adaptive/full策略；复用现有分页和UI基础，保留历史冻结。风险L3，用户授权分支、commit/push/PR、验证后merge。

# 背景、现状与问题

## 背景
持续监测需要可解释采样，深度采集需要真实全量；未来采集类型有独立领域身份。

## 当前现状
main 0a8f6b4c无plan_type；Plan/API/Scope只允许adaptive；创建和编辑共用抽屉。Supplement已有全量分页和100页保护。

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
root/thread最新coverage聚合及增量证明细节需进一步追当前生产Owner；未知Provider数量不可推断完整。

# 目标、成功标准与非目标

## 目标
完成Issue AC1–AC26全部产品能力并为AC27–AC28完成交付。

## 成功标准
- [ ] Issue AC1–AC26逐项有直接Evidence。
- [ ] AC27达到current-head/current-base Ready，AC28由post-merge生命周期取得证据后闭环。

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
| --- | --- | --- | --- |
| R1 | 采集策略仍含关键词包和采集计划；采集计划是多类型父概念，当前仅 TikHub；直接点击“新建 TikHub 采集计划”打开配置，UI 统一 TikHub，无类型选择中间层。 | #694 / AC1 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R2 | collection_plans 增加非空 plan_type=tikhub 和 Check Constraint；全部既有 Plan 回填 tikhub，既有评论策略保持 adaptive；不重命名关联子表。 | #694 / AC2 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R3 | 领域/API 区分通用 Plan 事实与 TikHub 类型配置，类型成为一级事实，不从 provider 推断，不预造未来类型或堆 Optional 字段；当前专属关联受类型约束。 | #694 / AC3 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R4 | Scheduler、手动计划运行及执行入口按 plan_type 分发；未知类型 fail closed，不创建或错误执行 TikHub Run/Scope/请求。 | #694 / AC4 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R5 | 新 Run 显式冻结 schema_version、plan_type、schedule_version、comment_policy 和一致执行策略；仅旧 collection-run-config.v2 缺类型时解释为 TikHub，不重写历史快照。 | #694 / AC5 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R6 | comment_policy 和 decision_policy.comment_mode 支持 adaptive/full，默认 adaptive，创建/更新单向同步或校验一致，不能出现 full/adaptive 矛盾；编辑仅影响未来 Run，不能启动历史补采。 | #694 / AC6 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R7 | 新增可审计 fetch_full action 并通过正式 Migration 扩展 Check Constraint；Contract/OpenAPI/JSON Schema/TS Client 从事实源生成且无手工 generated 修改。 | #694 / AC7 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R8 | Adaptive 回归：30一级目标30、500一级目标50、30回复目标5、评论数无变化通常跳过，未知数按现有 Probe/Detail 规则。 | #694 / AC8 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R9 | Full 新内容正数或未知数持续分页；500一级不在50停止、30回复不在5停止、未知数不在第一页停止；零评论跳过并形成正确完整事实。 | #694 / AC9 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R10 | Full 完整度由现有 root/thread coverage 聚合：根 complete 且全部必要回复线程 complete 才完整；根 partial 或任何必要线程 partial/缺失均不完整，不另造完整布尔表。 | #694 / AC10 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R11 | Full 先前完整且评论数相同跳过；先前不完整即使数量相同也继续补齐，不能把 Adaptive 样本覆盖误作 Full 完整。 | #694 / AC11 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R12 | 小红书/B站先前全部完整且数量增加时可靠 newest 增量、整页摄取和稳定 known boundary；证明满足时保持 complete，证据不足时 partial，不丢同页新评论或尚未补齐回复。 | #694 / AC12 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R13 | 抖音/微博/快手数量变化时按能力受控全量刷新并 Stable ID 去重、直到 Provider exhausted；不能退回50条自适应。 | #694 / AC13 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R14 | Full 二级线程 complete 且 reply_count 未变时跳过；数量改变/未知或线程partial时继续补齐；内容级和线程级均避免重复付费请求。 | #694 / AC14 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R15 | Plan Full 与 batch/content/date Supplement 统一全量判定并共用正式 comments/sub_comments 分页、Mapper/Canonical/Ingestion/Coverage；保留补采既有语义、Raw恢复、Fencing/取消。 | #694 / AC15 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R16 | 保留根/回复各100页安全上限；page_limit、分页停滞或Provider无法继续时明确partial及stop_reason，不能误标complete；全量仅承诺可获取范围。 | #694 / AC16 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R17 | 创建/编辑复用同一个 TikHubPlanDialog 和 AimaModalContainer；详情继续Drawer；约960×820且受viewport-48约束，固定Header/Footer、Body滚动、低干扰滚动条，无Wizard或第三套Modal基础。 | #694 / AC17 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R18 | Modal 基本信息、频率两列；关键词包/品牌两列；“采集渠道”改“目标平台”；五平台卡片大屏双列/窄屏单列，未选择平台不展开参数，保留真实Search能力选项、启用配置。 | #694 / AC18 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R19 | 评论策略两个Radio Card；Adaptive明确一级≤50尽量完整、>50默认50、回复默认5、无变化/可靠增量；Full说明一级+二级全部可获取、刷新/分页/部分与限制。 | #694 / AC19 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R20 | Full清晰提示TikHub请求及费用显著增加、当前没有请求或金额预算上限；规则说明与冻结执行参数一致，不作虚假完整或零成本承诺。 | #694 / AC20 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R21 | Modal Browser覆盖中央弹窗、Header/Footer/Body、取消/关闭/焦点、编辑回显/保存刷新、保存pending防重复及失败保留草稿。 | #694 / AC21 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R22 | 列表使用名称/类型/状态/采集范围/策略/调度与下次运行/操作；TikHub Badge与adaptive/full策略正确，不把平台作为通用顶层列。 | #694 / AC22 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R23 | 详情Drawer使用通用壳和TikHub专属配置，显示类型、策略、真实一级/回复/刷新规则、关键词包/品牌/平台/搜索参数；创建/编辑/复制/列表/详情完整round-trip。 | #694 / AC23 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R24 | 本地 Domain/Decision、Contract、PostgreSQL Migration旧数据/CRUD、Scheduler冻结、Collection执行/coverage/replies/安全上限及Adaptive回归均取得直接证据。 | #694 / AC24 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R25 | Frontend Unit/Browser Mock、正式build和少量Real Full-stack Golden Path：浏览器创建计划→真实API→PG→Scheduler Run→冻结快照，覆盖full/adaptive接线；Mock不冒充真实链。 | #694 / AC25 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R26 | 同步受影响正式Product/Blueprint/Collection/模块文档与操作/回滚事实，完整保留36节原方案和逐AC追溯；Completion Audit重读上游且反向核对入口/实现/结果，两阶段独立Review无阻塞项。 | #694 / AC26 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R27 | 从最新main创建本地任务分支，Issue/Change/首个治理或失败测试提交/首次push/早期PR稳定关联；本地验证和current-head/current-base required CI满足后按用户授权guarded merge远程main，必要管理员权限仅按实际授权规则使用。 | #694 / AC27 | not_satisfied | 开发中，尚未取得该行为的直接证据 |
| R28 | 合并后main-fresh和原生Change归档/同ID done得到确认，按直接Evidence回写Issue AC并重读关闭、安全清理任务资源；无Release/Deploy/生产Migration授权，未验证边界如实报告。 | #694 / AC28 | not_satisfied | 开发中，尚未取得该行为的直接证据 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| contracts/planning/Postgres/Scheduler | 显式类型和full策略/冻结 | 类型/兼容/执行 | R2–R7 |
| Collection Decision/Scope/Content Owner | 聚合coverage、增量、回复刷新、复用分页 | 完整且避免重复 | R8–R16 |
| collection-strategy/shared modal/generated | Modal/list/detail/round-trip | 用户入口与解释 | R17–R23 |
| tests/docs/Migration | 层级证据与正式知识 | 安全交付 | R24–R28 |

- [x] 调查当前实现和上游原文，建立Issue并通过create/live校验。
- [x] 新建本地任务分支，风险与验证矩阵已明确。
- [ ] 建立正确Red→Green；完成所有产品要求。
- [ ] 同步正式文档与生成物。
- [ ] 完成独立Review/Completion/CI与最终交付。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Decision/Full state/refresh/replies/adaptive，pytest unit collection/content |
| 接口 / 契约 | required | tests/contracts，generate_contracts.py，Orval drift/TS |
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

- [ ] upstream_re_read：重新读取live #694与36节方案独立重建完成定义。
- [ ] change_coverage：对照全部AC与实现/证据，无遗漏。
- [ ] reverse_audit：Frontend入口↔API/Domain及Scheduler/Worker/Coverage；writer→Migration→reader/历史兼容。
- [ ] unresolved_cleared：全部适用实现要求满足，post-merge生命周期按正式Owner另外闭环。

# 完成证据与状态

## 新鲜证据
| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main 0a8f6b4c Windows | git status；fetch；rev-parse | 干净且与origin/main一致 | 起点 |
| V2 | Issue #694 | canonical prepare/validate create、平台live readback/validate | PASS | 完整需求及机器载体成立 |

| V3 | 本任务分支初始实现前 Windows/Python 3.14.7 | .venv/Scripts/python.exe -X utf8 -m pytest tests/unit/collection/test_tikhub_plan_full_comments.py -q | exit 1，2 failed：Contract拒绝full | 原始缺口可复现Red |

## 未验证内容与剩余风险
所有产品实现和分层证据尚未完成，不能宣称可交付；原方案历史事实需逐项以现代码核验。

## 交付状态
提交/PR/CI/merge/main-fresh/archive/Closure均未执行。用户授权自动完成本地验证后merge；不把自动测试冒称用户人工验收。

## 备注
当前Source Mode读取canonical d2802f6994b78fcd6defed2bd2952acc54f86a35；文件位于本轮从GitHub直接获取的临时源码目录，仅本轮取得规则，未使用目标安装副本。原方案完整保存正式Roadmap和Issue。
