---
schema: coding-change/v1
id: CHG-20260928-141055-workbench-live-aggregation
title: 工作台全量声音流、聚合提速与用户心智图
level: L3
status: in_progress
owner: dingyuwen777
branch: fix/644-workbench-live-aggregation
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - backend
  - frontend
  - workbench
  - content
  - jobs
  - database
  - performance
  - documentation
affected_paths:
  - backend/src/aima_ugc/contracts/workbench.py
  - backend/src/aima_ugc/adapters/persistence/postgres/workbench.py
  - backend/src/aima_ugc/bootstrap/workbench_http.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/modules/workbench/
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/
  - frontend/src/features/workbench/
  - frontend/src/shared/
  - frontend/tests/
  - frontend/e2e/
  - tests/integration/content/
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/04_后端任务API与前端.md
contracts:
  - WorkbenchStreamQuery
  - WorkbenchStreamResponse
  - WorkbenchMindResponse
  - WorkbenchTrendResponse
data_changes:
  - 新增可重建的工作台聚合派生结果与刷新状态，不修改 canonical 内容事实
---

# 变更摘要

- **要解决的问题**：声音流只循环最新 30 条；品牌用户心智与趋势在约 921 万条生产数据上首次加载慢且偶发失败；用户心智展示、日均取整和成功提示生命周期不符合已确认体验。
- **实际目标**：声音流用稳定游标遍历筛选范围全部内容；聚合使用可失效、可追溯的持久派生结果并异步刷新；用户心智改为动态 N 边雷达图；普通成功/信息确认统一 3 秒消失。
- **交付边界**：Issue #644 的 AC1–AC9、Contract/Schema/Migration/Job/前后端/文档、分层测试、Review、CI、受保护合并、main-fresh、Issue 回写与清理。

# 背景、现状与问题

## 已确认事实

- `PostgresWorkbenchRepository.stream_rows()` 固定 `limit=30`，SQL 使用 `LIMIT :limit`；前端复制相同 `items` 并对首轮高度取模，因此只循环同一批数据。
- 声音流时间格式只输出月/日；平台图标已经复用共享 `AimaPlatformMark`。
- Trend/Mind 虽已合并为各自单条 SQL，但每次请求、15 秒补读与筛选变化仍同步扫描当前和上期明细、恢复 active Scheme 与人工事实。
- 既有 20,000 行隔离 PostgreSQL 暖态基准约为 Trend 68.57ms、Mind 108.58ms；该证据不能代表用户约 9,218,681 条生产数据。用户已观察到首次等待和间歇失败。
- Brand Mind 左侧仍为条形排行；active Taxonomy 已提供全部一级标签，现有响应已提供每个一级标签的用户占比、正向率和变化。
- Workbench Store 的布局成功提示没有清除定时器；其它页面同时存在永久提示和 2.6/2.8 秒局部实现。

## 根因与机制

1. 声音流不完整是服务端硬限制与客户端重复同一页共同造成，增加视觉副本不会增加数据覆盖。
2. 聚合慢与偶发失败是重型明细计算仍位于同步 HTTP 热路径造成；仅继续提高超时、隐藏错误或增加轮询会放大数据库争用。
3. 普通提示长期存在是各 Feature 各自维护字符串/计时器，没有共享生命周期语义。
4. 雷达图必须按容器尺寸重算并让数据节点与 DOM 详情解耦，否则自由缩放时会再次重叠。

## 暂时无法验证

- 无法访问用户生产服务器，因此不能在仓库内声明 9,218,681 条数据的真实线上毫秒数、部署 revision、连接池、查询计划或 I/O 状态。
- 生产部署、Migration 和 Worker 运行由后续正式 Release/Deploy 执行；本 Change 负责源码、迁移资产、回滚边界和仓库可重复证据。

# 目标、成功标准与非目标

## 目标

- 在有界 HTTP 响应和浏览器内存内遍历声音流全部匹配数据，保持向上滚动与暂停语义。
- 把重复重型聚合移出 Workbench 同步热路径，以持久最近成功结果提供快速读取，并由幂等 Job 刷新、记录来源与失败状态。
- 按参考样式交付动态用户心智图，并保持筛选、active Taxonomy、选中详情和自由缩放正确。
- 用一个共享 composable 管理普通瞬时提示，默认 3 秒自动清除。

## 成功标准

- [ ] Issue #644 / AC1–AC8 全部有实现与新鲜分层证据。
- [ ] Completion Audit 无 `not_satisfied`，两阶段 Review 无未解决高风险 Finding。
- [ ] PR current-head CI、受保护合并、main-fresh CI、Change 归档和 Issue AC 回写完成。

## 非目标

- 不一次性向浏览器发送或保存数百万条声音。
- 不引入 Redis、Kafka、WebSocket、微服务或新数据库。
- 不改变 active Taxonomy、AI Prompt、人工复核/覆盖和北京时间统计语义。
- 不把错误、持续进度和可操作警告统一自动隐藏。
- 不升级依赖或重构无关模块。

## 必须保持不变

- PostgreSQL 是唯一业务事实库；派生结果可重建且不得成为第二套 canonical 事实。
- 三个工作台模块继续独立请求、独立加载/失败/重试，并校验相同 Scheme/Taxonomy 身份。
- 所有现有平台、品牌、车型、发声、情感、一级/二级标签筛选及日期边界保持精确。
- 现有布局 Contract、自由缩放、声音流平台图标和深链保持兼容。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 全量声音流 | 稳定签名 keyset cursor + 有限 page；前端在滚动周期边界替换下一页，到末页后从第一页重启 | 不能用无限 response/offset 假装全量 | 完整遍历且内存有界 |
| 聚合读取 | 精确规范化筛选键对应一个持久最近成功 snapshot；HTTP 只读取 snapshot、判断陈旧并幂等 enqueue 刷新 | 重计算必须离开 15 秒 HTTP 热路径 | 热读快，刷新失败仍保留成功结果 |
| 首次结果 | Worker 启动保证默认筛选 snapshot Job；未命中筛选立即 enqueue，若无成功结果返回明确 preparing 状态 | Migration 不执行无界回填 | 首次冷筛选仍需一次后台计算，状态真实 |
| 新鲜度 | 投影变更维护单调数据 revision；snapshot 记录 source revision；旧 revision 可返回为 stale/refreshing 并自动刷新 | 禁止静默把旧数据称为当前 | API/页面可观察 freshness |
| Radar | ECharts 动态 `indicator` + ResizeObserver；DOM 详情/选中卡片复用现有选择状态 | 已有 ECharts，无需新依赖 | N 边、响应式、真实数据 |
| 提示 | `useTransientNotice` 默认 3000ms；错误/警告/进度继续单独持久状态 | 统一普通成功生命周期 | 避免误隐藏可操作状态 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 计划证据 |
| --- | --- | --- | --- | --- |
| R1 | 声音流遍历筛选期内全部数据并持续滚动 | #644 / AC1 | not_satisfied | Contract、PostgreSQL 多页、Store/Browser |
| R2 | 发帖时间显示时分且平台标记一致 | #644 / AC2 | not_satisfied | 组件 Unit/Browser |
| R3 | 相同筛选热读不重复扫描明细，聚合持久/幂等/可失效 | #644 / AC3 | not_satisfied | Schema、Job、SQL statement count、benchmark |
| R4 | 失败保留最近成功结果并暴露真实刷新状态 | #644 / AC4 | not_satisfied | PostgreSQL failure、API、Store/Browser |
| R5 | active Taxonomy 驱动动态 N 边用户心智图并匹配参考样式 | #644 / AC5 | not_satisfied | Component/Browser/视觉截图 |
| R6 | UGC 日均声量四舍五入为整数 | #644 / AC6 | not_satisfied | Unit/Browser |
| R7 | 普通成功/信息提示共享 3 秒生命周期，错误/进度/警告保留 | #644 / AC7 | not_satisfied | composable fake timer + 页面回归 |
| R8 | Contract/Schema/Client/Job/Docs 与依赖边界同步 | #644 / AC8 | not_satisfied | generation/migration/docs/quality gates |
| R9 | 分层验证、Review、CI、合并和收尾 | #644 / AC9 | explicitly_deferred | Ready 后按正式顺序执行 |

# 实施步骤

## 步骤 1：Red 证据与 Contract

→ 修改范围：Workbench Contract/API、Repository 集成、前端 Store/组件和瞬时提示测试。
→ 预期结果：旧实现因固定 30 条、无游标/新鲜度、条形 UI、小数日均和永久提示而失败。
→ 验证方式：目标 Pytest/Vitest/Playwright Red 结果。

## 步骤 2：声音流游标与前端滚动

→ 修改范围：签名 cursor、查询 hash、Repository keyset、generated client、Store、SoundStreamCard。
→ 预期结果：每页有界、跨页无遗漏/重复、结束重启、筛选重置、时分显示。
→ 验证方式：Contract + PostgreSQL + Unit/Browser。

## 步骤 3：聚合派生 snapshot

→ 修改范围：表/迁移、数据 revision、Job payload/handler/executor、HTTP 读取/enqueue、Worker 注册。
→ 预期结果：HTTP 热读只访问 snapshot；陈旧/失败保留最近成功并后台幂等刷新；默认 snapshot 自动准备。
→ 验证方式：Migration upgrade/downgrade、Job fencing/幂等、PostgreSQL 对账/失败、statement count、基准。

## 步骤 4：用户心智图、日均取整与提示治理

→ 修改范围：BrandMindCard、UgcTrendCard、共享 composable、存在普通成功 notice 的页面。
→ 预期结果：动态 N 边参考样式；整数日均；普通提示 3 秒清除且持久状态不受影响。
→ 验证方式：fake timer、组件、Browser、窄/宽容器截图与溢出断言。

## 步骤 5：文档、审计与交付

→ 修改范围：产品/Blueprint/Operations、Change、Issue/PR。
→ 预期结果：公共行为、派生事实、部署顺序、回滚和证据完整。
→ 验证方式：Contract/Docs/Change quality、Deep Review、CI、main-fresh。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 理由 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Cursor、Store 页面代次、Radar、timer |
| 接口 / 契约 | required | 新 query/response、生成 Client、兼容第一页 |
| 集成 / 持久化 | required | PostgreSQL 分页、snapshot、revision、Job、Migration |
| 用户 / 工作流 | required | 自动滚动/暂停/换页、筛选、加载/失败、自由缩放 |
| 跨组件关键路径 | required | Browser → generated client → API → snapshot/Job → PostgreSQL |
| 外部 Provider | not_applicable | 不改 TikHub/LLM，不使用付费 Probe |
| 性能 | required | 热读不扫描明细；代表性基准和执行计划 |
| 构建 / 打包 | required | Ruff/Mypy/Pytest、lint/typecheck/build/E2E |
| 文档 / 治理 | required | OpenAPI/Schema/Docs/Change/CI/Issue |

# 风险、兼容、迁移与回滚

- **游标风险**：签名必须绑定完整筛选和 page limit；使用 `(published_at, content_id)` 严格 keyset 并固定 UTC/北京时间边界。
- **陈旧风险**：响应显式包含状态、source revision、computed_at；UI 只有 freshness 为 fresh 才称为已同步。
- **刷新风暴**：Job 使用 `(module, query_hash, requested_revision)` 持久幂等键；同一 revision 只存在一个有效刷新。
- **Schema/Migration**：只创建可重建表、索引、revision/dirty 机制；不在 Alembic 做大数据回填。
- **部署**：Migration → Worker → API → Frontend；Worker 首次准备默认 snapshot。
- **回滚**：回滚应用 revision；新增表保留不影响旧代码/canonical 事实；若必须删除使用后续 migration，不执行生产手工 SQL。

# 文档与交付影响

- Targeted 更新产品工作台行为、Blueprint 的派生读模型/Job/失败语义和 Operations 的迁移顺序。
- 不新增或升级依赖，不新增 Secret/Provider 配置，不执行本任务外的 Release/Deploy。

# 完成审计

- [ ] upstream_re_read：Ready 前重读 Issue #644、用户雷达图参考、正式产品/Blueprint 和当前 Contract。
- [ ] change_coverage：R1–R8 无遗漏，R9 只保留顺序上必须后置的交付动作。
- [ ] reverse_audit：从前端入口反查后端真实能力，并从新 Contract/Schema/Job 反查所有消费者和运行入口。
- [ ] unresolved_cleared：Ready 前 `not_satisfied` 清零；延期/不适用具备正式依据。

# 完成证据与状态

- 当前状态：完成事实调查、Issue #644、本 L3 Change 与 Red 证据；尚未开始生产实现。
- Red（2026-09-28）：`uv run pytest tests/unit/content/test_workbench_contract.py -q` 因缺少 `WorkbenchStreamQuery` 在收集期失败；`npm exec vitest run tests/transient-notice.spec.ts tests/workbench.spec.ts` 因缺少共享 composable 及“用户心智图”断言失败（其余 9 个 Workbench Unit 通过）。
- Review/CI/merge/main-fresh/archive：待实施与分层验证后执行，不提前声明完成。
