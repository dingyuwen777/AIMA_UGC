---
schema: rvc-change/v1
id: CHG-20260826-stage12-historical-migration
title: 实现4000万历史数据迁移与手动AI打标
level: L3
status: ready_for_review
owner: aima
branch: main
created: 2026-08-26
updated: 2026-08-27
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - analysis
  - jobs
  - api
  - frontend
  - database
  - artifacts
  - runtime
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/http.py
  - frontend/src/features/import-batches/
  - frontend/src/features/voice-plaza/
  - frontend/src/generated/api/
  - migrations/
  - tests/
  - scripts/dev/
  - compose.yaml
  - env.local.example
  - env.production.example
  - docs/
contracts:
  - HTTP Pydantic/OpenAPI/generated TypeScript client
  - Historical Import Campaign/Item/Job versioned payloads
  - Unified Data Import source acquisition and ingestion policy
  - Analysis Run/Shard/Result identity
data_changes:
  - 新增历史 Campaign、Item、逐行结果与稀疏冲突表
  - 扩展 Campaign 来源类型、写入策略、本地上传暂存状态与标准观察结果账本
  - 扩展 processing_import_batches 的历史来源关系
  - 新增 Analysis Run 并扩展 Request/Result 身份
  - 回填已有 Analysis Request 为单 Request 历史 Run
  - 0029 前向收敛 Stage 12 开发期旧约束名并补齐 Source Manifest 唯一索引，不改变 0028 业务语义
---

# 目标

按照 `docs/roadmap/03_4000万历史数据迁移实施方案.md`，在现有 Artifact、Excel Mapper、Canonical、Content Owner、PostgreSQL Job 和 Analysis 架构上实现安全、可恢复、可对账的 4000 万历史数据迁移能力，以及与导入解耦、可重复保留历史的网页手动 AI Run。

# 成功标准

- [x] 网页只能枚举管理员批准的只读服务器根目录，并能建立 Campaign、预检、启动、取消和重试失败项。
- [x] 所有源文件先形成不可变 Artifact/Chunk 与 SHA-256，全部预检通过后才能启动业务导入。
- [x] 历史数据对已有同一身份只补空字段，绝不覆盖非空 Current；相同/冲突不推进新鲜度或 `last_seen_at`，冲突可审计。
- [x] 每个输入行都有唯一、可对账的终态；Chunk/Job 重试和 Lease 接管不重复产生业务副作用。
- [x] 导入全程流式、有界、集合式写库，普通 Job 不被历史任务饿死；本机 10 万/100 万容量阶梯完成，500 万及 4000 万生产估算按已批准门禁延期到公司服务器演练。
- [x] 历史导入不自动触发 AI；用户可创建分片 Analysis Run，同一 Content Version 多轮结果保留且 Current 选择稳定。
- [x] 旧上传、Collection、Content 查询、Analysis 合法行为和现有数据兼容。
- [x] 所有不依赖 Git/生产授权的 required 分层验证、Completion Audit、两阶段 Review 和 Ready Check 有本轮新鲜成功证据。
- [x] 软件能力完成与生产 4000 万实际执行分别报告；未获显式生产写授权时不执行全量迁移。
- [x] 历史预检与迁移展示真实进度条；AI Analysis Run、Excel 导出与采集 Scope 等已有真实进度的长任务统一使用可访问进度条，未知总量阶段不伪造百分比。
- [x] 页面只保留一个“导入数据”入口；本地文件/文件夹和服务器目录先分别取得 Source Artifact，再共用 Campaign 预检、Chunk、Job、进度、取消/重试和逐行账本；来源与 `standard_observation / historical_fill_only` 写入策略独立选择。
- [x] 旧 `/api/v1/import-batches` 合法请求与响应保持兼容，不作为新页面主路径，也不删除现有消费者能力。
- [ ] 已按用户授权在 `main` 创建功能批次提交；待推送远端后取得最终 `main` HEAD CI 证据并归档 Change。用户明确要求直接提交远端主分支，因此 PR 不适用。

# 范围

- Historical Import Campaign、目录 Browser、Manifest、Artifact 快照、预检、Chunk、调度和网页闭环。
- Content Owner 的集合式 Historical Fill-Only 写入与冲突输出。
- 逐行结果账本、稀疏冲突账本、来源筛选和汇总对账。
- Analysis Run/Shard、重复分析历史、Current 投影和网页闭环。
- Pydantic/OpenAPI/generated client、Alembic Migration、测试、基准、运行手册和受影响文档。

# 非目标

- 不自动对迁移数据调用 AI。
- 不创建任意路径文件管理器，不允许删除/移动/下载服务器源文件。
- 不绕过 Content Owner 直接写业务表。
- 不引入微服务、Redis、Kafka、第二数据库或搜索引擎。
- 不升级依赖，不改变五平台身份或 AI taxonomy。
- 不在本 Change 内实现认证、完整协调 Backup/Restore 或完整 Production Go-Live。
- 不把代码完成授权扩张为生产 4000 万数据写入授权。

# 必须保持不变

- 模块化单体与 API/Worker/Scheduler/Migration 分进程。
- PostgreSQL 是唯一业务事实库；长任务使用当前 PostgreSQL Job Runtime、Lease/Fencing/Deadline/Cancel/Retry。
- File Import 继续走 Input Artifact → Mapper → Canonical → Relevance → Content Owner，不伪造 Collection Candidate。
- 普通 `ingestion.import-excel.v1` 和 Collection 继续使用现有字段级新鲜度语义。
- Content 身份、Current + Version + Metric、表 Owner 和 ArtifactService/ArtifactStore 边界。
- Pydantic 是 HTTP 事实源，OpenAPI/generated client 只生成不手改。
- 当前 Prompt Markdown 是 AI taxonomy/判断唯一事实源。
- 当前合法 API、配置、数据、错误和页面行为默认兼容。

# 关键决策

1. 采用 Roadmap 03 的方案 A：历史命中只补空值，非空冲突不覆盖并留痕。
2. 网页目录访问使用单一 allowlisted root、只读挂载和相对路径，所有路径逃逸 fail closed。
3. 当前无 Authentication/Authorization，所有能访问内网页面的客户端都可调用新端点；不伪造角色权限，高价值 Campaign 操作写现有审计边界，访问范围扩大时另建认证 L3 Change。
4. Campaign 先冻结全部输入再由用户开始，避免导入期间源目录变化。
5. 每行建立紧凑结果账本，冲突另存稀疏字段哈希；不复制完整正文。
6. 最终写入使用 Content Owner 的集合式批量历史方法，不以逐行 SQL 往返处理 4000 万。
7. 历史 Job 低优先级且 in-flight 有界；Chunk/Attempt/Checkpoint 使用数据库唯一约束和 Fencing。
8. Analysis 增加 Run 父事实，现有 Request 作为 Shard；目标由 PostgreSQL 集合式冻结。
9. AI Current 按 Run 创建顺序选择；新 Run 失败不删除旧成功结果。
10. 生产全量执行是独立授权；代码回滚不自动删除或清空已迁移数据，数据补偿必须独立 Change。
11. 2026-08-27 用户替代原“两入口”决定：页面统一为一个“导入数据”入口；`local_upload / server_path` 只决定 Source Artifact 如何取得，`standard_observation / historical_fill_only` 独立决定 Content Owner 写入语义。Artifact 形成后必须共用 Campaign 预检、Chunk、持久 Job、进度、取消/重试和逐行账本。旧 `/api/v1/import-batches` 继续作为兼容入口保留，但新页面不再以它作为本地导入主路径。
12. 新版手动 Analysis Run 只开放显式选择 1—1000 条 Content；query scope 暂不开放，待真实付费模型 Gold Set、费用和容量报告后另行决策。兼容入口与历史 Run 的 query 事实继续可读。
13. 本机容量开发门禁以已完成的 10 万、100 万阶梯为上限；500 万延期到公司服务器生产前演练。本机两次未完成的 500 万尝试只保留风险证据，不作为通过结果；在服务器侧 500 万或经业务 Owner 批准的等效比例演练完成前，不授权真实 4000 万执行。
14. 进度展示采用用户确认的方案 A：Historical Campaign 由后端聚合真实预检与迁移进度并通过 Pydantic/OpenAPI/generated client 提供；其他长任务只复用已有 Job/Shard/Scope 进度。发现阶段或短请求无法确定总量时展示不确定进度，不伪造百分比。
15. 经用户授权删除 Stage 8C—8F 的一次性二进制视觉参考；现行 Figma/前端指南不再把这些路径描述为可访问资产，归档 Change 继续保留当时的尺寸、哈希和采用原因，不改写历史事实。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Internal V1-B 状态同步为业务 Owner 已确认完成，Stage 12 成为下一正式单元 | user:internal-v1-b-complete | satisfied | README、Roadmap README/01/02、运行文档、代码导航和持续开发指南已同步；`check_docs.py` 本轮通过，且所有文档明确外部确认不等于仓库持有服务器日志 |
| R2 | 网页可以枚举服务器目录并启动 4000 万导入 | user:web-directory-import | satisfied | Compose 与源码开发两条运行链路均已接通：开发 launcher 解析并向 API/Worker 传递 `AIMA_HISTORICAL_IMPORT_ROOT`，默认创建 `.runtime/historical-input`；目标回归 `28 passed, 2 skipped`，实机 API 返回 `available=true`，真实浏览器“导入数据 → 服务器目录”不再显示“未配置历史导入根目录” |
| R3 | 服务器目录访问限制在批准只读根目录，不能形成任意文件访问能力 | `docs/roadmap/03_4000万历史数据迁移实施方案.md` | satisfied | `HistoricalDirectoryBrowser` 拒绝绝对路径、逃逸、混合分隔符、Symlink/Junction/Reparse Point；Compose 只读挂载；12 条目录测试通过、1 条因当前 Windows 无符号链接权限跳过 |
| R4 | Historical Campaign 具有不可变快照、预检、分片、持久状态、取消、重试和断点恢复 | `docs/roadmap/03_4000万历史数据迁移实施方案.md` | satisfied | 对稀疏 Content/Author 多行 INSERT 新增真实 PostgreSQL 回归，修复前分别在 `contents.title`/`accounts.display_name` 得到现场同源 CompileError，修复后 2 passed；按原文件、原关键词包与原 Profile 重建的本地 Campaign `1c1ac489-17f8-4096-a6fa-6458f2d8deda` 已以 76 个 Chunk 完成 75,279 行，状态 `succeeded`、0 失败 |
| R5 | 历史命中采用只补空值、不覆盖非空值、冲突留痕的方案 A | user:historical-conflict-policy-a | satisfied | `PostgresHistoricalContentRepository.ingest_rows` 的真实 PostgreSQL 测试覆盖 Content/Author 补空、相同、冲突、版本、新鲜度与 Metric 不更新；2 条批量写入测试通过 |
| R6 | 每个输入行可追溯到终态，Campaign/文件/Chunk/Batch/Content/Artifact 可对账 | `docs/roadmap/03_4000万历史数据迁移实施方案.md` | satisfied | 逐行 outcome 唯一账本、稀疏冲突账本、Campaign/Item/Batch/Artifact 关系已由 Schema 与真实 Golden Path 验证 |
| R7 | 使用有界流式处理、集合式批量写入和公平调度，并通过容量阶梯证明 4000 万可执行性 | user:40m-effective-migration；user:defer-local-5m-capacity-2026-08-27 | explicitly_deferred | 有界 Chunk、集合式 PostgreSQL 写入和低优先级调度已实现；10 万、100 万完整报告分别位于 `.runtime/stage12-capacity-20260826/100k-r2/capacity_report.json` 和 `.runtime/stage12-capacity-20260826/1m/capacity_report.json`。500 万首次在 399.7 万行后因磁盘耗尽中断，重跑在 82.1 万行、0 失败 Chunk 时按用户决定中止；500 万或批准的等效比例演练正式延期到公司服务器生产前门禁，因此当前不证明也不授权 4000 万可执行性 |
| R8 | 历史导入与 AI 解耦，不自动产生模型调用或费用 | user:import-ai-decoupled | satisfied | Historical Worker 注册链路没有 Analysis 调用；真实 Campaign Golden Path 断言 Analysis Job 数为 0 |
| R9 | 网页手动 AI 使用 Run/Shard，同一 Content Version 可重复分析并保留每轮历史 | user:manual-ai-reanalysis | satisfied | 新版 selected-only Preview/Create、数据库内 Planner 冻结、Run/Target/Shard/Result、创建顺序 Current 与页面历史已实现；Analysis PostgreSQL、Browser Mock 和真实 Full-stack 均通过 |
| R10 | 复用现有架构/Owner/Contract/Job/Prompt，不引入平行系统或无关依赖升级 | `AGENTS.md` | satisfied | 架构/表 Owner/Secret 门禁通过；HTTP 由 Pydantic 生成 OpenAPI/Client 且生成前后哈希一致；Job Registry、ArtifactService、Content Owner 和 Prompt 事实源均复用；依赖/锁文件未修改 |
| R11 | 软件功能验收和生产 4000 万实际迁移分开，未经生产写授权不执行 | user:current-request | satisfied | 只在专用测试库运行合成容量阶梯和验证；运行手册、Roadmap 与本 Change 均保持生产 500 万演练和 4000 万独立授权边界，未启动生产 Campaign |
| R12 | 分层测试、容量/恢复门禁、Completion Audit、两阶段 Review 和文档同步完整 | `AGENTS.md` | satisfied | 最终 Stage 12 Contract/API/PostgreSQL/Worker/Migration 目标组 67 passed/1 skipped，容量 Harness 1 passed，Frontend 44 passed、Browser Mock 31 passed，统一导入真实 Browser/API/PostgreSQL/Worker/Fake LLM Golden Path 3 passed；Completion Audit、Review re-review 和所有本地适用门禁完成 |
| R13 | Git 操作必须保持在用户明确授权边界内，远端 CI 只能记录实际结果 | user:batched-direct-main-authorization-2026-08-27 | satisfied | 用户明确要求按功能分批提交到远端 `main`；已确认本地与 `origin/main` 无分叉并创建后端、前端、运行环境三个中文提交，未创建 PR、未强推、未改写历史；推送和远端 CI 仍按本 Change 交付任务取得实际证据后再归档 |
| R14 | 历史预检、迁移及其他具有真实进度事实的长任务必须显示进度条；未知总量阶段不得伪造百分比 | user:progress-bars-plan-a-2026-08-27 | satisfied | Historical Campaign 使用集合式 PostgreSQL 聚合持久化预检/迁移进度并通过 Pydantic/OpenAPI/generated client 返回；发现阶段显示不确定进度；Analysis Run 使用活跃详情中的 Shard 进度并以冻结目标总数为分母；Excel 导出和 Collection Scope 复用现有真实进度。Contract/API/PostgreSQL、Frontend、Browser Mock 与真实 Full-stack 均通过 |
| R15 | 页面统一为“导入数据”；本地文件/文件夹与批准服务器目录采用不同来源获取方式，Artifact 后共用 Campaign 管线；来源与标准观察/历史只补空策略解耦；旧单文件接口兼容保留 | user:unified-data-import-approved-2026-08-27 | satisfied | Pydantic/OpenAPI/generated client 提供 `data-import-*` 统一 Contract；本地清单/逐 Item 流式上传/finalize 与服务器批准目录均进入同一 Campaign/Artifact/预检/Chunk/Job/账本；Worker 按冻结策略分派标准观测或历史补空；页面只有一个“导入数据”入口；旧 `/api/v1/import-batches` 与 `/historical-import-*` 回归保持兼容。真实 Full-stack 3 passed，Browser Mock 31 passed |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 最终 Stage 12 目标组 67 passed、1 skipped，容量 Harness 1 passed；完整 Python 套件在 Windows 为 975 passed/8 skipped/3 个 POSIX-only `prepare_host` 失败，同 3 个用例在 Linux 镜像补验为 3 passed；前端 Vitest 10 files / 44 tests passed |
| Contract / Generated Client | required | 完整 Contract/API 124 passed；OpenAPI 与 TypeScript Client 由生成脚本刷新，`generate.py --check` 和兼容检查均退出码 0 |
| Backend/API/PostgreSQL Integration | required | 专用 `aima_ugc_stage12_test` 执行最终目标组 67 passed/1 skipped；新增回归证明 `uploading` 可取消并直接终止 Source Item，取消后的晚到上传返回 409 且 Artifact 数保持 0；本轮完整 Migration 生命周期 13 passed，真实开发库为 `20260827_0029 (head)` 且 no drift |
| Browser Mock Acceptance | required | 最终完整 Browser Mock 31 passed；覆盖单一入口、本地/服务器来源、写入策略、预检/迁移进度、上传中取消、start/conflict/cancel/retry、Analysis Run、Excel 导出与 Collection Scope |
| Real Full-stack Golden Path | required | 全新隔离数据库上的统一导入真实 Browser/Vite/API/PostgreSQL/Worker/Fake LLM 3 passed：本地标准观测入库与 Voice Plaza、错误表头预检拒绝、服务器历史补空故障重试/冲突不覆盖/Voice Plaza/两次 Analysis Run Current 顺序均通过；没有自动 Analysis Job |
| Real Provider Probe | not_applicable | 历史导入不调用 Provider；真实 AI Probe 只有需要确认当前模型事实时才有界执行，普通 CI 不需要 |
| Build / Package / Runtime | required | 最终前端 lint/typecheck/build 均退出码 0，Vite 构建 115 modules；Compose Windows 合并配置、API/Worker/Frontend 镜像、`backend.py --validate-only` 和源码开发 Frontend/API/Worker 已验证；Migration 与正式进程由真实 Full-stack 接线验证 |
| Capacity / Recovery | required | 10 万/100 万报告完整并逐行对平；500 万依正式决定延期。恢复专项覆盖 Source Artifact 复用、失败重试、排队取消、Lease 接管/Fencing、重复执行和终态对账 |
| Docs / Governance / Other | required | Docs Skill 同步长期文档/模块 README/运行手册及 `uploading` 取消语义；架构、Owner、Secret、Docs、Ruff format/check、Mypy、Contract 生成检查与 `git diff --check` 通过；Ready Check 通过；最终远端 `main` CI 正在按 R13 授权进入集成步骤 |

# 完成阶段两阶段 Review

## Review A：上游要求 → 方案/Change

从用户当前决定、用户提供的参考材料和仓库正式事实重新建立完成定义，已覆盖：V1-B 完成状态、Stage 12 优先级、网页服务器目录、4000 万容量目标、方案 A 不覆盖语义、逐行对账、导入/AI 解耦、手工重复 AI、现有架构复用、分层验证和生产写授权边界。参考材料被明确标为设计输入，没有当作用户指令或当前实现事实。

结论：当前 Change 已映射全部已确认 Requirement，包括后续确认的方案 A 进度展示；实现、测试、文档和正式延期事实均有对应证据，没有未满足 Requirement。

## Review B：方案 → 当前代码/风险

Review A1 重新读取用户已确认决定、Roadmap 02/03、Blueprint 07 和当前机器事实，独立重建了目录安全、不可变快照、方案 A、逐行对账、恢复、公平调度、AI 解耦/Run Current、兼容、容量与授权边界；R1—R13 没有遗漏。500 万演练仍有明确延期依据，Git 边界已更新为用户批准的分批直推 `main`，PR 不适用，远端 CI 只能在实际推送后记录。

Review A2 正反向审计了 `Directory Browser → Campaign → Source Artifact → Chunk Artifact → Job → Content Owner → outcome/conflict → Campaign 页面/Voice Plaza`，以及 `声音广场动作 → Preview/Create → Planner → Target/Shard → Result → Current/历史状态`。后端动作均有页面入口或明确兼容入口，页面按钮/轮询状态与后端状态机一致；导入链没有 Analysis Job 副作用。

代码质量 Review 发现并修复四项 MEDIUM：前端在 `cancelling` 时停止轮询、source_file 因 `ordinal IS NULL` 绕过唯一约束、0026 downgrade 的 CheckConstraint 名被命名约定二次展开、Jobs 集成 Fixture 直接 DELETE 被 Stage 12 外键阻断。每项均先取得失败证据，再由 Coding 修复并通过目标/相关回归。

修复后 re-review 没有未解决的 BLOCKER/HIGH/MEDIUM Finding。一个 LOW 运行限制是目录 Cursor 只限制响应、不限制该层扫描/排序内存；本轮不扩张公共 Contract，已按 Docs Skill 明确要求批准根为专用且单目录子项有界，超出时另行做容量/Contract 决策。

进度增强的需求符合性 Review 反向追踪了 `Campaign Source/Chunk/Job → 聚合 Contract → 页面`、`Analysis Run/Target/Shard → 活跃详情 → 页面`、`Export Job → 页面` 和 `Collection Scope → 页面`。发现阶段没有可靠总量，使用不确定进度；其余百分比只来自持久化计数，不用前端计时器或模拟值。迁移失败/取消行计入“已处理终态”而不冒充成功，Analysis 未进入当前有界调度窗口的目标按 0% 计入冻结总量。

代码质量 Review 发现并修复三项进度问题：Analysis Run 列表为控制 Payload 不含 Shard，导致活跃 Run 仅按列表计算时恒为 0%；以已调度 Shard 合计为分母会在新 Shard 出现时产生进度倒退；Historical Campaign 两个聚合子查询未按本次 Campaign ID 集合过滤，会随历史总量扩大扫描。Coding 分别补充活跃 Run 详情读取、以不可变 `run.target_count` 为分母、以及聚合子查询集合过滤；目标测试先取得失败证据，修复后通过 Contract/API/PostgreSQL、Frontend、Browser Mock 和真实 Full-stack。re-review 未发现新的 BLOCKER/HIGH/MEDIUM Finding。活跃 Run 最多会按列表返回数量产生额外详情请求，但只轮询非终态 Run，且当前分页上限有界；这是复用现有 Contract 的已知低风险权衡，不扩张为第二套进度接口。

本轮继续任务时，真实页面暴露出源码开发 launcher 未传递 `AIMA_HISTORICAL_IMPORT_ROOT`。Review 先确认 Compose 已正确注入并只读挂载、后端目录安全逻辑与 HTTP Contract 无缺陷，再以失败回归证明根因为开发启动链路。Coding 仅补充配置解析、API/Worker 环境传递、默认目录创建和模板/本机配置；Docs targeted review 修正了配置变更与新增文件的重启边界，并补齐 `.runtime/historical-input` 运行目录事实。修复后 re-review 未发现新的 BLOCKER/HIGH/MEDIUM Finding。

本轮故障 Review 以现场 Worker 栈、SQLAlchemy 最小编译实验和真实 PostgreSQL Red 回归独立确认：`_new_content_values` 与 `_author_values` 返回的稀疏 dict 列集不一致，导致 SQLAlchemy 无法编译多行 INSERT。Coding 把新 Content/Author 的可选列形状固定，未观测值显式保持 `NULL`；这些列没有服务端默认，因此不改变新行语义，也不进入已有非空字段覆盖路径。修复后 re-review 检查了 NULL/非空、URL 序列化、Author 合并、ON CONFLICT 与批量往返上界，未发现新的 BLOCKER/HIGH/MEDIUM Finding。

统一导入 Completion Review 从上游重新追踪了 `本机选择/服务器相对路径 → Source Artifact → Campaign 预检 → Chunk/Job → 策略分派 → Content Owner → 账本/冲突 → 页面/Voice Plaza`，并反向检查了单一页面入口的创建、上传、finalize、start、cancel、retry 和兼容 Route。`source_kind` 与 `ingestion_policy` 分别冻结且互不推导；`server_path + historical_fill_only` 才承载 4000 万容量承诺；旧 `/api/v1/import-batches` 与 `/historical-import-*` 仍有 Contract/API 回归，generated client 只由正式生成器维护。

统一导入代码质量 Review 发现并修复两项 MEDIUM：本地上传失败会使 Campaign 永久停在 `uploading` 且前后端不能取消；取消后晚到上传虽返回 409，仍会先创建未绑定 Artifact。Coding 先分别取得 `409 instead of cancelled` 与 `Artifact count 1 instead of 0` 的 Red 证据，再实现上传阶段直接终止 Campaign/Source Item、前端启用取消，以及在流式存储前检查 Campaign/Item 状态。目标 PostgreSQL/API 与 Browser 测试转绿，相关 Stage 12 目标组 67 passed/1 skipped；最终 re-review 未发现新的 BLOCKER/HIGH/MEDIUM Finding。保留的 LOW 限制仍是批准目录单层扫描需有界部署，不改变公共 Contract。

本轮后端启动 Review 通过用户现场栈与真实开发库目录事实确认两项 HIGH 和一项 MEDIUM：早期 0026 开发草稿产生的二次前缀约束名使 0028 按正式名称删除时阻断启动；同一旧库还遗留 4 个截断约束名并缺少 Source Manifest 唯一索引；Windows 安全软件注入的不可写 `SSLKEYLOGFILE` 又会使 Python 3.14 `urllib` 在本地 HTTP readiness 检查时初始化 HTTPS 上下文并崩溃。Coding 先分别取得 PostgreSQL Migration、真实 launcher 和元数据契约 Red 证据，再让 0028 兼容阻塞约束旧名、以 0029 前向收敛其余旧对象、同步 Owner 元数据表达式，并改用纯 HTTP readiness 且只从本地子进程环境移除 keylog 变量。修复后完整 Migration 生命周期 13 passed、相关 Unit 19 passed/1 skipped，真实开发库迁到 0029 且无漂移，完整 API/Worker 启动与独立 readiness 均成功；re-review 未发现新的 BLOCKER/HIGH/MEDIUM Finding。

运行验证过程另发生一次本地操作事故：首次直接执行 PostgreSQL Integration 时误连当前开发库，现有 Fixture 的 `TRUNCATE ... CASCADE` 清除了该本地开发库中的 Job/Artifact/Account 及级联业务数据。发现后立即停止对开发库跑测试，创建专用 `aima_ugc_stage12_fix_test` 库完成后续验证；原始 Excel、文件快照和 Chunk Artifact 物理文件仍在，本轮按原输入重建并完成了 75,279 行 Campaign。未被修改的旧 Windows Compose volume 仍保留，并另建了已停止的恢复检查克隆 `aima-ugc-recovery-inspect-20260827`；其中可见 4 条 Content、1 个 Job、1 个 Artifact，但未经用户决定不擅自合并回当前开发库。

## 首次 main CI 修复专项 Review

永久 Workflow 的触发事件、Job/check 名称、权限、并发和依赖图均未改变；只同步 Stage 12 已新增但测试期望遗漏的运行边界，并让容量测试自行建立隔离依赖。

| 原证明责任 | 原位置 | 修复后位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| Windows overlay 的数据、日志、Secret 和 PostgreSQL 存储模型 | Runtime Acceptance / `Validate Windows overlay storage model` | 同一步骤，新增历史输入 bind 的来源、类型和只读断言 | 保持并增强 | 原有目标集合和类型断言全部保留，新增 `/data/aima-historical-input`；本地按同一 Compose JSON 模型验证通过 |
| Historical 容量 Harness 必须运行生产 Campaign/Worker 且只能清理专用库 | CI / `tests/integration/ingestion/test_stage12_historical_capacity_harness.py` | 同一测试、同一 benchmark，增加唯一临时容量库创建、Migration 和清理 | 保持并增强 | 不改 benchmark、行数、Chunk 或业务断言；完整 Ingestion 组 `17 passed` |

Review A1/A2 结论：两项修复不改变公共 Contract、Schema、权限、安全或生产数据语义，没有新增上游决策；代码质量 re-review 未发现 BLOCKER/HIGH/MEDIUM Finding。测试库名仍强制以 `_stage12_capacity` 结尾，清理仍由生产基准的 fail-closed 检查保护；临时库在测试结束时终止连接并删除。

# Completion Audit

- [x] upstream_re_read：重新读取用户决定、Roadmap 02/03、Blueprint README/04/07 和当前机器事实，独立重建软件完成、服务器容量演练、Git 集成与生产执行四个不同边界。
- [x] change_coverage：逐项复核 R1—R15；R1—R6、R8—R15 已满足，R7 的服务器 500 万/等效比例演练有明确上游延期依据，没有 `not_satisfied`；最终远端 CI 与归档是当前交付步骤，不改变产品 Requirement 状态。
- [x] reverse_audit：正反向核对本机/服务器来源获取、Artifact/Campaign 公共管线、策略分派、兼容入口、单一页面入口、Voice Plaza 与 Analysis Run；前端动作均有后端真实能力，后端公共能力均有页面或明确兼容消费者。
- [x] unresolved_cleared：本轮后端真实启动暴露的 0028/旧开发库 Schema 兼容、Windows readiness 和 Owner 元数据漂移均已按 Red→Green 修复并 re-review；无未解决的 BLOCKER/HIGH/MEDIUM Finding。

# 分步任务

- [x] 固化 Roadmap 03、方案 A、Internal V1-B 状态和当前 L3 Active Change。
- [x] 恢复当前实现、Git、Active Change、版本和测试事实。
- [x] Stage 12A：先建立失败测试和实际数据剖析，再实现 Historical Fill-Only 与逐行账本/批量入口。
- [x] Stage 12B：完成安全目录 Browser、Campaign、不可变快照/预检、Chunk 调度、网页闭环和 Lease/终态恢复专项。
- [x] Stage 12C：完成 selected-only Analysis Run/Shard、重复历史、Current 投影和网页；真实付费 AI Gold Set/查询范围按批准边界延期。
- [x] Stage 12D：完成本机 10 万/100 万容量报告、故障恢复、部署/运行手册和软件交付门禁；公司服务器 500 万/等效比例演练及生产 Go/No-Go 明确延期。
- [x] 同步所有受影响正式文档、OpenAPI/generated client 和 Migration 说明。
- [x] 运行所有不依赖 Git/生产授权的 required Validation Matrix 验证与仓库质量门禁。
- [x] 重新读取上游并完成 Completion Audit。
- [x] 执行需求符合性与代码质量两阶段 Review；四项 MEDIUM 修复后已 re-review。
- [x] 修复源码开发 launcher 漏传历史根目录配置的问题，并同步 `env.local`、配置模板、运行文档与回归测试。
- [x] 修复真实历史 Chunk 中 Content/Author 稀疏字段导致多行 INSERT CompileError 的问题，并按原输入完成 75,279 行本地迁移。
- [x] 按方案 A 实现 Historical Campaign 持久化进度 Contract、统一可访问进度组件，并接入 Analysis Run、Excel 导出和 Collection Scope；完成生成、文档、分层测试与 Review 修复。
- [x] Red：建立统一导入 Contract、本地上传暂存、策略分派、兼容入口和 Browser 工作流失败测试。
- [x] Green/Refactor：实现来源与写入策略解耦、Artifact 后共用 Campaign 流水线和单一“导入数据”页面入口。
- [x] 同步 Blueprint、Roadmap、Appendix、模块 README、OpenAPI/generated client，并完成新的 Completion Audit 与两阶段 Review。
- [x] 修复真实后端启动的 0028 旧约束名、0029 Schema 收敛、Windows `SSLKEYLOGFILE` readiness 崩溃和 Owner 元数据漂移，并完成真实启动复验。
- [x] 修复首次远端 `main` 集成暴露的 Runtime Windows overlay 挂载断言漂移，以及容量 Harness 依赖本机预置数据库的问题；本地按远端同范围复验通过。
- [ ] 按用户授权把功能批次推送到远端 `main`，取得最终 HEAD 的新鲜 CI 证据，再按规则归档 Change；PR 不适用。
- [ ] 只有获得独立生产写授权后，才执行实际 4000 万 Campaign 和全量对账。

# 验证

## 计划

- 目标测试：Historical Fill-Only、逐行 outcome、路径逃逸、Campaign/Item 状态、幂等/断点、Run Current/Shard。
- 相关测试：现有 Import、Content、Collection、Analysis、Job Runtime、API、Contract、Frontend。
- 数据库：Alembic upgrade、PostgreSQL 集合式写入、并发竞态、旧 Analysis 回填。
- 浏览器：Browser Mock 广覆盖 + Real Full-stack 少量 Golden Path。
- 容量/恢复：本机 10 万→100 万；公司服务器生产前 500 万或批准的等效比例演练；kill Worker/Lease 接管/取消/重试。
- 静态/构建/治理：按当前 CI 加架构、Owner、Secret、Docs、Ready Check。
- Ready Check：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- Stage 12 目标套件（Directory、Planner、Contract、API、Historical PostgreSQL/Worker/Recovery、Analysis Run、Capacity Harness）：`46 passed, 1 skipped`；唯一跳过是当前 Windows 账户不能创建测试 Symlink，随后在已构建 Linux Backend 镜像补验真实 POSIX Symlink，输出 `POSIX symlink rejection passed`。
- 完整 Python Unit：Windows `669 passed, 8 skipped, 3 failed`；3 个失败均为 `tests/unit/test_prepare_host.py` 对 Linux/POSIX `os.geteuid/os.chown` 的平台前提，同 3 个用例在已构建 Linux Backend 镜像只读挂载仓库后 `3 passed`。
- 完整 Contract `86 passed`；完整 API `37 passed`；PostgreSQL Integration 分组共 `170 passed`（platform 1、database 20、jobs 13、collection 90、content 31、ingestion 15）。
- Frontend Vitest `9 files / 41 tests passed`；Browser Mock `29 passed`，其中 Historical Migration `6 passed`；真实 Full-stack `6 passed`，Stage 12 历史迁移/重复 Analysis Run 路径通过。
- `ruff format --check backend tests scripts`：523 files already formatted；`ruff check`：All checks passed；`mypy backend/src`：254 source files 无问题。
- `alembic downgrade 20260826_0025` 后 `upgrade head` 成功；`alembic current` 为 `20260826_0027 (head)`；`alembic check` 为 `No new upgrade operations detected`。
- 重新运行 OpenAPI/Pydantic 与 Orval TypeScript Client 生成，生成前后文件哈希一致；Contract generation `--check` 与兼容检查通过。
- `npm run lint`、`npm run typecheck`、`npm run build` 均退出码 0；Vite 构建 115 modules。
- `docker compose -f compose.yaml -f compose.windows.yaml config` 通过；API、Worker、Frontend 镜像构建通过；真实 Full-stack 使用隔离数据库/API/Worker/Fake LLM 运行后已停止测试进程。
- 架构、表 Owner、Secret、Docs 四项质量门禁均退出码 0；`git diff --check` 退出码 0。
- 10 万报告：169.539 秒、589.836 rows/s、峰值 RSS 163,909,632 bytes、逐行对平、普通 Job 探针通过；100 万报告：1594.708 秒、627.074 rows/s、峰值 RSS 171,171,840 bytes、逐行对平、普通 Job 探针通过。500 万两次未完成，按 R7 正式延期，未计为通过。
- `python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`：退出码 0，`gated=44 / strict=44 / legacy=72`。
- 本轮源码开发配置补漏先以目标测试得到 `1 failed`（`LocalDevConfig` 缺少 `historical_import_root`），实现后目标/相关回归为 `28 passed, 2 skipped`；Ruff format/check、`mypy scripts/dev/local_runtime.py backend/src`、`backend.py --validate-only` 均退出码 0。
- 本轮实际启动源码 Frontend/API/Worker 后，目录 API 返回 HTTP 200、`available=true`；内置浏览器打开服务器历史迁移弹窗，未配置错误计数为 0，并显示批准根目录当前为空的真实状态。
- 本轮稀疏批量回归在修复前得到 2 failed，与现场一致地分别触发 `contents.title` 和 `accounts.display_name` CompileError；修复后目标 2 passed，完整文件 5 passed。
- 本轮在专用 `aima_ugc_stage12_fix_test` 库重新迁移到 `20260826_0027 (head)` 且 `alembic check` 无漂移；Stage 12 目标矩阵 48 passed/1 skipped，完整 Content/Ingestion PostgreSQL Integration 48 passed。
- 本轮实际重建并启动本地 Campaign `1c1ac489-17f8-4096-a6fa-6458f2d8deda`：75,279 行全部终态为 created 25,885 / filtered 49,393 / duplicate 1，76 个 Chunk 全部 `succeeded`、0 失败 Job、0 Analysis Job；API 与 Frontend 均为 HTTP 200，内置浏览器显示相同结果。
- 本轮 Ruff format/check、Mypy、架构、表 Owner、Secret、Docs 与 `git diff --check` 均退出码 0。
- 本轮 `uv run python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready` 退出码 0：`gated=44 / strict=44 / legacy=72`。
- 进度增强 Red 证据：Contract 在缺少 `progress` 时被 extra/required 校验拒绝；统一进度组件尚不存在时组件测试失败；Analysis 活跃 Run 测试确认列表不含 Shard 时未读取详情而失败。实现后最终 Frontend Vitest `10 files / 44 tests passed`，Browser Mock `30 passed`。
- 进度增强后在专用 `aima_ugc_stage12_fix_test` 库执行 Stage 12 目标矩阵 `49 passed, 1 skipped`，唯一跳过仍为当前 Windows Symlink 权限；历史 Campaign Integration `9 passed`，完整 Contract/API `124 passed`。
- 进度增强后的真实 Full-stack 在全新专用数据库 `aima_ugc_stage12_progress_fullstack_test_3` 上以真实 Browser/Vite/API/PostgreSQL/Worker/Fake LLM 运行，关键 Analysis Run Golden Path `1 passed`；API 日志可见页面对活跃 Run 调用详情端点并读取真实 Shard 进度。
- 最终 `npm run lint`、`npm run typecheck`、`npm run build` 均退出码 0，Vite 构建 118 modules；`ruff format --check` 为 523 files already formatted，`ruff check`、Mypy 254 source files、Contract 生成检查、兼容检查、架构、表 Owner、Secret、Docs 与 `git diff --check` 均退出码 0。
- Progress Completion Audit 写回后，最终 Docs 门禁退出码 0；`uv run python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready` 退出码 0：`gated=44 / strict=44 / legacy=72`。
- 统一导入最终目标组在专用 `aima_ugc_stage12_test` 数据库执行 `67 passed, 1 skipped`；容量 Harness `1 passed`。最终 Migration 当前为 `20260827_0029 (head)`，`alembic check` 无漂移。
- 上传取消 Review Red 证据：修复前取消 `uploading` Campaign 返回 409；第一轮修复后取消成功但晚到上传使 Artifact 数从 0 变 1。最终实现使 Campaign/Source Item 同事务进入 `cancelled`，晚到上传返回 409 且 Artifact 数保持 0；目标 PostgreSQL/API `1 passed`，Browser `1 passed`。
- 统一导入最终 Frontend Vitest `10 files / 44 tests passed`，完整 Browser Mock `31 passed`；lint/typecheck/build 退出码 0，Vite 构建 115 modules。
- 统一导入真实 Full-stack 在全新专用数据库上执行 `3 passed (27.9s)`：本地标准观测、错误表头预检拒绝、服务器历史补空故障重试/冲突不覆盖/Voice Plaza/两次 Analysis Run 均通过。API、Worker 与 Fake LLM 测试进程已停止，8090/8091 无监听。
- 最终 Ruff format 为 523 files already formatted，Ruff check、Mypy 254 source files、Contract 生成检查、架构、表 Owner、Secret、Docs 与 `git diff --check` 均通过；最终 Ready Check 退出码 0：`gated=44 / strict=44 / legacy=72`。
- 后端启动故障 Red 证据：真实开发库在 0027 执行 0028 时因不存在正式约束名触发 `UndefinedObject`；兼容回归修复前同样失败，修复后正式/旧名升级与降级保护 3 passed。真实库随后成功迁到 0028。
- Windows readiness Red 证据：系统 `SSLKEYLOGFILE=C:\nss_ssl_sfagent.log` 不可写，迁移修复后完整 launcher 在 `urllib` 初始化 TLS context 时触发 `PermissionError`；两个最小回归修复前均失败，改用纯 HTTP readiness 并净化子进程环境后 2 passed。
- Schema re-review Red 证据：Owner 元数据不包含 `standard-observation.v1`，契约测试修复前失败；同步 0028 表达式后完整 Schema 文件 3 passed。真实开发库另有 4 个开发期截断约束名和缺失 Source Manifest 唯一索引，0029 回归修复前因 revision 不存在失败，修复后通过。
- 最终相关 Unit `19 passed, 1 skipped`（跳过项为当前 Windows 账户不能创建测试 Symlink）；完整 Migration 生命周期 `13 passed`。真实开发库 `20260827_0029 (head)`，`alembic check` 为 `No new upgrade operations detected`。
- 最终 `uv run python scripts/dev/backend.py` 已实际启动 API 与 Worker，Uvicorn 监听 `127.0.0.1:8090`，launcher 和独立请求两次取得 `/health/ready` HTTP 200；响应确认 database、artifact_store、log_directory 均为 `ok`。验证用 API/Worker 已停止，未启动任何历史 Campaign 或 AI Job。
- 本轮 Ruff format 为 523 files already formatted，Ruff check 全通过，Mypy `backend/src + scripts/dev/local_runtime.py` 检查 255 个 source file 无问题，`git diff --check` 退出码 0。
- 后端启动修复写回 Completion Audit 后，架构、表 Owner、Secret、Docs 四项质量门禁均退出码 0；最终 Ready Check 退出码 0：`gated=44 / strict=44 / legacy=72`。
- 首次推送远端 `main` HEAD `2e09142409245e379b018095fe5a38062a7cdc32` 后，Change Completion Gate、Full-stack Acceptance、Developer Tooling Compatibility 和 CI 的 Repository Quality 成功；Runtime Acceptance 因永久 Workflow 未把新增只读 `/data/aima-historical-input` 纳入 Windows overlay 精确挂载集合而失败，CI PostgreSQL Ingestion 因容量测试硬编码了 CI 不存在的本机预置数据库而失败。这两项是远端真实 Red 证据，未被重跑或跳过掩盖。
- 修复后，Windows overlay Compose JSON 的 bootstrap/postgres/backend 精确挂载集合通过，历史目录为只读 bind；容量 Harness 改为每次创建唯一专用临时库、迁移到 head 并在完成后删除，与远端相同的完整 Ingestion PostgreSQL Integration 为 `17 passed`。Workflow/测试修复不改变业务 Contract、Schema 或生产迁移语义，最终远端新 HEAD CI 仍待推送后取得。

# 文档影响

- Docs Impact：`full`，覆盖本 Change 引起的 Roadmap、Blueprint、Appendix、模块 README、运行部署、代码导航和用户行为；只修改真实受影响文件。
- Roadmap 03 保留批准语义并同步为“软件工作区已完成本地验收，待 Git 集成、公司服务器容量演练和生产授权”；不写成已合并或 4000 万实际迁移完成。
- Internal V1-B 状态依据用户明确确认更新；仓库没有服务器执行明细时必须保留这一证据边界。
- 本轮 Docs Impact：`targeted`；同步源码开发 `env.local` 配置、默认历史输入目录、API/Worker 传递、重启边界和 `.runtime` 目录清单，没有复制 HTTP Contract 或新建第二套运行方案。
- 本轮稀疏批量修复 Docs Impact：`not_applicable`；公共 Contract、Schema、配置、用户流程和已批准历史只补空语义均未改变，现有 Roadmap/Blueprint/Appendix 已描述目标行为，只需在本 Change 记录现场缺陷与验证证据。
- 本轮进度增强 Docs Impact：`targeted`；同步 Blueprint 04、Roadmap 03 与历史迁移/Analysis Run 运行手册，说明确定/不确定进度语义、失败/取消终态计数、Analysis 冻结目标分母和活跃详情读取，不复制第二套 Contract。
- 本轮统一导入 Docs Impact：`full`；同步单一页面入口、本机/服务器来源边界、独立写入策略、`data-import-*` 主 Contract、旧接口兼容、0028 Migration、4000 万容量适用组合和当前交付状态。上传取消修复后再按 Docs Skill `targeted` 更新 `uploading → cancelled` 与晚到上传边界。
- 本轮后端启动修复 Docs Impact：`targeted`；业务 Contract、用户操作和已批准数据语义未改变，长期运行文档的 `backend.py → alembic upgrade head → readiness` 流程仍然正确；只在当前 Change 同步 0029 当前 head、旧开发 Schema 收敛原因和真实启动证据，不复制约束清单形成第二套 Schema。
- 本轮旧视觉资产清理 Docs Impact：`targeted`；删除已获授权的一次性 PNG/JPG 二进制文件，并同步 `docs/guides/01_Figma与前端设计开发工作流.md` 与 `frontend/README.md`，使现行文档不再指向不存在的资产；归档 Change 仅保留历史采用事实。
- 本轮首次 main CI 修复 Docs Impact：`not_applicable`；只同步永久 Runtime Workflow 的既有挂载责任与容量测试数据库隔离，产品行为、HTTP Contract、Schema、部署操作和用户文档均未改变，验证与失败证据记录在当前 Change。

# 交付

- Commit：已在 `main` 创建 `7ed798de`（后端与 Migration）、`48e026a0`（统一导入前端与进度）、`e8d7ace4`（本地运行与全栈环境）、`2e091424`（文档与交付记录）；首次 main CI 修复随当前提交。
- PR：不适用；用户明确要求按功能分批直接提交到远端主分支。
- CI：首批 4 个提交已推送到 `2e091424`；该 HEAD 的 Change Completion、Full-stack、Developer Tooling 和 Repository Quality 成功，Runtime 与 PostgreSQL Ingestion 的两项真实失败已按 Red→Green 修复并随当前 CI 修复批次提交；最终新 HEAD 结果待推送后读取，不伪造成功。
- 发布：未授权、未执行。
- 生产 4000 万迁移：未授权、未执行。
