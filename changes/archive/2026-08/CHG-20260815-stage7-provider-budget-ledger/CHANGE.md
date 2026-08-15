---
schema: rvc-change/v1
id: CHG-20260815-stage7-provider-budget-ledger
title: 建立 Stage 7 Provider 多级预算账本
level: L3
status: done
owner: dingyuwen777
branch: feature/stage7-provider-budget-ledger
created: 2026-08-15
updated: 2026-08-15
depends_on: []
affected_areas: [collection, system, database, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/adapters/providers/tikhub/, backend/src/aima_ugc/database_schema.py, migrations/versions/20260815_0012_stage7_provider_budget_ledger.py, tests/unit/collection/, tests/integration/collection/, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/08-采集策略与平台能力.md, docs/blueprint/README.md, docs/collection/README.md, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/stage7-provider-budget-ledger.yml]
contracts: []
data_changes: [provider_requests.provider_config_id, provider_budget_accounts, provider_budget_reservations]
---

# 目标

建立 Stage 7 最终 Provider 多级 Budget Ledger，使真实 billable Attempt 在进入外部发送边界前必须取得数据库硬预算预留，并在 `completed/not_sent/unknown` 终态结算、释放或保守占用；Provider Request 与稳定 `provider_config_id` 绑定，不同配置实例不能混用额度。

在 Review 前进一步确认 TikHub 计费真实性边界：普通业务响应没有被当前证据证明会返回逐请求实际扣费，因此不能把测试值、本地计算值或历史平均值伪装成 TikHub `actual_cost`。本 Change 最终采用后端版本化 Provider Pricing + 发送前保守价格快照 + 可选权威实际费用结算。

# 已确认关键决策

1. TikHub 硬预算价格来自 TikHub 官方 endpoint 价格事实，不使用历史平均费用猜单价。
2. Provider endpoint 单价由后端 Provider Adapter 的版本化配置维护，不在前端展示或编辑，也不包含 API Key、Token、Cookie 等 Secret。
3. TikHub 的全局常见价格或阶梯说明不能作为未核验 endpoint 的发送 fallback；目标 endpoint 未核验精确基础价时 fail closed。
4. 已核验 endpoint 的官方基础价作为 `unit_price_snapshot/estimated_cost` 和货币 Reservation 的保守上界；首版硬预算不因阶梯折扣降低预留。
5. `completed + confirmed` 仅用于 Provider 明确提供权威逐请求费用时，货币账本按 `actual_cost` 结算。
6. `completed + estimated` 表示没有权威逐请求费用：Attempt `actual_cost=0`，Budget 把原保守 Reservation 转入 `settled_amount`；该值是预算占用上界，不是财务账单实际消费。
7. `not_sent` 释放 Reservation；`unknown` 把原预留转入 `unknown_amount` 并继续占预算。
8. TikHub 内新增平台、endpoint 或官方改价，只维护 TikHub Pricing 配置和相应测试；Budget Ledger 核心逻辑不变。
9. 后续新增其他 Provider，由新的 Provider Adapter 维护自己的 pricing 配置/loader，并生成统一 `ProviderBillingV1`；只有出现第二个真实 Pricing 实现后才评估必要公共抽象。

# 成功标准

- [x] `provider_requests` 通过新增 `20260815_0012` 增加兼容可空的 `provider_config_id` 外键；历史 `0001`—`0011` 未改写。
- [x] 新建 Collection Owner 的 `provider_budget_accounts/provider_budget_reservations`，支持 `global/run/run_comments/content_comments` 四层、`request_count/monetary_cost` 两维并绑定稳定 Provider Config。
- [x] 同 Provider Config、Scope、维度、单位的预算周期禁止重叠；范围、时间、金额、单位和关系由 PostgreSQL CHECK/FK/Unique/Exclusion 保护。
- [x] 普通 billable Attempt 原子预留 `global + run`；评论/回复额外预留 `run_comments + content_comments`；每层同时预留请求次数和货币额度。
- [x] 必需账户缺失、超额、来源链不匹配、价格快照无效或 Reservation 不完整时 fail closed，Transport 不得被调用。
- [x] 同 Attempt 预留事务重放幂等；真正网络重试必须创建新 Attempt；并发额度竞争由数据库行锁裁决。
- [x] TikHub 后端 `pricing.toml` + loader 已建立；缺失、未核验、重复、非法或非正精确价格均 fail closed；全局常见价格不作为发送 fallback。
- [x] 已核验 Pricing 可生成 `ProviderBillingV1(status="estimated")`，`unit_price_snapshot/estimated_cost` 使用保守官方基价，`actual_cost=0`。
- [x] Provider Client 使用数据库持久化的发送前 Billing 快照；普通确定响应不能把计划费用覆盖成不计费或改写 estimate，`confirmed` 只能补权威 `actual_cost`。
- [x] `completed + estimated` 的 Attempt `actual_cost=0`，Budget 按原 Reservation 保守结算；`completed + confirmed` 保留泛 Provider 权威实际费用结算能力。
- [x] `not_sent` 全量释放；`unknown` 保守进入 `unknown_amount`；账户可从 Reservation 重算并检测 drift。
- [x] TikHub Pricing 配置通过 Wheel 构建、安装并从 site-packages 实际加载，证明 Release Python 包携带 `pricing.toml`。
- [x] 分支专项 Unit/PostgreSQL/Quality、PR 广域 CI、合并后 main CI 和 main 机器事实均获得新鲜 Green 证据。

# 范围

- Provider Request 稳定 Provider Config 关联。
- Provider Budget Account / Reservation Domain、Table、Migration、Repository/Service。
- 普通/评论 Attempt 多级并发原子预留。
- Dispatch 发送前 fail-closed Budget 门禁和 Dispatch/Recovery 终态记账。
- TikHub 后端版本化 Pricing 配置、严格解析/校验、保守 Billing 构造和 Wheel 资源验证。
- 发送前 Billing 快照和 `estimated/confirmed/unknown/not_sent` 真实性语义。
- Unit/PostgreSQL CI、长期 Blueprint/Collection 文档和 Change 交付闭环。

# 非目标

- 不建立 Plan、Plan Platform、Occurrence、Run Snapshot 或 Scheduler；不决定 `misfire_policy/max_catch_up_runs`。
- 不新增前端价格/预算页面；前端以后只配置预算上限，不维护 Provider 单价表。
- 不实现自动充值、每日用量/余额/账单 Reconciliation。
- 不把“多数服务某价格”批量填成当前 endpoint 精确价格；当前无法核验的 endpoint 保持 `pending_endpoint_info`。
- 不修改抖音/微博/B站/快手 Mapper、真实 Fixture、Capability/Registry 状态。
- 不实现 Retention、生产容量、SLO/RPO/RTO 或生产部署。

# 必须保持不变

- 历史 Migration `0001`—`0011` 不改写。
- Provider Client 一次 Attempt 最多一次 Transport send；重发是新 Attempt。
- Raw → Mapper → Canonical → Ingestion 与数据 Owner 边界不改变。
- Stage 5 `not_billable` Fake/文件型 Attempt 继续兼容。
- Secret/API Key/Token 不进入 Pricing、Budget、Request 参数、日志、Fixture、Change 或测试输出。
- Provider Config 属于 System Owner；Provider Request/Attempt/Budget 属于 Collection Owner。

# 方案比较

## 方案 A：官方价格后端配置 + 保守预留 + 可选权威实际费用（采用）

运行时只使用已核验 endpoint 基价建立发送前快照和硬预算 Reservation；普通 TikHub 响应没有权威逐请求费用时不造 `actual_cost`。该方案可审计、可替换且不依赖前端。

## 方案 B：把 TikHub 常见价格当所有 endpoint 默认价（拒绝）

不同 endpoint 可能不同价，默认值可能低估费用，不能作为硬预算发送依据。

## 方案 C：用历史平均费用做硬预算价格（拒绝）

历史只可帮助预测请求数量或统计异常，不能证明 Provider 当前 endpoint 单价。

## 方案 D：每次业务发送前在线查询价格（拒绝作为运行时主路径）

会增加外部可用性依赖和额外网络链路。官方价格接口可用于开发/运维核验配置，不成为每次采集前的同步依赖。

# 实施结果

1. Provider Budget Ledger：建立四层两维数据库账户/Reservation、稳定 Provider Config 隔离、并发原子预留、同 Attempt 重放幂等、Dispatch fail-closed、终态记账和 drift 审计。
2. TikHub Pricing：建立 `pricing.toml` 与严格 loader；当前已知 Operation endpoint 都显式登记，未核验精确价格保持 `pending_endpoint_info`，不猜默认值。
3. Billing 真实性：billable Attempt 在创建时固化发送前价格快照；Provider Client 使用数据库持久化快照执行单次 Transport send。没有权威逐请求账单时保留 `estimated` 且 `actual_cost=0`；只有 `confirmed` 可补实际费用。
4. Release 资源：CI 构建 Wheel、强制安装到锁定环境并从 `site-packages` 实际加载 `pricing.toml`。
5. 文档：同步数据库、采集策略、Blueprint 导航、Collection 开发说明和“TikHub 改价/新增 endpoint/换 Provider”的维护步骤；Provider 单价明确不属于前端业务配置。
6. Review 中移除了 `docs/blueprint/03-数据库与文件存储.md` 的无关整文件归一化，只保留 `0012` 与预算语义的定点修改。

# Red → Green → Refactor 证据

## Budget Red

- Run `31872227188`：锁定环境安装成功，Budget Unit 因预算生产模块尚不存在以退出码 2 失败，确认是正确功能 Red。

## Pricing / Billing Red

- Run `31875013095`：锁定环境安装成功，Unit 因 TikHub Pricing 生产符号尚不存在以退出码 2 失败。
- 新增 Provider Client 价格快照行为时，先发现 Stage 7 Unit workflow 没有覆盖 `test_provider_client.py`；该次绿色不作为 Red 证据。补齐 workflow 后，Run `31875583663` 的 Unit 因 `planned_billing` 行为尚未实现而失败，形成正确 Red。

## Green / Refactor

- Run `31876319702`：最终代码候选三 Job 全绿；Unit `14 passed`、PostgreSQL `24 passed`，`0011 → head`、`base → head`、`alembic check`、Ruff、mypy、Contract、Architecture、Table Ownership、Secret Scan、Docs、Wheel runtime load 均通过。
- Run `31876394190`：`ready_for_review` 最终 feature HEAD 的 Unit/PostgreSQL/Quality 三 Job 全绿。
- PR #51：head `b9a44d435904822961eb344eaf6ed2915e17d866` 触发 10 个 pull_request Workflow，`10/10` 均为 `success`；无 review submission、无 inline review thread、无普通 PR 评论阻塞。
- 合并后 main：`58e711d3e4d35afc9c6325dea3853d5b915b459a` 触发 10 个 push Workflow，`10/10` 均为 `success`。其中 Stage 7 Budget Run `31876529662` 成功，主 CI Run `31876529598` 的 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 四 Job 全部成功。

# Review

## 阶段一：需求符合性

- 最终差异只覆盖稳定 Provider Config、Budget Ledger、TikHub Pricing、发送前 Billing 快照、对应 Migration/测试/CI/文档；没有实现 Plan/Scheduler、前端、真实付费 Transport、Reconciliation 或其他平台 Mapper。
- 未核验 TikHub endpoint 精确价格没有被猜测；对应配置保持 `pending_endpoint_info` 并 fail closed。
- `actual_cost` 不再由本地估算、历史均值或 Fake 数字解释为 TikHub 实际扣费。
- 用户确认的长期维护规则已经写入 `docs/collection/README.md` 与 Blueprint 08：同一 TikHub 新增平台/改价只维护 Provider Pricing；切换其他 Provider 时新 Adapter 自己维护 pricing，Budget 核心不变；前端不维护 Provider 单价。

## 阶段二：代码质量

- Reservation 使用 PostgreSQL 行锁和调用方事务保证全有或全无；并发、一致性、幂等和 drift 有独立测试。
- Dispatch 在 `reserved → dispatching` CAS 前校验 Job Fence、完整 Budget Reservation 与持久化计划价格快照，外部 HTTP 不在数据库事务中。
- Provider Client 对 planned Billing 做一致性合并：无账单保持 estimate，显式 `not_billable` 才可释放，`confirmed` 只补 actual，unknown 保留计划快照。
- Pricing loader 只使用标准库 TOML/resource，不新增依赖；配置随 Wheel 验证。
- `btree_gist` Migration 需要部署数据库角色具备创建/使用扩展的权限；这是部署前置条件，不在代码中绕过。

# 文档影响

已同步：

- `docs/blueprint/03-数据库与文件存储.md`：稳定 Provider Config、四层两维 Ledger、Reservation/结算语义、Migration 链；
- `docs/blueprint/08-采集策略与平台能力.md`：Provider Pricing、前后端职责、保守预算和 Provider 替换边界；
- `docs/blueprint/README.md`：Stage 7 当前机器事实与剩余工作；
- `docs/collection/README.md`：TikHub 改价/新增 endpoint、换 Provider 的具体维护步骤；
- `backend/src/aima_ugc/modules/collection/README.md`：生产入口、验证命令和当前限制。

# 兼容、Migration、部署与回滚

- Provider V1 公共字段/枚举保持兼容，没有新增破坏性 HTTP API。
- 未新增第三方依赖。
- `0012` 只追加 Budget 表和兼容可空 `provider_config_id`；父 Revision 固定 `0011`。
- billable Provider Dispatch 前必须先升级 `0012`、配置覆盖调用时刻的 Budget Account，并为目标 endpoint 提供已核验 Pricing；任一缺失都 fail closed。
- Schema 可 downgrade `0012 → 0011`；如果预算账本已有数据，downgrade 会删除 Budget 数据并移除 Request Config 关联，执行前必须备份/导出，不能称为无损回滚。
- 当前未执行生产部署。

# 当前未验证事实与风险

- 本任务执行环境无法解析 `api.tikhub.io`，因此没有取得目标 endpoint 的实时 Endpoint Info；对应 Pricing 保持 `pending_endpoint_info`，未伪造价格，也没有确认产生真实 Provider 费用。
- TikHub 逐请求财务账单/余额自动 Reconciliation 尚未实现；TikHub `completed + estimated` 的 `settled_amount` 是保守预算占用，不是实际财务消费。
- 本宿主不能确认用户本地工作区、未提交修改或未推送提交；本 Change 的 Git 结论只基于 GitHub 远端可见事实。
- `btree_gist` 的生产 Migration 权限需要部署前验证。

# Git / 交付状态

- 初始 main：`d44397ae076b5502de310f6f617c85457131d7be`。
- 实现分支：`feature/stage7-provider-budget-ledger`；PR 合并后已删除。
- PR：#51 `Stage 7 Provider 多级预算账本与 TikHub 官方价格边界`。
- PR head：`b9a44d435904822961eb344eaf6ed2915e17d866`。
- 合并 main：`58e711d3e4d35afc9c6325dea3853d5b915b459a`。
- PR CI：10/10 Workflow success。
- 合并后 main CI：10/10 Workflow success。
- 生产部署：未执行。
- Change 已满足成功标准、Review、文档、PR、合并和 main 复验门禁，状态更新为 `done` 并移入本归档目录。
