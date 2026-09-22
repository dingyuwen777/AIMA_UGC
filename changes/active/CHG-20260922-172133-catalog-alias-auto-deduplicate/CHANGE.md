---
schema: coding-change/v1
id: CHG-20260922-172133-catalog-alias-auto-deduplicate
title: 品牌车型重复别名自动去重保存
level: L2
status: active
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

# 目标、成功标准与非目标

## 目标

- 同一品牌或车型内规范化重复的别名保留第一次出现的文本与顺序。
- 保存继续成功，页面提示“检测到重复识别词，已自动去重并保存。”
- 后端 Contract 对网页外的直接调用采用同一幂等收敛语义。

## 成功标准

- [ ] 品牌新增/编辑与车型新增/编辑不再因规范化重复别名失败。
- [ ] 前端提交体只包含去重后的别名，重复被移除时显示明确成功提示。
- [ ] 后端 Brand/Vehicle Contract 返回稳定、去重且保留首项的 tuple。
- [ ] 空别名继续拒绝，最多 100 个规范化唯一别名的边界继续生效。
- [ ] Contract、Browser、静态检查、构建和项目门禁通过。

## 非目标

- 不改变跨品牌或跨车型允许相同别名的现有语义。
- 不修改数据库 Schema、Migration、目录版本、重筛或 AI 行为。
- 不执行生产部署、生产数据修改或 Canonical Replay。

## 必须保持不变

- 车型保存仍只提交实际变化字段，并在请求期间保持弹窗稳定。
- 品牌/车型保存不自动触发重筛。
- 服务端仍是唯一最终 Contract 守卫；生成 Client 不手工修改。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | 前端 `splitLines` 只按原字符串去重 | 管理员品牌与车型页面 | 前端需补规范化身份去重 |
| E2 | Brand/Vehicle Contract 对规范化重复抛 `ValueError` | Pydantic Contract 与本地复现 | 后端应改为保留首项 |
| E3 | `Q7/q7` 与内部空格变体稳定复现 `body.aliases: value_error` | Issue #564、Contract 模型执行 | 建立回归测试 |
| E4 | 数据库按对象内规范化身份有唯一约束，跨对象同名允许 | Vehicle/Brand Alias Schema 与 Repository | 只收敛单次请求内重复，不扩大唯一范围 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 计划证据 |
| --- | --- | --- | --- | --- |
| R1 | 发现规范化重复时自动删除重复项并继续保存 | #564 / AC1、AC2、AC4 | not_satisfied | Contract 与 Browser 回归 |
| R2 | 保存成功后明确告知已去重 | #564 / AC3 | not_satisfied | Browser 可见提示断言 |
| R3 | 保留空值、上限和跨对象同名等相邻语义 | #564 / AC5 | not_satisfied | Contract/相关回归 |
| R4 | 完成分层验证、文档和交付门禁 | #564 / AC6 | not_satisfied | 本地验证、Review、PR CI |

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

# 完成审计

- [ ] upstream_re_read：Ready 前重新读取 #564、用户决定、Contract、页面与产品文档。
- [ ] change_coverage：R1—R4 均映射到实现、测试、文档与交付证据。
- [ ] reverse_audit：从前端四条保存路径反查 Contract 与 Repository，确认无旁路和无自动重筛。
- [ ] unresolved_cleared：`not_satisfied` 清零，未验证风险单独披露。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Red / Windows 本地 Contract | `pytest tests/contracts/test_u1_u5_contracts.py -q -k catalog_contracts_normalize_and_deduplicate_aliases` | 1 failed：`BrandCreateRequest.aliases` 对规范化重复仍抛 `value_error` | 后端当前拒绝重复，未满足自动收敛要求 |
| V2 | Red / Playwright Browser Mock | `npm run test:e2e -- admin-configuration-figma.spec.ts --grep "deduplicates normalized\|duplicate-only"` | 2 failed：页面找不到自动去重成功提示 | 前端当前既未按目标提示，也未支持重复清理交互 |

Green、静态检查、构建、Review 和 CI 证据待实现后填写。

## 交付状态

- Issue：#564。
- 分支：`fix/catalog-alias-auto-deduplicate`。
- PR、CI、合并、Change Archive 与 main-fresh：待后续完成。
