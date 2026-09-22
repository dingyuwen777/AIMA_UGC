---
schema: coding-change/v1
id: CHG-20260922-172133-catalog-alias-auto-deduplicate
title: 品牌车型重复别名自动去重保存
level: L2
status: ready_for_review
owner: codex
branch: fix/catalog-alias-auto-deduplicate
created: 2026-09-22
updated: 2026-09-22
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - contracts
  - administration
  - vehicles
  - documentation
affected_paths:
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/contracts/brand_vehicle.py
  - frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/CatalogConfigurationPanel.vue
  - frontend/e2e/admin-configuration-figma.spec.ts
  - tests/contracts/test_u1_u5_contracts.py
  - tests/api/test_brand_vehicle_stage2_contract.py
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/04_后端任务API与前端.md
contracts:
  - BrandCreateRequest.aliases
  - VehicleModelCreateRequest.aliases
  - VehicleModelUpdateRequest.aliases
data_changes: []
---

# 变更摘要

- **要解决的问题**：品牌或车型识别词包含规范化后重复项时，前端仍提交多个值，后端 Contract 返回 `body.aliases: value_error`，用户不能继续保存。
- **拟议修改**：前端按后端语义保留首项并去重，保存成功后明确提示；后端 Contract 同样幂等去重，保护直接 API 调用。
- **预期结果**：大小写或连续空格变体不再阻塞保存，数据库仍只接收规范化唯一的别名。

# 背景、现状与问题

Issue #564 固化了用户当前决定与六条验收标准。当前前端只按修剪后的原字符串 `Set` 去重；后端则按首尾修剪、内部空白折叠与 `casefold` 生成身份，并在重复时拒绝请求。两端不一致导致部分看似不同的输入直到 HTTP Contract 校验才失败。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | 前端 `splitLines` 只按原字符串去重 | 管理员品牌与车型页面 | 前端需补规范化身份去重 |
| E2 | Brand/Vehicle Contract 对规范化重复抛 `ValueError` | Pydantic Contract 与本地复现 | 后端应改为保留首项 |
| E3 | `Q7/q7` 与内部空格变体稳定复现 `body.aliases: value_error` | Issue #564、Contract 模型执行 | 建立回归测试 |
| E4 | 数据库按对象内规范化身份有唯一约束，跨对象同名允许 | Vehicle/Brand Alias Schema 与 Repository | 只收敛单次请求内重复，不扩大唯一范围 |

# 目标、成功标准与非目标

## 目标

- 同一品牌或车型内规范化重复的别名保留第一次出现的文本与顺序。
- 保存继续成功，页面提示“检测到重复识别词，已自动去重并保存。”
- 后端 Contract 对网页外的直接调用采用同一幂等收敛语义。

## 成功标准

- [x] 品牌新增/编辑与车型新增/编辑不再因规范化重复别名失败。
- [x] 前端提交体只包含去重后的别名，重复被移除时显示明确成功提示。
- [x] 后端 Brand/Vehicle Contract 返回稳定、去重且保留首项的 tuple。
- [x] 空别名继续拒绝，最多 100 个规范化唯一别名的边界继续生效。
- [x] Contract、Browser、静态检查、构建和本地项目门禁通过；current-head CI 继续作为合并硬门禁。

## 非目标

- 不改变跨品牌或跨车型允许相同别名的现有语义。
- 不修改数据库 Schema、Migration、目录版本、重筛或 AI 行为。
- 不执行生产部署、生产数据修改或 Canonical Replay。

## 必须保持不变

- 车型保存仍只提交实际变化字段，并在请求期间保持弹窗稳定。
- 品牌/车型保存不自动触发重筛。
- 服务端仍是唯一最终 Contract 守卫；生成 Client 不手工修改。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只修改管理员品牌车型输入、对应 Pydantic Contract 和当前行为文档 | E1—E4、#564 | 不触碰采集、Canonical Replay、AI 或其他配置页 |
| 接口与契约 | 原失败的重复数组改为幂等收敛；字段、响应形状和合法输入语义不变 | #564 / AC4 | 是向后兼容的输入放宽，不需要生成 Client 变更 |
| 数据与迁移 | 不修改 Schema、Repository 唯一范围或历史数据 | E4、#564 / AC5 | 无 Migration、回填或数据恢复动作 |
| 错误与失败语义 | 规范化重复不再是错误；空项和超过 100 个唯一项仍拒绝 | #564 / AC4、AC5 | 只把可确定收敛的输入转成成功 |
| 兼容性 | 保留第一次出现的显示文本与顺序，跨对象同名继续允许 | #564 / AC1、AC2、AC5 | 数据库只接收单对象内规范化唯一集合 |
| 部署与回滚 | 普通前后端发布；Git 回滚即可恢复旧行为 | 无 Schema、配置或依赖变化 | 不执行生产 Migration 或 Canonical Replay |

# 修改方案与决策依据

## 最小充分方案

1. 用 Contract 与 Browser 失败回归固定品牌/车型四条保存路径、提示和相邻边界。
2. 前端统一解析识别词，按修剪、折叠连续空白和忽略大小写的身份保留首项，并把重复数量用于成功反馈。
3. Brand Create、Vehicle Create/Update Contract 在数组长度检查前执行相同的幂等去重，保护直接 API 调用。
4. 同步当前产品与前端架构文档，执行生成、静态、构建、浏览器和项目门禁。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：前端提交前去重并提示 | E1、E3 | 避免把可修复输入变成 HTTP 错误，同时给用户明确结果 |
| D2：后端 Contract 同样去重 | E2、#564 / AC4 | 防止网页外调用绕过规则，并保持服务端最终守卫 |
| D3：不改数据库唯一范围 | E4、#564 / AC5 | 问题只发生在单次请求内，没有 Schema 或历史数据缺陷 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 规范化重复的品牌别名自动去重并保存成功 | #564 / AC1 | satisfied | 品牌新增/编辑 Browser 回归与 Brand Create Contract |
| R2 | 规范化重复的车型别名自动去重并保存成功 | #564 / AC2 | satisfied | 车型新增/编辑 Browser 回归与 Vehicle Create/Update Contract |
| R3 | 保存成功后明确告知已去重 | #564 / AC3 | satisfied | Browser 精确断言“检测到重复识别词，已自动去重并保存。” |
| R4 | 直接 API 请求保留首项并返回去重结果 | #564 / AC4 | satisfied | Brand/Vehicle Create 与 Vehicle Update Pydantic Contract 回归 |
| R5 | 保留空值、唯一数量上限、跨对象同名与既有保存行为 | #564 / AC5 | satisfied | Contract 覆盖空项拒绝、101 个原始重复可收敛、101 个唯一项拒绝；Schema/Repository 不变 |
| R6 | 完成分层验证、文档和交付门禁 | #564 / AC6 | explicitly_deferred | 本地分层验证、targeted 文档与 Review 已完成；current-head CI、merge、main-fresh 和归档只能在 Ready 后完成 |

# 计划改动

| 文件 / 模块 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| Brand/Vehicle Pydantic Contract | 在长度约束前按规范化身份保留首项 | 直接 API 调用也不再失败，唯一数量仍受限 | R1、R3 |
| 管理员品牌与车型页面 | 解析输入时返回去重结果和重复标记；四条保存路径显示成功提示 | 提交前收敛并提供用户反馈 | R1、R2 |
| Contract/API/Browser 测试 | 建立失败回归与相邻行为保护 | 防止再次出现前后端不一致 | R1—R3 |
| Product/Blueprint | targeted 同步自动去重的当前用户行为 | 防止产品说明与实现漂移 | R2、R4 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 前端别名解析、后端 Contract 去重 |
| 接口 / 契约 | required | BrandCreate、VehicleCreate/Update、OpenAPI/生成一致性 |
| 集成 / 持久化 | not_applicable | Schema/Repository 写语义不变；Contract 输出已是唯一集合 |
| 用户 / 工作流验收 | required | Browser Mock 品牌与车型保存及成功提示 |
| 跨组件关键路径 | required | PR 既有管理员 Full-stack/Golden Path 与 API CI |
| 外部依赖 / Provider | not_applicable | 不调用 TikHub、LLM 或其他外部 Provider |
| 构建 / 运行 | required | 前端 lint/test/typecheck/build，后端 Ruff/Mypy |
| 文档 / 治理 | required | targeted 文档、Completion Audit、Review、Ready Gate |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 主要风险 | 去重顺序漂移或把跨对象同名错误合并 | 只在单个请求数组内保留首项，测试稳定顺序 |
| Contract 兼容 | 放宽输入、响应形状不变 | 原合法请求完全不变；原失败重复请求转为成功 |
| 数据 / Migration | 不适用 | 无 Schema 或历史数据变化 |
| 部署 | 普通前后端发布 | 无配置、Worker、Secret 或 Migration 变化 |
| 回滚 | Git 回滚 | 无数据恢复动作 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 同步当前产品流程和后端任务/API/前端边界中的自动去重行为。
- **依赖 / Runtime**：不新增、删除或升级依赖和 Runtime。
- **配置 / Secret**：不变。
- **Schema / Migration / 数据**：不变，不需要历史回填。
- **部署 / Release**：本任务只交付源码，不执行生产部署、Migration 或 Canonical Replay。

# 完成审计

- [x] upstream_re_read：Ready 前重新读取 #564、用户决定、Contract、页面与产品文档，验收语义无漂移。
- [x] change_coverage：R1—R5 均映射到实现、Contract/Browser 测试和文档；R6 只延期 Ready 后才能发生的远程生命周期动作。
- [x] reverse_audit：从品牌/车型四条保存路径反查 Contract、API 与 Repository；只在单对象输入数组内去重，未新增保存到 Canonical Replay 的调用。
- [x] unresolved_cleared：`not_satisfied` 已清零；本机既有 Provider 输出污染和 Pytest 临时目录权限噪声明确隔离，干净 Linux CI 仍为合并硬门禁。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Red / Windows 本地 Contract | `pytest tests/contracts/test_u1_u5_contracts.py -q -k catalog_contracts_normalize_and_deduplicate_aliases` | 1 failed：`BrandCreateRequest.aliases` 对规范化重复仍抛 `value_error` | 后端当前拒绝重复，未满足自动收敛要求 |
| V2 | Red / Playwright Browser Mock | `npm run test:e2e -- admin-configuration-figma.spec.ts --grep "deduplicates normalized\|duplicate-only"` | 2 failed：页面找不到自动去重成功提示 | 前端当前既未按目标提示，也未支持重复清理交互 |
| V3 | Green / Windows 本地 Contract | `pytest tests/contracts/test_u1_u5_contracts.py -q -k catalog_contracts_normalize_and_deduplicate_aliases` | 1 passed | Brand Create、Vehicle Create/Update 保留首项去重，空项与唯一数量上限仍受约束 |
| V4 | Windows / Contract 与 API | Contract suite 排除一个本地历史 Provider 输出污染项；`pytest tests/api/test_brand_vehicle_stage2_contract.py -q`；生成/兼容检查 | 110 passed / 1 deselected；4 passed；生成与兼容通过 | 公共输入收敛、API Schema 和生成物没有意外漂移 |
| V5 | Windows / Frontend | ESLint；typecheck；Vitest；Vite build | lint/typecheck 通过；32 files / 227 tests；生产构建通过 | 前端静态、组件与构建无回归 |
| V6 | Windows / Playwright Browser Mock | `npm run test:e2e -- admin-configuration-figma.spec.ts` | 28 passed | 品牌新增/编辑、车型新增/编辑均自动去重并显示目标成功提示；既有手动重筛与弹窗行为仍通过 |
| V7 | Windows / Backend 与文档门禁 | Ruff changed scope；Mypy `backend/src`；architecture/table ownership；docs/docs-facts；Secret scan | 全部通过 | Python 静态质量、模块边界、文档导航和 Secret 边界成立 |
| V8 | base `5f90d856` → head `95c35875` 独立要求/实现/证据审查 | 用户决定、Issue、Change、四条保存入口、Pydantic Contract、测试与文档双向审计 | `NO_FINDINGS_WITHIN_SCOPE` | 未发现阻塞正确性、兼容、持久化或用户工作流的 Finding |

## 未验证内容与剩余风险

- 本地全量 Contract 的一个机器事实扫描被既有、未跟踪的历史 Provider 输出污染；未修改这些用户本地数据，干净 PR CI 负责完整 Linux 证据。
- 本地全量 Unit/API 初次运行受系统 Pytest 临时目录拒绝访问影响；相关 Contract/API 使用隔离临时目录已通过，完整干净环境仍以 PR CI 为准。
- 未执行生产部署、生产 Migration、生产数据修改或 Canonical Replay。

## 交付状态

- Issue：#564。
- 分支：`fix/catalog-alias-auto-deduplicate`。
- PR：#565，当前为 Draft；实现提交 `95c35875` 已推送。
- current-head required checks、合并、Issue Closure、Change Archive、main-fresh 与分支清理待后续完成。
- Schema / Migration / 依赖 / 配置：均不变；发布与生产操作不在本次执行范围。
