---
schema: rvc-change/v1
id: "CHG-20260820-stage8c-collection-runtime-center"
title: "Stage 8C 采集运行中心首个前后端纵切"
level: L3
status: in_progress
owner: "codex"
branch: "feature/stage8c-collection-runtime-center"
created: 2026-08-20
updated: 2026-08-21
depends_on: []
affected_areas:
  - "ingestion"
  - "api"
  - "frontend"
  - "contracts"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc/contracts/http.py"
  - "backend/src/aima_ugc/modules/ingestion"
  - "backend/src/aima_ugc/adapters/persistence/postgres"
  - "backend/src/aima_ugc/bootstrap/api.py"
  - "backend/src/aima_ugc/bootstrap/import_http.py"
  - "contracts/openapi/openapi.json"
  - "frontend"
  - "tests"
  - "docs"
contracts:
  - "HTTP Pydantic → OpenAPI → Orval：Import Batch List / Summary / Detail / Job"
data_changes: []
---

# 目标

在不重写 Stage 8A/8B Excel Import、Job Runtime、Artifact 或 Ingestion 的前提下，交付首个正式
“采集运行中心”前后端纵切：浏览器能够上传 `.xlsx`、查看 Processing Import Batch 三项 KPI、按
真实状态/阶段/时间筛选签名 Cursor 列表、查看 Batch/Job 详情并轮询到终态；Vue 页面以固定 HTTP
Contract 和 Orval Client 为唯一数据入口。

# 背景与当前事实

- 任务基线为 `main` / `origin/main` `73767990a700e984dd2267f3778ec382c11179b3`；开始时开放 PR 为 0，
  该 SHA 的 GitHub `CI` 与可见 Stage 7 Required Checks 均成功。
- Stage 8B 实现 PR `#97`、归档 PR `#98` 与导航闭环 PR `#99` 已合并；归档 Change 为
  `changes/archive/2026-08/CHG-20260820-stage8b-import-http-job/CHANGE.md`。
- 当前 OpenAPI 已有创建 Import、按 ID 查询 Batch、按 ID 查询 Import Job、Keyword Pack 与全局
  Relevance；没有 Batch 列表/KPI/Cursor Query。
- `processing_import_batches.stats.source_filename` 已保存安全原文件名；没有独立 `batch_name`，本阶段
  不新增该字段或 Migration。
- 前端仍是 Stage 1 单路由骨架；Vue/Pinia/Router/Element Plus/Playwright/Orval 已锁定，但尚无正式
  Feature Page 和 Playwright 配置/脚本。
- 视觉资产为 `docs/assets/stage8c/collection-runtime-center-prototype.png`。
- 该 PNG 为 1586×992，SHA-256 为
  `9060D07E527C2A29E3D307EDF5A4C35B31A7726FC151F7550B0164D216635CBD`；它只在本 Change 内作为
  用户批准的一次性视觉基线，不改变 Blueprint 16 的长期 Figma 规则。

# 成功标准

- [ ] `GET /api/v1/import-batches` 通过正式 Pydantic Contract 返回稳定排序、查询绑定且签名的 Cursor
  列表；支持 Batch ID/Job ID、status、stage、created_at 时间范围筛选。
- [ ] `GET /api/v1/import-batches/summary` 返回用户批准的三项 KPI：处理中、北京时间今日完成、北京
  时间今日成功导入行数；前端不从当前页推算全局 KPI。
- [ ] 列表显示 `source_filename`、Batch/Job 状态、阶段、固定统计、时间与安全错误摘要；既有详情和
  Job API 保持兼容。
- [ ] Cursor 使用 HMAC-SHA256、查询条件指纹和过期时间，篡改、过期或跨查询复用返回统一 400
  Error Contract；Secret 不进 URL、日志、数据库或仓库。
- [ ] Vue 按 App/Shared/Feature/Page 分层实现原型的桌面 Normal 页面，并具备 Loading、Empty、Error、
  上传、筛选、Cursor、详情 Drawer 与非终态 5 秒轮询。
- [ ] 页面关闭、终态或组件卸载会停止轮询；浏览器不可见时暂停，恢复可见后立即刷新。
- [ ] 固定 OpenAPI 与 Orval Client 无漂移，生成 TypeScript 可编译；Playwright 有可执行 E2E 入口。
- [ ] 目标测试经历正确原因的 Red → Green，适用后端、PostgreSQL、前端、E2E、生成物与质量门禁在
  最终 Head 获得新鲜证据。
- [ ] 两阶段 Review 严重/重要问题清零，PR 正常合并，合并后 main 新鲜验证成功，Change 完成归档。

# 范围

- Import Batch 只读列表/KPI Query Repository、Application Service、Pydantic HTTP Contract 和 Route。
- Batch ID/Job ID 精确查询；status、stage、created_at 范围；`created_at DESC, id DESC` 稳定排序。
- 签名、不透明、查询绑定并过期的 Cursor；默认 20、最大 100。
- 复用 Stage 8B multipart 创建、Batch detail、Job status、统一 Error Contract 和 Orval 生成链。
- App Shell、Design Token、Collection Feature API/Store/Page、页面私有组件与测试。
- PNG、前端操作说明、API/Blueprint/测试说明等真实受影响文档。

# 非目标

- 不实现 Stage 8D Content Center 或“查看处理内容”。
- 不实现 Stage 8E TikHub 补采页面/按钮，亦不把 Collection Run 混入 Import Batch Read Model。
- 不实现 Stage 8F Relevance 配置页面、AI/Analysis 持久化、报告、趋势图或导出。
- 不实现认证、权限、任务取消、Provider 成本/预算、移动端/平板响应式。
- 不新增自定义批次名称、失败批次 KPI、模糊全文搜索、任意排序或页码分页。
- 不引入 React、Tailwind、第二套 UI/图表库、第二套 Client/Store/Repository/Job Runtime。

# 必须保持不变

- Stage 8A/8B `Artifact → Batch → Durable Job → Worker → Formal File Import → Ingestion` 单一生产链。
- 现有 Batch detail、Job status、Keyword Pack、Global Relevance HTTP Contract 的合法行为。
- `.xlsx` 500 MiB、multipart 550 MiB、Attempt 0.5 小时、最多 10 次及 Windows/Linux 文件语义。
- `processing_import_batches` 与 `jobs` 的写 Owner；Query Repository 只读，不借列表 API 写表。
- Pydantic → FastAPI OpenAPI → 固定 JSON → Orval Fetch Client 单一 Contract 链。
- 当前 Python/Node/PostgreSQL/Vue/Element Plus/Orval/Playwright 精确锁定版本，不升级依赖。
- 页面结构必须使未来 Figma 重生成主要替换 Page/页面私有组件/Token，不改 HTTP Contract、Feature API、
  生成 Client、Store 业务语义和 E2E 行为断言。

# 关键决策

## 用户已确认

- Stage 8C 批准 PNG 作为一次性视觉事实源，记录为 Blueprint 16“正式页面应先有 Figma Frame/Node”
  的显式例外；用户未来会用 Figma 把该图转为正式原型并重新生成/调整前端代码。
- 因此本阶段不得把视觉布局与数据访问耦合：Page 只组合稳定 Feature API/Store/View Model；原型演示
  数据不进入 Contract；未来 Figma 改版保持后端、Orval、Feature API 与行为测试兼容。
- `source_filename` 是主标题，Batch ID 是副标题；不新增 `batch_name`。
- KPI 只实现处理中、今日完成、今日导入内容；“今日”使用 `Asia/Shanghai` 自然日，数据库查询边界转为
  UTC；不实现原型中的失败批次 KPI。
- 列表与 KPI 采用两个只读接口；前端不得从当前页聚合 KPI。

## L3 方案比较

1. **采用：独立列表 + Summary Read Model**。职责清楚、KPI 不受当前页影响，复用同一 Query
   Repository 和已有 Detail/Job API；新增两个最小 GET Contract。
2. 列表响应内嵌 KPI。少一次 HTTP 请求，但把全局日统计与 Cursor/筛选生命周期耦合，每次翻页重复计算，
   不采用。
3. 前端聚合当前页 KPI。无需 Summary API，但结果不是全局事实且随分页变化，违反产品语义，不采用。

## Cursor、安全与兼容

- Cursor 内容为版本、`created_at/id` 位置、查询指纹和过期时间；规范 JSON 后使用 HMAC-SHA256，
  Base64URL 仅作传输编码。
- 默认有效期 30 分钟；这属于只读浏览会话的实现边界，不提供前端可配置项。
- 签名 Key 从 `<AIMA_SECRET_DIR>/import_batch_cursor_signing_key` 读取，要求至少 32 UTF-8 字节；不复用
  PostgreSQL 密码，不进入环境变量、数据库、日志或 Job Payload。
- Secret 缺失/不合格时 Import Batch 列表能力 fail closed；健康和错误响应不泄露路径或内容。
- 新接口为纯新增，既有字段不删除、不改名、不改变默认值；未来 Figma 修改不得反向改变 Contract。

## Vue、CSS 与基础控件例外

- 页面继续使用 Vue 3 SFC；业务样式只写在组件 `<style scoped>`，全局 CSS 仅保留
  `shared/styles/tokens.css` 的语义变量和基础 reset。App Shell 的桌面最小宽度留在自身 scoped 样式，
  不污染其他 Vue 页面。
- Blueprint 16 的长期基线仍是 Element Plus。实际验证表明，当前锁定 Element Plus `2.14.4` 即使按
  组件子路径导入，也会让锁定 TypeScript 7 原生检查在 `skipLibCheck=false` 下因
  `@vueuse/core` Web Bluetooth 声明缺失及 Element Plus `GlobalComponents` 约束失败。
- 本 Stage 不升级依赖、不修改 `skipLibCheck`、不屏蔽声明错误；首屏使用 Vue SFC 内的原生语义
  input/select/button/table，并未建立可复用的第二套控件库。未来如需恢复 Element Plus 控件，必须通过
  独立技术 Change 核验兼容版本；Figma 改版不得顺手静默升级依赖。

## Schema、Migration、性能

- 现有 Batch/Job 表和 `stats jsonb` 足以表达首版列表/KPI，因此默认不新增 Migration。
- 只有真实 PostgreSQL查询计划/测试证明当前索引不足时才增加最小索引 Migration；不因推测预建索引。
- Query 使用绑定参数和单次 Batch/Job join，不产生逐行 Job 查询；Summary 使用数据库聚合。

## 部署与回滚

- 部署增加只读 Secret 文件 `import_batch_cursor_signing_key`；Migration 当前不适用。
- 部署顺序：准备 Secret → 部署 API/前端；Stage 8B Worker/Scheduler 不受影响。
- 回滚可恢复到 Stage 8B API/前端版本并移除新增 Secret；新增 GET Contract 无持久数据需回填或回滚。

# 任务

- [x] 从最新 main 恢复 Stage 8B、GitHub、Contract、Migration、前端与测试事实
- [x] 取得 PNG 视觉例外、未来 Figma 兼容、批次标题、KPI 和接口拆分的用户决定
- [x] 写 Contract/API/Cursor/Query/PostgreSQL 失败测试并确认正确 Red
- [x] 实现最小 Pydantic Contract、Cursor、Query Repository、Service 与 Route
- [x] 固定 OpenAPI、生成 Orval Client
- [x] 写前端 Store/Page/轮询/上传/状态失败测试并确认正确 Red
- [x] 实现 App/Shared/Feature/Page 与 PNG 对齐的桌面页面
- [x] 建立 Playwright E2E 可执行入口并覆盖关键流程
- [x] 同步受影响 Blueprint/API/前端/测试/部署文档
- [x] 完成需求符合性与代码质量 Review；问题补回归 Red → Green
- [ ] 最终 Head 完整门禁、PR CI、Review、Merge、main 验证与 Change 归档

# 两阶段 Review

## 第一阶段：需求符合性

- Stage 8C 成功标准逐项映射到 Batch List、Summary、Detail/Job 复用、签名 Cursor、Vue 页面、轮询、
  Loading/Empty/Error、上传、OpenAPI/Orval 和 Playwright；页面只显示真实 Contract 字段。
- 生产上传仍为 Stage 8B `Artifact → Batch → Durable Job → Worker → Formal File Import → Ingestion`；
  Stage 8C 只增加只读 Query 和前端，不创建平行 Excel Reader/Mapper/Writer/Repository/Job。
- 前端与后端均未增加 Content Query、“查看处理内容”、TikHub 补采、Relevance/Keyword 配置、AI、报告
  或其他 Stage 8D—8F 行为；生成 Client 中既有 Keyword/Relevance 函数不构成页面实现。
- Schema 足以表达列表和 KPI；本 Stage 未修改 Alembic Revision，也未为形式创建 Migration。
- Review 补齐了 Playwright Loading/Empty/Error/`request_id` 证据；当前 E2E 为 3/3。

## 第二阶段：代码质量

- 修复浏览器隐藏后仍继续请求的问题：先观察正确 Red，再用 `visibilitychange` 实现隐藏暂停、恢复立即
  刷新；组件卸载移除计时器和事件监听。
- 把 Page 从 Stage 1 `views/` 骨架收口到 `features/import-batches/pages`，把 App Shell 收口到
  `app/layouts`；未来 Figma 不会跨越 Feature API/Store/Contract 边界。
- Summary 对 `rows_ingested` 只接受 1—18 位非负数字后再转 `bigint`，避免异常 JSON 数值导致聚合
  溢出；列表使用一次 Batch/Job Join、绑定参数和稳定复合排序，无 Router SQL 或 N+1。
- Cursor 具备版本、HMAC-SHA256、常量时间比较、查询指纹、过期、UTC 位置和 Secret fail-closed；统一
  400/503 不暴露 Secret、路径、SQL 或堆栈。
- 上传、Artifact、Job Attempt/Fencing/Retry 和 Ingestion 代码未改写；完整 PostgreSQL Integration 与
  既有 Job/Worker 回归通过，证明 Query 没有改变表 Owner 或事务语义。
- 修复剪贴板权限失败时的未处理 Promise，并移除列表重复显示的原文件名；页面文本由 Vue 转义，错误只
  展示统一安全摘要和 `request_id`。
- 实际按组件导入 Element Plus 的失败证据已记录；未升级依赖、未改 `skipLibCheck=false`、未关闭门禁。
  严重/重要问题清零，无延期为“以后优化”的本 Stage Bug。

# 验证

## 计划

- 目标测试：Stage 8C Contract/API/Cursor/Query/PostgreSQL、Frontend Unit/Component、Playwright E2E。
- 相关测试：Stage 8B API/Worker/Job、OpenAPI/Contract Generation/Compatibility、Migration（若适用）。
- 静态检查/构建：Ruff format/check、mypy、Architecture、Table Ownership、Secret、Docs、前端
  lint/TS7+Vue typecheck/Vitest/build、OpenAPI/Orval drift。

## 新鲜证据

- 开始前 `main` / `origin/main` 均为 `73767990a700e984dd2267f3778ec382c11179b3`，开放 PR 为 0；
  GitHub `CI` run `32382121508` 与同 SHA 可见 Stage 7 checks 成功。
- 后端初始 Red：Stage 8C 目标测试因 `ImportBatchListQuery`、Cursor/Query 模块和 Route 不存在，在收集期
  产生 3 个预期导入/Contract 失败；最小实现后目标与 Stage 8B 相关回归为 `28 passed`。
- 前端初始 Red：路由断言失败，Feature API/Store 模块不存在；最小实现后 3 个测试文件 7 个测试通过。
- Review 新发现浏览器隐藏时轮询未暂停：新增测试后先得到“隐藏 5 秒仍调用列表 API”的正确 Red；修复
  后同文件 3/3 Green。当前 Stage 8C 前端目标合计 3 文件 8 测试通过。
- 当前 Stage 8C 后端非 PostgreSQL 目标为 `10 passed`；Ruff 目标检查、TypeScript 7 + Vue typecheck、
  ESLint 均成功。
- Playwright 使用 1600×1000 Chrome 桌面视口，Normal/Loading/Empty/Error、详情、上传创建 Job 和
  `request_id` E2E 为 3/3；浏览器实机另检查了 Vue 页面 DOM、Loading 状态和 scoped CSS 布局，Mock
  数据截图完成视觉核对。
- PostgreSQL Integration 初次运行在连接前因本机缺少 `.runtime/secrets/postgres_password` 终止；用户
  随后授权启动 Docker Desktop 和使用临时密码。只使用本地 `postgres:18.4` 镜像建立绑定
  `127.0.0.1:55432` 的临时隔离容器，完成 base→head、`current=20260820_0020`、`alembic check`、Stage
  8C Query 1/1、完整 Integration 120/120、完整后端 685 passed / 1 skipped，以及 head→base→head。
  临时容器、密码、数据库、Artifact 与日志目录已删除；未读取或修改既有业务数据库。
- OpenAPI/JSON Schema Drift 与 Compatibility 成功；Orval 连续两次生成哈希一致
  `E072B68D43BA47211BB441E2E4749D577373D50A0D3ACF5C60138DC5EC2CA485`。
- 完整 Ruff format/check、mypy 198 source、Architecture、Table Ownership、Secret Scan、Docs Check、
  前端 Lint、TS7/Vue typecheck、Vitest 8/8、Build 与 Chrome Playwright 3/3 成功。最终 PR Head CI 尚待执行。

# 文档影响

- 必须同步 `docs/API接口说明.md`、Blueprint 04/16/17、`frontend/README.md`、测试/部署说明中真实变化。
- PNG 例外只描述当前 Stage 8C 的批准基线；不把 PNG 永久提升为全局前端规则。
- 未改变 Excel Workbook、Provider Operation、Analysis 或 Release 语义，不修改对应无关 Blueprint。

# 交付

- Branch：`feature/stage8c-collection-runtime-center`
- Commit：尚未创建
- PR：尚未创建
- 发布：尚未合并；Change 保持 Active
