---
schema: coding-change/v1
id: CHG-20260908-223421-collection-runtime-figma
title: 采集运行中心 Figma 补齐与增量实施
level: L2
status: done
owner: codex
branch: feature/collection-runtime-figma-20260908
created: 2026-09-08
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - collection
  - ingestion
affected_paths:
  - frontend/src/features/import-batches/
  - frontend/src/shared/ui/AimaDateRange.vue
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/stage12-historical-analysis.spec.ts
  - frontend/README.md
  - docs/product/
contracts: []
data_changes: []
---

# 目标与边界

依据 Issue #391，先补齐采集运行中心关键 Figma 画板，再在现有 Vue 页面和子组件中增量实施；总体页面结构、公共侧栏、视觉层级不变，必要可用性修正同步到 Figma。用户已授权完整交付并在验收通过后合并 main。初始 main 为 87ff0ffad99299843d4ef3c44d2195a3cdd8aeac。

保留现有 Vue/Pinia/Feature API/生成 Client/Contract/持久 Job、所有合法输入和后台行为；无新依赖、公开 Contract、数据库或迁移变化，不部署、不进行真实付费 Provider 调用。用户原有 docs/guides/01_Figma与前端设计开发工作流.md 修改排除在本次提交外。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 补车型、逐平台参数及两种补采来源画板 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC1 | satisfied | 正式表单复用车型与搜索参数组件；5167:31002 为仅车型状态；Browser Mock 验证车型独立/组合、Capability、Campaign/Batch 请求 |
| R2 | 导入详情、冲突明细、现有撤销完整表达 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC2 | satisfied | 既有 Campaign 统计/文件/分段保留；冲突表区分行数与返回字段数；新增六个撤销画板及公共确认框，真实全栈验证冲突和撤销 |
| R3 | 页面和浮层增量对齐 Figma，修正示例与说明 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC3 | satisfied | 主页面/导入/补采/结果/确认截图对照，修正已完成进度、问题记录和开发说明；日期按用户补充决定共用声音广场组件 |
| R4 | 多尺寸表格和弹层操作可达 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC4 | satisfied | 1180/1280/1440/1920 几何用例及运行探针通过，详情按钮滚动后全部可见；导入 840、补采 510、批次详情 450、确认 480×280 |
| R5 | 筛选确认、类型筛选、轮询分页和请求竞争正确 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC5 | satisfied | Store 9 项回归通过；已应用参数随成功窗口提交，40 条轮询保留，草稿不提交，旧响应不混入新查询 |
| R6 | 保留既有业务与错误恢复，补真实冲突消费 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC6 | satisfied | API/PostgreSQL 25 项、完整真实全栈 12 项通过；生成物无漂移；冲突、撤销和错误都使用既有服务 |
| R7 | 分层本地验证、构建及设计对照 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC7 | satisfied | 本地矩阵全部完成，见下方新鲜证据；正式 CI 独立追溯于 R9，不预报成功 |
| R8 | 双向 Figma 同步及两阶段审查 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC8 | satisfied | Figma 修正及作者/独立复核完成；正式交付收尾独立追溯于 R10 |
| R9 | 当前提交的正式 CI 全部通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC7 | explicitly_deferred | 仅延至首个实现提交推送后执行；依据 AGENTS 本地提交→push→CI/Ready→merge 的正式顺序，当前尚无待提交 SHA 的远程运行；合并前必须完成，未获豁免 |
| R10 | 合并后 main 验证、Change 归档、Issue 同步与任务分支清理 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC8 | explicitly_deferred | 仅延至 CI 通过及合并后执行；依据用户完整交付授权与 AGENTS 合并后验证→归档/清理顺序；在实际完成前不得关闭最终交付 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 全量 127 passed，包含 Store 筛选/分页/迟到响应及失败查询回归 |
| 接口 / Contract | required | generate.py --check 与 Orval 再生成通过，generated Client 无语义差异 |
| Backend/API/PostgreSQL | required | 既有导入、撤销和运行中心 API/持久化目标组合 25 passed |
| Browser Mock Acceptance | required | 全量 77 passed，包含车型/参数/来源/详情/冲突/撤销、日期与四种尺寸 |
| Real Full-stack Golden Path | required | 隔离 PostgreSQL + API + Worker + Browser，12 passed；模型使用本地 Fake |
| External Provider Probe | not_applicable | 本次不改变外部 Adapter/请求协议，不需付费调用 |
| Build / Runtime | required | lint、TS7/Vue 类型检查、build 通过；浏览器实际打开并截图 |
| Docs / Governance / Other | required | 产品文档和 Frontend README 定向同步；文档/事实/Secret/架构检查通过，Completion 与正式 CI 作为提交/合并门禁 |

# 实施计划

1. Figma 既有表单/详情公共组件 → 补最小缺口并保持页面外形 → 实例、滚动、状态、截图复核。
2. 既有 Page/Filters/Table/Detail 与 Store → 差异驱动实现与缺陷修复 → Red/Green 回归和 Browser Mock。
3. 真实前后端关键流程与正式构建 → 验证接线和兼容 → 对照 Figma 当前画板。
4. 文档/审查/PR/CI → 同步必要设计差异 → guarded merge 与 main 验证、项目自动归档和收尾。

# 兼容、部署与回滚

只调整已有前端消费者和布局，不改变后端持久化、来源身份或撤销语义。保留 Route、API 与依赖版本。无需数据迁移；回滚本次前端提交恢复旧界面，数据继续由现有服务维护。实际生产部署不属于本次授权范围。

# Completion Audit

- [x] upstream_re_read：2026-09-09 再次读取 Issue #391 的八项 AC 和日期补充决定；直接读取正式 Figma 主页面、只选车型、补采、已完成、确认框和公共组件实例。
- [x] change_coverage：从上游逐项重建要求，覆盖独立/组合车型、逐平台参数、两种来源、结果/文件/冲突/撤销、响应式、分页竞争及产品文案；无静默延期的实现要求。
- [x] reverse_audit：后端既有能力对应前端入口；前端请求继续通过生成 Client；Campaign 冲突字段由 conflicts API 消费；撤销先预览、再固定当前预览确认，成功/失败均回读真实结果；列表→详情→声音广场链路保留。
- [x] unresolved_cleared：实现与本地验证无未解决阻塞项。用户明确统一日期行为，替代旧的两个独立输入；正式 CI 和合并后收尾不能在尚未执行时宣称完成。

# 初始证据与当前状态

2026-09-08 基线只读审查：既有 collection-runtime/data-import-policy Browser Mock 10 passed；四种宽度探针确认 1180/1280 操作裁切；40 条加载后轮询回到 20 条并提交草稿 search。当前 Figma 正式入口 3500:2025，Page 3500:2023；行为说明 4908:22991，响应式说明 4764:8874。

首个提交 dceb7d5b 仅建立追溯与早期 PR。当前实现和本地验证已完成，正式 CI、合并及收尾仍须使用当前提交的新鲜结果。

# 新鲜验证记录

- Red → Green：Store 的页签类型、40→20、草稿被轮询提交、翻页迟到及失败查询污染旧游标先复现后修复；撤销确认框受 Teleport 影响导致 scoped CSS 未生效，280px 高度/右侧按钮断言先失败，再使用专用全局选择器修复。没有删减失败断言或降低预期。
- `npm run test -- --run`：127 passed。最终 `npm run test:e2e`：77 passed（45.9s）。沙箱初次因浏览器 spawn EPERM 未启动，正常主机权限复跑得到上述结果。
- `npm run lint`、`npm run typecheck`、`npm run build`：exit 0，继续使用锁定依赖。构建完成不等于已部署。
- `npm run test:e2e:fullstack`：12 passed，隔离数据库 aima_runtime_figma_recheck；真实 API/Worker/PostgreSQL，LLM 为本机 Fake，不调用真实付费 Provider。首轮 11 passed / 1 failed 源于旧“冲突 1”文案断言，按新字段表保留冲突业务断言并调整为“冲突行数 1”；原生 confirm 监听同步为实际公共确认框。
- 后端目标：test_stage12_historical_imports.py、test_import_campaign_revocation.py、test_import_campaign_revocation_postgres.py、test_stage8e_collection_http_runtime.py，合计 25 passed；62 条既有弃用警告。使用任务隔离库 aima_runtime_figma_integration。
- `scripts/contracts/generate.py --check`、`npm run generate:api` 通过，再生成后 generated Client 无语义差异；`scripts/quality/check_docs.py`、`check_docs_facts.py`、`scan_secrets.py`、`check_architecture.py`、`git diff --check` 通过。
- 补充运行探针在 1180/1280/1440/1920 确认表格详情按钮在局部横向滚动后可达；40 条结果轮询后仍为 40 条，未提交草稿 search。证据在任务本地 `.runtime/runtime-figma-test/probe-result.json`，不包含真实业务数据。
- 最终截图脚本 1 passed，实际检查 main/local/discovery/revoke/confirm；Figma 主页面、仅车型、补采、完成详情和确认框直接渲染复核。动态数据、文件名、进度和字体渲染以运行时为准，不把示例值写成业务事实。

# Figma 复核入口与公共组件

文件： https://www.figma.com/design/EAPm8KVarUe7BFTSnzvOpT 。以下 node-id 可直接定位：

| 用途 | 节点 |
| --- | --- |
| 正式主页面 | 3500:2025 |
| 本地导入 / 关键词包与车型组合 | 3500:2875 |
| 仅选择车型 | 5167:31002 |
| 主动发现 / 逐平台参数 | 3500:4257 |
| 导入完成 / 统计与字段冲突 | 3500:3951 |
| 撤销影响预览 | 5140:7670 |
| 不可撤销 / 已撤销 | 5143:7905 / 5143:8216 |
| 提交中 / 提交失败 | 5144:8367 / 5144:8678 |
| 居中撤销确认 | 5145:8833 |

日期继续使用公共日期输入 3270:6682 和日历 3270:6817；运行中心实例 4797:6754 与声音广场共用组件，保留各自变量隔离。代码只为 AimaDateRange 增加可选可访问标签，原声音广场默认值不变。新增结果/撤销状态使用既有 PageShell、ModalContainer、按钮与反馈组件；组件区重新排列，避免增高内容重叠。相关确认、取消、重试和评估入口连接到对应状态；画板不是服务器请求执行器，真实请求验证见分层记录。

# 两阶段审查与文件变化

- 需求/设计复核：以 Issue 八项 AC 和用户日期决定重新核对 Figma 与真实能力，保留公共外壳、列表和各浮层尺寸；开发说明退出产品主流程，技术 ID/错误保留在折叠详情。
- 独立代码复核：审查者读取 Issue、规则、diff、现有 Contract 和测试，发现失败查询可能污染旧游标的问题后补回归修复；统一日期依据用户决定关闭原独立输入差异。复审结论 NO_FINDINGS_WITHIN_SCOPE。独立审查未重新运行全量测试、未审查 Figma 文件，不能替代本轮作者设计核验和正式 CI。
- `CollectionRuntimePage.vue`：对齐页面标题、列表标题及分页间距，保留原有事件接线。
- `CollectionRuntimeFilters.vue`：复用公共日期组件，保留状态/类型/阶段筛选，宽度自适应。
- `CollectionRuntimeTable.vue`：最小宽度与局部横向滚动，操作列可达。
- `DataImportDialog.vue`：真实字段冲突明细、统计口径、技术折叠、撤销确认与固定预览身份；继续使用现有服务。
- `TikHubSupplementDrawer.vue`：复用 VehicleMultiSelect 与 CollectionSearchConfigFields，整理逐平台参数、来源及产品文案。
- `CollectionRunDetailDrawer.vue`、`ImportBatchDetailDrawer.vue`：遮罩统一至正式设计的 50%。
- `store.ts`：成功查询参数快照、轮询窗口恢复、翻页竞争与类型筛选，保存已返回冲突字段总数。
- `AimaDateRange.vue`：可选 label，保持公共日期行为和旧默认值。
- `collection-runtime.spec.ts`、`collection-runtime-design.spec.ts`、`import-batches-store.spec.ts`：关键行为、布局与失败路径回归。
- `stage12-historical-analysis.spec.ts`：真实全栈使用新的冲突标签与公共撤销确认框，保留原业务断言。
- `frontend/README.md`、`docs/product/02_当前产品能力与用户流程.md`：同步已实现能力和公共日期行为。原有工作流指南修改不在本次提交。

# 交付门禁与未验证边界

PR #392 / Issue #391 / feature/collection-runtime-figma-20260908 → main。R9/R10 的 explicitly_deferred 只表达正式流程的执行先后，不表示减少要求或延期到未来迭代。正式 CI 必须验证当前 head；通过后才执行受 SHA 保护的合并，并验证 main、等待自动归档、同步 Issue 和清理本任务分支。此记录不预报这些动作的结果，实际完成后在 Issue 与交付报告追加证据，归档 Change 保持历史时点。

最终独立增量复核发现 1200px 筛选行溢出 22px，新增断言先复现失败；将压缩断点调至 1280、两列断点调至 1120 后，1100/1180/1200/1280/1440/1920 的筛选容器和表格操作回归通过。此修正不改变 1440 基准画板布局。

未执行真实付费 TikHub/模型调用、生产部署和生产数据验证；本次不改变后端协议、数据库、迁移、依赖或 Secret，不需要数据迁移。Figma 是示例数据的正式交互与视觉基线，真实数量、时间和内容由现有 API 返回。
