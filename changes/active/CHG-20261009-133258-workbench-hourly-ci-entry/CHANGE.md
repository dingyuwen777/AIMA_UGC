---
schema: coding-change/v1
id: CHG-20261009-133258-workbench-hourly-ci-entry
title: 工作台每小时更新与前端检查入口修复
level: L3
status: ready_for_review
owner: dingyuwen777
branch: fix/workbench-hourly-refresh
created: 2026-10-09
updated: 2026-10-09
completion_gate: required
depends_on: []
affected_areas:
  - workbench
  - ci
  - docs
affected_paths:
  - frontend/src/features/workbench/pages/WorkbenchPage.vue
  - frontend/e2e/workbench.spec.ts
  - .github/workflows/ci.yml
  - scripts/dev/validate_changed.py
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_validate_changed.py
  - AGENTS.md
  - docs/product/02_当前产品能力与用户流程.md
contracts: []
data_changes: []
---

# 变更摘要

工作台普通聚合改为每一小时检查更新，修复入口文档链接；修复本 PR CI 暴露的前端定向测试工作目录错误。独立复核发现固定轮询与请求完成时间错位，本次同时修复，避免实际变成两小时更新。

# 背景、现状与问题

## 背景

用户要求工作台每小时更新、修复 ENTRY.md 入口问题，并合并远程主分支后清理本地开发分支。2026-10-09 用户明确同意纳入 CI 与本地检查脚本的前端测试入口及必要回归。

## 当前现状

PR #709 已包含一小时常量、页面文案、产品说明及 AGENTS.md 文档链接修复。当前目标 main 为 cb09cd148ca6dd22350164a869269962397a67e0。

## 问题、根因或约束

普通定时器从挂载开始，而过期判断从请求完成开始，首轮和后续请求耗时均可能导致整轮跳过。CI 和本地定向检查使用 npm exec，prefix 不改变进程工作目录，导致 Vitest 从仓库根启动，未加载前端 Vue 配置。

## 不修改的后果

正常请求存在耗时时，页面可能两小时才更新；CI 前端定向检查解析 Vue 失败并阻塞合并。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | lastAutoRefreshAt 在初始化和聚合请求完成后写入 | frontend/src/features/workbench/store.ts | 按实际完成时间安排下次检查 |
| E2 | 固定一小时定时器与完成时间错位可跳过整轮 | 独立 Review WBR-001 | 覆盖首轮及后续轮次的延迟 |
| E3 | CI Vue 解析失败可本地重现，npm script 正常 | CI run 37888447222 / npm --prefix frontend exec -- vitest run tests/workbench.spec.ts | CI 和本地均复用 npm script |
| E4 | CI 入口回归先失败两项 | uv run pytest tests/unit/test_validate_changed.py::test_validate_changed_reuses_classifier_and_builds_targeted_commands tests/unit/test_ci_workflow_structure.py::test_core_consumes_selected_backend_and_frontend_targets_from_ci_plan -q | 验证命令生成和工作流结构 |

## 推断与待确认

最新提交的远端必需检查和合并状态由正式平台结果确认，不能由本地测试推断。

# 目标、成功标准与非目标

## 目标

页面可见且没有在途请求时，按上一轮完成后一小时更新聚合；CI 与本地定向前端测试使用相同的正确配置。

## 成功标准

- [x] 页面显示每 1 小时检查更新，连续两轮更新均不因请求耗时跳过。
- [x] 隐藏标签页、慢请求、声音流游标和独立后台聚合跟进保持兼容。
- [x] ENTRY.md 链接可由文档检查解析。
- [x] CI 与本地定向检查回归通过；独立复核及当前版本必需检查继续作为合并前置门禁。

## 范围

工作台普通刷新计时、对应浏览器回归、产品描述和文档入口，以及获批的 CI/本地检查前端测试命令。

## 非目标

后端采集调度、公共 API、数据库、依赖升级、部署和 Release 不在本次任务内。

## 必须保持不变

复用 refreshAggregates，只补读 mind/trend；普通刷新不重置声音流；后台 preparing/refreshing 跟进独立；全部 CI 门禁和范围分类规则继续生效。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Parent 单 Writer，独立 Reviewer 只读 | 用户合并要求及项目独立复核规则 | 工作台、CI 和定向检查 |
| 接口与契约 | 不改公开 Contract | 仅使用现有 Service 与 npm script | 无生成物变化 |
| 数据与迁移 | 不适用 | 无持久化变化 | 无 Migration |
| 错误与失败语义 | 沿用 Store 错误处理 | E1 | 不改变模块错误 UI |
| 兼容性 | 保留隐藏、忙碌及游标保护 | E1、E2 | 单个在途普通刷新 |
| 部署与回滚 | 普通代码回滚即可 | 无数据变化 | 不执行部署 |

# 修改方案与决策依据

## 最小充分方案

补浏览器时间边界回归 → 工作台定时器按完成时间重新安排 → 验证连续两轮及原有可见性行为。修复 CI/本地脚本 → 复用现有 test/test:e2e npm script → 验证 Python 命令回归、前端单元、浏览器和构建。最终读取最新 main、取得独立 Review 及当前提交 CI，再受保护合并与本地分支清理。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1、E2 | 单次定时器从完成时间安排，避免固定轮询错位 |
| D2 | E3、E4 | 现有 npm script 已正确加载前端配置，无需复制配置或改测试工具 |

## 备选方案与取舍

只等待初始化后再启动 setInterval 仍会在后续请求完成后错位，不能满足连续轮次。仅指定 Vitest root 会让 Playwright 与本地入口继续分叉；复用两条现有 script 更小且一致。

# 需求追溯

三条用户指令各自只有一个明确验收单元，以下 AC1 分别定位对应原话：“每 1 小时检查更新”“修复 ENTRY.md 文档发现的问题”“纳入修复并继续合并”。保留产品异步边界及工程门禁属于已有约束，按上文“必须保持不变”和完成审计复核，不为正式文档虚构 AC 锚点。

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 每一小时检查并更新工作台数据 | user:hourly-refresh / AC1 | satisfied | WorkbenchPage 单次定时器；浏览器连续两轮及文案回归通过 |
| R2 | 修复 ENTRY.md 文档发现的问题 | user:entry-link-repair / AC1 | satisfied | AGENTS.md 链接修复及文档检查通过 |
| R3 | 修复 CI 和本地脚本前端测试入口及必要回归 | user:ci-entry-repair / AC1 | satisfied | 两项正确 Red；完整两个 Python 文件 41 passed；根目录 npm script 单元和浏览器均可运行 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| frontend/src/features/workbench/pages/WorkbenchPage.vue | 一小时文案与完成时间计时 | 用户行为 | R1、E1 |
| frontend/e2e/workbench.spec.ts | 小时边界及既有场景 | E2 | R1、E2 |
| .github/workflows/ci.yml、scripts/dev/validate_changed.py | 定向测试调用 npm script | E3 | R3 |
| tests/unit/test_ci_workflow_structure.py、tests/unit/test_validate_changed.py | 两个入口回归 | E4 | R3 |
| AGENTS.md、docs/product/02_当前产品能力与用户流程.md | 文档入口及频率同步 | 用户要求 | R1、R2 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 工作台 Store 与两个命令入口回归 |
| 接口 / 契约 | not_applicable | 未改 API、Pydantic 或生成 Client |
| 集成 / 持久化 / 运行依赖 | required | 正式 CI 按唯一 classifier 执行 CI 修改所需层 |
| 用户 / 工作流验收 | required | 浏览器连续两小时周期、可见性、后台跟进及声音流兼容 |
| 跨组件关键路径 | required | 当前提交正式 Full-stack 与 Compose Golden Path |
| 外部依赖 / 供应方探测 | not_applicable | 不改 Provider；不发付费请求 |
| 构建 / 打包 / 运行 | required | 前端 lint、TypeScript/Vue/Vite build |
| 文档 / 治理 / 其他 | required | 文档、Change、独立 Review、PR 与必需检查 |

## 验证计划

本地运行两个入口 Python 测试文件、前端 workbench 单元、浏览器受影响场景、ESLint/build、文档与项目 Change 检查。完整 CI 边界由 scripts/dev/validate_changed.py --base origin/main 生成；CI 配置修改接受完整正式 CI，不降低测试范围。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 时间错位、卸载后重新安排或重复在途请求 | 浏览器边界回归与 disposed/busy 保护 |
| 兼容性 | 保持现有模块和测试选择 | 不改 classifier、事件或必需检查 |
| 数据 / Migration | 不适用 | 无数据模型变化 |
| 部署 / 运行 | 本次只合并代码 | 用户未要求部署 |
| 回滚 / 恢复 | revert 本任务提交 | 无数据回填或不可逆操作 |

# 文档、依赖、部署与发布影响

长期文档同步工作台频率和入口链接。依赖 / Runtime、配置 / Secret 不适用，未增加或升级。部署 / Release、消费方通知不适用，本次没有公共接口及部署动作。

# 完成审计

- [x] upstream_re_read：2026-10-09 重新读用户要求、CI 修复授权、产品工作台能力及 AGENTS.md。
- [x] change_coverage：独立从上游重建完成定义，R1–R3 均已映射实现、文档与本地证据；正式产品与工程约束单独核实。
- [x] reverse_audit：普通刷新复用 refreshAggregates，只请求 mind/trend；声音流未重置；CI/本地定向入口均调用 package.json 现有 script。无 API 或数据库能力新增。
- [x] unresolved_cleared：实现与本地回归问题均已闭合；未取得独立复核及新提交 CI 前禁止合并，平台结果记录在同一 PR。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | b945c8d7 / Windows | 前端 workbench 单元与五项浏览器场景、build、文档检查 | 通过 | 原始修改基线，不能替代当前修复验证 |
| V2 | b945c8d7 + 回归修改 | 两项 CI 入口 pytest | 2 failed | 修复前正确失败 |
| V3 | b945c8d7 + 小时边界回归 | npm --prefix frontend run test:e2e -- e2e/workbench.spec.ts --grep 请求耗时后连续两轮 --workers=1 | 1 failed，预期第二次请求实际只有第一次 | 请求耗时引发跳轮的正确 Red |
| V4 | 2026-10-09 修复工作树 / Windows | uv run pytest tests/unit/test_validate_changed.py tests/unit/test_ci_workflow_structure.py -q | 41 passed | 两个测试入口及相邻工作流回归 |
| V5 | 同一修复工作树 | npm --prefix frontend run test -- --run tests/workbench.spec.ts | 27 passed | 根目录调用正确加载前端 Vue 配置及 Store 行为 |
| V6 | 同一修复工作树 | 工作台六项受影响 Browser Mock；增强小时边界两项复跑 | 6 passed；增强后 2 passed | 连续两轮、跨小时慢请求、隐藏过期恢复、后台独立跟进、原声游标保护 |
| V7 | 同一修复工作树 | 前端定向 ESLint、npm --prefix frontend run build、目标 Python Ruff、check_docs.py | 全部通过；既有 bundle 大小提示 | 静态、类型、构建、文档质量 |
| V8 | 同一修复工作树 | scripts/dev/validate_changed.py --base origin/main --json | full；所有正式层 required | CI 修改按唯一 classifier 升级验证范围，不跳过重依赖层 |

## 未验证内容与剩余风险

本地直接证据已取得；全量后端、PostgreSQL、Full-stack、镜像及 Compose 由本次提交正式 CI 执行。独立复核和当前提交全部必需检查仍是合并门禁，当前状态不声称已经完成远端交付。

## 交付状态

PR：https://github.com/dingyuwen777/AIMA_UGC/pull/709。本地修复可供复核，独立 Review 和当前提交正式 CI 通过前不可合并。合并后由仓库原生流程归档 Change。发布 / 部署不适用，用户要求仅合并与本地分支清理。

## 备注

项目已有顶层 changes carrier，依照 AGENTS.md 使用当前 schema；不改不可变 legacy archive 或安装器。
