---
schema: coding-change/v1
id: CHG-20261008-121150-frontend-security
title: 修复前端依赖安全审计阻塞
level: L2
status: in_progress
owner: Codex
branch: tech/frontend-security-20261008
created: 2026-10-08
updated: 2026-10-08
completion_gate: required
depends_on: []
affected_areas:
  - "frontend-dependencies"
affected_paths:
  - "frontend/package.json"
  - "frontend/package-lock.json"
contracts: []
data_changes: []
---

# 变更摘要

按用户批准的独立安全升级任务，把 Vue 及同步组件升级至 3.5.42，source-map-js 至 1.2.2，postcss-selector-parser 至 7.1.6，解除现有依赖审计阻塞；其他依赖与产品代码保持现行事实。

# 背景、现状与问题

## 背景

Requirement Source 为 #704；用户已明确批准上述最小升级并要求继续合并主分支。原 #702/#703 飞书整合任务保持原范围，本任务先独立修复其遇到的 main 基线依赖问题。

## 当前现状

起始 main 为 cef862941cf1a2bb9b67e0c0e32aa4edf2f265f1。Vue/@vue 3.5.41、source-map-js 1.2.1、postcss-selector-parser 7.1.5。Node 24.19.0/npm 11.17.0，唯一前端锁文件为 frontend/package-lock.json。

## 问题、根因或约束

锁定版本命中三项安全公告；npm audit 实测 exit 1，4 个漏洞计数中包含 Vue 元依赖计数，3 high/1 moderate。不能把包审计命中等同于生产漏洞已被利用，也不能绕过现有 required 检查。

## 不修改的后果

相同锁文件继续命中已确认公告，正式 required CI Gate 失败，阻止当前受保护 main 交付。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 旧锁实际 npm audit exit 1，3 high/1 moderate | .runtime/sync-local-feishu-20261008/security-audit-before.json；CI 37722547954/job113133356401 | 按失败版本修复，不关闭审计 |
| E2 | 公告的最小修复版本及 npm 发布均已确认 | GHSA-g2v6-rqmx-r4w6、GHSA-68fv-2mgg-jv7q、GHSA-rj75-hqrm-r3gf；官方 release 和 npm view | 仅升级已批准的三个补丁版本 |
| E3 | 两个间接依赖的上游范围支持修复版本 | @vue/compiler-core/postcss 的 source-map-js ^1.2.1；eslint-plugin-vue 的 parser ^7.1.4 | 优先普通依赖解析，不增加 override 或直接依赖 |
| E4 | 项目依赖升级是独立任务，现有 CI/归档有效 | AGENTS.md；.github/workflows/ci.yml、change-archive.yml | 本地独立分支、Issue、Change、PR |

## 推断与待确认

未测试生产部署或真实 Provider；无本轮发布授权，不构成依赖修复的证据替代。

# 目标、成功标准与非目标

## 目标

在保持产品兼容的前提下消除本次已确认的依赖公告，并让团队 main 可以通过正式安全审计。

## 成功标准

以 #704 / AC1–AC5 为上游完成定义。预合并 Ready 与实际 main-fresh/archive/Closure 不混为同一阶段。

## 范围

两个 frontend 依赖文件与本独立 Change。只更新 Vue 同版本组件及两个已批准间接依赖。

## 非目标

其他依赖/Runtime/工具链升级、业务代码、API/Schema/Migration、CI/保护规则改造、Release、部署与生产数据操作。

## 必须保持不变

Node/npm 精确版本、无关包版本、下载源与 integrity 校验、公共 Contract、业务 Schema、页面行为与现有质量门禁。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | root 单写，独立 Reviewer 只读 | #704、E4 | 两个依赖文件 |
| 接口与契约 | 不适用：不修改 HTTP/CLI/模型 | 仅 Manifest/lock 变化 | 无生产 Contract 变动 |
| 数据与迁移 | 不适用：不修改业务 Schema | 无后端或 migration diff | 不连接业务库 |
| 错误与失败语义 | 保留 npm audit 和 CI 的非零失败 | E1 | 禁止强制修复或 gate bypass |
| 兼容性 | 同一 minor 的精确补丁，Vue 内部保持同步 | E2/E3 | 编译、渲染与测试需回归 |
| 部署与回滚 | 正常 npm ci；普通 PR 可回滚 lock，但旧漏洞会复现 | E1/E4 | 不执行部署 |

# 修改方案与决策依据

## 最小充分方案

1. 保存旧 lock 的实际 audit Red，确认 Issue、分支和独立 Change；首个治理 checkpoint 后建立早期 Draft PR。
2. 用 npm 的 package-lock-only 精确更新 Vue 3.5.42；在现有 semver 内精确解析两个间接补丁，不增加直接依赖或 override。检查所有 lock 节点与元数据差异，拒绝无关漂移。
3. 正式 npm ci、audit 和完整 frontend lint/typecheck/unit/build/browser；运行生成器确认 Client 无漂移，并读取统一 classifier 的 preflight。
4. 重读 #704 / 用户决定，做 Completion Audit 和独立 Review；Final Ready 同步最新 main，取得 current-head CI 后 guarded merge、main-fresh、原生归档与 Issue Closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| 精确补丁升级 | E1/E2 | 切断已确认失败机制，避免解析 latest |
| 保留原解析策略 | E3 | 上游支持修复版本，无需新 override |
| 独立安全 PR | E4 | 与飞书资产分开审查和回滚 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 三组精确升级且无无关漂移 | #704 / AC1 | not_satisfied | 依赖尚未修改 |
| R2 | 正式安装与审计 Green，保留报告 | #704 / AC2 | not_satisfied | 当前 Red 为 exit 1 |
| R3 | 前端回归及生成一致性 | #704 / AC3 | not_satisfied | 新依赖尚未验证 |
| R4 | 需求/实现完整审计及独立 Review | #704 / AC4 | not_satisfied | 新实现尚未审查 |
| R5 | required CI、受保护合并、main-fresh 和原生 archive | #704 / AC5 | explicitly_deferred | AGENTS.md 与原生 Workflow 规定后续平台阶段；当前不声明实际完成，全部执行后才关闭 Issue |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| frontend/package.json | Vue 精确补丁版本 | 公告修复 | R1/E2 |
| frontend/package-lock.json | Vue 同版本树及两个间接依赖 | 正式可复现安装 | R1/R2/E3 |
| 本 Change | 当前计划及有效证据 | 项目独立升级追溯 | R4/E4 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 全部 frontend Vitest；Vue 编译、响应式、组件行为 |
| 接口 / 契约 | required | generate:api 后生成 Client 与 Git 一致 |
| 集成 / 持久化 / 运行依赖 | required | npm ci、lock diff、audit；正式 CI 按唯一 classifier 选择集成层 |
| 用户 / 工作流验收 | required | frontend Browser Mock Acceptance；Human Local Acceptance 不适用：无新增可见行为，也无人工路径可直接验证公告消除 |
| 跨组件关键路径 | required | 正式 CI 与 Compose Golden Path，按仓库实际选择器执行 |
| 外部依赖 / 供应方探测 | not_applicable | npm 元数据核实已完成；不需真实飞书/TikHub 等业务 Provider |
| 构建 / 打包 / 运行 | required | lint/typecheck/build 与 locked 安装 |
| 文档 / 治理 / 其他 | required | canonical Issue/Change/PR 校验、Completion/Review、Ready Check；版本事实由 Manifest/lock 唯一维护 |

## 验证计划

旧锁 audit 已真实失败；Manifest/lock 任务不用新增镜像版本断言的永久测试。替代证据为 npm 解析/安装/审计及现有行为回归。执行正式 frontend scripts、生成 Client 一致性和项目 changed-scope preflight；Windows npm.cmd 原生子进程限制如实报告，必要命令从 PowerShell 执行，不改工作流。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 编译/渲染回归及无关 lock 漂移 | 完整 frontend 回归与逐包 diff |
| 兼容性 | 精确补丁，无框架/工具链切换 | #704 批准范围与 npm 元数据 |
| 数据 / Migration | 不适用，无相关源码变化 | 不生成或运行业务迁移 |
| 部署 / 运行 | 构建依赖重新 npm ci | 不执行真实部署 |
| 回滚 / 恢复 | 普通 PR 恢复两个文件会重新引入已知审计失败 | 无数据回滚，不将回滚声明为安全修复 |

# 文档、依赖、部署与发布影响

长期文档不适用：既有技术栈和流程未变，精确版本由 Manifest/lock 维护，不复制平行版本列表。依赖仅为已批准的三组补丁。无配置、Secret、生产 Contract、Migration 或部署步骤改变。Release/Deploy 未授权且不执行。

# 完成审计

- [ ] upstream_re_read：重新读取用户决定与 live #704，独立重建 AC1–AC5。
- [ ] change_coverage：核对三组精确补丁、无关漂移、回归和平台交付全部责任。
- [ ] reverse_audit：Manifest → lock → npm ci 实际树 → audit → 现有用户/构建路径；公共业务入口无变化。
- [ ] unresolved_cleared：所有预合并 not_satisfied 清零；post-merge 责任保留且不冒充完成。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | cef8629 / Node24.19.0 npm11.17.0 | npm --prefix frontend audit --json | exit1；3 high/1 moderate | 旧 lock 的真实安全审计 Red |
| V2 | 当前 Source / Issue704 | canonical prepare/validate-issue create、平台读回同检 | PASS | 独立 Requirement 已持久化且符合机器 Contract |

## 未验证内容与剩余风险

新依赖尚未修改，Green/Review/current-head CI 尚未取得。真实部署和生产 Provider 不在此依赖修复范围。

## 交付状态

本地任务分支与独立 Requirement 已建立；当前为开工治理 checkpoint。未合并、未归档、未关闭 Issue。

## 备注

原 #702/#703 保持原意图和独立验收；本任务完成后其 Final Ready 集成最新 main 并重新取得所需证据。
