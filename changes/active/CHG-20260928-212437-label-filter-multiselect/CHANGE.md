---
schema: coding-change/v1
id: CHG-20260928-212437-label-filter-multiselect
title: 工作台与声音广场两级标签联动多选
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/653-label-filter-multiselect
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - backend
  - frontend
  - content
  - workbench
  - contract
  - documentation
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/workbench.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/src/features/workbench/
  - frontend/tests/
  - frontend/e2e/
  - tests/api/
  - tests/integration/content/
  - frontend/README.md
  - docs/product/02_当前产品能力与用户流程.md
contracts:
  - ContentFilterSnapshot
  - ContentListQuery
  - WorkbenchQuery
data_changes: []
---

# 变更摘要

- **要解决的问题**：工作台二级标签展示全部一级下的选项；声音广场标签筛选仍是单值，两个页面无法形成一致的父子联动多选。
- **拟议修改**：在不改变 Taxonomy、Schema 和依赖的前提下，补齐前端联动、多值 HTTP Contract、pair-aware PostgreSQL 查询、旧单值兼容和跨页深链。
- **预期结果**：用户可在两页选择多个一级标签，再只选择这些一级标签下的多个二级标签；查询链不会产生跨标签对误命中。

# 背景、现状与问题

## 背景

Issue #653 定义了两页标签筛选统一升级，并要求保持已有单值声音广场调用方兼容。

## 当前现状

工作台已经使用 primary_labels/secondary_labels 数组查询，但前端二级标签选项未按一级选择收窄，Repository 也把一级/二级标签拆成独立 EXISTS。声音广场 ContentFilterSnapshot、Store 和筛选 UI 仍使用单值 primary_label/secondary_label。

## 问题、根因或约束

只把下拉框改成多选不足以实现需求：声音广场 public Contract、查询/计数/导出共用的筛选快照、PostgreSQL 查询和跨页深链必须同步。一级与二级分成两个独立 EXISTS 时，还会允许不同标签对分别命中产生误筛。

## 不修改的后果

用户无法在两页一致地组合多个标签，且工作台已有数组语义仍会展示不相关二级选项；若仅扩展数组而不修正 SQL，同一内容的不同标签对可能被错误组合命中。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Workbench Store/Contract 已有一级、二级数组 | frontend/src/features/workbench/store.ts、backend/src/aima_ugc/contracts/workbench.py | 复用现有数组 Contract，不另建筛选模型 |
| E2 | Workbench 二级选项当前扁平展示全部 Taxonomy 子项 | frontend/src/features/workbench/components/WorkbenchFilters.vue | UI 必须按已选一级计算可用二级集合 |
| E3 | Voice Plaza 仍使用单值一级/二级字段 | backend/src/aima_ugc/contracts/http.py、frontend/src/features/voice-plaza/store.ts | public Contract 采用加法兼容 |
| E4 | Content 查询和 Workbench 查询均存在标签过滤 SQL | content_queries.py、workbench.py | 后端必须保证 same-pair 语义，不能只依赖前端 |
| E5 | Filter Options 已按一级标签返回分组二级标签 | ContentFilterOptionsResponse | 不需要新增 Taxonomy/目录 API |

## 推断与待确认

无。实现语义由 Issue #653 的 AC1–AC6 与当前 Contract/代码事实共同确定。

# 目标、成功标准与非目标

## 目标

统一两页标签筛选的多选、父子联动、查询语义与兼容行为。

## 成功标准

- [ ] Issue #653 / AC1–AC5 由实现和分层测试直接证明。
- [ ] Issue #653 / AC6 由 current-head required CI、Review 与合并后 main-fresh 证据证明。

## 范围

- Workbench / Voice Plaza 标签筛选 UI 与状态。
- ContentFilterSnapshot 加法兼容 Contract。
- Content/Workbench PostgreSQL 标签查询。
- OpenAPI / generated client、相关测试与当前行为文档。

## 非目标

- 不修改 Taxonomy、Analysis Scheme、数据库 Schema/Migration。
- 不新增/升级依赖。
- 不重构无关筛选器、布局或任务链。

## 必须保持不变

- 旧 primary_label/secondary_label 声音广场参数可继续使用。
- Taxonomy 继续来自后端 active Scheme。
- 其它筛选维度、权限、安全、部署和 Release 语义不变。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 复用 Workbench/Content 现有 Owner | E1–E5、Issue #653 | 不建立第二套筛选域 |
| 接口与契约 | Voice Plaza 新增 plural 字段并保留 singular | #653 / AC4 | OpenAPI/generated client 需要同步 |
| 数据与迁移 | 不改 Schema/Migration | #653 / AC6 | 仅查询语义变化 |
| 错误与失败语义 | 非法重复 plural 值由 Contract 拒绝；旧字段继续兼容 | 当前 Pydantic 模式 | 不新增错误体系 |
| 兼容性 | singular 与 plural 合并去重；前端新请求优先使用 plural | #653 / AC4–AC5 | 旧调用方不中断 |
| 部署与回滚 | 普通应用代码回滚，无数据迁移 | 无 Schema/依赖变化 | 可按 revision 回滚 |

# 修改方案与决策依据

## 最小充分方案

1. Contract/查询：为 ContentFilterSnapshot 增加 plural 标签并统一 effective values；Content 与 Workbench SQL 使用 same-pair EXISTS。
2. Workbench：按已选一级计算二级候选并在一级变化/Taxonomy 切换时清理失效二级。
3. Voice Plaza：Store/UI 改为数组，多选控件按父级收窄；兼容旧 Session 与旧单值深链。
4. 跨页与生成物：Workbench 深链发送 plural 参数，Voice Plaza 同时接受 plural/singular；更新 OpenAPI/Orval。
5. 分层验证：API Contract、PostgreSQL、Vue Unit、Browser Mock、required CI 和独立 Review。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 加法扩展 Voice Plaza Contract | E3 | 避免破坏已有单值 API/深链 |
| D2 后端 same-pair 过滤 | E4 | 前端联动不能作为服务端正确性边界 |
| D3 复用现有 Filter Options | E5 | 已有父子目录，无需新增 API |
| D4 Workbench 只补联动而不重做 Contract | E1–E2 | 当前数组 Contract 已满足多选数据表达 |

## 备选方案与取舍

- 仅前端多选：不能解决 public Contract 和服务端误筛，不采用。
- 直接把 singular 字段改名为 plural：会破坏现有调用方和旧深链，不采用。
- 新建标签 ID/关联 Schema：当前 Taxonomy/结果以字符串对为既有 Contract，需求不要求改变事实模型，会引入无必要 Migration，不采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 工作台两级标签支持多选且二级按一级选择收窄 | #653 / AC1 | not_satisfied | 实现与测试进行中 |
| R2 | 工作台一级变化自动清理非法二级选择 | #653 / AC2 | not_satisfied | 实现与测试进行中 |
| R3 | 声音广场支持相同联动多选并兼容旧 Session | #653 / AC3 | not_satisfied | 实现与测试进行中 |
| R4 | 后端 plural + singular 兼容且 same-pair 过滤 | #653 / AC4 | not_satisfied | 实现与测试进行中 |
| R5 | 列表/计数/导出/分析筛选与跨页深链语义一致 | #653 / AC5 | not_satisfied | 实现与测试进行中 |
| R6 | required 分层证据、CI 与交付闭环 | #653 / AC6 | not_satisfied | 等待实现后验证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Content HTTP Contract / Repository | plural 兼容与 same-pair 过滤 | 服务端正确性与兼容 | R4/R5 |
| Workbench Repository / Store / Filters | same-pair 与父子联动 | 现有数组语义补完整 | R1/R2 |
| Voice Plaza Store / Filters / Page | 数组状态、旧状态迁移、深链 | 用户工作流 | R3/R5 |
| OpenAPI / generated client | 从正式 Contract 重生成 | Consumer 一致性 | R4/R5 |
| API/Postgres/Vue/Browser 测试 | 补回归 | 直接证明行为 | R1–R6 |
| frontend/README + product docs | 同步当前用户行为 | 文档事实变化 | R1/R3 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [ ] 行为变化建立失败证据
- [ ] 完成最小实现
- [ ] 同步受影响长期文档
- [ ] 取得当前版本验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Store 过滤、父子联动、旧 Session 迁移 |
| 接口 / 契约 | required | Pydantic/OpenAPI/Orval、singular/plural 兼容 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL same-pair 查询语义 |
| 用户 / 工作流验收 | required | 两页多选、二级候选范围、跨页深链 |
| 跨组件关键路径 | required | Voice Plaza 筛选请求进入真实 API/PostgreSQL 的关键路径 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 TikHub/LLM 或其它外部 Provider |
| 构建 / 打包 / 运行 | required | 前端 build/typecheck + 后端静态/测试 + CI Gate |
| 文档 / 治理 / 其他 | required | Change、Requirement Source、文档、Review、CI |

## 验证计划

- 目标测试：Content/Workbench Contract + Repository + Store/Component。
- 相关回归：声音广场/工作台现有 API、前端 Unit 与 Browser。
- 静态检查或构建：Ruff/Mypy、frontend lint/typecheck/build、generated clean check。
- 专项真实边界：PostgreSQL Integration、必要的 full-stack golden path。
- 就绪检查：python scripts/quality/check_change_completion.py --root . --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 标签组合误筛、旧状态丢失 | same-pair SQL + singular/session 兼容测试 |
| 兼容性 | 加法兼容 | 保留 singular 字段，plural 与 singular 合并 |
| 数据 / Migration | 不适用 | 不改数据库结构或持久业务事实 |
| 部署 / 运行 | 普通应用升级 | 无额外配置、Secret、迁移顺序 |
| 回滚 / 恢复 | revision 回滚 | 无数据迁移需要恢复 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 Frontend README 与当前产品筛选行为。
- **依赖 / Runtime**：不新增、不升级。
- **配置 / Secret**：不变。
- **部署 / Release**：无额外步骤；本任务不执行 Release/Deploy。
- **兼容 / 消费方通知**：singular 参数保持兼容，generated client 新增 plural 字段。

# 完成审计

- [ ] upstream_re_read：Ready 前重新读取 Issue #653 与受影响 Contract/产品事实。
- [ ] change_coverage：Ready 前逐项确认 AC1–AC6 覆盖。
- [ ] reverse_audit：Ready 前执行前端→API→查询及后端能力→前端入口反查。
- [ ] unresolved_cleared：Ready 前清零 not_satisfied。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 待实现 | 待执行 | 待执行 | 当前处于开发阶段 |

## 未验证内容与剩余风险

- PostgreSQL、Browser 与 current-head CI 等待实现后验证。

## 交付状态

- 提交：本 Change 初始化提交待创建。
- 拉取请求：待创建 Draft PR。
- CI：待实现完成后运行。
- 合并：未执行。
- Change 归档：未执行。
- 发布 / 部署：不适用；本需求只交付源码并合并 main。

## 备注

无。
