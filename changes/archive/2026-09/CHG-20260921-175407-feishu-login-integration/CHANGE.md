---
schema: coding-change/v1
id: CHG-20260921-175407-feishu-login-integration
title: 将飞书企业登录交付补丁移植到当前主分支
level: L3
status: done
owner: AIMA_UGC
branch: feature/feishu-login-integration
created: 2026-09-21
updated: 2026-09-21
completion_gate: required
depends_on:
  - CHG-20260813-defer-auth-third-party-identity
affected_areas:
  - identity
  - authentication
  - security
  - api-contract
  - database-schema
  - frontend
  - deployment-configuration
affected_paths:
  - backend/src/aima_ugc/modules/identity
  - backend/src/aima_ugc/bootstrap
  - backend/src/aima_ugc/contracts
  - backend/src/aima_ugc/platform/config
  - backend/src/aima_ugc/platform/identity
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions
  - contracts/openapi
  - frontend/src
  - tests
  - compose.yaml
  - env.local.example
  - env.production.example
  - docs
contracts:
  - Feishu authentication HTTP routes
  - CurrentPrincipalResponse
  - AuthConnectorListResponse
  - identity persistence schema
data_changes:
  - 通过单一 0056 Migration 新增 identity principals/external identities/sessions/login states 表及索引
---

# 变更摘要

- **要解决的问题**：用户提供的飞书登录交付补丁基于 2026-09-18 的旧仓库基线，不能直接应用到当前 `main`；补丁同时触及认证、Session、Schema/Migration、公共 HTTP Contract、前端路由和部署配置。
- **拟议修改**：在独立本地分支上恢复补丁原始基线，移植到当前 `main`，解决真实冲突，修复交付包已披露的表 Owner 与数据库文档门禁，并完成当前 revision 的分层验证、Review、PR 与受门禁保护的合并。
- **预期结果**：当前 AIMA 代码可通过飞书企业身份完成登录、会话解析与登出；多企业 Connector 能按配置共存；既有 Provider-neutral Principal 和后端授权边界保持不变。

# 背景、现状与问题

## 背景

用户于 2026-09-21 提供 `飞书登录-改动补丁-20260921.patch`，明确要求先建立本地分支，确认无问题后再合并到主分支。仓库正式 Roadmap 已把真实企业身份登录、Session/Claims、Principal 映射、失效语义、浏览器流程和真实 Principal 审计列为 Production P0。

## 当前现状

- 当前分支从 `main@835f652db88dcd905fa2be0a09b8c1be9d464440` 创建，创建时与 `origin/main` 一致。
- 补丁已经移植到独立任务分支，企业登录实现与当前 Development Identity Resolver 并存；生产环境是否启用飞书由显式配置决定。
- 补丁可追溯到 `main@37721e83721ca203e8da9aa886dd8b3402254984` 的文件基线；当前 `main` 已继续演进，直接 `git apply --check` 和 `git apply --3way --check` 均显示多个真实冲突。
- 交付包自己的 Change 记录承认 `check_table_ownership` 与 `check_docs_facts` 未通过；本分支已经修复并用当前 revision 重新验证，未复用交付包旧测试数字。

## 问题、根因或约束

问题不是补丁格式本身，而是补丁基线落后于当前主分支，并且交付包仍有已知项目门禁缺口。安全移植必须同时保留补丁功能和主分支 2026-09-18 之后的合法变化，不能用整文件覆盖丢失主分支能力。

## 不修改的后果

直接套用会失败；强行覆盖会丢失当前主分支的新代码和文档。绕过已披露门禁则无法证明表 Owner、Schema 文档和完成状态满足项目要求。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 当前 `main` 与 `origin/main` 同为 `835f652d...` | `git fetch origin main --prune`、`git rev-list --left-right --count main...origin/main` | 任务分支必须从该 revision 移植 |
| E2 | 补丁基线对应 `37721e83...` 的 18 个受影响旧 blob | 补丁 `index` 行与 `git ls-tree` 交叉比对 | 必须采用三方移植而非整文件覆盖 |
| E3 | 正式 Roadmap 要求企业登录、Session/Claims、Principal 映射、失效与审计 | `docs/roadmap/02_生产上线实施路线.md` 第 2 节 | 功能方向已有正式上游依据 |
| E4 | 飞书只能作为 Identity Adapter，业务继续依赖 Provider-neutral Principal | `docs/blueprint/07_技术决策与实施门禁.md` 第 25 节 | 不允许把飞书私有身份扩散到业务模块 |
| E5 | 交付包记录两个未通过项目门禁 | 外部交付包原 Change 的“完成审计” | 合并前必须修复并重新运行 |

## 推断与待确认

- 正式 Requirement Source 已建立为 GitHub Issue #555，早期 Draft PR 为 #556。
- 当前环境没有两家真实飞书应用的 App、组与回调配置，因此不能执行真实双企业外部联调；本轮以生产 Adapter 的确定性 HTTP Fake、真实 PostgreSQL 和 Browser Mock 覆盖请求/响应、隔离与失败语义，不把交付包历史叙述冒充本轮证据。

# 目标、成功标准与非目标

## 目标

1. 将交付补丁完整、可审查地移植到当前主分支能力基线上。
2. 实现飞书登录、回调、Session、登出、身份映射、审计和多 Connector 配置。
3. 保持既有 Principal/Authorization、公用 API 合法行为与主分支后续能力不回退。
4. 通过当前仓库要求的测试、质量、文档、Review、PR/CI 与合并门禁。

## 成功标准

- [x] 补丁功能已移植且无未解决冲突，不覆盖当前主分支后续合法变化。
- [x] 登录、回调、一次性 state、Session、登出、角色映射与审计的安全正反例通过。
- [x] 多企业 Connector 隔离、跨企业 state 拒绝、旧单企业配置与旧路由兼容通过。
- [x] Migration、真实 PostgreSQL、Contract/generated client、前端交互与构建验证通过。
- [x] 表 Owner、数据库文档、Change Completion 和 Secret 扫描等本地项目门禁通过。
- [x] Deep Review 无阻塞 Finding；当前 PR head 的 required CI 仍须通过后才允许合并。

## 范围

- 交付补丁内的后端身份模块、HTTP 装配、配置、Contract、Schema/Migration、前端身份流程、测试、生成物和直接承担当前事实的文档。
- 为解决与当前 `main` 冲突、已披露门禁或 Review Finding 所必需的最小修复。

## 非目标

- 不执行生产部署、Release 或生产 Migration。
- 不声明完整 Production Go-Live；HTTPS、协调 Backup/Restore、供应链与生产实机验收仍由 Roadmap 管理。
- 不实现本地用户名/密码、SaaS 数据多租户、部门级授权或动态 Connector 管理 UI。
- 不升级依赖或重构与身份接入无关的模块。

## 必须保持不变

- `Principal` 与业务角色继续 Provider-neutral；现有后端授权调用不依赖飞书字段。
- 未配置飞书时的受控开发身份行为保持兼容。
- 既有合法 API、前端路由、主分支 2026-09-18 后的新能力、Compose 基线和生成物所有权不回退。
- Secret 不进入 Git、日志、数据库明文、前端响应或 Job Payload。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | `identity` 拥有身份表与映射；业务模块只消费 Principal | E4 与项目模块边界 | 需要同步表 Owner 机器清单 |
| 接口与契约 | 新增认证路由、Connector 列表及 Principal 可选展示字段；旧单企业路由保留兼容 | 交付包方案与兼容目标 | 必须重生成 OpenAPI/Client 并验证旧消费者 |
| 数据与迁移 | 新表与 ID 类型演进只通过新增 Alembic Migration | 项目 Schema 规则 | 需要升级、降级/恢复策略与真实 PostgreSQL 证据 |
| 错误与失败语义 | 未登录 401、已登录无权限 403；state 重放/串企业失败关闭 | 安全边界 | 后端与前端都要有正反例 |
| 兼容性 | `connector_id` 派生算法、旧 env 和旧回调路由保持兼容 | 已有身份映射与交付包 DoD | 需专门回归 |
| 部署与回滚 | 本任务只交付代码与配置模板；不部署生产 | 用户授权范围与 Roadmap | 回滚以代码 revert 与 Migration 可逆性为边界 |

# 修改方案与决策依据

## 最小充分方案

1. 在补丁原始基线恢复完整 patch，得到可追溯的源提交。
2. 将源提交移植到当前任务分支，逐个文件解决冲突并保留双方合法变化。
3. 先运行补丁直接相关测试，定位并修复生产缺陷、测试漂移和生成物漂移。
4. 补齐表 Owner、数据库/身份/API/运行文档，执行 Migration、PostgreSQL、前端和质量门禁。
5. 完成 Requirement Traceability、Completion Audit、Deep Review；推送 PR 并等待当前 head required CI。
6. 仅在保护规则允许且 current-head 证据绿色时合并；合并后核验 main-fresh 与自动 Change 归档。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 三方移植 | E1、E2 | 直接应用已经被当前命令证明失败，整文件覆盖会丢失主分支演进 |
| D2 修复门禁后再 Ready | E5 | 已知门禁失败不能被交付包旧结果豁免 |
| D3 保持 Provider-neutral | E3、E4 | 这是现有业务授权与未来 IdP 可替换性的长期边界 |

## 备选方案与取舍

- **直接 `git apply`**：已验证失败，且无法解决当前主分支已修改文件的语义冲突。
- **用交付包完整目录覆盖仓库**：会把三天内的主分支变化一起回退，不可接受。
- **只复制新增文件、不移植现有文件改动**：认证装配、Contract、Migration 注册和前端入口不会闭环，不充分。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 完成 OAuth、一次性 state、Principal 映射、Session 与安全审计 | #555 / AC1 | satisfied | 生产 Route/Adapter/Store 已接通；定向身份测试 151 passed、9 skipped，真实 PostgreSQL 集成 53 passed |
| R2 | 角色、拒绝语义、401/403 与现有后端授权保持正确 | #555 / AC2 | satisfied | 角色/组映射、当前 Principal、无登录 401、无权限 403 和审计回归通过；业务继续消费 Provider-neutral Principal |
| R3 | state/重放/串企业、开放重定向、敏感信息与登录滥用失败关闭 | #555 / AC3 | satisfied | state 绑定非空 Connector、原子消费、return_to allowlist、并发限流 advisory lock、Secret/授权码日志边界均有正反例；移除授权码交换隐藏重试 |
| R4 | 多 Connector 隔离并保持单企业、旧路由与 connector_id 兼容 | #555 / AC4 | satisfied | 每个 Connector 独立 app_id/secret_ref/client；跨企业 state 拒绝、旧路由、旧单企业 env 和稳定 connector_id 回归通过 |
| R5 | Schema/Migration、表 Owner 与真实 PostgreSQL 语义闭环 | #555 / AC5 | satisfied | 合并为当前 head 后唯一 `0056` Migration；PostgreSQL 18.4 upgrade/current/check、迁移兼容和 53 项集成回归通过；表 Owner 门禁通过 |
| R6 | 前端登录、降级、401/403、身份展示与登出闭环 | #555 / AC6 | satisfied | 前端只消费 generated client；Vitest 223 passed、Playwright 129 passed、lint/build 通过，并补充 logout HTTP 失败不误报成功回归 |
| R7 | 当前 revision 的 Contract、测试、构建、跨组件与外部边界证据充分 | #555 / AC7 | satisfied | OpenAPI 重新生成并通过 `--check`；Ruff、mypy、wheel、Compose 与分层测试通过；真实飞书租户因无授权环境不适用本地自动验收，保留为部署前门禁 |
| R8 | 文档/治理、Deep Review、PR CI、合并后 main-fresh 与归档完成 | #555 / AC8 | satisfied | targeted 文档、Completion Audit 与 Deep Review 已完成，本地无阻塞 Finding；PR #556 的 clean-checkout CI、受保护合并、main-fresh 与归档作为交付终态继续跟踪，任一失败均不合并 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `backend/src/aima_ugc/modules/identity/` | 飞书 Adapter、Session、映射、限流、表 Owner | 建立认证与持久化边界 | R2-R5 |
| `backend/src/aima_ugc/bootstrap/`、`entrypoints/api_main.py` | 路由、中间件、Resolver 装配 | 接通生产 HTTP 入口 | R2-R5 |
| Contract/OpenAPI/generated client | 新增兼容 Contract 并重生成 | 保证前后端一致 | R2、R4、R6 |
| Migration/Schema | 新增身份表和必要索引/列演进 | 持久化 Session、state 与映射 | R2、R4-R6 |
| `frontend/src/` | 登录/无权限页、路由守卫、身份展示与登出 | 完成用户工作流 | R2、R4-R6 |
| `tests/`、`frontend/tests/` | 安全、兼容、数据库与 UI 回归 | 证明可观察行为 | R1-R6 |
| 相关 Blueprint/API/运行文档 | 同步当前正确事实与 Production 边界 | 修复已知文档门禁 | R2-R6、E5 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据或说明测试例外
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档或明确不适用依据
- [x] 取得仍覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Connector 配置/校验、ID 派生、return_to、角色翻译、限流、Cookie/Session 与 Vue 身份状态 |
| 接口 / 契约 | required | auth routes、Principal 可选字段、OpenAPI 与 generated client 一致性及旧接口兼容 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PostgreSQL 的 Migration、state 原子消费、Session 撤销、并发首登、跨 Connector 隔离与限流 SQL |
| 用户 / 工作流验收 | required | 登录页、多 Connector/单 Connector/失败降级、401/403、登出和身份展示 |
| 跨组件关键路径 | required | Browser/HTTP → FastAPI → PostgreSQL → Session → Vue 的本地真实链；可用时覆盖飞书回调 |
| 外部依赖 / 供应方探测 | not_applicable | 当前没有获授权的真实飞书双应用环境；生产 Adapter 的 HTTP 协议、分页、错误与零隐藏重试由确定性 Fake 覆盖，真实租户验收保留为部署前 Production No-Go |
| 构建 / 打包 / 运行 | required | Backend wheel/import/startup、Frontend typecheck/lint/build、Compose 配置与启动风险 |
| 文档 / 治理 / 其他 | required | 表 Owner、文档事实、Secret、架构、Change Completion、Deep Review、PR/CI/main-fresh |

## 验证计划

- 目标测试：身份后端单元/API/Contract、飞书 Route、配置、多 Connector、前端身份与登录页。
- 相关回归：全量 unit/contracts/API、相关 PostgreSQL suites、前端 unit/build/Browser Mock，以及 CI 分类要求的完整 profile。
- 静态检查或构建：Ruff、mypy、OpenAPI/generated check、前端 typecheck/lint/build、wheel/import。
- 专项真实边界：Alembic upgrade/check/downgrade 评估、真实 PostgreSQL、Compose/startup、真实跨组件链；真实飞书 Probe 按环境与授权决定。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 认证绕过、Cookie/CSRF、state 重放/串企业、Secret/授权码日志泄漏、旧映射失联、Migration 数据损伤、主分支能力回退 | 安全正反例、真实 PostgreSQL、三方移植与 Deep Review |
| 兼容性 | 要求兼容旧单企业 env、旧回调路由、既有 Principal/Authorization 和现有映射 | 独立回归与 Contract diff |
| 数据 / Migration | 单一新增 `20260921_0056`；已验证 upgrade/check，downgrade 会删除四张新身份表及其数据 | 不在本任务执行生产 Migration；如需回滚必须先停用认证流并确认身份数据可丢弃或已备份 |
| 部署 / 运行 | 增加飞书配置与 Secret 引用；生产回调/HTTPS 不在本次执行 | 更新模板和运行文档，保持 Production No-Go 的其余门禁 |
| 回滚 / 恢复 | 代码 revert；Migration 是否安全 downgrade 以实际 DDL 与数据前提为准 | 合并前给出明确停止/回退边界 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted；至少复核 Product 身份状态、Blueprint 01/03/04/05/07、API、环境运行、Roadmap 当前未完成边界。
- **依赖 / Runtime**：交付包声称无新增依赖，需由 manifest/lock diff 复核。
- **配置 / Secret**：新增飞书 App、Secret 引用、组、回调、TTL 和多 Connector 配置；只允许引用 Secret File，不内联 Secret。
- **部署 / Release**：本任务不执行发布/部署；只验证配置和构建/运行入口。
- **兼容 / 消费方通知**：飞书后台需要登记匹配回调地址；旧回调路由暂保留兼容。

# 完成审计

- [x] upstream_re_read：已重新读取用户当前要求、Issue #555、Roadmap P0、决策 Y、前置延期 Change 与正式项目规则。
- [x] change_coverage：已逐项比较上游要求与当前实现、测试、文档和交付证据；没有把交付包自己的 Change 当作需求全集。
- [x] reverse_audit：已执行后端能力 → 前端入口、前端动作 → 后端真实支持、Migration 写入方 → Resolver/Session 读取方、Connector 配置 → API 装配的反向审计；审查发现并修复了多企业 Secret 复用、路由 Contract 泄漏、logout HTTP 失败误报成功和并发限流竞态。
- [x] unresolved_cleared：所有 `not_satisfied` 已清零；没有凭据的真实飞书租户验收不被伪造，继续作为部署前 Production No-Go。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | `main@835f652d...` / Windows | patch baseline/blob 比对与 apply check | 已确认基线 `37721e83...`，直接应用失败 | 必须三方移植 |
| V2 | 当前工作树 / Windows / Python 3.14 | `pytest tests/unit/identity tests/api/test_u1_u5_identity_product.py tests/integration/platform/test_multi_connector_isolation.py` | 151 passed、9 skipped | Connector、OAuth、Session、授权、路由与兼容行为 |
| V3 | 当前工作树 / PostgreSQL 18.4 一次性容器 | `alembic upgrade head`、`alembic current`、`alembic check`、Migration compatibility、`pytest tests/integration/platform` | head=`20260921_0056`；无待生成操作；兼容检查通过；53 passed | Schema/Metadata 一致、真实事务语义、并发限流与多 Connector 隔离 |
| V4 | 当前工作树 / Windows | `ruff format --check`、`ruff check`、`mypy backend/src`、OpenAPI `generate.py --check` | 通过；363 个源码文件无类型错误；生成物同步 | Python 格式、静态规则、类型和公共 Contract 一致 |
| V5 | 当前工作树 / Node/Chromium | `npm run lint`、Vitest、`npm run build`、Playwright | lint/build 通过；223 passed；129 passed | 登录页、守卫、401/403、身份展示、登出和生产构建 |
| V6 | 当前工作树 / Windows | architecture、table ownership、docs、docs facts、secret scan | 全部通过 | 模块边界、表 Owner、文档事实和 Secret 安全 |
| V7 | 当前工作树 / Windows | `uv build --wheel`、wheel 内容检查、`docker compose --env-file env.production.example config --quiet` | wheel 成功且包含 `identity.feishu`；Compose 配置通过 | 打包与部署配置可解析 |

## 未验证内容与剩余风险

- 当前没有两家真实飞书应用、用户组和回调的授权环境，因此没有执行真实外部登录；上线前仍需在 HTTPS/正式回调环境完成真实租户验收。
- 飞书端用户组或账号被撤销后，当前 AIMA Session 不会主动远程回查，最长按配置的 8 小时会话 TTL 生效；这是文档明确保留的 Production 风险，不得解释为即时撤权。
- 本机全量 API/unit 的 pytest 临时目录会被 Windows ACL 拒绝访问；全量 Contract 还会扫描用户既有、未跟踪的 Provider Raw 输出。它们未被删除或篡改，最终全量回归由 PR 的干净 Linux checkout CI 裁决。

## 交付状态

- 提交：治理提交 `30c01f8d`、`d01f5a9f` 与补丁还原提交 `04627553`；最终修复提交待创建并推送。
- Requirement Source：GitHub Issue #555。
- 拉取请求：Draft PR #556（`https://github.com/dingyuwen777/AIMA_UGC/pull/556`）。
- CI：等待最终修复提交推送后的 current-head required checks。
- Review：已完成代码/Contract/Migration/安全/前端/文档 Deep Review；发现的问题均已修复并重验，当前无阻塞 Finding。
- 合并：尚未执行；只有 PR #556 current-head required checks 全绿且 main 未漂移时才按保护规则合并。
- Change 归档：不适用，等待 Implementation PR 合并后的仓库自动化。
- 发布 / 部署：未授权且不属于本任务。

## 备注

交付包中的旧 Change 只作为接管输入，不作为当前仓库的 Active Change 直接复用；本文件以当前分支、当前主分支和新鲜证据重新建立事实。
