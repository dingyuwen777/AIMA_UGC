---
schema: coding-change/v1
id: CHG-20260921-175407-feishu-login-integration
title: 将飞书企业登录交付补丁移植到当前主分支
level: L3
status: proposed
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
  - 新增 identity principals/external identities/sessions/login states 表
  - 身份 ID 列统一为 text
  - 登录 state 增加 client_ip 与限流索引
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
- 当前代码只有 Development Identity Resolver；企业真实登录仍是正式 Roadmap 中未完成的 P0。
- 补丁可追溯到 `main@37721e83721ca203e8da9aa886dd8b3402254984` 的文件基线；当前 `main` 已继续演进，直接 `git apply --check` 和 `git apply --3way --check` 均显示多个真实冲突。
- 交付包自己的 Change 记录承认 `check_table_ownership` 与 `check_docs_facts` 未通过，不能把交付包中的旧测试数字当作当前分支的新鲜证据。

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

- 当前尚未取得正式 GitHub Issue/PR；在早期治理提交推送后按项目规则建立远端追溯链。
- 真实飞书双企业外部联调需要有效 App、组、回调与 Secret；交付包的历史叙述不能替代当前 revision 的新鲜证据。若当前环境没有凭据，将单独判断是否阻塞合并。

# 目标、成功标准与非目标

## 目标

1. 将交付补丁完整、可审查地移植到当前主分支能力基线上。
2. 实现飞书登录、回调、Session、登出、身份映射、审计和多 Connector 配置。
3. 保持既有 Principal/Authorization、公用 API 合法行为与主分支后续能力不回退。
4. 通过当前仓库要求的测试、质量、文档、Review、PR/CI 与合并门禁。

## 成功标准

- [ ] 补丁功能已移植且无未解决冲突，不覆盖当前主分支后续合法变化。
- [ ] 登录、回调、一次性 state、Session、登出、角色映射与审计的安全正反例通过。
- [ ] 多企业 Connector 隔离、跨企业 state 拒绝、旧单企业配置与旧路由兼容通过。
- [ ] Migration、真实 PostgreSQL、Contract/generated client、前端交互与构建验证通过。
- [ ] 表 Owner、数据库文档、Change Completion 和 Secret 扫描等项目门禁通过。
- [ ] Deep Review 无阻塞 Finding，当前 PR head 的 required CI 通过后才允许合并。

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
| R1 | 在本地任务分支集成补丁，确认无问题后才合并主分支 | user:2026-09-21-current-request / AC1 | not_satisfied | 尚未完成移植、验证、Review、PR 与合并 |
| R2 | 提供真实企业身份登录、Session/Claims、Principal 映射与审计 | docs/roadmap/02_生产上线实施路线.md / AC1 | not_satisfied | 待移植并验证 |
| R3 | 飞书身份保持在 Adapter 边界，业务只消费 Provider-neutral Principal | docs/blueprint/07_技术决策与实施门禁.md / AC1 | not_satisfied | 待移植后执行调用链与架构审查 |
| R4 | 多个飞书 Connector 可同时配置且相互隔离，旧单企业配置保持兼容 | external:飞书登录-交付包-20260921-多企业计划 / AC1 | not_satisfied | 待移植并运行配置、路由与 PostgreSQL 回归 |
| R5 | 跨企业 state、重放、开放重定向、日志泄密和登录滥用必须失败关闭 | external:飞书登录-交付包-20260921-安全验收 / AC1 | not_satisfied | 待运行安全正反例与 Review |
| R6 | 当前 revision 的 Contract、Migration、前后端、质量门禁、PR CI 与 main-fresh 证据完整 | user:2026-09-21-current-request / AC2 | not_satisfied | 待执行 |

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
- [ ] 行为变化建立失败证据或说明测试例外
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档或明确不适用依据
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Connector 配置/校验、ID 派生、return_to、角色翻译、限流、Cookie/Session 与 Vue 身份状态 |
| 接口 / 契约 | required | auth routes、Principal 可选字段、OpenAPI 与 generated client 一致性及旧接口兼容 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PostgreSQL 的 Migration、state 原子消费、Session 撤销、并发首登、跨 Connector 隔离与限流 SQL |
| 用户 / 工作流验收 | required | 登录页、多 Connector/单 Connector/失败降级、401/403、登出和身份展示 |
| 跨组件关键路径 | required | Browser/HTTP → FastAPI → PostgreSQL → Session → Vue 的本地真实链；可用时覆盖飞书回调 |
| 外部依赖 / 供应方探测 | required | 真实飞书 App/组/回调当前事实；仅在已授权凭据与环境可用时有界执行，不进普通 CI |
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
| 数据 / Migration | 三个新增 Migration；合并前验证 upgrade/check，并审查 downgrade 前提 | 不在本任务执行生产 Migration |
| 部署 / 运行 | 增加飞书配置与 Secret 引用；生产回调/HTTPS 不在本次执行 | 更新模板和运行文档，保持 Production No-Go 的其余门禁 |
| 回滚 / 恢复 | 代码 revert；Migration 是否安全 downgrade 以实际 DDL 与数据前提为准 | 合并前给出明确停止/回退边界 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted；至少复核 Product 身份状态、Blueprint 01/03/04/05/07、API、环境运行、Roadmap 当前未完成边界。
- **依赖 / Runtime**：交付包声称无新增依赖，需由 manifest/lock diff 复核。
- **配置 / Secret**：新增飞书 App、Secret 引用、组、回调、TTL 和多 Connector 配置；只允许引用 Secret File，不内联 Secret。
- **部署 / Release**：本任务不执行发布/部署；只验证配置和构建/运行入口。
- **兼容 / 消费方通知**：飞书后台需要登记匹配回调地址；旧回调路由暂保留兼容。

# 完成审计

- [ ] upstream_re_read：完成前重新读取用户当前要求、Roadmap P0、决策 Y、前置延期 Change 与正式 Requirement Source。
- [ ] change_coverage：逐项比较上游要求与当前实现、测试、文档和交付证据。
- [ ] reverse_audit：执行后端能力 → 前端入口、前端动作 → 后端支持、Migration 写入方 → 读取方、配置 → 运行装配的反向审计。
- [ ] unresolved_cleared：清零所有 `not_satisfied`；延期/不适用仅保留正式批准且不阻塞本次目标的项目。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | `main@835f652d...` / Windows | patch baseline/blob 比对与 apply check | 已确认基线 `37721e83...`，直接应用失败 | 必须三方移植 |

## 未验证内容与剩余风险

- 尚未应用生产实现，全部功能与交付证据待当前分支重建。
- 尚未确认当前环境是否具备两家真实飞书应用的联调凭据；不得复用交付包叙述冒充本轮证据。

## 交付状态

- 提交：尚未创建。
- 拉取请求：尚未创建。
- CI：尚未运行。
- 合并：尚未执行。
- Change 归档：不适用，等待 Implementation PR 合并后的仓库自动化。
- 发布 / 部署：未授权且不属于本任务。

## 备注

交付包中的旧 Change 只作为接管输入，不作为当前仓库的 Active Change 直接复用；本文件以当前分支、当前主分支和新鲜证据重新建立事实。
