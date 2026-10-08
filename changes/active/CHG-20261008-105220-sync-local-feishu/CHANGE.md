---
schema: coding-change/v1
id: CHG-20261008-105220-sync-local-feishu
title: 保留本地飞书回归并安全同步远端主分支
level: L2
status: in_progress
owner: Codex
branch: fix/sync-local-feishu-20261008
created: 2026-10-08
updated: 2026-10-08
completion_gate: required
depends_on: []
affected_areas: [identity-tests, local-compose-helper]
affected_paths: [backend/src/aima_ugc/platform/identity/__init__.py, deploy.cmd, tests/integration/platform/mock_feishu_server.py, tests/integration/platform/test_multi_connector_e2e_mock.py, tests/integration/platform/test_multi_connector_routes.py, tests/unit/identity/test_multi_connector_clients.py]
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

## 推断与待确认

用户现有业务数据库是否执行过旧迁移不明；本任务不连接该库，不宣称新版可直接迁移该旧库。真实部署需要另行只读核对其 revision 和正式升级方案，不阻塞本次源码整合。

# 目标、成功标准与非目标

## 目标

独有有效资产可由团队从 main 使用，现行身份安全边界与迁移链保持，并保留原始本地改动的恢复能力。

## 成功标准

按 #702 / AC1–AC6 验收；本 Change 不产生第二套完成定义。源码 Ready 与平台 merge/main-fresh/archive/Issue Closure 是不同阶段，后者实际发生前不声称整体完成。

## 范围

元数据所列 6 个文件、该 Change 及资产自身必要的测试隔离、生命周期、命令退出和使用说明修正。

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
| R2 | Secret、客户端、state、Principal 与权限企业隔离 | #702 / AC2 | not_satisfied | 已有目标测试；独立审查及修复后复验尚未结束 |
| R3 | 真实 Adapter 到 HTTP 假服务及测试环境资源隔离 | #702 / AC3 | not_satisfied | 隔离 PostgreSQL/HTTP 路径已有初次证据；当前审查继续核验断言与清理 |
| R4 | Windows 命令语义、失败退出与使用范围 | #702 / AC4 | not_satisfied | 静态 Compose 服务核对；受控命令验证尚未执行 |
| R5 | Contract/迁移/依赖保持与适用验证、独立审查 | #702 / AC5 | not_satisfied | Contract/Orval 无漂移；mypy459、identity153、集成57、前端306 通过；原生 preflight 与最终 Review 继续完成 |
| R6 | 受保护合并、main-fresh、自动归档和 Closure/cleanup | #702 / AC6 | explicitly_deferred | AGENTS.md 与 .github/workflows/change-archive.yml 规定合并后执行；正式 Owner #702 / AC6 保持 open，交付过程必须继续完成，未发生阶段不提前声明 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| backend/src/aima_ugc/platform/identity/__init__.py | 平台配置 Owner 包说明 | 明确依赖方向 | R5 / E2 |
| tests/unit/identity/test_multi_connector_clients.py | 客户端/Secret/cache 隔离回归 | 保留独有本地测试 | R2 |
| tests/integration/platform/test_multi_connector_routes.py | 公开路由与 PostgreSQL 企业身份回归 | 验证 state/身份/权限 | R2、R3 |
| tests/integration/platform/mock_feishu_server.py | 回环 HTTP 假服务 | 生产 Adapter 的真实 HTTP 接线 | R3 |
| tests/integration/platform/test_multi_connector_e2e_mock.py | HTTP/PostgreSQL 集成 | 同源 production client、错误凭据及部门/群组 | R2、R3 |
| deploy.cmd | Windows 本地重建/重启和失败退出 | 保留本地辅助入口 | R4 |

- [x] 调查当前实现和事实源。
- [x] 建立当前用户授权和验收矩阵。
- [x] 测试迁移明确例外：本任务保留既有测试，未新增产品行为；已实际复现旧测试对现行接口不兼容后适配，不伪造生产 Bug 的 Red。
- [ ] 完成独立审查与一次打包修复。
- [ ] 取得修复后相关验证并同步准确使用说明。
- [ ] 完成需求追溯、审计和 Ready 机器检查。

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

- [ ] upstream_re_read：重新读取 #702 当前验收和用户决定。
- [ ] change_coverage：逐项核对 #702 / AC1–AC6，不以本 Change 反推需求。
- [ ] reverse_audit：核对测试真实 production 调用链、数据库清理边界和部署 helper 参数/命令/退出。
- [ ] unresolved_cleared：审查阻塞问题、适用本地验证和 not_satisfied 清零；平台阶段仍由 #702 持续跟踪。

# 完成证据与状态

## 新鲜证据

已有证据与本轮适配文件对应，最终修复后更新受影响层：identity153 单元、4 身份集成文件57通过无跳过，隔离 PostgreSQL18.4空库迁至0082；前端完整306通过；mypy backend+4tests459通过；Contract --check、Orval 生成后无 diff。完整 backend 初跑2069通过、16跳过、4个既有 fullstack 子进程测试因 Windows GBK 解码 UTF-8 失败；测试进程改为 PYTHONUTF8=1 后对应6项复验通过，原始失败如实保留，未改生产/断言。

## 未验证内容与剩余风险

当前独立 Review、受控 cmd、最终本地 preflight 与 remote current-head CI 尚未结束，故此时为 in_progress。真实飞书、用户业务库旧 migration 状态和真实部署未验证，均未对这些事实作交付声明。

## 交付状态

需求 #702 已写前/写后校验，当前 open；分支 fix/sync-local-feishu-20261008；尚无本任务 commit/PR。平台 CI、guarded merge、main-fresh、自动归档和 Issue Closure 后续按真实 Owner 查询；不使用关闭关键字提前关闭。Release/Deploy 不适用，用户只授权源码合并。

## 备注

备份与本地逐文件处理记录留在调用者机器；不把 Secret、原始环境文件或旧 migration 当成 PR 资产。
