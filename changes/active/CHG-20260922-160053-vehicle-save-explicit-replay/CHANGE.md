---
schema: coding-change/v1
id: CHG-20260922-160053-vehicle-save-explicit-replay
title: 车型保存与重筛解耦并修复慢响应弹窗
level: L2
status: ready_for_review
owner: codex
branch: fix/vehicle-save-explicit-replay
created: 2026-09-22
updated: 2026-09-22
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - administration
  - vehicles
  - persistence
  - documentation
affected_paths:
  - frontend/src/features/admin-configuration/
  - frontend/e2e/admin-configuration-figma.spec.ts
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - tests/integration/database/test_u1_u5_administration.py
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/04_后端任务API与前端.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：编辑已有车型时仍提交全部字段，后端存在重复行锁、无变化别名重写与重复引用查询；请求等待期间弹窗缺少保存状态且可被意外关闭。品牌/车型保存与历史 Canonical 重筛还需要永久回归证明只由显式按钮触发。
- **拟议修改**：前端只提交变化字段，保存中锁定弹窗并展示进度；后端复用已锁定车型并用单次查询计算引用状态；补充 Browser Mock 与 PostgreSQL 查询数量回归。
- **预期结果**：保存链更短、交互状态明确；只有点击并确认“重筛入库”才会创建 Canonical Replay。

# 背景、现状与问题

## 背景

Issue #562 固化了本轮用户决定和六条验收标准。上一轮已经提供全历史 Canonical 手动重筛入口，本轮只修正车型保存体验和两条链路的显式边界。

## 当前现状

- `saveVehicle()` 没有调用 Canonical Replay，但编辑单字段时仍发送名称、品牌、系列、全部别名和状态。
- 车型更新服务先锁定当前车型，Repository 随后再次查询并锁定同一行。
- 更新响应通过两个顺序查询判断内容证据或合并引用。
- 编辑弹窗在请求等待期间没有“正在保存”文案，且原生 Escape 或遮罩可关闭弹窗。
- 本地开发数据库已在 Alembic `20260922_0058`，两个相关引用索引存在；本地最近审计没有保存车型后创建 Replay 的记录。

## 问题、根因或约束

保存慢不能归因于自动重筛，因为当前保存调用链不创建 Replay。已确认的可消除同步开销是前端过量字段提交、重复车型锁和重复引用查询；交互混乱来自保存中状态不明确且弹窗仍可 dismiss。真实大数据环境端到端 P95 尚无本轮观测，不能虚构为已解决的单一数据库性能结论。

## 不修改的后果

普通名称修改仍会触发无变化别名删除/重建和多余 SQL；网络或数据库稍慢时，用户无法判断保存是否仍在执行，并可能通过 Escape/遮罩关闭编辑层。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 车型保存只调用 Vehicle API，Replay 只由按钮确认函数调用 | `CatalogConfigurationPanel.vue`、`api.ts`、FastAPI Router | 保存与重筛保持显式分离，并补永久回归 |
| E2 | 前端编辑请求固定发送全部可编辑字段 | `saveVehicle()` | 只发送真实变化字段 |
| E3 | 后端对同一车型执行两次 `FOR UPDATE`，引用状态最多两次查询 | `administration_http.py`、`vehicles.py` | 复用已锁定对象并合并引用查询 |
| E4 | 保存时 `saving=true`，但弹窗仍允许原生取消/遮罩关闭且按钮文案不变 | `CatalogConfigurationPanel.vue`、`AimaDialog.vue` | 在当前页面拦截 dismiss 并展示保存状态 |
| E5 | 本地开发库为 `20260922_0058` 且引用索引存在 | 2026-09-22 本地 PostgreSQL 只读查询 | 本轮不新增 Migration，不把缺索引当作当前本地根因 |

## 推断与待确认

- **待确认**：生产或大数据环境的实际网络、锁等待和 P95；本轮通过减少确定性往返和真实 PostgreSQL 查询数量回归降低同步开销，但部署后仍需按目标环境观测。

# 目标、成功标准与非目标

## 目标

让车型保存只做目录更新并缩短同步链路；让保存中的编辑弹窗保持稳定、可理解；用自动化测试证明 Replay 只能由显式按钮触发。

## 成功标准

- [x] 车型保存不请求 `/api/v1/canonical-replays/all`。
- [x] 只修改名称时 PUT 仅包含 `display_name`，无变化别名不重写。
- [x] 保存未完成时弹窗显示“正在保存…”且 Escape、遮罩、取消、删除不能关闭或修改草稿。
- [x] 成功后才关闭并本地更新；失败保持弹窗、草稿和错误。
- [x] 后端去除重复行锁与重复引用查询，并以 PostgreSQL SQL 数量回归保护。
- [x] 目标测试、相关回归、构建、文档和独立 Review 已通过；当前 PR required checks 继续作为合并硬门禁。

## 范围

- 管理员车型编辑请求、保存中弹窗状态和 Browser Mock 验收。
- 车型更新 Application Service / Repository 的同步 SQL 收敛。
- 产品与前端架构文档中的显式重筛和保存反馈事实。

## 非目标

- 不改变品牌保存、车型合并/删除业务语义。
- 不修改 Canonical Replay 的 Artifact 范围、分组、Job 或 Worker。
- 不修改公共 HTTP Contract、数据库 Schema、Migration、依赖或 Runtime。
- 不执行生产部署、生产 Migration 或生产 Replay。

## 必须保持不变

- 车型更新响应、错误语义、审计和目录版本递增规则。
- 保存失败保留草稿；成功结果采用服务端规范化响应。
- Replay 只使用现有显式 API 和幂等边界。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 重筛触发 | 只允许“重筛入库”确认动作创建 Replay | #562 / AC1 | 目录保存不隐式排队 Job |
| 更新请求 | 仅发送相对当前服务端投影发生变化的字段 | #562 / AC2 | 保留 PATCH-like PUT Contract 的缺省语义 |
| 弹窗状态 | 请求未结束前不可 dismiss，成功后自动关闭，失败保留 | #562 / AC3、AC4 | 明确完成边界，避免重复操作 |
| 后端性能 | 只减少冗余 SQL，不改变目录写事务和响应 Contract | #562 / AC5 | 无 Schema/部署兼容变化 |

# 修改方案与决策依据

## 最小充分方案

1. 先用延迟 Vehicle PUT 的 Browser 测试固定保存中状态、禁止关闭、最小请求体和零 Replay 调用。
2. 前端根据当前车型构造差异请求，无实际变化时禁止保存。
3. 编辑弹窗改为受控关闭；保存中拦截 Escape/遮罩并禁用会改变状态的控件。
4. 后端把已锁定车型传给 Repository，引用判断收敛成单次 SQL；用查询数量测试防回退。
5. 同步当前产品行为并执行分层验证。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 保存不触发 Canonical Replay | #562 / AC1 | satisfied | 延迟保存 Browser 回归拦截全量 Replay 路由并断言零请求；生产保存调用链无 Replay 依赖 |
| R2 | 更新只发送变化字段 | #562 / AC2 | satisfied | Browser 回归断言单改名称只有 `display_name`，清空系列/别名仍正确提交 `null`/空数组 |
| R3 | 保存中弹窗稳定且有明确反馈 | #562 / AC3 | satisfied | 延迟响应期间“正在保存…”禁用，Escape/遮罩不关闭，表单与危险操作禁用 |
| R4 | 成功/失败状态保持正确且不全量重载 | #562 / AC4 | satisfied | 管理员 E2E 覆盖成功本地 upsert、零目录 GET 和失败保留草稿 |
| R5 | 后端减少冗余 SQL | #562 / AC5 | satisfied | PostgreSQL 回归证明单字段更新由 11 次降至 9 次，别名保持不变 |
| R6 | 分层验证、文档和交付门禁 | #562 / AC6 | explicitly_deferred | 本地分层验证、targeted 文档与 Review 已完成；current-head CI、merge、main-fresh 和归档只能在 Ready 后完成 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 差异请求、保存状态与关闭守卫 |
| 接口 / 契约 | required | 既有 Vehicle Update Contract 不变、生成物无漂移 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PostgreSQL 更新语义与 SQL 数量 |
| 用户 / 工作流验收 | required | Browser Mock 延迟成功、失败保留、零 Replay 调用 |
| 跨组件关键路径 | not_applicable | 公共接口和跨层语义不变；PR CI 复用现有真实 Golden Path |
| 外部依赖 / 供应方探测 | not_applicable | 不调用 TikHub、LLM 或其他外部 Provider |
| 构建 / 打包 / 运行 | required | 前端 lint/typecheck/build、后端 Ruff/Mypy |
| 文档 / 治理 / 其他 | required | targeted 文档、Completion Audit、Review、Ready Gate |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 差异请求漏传清空值；保存中关闭守卫影响正常成功关闭 | 显式 null/空别名回归；延迟成功/失败 Browser 验收 |
| 兼容性 | 向后兼容 | HTTP Contract、响应、错误和数据库结构不变 |
| 数据 / Migration | 不适用 | 不新增或修改 Schema，不回填数据 |
| 部署 / 运行 | 普通前后端发布 | 不改变配置、Secret、Worker 或 Migration |
| 回滚 / 恢复 | Git 回滚实现提交 | 无数据恢复动作 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 同步品牌/车型保存与手动重筛的用户行为。
- **依赖 / Runtime**：不新增、删除或升级依赖和 Runtime。
- **配置 / Secret**：不变。
- **部署 / Release**：本任务只修改源码，不执行生产部署。

# 完成审计

- [x] upstream_re_read：Ready 前重新读取 Issue #562、用户当前决定、产品文档、前端架构说明与真实调用链；六条 AC 无漂移。
- [x] change_coverage：R1—R5 均映射到实现、Browser/PostgreSQL 回归与文档；R6 仅延期 Ready 后才能发生的远程生命周期动作。
- [x] reverse_audit：从车型保存反查 Vehicle API/Service/Repository，从重筛按钮反查 Canonical Replay API；只有确认重筛函数调用 Replay，不存在保存到重筛的交叉触发。
- [x] unresolved_cleared：`not_satisfied` 已清零；生产规模 P95 和部署后锁等待保留为未验证风险，不把本地 SQL 收敛夸大为生产性能结论。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Red / Windows 本地浏览器 Mock | `npm --prefix frontend run test:e2e -- admin-configuration-figma.spec.ts --grep "keeps Vehicle save explicit"` | 1 failed：保存中不存在“正在保存…”按钮 | 保存状态和不可关闭边界在修改前缺失 |
| V2 | Red / PostgreSQL 18.4 隔离容器 | `.venv\\Scripts\\python.exe -m pytest tests/integration/database/test_u1_u5_administration.py -q -k vehicle_display_name_update_uses_bounded_queries` | 1 failed：实际 11 次 SQL，不满足 9 次上限 | 重复行锁和顺序引用查询在修改前真实存在 |
| V3 | Windows / Playwright Browser Mock | `npm --prefix frontend run test:e2e -- admin-configuration-figma.spec.ts` | 26 passed | 明确按钮重筛、车型差异保存、慢请求弹窗保护、失败草稿和管理员页面回归成立 |
| V4 | PostgreSQL 18.4 隔离容器 / Alembic `20260922_0058` | `pytest tests/integration/database/test_u1_u5_administration.py -q` | 5 passed；名称单字段更新 9 次 SQL | 事务、审计、目录投影、别名保持与查询数量收敛成立 |
| V5 | Windows / frontend | ESLint；Vitest；typecheck + Vite build | lint 通过；32 files / 227 tests；生产构建通过 | 前端静态、组件和构建无回归 |
| V6 | Windows / backend | Ruff changed scope；Mypy `backend/src`；完整 API | Ruff clean；Mypy 364 files clean；API 76 passed | Python 静态质量和 HTTP 行为无回归 |
| V7 | Windows / Contract 与文档 | Contract generate `--check`/compatibility；docs/docs-facts；architecture/table ownership | 全部通过 | 公共 Contract 未漂移，文档与模块边界一致 |
| V8 | Windows 扩大回归 | `pytest tests/unit -q`；`pytest tests/contracts -q -k "not current_machine_facts_do_not_reintroduce_platform_aliases"` | Unit 1215 passed / 8 skipped / 3 Windows POSIX-only failed；Contract 110 passed / 1 本地 Provider 输出污染项 deselected | 除已识别本机/平台既有边界外无新增失败；干净 Linux PR CI 仍为合并硬门禁 |
| V9 | base `b95d3fb1` → head `f8264f90` 独立要求/实现/证据审查 | 保存入口、Replay 入口、前后端 diff、测试和文档双向审计 | `NO_FINDINGS_WITHIN_SCOPE` | 未发现阻塞正确性、兼容、事务或用户工作流的 Finding |

## 未验证内容与剩余风险

- 真实生产规模和网络下的保存 P95 尚未验证。
- 未修改或删除污染全量契约扫描的本地 Provider 原始输出；干净 PR CI 负责给出当前 revision 的完整 Linux 契约证据。
- 未执行生产部署、生产 Migration 或生产 Replay。

## 交付状态

- Issue：#562；PR #563；分支 `fix/vehicle-save-explicit-replay`。
- Red/Change 提交 `e96560a4`；实现提交 `f8264f90`；Ready 提交待创建。
- PR 当前仍为 Draft；current-head required checks、合并、Issue Closure、Change Archive、main-fresh 与分支清理待后续完成。
- 发布 / 部署：不在本次授权范围，且本轮无 Schema/Migration/依赖变化。

## 备注

- 无。
