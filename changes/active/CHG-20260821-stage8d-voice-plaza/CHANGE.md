---
schema: rvc-change/v1
id: "CHG-20260821-stage8d-voice-plaza"
title: "Stage 8D 声音广场、Analysis 持久化与 Excel 导出产品化"
level: L3
status: in_progress
owner: "codex"
branch: "feature/stage8d-voice-plaza"
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas: ["analysis", "content", "api", "jobs", "artifacts", "frontend", "contracts", "docs"]
affected_paths:
  - "backend/src/aima_ugc/modules/analysis"
  - "backend/src/aima_ugc/modules/content"
  - "backend/src/aima_ugc/modules/reporting"
  - "backend/src/aima_ugc/adapters/persistence/postgres"
  - "backend/src/aima_ugc/bootstrap"
  - "backend/src/aima_ugc/contracts/http.py"
  - "migrations"
  - "contracts/openapi/openapi.json"
  - "frontend"
  - "tests"
  - "docs"
contracts:
  - "HTTP Pydantic → OpenAPI → Orval：Content List / Detail / Analysis / Export"
  - "Analysis Result + ordered Label Pairs persistence identity"
  - "analysis.content-label.v1 / reporting.content-export-excel.v1 Job Payload"
data_changes: ["analysis_content_results", "analysis_content_label_pairs", "analysis_content_requests", "analysis_content_request_items", "reporting_data_exports", "reporting_data_export_items"]
---

# 背景与当前事实

- 本 Change 从已同步的 `main` `6c4cb4fb8978153f1a6635a043b12c734b7cac04` 创建；该 Head 已包含 Stage 8C 实现及归档。
- PostgreSQL Migration Head 为 `20260820_0020`。
- Content Current / Version / Metric、Comment、Coverage 与来源追溯已经是 PostgreSQL 正式事实；尚无统一 Content 查询 HTTP 与前端页面。
- Analysis 已有 `ContentLabelingService`、严格校验后的 `ContentLabelAnalysisV2`、LLM Adapter 与 JSONL/Excel 投影，但尚无正式数据库持久化、当前结果查询和产品 HTTP。
- 唯一 Provider-neutral Excel 实现是 `platform/export/excel.py`；本阶段必须复用，不能从页面数据或另一份映射重新生成 Excel。
- 现有持久化 Job Runtime 已具备 lease、fencing、heartbeat、attempt deadline、分类重试和终态；Analysis 与 Export 只能注册为新 Job Type，不能另建队列。
- Stage 8C 已提供采集运行中心和导入批次状态；Stage 8D 不改变其 Contract 和行为。

# 目标

交付正式“声音广场”：浏览器可查询 PostgreSQL 中的统一 Content、查看内容详情与来源/评论覆盖、读取当前有效 AI 情感及全部一级/二级标签，并按冻结的查询条件或选择项创建持久化 Excel 导出 Job，完成后通过 Artifact 下载。

# 成功标准

- [x] 声音广场列表只通过 Pydantic HTTP Contract、生成 OpenAPI 和 Orval Client 查询 Content，不直接访问数据库或手写平行 Client。
- [x] 列表支持经批准的全文、平台、内容类型、发布时间、来源 Batch/Run、AI 状态、AI 情感、一级/二级标签过滤和稳定游标分页。
- [x] 列表“标签”栏按 Analysis 原始有序结果展示全部 `{primary_label, secondary_label}` 标签对，而非只取第一组或拼成后端不可解析字符串。
- [x] 详情抽屉展示原始内容、作者与指标、当前有效 AI 情感和全部标签对、评论/覆盖信息及来源记录；没有媒体时显示文本状态，不伪造缩略图。
- [x] Analysis 成功结果与有序标签对在同一事务持久化；精确重试幂等，输入或配置身份变化保留历史；只有匹配当前 Content 输入和选定配置身份的结果才是 current。
- [x] 未分析或当前结果失效的 Content 保持可查询、可导出，AI 字段为空并返回明确 Analysis 状态。
- [x] 导出支持当前全部查询结果、当前页和显式选择项；创建持久化 Job 后由 Worker 复用共享 Excel exporter，产物登记为 Artifact，HTTP 请求不执行长任务。
- [x] 导出严格冻结请求时的过滤条件/排序或 Content ID 集合；未分析项不静默剔除，完成统计明确报告总数、已分析数和未分析数。
- [x] OpenAPI Drift、Orval 生成、前后端质量门禁、真实 PostgreSQL Migration/Integration、Job fencing/retry/idempotency 均通过。
- [ ] 两阶段 Review、最终 PR Head 新鲜 CI、正常合并、合并后 main 验证和 Change 归档全部完成。

# 范围

- Analysis Result / ordered Label Pair 的 PostgreSQL Schema、Migration、Owner Repository 和 current 解析。
- Content 列表/详情/评论覆盖/来源追溯 Query Repository、Application Service 与 HTTP Contract。
- Content Analysis 状态与结构化完整标签集合在 HTTP、OpenAPI、Orval 和 Vue 中的投影。
- Excel Export Request/Record、Job Payload/Handler、Artifact 关联、状态查询与下载。
- 声音广场 Vue 页面、筛选、表格、详情抽屉、导出交互和必要的导航入口。
- 受影响 Blueprint、API/运维说明和本 Change 的同步。

# 非目标

- 不进入 Stage 8E 的 TikHub 补采、正式采集编排扩展或其他 Provider 能力。
- 不进入 Stage 8F 的全局 Relevance 词包配置页面、Discovery 词包、智能洞察或保存筛选方案。
- 不新增媒体抓取、图片 Artifact、OCR 或虚构 Content 缩略图。
- 不新增车辆结构化字段/筛选、账号类型、UGC 类型推断或基于文本猜测业务标签。
- 不实现本地账号密码、第三方身份接入或公网生产认证；不得宣称敏感写 API 已具备公网生产权限边界。
- 不升级依赖，不替换 Vue 3 / Pinia / Vite / Orval，不引入平行 UI 框架或 API Client。
- 不实现 Artifact 自动过期或删除；沿用当前“未批准具体保留期、不得自动删除”的事实。

# 必须保持不变

- Router → Service → Repository；数据库读取走 Query Repository，表只能由各自 Owner 写入。
- Content Current + Version + Metric、ArtifactService、PostgreSQL Job Runtime、Stage 8C Import 和共享 Excel exporter 的既有公共行为。
- `ContentLabelAnalysisV2` 是成功 Analysis 的唯一正式结构；持久化、页面和 Excel 必须源于同一份校验结果。
- Job Payload 版本化，Secret 不进 Payload/数据库/日志；旧 fencing token 不能提交业务可见结果。
- 页面名称和导航文案使用“声音广场”，内部 Content 模块及公共资源语义保持稳定，便于后续用 Figma 重新生成视觉层。
- 页面使用 Vue SFC、现有 store/api 分层与共享 design tokens；局部 scoped CSS 仅表达布局样式，不改变 Vue 技术栈或污染全局。

# 关键决策

## 已批准

1. **产品命名**：用户可见名称为“声音广场”；后端仍以 Content 为领域名，避免视觉命名渗入稳定 Contract。
2. **视觉基线例外**：本阶段无 Figma 文件，用户批准 PNG/JPG 一次性视觉基线及对 Blueprint Figma 门禁的 Change 级例外。基线为：
   - `docs/assets/stage8d/voice-plaza-list-reference.jpg`，1280×720，SHA-256 `EE01DE81E0CECF0AD4E35538865A1DF34547B6D7C2944C99F08A6A538F0D6BE6`；
   - `docs/assets/stage8d/voice-plaza-detail-reference.jpg`，1280×720，SHA-256 `7397FC2EB9336BD9AE5CF671D709CB96713C2E0F32BBA111C4E40DF4A7BE0380`。
   ImageGen 在 2026-08-21 因服务网络错误未产出新图，未用 API Key/第三方服务绕过。实现保持 Page/私有组件/Token 可替换，未来 Figma 代码仅替换视觉层，不改 Contract、Orval、Store 语义。
3. **媒体**：Excel Import 没有图片；TikHub 现有 `content_media` 只保存外部 URL 元数据。本阶段文本优先，有合法媒体元数据时可展示，否则显示无媒体状态，绝不伪造图片。
4. **Analysis 展示**：列表和详情显示当前有效 AI 情感，并按 `ordinal` 展示全部一级/二级标签对。HTTP 返回结构化数组；前端不只取第一组，不丢弃重复一级标签下的不同二级标签。
5. **Analysis 持久化**：结果与标签对独立于 Content 表；成功才写 Result，失败留在 Job/Attempt 错误事实。身份至少包含 Content、Content 输入 Hash、Prompt 版本/Hash、Taxonomy Hash、Provider、Model；精确重试返回既有结果，身份变化形成历史。
6. **Excel 导出范围**：支持冻结的全部筛选结果、当前页、显式选择项。未分析 Content 继续导出且 AI 字段为空；若只要已分析数据，用户通过 AI 状态筛选为完成。
7. **Excel 导出执行**：HTTP 只创建 Export 记录与持久化 Job；Worker 通过同一 Query/Projection 读取 PostgreSQL，复用 `export_unified_data_excel`，再登记 Artifact。页面提供导出记录和状态，不返回同步生成的大文件。
8. **保留与下载**：沿用当前 Artifact 生命周期，没有批准的保留期前不自动删除；下载通过 ArtifactService/Store 抽象，不直接暴露本地存储路径。

## L3 方案比较

- **选定方案：独立 Analysis 历史表 + current 查询投影 + 独立 Reporting Export 记录**。优点是 Content Owner 不被 AI 配置污染，Analysis 可审计，导出 Job/Artifact 有稳定业务关联；代价是一条 Migration 和跨 Owner 只读查询。
- 未选：把 AI 字段直接加到 `contents`。无法保存配置变化历史，且会让 Analysis 越权写 Content Owner 表。
- 未选：只把 Analysis/Export 结果放 Job JSON。无法建立可靠 current 语义、标签过滤、Artifact 业务关系或可审计查询。

## 已批准：真实 LLM 触发策略

用户于 2026-08-21 批准按推荐方案持续实施：声音广场由用户明确选择 Content 或按当前冻结筛选范围创建 durable Analysis Job，默认不因 Import/Collection 自动调用付费 Provider。这样费用发生有显式用户动作，且不改写所有 Ingestion 路径；自动随采集分析如未来需要，另立 L3 Change 评估持续费用、调度和事务级联。

# 数据、Migration、部署与回滚

- 新建 `analysis_content_results` 与 `analysis_content_label_pairs`，由 Analysis Owner 写；标签通过 `(analysis_result_id, ordinal)` 保序，业务身份由数据库唯一约束保障。
- 新建 `reporting_data_exports`，由 Reporting Owner 写；引用 Job 与 Artifact，不复制 Job 状态。
- Migration 从 `20260820_0020` 升到本阶段新 Head；验证 base→head、previous→head、downgrade/re-upgrade 与 `alembic check`。
- 部署顺序：先 Migration，再 API/Worker/Frontend；Worker 必须注册 Analysis（若触发策略获批）与 Export Job Type 后才接受对应创建请求。
- 回滚：先停止新 Job 创建和 Worker 领取，回滚应用，再 downgrade Migration。导出文件由 Artifact 生命周期保留；若表中已有生产 Analysis/Export 事实，downgrade 会丢失新表数据，执行前必须备份，不能自动操作。

# 安全、性能与兼容性

- 查询使用参数绑定、受控排序、签名游标和有限 page size；详情与导出选项拒绝任意列/路径。
- 下载按 Artifact 元数据定位并使用 Store 抽象，响应不泄露 `storage_key` 或服务器路径；文件名与 Excel 单元格继续复用现有安全处理。
- Secret 不进 Job Payload；真实 LLM 配置仅从既有 Secret/环境装配边界读取。
- 当前版本无认证，写/下载 API 只适用于受信部署边界；文档必须如实说明，不能通过本 Change 发明权限模型。
- 新字段是新增 Contract；不删除或改变 Stage 8C 端点。未来 Figma 重做保持 route、store、Pydantic/Orval 类型与操作语义兼容。

# 任务

- [x] 恢复 main、PR、CI、Migration、Active Change、Blueprint、Contract、Job/Artifact/Export/Analysis/Frontend 机器事实
- [x] 固化视觉基线、已批准产品决策和 L3 边界
- [x] 以失败测试固定 Analysis Schema/Repository/current/幂等/事务语义
- [x] 实现 Migration 与 Analysis 持久化
- [x] 以失败测试固定 Content List/Detail/Filter/Cursor/Error Contract
- [x] 实现 Content Query Repository、Service 与 HTTP
- [x] 以失败测试固定 Export Request/Job/Artifact/下载语义
- [x] 实现 Reporting Export、Worker Handler 与 Artifact 下载
- [x] 根据批准的显式触发策略实现 Analysis Job 入口
- [x] 生成并校验 OpenAPI 与 Orval Client
- [x] 实现声音广场 Vue 页面、完整标签显示、详情抽屉和导出交互
- [x] 同步真正受影响的 Blueprint/API/运维文档
- [x] 运行真实 PostgreSQL、Migration、后端/前端/生成物和质量门禁
- [x] 完成需求符合性 Review 与代码质量 Review，严重/重要问题清零
- [ ] Commit、Draft PR、Review、最终 Head 新鲜 CI、Ready、正常合并
- [ ] 合并后 main 验证、Change done/归档、归档 PR 和分支清理

# 验证

## Red → Green 计划

- Analysis：先验证表不存在/Repository Contract 未实现导致正确失败，再实现 Migration、幂等、current 和 rollback。
- Content HTTP：先验证端点缺失/Contract 不满足，再实现成功、非法过滤、游标篡改、404、request_id、全部标签与未分析状态。
- Export：先验证端点/Job Type 缺失，再实现创建、冻结范围、Worker claim/fencing/retry、Artifact 关联、未分析统计和安全下载。
- Frontend：先写 store/page/component 失败测试，再生成 Orval、实现筛选/分页/详情/标签/导出并通过类型与构建。

## 已观察 Red → Green 证据

- Analysis/Reporting Schema：首次因模块/表不存在失败；实现六表与 Migration 后 `3 passed`。
- HTTP Contract/API：首次因 Stage 8D Contract/Route 不存在失败；实现后目标 API/Contract `11 passed`；
  XLSX OpenAPI 首次缺 `binary` schema，补 Contract 后 `4 passed` 且 Orval 生成 `Promise<Blob>`。
- Vue：首次因 `/voice-plaza`、Feature API 和 Table 不存在失败；实现后前端全量 `12 passed`，其中 SSR
  断言同一内容全部三组一级/二级标签均出现在标签栏。
- PostgreSQL 18 E2E：先后暴露非法 Fake Taxonomy、JSONB null 和表头断言问题并修正测试/实现；最终
  Import 2 行 → Analysis 两标签 → 精确重试幂等 → current 配置选择 → Export 2 行 → Artifact 下载 →
  XLSX 重开为 `1 passed`。新增作者搜索与错误 binary 回归先失败，修正后均转绿。
- Review 回归：显式空 `provider_name` 原会回退到 URL 推导值；`DID NOT RAISE` Red 后恢复严格拒绝。
  分析 Job 轮询错误原产生未处理 Promise；Vitest 捕获 Unhandled Rejection 后统一显示错误并转绿。
- 导出范围：Playwright 等待不存在的“当前页内容”超时 Red；实现后当前已加载 Content ID 被显式冻结为
  `selected` Contract 并转绿。Analysis 批处理进度原把当前批次重复计数；独立进度回归转绿。
- Content Version 在 LLM 调用期间变化时，原实现更新 `stale` 后抛错导致事务回滚；PostgreSQL 回归明确
  复现 `ValueError`，修正为同一 fenced 事务提交 `stale/content_version_changed` 后 Job 正常成功。
- 来源追溯：同一 Content 被后续 Import 更新后，原 Batch 筛选返回空集；PostgreSQL 回归从 Red 转绿，
  现按全部 Content Version 来源账本匹配 Batch/Run，同时仍返回最新 Current。
- Schema 新增 Analysis Request Item 状态/结果/错误字段一致性和 Export Artifact/Stats/完成时间一致性
  CHECK；单元 Schema 回归从两项失败转绿，Migration 多路径与 `alembic check` 通过。

## Review 记录

### 第一阶段：需求符合性（已完成）

- 已确认列表/详情遍历全部结构化标签对，未进入 Stage 8E/8F，未伪造媒体，未建立平行 Client/Job/
  Repository/Exporter；采集运行中心已提供按 Batch 查看处理内容跳转。
- 发现并修复：文本输入写明搜索作者，但后端未包含作者；已补 PostgreSQL JSONB 作者搜索回归。
- 发现并修复：Change 已批准全部查询、当前页、显式选择三种导出范围，但页面遗漏当前页；现复用
  `selected + content_ids` Contract 冻结当前已加载项，没有增加平行 HTTP 语义。
- 已逐项确认不含 Stage 8E TikHub 补采和 Stage 8F Relevance/Plan 页面，不改变无关业务语义。

### 第二阶段：代码质量（已完成）

- 发现并修复：Query/Export 原先会选择同 Content Version 的任意最新 Analysis，可能把旧 Provider/Model
  结果误当 current；现统一匹配 Prompt Version/Hash、Taxonomy Hash、Provider 与 Model，并用更新但
  非当前配置的数据库结果证明不会覆盖当前标签。
- 发现并修复：Orval binary 下载在 409 时返回 JSON Blob，Feature API 可能保存伪 XLSX；现识别 JSON
  Blob 并恢复统一 HTTP Error Contract，回归测试先红后绿。
- 已证明旧 Export Fencing Token 无法关联 Artifact，失败事务不改变 Export 记录。
- 发现并修复：Content Version 在模型调用期间变化时 stale 更新会随异常回滚；现 fenced 事务保留 stale
  事实且不落过期 Analysis Result。
- 发现并修复：批处理进度重复计算当前批次、轮询 Promise 未处理、显式空 Provider 身份错误回退。
- 发现并修复：Batch/Run 过滤只匹配最新来源；现使用参数化 correlated EXISTS 匹配全部版本来源账本。
- Schema 增加终态字段一致性约束；重新核查事务、Fencing、Retry、Artifact、下载文件流、Secret、错误
  响应、公式注入防护、Migration downgrade/re-upgrade 与临时文件生命周期，严重/重要问题清零。

## 当前新鲜证据

- 后端：隔离 PostgreSQL 18.4 上 `uv run pytest tests -q` 为 `705 passed, 1 skipped`；两个 warning 分别为
  既有 Starlette TestClient/httpx 弃用提示和 Zip duplicate-member 安全测试的标准库提示。
- PostgreSQL Migration：base→`20260821_0021`、previous `20260820_0020`→head、downgrade base、
  downgrade/re-upgrade、`alembic current` 与 `alembic check` 均通过。
- Python/质量：`uv lock --check`、直接 import、Ruff Format/Check、mypy `217 source files`、Architecture、
  Table Ownership、Secret Scan、Docs Check 均通过；Wheel 构建、包内容核对、隔离 venv 安装/import 通过。
- Contract/Frontend：OpenAPI `--check`、Compatibility 与 Orval SHA-256 无漂移；Vitest `13 passed`、
  ESLint、TypeScript 6/7、Vite build、Playwright `5 passed` 均通过；npm 生产/全部依赖 audit 均为
  `found 0 vulnerabilities`。
- GitHub Actions：待最终 PR Head 执行。

# 文档影响

- `docs/blueprint/17-实现顺序与Definition-of-Done.md`：完成后同步 Stage 8D 当前事实和下一单元，不写实现流水账。
- Analysis/Content/HTTP/Job/Artifact/Export 相关 Blueprint：仅同步实际落地的 Contract、Owner、表与运行链路。
- API/运维说明：补充声音广场、导出 Worker/Artifact、无认证受信边界和部署顺序。
- 视觉基线例外、用户决定、Red/Green/Review/PR/CI 证据保留在本 Change。

# 交付

- Branch：`feature/stage8d-voice-plaza`
- Implementation Commit：`deee4395c774241f402cc9efc6010817c968c2e5`。
- PR：[#102](https://github.com/dingyuwen777/AIMA_UGC/pull/102)，Draft，最终 Head CI 运行中。
- Merge：待完成。
- Archive：待完成。
