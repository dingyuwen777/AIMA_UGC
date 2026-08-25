---
schema: rvc-change/v1
id: "CHG-20260825-provider-secret-error-visibility"
title: "修复补采 Secret 错误分类与前端展示"
level: L2
status: ready_for_review
owner: "codex"
branch: "fix/provider-secret-error-visibility"
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - "collection"
  - "frontend"
  - "test-infrastructure"
affected_paths:
  - ".github/workflows/fullstack.yml"
  - ".agents/project-context.json"
  - "backend/src/aima_ugc/bootstrap/collection_scope.py"
  - "backend/src/aima_ugc/modules/collection/README.md"
  - "backend/src/aima_ugc/modules/collection/collection_run_executor.py"
  - "docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md"
  - "frontend/README.md"
  - "frontend/e2e/collection-runtime.spec.ts"
  - "frontend/src/features/import-batches"
  - "tests/fullstack/seed_collection_plan_provider.py"
  - "tests/integration/collection"
  - "tests/unit/collection/test_collection_run_executor.py"
  - "tests/unit/fullstack/test_seed_collection_plan_provider.py"
contracts:
  - "CollectionScopeResponse.stop_reason"
data_changes: []
---

# 目标

当 Collection Worker 因 Provider Secret 文件不可用而无法发送请求时，保留安全、稳定且可审计的失败原因，并让 `/collection-runtime` 用户直接看到可操作的中文提示；同时修复会把集成/全栈测试 Provider Config 留在共享本地数据库中的测试隔离问题。

# 成功标准

- [x] Secret 文件缺失、不可读或不安全时不发送 TikHub 请求，Scope 终态使用稳定 `provider_secret_unavailable`，日志只记录既有业务 ID 和错误码，不记录 `secret_ref`、路径或 Secret 内容。
- [x] Run 详情 API 继续通过既有 `CollectionScopeResponse.stop_reason: string | null` 返回该错误码，不增加或删除 HTTP 字段，不修改数据库 Schema。
- [x] Collection Runtime 详情在失败 Scope 旁显示“Provider Secret 不可用，请联系管理员检查运行配置”，并保留 Run/Job ID 供排障。
- [x] 创建测试 Provider Config 的目标测试在结束后清理自身数据，重复执行后不会把测试配置暴露给日常开发页面。
- [x] 现有 Provider HTTP/恢复语义、合法 Provider Config、正常补采和既有错误码保持兼容。

# 范围

- Collection Scope 对 `SecretFileError` 的安全错误分类、持久化和低频错误日志。
- Run 失败摘要从 Scope 终态推导安全、稳定的错误码。
- Collection Runtime 详情组件的 Scope 错误映射与展示。
- 创建 Provider Config 的相关集成/全栈测试隔离和回归测试。
- 受影响的 Collection/Frontend 当前事实文档。

# 非目标

- 不把 TikHub Secret 挂载给 API，也不在 API 进程读取 Provider Secret。
- 不改变 Provider Config 的稳定身份、`secret_ref`、Capability、路由或多配置设计。
- 不删除、禁用或改写当前本地数据库中已经存在的历史测试配置；数据处置另行显式授权。
- 不调用真实 TikHub，不验证或改变第三方 endpoint、字段、费用和限流。
- 不新增依赖、数据库字段、Migration、运行时配置或新管理页面。

# 必须保持不变

- `CollectionScopeResponse.stop_reason` 继续是可空字符串，OpenAPI/Generated Client 字段形状不变。
- Provider Request/Attempt 的“发送前失败不冒充已发送”和现有 Fencing/恢复边界保持不变。
- API/Worker/Scheduler/Migration 分进程以及只由 Worker 挂载 TikHub Secret 的部署边界保持不变。
- Secret 不进入数据库明文、Job Payload、Raw、HTTP 响应或日志。
- 合法 Provider Config 的 Discovery、Batch Supplement、评论/二级回复行为保持不变。

# 关键决策

- 采用兼容增量方案：在既有 `stop_reason` 字符串中新增 `provider_secret_unavailable`，不新增 Contract 字段或 Schema。
- 不实施 API 创建前 Secret 读取。`compose.yaml` 只给 Worker 挂载 `tikhub_api_key`，这是最小权限边界；扩大 API Secret 权限不属于本缺陷修复。
- `SecretFileError` 只能映射为安全错误码和固定中文提示；底层异常消息包含路径，不得透传或写入日志。
- 历史测试数据不通过代码硬编码名称删除；测试修复只保证各测试清理自己创建的配置。

# Requirement Traceability

从用户已确认决定、正式 Roadmap/Spec/Stage 完成定义或其他上游事实源独立提取要求。**当前 Change 不能把自身作为 Requirement Source，也不能把本表当作上游需求全集。**

状态只允许：

- `satisfied`：已有实现/验证证据；
- `explicitly_deferred`：已有正式批准的延期依据；
- `not_applicable`：有明确事实证明不适用；
- `not_satisfied`：尚未满足，进入 `ready_for_review` 前必须清零。

`Source` 优先写仓库相对事实源路径；本轮用户明确决定可写 `user:<简短标识>`。`Evidence` 必须写实际实现、测试、运行或正式延期/不适用依据，Ready 时不得保留占位内容。

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复最近补采因 Provider Secret 不可用而只显示泛化错误的问题 | user:按诊断结论修改代码 | satisfied | 隔离 PostgreSQL 集成测试证明 Worker 未发送请求，Scope/Run/API 返回稳定错误码；Browser Mock 证明详情显示固定中文提示 |
| R2 | 测试 Provider Config 不得泄漏到日常开发能力列表 | user:按诊断结论修改代码 | satisfied | 增量评论测试按自身 ID teardown；重复集成回归后目标 `secret_ref` 行数为 0；Full-stack seed 未显式 opt-in 时在连接数据库前拒绝执行 |
| R3 | Provider Config 多实例设计与正常补采行为保持不变 | docs/blueprint/08_采集策略与平台能力.md | satisfied | Stage 8E、Scope/恢复相关回归通过；未修改 Provider Config/Capability/Operation；Contract compatibility 通过 |
| R4 | Secret 只使用批准的只读文件边界，不进入 HTTP、日志、Job、Raw 或数据库明文 | AGENTS.md | satisfied | 集成测试断言异常路径不在日志中且 Transport 调用为 0；`scan_secrets.py` 退出码 0；API Secret 挂载边界未改 |
| R5 | 前端继续消费生成 Client，不能手写第二套 HTTP Response Contract | docs/blueprint/07_技术决策与实施门禁.md | satisfied | 组件继续消费 generated `CollectionScopeResponse.stop_reason`；Contract compatibility、前端 39 项测试和生产构建通过 |

# Validation Matrix

先按当前任务的**真实失败边界**选择通用验证维度。每层只使用 `required` 或 `not_applicable`：`required` 写明本次要证明的 Scope，并在完成前补当前 Evidence；`not_applicable` 必须说明该层为什么没有独立证明价值。

不要为了填模板机械执行所有层，也不要因为某一层已经绿色就推断另一层已经被证明。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Run 聚合与 Full-stack seed guard 目标单测 5 项通过，其中混合/缺失失败原因保守回退为 `scope_execution_failed`；前端 Vitest 9 文件 39 项通过 |
| 接口 / Contract | required | `scripts/contracts/check_compatibility.py` 退出码 0；Pydantic/OpenAPI/generated client 仍为 `string | null`，没有生成差异 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 18.4 隔离容器中 Stage 8E、增量评论、Scope/评论/回复/恢复/4xx 回归共 17 项通过；Transport 调用为 0，Scope/Run 持久化安全错误，目标测试配置清理后行数为 0 |
| 用户 / Workflow Acceptance | required | `frontend/e2e/collection-runtime.spec.ts` 7 项 Browser Mock 通过，覆盖固定中文提示、未知/既有泛化错误和 ID 保留 |
| 跨组件 Golden Path | not_applicable | 本次不改变路由、字段或组装接线；Backend Integration 与 Browser Mock 分别验证真实持久化和用户状态，现有成功 Golden Path 作为相关回归即可 |
| External Dependency / Provider Probe | not_applicable | 根因在本地 Secret 文件读取且不改变 Provider 当前事实；真实 TikHub 调用无证明价值且可能计费 |
| Build / Package / Runtime | required | Ruff format/check、Mypy 244 个源码文件、前端 lint、Vitest 与 Vite 生产构建均退出码 0 |
| Docs / Governance / Other | required | Collection/Frontend/Stage 8F 文档已同步；Architecture、Table Owner、Secret Scan、Docs Check 均退出码 0 |

通用规则见 `.agents/skills/coding/references/07_通用验证与证据策略.md`。

项目存在专项 profile 时在保持语义责任不变的前提下使用更具体层名。例如 Web/API/PostgreSQL/Provider 项目继续按 `.agents/skills/coding/references/08_分层测试与验收策略.md` 使用：

```text
用户 / Workflow Acceptance
→ Browser Mock Acceptance

集成 / Persistence / Runtime Dependency
→ Backend/API/PostgreSQL Integration

接口 / Contract
→ Contract / Generated Client

跨组件 Golden Path
→ Real Full-stack Golden Path

External Dependency / Provider Probe
→ Real Provider Probe
```

Browser Mock 不能冒充真实 Backend/DB；一条 Full-stack 不能冒充全部状态；真实 Provider Probe 默认有界且不进普通 CI。

# Completion Audit

进入 `ready_for_review` 前必须**重新读取上游事实源**，不要从当前 Change 的 checklist 反推需求。

按当前项目形态和任务边界执行正向/反向审计。例如：

- 前后端：后端能力 → 前端入口，前端动作 → 后端真实能力；
- CLI：public command/flag → handler → stdout/stderr/exit/副作用；
- Library：public API → consumer；
- 异步：请求 → 状态 → 错误/恢复 → 最终结果；
- Schema/Migration：writer → migration → reader/consumer；
- Package/Release：source → build artifact → install/startup；
- Infra：config → plan/render → runtime/deploy boundary（在授权范围内）。

同时复核 Validation Matrix：每个 `required` 都有足够的新鲜证据，每个 `not_applicable` 都有真实依据。

- [x] upstream_re_read：已重新读取用户决定、根/`docs/` AGENTS、Blueprint 07/08、HTTP Contract、generated client 与 `compose.yaml` Secret 挂载事实，并从它们独立重建完成定义。
- [x] change_coverage：已确认当前 Change 覆盖错误分类、持久化、API 消费、前端展示和两个已识别测试配置来源，没有把 Change 自身当作需求全集。
- [x] reverse_audit：已完成“Worker 失败 → Scope/Run → HTTP → generated client → Drawer”和“前端提示 → 后端稳定错误码”的双向审计；真实 Provider Probe 与新增 Full-stack 路由因无独立证明价值保持不适用。
- [x] unresolved_cleared：Requirement Traceability 无 `not_satisfied`；Validation Matrix 的不适用项均有任务边界依据。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立四维任务路由：Full-stack 模块化单体；Bug Fix；Python 3.14/uv + Vue 3/TypeScript/npm；L2
- [x] Red：补充 Secret 不可用、Run 错误聚合、测试配置清理和前端错误展示回归，并确认因目标行为缺失失败
- [x] Green：最小修改 Scope、Run 聚合、测试清理与前端详情展示
- [x] 运行目标测试、相关后端/前端测试、Contract/生成漂移、静态检查和构建
- [x] 同步受影响的 Collection/Frontend 当前事实文档
- [x] 完成 Requirement Traceability、Validation Matrix、Completion Audit 与两阶段 Review

# 验证

## 计划

- Validation Matrix：按 `.agents/skills/coding/references/07_通用验证与证据策略.md` 选择通用维度；存在专项 profile 时再叠加专项策略
- 目标测试：Secret 不可用的 Collection Scope/PostgreSQL 回归；Collection Run 聚合 Unit；Collection Runtime Vue/Browser 错误展示；Provider Config 测试隔离
- 相关测试：Collection Scope/Run/Stage 8E API 与前端 collection-runtime 测试
- Contract/生成：`uv run python scripts/contracts/check_compatibility.py`
- 静态检查/构建：`uv run ruff format --check backend tests scripts`、`uv run ruff check backend tests scripts`、`uv run mypy backend/src`、`npm --prefix frontend run lint`、`npm --prefix frontend run test -- --run`、`npm --prefix frontend run build`
- 仓库门禁：Architecture、Table Owner、Secret Scan、Docs Check
- Ready Check：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- 事实恢复：同步前使用旧入口刷新 82 个事实入口；同步 `origin/main` 后按新入口 `python .agents/skills/coding/scripts/coding.py discover --root .` 重建 `.agents/project-context.json`，退出码 0，共 83 个事实入口。
- 并行状态：同步后运行 `python .agents/skills/coding/scripts/coding.py status --root . --json` 与 `conflicts --root . --json`，退出码 0，无其他 Active Change 或冲突。
- Red：Stage 8E Secret 回归得到 `run.error_summary=scope_execution_failed` 而非预期安全错误码；Browser Mock 收到机器码但找不到中文提示；seed 脚本未 opt-in 时进入 Runtime 初始化；混合失败 Scope 被错误聚合为 Secret 故障。四项均因目标行为缺失而失败。
- Green/后端关键链：隔离 PostgreSQL 18.4 中运行 Stage 8E、增量评论、Scope/评论/回复/恢复/Provider 4xx，`17 passed`；Run 聚合与 seed guard 目标单测为 `5 passed`。
- 相关后端回归：Collection Scope、Comments、Replies、Recovery、Provider 4xx 共 `7 passed`；Stage 8E 全模块 `9 passed`；相关 Collection Unit `6 passed`。
- 测试隔离：增量评论回归完成后按测试 `secret_ref` 查询为 `0` 行；Full-stack seed 正向路径只在显式 opt-in 的隔离数据库中运行。
- Browser Mock：`npx playwright test e2e/collection-runtime.spec.ts`，`7 passed`。
- Frontend Unit/Build：`npm --prefix frontend run lint`、`npm --prefix frontend run test -- --run`（9 文件、39 项）、`npm --prefix frontend run build`（TypeScript/Vue/Vite）均退出码 0。
- Backend Static：Ruff format/check、Mypy 均退出码 0；Mypy 检查 244 个源码文件。
- Contract/Governance：Contract Compatibility、Architecture、Table Ownership、Secret Scan、Docs Check 均退出码 0；`git diff --check` 无空白错误。
- Completion Gate：最新主线重新发现 83 个事实入口；Active Change 状态为 `ready_for_review` 且无冲突；UTF-8 模式下 Coding 工作流测试 `37 passed`；`ready_check.py --require-active-ready` 退出码 0（gated 37、strict 37、legacy 72）。
- 验证环境清理：已停止并自动移除无持久卷容器 `aima-ugc-codex-provider-secret-test`，并在解析、校验绝对路径位于仓库后删除四个 `codex-provider-secret-test*` 临时路径；`.runtime` 其他开发数据未触碰。
- 扩大回归尝试：最新主线执行 `uv run pytest tests/unit tests/contracts tests/api -q` 得到 `3 failed, 763 passed, 7 skipped`；3 项均在 Windows 缺少 POSIX `os.geteuid`/`os.chown` 的 `tests/unit/test_prepare_host.py` monkeypatch 边界失败，与本次差异文件无交集。本任务未删除、跳过或篡改这些失败测试，完整 CI 仍需 Linux 环境确认。

# 文档影响

- 需要同步 Collection 模块 README 与 Frontend README 的当前错误展示/排障说明；Blueprint、Roadmap、Schema、Migration 和部署拓扑不变化。

# 交付

- Commit：用户已授权提交并将修改集成到远程 `main`；等待最新主线复验通过后执行。
- PR：按仓库规则从任务分支创建 PR，等待 Linux CI 和分支保护通过后合入远程 `main`。
- 发布：不适用，未执行。
