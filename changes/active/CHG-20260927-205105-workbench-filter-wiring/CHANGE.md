---
schema: coding-change/v1
id: CHG-20260927-205105-workbench-filter-wiring
title: 修复工作台真实数据筛选、滚动与趋势展示
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/634-workbench-filters
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - workbench
  - shared-ui
  - content
  - ingestion
affected_paths:
  - backend/src/aima_ugc/adapters/persistence/postgres/workbench.py
  - backend/src/aima_ugc/bootstrap/workbench_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/modules/vehicles/brand_vehicle.py
  - frontend/src/features/workbench/
  - frontend/src/features/voice-plaza/pages/VoicePlazaPage/
  - frontend/src/features/import-batches/store.ts
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue
  - frontend/src/shared/ui/
  - frontend/e2e/workbench.spec.ts
  - frontend/e2e/voice-plaza.spec.ts
  - frontend/e2e/historical-migration.spec.ts
  - frontend/tests/workbench.spec.ts
  - frontend/tests/collection-runtime.spec.ts
  - tests/api/test_workbench.py
  - tests/integration/content/test_workbench_runtime.py
  - tests/integration/content/test_workbench_scheme_bootstrap.py
  - tests/integration/ingestion/test_stage8b_import_http_worker.py
  - tests/integration/ingestion/test_stage12_historical_campaign_worker.py
  - tests/integration/vehicles/test_content_reclassification_postgres.py
  - tests/unit/test_brand_vehicle_resolver.py
  - docs/product/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：工作台筛选弹层、日期写入和刷新链路会造成不可操作、422、结果等待或暂时错误；声音流和趋势展示未达到 Figma；导入完成后的定位、作者、运行中统计和品牌车型解析存在可观察缺口。
- **拟议修改**：修复工作台前后端读取链、声音广场深链、Data Import 运行中读模型和统一 Brand/Vehicle Resolver，并补对应测试与当前产品文档；保持公共 Contract、Schema、依赖和部署方式不变。
- **预期结果**：用户按筛选即时取得三个真实模块结果，声音流连续滚动并可直达原声，导入中的结果及时可见，品牌车型按品牌优先规则稳定识别。

# 背景、现状与问题

## 背景

Issue #634 / AC1–AC13 汇总了本轮用户请求、截图、Figma 节点及后续补充。用户明确要求仓库验证完成后通过 Review、CI 并合并 `main`。

## 当前现状

- 工作台已有三个真实后端接口与 PostgreSQL 查询，但多选面板被横向容器裁切，日期两次写回可能形成反向范围。
- 三模块原来等待最慢请求后才一起更新；可见页没有持续补读，空库首次读取生成的 Scheme bootstrap 会随读事务回滚。
- 声音流只展示前六条且不连续滚动，作者只读 Account，平台标识和声音广场各自维护。
- Excel/统一导入的 Content 与声音广场投影已经同事务提交，但来源深链会叠加会话旧筛选；Data Import 运行中统计只在终态精确结算。
- Brand/Vehicle Resolver 原来先匹配车型再派生品牌，短 ASCII 别名会命中更长英文词。

## 问题、根因或约束

根因分布在多个真实边界：前端事件快照、并发 Store 提交、HTTP 读事务、声音广场会话筛选、Campaign 终态结算和统一 Resolver 顺序。继续叠加页面补丁不能闭合跨组件问题；方案必须保持当前 Contract/Schema 和吞吐边界，同时让已提交事实及时可读。

## 不修改的后果

用户仍会遇到筛选不可选、日期 422、正确筛选显示错误、导入结果难以定位、运行中统计为零、作者错误及品牌车型误识别，且短声音列表无法按 Figma 连续滚动。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 三个 Workbench API 已有统一 Query Contract 和 PostgreSQL Repository | `backend/src/aima_ugc/bootstrap/workbench_http.py`、`adapters/persistence/postgres/workbench.py` | 复用现有接口，不建立平行数据源 |
| E2 | 日期组件分开发出起止值，筛选条有横向裁切上下文 | `AimaDateRange.vue`、`WorkbenchFilters.vue` 原实现及 Browser 复现 | 日期必须原子提交，菜单进入 top layer |
| E3 | Generated Client 返回当前三个模块的 Scheme/Taxonomy 身份 | `frontend/src/generated/api/client.ts` | 独立响应后仍须防止混合口径 |
| E4 | 单文件 Import 的 Content、Version 与 Voice Plaza projection 在任务成功前同事务提交 | `test_stage8b_import_http_worker.py` 真实 PostgreSQL 回归 | 不新增异步回填或第二套缓存 |
| E5 | Content Version 保存 Excel 作者快照 | `content_versions.author_snapshot` 与工作台查询 | 作者优先取当前版本快照 |
| E6 | Campaign Chunk 已保存结算摘要，终态再从逐行账本精确汇总 | `historical_import.py`、Stage 12 Worker 测试 | 运行中只读已提交 Chunk 摘要，终态语义不变 |
| E7 | 前台导入优先屏障、Job Priority 与动态后台槽已存在 | 数据入口实现与现有容量测试 | 不更改资源配额或调度体系 |
| E8 | Excel、历史导入和历史重分类复用同一 BrandVehicleResolver | 生产调用链与 PostgreSQL Worker 测试 | 品牌优先和词边界只在统一 Resolver 实现 |
| E9 | Figma 节点定义连续声音流和粉色趋势折线 | Figma `4052:200`、`4190:4215` | UI 动效与图表按当前设计实现 |
| E10 | 远程 main 在施工期间前进 19 个提交 | `git fetch origin main`、rebase 结果 | 合并前必须基于最新 main 复验 |

## 推断与待确认

- 实际已部署环境的端到端时延暂时无法验证，因为用户不能提供环境地址和具体任务时间；不阻塞仓库交付，但不得宣称线上已经验证。

# 目标、成功标准与非目标

## 目标

让工作台根据用户选择及时展示真实后端数据，并完整闭合声音流、趋势、声音广场、导入运行统计和品牌车型解析的关联问题。

## 成功标准

- [x] Issue #634 / AC1–AC13 均有实现和自动化证据。
- [x] 本地 required 验证、独立 Review 和 Change Completion Gate 通过。
- [ ] 当前 PR HEAD 的 required CI 全部通过后合并 `main`，再确认归档与 Issue Closure。

## 范围

- Workbench 筛选、日期、并发更新、定时补读、滚动、图表、作者和深链。
- Voice Plaza 明确来源/内容深链的筛选恢复与详情定位。
- Data Import 运行中 Campaign 统计和来源项读取。
- Brand/Vehicle 自动解析顺序、ASCII 词边界及历史重分类回归。
- 直接受影响的产品与数据入口文档、测试和 Change。

## 非目标

- 不新增 WebSocket、Redis、Provider 推送或高频逐行轮询。
- 不改变 TikHub/LLM 调用、资源配额、调度策略或生产部署。
- 不修改公共 Contract、Schema/Migration、生成 Client 或依赖版本。

## 必须保持不变

- active Taxonomy / Scheme 一致性、当前 Workbench Query、布局 CAS 与声音广场合法筛选行为。
- PostgreSQL 是唯一业务事实库；Import 成功、投影和业务可见性继续同事务提交。
- Campaign 终态继续用既有逐行账本精确结算；前台导入优先和后台吞吐控制继续生效。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Workbench/Voice Plaza/Import Read Model/Resolver 各自在现有 Owner 内修复 | E1、E4、E6、E8 | 不复制 Store、Repository 或 Writer |
| 接口与契约 | 继续消费现有 generated Workbench/Content/Campaign Contract | E1、E3 | OpenAPI 与 generated client 无变更 |
| 数据与迁移 | 不改 Schema/Migration；运行统计来自已提交 Chunk JSON 摘要 | E4、E6 | 无回填或生产 Migration |
| 错误与失败语义 | 模块独立失败并保留上次成功快照；首次失败显示完整错误态 | #634 / AC7 | 网络瞬断不清空其它模块或旧数据 |
| 兼容性 | 日期旧事件继续发出；共享平台组件保持声音广场样式；人工品牌/车型锁语义不变 | 现有消费者与 Resolver 测试 | 既有页面和人工证据不退化 |
| 部署与回滚 | 普通应用代码发布；无需额外配置、迁移或数据操作；可回滚提交 | 无 Contract/Schema/依赖变化 | 本任务不执行 Release/Deploy |

# 修改方案与决策依据

## 最小充分方案

1. 将筛选菜单放入浏览器 top layer，日期一次写回有序范围，三个请求独立完成即提交，并增加 15 秒可见页补读。
2. 以 Figma 连续轨道实现声音流，复用平台标识，按 Content ID 跳转；趋势图消费后端 daily 数据调整视觉。
3. 提交 Workbench 首次 Scheme bootstrap，优先读取 Content Version 作者快照；明确深链重置旧筛选并直接读取详情。
4. 运行中 Campaign 只聚合已提交 Chunk 摘要并同步来源项；终态继续读取既有精确统计。
5. Resolver 先解析品牌、再限制车型候选；无品牌时全局车型回退；ASCII 边界在批次级自动机命中处统一执行。
6. 运行分层测试、targeted 文档复核、独立 Review、Completion Audit、CI、合并与归档核查。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 原子日期 + 独立模块提交 | E1–E3 | 直接切断 422 和最慢模块阻塞，不改变公共接口 |
| D2 15 秒补读而非新实时基础设施 | E1、E7 | 满足已入库事实近实时展示，同时控制聚合并发 |
| D3 深链与作者读当前事实 | E4、E5 | 修复可见性和作者根因，不引入异步复制 |
| D4 Chunk 摘要运行统计 | E6、E7 | 避免逐行账本轮询和父行写热点，保留终态准确性 |
| D5 统一 Resolver 品牌优先 | E8 | Excel、历史导入和重分类一次修复，避免路径漂移 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 声音流筛选项可点击并能看到可选项 | #634 / AC1 | satisfied | Browser 测试确认弹层位于顶层、内部滚动不关闭、选项可点击。 |
| R2 | 日期确认后起止日期完整且有序地进入三个模块查询，反向选日不再触发 422 | #634 / AC2 | satisfied | Browser 正反向日期请求、Store 单元测试、后端 Query 校验。 |
| R3 | 多选、重置和三模块呈现与当前 PostgreSQL 筛选口径保持一致 | #634 / AC3 | satisfied | Browser 三模块筛选/空态/重置、API 参数转发、PostgreSQL 集成筛选。 |
| R4 | 声音流按 Figma 连续向上滚动，悬停或聚焦暂停，并使用声音广场平台标识 | #634 / AC4 | satisfied | Browser 长短列表滚动、四类暂停和共享标识断言。 |
| R5 | 折线图按 Figma 的平滑粉线、渐变面积、点状网格与悬停提示呈现，值仍来自后端 | #634 / AC5 | satisfied | Design Context 对照、ECharts 配置复核与 Browser daily 响应渲染。 |
| R6 | 筛选确认后及时显示新数据，可见页持续检查新入库结果 | #634 / AC6 | satisfied | 日期直接请求、选项 100ms 合并、15 秒轮询 Browser 测试。 |
| R7 | 慢模块不拖住已返回模块；正确筛选与空库首次读取不产生口径漂移错误 | #634 / AC7 | satisfied | Store 延迟请求回归；独立数据库三接口并发 bootstrap；错误快照 Browser 回归。 |
| R8 | Excel 单文件导入完成后，已提交内容可在声音广场立即查询，来源深链不继承旧筛选 | #634 / AC8 | satisfied | Import Worker PostgreSQL 同提交投影；Browser 旧筛选深链回归；部署环境时延列为未验证。 |
| R9 | 声音流显示真实作者，与声音广场同源；点击笔记可定位对应详情 | #634 / AC9 | satisfied | Excel 作者快照集成测试；Workbench → Voice Plaza 跨分页详情 Browser 测试。 |
| R10 | 日期反向、取消、单日、清空均有一致的显示与请求口径 | #634 / AC10 | satisfied | Browser 日期生命周期回归；空日期恢复默认近 30 天。 |
| R11 | 尽可能快地展示已入库数据，保持其它处理吞吐与动态前台优先机制 | #634 / AC11 | satisfied | 三模块独立响应；现有优先屏障、后台槽与 Job Priority 复核；不增加逐行轮询。 |
| R12 | 采集运行中心导入期间持续更新处理统计和数据处理结果 | #634 / AC12 | satisfied | PostgreSQL 中间 Chunk 后 Campaign/来源项/统一运行 API；5 秒前端轮询 Store/Browser 回归。 |
| R13 | 品牌命中后只匹配该品牌车型；没有品牌时才由车型回推品牌；英文短别名不命中更长英文词；历史重筛沿用同一规则 | #634 / AC13 | satisfied | Resolver 24 项单元覆盖；PostgreSQL 重分类 Worker 验证历史 Evidence。 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `frontend/src/features/workbench/`、共享日期/平台组件 | 筛选、刷新、滚动、图表、作者和跳转交互 | 闭合工作台主要用户流程 | R1–R7、R9–R10 / E1–E3、E5、E9 |
| Workbench PostgreSQL/HTTP | 作者快照与首次 Scheme 提交 | 保证真实作者和空库一致性 | R7、R9 / E3、E5 |
| Voice Plaza Page/Table | 共享图标、深链筛选与直接详情 | 导入和工作台目标可准确定位 | R8–R9 / E4–E5 |
| Historical Import Repository/HTTP/Collection Runtime | 读取运行中结算统计并刷新来源项 | 终态前显示真实处理结果 | R11–R12 / E6–E7 |
| BrandVehicleResolver | 品牌优先和 ASCII 词边界 | 切断跨品牌及短词误匹配 | R13 / E8 |
| 前后端测试、产品文档、Change | 回归与当前事实同步 | 提供可复核交付证据 | R1–R13 |

- [x] 调查当前实现和事实源。
- [x] 建立与风险相称的验证矩阵。
- [x] 为缺陷建立自动回归证据。
- [x] 完成最小充分实现并避免无关重构。
- [x] 同步受影响的产品与数据入口文档。
- [x] 取得覆盖 rebase 后版本的新鲜验证证据。
- [x] 完成需求追溯、完成审计和独立 Review。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Workbench/Collection Runtime/Voice Plaza Store 与 Resolver；3 files / 51 前端测试及 Resolver 单元包含于后端 111 项。 |
| 接口 / 契约 | required | 三模块完整 Query 参数 API 测试；确认无 OpenAPI/generated diff。 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 18 + Alembic head 的筛选、导入投影/作者、并发 Scheme、运行统计和历史重分类；111 passed。 |
| 用户 / 工作流验收 | required | Workbench、Voice Plaza、Data Import 三条 Browser 流程；36 passed。 |
| 跨组件关键路径 | required | Import → projection → Voice Plaza/Workbench、Workbench → Voice Plaza、Chunk → Campaign/Runtime API 均有真实或 Browser 接线证据。 |
| 外部依赖 / 供应方探测 | not_applicable | 不改 TikHub/LLM；仓库测试不需要产生外部请求或费用。 |
| 构建 / 打包 / 运行 | required | ESLint、TypeScript/Vue typecheck、Vite production build 通过。 |
| 文档 / 治理 / 其他 | required | 产品/数据入口 targeted 同步；Completion Gate 通过；PR current-head CI 作为合并门禁。 |

## 验证计划

- 目标测试：工作台 Store/API/PostgreSQL、Resolver、Data Import 运行统计。
- 相关回归：声音广场深链、历史导入、历史重分类、错误快照。
- 静态检查或构建：Ruff、ESLint、TypeScript/Vue typecheck、Vite build、diff check。
- 专项真实边界：隔离 PostgreSQL 18 数据库与并发首次 Scheme bootstrap。
- 就绪检查：项目 `check_change_completion.py` 与 PR `check_pr_requirement_source.py`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 轮询聚合、Scheme 切换和视觉重复轨道 | 防重入；响应身份校验；视觉副本隐藏交互语义；Chunk 摘要有界聚合 |
| 兼容性 | 公共 API、generated client、日期旧事件、布局和人工 Evidence 保持兼容 | Contract/Schema 无 diff；相关回归通过 |
| 数据 / Migration | 不适用 | 不改 Schema、Migration 或生产数据；只读已存在 JSON 摘要 |
| 部署 / 运行 | 普通应用发布，无新配置或停机要求 | 依赖和进程拓扑不变；本任务未获 Release/Deploy 请求 |
| 回滚 / 恢复 | 可回滚本 PR 提交 | 无不可逆数据或 Schema 变化；终态统计事实未改写 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 更新 `docs/product/` 的当前工作台/导入能力及 `docs/appendix/08_数据入口与统一入库实现.md` 的 Resolver 规则。
- **依赖 / Runtime**：不新增、删除或升级依赖；Python、Node、PostgreSQL 基线不变。
- **配置 / Secret**：不改变配置、默认值或 Secret；未使用用户提供的 TikHub key。
- **部署 / Release**：不适用；没有 Migration、额外发布步骤、停机或生产操作，本任务只合并源码。
- **兼容 / 消费方通知**：现有前端继续消费 generated client；无外部调用方 Contract 变化。

# 完成审计

- [x] upstream_re_read：交付前已重读 Issue #634 / AC1–AC13、产品工作台能力和数据入口品牌/车型语义。
- [x] change_coverage：R1–R13 均有实现与验证证据；未把仓库外部署状态写成已验证。
- [x] reverse_audit：已核对前端筛选/日期/深链/轮询到真实 API，并核对 Workbench、导入投影、运行统计和 Resolver 后端能力的消费者。
- [x] unresolved_cleared：所有 Requirement 为 `satisfied`；required 本地验证通过，独立 Review 无未解决 finding。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | rebase 后分支 + PostgreSQL 18 隔离库 | `uv run pytest` 目标 API/Unit/Integration/Worker 集合 | 111 passed | 真实筛选、导入投影/作者、Scheme、运行统计和重分类 |
| V2 | rebase 后前端 | `npm run test -- --run ...` | 3 files / 51 passed | Store 与组件状态行为 |
| V3 | Chromium Browser Mock | `npm run test:e2e -- e2e/workbench.spec.ts e2e/voice-plaza.spec.ts e2e/historical-migration.spec.ts` | 36 passed | 三条用户流程、滚动、错误、日期、深链与运行更新 |
| V4 | 当前分支 | `uv run ruff check ...`、`npm run lint`、`npm run typecheck` | 通过 | Python/TS/Vue 静态质量 |
| V5 | 当前分支 | `npm run build` | 通过，835 modules | 生产构建可生成；仅既有大 Chunk 警告 |
| V6 | 当前分支 | `python scripts/quality/check_change_completion.py --root . --require-active-ready` | 通过 | Change 状态、AC 追溯与完成审计机器结构 |
| V7 | 当前分支 | `git diff --check` | 通过 | 无 whitespace error；Windows 仅 LF/CRLF 提示 |

## 未验证内容与剩余风险

- 实际部署环境的端到端导入时延未验证：用户暂不能提供环境和任务时间。仓库内已用真实 PostgreSQL 证明任务成功提交后投影立即可查询；该环境缺口不阻塞本次仓库交付。
- 当前 PR HEAD 的 GitHub required CI 仍需在 canonical Change 结构修正提交后重新通过，未以本地结果替代。

## 交付状态

- 提交：实现与 Change Ready 提交已在 `fix/634-workbench-filters`。
- 拉取请求：#635，已关联 #634。
- CI：上一轮仅因 Change 缺 canonical 标题失败；本次结构修正后待重跑。
- 合并：待 current-head required CI 通过后按用户授权合并 `main`。
- Change 归档：待 merge 后自动归档并核查。
- 发布 / 部署：不适用；用户要求合并源码，没有 Release/Deploy 授权。

## Review 结论

- 已修复 Review 中发现的面板内部滚动关闭、视觉副本重复交互语义、成功快照错误提示过度占位三项问题。
- Scheme bootstrap、模块身份、Campaign 聚合边界和统一 Resolver 调用链均已复核，没有未解决 finding。

## 备注

当前 Change 保持 active 供实现 PR 使用；合并后的 Change Archive workflow 负责转为 done/archive。
