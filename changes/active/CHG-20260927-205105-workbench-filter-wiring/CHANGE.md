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

# 目标与现状

Issue #634：工作台三个模块已有真实后端接口及 PostgreSQL 筛选查询，但声音流内的多选面板被横向滚动容器裁切；日期范围分两次写入父级筛选快照，可能丢失首次写入并形成 `date_from > date_to` 的 422 请求。声音流静止且只截取前六条，平台标识与声音广场不一致；页面写着“自动刷新”却只在初次进入、筛选和 Analysis Run 变化时请求。进一步核查发现工作台空库首次请求会回滚 Scheme bootstrap；Excel 作者名来自当前 Content Version 快照，工作台只读 Account 名会漏掉无稳定账号的导入作者；带来源的声音广场深链叠加历史会话筛选，可能隐藏刚入库内容；三个并发模块目前等最慢请求返回才一起更新。Data Import 运行期的前端只轮询 Campaign 汇总而不更新来源项；更关键的是 Campaign 持久统计按设计只在任务终态从逐行账本汇总，已提交 Chunk 的统计在运行期仍返回零。用户要求三模块及时展示真实结果，Figma 滚动与折线、作者与声音广场一致、点击笔记打开对应详情、导入中统计及处理结果实时更新，并完成测试、Review、CI、合并。

# 范围与不变项

- 修复声音流的多选弹层显示和键盘/关闭行为，并保留横向滚动的窄卡片布局。
- 日期确认时一次性写入有序起止日期，三个工作台模块收到同一筛选快照；筛选和重置均触发真实接口刷新。
- 声音流用 Figma 双轨循环结构播放当前真实列表，悬停、聚焦、标签页隐藏和减少动画时暂停；平台标识与声音广场共用组件。
- 趋势折线保持后端按日数据语义，按 Figma 调整线条、渐变、网格、悬停点与提示。
- 用户确认筛选后及时发请求；可见页面按现有任务中心的 15 秒频率补读已入库事实，恢复可见时立即补读，避免慢请求叠加。
- 三模块各自返回即更新，同时保留 Scheme 身份一致性；空库首次读取须持久化唯一 active Scheme。
- 声音流作者优先使用当前内容版本的作者快照；无值时显示“未知作者”。笔记跳转使用 Content ID 直接打开声音广场详情，不依赖列表分页。
- 带明确目标的声音广场深链先清除会话旧筛选，保证来源/日期/内容定位不被隐式条件遮挡；Excel 成功状态与投影在同一事务提交的现有不变量用真实 PostgreSQL 复核。
- 保持现有前台导入优先屏障、后台动态并发槽与 Worker 优先级；本次不改处理资源配额或调度策略。
- 采集运行中心的 Data Import 弹窗在运行期同步统计和已结算来源项；Campaign 详情与运行列表仅对当前可见记录按已提交 Chunk 摘要聚合实时统计，不写父 Campaign 热行，也不在每次轮询扫描逐行账本。任务终态仍使用既有精确账本结算。
- 品牌/车型解析先按正文命中品牌，再只接受这些品牌旗下车型；无品牌命中时才由车型全局匹配并回推品牌。英文短别名按完整 ASCII 词边界匹配，避免 `O` 命中 `model` 等英文单词。
- 保持 active Taxonomy、品牌车型目录、布局编辑、声音广场深链及现有生成 Client/后端 Contract 不变。
- 不变更 Schema、Migration、依赖、部署或生产数据。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 声音流筛选项可点击并能看到可选项 | #634 / AC1 | satisfied | Browser 测试确认弹层位于顶层、选项可点击。 |
| R2 | 日期确认后起止日期完整且有序地进入三个模块查询，反向选日不再触发 422 | #634 / AC2 | satisfied | Browser 正反向日期请求、Store 单元测试、后端 Query 校验。 |
| R3 | 多选、重置和三模块呈现与当前 PostgreSQL 筛选口径保持一致 | #634 / AC3 | satisfied | Browser 三模块筛选/空态/重置、API 参数转发、PostgreSQL 集成筛选。 |
| R4 | 声音流按 Figma 连续向上滚动，悬停或聚焦暂停，并使用声音广场平台标识 | #634 / AC4 | satisfied | Browser 长短列表滚动、暂停和共享标识断言。 |
| R5 | 折线图按 Figma 的平滑粉线、渐变面积、点状网格与悬停提示呈现，值仍来自后端 | #634 / AC5 | satisfied | Design Context 对照、ECharts 配置复核与浏览器真实 daily 响应渲染。 |
| R6 | 筛选确认后及时显示新数据，可见页持续检查新入库结果 | #634 / AC6 | satisfied | 日期直接请求、选项 100ms 合并、15 秒轮询 Browser 测试。 |
| R7 | 慢模块不拖住已返回模块；正确筛选与空库首次读取不产生口径漂移错误 | #634 / AC7 | satisfied | Store 延迟请求回归；独立数据库三接口并发 bootstrap 测试。 |
| R8 | Excel 单文件导入完成后，已提交内容可在声音广场立即查询，来源深链不继承旧筛选 | #634 / AC8 | satisfied | Import Worker PostgreSQL 测试同提交投影；Browser 旧筛选深链请求回归。实际已部署环境时延待环境证据复核。 |
| R9 | 声音流显示真实作者，与声音广场同源；点击笔记可定位对应详情 | #634 / AC9 | satisfied | Excel 真实入库作者快照集成测试；Workbench → Voice Plaza Browser 深链及跨分页详情测试。 |
| R10 | 日期反向、取消、单日、清空均有一致的显示与请求口径 | #634 / AC10 | satisfied | Browser 日期生命周期回归；空日期恢复默认近 30 天。 |
| R11 | 尽可能快地展示已入库数据，保持其它处理吞吐与动态前台优先机制 | #634 / AC11 | satisfied | 三模块独立响应；前台优先屏障、后台槽与 Job Priority 现有实现/测试复核，不增加常态数据库轮询频率。 |
| R12 | 采集运行中心导入期间持续更新处理统计和数据处理结果 | #634 / AC12 | satisfied | PostgreSQL 分段导入中 Campaign 详情、来源项与统一运行列表 API 均返回已提交 Chunk 统计；运行期 5 秒轮询同步两者，Store 与 Browser 回归。 |
| R13 | 品牌命中后只匹配该品牌车型；没有品牌时才由车型回推品牌；英文短别名不命中更长英文词；历史重筛沿用同一规则 | #634 / AC13 | satisfied | Resolver 单元回归覆盖同品牌、跨品牌、车型回退及 `O` 正反边界；PostgreSQL 重分类 Worker 回归确认历史内容按同一规则重写 Evidence。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 工作台 Store、共享日期组件及 Brand/Vehicle Resolver 品牌优先与英文词边界回归。 |
| 接口 / Contract | required | 核对生成参数与现有 WorkbenchQuery，不修改公共 Contract；空库首次读取 Scheme 提交。 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 18 + Alembic head 上运行筛选维度、Excel 入库后投影/作者、空库并发 Scheme。 |
| 用户 / Workflow Acceptance | required | Browser Mock 从点击、选择、确认到三个 HTTP 请求参数、旧筛选来源深链、笔记定位。 |
| 跨组件 Golden Path | required | 验证工作台三个 generated-client 请求共用同一筛选参数；如可运行，执行现有 fullstack 关键链。 |
| External Dependency / Provider Probe | not_applicable | 不改 TikHub/LLM 外部调用。 |
| Build / Package / Runtime | required | 前端 lint、typecheck、build。 |
| Docs / Governance | required | 产品文档现有口径核对，Change Completion 检查。 |

# 实施步骤

1. 用 Browser 测试复现弹层裁切与日期丢失，确认真实后端 Contract 和 Figma 结构。
2. 修复筛选、日期、独立刷新、空库 Scheme 提交、流滚动、真实作者与图表；复用声音广场平台标识。
3. 验证 Excel 成功与投影的同事务可见性，修复来源深链旧筛选叠加，补齐笔记详情跳转和导入中统计/结果刷新；运行 Browser、Store、API、真实 PostgreSQL 集成及前端质量门禁，更新产品文档。
4. 做独立 Review、Completion Audit、PR Ready 和 CI，按授权合并 main 并核查归档。

# Completion Audit

- [x] upstream_re_read：交付前已重读 Issue #634、产品工作台能力和数据入口品牌/车型语义。
- [x] change_coverage：R1-R13 均有实现与验证证据；未把仓库外部署状态写成已验证。
- [x] reverse_audit：已核对筛选/日期/深链/轮询到真实 API，也核对 Workbench、导入投影、运行统计和 Resolver 后端能力均有前端入口或明确不适用边界。
- [x] unresolved_cleared：required 本地验证全部通过，独立 Review 无未解决 finding；合并仍以当前提交 GitHub CI 通过为门禁。

# 交付状态

实现与本地 Review 已完成，PR #635 已可进入当前提交 CI。未修改公共 Contract、生成 Client、Schema、Migration、依赖、部署配置或生产数据；未调用 TikHub/LLM。用户暂不能提供实际部署环境，因此“部署后端到端时延”未伪造为已验证，仓库内用真实 PostgreSQL 证明 Import/投影同事务提交后立即可查询。

## 新鲜验证证据

- `uv run pytest tests/api/test_workbench.py tests/unit/test_brand_vehicle_resolver.py tests/integration/content/test_workbench_runtime.py tests/integration/content/test_workbench_scheme_bootstrap.py tests/integration/ingestion/test_stage8b_import_http_worker.py tests/integration/ingestion/test_stage12_historical_campaign_worker.py tests/integration/collection/test_stage8e_collection_http_runtime.py tests/integration/vehicles/test_content_reclassification_postgres.py -q`：111 passed。
- `uv run ruff check ...`（本次全部 Python 生产与测试文件）：通过。
- `npm run test -- --run tests/workbench.spec.ts tests/collection-runtime.spec.ts tests/voice-plaza.spec.ts`：3 files / 51 tests passed。
- `npm run test:e2e -- e2e/workbench.spec.ts e2e/voice-plaza.spec.ts e2e/historical-migration.spec.ts`：36 passed。
- `npm run lint`、`npm run typecheck`：通过。
- `npm run build`：通过，835 modules transformed；仅保留仓库既有大 Chunk 提示。
- `git diff --check`：通过；Windows 工作区仅报告 Git 的 LF/CRLF 提示，无 whitespace error。

## Review 结论

- 已修复 Review 中发现的三项问题：面板内部滚动不应关闭 Popover；声音流视觉副本不应重复暴露可交互语义；已有成功快照时错误提示应紧凑展示且继续显示真实结果。
- Scheme 首次 bootstrap 由 PostgreSQL advisory lock 串行化并在 HTTP 成功响应前提交；三模块仍校验 Scheme/Taxonomy 身份，未引入混合口径。
- 运行中 Campaign 统计只聚合当前可见活动 Campaign 的已提交 Chunk 摘要；不扫描逐行账本、不写父 Campaign 热行，终态继续使用既有精确结算。
- 品牌优先、车型回退与 ASCII 边界由同一 Resolver 承载，Excel、历史导入与历史重分类继续复用该生产实现。
