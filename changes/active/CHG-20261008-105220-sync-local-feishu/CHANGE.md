---
schema: coding-change/v1
id: CHG-20261008-105220-sync-local-feishu
title: 保留本地飞书回归并安全同步远端主分支
level: L2
status: ready_for_review
owner: Codex
branch: fix/sync-local-feishu-20261008
created: 2026-10-08
updated: 2026-10-08
completion_gate: required
depends_on: []
affected_areas:
  - "identity-tests"
  - "local-compose-helper"
affected_paths:
  - "backend/src/aima_ugc/platform/identity/__init__.py"
  - "deploy.cmd"
  - "tests/integration/platform/mock_feishu_server.py"
  - "tests/integration/platform/test_multi_connector_e2e_mock.py"
  - "tests/integration/platform/test_multi_connector_routes.py"
  - "tests/unit/identity/test_multi_connector_clients.py"
  - "tests/integration/platform/identity_test_database.py"
  - "tests/unit/identity/test_identity_test_database.py"
contracts: []
data_changes: []
---

# 变更摘要

用户要求保留本地改动，逐项处理与远端新版的重叠，再合入远程 main。生产实现沿用当前远端事实，补入独有的多企业回归、回环 HTTP 假服务、平台包说明和 Windows 本地部署辅助入口。通过 PR、独立审查和既有 CI 交付。

# 背景、现状与问题

## 背景

Requirement Source 为 #702；本轮用户明确授权保留并合并本地改动以及远程主分支交付。

## 当前现状

起始基线 cef862941cf1a2bb9b67e0c0e32aa4edf2f265f1，远端已包含新版飞书多企业登录和后续业务实现。59 个原始改动中，49 个意图已有等价或更完整的远端实现；6 个独有文件适配当前接口后保留；3 个旧迁移和旧 Change 仅备份。正式 Alembic 单 head 为 20261003_0082。

最终交付基线已同步到 d37d9b83aff4b83b9f6944efc4eb9c757355266b。先前正式 CI 37722547954 的依赖审计阻塞已由用户批准的独立 #704 / PR #705 修复；该 PR 已在全绿后合并、取得真实 main-fresh，并由仓库自动归档为 done，#704 已完成关闭。本任务沿用这一最新 main 的依赖与 CI 事实，不在本 PR 重复承载安全升级。正常 merge 同步无新冲突，原 8 个源码/测试 Git blob 全部与 38688f7 相同。

## 问题、根因或约束

旧飞书迁移从旧节点分叉，与远端正式身份建表重叠，不能直接重新叠加。旧测试使用缓存字段与 Secret reader 签名也已变化，必须按当前生产实现适配；备份内容不能冒充当前 Ready 或迁移事实。

## 不修改的后果

独有测试和本地辅助入口无法由团队通过 Git 使用；若重新激活旧迁移，会产生重复建表和迁移多 head。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 原始 59 文件有完整 stash 与逐字节 ZIP 备份 | 本地 stash 44af9851c3b682c218146d7bca0c909262f654db；.git/local-sync-backups/20261008-094247/local-work.zip，逐文件 SHA256 核对 | 不覆盖用户原始修改；保留可恢复原件 |
| E2 | 正式身份实现已覆盖旧业务实现 | backend/src/aima_ugc/bootstrap/feishu_auth_http.py、modules/identity/feishu/、platform/identity/connector.py；本地三方处理记录 | 仅补入独有资产，生产逻辑继续使用远端当前实现 |
| E3 | 旧链与正式迁移重叠 | migrations/versions/20260921_0056_feishu_identity.py 与本地备份旧 0053–0055；uv run alembic heads | 不重新引入旧 migration；单 head 保持 |
| E4 | 根 Compose 已定义脚本所用服务 | compose.yaml、compose.windows.yaml | 辅助入口复用既有本地环境，不能另建部署系统 |
| E5 | 仓库已有 required CI 与自动归档 | .github/workflows/ci.yml、change-archive.yml、实时 main Rulesets | 通过现有 PR/CI/归档门禁交付 |
| E6 | 独立安全修复已成为当前主分支基线，原整合源码保持 | #704/#705；merge 38782fa0884d1aaaa00af9b1f1b2a7a5be1e5a59；archive d37d9b83aff4b83b9f6944efc4eb9c757355266b；8 文件 Git blob 与 38688f7 比对 | 原 PR 的基线漏洞阻塞已闭合；按新 base/head 继续独立审查与正式 CI，不复用旧失败 head 的合并结论 |

## 推断与待确认

用户现有业务数据库是否执行过旧迁移不明；本任务不连接该库，不宣称新版可直接迁移该旧库。真实部署需要另行只读核对其 revision 和正式升级方案，不阻塞本次源码整合。

# 目标、成功标准与非目标

## 目标

独有有效资产可由团队从 main 使用，现行身份安全边界与迁移链保持，并保留原始本地改动的恢复能力。

## 成功标准

按 #702 / AC1–AC6 验收；本 Change 不产生第二套完成定义。源码 Ready 与平台 merge/main-fresh/archive/Issue Closure 是不同阶段，后者实际发生前不声称整体完成。

## 范围

6 个原始独有资产、共享隔离数据库 helper、其 9 项安全回归及本 Change；新增 helper 仅服务上述资产自身的连接前保护和异常清理。

## 非目标

新增登录业务、改写身份实现、引入旧迁移、依赖升级、CI/Ruleset 修改、真实部署、Release 或生产数据库操作。

## 必须保持不变

现行公开 API、OpenAPI/生成 Client、业务 Schema、Alembic 线性链、依赖锁、身份/权限策略和平台保护规则。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 单一写入者维护 6 资产；独立 Reviewer 只读 | #702 范围；AGENTS.md | 没有跨模块业务实现 |
| 接口与契约 | 使用现行 Secret reader、客户端缓存和响应结构 | E2 | 不修改正式 Contract |
| 数据与迁移 | 保持正式单 head，测试仅隔离 PostgreSQL | E3；#702 / AC3 | 不连接用户业务库 |
| 错误与失败语义 | 假服务拒绝错误凭据；部署步骤失败返回非零 | #702 / AC3、AC4 | 辅助资产本身可检验 |
| 兼容性 | 生产、生成物和锁文件保持基线 | #702 / AC5 | 没有消费方迁移 |
| 部署与回滚 | 只交付本地脚本，不运行实际部署；撤销新增资产可正常 PR 回滚 | #702 非目标 | 无生产副作用 |

# 修改方案与决策依据

## 最小充分方案

1. 保存完整原始内容，按三方比较与当前调用链确认远端覆盖意图；恢复独有文件并按现行接口适配。
2. 审查企业隔离断言、HTTP 假服务、数据库/客户端生命周期和 Windows 命令行为；在同一范围修正阻塞问题。
3. 用目标测试、真实隔离 PostgreSQL、回环 HTTP、受控 Windows 命令及仓库原生 preflight 取得新鲜证据。
4. 建立需求/Change/分支/PR 关联，等待 required CI，核验当前 head/base 后受保护合并；按仓库原生自动归档和 main-fresh 结果完成 #702 回写/关闭与任务分支清理。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| 保留远端当前生产实现 | E2、E3 | 有效旧意图已实现，重新叠加旧链会破坏事实 |
| 保留并适配独有资产 | E1、#702 | 满足用户保留本地工作要求，并继续保护企业边界 |
| 通过既有 PR 与自动归档 | E5 | 保持现有平台门禁与治理 Owner |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 原始备份、处理记录和唯一迁移 head | #702 / AC1 | satisfied | E1–E3；59 文件 SHA256 核对；旧 0053–0055 仅备份；正式 head 20261003_0082 |
| R2 | Secret、客户端、state、Principal 与权限企业隔离 | #702 / AC2 | satisfied | V2/V3；现有真实Secret选择测试与新增客户端回归；跨企业state/Principal/role路由证据，独立复审通过 |
| R3 | 真实 Adapter 到 HTTP 假服务及测试环境资源隔离 | #702 / AC3 | satisfied | V3/V4；连接前拒绝业务配置与初始化失败dispose，57项真实隔离PostgreSQL/HTTP路径通过；IR-01 closed |
| R4 | Windows 命令语义、失败退出与使用范围 | #702 / AC4 | satisfied | V8：12场景全部通过；复用正式容量/全服务启动、同项目frontend --wait与失败非零；IR-02/03 closed |
| R5 | Contract/迁移/依赖保持与适用验证、独立审查 | #702 / AC5 | satisfied | V1–V9；Contract/Orval/迁移单head与依赖不变；mypy461、后端2082、集成57、前端306/浏览器205通过；独立复审IR-01–04 closed、无源码阻塞 |
| R6 | 受保护合并、main-fresh、自动归档和 Closure/cleanup | #702 / AC6 | explicitly_deferred | AGENTS.md 与 .github/workflows/change-archive.yml 规定合并后执行；正式 Owner #702 / AC6 保持 open，交付过程必须继续完成，未发生阶段不提前声明 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| backend/src/aima_ugc/platform/identity/__init__.py | 平台配置 Owner 包说明 | 明确依赖方向 | R5 / E2 |
| tests/unit/identity/test_multi_connector_clients.py | 客户端/Secret/cache 隔离回归 | 保留独有本地测试 | R2 |
| tests/integration/platform/test_multi_connector_routes.py | 公开路由与 PostgreSQL 企业身份回归 | 验证 state/身份/权限 | R2、R3 |
| tests/integration/platform/mock_feishu_server.py | 回环 HTTP 假服务 | 生产 Adapter 的真实 HTTP 接线 | R3 |
| tests/integration/platform/test_multi_connector_e2e_mock.py | HTTP/PostgreSQL 集成 | 同源 production client、错误凭据及部门/群组 | R2、R3 |
| deploy.cmd | 复用正式资源启动与 Compose 健康等待 | 保留本地意图并修正资源覆盖与误报 | R4 |
| tests/integration/platform/identity_test_database.py | 连接前校验和共享隔离清理 | 阻止本地应用凭据触发清库 | R3 |
| tests/unit/identity/test_identity_test_database.py | 7 个拒绝场景与 2 个异常释放场景 | 保护上述 fail-closed 边界 | R3 |

- [x] 调查当前实现和事实源。
- [x] 建立当前用户授权和验收矩阵。
- [x] 测试迁移明确例外：本任务保留既有测试，未新增产品行为；已实际复现旧测试对现行接口不兼容后适配，不伪造生产 Bug 的 Red。
- [x] 完成独立审查与一次打包修复，IR-01–04 原因及相邻路径已闭合。
- [x] 修复后取得 V1–V9，脚本/假服务自身说明与实际范围一致。
- [x] 从上游逐项复核需求追溯与审计；Ready 机器检查随本次治理提交执行。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 企业 Secret/client/cache；identity 单元，前端回归，受控 cmd 失败退出 |
| 接口 / 契约 | required | 现行 Pydantic/OpenAPI/生成 Client 无漂移 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL18.4 的 state/Principal/role 与测试清理；回环 HTTP |
| 用户 / 工作流验收 | required | Windows helper 受控实际 cmd 调用的命令顺序和退出；没有新增产品 UI 行为，产品人工验收不适用 |
| 跨组件关键路径 | required | 生产 Router/Service/Adapter + 假 HTTP + 真实 PostgreSQL；完整产品 Golden Path 由既有 required CI 证明 |
| 外部依赖 / 供应方探测 | not_applicable | 未改真实飞书协议实现或 Provider 事实；使用回环假服务，不宣称真实飞书可用 |
| 构建 / 打包 / 运行 | required | 原生 preflight 前端构建与浏览器回归；正式 CI package/stack/Compose |
| 文档 / 治理 / 其他 | required | 脚本使用说明、Secret/Change/Requirement 校验及独立 Review |

## 验证计划

按 scripts/dev/validate_changed.py 原生 full profile 执行；真实 PostgreSQL 与完整 Golden Path 等重依赖正式 CI 按原有门禁执行。本地 targeted PostgreSQL 与 HTTP 已在隔离容器验证；受控 cmd 不访问真实 Docker。Ready 使用 scripts/quality/check_change_completion.py --root . --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 测试误报隔离有效、辅助脚本误报成功 | 独立审查、负向测试及受控实际命令 |
| 兼容性 | 现行业务行为保持 | 未修改生产逻辑与 Contract |
| 数据 / Migration | 正式链保持，业务旧库状态未知 | 不恢复旧 migration，不执行生产数据库操作 |
| 部署 / 运行 | 新增人工本地 helper | 根 Compose/env.local 边界；本任务不真实部署 |
| 回滚 / 恢复 | 可用正常 PR 撤销新增资产 | stash/ZIP 保留原始用户内容 |

# 文档、依赖、部署与发布影响

长期产品与架构文档不变：现行远端业务事实未改变。Windows 脚本自身维护最小使用、范围及失败说明，不另建部署事实源；日常启停仍由 scripts/deploy/start_compose.py 和 stop_compose.py 承担。依赖、Runtime、正式配置和 Secret 处理不变；发布、真实部署和生产 Migration 不属于当前授权。

# 完成审计

- [x] upstream_re_read：重新读取 #702 当前 AC1–AC6 和用户保留/合并/主分支交付决定，未从 Change 反推需求。
- [x] change_coverage：#702 / AC1–AC6 均映射；代码范围R1–R5证据充分，R6按正式平台阶段继续执行。
- [x] reverse_audit：生产Secret构造与HTTP预填cache证据分开；连接前拒绝非测试库、初始化异常释放；cmd复用真实容量Owner和同项目健康等待，参数/命令/退出12场景通过。
- [x] unresolved_cleared：R1–R5 satisfied、源码阻塞IR-01–04 closed、无not_satisfied；R6正式Owner #702仍open；IR-05非阻塞仅限制fake协议证据，未静默当成真实飞书或全部协议验证。

# 完成证据与状态

## 新鲜证据

受验代码基线为首个本地提交 8ff43a2423d5e55fe3a65f4ad2e8a7b78e524ed8；后续仅更新该治理记录，生产/测试源码不变。

同步最新 main 后，PR 相对新基线仍仅为原 8 个源码/测试文件及本 Change。依赖两文件与 CI 前置修复两文件逐个 Git blob 等于 main；独立安全修复不是本 Change 的实现差异。V1–V9 仅证明其明确范围，最终新 head 的全量正式 CI、新 base/head 的独立复核和合并后阶段必须另取真实平台证据。

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 仓库锁定 Python3.14/uv；PYTHONUTF8=1 | uv run python scripts/dev/validate_changed.py --base origin/main --execute | backend/Contract 阶段通过；npm 子进程阶段 WinError2 | 分类 full，正式本地命令没有降级；Windows npm.cmd 启动限制保留原错 |
| V2 | 同一工作区代码、Python3.14 | uv run pytest tests/unit tests/contracts tests/api -q | 2082 passed、16 skipped、12 subtests passed | 后端局部行为、公共 Contract/API；不冒充 PostgreSQL 或真实飞书 |
| V3 | 独立 Docker PostgreSQL18.4；127.0.0.1:53645/aima_sync_test；显式测试授权 | uv run alembic upgrade head；uv run pytest tests/integration/platform/test_feishu_login_routes.py tests/integration/platform/test_multi_connector_isolation.py tests/integration/platform/test_multi_connector_routes.py tests/integration/platform/test_multi_connector_e2e_mock.py -q | 空库至0082；57 passed、无跳过；容器与匿名卷已清理 | 真实 state/身份/权限持久化、生产 Adapter 到回环 HTTP |
| V4 | 无真实数据库 | uv run pytest tests/unit/identity/test_identity_test_database.py -q | 9 passed | 非测试配置在运行时构造前被拒绝；合法测试初始化失败释放资源 |
| V5 | 相同 7 Python 文件 | uv run ruff format --check 与 ruff check：backend/src/aima_ugc/platform/identity/__init__.py、identity_test_database.py、mock_feishu_server.py、test_multi_connector_e2e_mock.py、test_multi_connector_routes.py、test_identity_test_database.py、test_multi_connector_clients.py；mypy --explicit-package-bases backend/src 同6个测试/helper（MYPYPATH仅静态源码根） | ruff通过；mypy461 source files无问题 | 当前格式、类型与导入边界 |
| V6 | 同一手写 Contract 与生成物 | uv run python scripts/contracts/generate.py --check；uv run python scripts/contracts/check_compatibility.py；npm --prefix frontend run generate:api 后 git diff | 均通过；Orval无diff；uv run alembic heads 单0082 | 正式 API/Schema/生成 Client 和迁移链保持 |
| V7 | Windows PowerShell、仓库当前 Node/npm/lock | npm --prefix frontend run lint；npm --prefix frontend run test -- --run；npm --prefix frontend run build；npm --prefix frontend run test:e2e | lint/typecheck/build通过；306单元、205浏览器通过 | 按原生 preflight 相同命令补完 Windows npm 子进程未进入的前端层 |
| V8 | Windows实际cmd；脚本字节相同的隔离副本、真实start_compose.py；仅Docker替身 | uv run python .runtime/sync-local-feishu-20261008/cmd-harness/verify_cmd.py | 12场景通过 | 两种构建目标、资源覆盖/完整服务启动、失败退出、继承HEALTH/自定义项目身份无误报；不证明真实部署 |
| V9 | 当前仓库与 canonical Source模板/validator | scan_secrets.py；check_docs.py；check_agent_governance.py；canonical validate-change/issue/pr create | 均通过 | Secret、文档/治理接线与载体结构，不能替代语义 Review |
| V10 | 最终 main 基线 d37d9b83aff4b83b9f6944efc4eb9c757355266b；同日独立安全任务 | 原 8 个源码/测试 Git blob 与 38688f7 比对；依赖/CI 4 文件与 origin/main 比对；#705 最终 CI 37731846686、真实 main CI 37733550157 与原生 archive 37733550315 | blob 无漂移；#705/main/archive SUCCESS、同一安全 Change status=done、#704 CLOSED | 依赖阻塞原因已修复且按独立 Owner 交付；不代替本任务新 head 的 required CI 或最终 merge/main-fresh/archive/Closure |

最初完整 backend 的4项既有子进程测试因 Windows GBK 解码UTF8失败；统一测试进程UTF8后完整V2通过。未修改断言、生产Runtime或依赖来取得绿色。原生Windows npm调用限制由逐命令完成等价前端层处理，未改写仓库工具或正式CI。

## 未验证内容与剩余风险

独立源码复审已通过，reviewed head=8ff43a2423d5e55fe3a65f4ad2e8a7b78e524ed8、base=cef862941cf1a2bb9b67e0c0e32aa4edf2f265f1、decision_epoch=1；仅治理记录和换行机械规范化后核对8源码Git blob未变。remote current-head CI在Draft转Ready后完成，未提前声称merge-ready。本地适用层已取得 V1–V9；原生Windows npm子进程限制按相同前端命令补完。真实飞书、用户业务库旧 migration 状态和真实部署未验证，均未对这些事实作交付声明。

上述旧 head 的 CI 37722547954 曾因基线依赖漏洞失败，不能作为本次合并 Green。该阻塞已由 E6/V10 的独立修复闭合；本次新 main 基线下重新绑定独立 Review 与正式 CI，所有 required checks 通过后才执行用户已批准的合并。源码范围与需求 #702 / AC1–AC6 无变化，IR-05 的假协议证据边界仍保留。

## 交付状态

需求 #702 已写前/写后校验，当前 open；本地Source Ready与Human Local Acceptance applicability已核对：本任务为已有本地资产整合，无产品UI/业务行为变化；真实部署会写本地业务库，不在本轮授权且旧库revision未知，因此没有可行且有意义的产品本地人工验收路径，不把自动测试冒充人工验收。分支 fix/sync-local-feishu-20261008，首个提交8ff43a2423d5e55fe3a65f4ad2e8a7b78e524ed8；Draft PR #703已写前/写后校验。Draft按仓库规则不产生可合并required Evidence，最终Ready提交另行触发。平台 CI、guarded merge、main-fresh、自动归档和 Issue Closure 后续按真实 Owner 查询；不使用关闭关键字提前关闭。Release/Deploy 不适用，用户只授权源码合并。

## 备注

备份与本地逐文件处理记录留在调用者机器；不把 Secret、原始环境文件或旧 migration 当成 PR 资产。
