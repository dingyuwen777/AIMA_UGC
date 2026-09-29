---
schema: coding-change/v1
id: CHG-20260928-212400-hierarchical-label-multiselect
title: 统一工作台与声音广场的层级标签多选筛选
level: L2
status: done
owner: codex
branch: feature/652-hierarchical-label-multiselect
created: 2026-09-28
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - workbench
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/src/features/workbench/
  - frontend/tests/
  - frontend/e2e/
  - tests/api/test_stage8d_contents.py
  - tests/integration/content/test_stage8d_voice_plaza_runtime.py
  - docs/product/02_当前产品能力与用户流程.md
contracts:
  - ContentFilterSnapshot primary_labels / secondary_labels
data_changes: []
---

# 变更摘要

- **要解决的问题**：工作台虽然已有标签数组筛选，但二级候选没有按一级收敛；声音广场仍是一级/二级单选，且公共 Content Filter 只能表达 singular 标签。
- **实际修改**：兼容扩展 plural Contract；统一 projection/fallback 多值查询；两页建立“父级决定二级候选、父级取消清理失效子项”的状态不变量；深链改为 plural 并兼容 legacy singular。
- **预期结果**：用户可在工作台和声音广场多选一级、二级标签，且不会选择或隐藏携带不属于当前一级集合的二级条件。

# 背景、现状与问题

## 背景

Requirement Source 为 canonical `[需求]` Issue #652。用户要求工作台和声音广场的一级、二级标签都支持多选，并且选择一级标签后只能选择这些一级标签下面的二级标签。用户随后明确本任务只提交 PR，不合并 `main`。

## 当前现状

- 工作台 `WorkbenchQuery` 已使用 `primary_labels / secondary_labels` 数组，服务端注释和 SQL 均定义同维度 OR、跨维度 AND。
- 工作台前端原先把 active Taxonomy 的所有二级标签平铺展示。
- 声音广场 `ContentFilterSnapshot` 原先只有 `primary_label / secondary_label` 单值。
- 声音广场存在 projection ready 热路径和 projection 未就绪 fallback 路径。
- List、Count、query-scope Analysis/Export 通过 `ContentFilterSnapshot` / `ContentTargetSelection.filters` 共享查询事实。
- Workbench → Voice Plaza 原深链只在恰好一个标签时传递 singular Query。

## 问题、根因或约束

只把控件换成 checkbox 不足以解决问题。若 Store 不清理失效二级值，用户取消一级后旧二级仍可能隐藏参与查询；若只修改 projection 热路径，projection 未就绪时会出现同一筛选不同结果；若直接删除 singular Contract，又会破坏旧 HTTP 调用和历史 Analysis/Export 快照。

## 不修改的后果

两页筛选行为继续不一致；声音广场无法表达多标签查询；工作台用户仍能看到未选一级下的二级候选；未来 projection/fallback 或历史快照可能出现语义漂移。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Workbench 服务端已经是 plural，并使用两个独立 `EXISTS ... ANY(array)` | `contracts/workbench.py`、`postgres/workbench.py` | 声音广场多选必须与工作台保持同维度 OR、跨维度 AND |
| E2 | Voice Plaza 原 Contract 是 singular，List 会经 `_filters()` 转为 `ContentFilterSnapshot` | `contracts/http.py`、`bootstrap/content_http.py` | 应在公共 Filter Snapshot 做兼容扩展 |
| E3 | Analysis query scope 会持久化 Filter Snapshot，Planner 恢复时执行 `ContentFilterSnapshot.model_validate` | `content_http.py`、`analysis_high_throughput_planner.py` | 保留 singular 即可兼容旧历史快照，无需 Migration |
| E4 | Export query scope 直接用 `ContentTargetSelection.filters` 冻结目标并保存 request snapshot | `bootstrap/reporting_http.py` | plural Filter Snapshot 可自然贯穿导出 |
| E5 | Voice Plaza projection 与 fallback 是两套 SQL 构造入口 | `content_queries.py` | 两条路径必须同时实现多选语义 |
| E6 | 前端动态筛选目录保留 active + historical 标签父子关系 | `ContentFilterOptionsResponse` + Voice Plaza filter options | 父子合法性应由后端目录/Taxonomy 驱动，不维护静态平行枚举 |
| E7 | 专项验证 run 36433340226 三 Job 全绿 | GitHub Actions | 当前实现已有 Backend、PG、Frontend 分层证据 |
| E8 | Browser Review 曾复现层级菜单展开覆盖“查询”按钮 | Temporary Validation 早期失败日志 | 需要让 tertiary 多选展开参与布局，而不是只改测试点击方式 |
| E9 | R655-F1 证明旧版允许 secondary-only Route/Session；原实现会在动态目录加载后把该筛选清空并放宽为无标签查询 | PR #655 Review comment 5873630388 + `VoicePlazaPage.vue` / `store.ts` 调用链 | 兼容迁移必须在真实目录加载后补齐父级；无法解析时保留旧 secondary-only 精确条件，不能静默放宽 |
| E10 | R655-F2 证明新增空 plural 默认字段会改变旧 `_query_hash` payload，导致仍在有效期内的旧 Cursor 失效 | PR #655 Review comment 5873630388 + main@f77e02c 的旧 `ContentFilterSnapshot` / `_query_hash` | query hash 必须规范化空 plural 与 singleton plural，且不能放松 Cursor query binding |
| E11 | R655-F1b 证明旧 Workbench 可产生 cross-parent singular Route/Session；该状态在旧服务端按一级维度 AND 二级维度合法执行，不能强行改写成当前父子层级 | PR #655 Review comment 5874500915 + 旧 Workbench 深链规则 + 当前 Store sanitize 调用链 | legacy compatibility 必须带来源状态；无法无损层级化或目录已缺失的旧值原样保留并在 UI 明示，直到用户主动修改标签 |
| E12 | singular + plural 在 Pydantic field 长度校验之后才归一化，理论上可把 100/200 上限追加成 101/201 | PR #655 Review comment 5874500915 + `ContentFilterSnapshot.validate_date_order` | 最终归一化集合必须再次执行 100/200 cardinality 校验 |
| E13 | R655-F1c 证明 Filter Options 在 `catalog_status=building` 时可能只暴露目录子集；用当前目录给 legacy secondary-only 自动补父级会在 ready 后发现更多父级时永久收窄旧查询 | PR #655 Review comment 5882316280 + `refreshFilterOptions()/sanitizeLabelFilters()` 生命周期 | legacy compatibility 不得由动态 Filter Options 自动改写；只有用户主动修改标签并提交才退出 |

## 推断与待确认

无。当前关键机制均已由代码、实际 PostgreSQL 或 Browser Evidence 确认。

# 目标、成功标准与非目标

## 目标

- 两页一级、二级标签都可多选。
- 二级候选只来自已选一级标签，未选一级时不可选；父级取消时同步清理失效子项。
- 同一维度 OR，一级维度与二级维度 AND，并与工作台现有 PostgreSQL 语义一致。
- 声音广场列表、Count、query-scope Analysis/Export 复用同一 `ContentFilterSnapshot`。
- projection ready 热路径与 fallback 路径一致。
- 新前端只发 plural 字段；legacy singular HTTP/历史快照继续兼容。
- Workbench → Voice Plaza 支持多标签深链；legacy singular 深链可恢复。

## 成功标准

- [x] AC1–AC5：两页多选、父子候选和失效子项清理有 Unit + Browser Evidence。
- [x] AC6–AC8：服务端语义与工作台一致，并由实际 PostgreSQL 验证 projection/fallback。
- [x] AC9：plural + legacy singular Contract 兼容且 generated client clean。
- [x] AC10：plural 深链与 legacy singular 恢复都保留。
- [x] AC11：Backend/API、PostgreSQL、Frontend Unit/Browser、Contract generation/compatibility 均已有新鲜绿色证据。

## 范围

- Content Filter Contract 与 Query Read Model。
- Voice Plaza 标签筛选状态、控件、路由恢复。
- Workbench 标签父子候选、状态清理、深链。
- 相关 Unit/API/PostgreSQL/Browser 测试、生成物和当前产品文档。

## 非目标

- 不修改 active Taxonomy 内容、标签层级定义或 AI Prompt。
- 不新增数据库表、列或 Migration。
- 不升级依赖、不改变其它筛选维度。
- 不执行 Release、Deploy 或生产数据操作。
- 按用户最新指令，本任务只提交 PR，不合并 `main`。

## 必须保持不变

- 旧 `primary_label / secondary_label` HTTP 输入仍可解析。
- 旧 Analysis query snapshot 仍可由 Planner 恢复。
- Workbench 既有“同维度 OR、跨维度 AND”查询口径不变。
- 其它平台、品牌、车型、情感、发声类型、日期、相关性、排序和 Cursor 语义不变。
- 现有 CI、Branch Protection、Release/Deploy 权限边界不降低。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只改 Content Read Filter + Workbench/Voice Plaza 前端 | E1–E6 / #652 | 不扩到 Taxonomy、Prompt 或其它页面 |
| 接口与契约 | additive 新增 plural，singular 保留并归一化 | E2–E4 | 新前端用 plural；旧调用不破坏 |
| 数据与迁移 | 不新增 Migration | E3 | 历史 JSON snapshot 在读取时经 Pydantic 兼容 |
| 错误与失败语义 | 无新增错误码；筛选目录不可用时保留原独立失败边界 | 现有 Voice Plaza 设计 | 不因标签改动扩大错误面 |
| 兼容性 | Session/Route 也兼容旧 singular 值 | #652 / AC9–AC10 | 旧会话和旧链接可恢复 |
| 部署与回滚 | 普通源码回滚，无数据恢复 | 无 Schema/依赖变化 | 不需要额外部署步骤 |
| 交付 | 仅提交 PR，不 merge | 用户最新指令 | 不执行 main-fresh/archive/issue closure/cleanup |

# 修改方案与决策依据

## 最小充分方案

1. **Contract**
   → `ContentFilterSnapshot` 增加 `primary_labels/secondary_labels`
   → singular 输入合并进 plural 后清空 singular
   → API 回归 + generator/compatibility 验证。

2. **PostgreSQL Read Model**
   → projection JSONB 标签按两个多值维度独立 OR
   → fallback AI/manual 标签按相同语义过滤
   → 实际 PG 测试在 ready/pending 两种 projection 状态下验证。

3. **Voice Plaza 状态与 UI**
   → Store 使用数组并持久化 plural
   → filter options 刷新和 apply 时都清理父子非法值
   → 两级 checkbox 多选；二级未选父级时禁用
   → tertiary 展开菜单参与正常布局，避免覆盖查询按钮。

4. **Workbench**
   → 二级候选只从所选一级生成
   → Store 再次执行父子合法性清理
   → 深链输出 plural arrays；心智单维度钻取不携带旧二级。

5. **Compatibility / Docs / Tests**
   → Voice Plaza 恢复 plural，缺失时回退 singular
   → 正式生成 OpenAPI/Orval
   → 同步当前产品说明
   → Unit/API/PG/Browser 分层回归。

6. **PR #655 首轮 Repair Batch**
   → R655-F1：先建立 legacy compatibility state，避免 secondary-only 在目录加载时被清空放宽；后续 R655-F1c 进一步收紧为“不依据任何动态目录阶段自动补父级”
   → R655-F2：`_query_hash()` 对 plural 标签做 canonical compatibility 编码；空数组忽略、singleton 映射回旧 singular key、multi-value 保留 plural
   → 不修改 `ContentCursorCodec.decode()` 的 query-hash 等值校验，不降低 Cursor 绑定
   → 新增 Session/Route 最终态、List/Count/query Export、旧 hash/v1 Cursor 与不同查询拒绝复用回归。

7. **R655-F1b consolidated review-correction batch**
   → legacy Route/Session 恢复时记录显式 compatibility state，不把 cross-parent 或 catalog-missing 误判为新 UI 非法状态
   → secondary-only 且目录可完整解析时继续无损迁移到当前父子层级；cross-parent/catalog-missing 则保留原 primary/secondary 数组，因此 List/Count/query Export 继续使用旧 AND 语义
   → Filter UI 明示当前“旧版兼容筛选”和实际 primary/secondary 条件；用户主动改动标签并查询后清除 compatibility state，回到当前父子规则
   → `ContentFilterSnapshot` singular 合并 plural 后再次校验最终 100/200 上限
   → 新增 cross-parent Session/Route、catalog-missing、主动退出兼容态和 post-normalization cardinality Regression。

8. **R655-F1c Repair Verify**
   → legacy `primary=[] + secondary=[S]` 从恢复开始一直保持 secondary-only 与 compatibility marker
   → `catalog_status=building` 只知道 `P1/S`、后续 `ready` 新增 `P2/S` 时均不得自动补 primary 或退出 compatibility
   → List / Count / query-scope Export / Session 始终消费原 secondary-only snapshot
   → 只有用户主动修改标签草稿并提交查询时清除 compatibility，再按当前父子规则 sanitize
   → 只修改 Voice Plaza Store 与对应 Unit/Browser Regression，不触碰已闭环 Cursor、Contract cardinality、SQL、generated client 和其它筛选。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 Contract additive 而非 rename/delete | E2–E4 | 避免破坏旧 URL、历史快照和潜在调用方 |
| D2 两个标签维度独立过滤 | E1 | 与工作台既有业务语义一致 |
| D3 Store 清理而非仅 UI 隐藏 | #652 / AC5、E6 | 防止失效二级仍隐藏参与请求 |
| D4 projection/fallback 同时改 | E5 | 防止读模型状态切换时查询结果漂移 |
| D5 tertiary 展开参与布局 | E8 | 切断遮挡查询按钮的真实交互根因 |
| D6 legacy secondary-only 始终保留原查询直到用户主动修改 | E9,E13 | Filter Options 可能处于 building 子集，任何自动补父级都可能收窄旧查询；因此 compatibility state 不受目录阶段改写，只有用户提交新的标签选择后退出 |
| D7 query hash 使用兼容 canonical payload | E10 | 空 plural 不进入旧查询身份；singleton plural 回写旧 singular key；真正 multi-value 才使用 plural key，因此保持旧 Cursor 有效且不削弱不同查询隔离 |
| D8 所有 legacy Route/Session 标签组合使用显式 compatibility state | E11,E13 | secondary-only、cross-parent、catalog-missing 都保持恢复时的原 primary/secondary 查询事实并在页面提示；动态目录只服务当前新 UI，用户主动改标签并提交后才退出兼容态 |
| D9 plural/singular normalization 后重复校验 cardinality | E12 | 保持 OpenAPI 既有 100/200 上限事实，同时堵住 legacy append 绕过上限的 Contract 漏洞 |

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 工作台一级/二级标签均支持多选 | #652 / AC1 | satisfied | 既有数组 Store/Contract 保留；`WorkbenchFilters.vue` 二级继续使用 `WorkbenchMultiSelect`，Browser 验证多父级选择。 |
| R2 | 声音广场一级/二级标签均支持多选 | #652 / AC2 | satisfied | `VoicePlazaFilters.vue` plural checkbox 多选；Unit + Browser 通过。 |
| R3 | 未选择一级时二级不可选并提示 | #652 / AC3 | satisfied | 两页均禁用二级入口；Browser 验证提示与 disabled/aria-disabled。 |
| R4 | 二级候选只来自所选一级标签并取并集 | #652 / AC4 | satisfied | 两页均按 selected primary 过滤 Taxonomy；Unit + Browser 验证未选父级子项不可见。 |
| R5 | 取消一级后清理失效二级，不允许隐藏条件继续查询 | #652 / AC5 | satisfied | 两个 Store 均清理；Voice Plaza Browser 最终请求只含剩余合法 secondary。 |
| R6 | 同维度 OR、一级与二级维度 AND，保持工作台一致 | #652 / AC6 | satisfied | Workbench SQL 与 Content projection/fallback 已复核；PG cross-pair 回归通过。 |
| R7 | List/Count/query-scope Analysis/query-scope Export 共用多选 Filter Snapshot | #652 / AC7 | satisfied | Voice Plaza `filterSnapshot()` 供 List/Count/query export；后端 `ContentTargetSelection.filters` 同时供 Analysis/Reporting freeze。 |
| R8 | projection 与 fallback PostgreSQL 路径一致 | #652 / AC8 | satisfied | PG 测试先走 ready projection，再置 pending 走 fallback；cross-pair 结果一致。 |
| R9 | plural Contract + legacy singular 兼容 | #652 / AC9 | satisfied | API repeated plural + legacy singular 归一化；R655-F1b/F1c 要求所有 legacy Session/Route 标签状态保持恢复时查询事实直到用户主动修改，覆盖 secondary-only building→ready、cross-parent 与 catalog-missing；归一化后 100/200 上限与 R655-F2 Cursor 兼容保持不变。 |
| R10 | Workbench 多标签深链与 legacy singular 深链兼容 | #652 / AC10 | satisfied | Workbench 输出 repeated plural；Voice Plaza 优先 plural、回退 singular；legacy singular 一律保留原标签维度语义与 compatibility marker，R655-F1c 专项覆盖 secondary-only 在 building→ready 目录生命周期中不被自动补 primary，用户主动修改后才进入当前层级规则。 |
| R11 | 分层验证与 generated drift/compatibility 通过 | #652 / AC11 | satisfied | Temporary Validation run 36433340226：Backend、PostgreSQL、Frontend 三 Job success。 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `contracts/http.py` | plural + singular compatibility | 公共筛选表达能力 | R7–R9 / E2–E4 |
| `content_queries.py` | projection/fallback 多值过滤 | 统一服务端语义 | R6–R8 / E1,E5 |
| Voice Plaza Store/Page/Filters | 数组状态、父子清理、多选与深链 | 用户可见主入口 | R2–R5,R7,R10 |
| Workbench Store/Filters/Page | 父子候选、清理与 plural 深链 | 两页一致 | R1,R3–R6,R10 |
| OpenAPI/generated client | 正式重新生成 | Contract 单一事实 | R9,R11 |
| Unit/API/PG/Browser tests | 覆盖状态、Contract、双读路径和用户工作流 | 防止语义投影遗漏 | R1–R11 |
| 产品能力文档 | 同步当前层级多选行为 | 用户行为事实变化 | R1–R6 |

执行状态：

- [x] 调查当前实现和事实源
- [x] 建立验证矩阵
- [x] 行为变化建立回归证据
- [x] 完成最小实现
- [x] 同步长期产品事实
- [x] 取得覆盖当前实现的专项验证
- [x] 完成需求追溯与两阶段复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 原实现 Voice Plaza + Workbench 2 files / 51 tests；首轮 Repair Voice Plaza 36 tests；F1b Repair Voice Plaza 38 tests passed |
| 接口 / 契约 | required | 首轮 Repair Cursor + Stage8D API 18 passed；F1b Stage8D API 13 passed，覆盖 normalization 最终 cardinality；generator/Orval diff clean、`--check`、compatibility 通过 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 18.4 + Alembic head/check；目标集成覆盖 projection/fallback |
| 用户 / 工作流验收 | required | 原两页 Browser Mock 37 passed；首轮 Repair Voice Plaza Browser 16 passed；F1b Repair Voice Plaza Browser 18 passed，覆盖 cross-parent/catalog-missing singular 深链与兼容提示 |
| 跨组件关键路径 | required | Workbench deep link → Voice Plaza plural restore；Filter Snapshot → PG Read Model |
| 外部依赖 / 供应方探测 | not_applicable | 不涉及第三方 Provider 当前事实 |
| 构建 / 打包 / 运行 | required | Frontend lint/typecheck/Vite build；Backend mypy/Ruff |
| 文档 / 治理 / 其他 | required | Product docs、generated assets、Change/PR gates |

## 验证计划

- 目标测试：两页标签状态 Unit、Stage8D Content API、真实 PG label filter。
- 相关回归：Voice Plaza/Workbench Browser Mock。
- 静态检查或构建：Ruff、mypy、frontend lint/typecheck/build。
- 专项真实边界：PG 18.4 projection ready/fallback pending；OpenAPI/Orval generated drift/compatibility。
- 就绪检查：PR CI 的 Requirement Traceability / Change Completion / docs / secret / architecture 等现有门禁。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 父级取消但子级隐藏残留；projection/fallback 语义漂移；展开菜单遮挡操作 | Store 清理 + 双路径 PG 回归 + Browser 布局回归 |
| 兼容性 | additive Contract；legacy singular HTTP/route/session/snapshot 保留 | R9–R10 |
| 数据 / Migration | 不适用 | 无 Schema 变化，旧 JSON 通过 Pydantic 恢复 |
| 部署 / 运行 | 不适用 | 无配置、进程、依赖或部署步骤变化 |
| 回滚 / 恢复 | 可直接回滚本 PR | 无不可逆数据行为 |

# 文档、依赖、部署与发布影响

- **长期文档**：已同步 `docs/product/02_当前产品能力与用户流程.md` 的两页标签筛选当前行为。
- **依赖 / Runtime**：不适用；没有新增、删除或升级依赖，也没有新增 Runtime 进程。
- **配置 / Secret**：不适用；没有新配置或密钥。
- **部署 / Release**：不适用；本任务不执行 Release/Deploy，也不需要 Migration 顺序。
- **兼容 / 消费方通知**：公共 HTTP Contract 为 additive；新版前端发送 plural，旧 singular 消费方仍可继续使用。

# 完成审计

- [x] upstream_re_read：已重读 #652 最新 AC 与用户“只提交 PR、不合并 main”的后续指令，并重读 Workbench SQL、Content Filter Contract、Analysis/Export query-scope 冻结链和最终前端状态链。
- [x] change_coverage：AC1–AC11 均映射到实现与新鲜测试；没有用 UI 多选替代后端 Contract、Count、freeze target 或 fallback 语义。
- [x] reverse_audit：从用户勾选/取消一级 → 二级候选/清理 → applied snapshot → List/Count → Analysis/Export freeze → projection/fallback 反查；从 Workbench → Voice Plaza plural/legacy deep link 反查恢复。
- [x] unresolved_cleared：实现范围内无 `not_satisfied`；首轮 R655-F1/R655-F2 已关闭；delta re-review 的同根 FIRST_REVIEW_ESCAPE R655-F1b 与邻接 cardinality 边界已作为统一 Repair Batch 修复并取得直接回归证据；此前展开菜单遮挡查询按钮也已由 Browser 复验。merge/main-fresh/archive/cleanup 因用户明确限定“只提交 PR”而不属于本任务交付范围。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | run 36433340226 / Ubuntu 24.04 / Python 3.14.7 | Ruff format/check + mypy + Stage8D API | Ruff green；mypy 413 source files；11 passed | Backend/Contract API 静态与行为正确 |
| V2 | run 36433340226 / PostgreSQL 18.4 | Alembic upgrade/check + PG target integration | 1 passed, 8 deselected | plural/cross-pair、projection/fallback 一致 |
| V3 | run 36433340226 / Node 24.19.0 | Contract generator + Orval + diff + check + compatibility | success | generated assets 与 Pydantic 一致且兼容检查通过 |
| V4 | run 36433340226 / Frontend | lint + two target Unit + build | 2 files / 51 tests；build success | 两页状态与正式构建通过 |
| V5 | run 36433340226 / Chromium Browser Mock | Voice Plaza + Workbench E2E | 37 passed | 用户多选、父子联动、请求、深链、布局无回退 |
| V6 | final diff review | main...feature compare + source re-read | behind 0；20 正式文件；临时 Workflow 已删除 | 无临时验证资产或 main 漂移混入 |
| V7 | Repair run 36448358583 / Ubuntu 24.04 / Python 3.14.7 / Node 24.19.0 | Ruff + `tests/unit/content/test_content_cursor.py` + `tests/api/test_stage8d_contents.py` | 18 passed；Ruff green | R655-F2 旧 query-hash/v1 Cursor 兼容及 Content API 邻近回归 |
| V8 | Repair run 36448358583 / Frontend | Voice Plaza Unit + lint + build | 1 file / 36 tests passed；build success | R655-F1 legacy Session 迁移后 List/Count/query Export 最终快照等价 |
| V9 | Repair run 36448358583 / Chromium Browser Mock | Voice Plaza E2E | 16 passed | R655-F1 legacy secondary-only URL 等待真实 filter options 后最终请求与 Session 不被放宽 |
| V10 | Repair run 36448358583 | Contract generator + Orval + generated diff + compatibility | success | Repair 未造成 Contract/generated drift；F2 只修查询身份 canonicalization |
| V11 | PostgreSQL | Repair 未触碰 `content_queries.py`、Schema 或 SQL；此前 current-head predecessor 的 PG Integration 已 success | reusable per Fresh Evidence Contract until affected boundary changes | R655-F1/F2 修复不改变持久化查询语义；最终 PR CI 若 changed-scope 重跑 PG，以 current-head 结果为准 |
| V12 | F1b Repair run 36500100933 / Ubuntu 24.04 / Python 3.14.7 | Ruff + Stage8D Content API | 13 passed；Ruff green | singular+plural normalization 后 100/200 最终上限、重复同值不伪溢出 |
| V13 | F1b Repair run 36500100933 / Node 24.19.0 | Voice Plaza Unit + lint + build | 1 file / 38 tests passed；build success | cross-parent Session、catalog-missing、List/Count/query Export、用户主动改标签退出 compatibility state |
| V14 | F1b Repair run 36500100933 / Chromium Browser Mock | Voice Plaza E2E | 18 passed | cross-parent/catalog-missing singular Route 在动态目录完成后不静默放宽，并明确展示旧版兼容筛选 |
| V15 | F1b Repair run 36500100933 | Contract generator + Orval + generated diff + compatibility | success | validator 收口未改变 OpenAPI/generated Schema，Contract 生成物无 drift |

## 未验证内容与剩余风险

- F1b Repair Batch 已取得 targeted green；临时 Workflow 已删除。更新本 Change 后仍需等待 PR 最终 current-head required CI，CI 未完成前不请求“可合并”结论。
- 未执行真实 Release、Deploy 或生产数据操作；本任务不需要也未获授权。
- 不做线上生产量性能声明；本次没有改变标签目录规模上限，也未新增逐行 SQL/额外 HTTP 往返。

## 交付状态

- 提交：任务分支已提交并推送。
- 拉取请求：#655，open。
- CI：F1b targeted 已绿色；最终 current-head required CI 待本 Change 更新后的 head 执行完成。
- 合并：未授权，不执行。
- Change 归档：不执行；只有未来 merge 后且再次授权才进入。
- 发布 / 部署：不适用，本任务无 Release/Deploy。

## 备注

用户最新交付指令优先：只提交 PR，不合并主分支。
