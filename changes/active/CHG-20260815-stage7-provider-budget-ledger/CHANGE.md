---
schema: rvc-change/v1
id: CHG-20260815-stage7-provider-budget-ledger
title: 建立 Stage 7 Provider 多级预算账本
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/stage7-provider-budget-ledger
created: 2026-08-15
updated: 2026-08-15
depends_on: []
affected_areas: [collection, system, database, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/adapters/providers/tikhub/, backend/src/aima_ugc/database_schema.py, migrations/versions/20260815_0012_stage7_provider_budget_ledger.py, tests/unit/collection/, tests/integration/collection/, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/08-采集策略与平台能力.md, docs/blueprint/README.md, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/stage7-provider-budget-ledger.yml]
contracts: []
data_changes: [provider_requests.provider_config_id, provider_budget_accounts, provider_budget_reservations]
---

# 目标

建立 Stage 7 最终 Provider 多级预算 Ledger，使真实计费 Attempt 在进入 Provider 发送边界前必须取得数据库硬预算预留，并在 `completed/not_sent/unknown` 终态结算、释放或保守占用；Provider Request 与稳定 `provider_config_id` 绑定，避免不同配置实例混用额度。

本 Change 在 Review 前根据 TikHub 官方计费事实修正一项重要语义：**TikHub 普通业务响应只证明成功请求会计费，不提供已确认的逐请求实际扣费金额，因此系统不得把估算值或 Fake Transport 的 `actual_cost` 冒充 TikHub 实际费用。** TikHub 预算估算必须来自后端版本化官方价格配置；只有经 TikHub 官方 endpoint 信息明确核验的单价才可用于真实发送，缺少已核验单价时 fail closed。

# 本轮已确认计费决策

1. TikHub 价格事实源是 TikHub 官网/官方 endpoint 价格信息，不使用历史平均费用猜测硬预算。
2. 后端保存版本化 TikHub Pricing 配置文件；不进入前端页面，不允许前端修改，也不把 Secret/API Key 写入该配置。
3. TikHub 官网“多数服务 0.001 USD/请求”只作为全局说明，**不是所有 endpoint 的可发送默认价**；因为 TikHub 存在不同价格的 endpoint。具体 endpoint 未经官方价格信息核验时不得使用全局默认值放行请求。
4. 已核验 endpoint 的 `base_price` 作为发送前保守预留金额和 Attempt `unit_price_snapshot`。当前 Budget Ledger 的 `estimated_cost` 对 TikHub 首版同样采用该保守基价，不先用阶梯折扣缩小硬预留。
5. TikHub 的阶梯折扣规则可以保存在 Pricing 配置中作为官方计费规则快照，但在没有逐请求账单/账户级对账实现前，不把折扣计算结果命名为 `actual_cost`。
6. `completed + billing=confirmed` 仅用于真正能提供权威逐请求费用的 Provider，货币预算按真实 `actual_cost` 结算。
7. `completed + billing=estimated` 表示 Provider 没有逐请求权威费用；货币预算按原 Reservation 的保守金额结算，Attempt 的 `actual_cost` 必须保持 0。这是“预算记账上界”，不是财务实际消费。
8. `not_sent` 释放 Reservation；`unknown` 把原 Reservation 转入 `unknown_amount` 并继续占用；如果未来 TikHub Adapter 能根据明确非 200 规则确认不收费，可在 Provider 计费语义中返回不计费结果再释放货币预算。
9. 将来若实现 TikHub `daily usage`、余额或账单对账，应作为独立对账能力增加；在此之前不得声称 `settled_amount` 等于 TikHub 财务账单实际费用。

# 成功标准

- [x] `provider_requests` 通过附加 Migration 增加可追溯 `provider_config_id` 外键；已进入 main 的历史 Revision `0001`—`0011` 不改写。
- [x] 新建 Collection Owner 的 `provider_budget_accounts/provider_budget_reservations`，支持 `global/run/run_comments/content_comments` 四层、`request_count/monetary_cost` 两维并绑定稳定 `provider_config_id`。
- [x] 同 Provider Config、Scope、维度、单位的预算周期禁止重叠；范围、时间、金额、关系由 PostgreSQL 约束保护。
- [x] 普通 billable Attempt 原子预留 `global + run`；评论/回复额外预留 `run_comments + content_comments`；每层同时预留请求次数与货币额度。
- [x] 必需账户缺失、超额、来源链不匹配或 Reservation 不完整时 fail closed，Transport 不得被调用。
- [x] 同 Attempt 预留重放幂等；新 Attempt 独立预留；并发额度竞争由数据库行锁裁决。
- [x] 增加后端 TikHub Pricing 配置与 loader：保存官方全局价格说明/阶梯规则及逐 endpoint 核验状态；没有已核验精确价格的 endpoint 必须 fail closed。
- [x] TikHub Pricing 生成的 `ProviderBillingV1` 使用已核验官方基价作为 `unit_price_snapshot/estimated_cost`，`actual_cost=0`，且不依赖前端输入。
- [x] `completed + estimated` 不再把 0 或猜测值当实际费用，而按原保守 Reservation 进入预算 `settled_amount`；`completed + confirmed` 仍保留泛 Provider 的权威实际费用结算能力。
- [x] `not_sent` 全量释放；`unknown` 保守转入 `unknown_amount`。
- [x] 预算账户可从 Reservation 重算并检测 drift。
- [x] 新计费语义完成 Red → Green → Refactor，独立 Stage 7 Budget CI 新鲜全绿。
- [ ] PR 广域 CI、合并后 main CI 和 main 机器事实重新验证完成；满足前不得归档 Change。

# 范围

- Provider Request 稳定 `provider_config_id` 持久化关联。
- Provider Budget Account / Reservation 数据模型、Table、Migration、Repository/Service。
- 普通 Attempt 两层预算、评论 Attempt 四层预算及并发原子 reserve。
- Dispatch 发送前 fail-closed 预算门禁和 Dispatch/Recovery 终态记账。
- 后端 TikHub Pricing 静态版本化配置、解析/校验、已核验 endpoint 查价与 `ProviderBillingV1` 构造。
- TikHub 没有逐请求权威账单时的保守预算记账语义。
- 独立 Unit/PostgreSQL CI 与相关长期文档。

# 非目标

- 不建立 `collection_plans`、Plan Platform、Occurrence、Run Snapshot 或 Scheduler；不决定 `misfire_policy/max_catch_up_runs`。
- 不新增前端价格/预算页面，不允许前端读取或修改 TikHub Pricing 配置。
- 不实现自动充值、财务账单拉取、每日使用量/余额对账 API；这些属于后续独立能力。
- 不把 TikHub 官网“多数服务 0.001 USD”批量填成所有当前 endpoint 的精确价格。
- 当前执行环境无法解析 `api.tikhub.io` DNS 时，不伪造 endpoint-info 返回；未核验 endpoint 保持不可发送状态。
- 不修改四个平台 Mapper/Fixture/Capability/Registry 状态，不实现 Retention/SLO/RPO/RTO 或生产部署。

# 必须保持不变

- 已进入 main 的 Revision `20260813_0001`—`20260815_0011` 不改写；`0012` 尚未合并，可在本 Change 内修正，但不得创建与本单元无关的 Schema。
- Provider Client 继续一次 Attempt 最多一次 Transport send；真正重发必须新建 Attempt。
- Raw/Mapper/Canonical/Owner Repository 边界不改变。
- 既有 `not_billable` Fake/文件型 Attempt 保持兼容。
- Secret/API Key/Token 不进入 Pricing 配置、Budget 表、Request 参数、日志、Change、Fixture 或测试输出。
- Provider Config 属于 System Owner；Budget 与 Provider Request/Attempt 属于 Collection Owner。
- 同 Provider 类型的不同 `provider_config_id` 预算严格隔离。

# 方案比较

## 方案 A：官方价格后端配置 + 保守预留 + 可选权威实际费用（采用）

已核验 TikHub endpoint 基价固化为后端配置。真实发送前按基价保守 reserve；TikHub 普通响应没有逐请求账单时按 Reservation 上界记预算，不写假 `actual_cost`。其他未来 Provider 若能返回权威逐请求费用，仍可用 `confirmed + actual_cost` 精确结算。

## 方案 B：把 0.001 当 TikHub 所有接口默认单价（拒绝）

TikHub 官方仅说明“多数服务”为 0.001，且文档存在其他固定价格接口。把 0.001 当全局硬预算默认值可能低估费用，不能保证预算限制有效。

## 方案 C：按历史平均费用预测下一次硬预算（拒绝）

历史平均不是 Provider 当前价格事实，价格变更或 endpoint 不同都会导致低估；只可未来用于统计/异常检测，不能用于发送门禁。

## 方案 D：每次业务请求前在线调用 TikHub 价格接口（拒绝作为运行时主路径）

会把真实采集额外依赖网络和价格服务可用性，并增加调用链复杂度。生产运行时以版本化本地配置为事实；官方 endpoint-info 用于开发/运维校验和配置更新。

# Red / Green / Refactor 证据

1. 初始 Budget Red：Run `31872227188` 的 Unit Job 因生产预算模块不存在而退出 2，证明 Budget 行为测试先于实现。
2. 旧 Budget Green：Run `31873153498` 的 Unit/PostgreSQL/Quality 全部成功，作为本次 TikHub 计费语义修正前的回归基线。
3. TikHub Pricing 新 Red：Run `31875013095` 在锁定环境安装成功后，Unit 以 exit code 2 失败，原因是新 Pricing 生产符号尚不存在，符合新的 Red 断言。
4. Green/Refactor 过程中，CI 先后捕获并修正 Ruff、mypy、测试隔离、计划 Billing 贯穿、Provider Persistence 整文件误覆盖和 Wheel 校验环境问题；未关闭或降低任何门禁。
5. 最终代码候选 Run `31876319702` 全绿：
   - Unit：`14 passed`；
   - PostgreSQL：`24 passed`；
   - `20260815_0011 → head` 通过；
   - `base → head` 通过；
   - 三处 `alembic check` 均为 `No new upgrade operations detected.`；
   - Ruff format/check、mypy、Contract generate/compatibility、Architecture、Table Ownership、Secret Scan、Docs 全部通过；
   - Wheel 构建后以 `--reinstall --no-deps` 覆盖锁定 CI venv 中的 editable 安装，实际 `aima_ugc` 导入路径来自 `site-packages`，包内 `pricing.toml` 与运行时 loader 验证成功。
6. 本文件切换到 `ready_for_review` 后仍需以新的最终分支 HEAD 再跑同一 Workflow；只有该 HEAD 全绿才进入 PR。

# Review 门禁

## 阶段一：需求符合性

- TikHub 精确价格不得由测试值、历史平均、前端参数或“多数服务默认价”猜测。
- 未核验 endpoint 发送前必须失败；已核验价格形成 Attempt 快照并进入 Budget Reservation。
- TikHub 无权威逐请求费用时 `actual_cost` 保持 0，文档不得称预算记账值为实际财务消费。
- 本 Change 不扩展到 Scheduler、Plan、前端、财务对账或其他 Stage 7 平台 Mapper。

## 阶段二：代码质量

- Pricing 配置必须可版本控制、可严格解析、Secret-free，并随 Python Wheel 正常打包。
- Budget 终态仍与 Provider Attempt/Artifact 在同一短事务提交；Recovery 使用同一逻辑。
- 继续保持 Reservation 幂等、并发原子性、账户审计和旧 Provider-neutral 行为。
- 不为通过检查降低 Ruff/mypy/Contract/Architecture/Table Ownership/Secret Scan/Docs 门禁。

# 验证范围

- Stage 7 Provider Budget Unit：Budget + TikHub Pricing + Provider Client/Persistence/Dispatch。
- Stage 7 Provider Budget PostgreSQL：Budget + estimated 终态 + Provider Repository/Dispatch、`0011 → head`、`base → head`、`alembic check`。
- Quality：Ruff、mypy、Contract generate/compatibility、Architecture、Table Ownership、Secret Scan、Docs、Wheel 资源/运行时加载。
- PR 广域 CI；合并后 main 新鲜 CI。

# 兼容、Migration、部署与回滚

- Contract：保持现有 Provider V1 字段/枚举兼容；通过更严格的 TikHub Adapter/Provider Client 使用方式和 Budget 终态语义消除假 `actual_cost`，没有为本修正修改 Provider V1 公共 Schema。
- Migration：Pricing 不新增数据表；当前 Schema 变化仍集中在尚未合并的 `0012`，父 Revision 为 `0011`，已验证 `0011 → head` 与 `base → head`。
- 依赖：TikHub Pricing parser 使用 Python 标准库 `tomllib/importlib.resources`，没有新增或升级第三方依赖。
- 部署：真实 TikHub billable Dispatch 只有在目标 endpoint 有已核验配置价且相应 Budget Account 覆盖调用时刻时才允许发送。Migration 使用 `btree_gist`，生产 Migration 角色需要具备创建/使用该 Extension 的权限。
- 回滚：代码可回退 Pricing/记账逻辑；Schema downgrade 仍按 `0012 → 0011`，若预算账本已有数据必须先备份，不能宣称无损回滚。

# 当前未验证事实与风险

- 当前执行环境对 `api.tikhub.io` DNS 解析失败，无法调用 `get_endpoint_info` 取得当前目标 endpoint 精确价格；因此生产 `pricing.toml` 中当前 Operation endpoint 均保持 `pending_endpoint_info`，不会填写未经核验的精确单价。
- TikHub 官网当前公开全局说明为“多数服务 0.001 USD/请求，非 200 不收费”，并提供 endpoint-info / calculate-price / 阶梯折扣能力；这些是配置规则来源，不等于每个目标 endpoint 都已取得精确价格。
- 本轮尚未实现账户级财务对账，因此 Budget `settled_amount` 对 TikHub 只能表示保守记账占用，不应对外称为账单实际消费。
- 用户本地工作树、未推送提交和本地环境状态无法从当前 GitHub connector 确认；本 Change 的 Git/CI 结论仅指远端分支与 GitHub Actions。

# 结束条件

只有两阶段 Review、PR 全绿、合并后 main 新鲜验证全部完成后，才把 `status` 改为 `done`、移动到 `changes/archive/2026-08/`，最后清理本任务分支。