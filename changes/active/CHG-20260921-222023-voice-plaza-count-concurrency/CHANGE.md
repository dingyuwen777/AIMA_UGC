---
schema: coding-change/v1
id: CHG-20260921-222023-voice-plaza-count-concurrency
title: 声音广场筛选总数独立加载与可观测性
level: L2
status: ready_for_review
owner: codex
branch: fix/voice-plaza-count-independent-loading
created: 2026-09-21
updated: 2026-09-21
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - product
  - documentation
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/product_http.py
  - backend/src/aima_ugc/bootstrap/voice_plaza_observability.py
  - tests/unit/content/
  - docs/blueprint/04_后端任务API与前端.md
  - docs/operations/04_声音广场读模型回填与性能验证.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：声音广场页面目前必须等待列表请求结束后才启动总数请求；列表慢时，即使投影计数很快，总数也会被同样延迟。总数失败、投影未就绪和零结果又被页面收敛成相近或不可见的状态，难以验证实际效果。
- **拟议修改**：列表与同一筛选快照的总数请求独立启动；过期总数请求取消并继续保留 revision 防护；总数状态在列表为空时也可见；后端为 Count 增加与既有声音广场读取一致的安全耗时日志。现有投影回填、索引、API Contract、Schema、Migration 和筛选语义不变。
- **预期结果**：总数显示时间不再包含列表耗时，列表也不等待总数；用户能区分统计中、投影准备中、请求失败和可靠的零/非零总数；服务器日志可以分别测量列表与 Count。

# 背景、现状与问题

## 背景

Issue #551 的 AC8 仍等待 1,823,565+ 条真实服务器数据验收。PR #554 已提供投影精确 Count、回填索引和有界回填；用户进一步确认总数不能被慢列表串行拖延，并授权实现后合并主分支。

## 当前现状

- `VoicePlazaPage.refreshPage/search/reset` 都先 `await store.refresh()`，之后才调用 `store.refreshCount('estimated')`。
- Store 已用独立 `countRevision` 防止迟到结果覆盖当前筛选，但未取消已经过期的 HTTP Count 请求。
- 页面只在 `items.length > 0` 时显示筛选区下方总数，因此准确的 `0` 结果不会出现；`countError` 没有用户可见表达。
- 后端 Count 在投影 `ready` 后复用与列表一致的筛选 SQL 返回精确总数，但没有 Count 专属阶段耗时和 `projection_ready` 日志。

## 问题、根因或约束

可观察延迟由前端串行编排造成：`T(总数可见)=T(列表)+T(Count)`。直接使用应用层多进程不会缩短单条 PostgreSQL Count，反而可能增加数据库竞争；正确边界是让两个独立 HTTP 请求并发启动，同时依靠投影、取消过期请求和后端观测控制资源风险。

## 不修改的后果

当列表需要数秒时，总数即使很快也必须等待；连续筛选会留下无价值的旧 Count 请求；用户无法区分投影尚未准备和真实请求失败，也无法在空结果时确认总数为零。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 页面在三个入口都先等待列表再启动 Count | `VoicePlazaPage.vue` 的 `refreshPage/search/reset` | Count 必须从列表 await 链中解耦 |
| E2 | Store 已隔离 Count 状态并用 revision 丢弃迟到结果 | `frontend/src/features/voice-plaza/store.ts` | 复用现有状态，不建立第二套请求管理 |
| E3 | 投影 ready 后 Count 在窄投影上复用列表筛选返回精确值 | `content_product.py`、`content_queries.py`、PostgreSQL 集成测试 | 保持后端计数语义，不退回慢旧查询 |
| E4 | 页面隐藏零结果总数且不渲染 `countError` | `VoicePlazaPage.vue` 的两个 Count 区域 | 必须补齐零值和失败状态 |
| E5 | 现有声音广场读取日志覆盖 list/filter_options/detail/comments，不覆盖 count | `content_http.py`、运行手册 | 增加同一日志契约的 Count 观测 |

## 推断与待确认

- **待确认**：并发后的生产列表/Count P50/P95、数据库 CPU/IO 和投影实际状态只能在新 revision 部署后通过 #551 / AC8 验证；本 Change 不用本地小数据宣称生产性能已经通过。

# 目标、成功标准与非目标

## 目标

让列表和筛选总数独立、可取消、可观察地加载，使慢列表不再推迟总数开始时间，同时不改变计数准确性或阻塞列表。

## 成功标准

- [x] 页面进入、查询和重置时，列表与 Count 使用同一已应用筛选快照独立启动。
- [x] Count 完成或失败都不阻塞列表；新筛选取消旧 Count，并继续拒绝迟到结果。
- [x] 页面在空列表时也显示统计状态，准确展示 `共 0 条`，并区分准备中、请求失败和可靠总数。
- [x] Count 日志包含总耗时、配置读取耗时、数据库查询耗时、投影就绪状态和筛选形状，不记录筛选值或正文。
- [x] 现有 HTTP Contract、Schema/Migration、依赖、列表筛选和投影回填语义保持不变。
- [x] 目标回归、前端构建、Contract 漂移检查和独立 Review 已通过；PR CI 与合并按交付状态继续执行。

## 范围

- 声音广场页面与 Store 的列表/Count 请求编排、Count 取消和状态展示。
- Count 后端安全耗时日志及其单元回归。
- 目标前端测试、相关文档和交付治理。

## 非目标

- 不用应用层多进程拆分一次 Count 查询。
- 不新增缓存、Redis、搜索引擎、后台进程、数据库对象或依赖。
- 不修改 Count HTTP 字段、筛选语义、列表排序、Cursor 或权限。
- 不在本次执行生产部署、Migration、数据操作或伪造真实服务器性能结论。

## 必须保持不变

- PostgreSQL 写模型仍是唯一业务事实，声音广场投影仍是可重建派生读模型。
- 投影未 ready 时，筛选 Count 不返回不可靠的部分总数。
- 列表、Count、导出和分析继续消费同一已应用筛选快照。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 页面/Store 负责并发与取消，Content/Product 负责 Count 与日志 | E1–E5 | 不把前端状态塞进列表 Contract |
| 接口与契约 | 公共 HTTP 字段不变 | #551 / AC12 | 无 OpenAPI/生成 Client 变化 |
| 数据与迁移 | 不修改 Schema/Migration/数据 | E3 | 继续使用 0054/0055 投影和索引 |
| 错误与失败语义 | Count 失败独立展示和重试，不覆盖列表 | #551 / AC10 | 列表可正常浏览 |
| 兼容性 | 保持筛选、排序、分页和 Count 准确性 | #551 / AC9–AC12 | 仅改变启动时序和状态表达 |
| 部署与回滚 | 普通应用发布；回滚本次代码即可恢复旧编排 | 无 Schema/配置变化 | 无数据回滚 |

# 修改方案与决策依据

## 最小充分方案

1. 在 Store 建立一个“列表与 Count 同时启动、只等待列表”的公开动作，三个页面入口统一复用。
2. Count 请求通过现有生成 Client 的 `RequestInit.signal` 支持取消；新 Count 启动前取消旧请求，同时保留 revision 和筛选快照双重提交守卫。
3. 筛选区下方 Count 状态不再依赖 `items.length`；新增失败重试和投影 building 文案，分页区复用同一状态语义。
4. 抽取既有声音广场读取耗时日志 helper，让 list/filter/detail/comments/count 使用同一事件和 500ms 阈值；Count 只记录布尔筛选形状。
5. 用失败测试证明修复前 Count 等待列表、零值/错误不可见和 Count 日志缺失，再完成实现、相关回归、构建、文档与 CI。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：请求并发而非 Count 前置或应用多进程 | E1、E3 | 去掉串行等待，同时让数据库继续决定单条查询执行计划 |
| D2：取消 + revision 双重保护 | E2 | 取消减少无价值负载，revision 处理取消已晚或实现不支持取消的竞态 |
| D3：复用统一日志事件 | E5 | 保持运维查询方式稳定，不引入第二套日志协议 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 列表与同一筛选快照总数独立启动、互不等待 | #551 / AC9 | satisfied | `refreshResults` 先调用列表再立即启动 Count；Store 回归与 Playwright 慢列表场景均证明 Count 不等待列表 |
| R2 | 取消/丢弃过期 Count，失败不影响列表，页面区分状态并显示零 | #551 / AC10 | satisfied | AbortSignal + revision/快照守卫；Store、SSR 页面回归覆盖迟到结果、失败隔离、零值、准备中和重试状态 |
| R3 | 投影精确 Count 具备不泄露筛选值的阶段耗时观测；生产性能留给 AC8 | #551 / AC11 | satisfied | Count 继续调用 `display_count`；后端回归证明 `operation=count`、投影状态、阶段耗时和仅字段名日志，Blueprint/运维手册已同步 |
| R4 | 不改变公共 Contract/Schema/Migration/依赖/筛选语义，验证和 Review 后合并 | #551 / AC12 | satisfied | 无 Contract/Schema/Migration/依赖 diff；兼容检查、类型/构建/静态门禁和 Standard Review 通过，PR #557 继续执行 CI 后合并 |
| R5 | 真实 1,823,565+ 条数据性能验收 | #551 / AC8 | explicitly_deferred | AC8 明确要求在 Implementation merge 后的服务器环境执行，本 Change 不伪造该结果 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Voice Plaza Store/API | 并发动作、Count AbortSignal 和竞态保护 | Count 不等待列表并减少旧请求 | R1、R2 / E1、E2 |
| Voice Plaza Page/tests | 统一入口和完整 Count 状态 | 零结果、失败和投影准备状态可观察 | R1、R2 / E4 |
| Product/Content HTTP + tests | 共用读取耗时 helper，记录 Count 阶段 | 可独立验证服务器 Count 耗时 | R3 / E5 |
| 声音广场运维手册 | 补充 Count 事件和并发验收 | 支持 AC8 后续服务器复测 | R3、R5 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档
- [x] 取得仍覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Store 并发/取消/竞态、页面零值/错误/准备状态、后端日志字段 |
| 接口 / 契约 | required | OpenAPI/生成 Client 无漂移，现有 Count Contract 回归 |
| 集成 / 持久化 / 运行依赖 | required | 复用当前 PostgreSQL ready 后筛选精确 Count 集成证据；本次不改变 SQL/Schema |
| 用户 / 工作流验收 | required | 浏览器模拟进入、筛选、重置、空结果和 Count 失败恢复 |
| 跨组件关键路径 | required | 页面 → 生成 Client → Count Service → 投影日志的真实接线由目标 full-stack/CI 选定证据覆盖 |
| 外部依赖 / 供应方探测 | not_applicable | 不修改或调用外部 Provider |
| 构建 / 打包 / 运行 | required | 前端类型检查与正式构建、后端静态检查 |
| 文档 / 治理 / 其他 | required | 运维手册、Change Ready、Issue/PR/CI/合并与归档 |

## 验证计划

- 目标测试：声音广场 Store/Page Vitest；Count 日志后端单元测试。
- 相关回归：Count Contract；声音广场读模型单元和 PostgreSQL 集成证据。
- 静态检查或构建：受影响 ESLint/Ruff/Mypy、前端 typecheck/build、Docs/Contract drift。
- 专项真实边界：真实生产服务器性能由 #551 / AC8 在合并后执行。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 并发 Count 与列表竞争数据库；快速筛选留下旧请求 | 投影窄查询、取消旧 Count、独立耗时日志和 AC8 生产复测 |
| 兼容性 | 向后兼容 | 公共 HTTP 字段、筛选、排序和 Cursor 不变 |
| 数据 / Migration | 不适用 | 不修改表、索引、Migration 或业务数据 |
| 部署 / 运行 | 普通应用发布后生效 | 必须继续确保 0054/0055 已迁移且 Worker 将投影推进到 ready |
| 回滚 / 恢复 | 回滚本次应用 revision | 无数据格式或不可逆副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 更新声音广场回填与性能验证运行手册。
- **依赖 / Runtime**：不新增、删除或升级依赖和 Runtime。
- **配置 / Secret**：不新增配置、Secret 或日志敏感字段。
- **部署 / Release**：本次只合并源码，不执行生产部署或 Migration。
- **兼容 / 消费方通知**：公共 Contract 不变；运维可新增按 `operation=count` 查询同一日志事件。

# 完成审计

- [x] upstream_re_read：2026-09-21 合并前重新读取 #551 live AC9–AC12、AC8 post-merge 边界、用户合并授权和当前 main/PR 事实。
- [x] change_coverage：AC9–AC12 已逐条映射到实现、回归、文档和交付；AC8 继续保留真实服务器 post-merge 验收。
- [x] reverse_audit：已从页面进入/查询/重置反查 Store、生成 Client、Count Service 与投影，并从 Count/日志反查页面状态、重试和运维验收。
- [x] unresolved_cleared：R1–R4 已有当前实现与本轮证据，唯一延期 R5 由 #551 / AC8 明确要求在合并后服务器验证。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Red / Windows / Node 24.19 / Python 3.14 | `npm --prefix frontend test -- --run tests/voice-plaza.spec.ts tests/voice-plaza-design.spec.ts`；`uv run pytest tests/unit/content/test_voice_plaza_observability.py -q -p no:cacheprovider` | 前端 3 failed、37 passed；后端 1 failed、1 passed | 当前缺少并发入口、AbortSignal、空列表 Count 状态和 Count 日志，失败原因与 AC9–AC11 一致 |
| V2 | Green / Windows / Node 24.19 / Python 3.14 | 同一目标回归命令 | 前端 41 passed；后端 2 passed | 同一 Red 路径已修复，并补充 Count 失败不覆盖列表 |
| V3 | Windows / Node 24.19 | `npm --prefix frontend run test -- --run`；`npm --prefix frontend run lint`；`npm --prefix frontend run build` | 227 passed；lint、双 TypeScript 检查和 Vite build 通过 | 前端完整回归、类型和正式产物构建未受破坏 |
| V4 | Windows / Playwright Browser Mock Acceptance | `npm --prefix frontend run test:e2e -- voice-plaza-design.spec.ts --grep "shows the matching total"` | 1 passed | 真实页面入口中列表保持 pending 时总数已经显示，之后列表正常提交 |
| V5 | Windows / Python 3.14 | `uv run pytest tests/unit -q -p no:cacheprovider --ignore=tests/unit/test_prepare_host.py`；`uv run pytest tests/contracts tests/api -q -p no:cacheprovider -k "not current_machine_facts_do_not_reintroduce_platform_aliases"` | 1215 passed、8 skipped；185 passed、1 deselected | 除 Windows 不具备 POSIX API 和既有本地 Provider 输出扫描干扰外，后端单元、Contract 与 API 回归通过 |
| V6 | Windows / Python 3.14 | Ruff format/check、Mypy、Contract generate/compatibility、architecture/table ownership、Docs checks、Change schema | 全部通过 | 静态类型、格式、架构边界、公共 Contract、文档和 Change 结构无回归 |
| V7 | Standard Review / `origin/main` 9963e2f | AC9–AC12 → diff/调用链 → 测试/文档反向审查 | `NO_FINDINGS_WITHIN_SCOPE` | 当前范围无阻断 Finding；浏览器证据为 Mock，真实 PostgreSQL 与 Linux 门禁交给 PR CI |

## 未验证内容与剩余风险

- 真实服务器投影状态、并发列表/Count P50/P95 与数据库 CPU/IO 仍由 #551 / AC8 在合并后验证。
- Windows 本地无法执行 3 个 Linux POSIX 主机权限测试；一项 Contract 仓库扫描受工作区既有、非本 Change 的 Provider 原始输出影响，未删除用户数据。干净 Linux PR CI 负责最终确认。

## 交付状态

- 提交：Change、Red 已提交；Green/文档/证据提交待创建。
- 拉取请求：#557（早期 PR，待更新为可审查说明）。
- CI：早期 proposed Change 门禁按预期失败；ready_for_review 推送后重跑。
- 合并：待执行。
- Change 归档：合并后由仓库自动化处理。
- 发布 / 部署：不在本次授权范围。

## 备注

- 无。
