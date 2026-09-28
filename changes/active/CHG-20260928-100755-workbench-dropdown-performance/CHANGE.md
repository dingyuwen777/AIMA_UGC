---
schema: coding-change/v1
id: CHG-20260928-100755-workbench-dropdown-performance
title: 修复工作台下拉首次误开并优化心智趋势聚合
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/640-workbench-dropdown-performance
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - workbench
  - content
  - performance
affected_paths:
  - frontend/src/features/workbench/components/WorkbenchMultiSelect.vue
  - frontend/src/features/workbench/components/UgcTrendCard.vue
  - frontend/src/features/workbench/components/BrandMindCard.vue
  - frontend/src/features/workbench/pages/WorkbenchPage.vue
  - frontend/src/features/workbench/store.ts
  - frontend/e2e/workbench.spec.ts
  - backend/src/aima_ugc/adapters/persistence/postgres/workbench.py
  - backend/src/aima_ugc/bootstrap/workbench_http.py
  - tests/integration/content/test_workbench_runtime.py
  - docs/product/02_当前产品能力与用户流程.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：声音流多选面板首次进入即显示且在长选项/不同视口下错位；品牌用户心智和 UGC 趋势对同一范围重复恢复昂贵 PostgreSQL 事实，加载明显慢于声音流。
- **拟议修改**：让面板显示状态由组件 open 状态显式控制并按实际尺寸定位；将心智和趋势各自合并为单条范围快照查询，复用一次 active Scheme、人工复核/覆盖和标签恢复结果。
- **预期结果**：首次进入所有下拉关闭，交互与视口定位稳定；两个聚合模块减少重复关联和往返，统计/筛选语义保持一致。
- **补充目标**：三个模块以现有 12 列 Contract 的单列步进独立调整宽度、以单行步进调整高度；每个卡片按自己的真实容器宽度重排，单模块失败只重试自身。

# 背景、现状与问题

## 背景

Issue #640 / AC1–AC9 来自用户 2026-09-28 的工作台截图与明确交付要求。用户已授权完成 Review、CI 后合并 `main`。

## 当前现状

- `WorkbenchMultiSelect.vue` 给带 `popover` 的面板直接设置 `display:grid`，关闭态依赖浏览器 UA 样式；首屏截图证明该依赖在当前使用环境中失效。
- 面板定位用固定 275px 判断上下方向，未按真实内容高度和当前视口计算。
- Store 已经并发请求并逐模块提交，排除前端串行等待作为主要慢因。
- Trend HTTP 对同一查询范围调用 2 次 summary + daily + sentiment；Mind 调用 2 次 summary + 2 次 primary + 1 次 secondary。每次都执行 `_base_sql` 的 active Result、人工复核/覆盖、标签等完整关联。
- 布局 Contract 已允许 `column_span=4..12`，但 Store 把任意拖动强制量化为 `6/12` 两档；卡片 CSS 使用 viewport media query，宽屏中把单个模块缩窄时不会重排；任一模块的“重试”还会调用全量 `refreshData()`。

## 问题、根因或约束

下拉根因是关闭态没有由组件事实显式控制，表现依赖浏览器对 Popover 的支持和 UA 样式优先级；定位又使用固定估值。性能根因是同一模块请求内多次重建相同范围事实，而非三个模块未并发。永久修复需要分别切断这两个机制，不能只隐藏加载提示或提高轮询频率。

## 不修改的后果

用户首次进入仍可能被浮层遮挡；选项越多越容易越界。数据规模增长时每次筛选和 15 秒补读都会重复执行 4/5 组昂贵关联，放大数据库 CPU、I/O 和连接占用。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 首屏截图出现未点击的二级标签面板 | 用户截图 | 关闭态必须由组件显式保证 |
| E2 | 面板样式直接写 `display:grid`，定位固定 275px | `WorkbenchMultiSelect.vue` | 修复显示状态与真实尺寸定位 |
| E3 | Store 已对三个接口并发请求并逐模块 settle | `frontend/src/features/workbench/store.ts` | 不重复实现前端并发或合并接口 |
| E4 | Trend/Mind 分别调用 4/5 次重复 `_base_sql` | Workbench HTTP/Repository | 在各模块 Owner 内合并快照查询 |
| E5 | 聚合必须使用 active Scheme、人工复核/覆盖和当前标签 | 产品文档、集成测试、当前 SQL | 优化不能退化业务口径 |
| E6 | 投影已有日期/平台/品牌/车型索引和 AI 派生列，但 projection latest 可能不是 active Scheme | Schema/Migration、active Scheme 回归 | 继续按 active Scheme 恢复，不用错误快照换速度 |

## 推断与待确认

- 实际部署环境数据量、查询计划和端到端时延暂时无法验证；用户要求先按仓库测试交付。本 Change 只能用隔离 PostgreSQL 18 的代表性数据和查询计划证明优化机制，不能宣称线上时延数值。

# 目标、成功标准与非目标

## 目标

系统性修复声音流筛选面板首次误开/错位，在不改变工作台统计口径的前提下消除品牌心智与趋势请求内的重复聚合，并让三个模块的尺寸、内容重排与错误重试保持独立。

## 成功标准

- [ ] Issue #640 / AC1–AC9 全部有实现和新鲜证据。
- [ ] 代表性数据库基准记录基线与新实现的同口径结果和耗时。
- [ ] Completion Audit、独立 Review、current-head CI 通过并按授权合并 `main`。

## 范围

- Workbench 多选面板开关、定位、关闭和键盘/滚动行为。
- 三个模块的单列/单行尺寸调整、容器自适应和单模块重试。
- Mind/Trend PostgreSQL 只读聚合与 HTTP 响应组装。
- 直接相关的浏览器、API/集成、性能证据和产品事实同步。

## 非目标

- 不新增 Redis、WebSocket、缓存表或新的聚合服务。
- 不调整 15 秒可见页补读、声音流滚动或工作台布局。
- 不引入任意像素绝对定位画布；继续使用当前可持久、可兼容的 12 列布局 Contract。
- 不升级依赖、Runtime 或改变公共 API、Schema/Migration。

## 必须保持不变

- 三模块并发、独立更新/失败和 Scheme/Taxonomy 身份对齐。
- 所有筛选、北京时间日界、前后紧邻等长周期、人工复核/覆盖和 active Scheme 语义。
- PostgreSQL 是唯一业务事实源。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| UI 状态 | open 是显示事实；原生 Popover 仅负责 top layer/light dismiss，有显式 fallback | E1–E2 | 首次关闭不依赖 UA；浏览器支持时继续 top layer |
| 查询结构 | 每个慢模块单条快照 SQL，范围 base 只恢复一次 | E3–E5 | 保持三个独立接口，消除请求内重复关联 |
| 数据口径 | 继续按 active Scheme 恢复有效值 | E5–E6 | 不直接信任可能属于旧 Scheme 的 projection AI 列 |
| Contract/Schema | 保持现有响应和表结构 | 当前能力足够 | 无 generated client、Migration 或部署前置 |
| 性能声明 | 只报告隔离环境同口径基准 | 缺部署环境事实 | 不把仓库基准冒充线上 SLO |
| 布局粒度 | 复用 Contract 已允许的 4–12 列并按 1 列取整；高度继续 48–160 行按 1 行取整 | 用户要求自由缩放，当前 Contract 已具备范围 | 无公共 Contract/Schema 变化 |
| 模块独立性 | 各卡片按容器宽度重排；错误按钮只重试自身 | 新截图和现有调用链 | 全局筛选/周期刷新仍按产品规则更新三模块 |

# 修改方案与决策依据

## 最小充分方案

1. 给面板添加显式 open 状态样式，支持原生 Popover 与缺少 API 的 fallback；统一外部点击/Escape/页面滚动关闭。
2. 打开后读取触发器和面板真实尺寸，按上下可用空间选择方向并钳制 left/top/max-height 到视口。
3. 为 Trend/Mind 分别构建覆盖前后周期的 `MATERIALIZED base`，在同一 SQL 中返回 summary、daily/sentiment 或 primary/secondary 聚合快照。
4. HTTP Service 只调用一次对应快照并复用现有响应计算函数。
5. 用现有 active Scheme/人工覆盖集成数据做结果等价和筛选回归；用代表性数据做多轮基准与 EXPLAIN。
6. 移除 Store 的 `6/12` 二档硬编码，按 Contract 单列/单行钳制；以 CSS container query 让 Mind/Trend/Sound 在自身宽度变化时重排并保持内部滚动。
7. 增加 `refreshModule`，错误态重试只读取对应接口；全局筛选、Analysis 变化和周期补读仍按既有语义更新三个模块。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 显式关闭态 + fallback | E1–E2 | 直接切断首次误开机制，保持原生 top layer 能力 |
| D2 真实尺寸定位 | E2 | 选项数量、字体和视口变化不再依赖固定猜测 |
| D3 单模块单 SQL 快照 | E3–E6 | 复用昂贵事实且不把三个模块耦合成新接口/缓存 |
| D4 保持 active Scheme 关联 | E5–E6 | 避免用投影中的其它 Scheme 结果换取错误速度 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 首次进入所有声音流筛选面板关闭 | #640 / AC1 | not_satisfied | 已加入 Browser 失败回归，待实现。 |
| R2 | 点击打开对应面板并在视口内可滚动操作 | #640 / AC2 | not_satisfied | 已加入 Browser 位置断言，待实现。 |
| R3 | 外部点击/Escape/滚动/卸载关闭且焦点、ARIA 一致 | #640 / AC3 | not_satisfied | 待补完整交互回归。 |
| R4 | Mind/Trend 各一次数据库执行复用范围事实 | #640 / AC4 | not_satisfied | 已加入真实 PostgreSQL 失败回归，待实现。 |
| R5 | 代表性数据库基准证明改善 | #640 / AC5 | not_satisfied | 待建立基线、实现后对照。 |
| R6 | 统计、筛选、active Scheme 与人工覆盖不退化 | #640 / AC6 | not_satisfied | 复用并扩展现有集成回归。 |
| R7 | 三模块继续并发独立更新且状态真实 | #640 / AC7 | not_satisfied | 复用 Store/Browser 回归并补慢响应验收。 |
| R8 | 不新增平行事实或不必要 Contract/Schema/依赖 | #640 / AC8 | satisfied | 当前方案限定为组件状态与只读查询重组。 |
| R9 | 完成分层验证、Review、CI 和交付收尾 | #640 / AC9 | not_satisfied | 待执行。 |
| R10 | 三个模块横向按单列、纵向按单行独立缩放并分别持久化 | 用户补充请求 | not_satisfied | 已加入 Store/Browser 失败回归，待实现。 |
| R11 | 模块在自身窄宽度下重排，趋势图、KPI 和情感区不重叠 | 用户补充截图 | not_satisfied | 已加入 Browser 几何回归，待实现。 |
| R12 | 品牌心智失败提示的根因被切断；错误重试只请求品牌心智 | 用户补充请求 | not_satisfied | 已加入独立重试失败回归；聚合性能修复待实现。 |
| R13 | 声音流、心智、趋势的数据、布局和错误边界互不覆盖 | 用户补充请求 | not_satisfied | Store 请求代次与布局草稿待复核。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 理由 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Store 独立响应、查询快照解析和错误状态。 |
| 接口 / 契约 | required | 现有三个 Workbench API 响应与查询参数不变。 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 18 上 active Scheme、人工覆盖、筛选、前后周期和单 SQL 计数。 |
| 用户 / 工作流验收 | required | 首次关闭、打开定位、选择、外部/键盘/滚动关闭、加载/失败。 |
| 跨组件关键路径 | required | 浏览器 → generated client → Workbench HTTP → PostgreSQL 聚合。 |
| 外部依赖 / 供应方探测 | not_applicable | 不改 TikHub/LLM，也不需要外部付费调用。 |
| 构建 / 打包 / 运行 | required | Frontend lint/typecheck/build，Backend lint/type。 |
| 文档 / 治理 / 其他 | required | 产品事实 targeted re-review、Change Completion、PR CI。 |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 聚合 SQL 合并后口径漂移；窄卡片内容溢出；单模块响应污染其它模块代次 | 结果等价集成回归 + API/Browser 几何与乱序回归 + 真实 PostgreSQL 基准 |
| 兼容性 | 现有 Workbench Query/Response、generated client 和布局不变 | 不改 Contract |
| 数据 / Migration | 不适用 | 只重组 SELECT，不改表或数据 |
| 部署 / 运行 | 普通应用代码发布；无新配置/服务 | 进程拓扑与依赖不变 |
| 回滚 / 恢复 | 可回滚本 PR | 无不可逆数据或 Schema 行为 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 更新产品工作台的下拉关闭/定位和单次范围事实聚合说明，避免复制 SQL 实现细节。
- **依赖 / Runtime**：不新增、删除或升级依赖。
- **配置 / Secret**：无变化；不使用用户提供的 TikHub 凭据。
- **部署 / Release**：本任务只合并源码，不执行 Release/Deploy。

# 完成审计

- [ ] upstream_re_read：交付前重读 #640、用户请求、产品工作台事实和 Change Requirements。
- [ ] change_coverage：R1–R9 清零 `not_satisfied`，延期或不适用有正式依据。
- [ ] reverse_audit：核对前端所有筛选动作有真实后端支持；核对优化后的后端筛选/状态仍有当前页面消费者和回归。

# Review、CI 与交付记录

- 当前状态：已建立失败回归，尚未进入实现完成/Ready。
- Review：待实现后按当前 main 与 PR diff 独立执行。
- CI：待首次治理提交后创建早期 PR。
- 合并与收尾：用户已授权合并 `main`；仅在 required CI 和 Completion Gate 通过后执行。
