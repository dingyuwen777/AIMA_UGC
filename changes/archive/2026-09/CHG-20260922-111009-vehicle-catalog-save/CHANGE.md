---
schema: coding-change/v1
id: CHG-20260922-111009-vehicle-catalog-save
title: 简化车型配置并优化目录保存性能
level: L3
status: done
owner: codex
branch: perf/vehicle-catalog-save
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
  - frontend/e2e/
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/modules/vehicles/
  - migrations/versions/
  - tests/
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/04_后端任务API与前端.md
contracts: []
data_changes:
  - 为 content_vehicle_evidence.vehicle_model_id 增加完整索引
  - 为 vehicle_models.merged_into_id 增加索引
---

# 变更摘要

- **要解决的问题**：管理员车型表单包含无必要的“类别”输入；车型保存成功后还阻塞等待品牌与车型全量重载，后端目录列表又逐条查询别名和引用状态，真实目录规模下放大了保存等待时间。
- **拟议修改**：车型表单只保留车型名称、品牌、系列、识别词与状态；保存成功后用服务端响应更新本地目录；品牌与车型列表批量装配别名和引用状态；新增两个匹配引用检查条件的数据库索引。
- **预期结果**：新增或编辑车型后立即看到服务端规范化结果并结束保存；列表查询次数对当前页条目数保持有界；既有公共 HTTP Contract 与历史业务数据保持兼容。

# 背景、现状与问题

## 背景

Issue #558 固化了本轮用户决定和五条验收标准。用户已明确授权按系统方案修改并合并主分支。

## 当前现状

- 车型创建/更新 API 返回完整 `VehicleModelResponse`，前端保存成功后仍调用 `load()`，重新分页读取全部车型和品牌。
- `fetchVehicles()` 与 `fetchVehicleBrandsForAdmin()` 会顺序获取所有分页，因此一次车型保存的完成时间包含两类目录全量重读。
- 车型列表响应逐条查询 alias 和 referenced；品牌列表响应逐条查询 alias，查询次数随条目数增长。
- `content_vehicle_evidence.vehicle_model_id` 只有 `is_active` 条件的部分索引，而删除资格检查查询任意历史引用；`vehicle_models.merged_into_id` 没有匹配索引。
- AC1 的界面调整已在用户确认后形成未提交本地修改；本 Change 如实接管该现有修改，不伪造其实现前 Red 历史。性能与批量查询行为仍先建立失败回归证据。

## 问题、根因或约束

保存等待并非一个已经证明的“数据库写入慢”问题。已确认的放大链路是：保存请求成功后阻塞全量重读，而目录列表存在 N+1 查询和缺失索引；空目录本地实测无法代表真实数据量。永久修复应切断这条放大链路，并用查询数量与执行计划直接验证，不用提高超时或隐藏加载状态止血。

## 不修改的后果

目录越大，单次车型保存后的等待和 SQL 数量越高；历史引用与合并引用检查可能继续使用顺序扫描；成功写入还可能因后续重读失败而被前端展示为保存失败。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 车型保存后调用 `await load()`，而 `load()` 同时全量读取车型和品牌 | `CatalogConfigurationPanel.vue`、`frontend/src/features/admin-configuration/api.ts` | 保存成功后应直接消费服务端响应 |
| E2 | 车型列表逐条查询 alias 与 referenced，品牌列表逐条查询 alias | `administration_http.py`、`brand_vehicle_http.py` 及两个 PostgreSQL Repository | 列表投影应按当前页批量查询 |
| E3 | 两个引用检查条件缺少完整匹配索引 | 当前 Table metadata、Migration 与 PostgreSQL `EXPLAIN` | 增加可回滚索引，不改变引用语义 |
| E4 | 空 Compose 数据库的列表请求为毫秒级，不能复现真实数据规模 | 本轮本地 Compose 诊断 | 不把空库结果写成生产性能结论 |
| E5 | Issue 已明确要求兼容保留 `category_name` | #558 / AC1 | 只移除 UI 输入，不删除 API/数据库字段 |

## 推断与待确认

- **待确认**：真实生产目录规模、保存 P50/P95 与索引实际命中只能在部署到代表性环境后测量；不阻塞本次对已确认放大机制的修复，但本 Change 不宣称生产耗时已经达到具体数值。

# 目标、成功标准与非目标

## 目标

简化管理员车型编辑语义，并让保存完成时间不再包含全目录重读；让目录投影与引用检查在真实数据规模下具备有界 SQL 数量和匹配索引。

## 成功标准

- [x] 车型表单显示“车型名称”，不展示或提交类别，后端兼容字段保持不变。
- [x] 新增/编辑车型成功后用响应更新本地列表并立即结束保存，不触发品牌或车型全量重读。
- [x] 品牌、车型列表按当前页批量装配 alias 与 referenced，查询次数不随条目数线性增长。
- [x] 两个索引通过可回滚 Migration 和 Table metadata 建立，不回填、不改写业务数据。
- [x] 目标回归、PostgreSQL 集成、Contract 漂移、前端构建、文档、独立审查与本地就绪门禁通过；PR required checks 继续作为合并硬门禁。

## 范围

- 管理员品牌与车型页面的车型表单、保存后状态更新与浏览器验收。
- 品牌/车型列表投影的批量读取和 PostgreSQL 回归。
- 两个索引的 Table metadata、Alembic Migration、Schema 检查与相关文档。

## 非目标

- 不删除 API/数据库的 `category_name`，不做历史类别数据迁移。
- 不改变目录版本锁、品牌/车型业务校验、删除/合并资格语义或声音广场筛选 Contract。
- 不新增缓存、队列、并行请求框架或依赖。
- 不执行 Release、生产部署或生产 Migration。

## 必须保持不变

- Pydantic/OpenAPI/生成 TypeScript Client 的公共字段和错误语义。
- PostgreSQL 作为目录与引用事实源，Repository/Service/Router 既有 Owner 边界。
- 车型保存失败时保留弹窗草稿并展示错误；成功时采用服务端返回的规范化值、版本和 ID。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Page 负责本地响应合并，Repository 负责批量查询 | E1、E2 | 不建立前端第二事实源，不让 Router 直接 SQL |
| 接口与契约 | 公共 HTTP Contract 不变 | E5、#558 / AC1 | 不重新生成新字段，不删除兼容字段 |
| 数据与迁移 | 只增加两个普通索引 | E3、#558 / AC4 | 无回填、无业务数据改写，downgrade 删除索引 |
| 错误与失败语义 | 保存 API 失败保持原草稿；成功后的本地合并不再受重读失败影响 | #558 / AC2 | 修正成功与刷新失败被混合的语义 |
| 兼容性 | 列表响应字段、排序、分页和引用判定保持不变 | #558 / AC1、AC3 | 仅改变查询装配方式和 UI 输入面 |
| 部署与回滚 | 应用代码和 Migration 随普通发布顺序执行；源码回滚配合 downgrade | #558 / AC4 | 本任务只合并源码，不执行部署 |

# 修改方案与决策依据

## 最小充分方案

1. 用 Browser Mock 回归固定车型保存成功后不再发起目录 GET，并校验新增/编辑响应立即出现在当前品牌列表。
2. 在车型和品牌 Repository 增加按 ID 集合批量读取方法，列表 Router 一次读取当前页关联数据；保留单条响应路径兼容创建、更新和详情。
3. 用真实 PostgreSQL 集成测试对比 1 条与多条目录的 SQL 数量，证明查询次数有界，并校验响应别名/引用语义不变。
4. 在 Table metadata 和新 Alembic Migration 增加引用检查索引，验证 upgrade/downgrade 与索引定义。
5. 同步产品与架构文档，执行 Contract、构建、关键路径、Review、CI 和合并后门禁。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：保存后本地 upsert 服务端响应 | E1、E5 | 响应已是权威规范化事实，可直接切断全量重读等待且不改变 Contract |
| D2：批量投影而非缓存 | E2 | 在现有 Repository 边界内消除 N+1，不引入失效与一致性复杂度 |
| D3：补齐两个索引 | E3 | 索引与当前引用检查谓词匹配，可降低真实数据规模下的扫描成本 |

## 备选方案与取舍

- **只改前端**：可以立刻缩短保存等待，但目录首次加载和其他刷新仍保留 N+1，未闭合已确认根因链，未采用。
- **保存后后台静默全量刷新**：仍产生相同 SQL 放大，并引入迟到刷新覆盖当前状态的竞态，未采用。
- **新增缓存或搜索服务**：当前问题可由既有响应、批量 SQL 和索引解决，新增基础设施复杂度没有证据支持，未采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 车型字段改名并移除类别输入，保持后端兼容 | #558 / AC1 | satisfied | `CatalogConfigurationPanel.vue` 只提交车型名称、品牌、系列、别名与状态；Browser 32/32 通过；Contract 生成无差异，`category_name` 仍保留 |
| R2 | 保存成功后本地更新且不阻塞全量重读，失败保留反馈 | #558 / AC2 | satisfied | `saveVehicle()` 使用服务端响应本地 upsert；Browser 同时断言成功无额外目录 GET、失败保留草稿和错误 |
| R3 | 品牌/车型列表批量装配，查询次数有界 | #558 / AC3 | satisfied | Repository 批量读取当前页关联投影；真实 PostgreSQL 回归固定车型 6 条、品牌 4 条 SQL，1 条和 4 条页面一致，并校验别名与合并引用语义 |
| R4 | 增加可回滚索引且不改写业务数据 | #558 / AC4 | satisfied | Migration `20260922_0057` 与 Table metadata 一致；独立 PostgreSQL 18 上索引数量经 upgrade/downgrade/upgrade 为 `2/0/2`，无数据语句 |
| R5 | 分层验证、文档、Review 与合并就绪 | #558 / AC5 | satisfied | 前端、API、数据库、Schema/Migration、Contract、静态检查、构建、Wheel、文档和项目门禁取得当前工作树证据；独立 A1/A2 Review 无 Finding；PR required checks 在合并前强制执行 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `CatalogConfigurationPanel.vue`、管理员 E2E | 简化字段并在保存后本地 upsert | 消除无意义输入和全量重读等待 | R1、R2 / E1、E5 |
| Administration/Brand HTTP 与 PostgreSQL Repository | 批量读取别名和引用状态 | 消除列表 N+1 | R3 / E2 |
| Vehicle/Content Table metadata、Alembic、Schema tests | 增加并验证两个索引 | 匹配引用检查查询 | R4 / E3 |
| Product/Blueprint/Change | 同步当前行为、性能机制与证据 | 保持长期事实与实现一致 | R1–R5 |

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
| 行为 / 单元 / 组件 | required | 前端响应 upsert、后端批量分组与空集合边界 |
| 接口 / 契约 | required | Pydantic/OpenAPI/生成 Client 无漂移，兼容字段继续存在 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PostgreSQL 中列表关联语义、固定查询数量及 Migration/index |
| 用户 / 工作流验收 | required | 管理员新增/编辑车型的 Browser Mock 请求、表单与成功/失败状态 |
| 跨组件关键路径 | required | 管理员页面经真实 API/PostgreSQL 保存并重新查询车型的关键成功链 |
| 外部依赖 / 供应方探测 | not_applicable | 本次不修改或调用外部 Provider |
| 构建 / 打包 / 运行 | required | 前端类型检查和正式构建、后端静态检查与 Compose Migration/health |
| 文档 / 治理 / 其他 | required | 产品/架构文档、Migration graph、Change Ready、Issue/PR/CI/合并/归档 |

## 验证计划

- 目标测试：管理员 Playwright 保存工作流；车型/品牌批量 Repository/HTTP 回归；索引 Schema/Migration 回归。
- 相关回归：管理员配置 E2E、车辆管理单元/集成测试、API/Contract。
- 静态检查或构建：ESLint、Vue/TypeScript typecheck、Vite build、Ruff format/check、Mypy、docs/architecture/table-owner checks。
- 专项真实边界：Docker Compose PostgreSQL migration 与一条管理员保存 Golden Path。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 批量分组漏项、保存响应覆盖错误对象、索引 Migration 锁时间 | 空集合/多品牌/多车型/新增编辑回归；普通索引按项目发布窗口执行 |
| 兼容性 | 向后兼容 | HTTP 字段、数据库列、合法目录行为和错误保持不变 |
| 数据 / Migration | 只增加索引 | 不回填、不改写行；downgrade 删除本次索引 |
| 部署 / 运行 | 需要在应用发布前执行新 Migration | 本任务只提交并合并源码，不触发生产部署 |
| 回滚 / 恢复 | 代码回滚 + Alembic downgrade | downgrade 只删除新增索引，业务数据不变 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 同步管理员车型字段、保存后状态和目录批量投影/索引事实。
- **依赖 / Runtime**：不新增、删除或升级依赖和 Runtime。
- **配置 / Secret**：不改变配置、代理或 Secret；GitHub 外部操作仅在获准命令中使用 7897 代理。
- **部署 / Release**：需要随未来正式发布执行 Alembic upgrade；本次不执行生产部署、Release 或生产 Migration。
- **兼容 / 消费方通知**：公共 HTTP Contract 不变，无需消费者迁移；管理员 UI 不再提交 category。

# 完成审计

- [x] upstream_re_read：Ready 前重新读取 Issue #558 当前正文、用户决定、`docs/product/02_当前产品能力与用户流程.md`、`docs/blueprint/04_后端任务API与前端.md` 与当前 PR #559；五条 AC、非目标和兼容/回滚边界无漂移。
- [x] change_coverage：从 Issue #558 独立重建 AC1–AC5，对照本 Change 的 R1–R5、实现、测试和文档；没有把 Change 自身当作上游需求全集。
- [x] reverse_audit：从车型表单新增/编辑反查正式 API 响应与 PostgreSQL 持久化，从品牌/车型列表响应反查批量 Repository，从删除/合并引用查询反查 Table metadata 与 Migration 索引；公共 Contract、Owner 与失败语义保持不变。
- [x] unresolved_cleared：R1–R5 均为 `satisfied`；无延期或不适用的业务要求。真实生产数据规模下的 P50/P95 仍作为部署后观测边界，不被虚构为本轮已验证结论。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Red / Windows / Node 24.19 / Python 3.14 / 一次性 PostgreSQL 18 | `npm --prefix frontend run test:e2e -- admin-configuration-figma.spec.ts --grep "updates Brand aliases and creates a Vehicle"`；`.venv\\Scripts\\python.exe -m pytest tests/integration/database/test_u1_u5_administration.py -q -p no:cacheprovider -k "catalog_list_query_count"`；`.venv\\Scripts\\python.exe -m pytest tests/unit/database/test_u1_u5_schema.py -q -p no:cacheprovider` | Browser 1 failed：保存后响应车型未出现在列表；Integration 1 failed：4 个车型 15 条 SQL、1 个车型 6 条；Schema 1 failed、3 passed：两个索引未注册 | 旧实现确实存在保存后全量重读、列表 N+1 和索引缺口；数据库测试使用无持久卷独立容器，未接触本地开发数据 |
| V2 | Green / Windows / Node 24.19 | `npm --prefix frontend run lint`；`npm --prefix frontend run test -- --run`；`npm --prefix frontend run build`；受影响的三个 Playwright spec | lint 通过；Vitest 32 files / 227 tests 通过；typecheck + Vite production build 通过；Playwright 32/32 通过 | 前端类型、组件回归、正式构建，以及管理员车型成功/失败、字段和无额外目录 GET 的用户可见行为正确 |
| V3 | Green / Windows / Python 3.14 / 独立无卷 PostgreSQL 18.4 | `pytest tests/integration/database -q`；Alembic `upgrade head`、`downgrade 20260921_0056`、`upgrade head`、`current`、`check`；`pg_indexes` 核验 | Database 83/83 通过；head 为 `20260922_0057`；无待生成操作；目标索引数量 `2 → 0 → 2` | 真实 PostgreSQL 列表语义、固定查询数量、Schema 与 Migration 正反向路径成立，且不接触开发库 |
| V4 | Green / Windows / Python 3.14 | Ruff format/check（仓库 CI 正式范围并额外包含新迁移）、Mypy、`pytest tests/api -q` | Ruff 758 files clean；Mypy 364 source files clean；API 75/75 通过 | Python 静态质量、类型和 API 行为无回归 |
| V5 | 受限环境说明 / Windows | `pytest tests/unit -q`；`pytest tests/contracts -q` | Unit 1209 passed / 8 skipped / 9 failed；Contract 110 passed / 1 failed | 9 个 Unit failure 是现有 Linux/POSIX 或 Windows 文档扫描差异；1 个 Contract failure 只命中 Git 忽略的本机 Provider 原始输出。相关目标测试已通过，干净 Linux CI 仍为合并硬门禁，不把这些环境失败写成产品成功 |
| V6 | Green / Windows | Contract generator + Orval + generated diff + compatibility；architecture/table ownership/docs/docs facts；`uv build --wheel` + 独立 venv `--no-deps` install/import | 生成物无差异，兼容检查通过；四类项目门禁通过；Wheel 构建、安装、导入 `0.1.0` 成功 | 公共 Contract 未变，架构/Owner/文档一致，构建产物可用 |
| V7 | Review / base `0d587ac305936e8ada8cf7c41b03e840ceb285b7` → 当前工作树 | 独立重建 Issue #558 AC1–AC5；检查前端成功/失败状态、响应排序与归属、后端批量语义、历史引用、迁移回滚、兼容边界和测试真实性 | `NO_FINDINGS_WITHIN_SCOPE`；PR #559 当前 early revision 的失败门禁来自 Change 尚未 Ready，待本次提交触发 current-head checks | A1 上游要求无漏项；A2 实现均有匹配证据；最终可合并性仍由 current-head required checks 决定 |

## 未验证内容与剩余风险

- 真实生产数据量下的保存 P50/P95 尚未验证；本 Change 只对已确认查询放大机制建立确定性回归。

## 交付状态

- 提交：早期治理/Red 提交 `3faae03c`；实现与 Ready 证据提交待创建。
- 拉取请求：#559，已建立 `Requirement-Source: #558`，当前等待实现提交更新。
- CI：早期 revision 因 Change `in_progress` 按预期未通过 Completion/CI Gate；实现 revision 推送后重新执行全部 required checks。
- 合并：待执行。
- Change 归档：合并后由仓库自动化处理。
- 发布 / 部署：不在本次授权范围。

## 备注

- 无。
