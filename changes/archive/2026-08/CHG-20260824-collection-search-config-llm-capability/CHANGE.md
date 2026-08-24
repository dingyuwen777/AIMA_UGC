---
schema: rvc-change/v1
id: "CHG-20260824-collection-search-config-llm-capability"
title: "采集搜索配置与 LLM 能力修复"
level: L3
status: done
owner: "aima"
branch: "feature/collection-search-config-llm-capability"
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on:
  - "CHG-20260824-multi-keyword-pack-entrypoints"
affected_areas:
  - "collection"
  - "analysis"
  - "frontend"
  - "contracts"
affected_paths:
  - "backend/src/aima_ugc/contracts/http.py"
  - "backend/src/aima_ugc/modules/collection/"
  - "backend/src/aima_ugc/bootstrap/collection_http.py"
  - "backend/src/aima_ugc/bootstrap/collection_strategy_http.py"
  - "backend/src/aima_ugc/bootstrap/analysis_capability_http.py"
  - "backend/src/aima_ugc/modules/collection/run_snapshot.py"
  - "frontend/src/features/import-batches/"
  - "frontend/src/features/collection-strategy/"
  - "frontend/src/shared/"
  - "contracts/openapi/openapi.json"
  - "frontend/src/generated/api/"
  - "tests/api/"
  - "tests/contracts/"
  - "tests/integration/collection/"
  - "tests/unit/collection/"
  - "tests/fullstack/"
  - "frontend/e2e/"
  - "frontend/e2e-fullstack/"
  - "frontend/tests/"
  - ".github/workflows/stage8f-fullstack.yml"
  - "docs/02_环境运行与部署.md"
  - "docs/blueprint/04_后端任务API与前端.md"
  - "docs/blueprint/08_采集策略与平台能力.md"
  - "docs/appendix/07_AI舆情打标与分析实现.md"
  - "docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md"
  - "docs/collection/README.md"
  - "backend/src/aima_ugc/modules/analysis/README.md"
  - "backend/src/aima_ugc/modules/collection/README.md"
contracts:
  - "HTTP OpenAPI"
data_changes: []
---

# 目标

让手工 TikHub 主动发现和周期 Collection Plan 通过同一套 Provider-neutral Search Config Contract 表达平台差异：手工发现使用“最新、一天内、全部内容”的平台合法默认值，Plan 新建时逐平台显式提交；同时修复本地 `env.local` 已完整配置 LLM 时能力接口仍误报不可用的问题。

# 成功标准

- [x] `GET /api/v1/collection-capabilities` 返回每个平台支持的搜索维度、合法值和手工发现默认配置，不返回 Provider 私有参数。
- [x] 手工 Discovery 前端按所选平台显示合法配置，默认使用平台支持的 `latest + 1d/day + all` 语义并将最终配置冻结进各 Scope。
- [x] 新建 Collection Plan 必须逐平台显式提交合法 Search Config；前端可以独立配置每个平台并能回显已保存配置。
- [x] 已有 Plan 中的空 `config={}` 不迁移、不重写，Scheduler 继续按现有 Runtime 默认值解释，维持 `all` 时间范围兼容。
- [x] 后端拒绝未知字段、平台不支持的字段和值；前端选项由 Capability 驱动而非维护平台 `if/else` 枚举。
- [x] `env.local` 的 LLM Base URL、Model、API Key 完整且外部 Secret 文件可读时，`/content-analysis-capabilities` 返回 `configured=true`，Worker 与能力接口使用相同 Secret 根边界。
- [x] Pydantic、OpenAPI、generated TypeScript Client、前端请求和后端消费保持一致。

# 范围

- Collection Search Config HTTP Contract、Capability 投影、服务端校验、Manual/Plan Scope 快照。
- `/collection-runtime` 手工 Discovery 抽屉和 `/collection-strategy` Plan 创建/详情交互。
- Analysis Capability 的 LLM Secret 可读性判断根目录修复。
- 相关后端/前端/Contract/Full-stack 测试、生成物与正式文档。

# 非目标

- 不修改 TikHub endpoint、Provider 私有参数值、分页、Mapper、Pricing 或自动 API family fallback。
- 不新增数据库表、列或 Alembic Migration；继续复用 Plan/Run/Scope 现有 JSON 配置快照。
- 不迁移或改写已有 Plan，不根据 Cron 自动推导时间窗口。
- 不在前端读取 `env.local`、Secret 文件或提供 LLM Secret 配置 API。
- 不改变 AI Prompt、Taxonomy、Analysis Result Schema 或 LLM 请求重试语义。

# 必须保持不变

- 既有 Plan `config={}` 的运行语义和 Scheduler 恢复行为保持不变。
- 已有 Run/Scope/Plan JSON 快照、Content 身份、Job Runtime、Provider Request/Attempt/Raw 链不变。
- Batch Supplement 不获得关键词搜索配置，仍只对冻结目标执行 Detail/Comments/SubComments。
- 手工 Discovery 旧 API 客户端省略 Search Config 时由后端解析为手工默认，避免部署窗口单侧升级失败；Plan 新建 Contract 按用户决定改为显式必填。
- LLM Secret 仍只保存在批准的外部 Secret 根，不复制、不写日志、不返回 HTTP。
- 不触碰用户已有的 `scripts/dev/frontend.py` 未提交修改。

# 关键决策

1. 采用“一个强类型 Provider-neutral `CollectionSearchConfig` + Capability 校验 + 现有 JSON 快照”的最小增量方案。相比只在前端增加表单/提交任意字典，它能让后端继续作为最终守卫；相比为五个平台建立五套 provider-specific Union Contract，它不会把 TikHub 私有命名泄露到公共 API。
2. 手工默认由后端根据 Capability 生成并由能力接口公开：排序优先 `latest`；时间优先 `1d`，微博合法映射为 `day`；支持 `all` 的时长/内容类型使用 `all`，只有单一合法内容类型时使用该值。前端只消费该默认，不复制平台判断。
3. Plan 新建请求的 Search Config 为逐平台必填；持久化继续使用既有 `CollectionPlanPlatform.config` JSON。已有空配置不做 Migration，因而回滚无需数据恢复。
4. Manual Discovery 为兼容旧客户端允许省略 Search Config，但后端会在创建 Scope 前解析为完整手工默认并冻结；前端始终显式发送当前配置。
5. LLM 问题采用修正 Analysis Capability `read_secret_file(..., root=settings.external_secret_root)` 的单一根因修复。拒绝前端绕过 `configured` 和把 API Key 复制进内部 Secret 根的方案，因为两者分别会制造假可用或重复 Secret。
6. 部署必须同步后端 Contract/OpenAPI/generated client/前端；已有后端可读取旧 Plan。回滚时整体回滚采集前后端 Contract，LLM 根目录修复可独立回滚且不涉及数据。

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
| R1 | 新建 Plan 逐平台显式配置，已有 Plan 保持当前 all 行为 | user:2026-08-24-collection-plan-search-config | satisfied | Plan 创建前后端完整配置、旧 `{}` 读取/重新启用/Scheduler 非完整兼容；Collection PostgreSQL 集成 89 passed，Mock E2E 17 passed，真实 Plan full-stack 1 passed |
| R2 | 手工主动发现默认使用 latest + 1d + all | user:2026-08-24-manual-discovery-default | satisfied | 五平台默认单元测试、Run Snapshot 集成断言和浏览器 payload 断言覆盖；平台不支持维度不伪造 |
| R3 | 不同平台只能展示和提交各自 Capability 支持的参数 | user:2026-08-24-platform-specific-config | satisfied | `search_config.py` 统一校验，Capability 投影合法值，共享 Vue 控件只消费 Capability；未知/非法/缺失字段测试通过 |
| R4 | 修复完整配置 env.local 后 AI 打标仍不可用 | user:2026-08-24-llm-runtime-capability-fix | satisfied | Capability 改用 `external_secret_root`；回归测试先失败后通过，正式 launcher 实测接口 `configured=True` 且未调用 LLM |
| R5 | HTTP Contract 变化必须同步 OpenAPI/generated Client/Frontend | docs/blueprint/04_后端任务API与前端.md | satisfied | Contract 全套 75 passed；生成器 `--check` 通过；Orval 二次生成 SHA-256 稳定；前端 build 通过 |
| R6 | Capability 只公开真实平台能力，前端不维护平台 if/else | docs/blueprint/08_采集策略与平台能力.md | satisfied | 五平台 Capability/default 测试与公共响应字段断言通过；前端字段/选项由统一 Capability 映射生成 |
| R7 | Secret 不进入公共配置、响应或日志 | docs/blueprint/07_技术决策与实施门禁.md | satisfied | Capability 只返回布尔值；API 回归断言不含 Secret/Base URL/Model；`scan_secrets.py` 退出 0 |

# Validation Matrix

按当前任务真实边界选择验证层。每层只使用 `required` 或 `not_applicable`：`required` 写明本次要证明的 Scope，并在完成前补当前 Evidence；`not_applicable` 必须说明为什么该层没有独立证明价值。不要机械要求所有任务执行全部层，也不要用 Browser Mock 冒充 Real Full-stack。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | `npm --prefix frontend run test:e2e`：17 passed；`npm --prefix frontend run test -- --run`：38 passed；覆盖手工默认 payload、新 Plan 未完整配置禁用/完整 payload、历史 Plan 兼容回显 |
| Backend/API/PostgreSQL Integration | required | Collection PostgreSQL Integration：89 passed；Collection unit：324 passed；API：31 passed；正式 launcher 实测 LLM capability `configured=True` |
| Contract / Generated Client | required | Contract：75 passed；`generate.py --check` 退出 0；Orval 二次生成 hash 稳定；Mypy 238 files、frontend build 退出 0 |
| Real Full-stack Golden Path | required | `collection-plan-search-config.spec.ts`：1 passed；真实 Browser → Vue → generated Client → API → PostgreSQL → GET Plan 回读，不创建 Run/Job/Provider 请求 |
| Real Provider Probe | not_applicable | 不改变 TikHub endpoint、参数映射或真实供应商事实，稳定 Operation/Fixture 测试足够且避免收费 |
| Docs / Governance / Other | required | Blueprint 04/08、Collection/Analysis README、环境文档、AI/Stage8F Appendix 已同步；架构、表 Owner、Secret、Docs 四项质量门禁退出 0 |

详细分层规则见 `.agents/skills/reliable-vibe-coding/references/testing-strategy.md`。

# Completion Audit

进入 `ready_for_review` 前必须**重新读取上游事实源**，不要从当前 Change 的 checklist 反推需求。按当前任务实际边界执行正向和反向审计；例如前后端任务应检查“后端能力 → 前端入口”和“前端动作 → 后端能力”，异步任务应检查状态、错误和结果闭环，同时复核 Validation Matrix：每个 `required` 层都有足够的新鲜证据，每个 `not_applicable` 都有真实依据。

- [x] upstream_re_read：已重新读取用户确认决定、Blueprint 04/07/08、Collection/Analysis 模块 README 和 Completion Gate 规则，并独立重建完成定义。
- [x] change_coverage：已确认当前 Change 覆盖新 Plan、旧 Plan、手工默认、平台差异、LLM 根目录、Contract/Secret/Git 边界，没有把 Change 自身当作需求全集。
- [x] reverse_audit：后端 Search Capability 均有手工/Plan 前端入口；两种前端动作均由后端 Capability/完整性守卫支持；Plan 可回读，Manual 冻结 Run Snapshot；Batch Supplement 明确排除；各验证层证据职责匹配。
- [x] unresolved_cleared：所有 Requirement 均为 `satisfied`；唯一 `not_applicable` 是未改变外部 Provider 事实且会产生费用的 Real Provider Probe，依据明确。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 建立并维护 Validation Matrix
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- Validation Matrix：按 `.agents/skills/reliable-vibe-coding/references/testing-strategy.md` 选择适用层
- 目标测试：`uv run pytest tests/contracts/test_stage8e_http.py tests/api/test_stage8e_collection_runs.py tests/unit/platform/test_analysis_capability_http.py -q`（按实际现有文件调整为对应测试入口）
- 相关测试：Collection Plan/Scheduler PostgreSQL integration、Capability/Runtime unit、Voice Plaza/Collection Browser Mock、Real Full-stack Golden Path
- 静态检查/构建：Ruff、mypy、OpenAPI/Orval drift、frontend lint/typecheck/test/build、四项仓库质量检查
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- 调查证据：`env.local` 的四个 LLM 键均非空且 `.runtime/secrets/llm_api_key` 存在；`analysis_capability_http.py` 错把 `settings.secret_dir` 作为读取 `settings.llm_api_key_file` 的批准根，而正式 Worker 使用 `settings.external_secret_root`。
- Red：Search Config 单元测试最初因模块不存在失败；LLM 外部 Secret Root 回归最初得到 `configured=False`；Playwright 最初因 Manual payload 缺配置、Plan 未禁用而 2 failed。
- Green：Collection unit 324 passed；API 31 passed；Contract 75 passed；Collection PostgreSQL Integration 89 passed；Vitest 38 passed；Mock Playwright 17 passed；Real Full-stack 1 passed。
- 静态/构建：目标 Ruff 通过，Mypy 238 files 通过，frontend lint/typecheck/build 通过，OpenAPI check 与 Orval 稳定性通过，四项质量脚本通过。
- 实机症状：正式 `scripts/dev/backend.py` 读取本机 `env.local` 后启动成功，安全能力接口返回 `configured=True`；仅查询能力，没有发送 LLM 请求。
- 已知基线：`uv run ruff check .` 仍报告 63 个本轮外的 Skill/Migration 既有格式问题；本轮全部 Python 文件目标 Ruff/Format 检查通过，不修改历史 Migration 掩盖基线。
- 平台限制：Windows 本地执行 `uv run pytest tests/unit -q` 得到 616 passed、7 skipped、3 failed；失败均位于本轮未修改的 `tests/unit/test_prepare_host.py`，原因是 Windows `os` 不提供测试直接 monkeypatch 的 `geteuid/chown`。PR 的 Ubuntu CI 作为该组 POSIX 测试的合并证据，不为本任务修改发布脚本测试。
- PR CI：PR #206 最终 head `9cf6ad3f` 触发的 17 个 GitHub 工作流全部 `success`，包括 CI、Stage 5A—5D、Stage 6、Stage 7、Stage 8F Full-stack、Windows Compose、Release dry-run 和 Completion Gate。
- 合并后验证：远程 `main` merge commit `95159e37`；本地主分支复跑 Collection unit 324 passed、Contract + API 106 passed、Vitest 38 passed、frontend build、Secret 扫描与 Ready Check 均退出 0。

# 文档影响

- `docs/blueprint/04_后端任务API与前端.md`：同步采集 Contract/Capability 和 LLM Capability 根边界。
- `docs/blueprint/08_采集策略与平台能力.md`、Collection README：同步 Manual/Plan Search Config、平台默认和旧 Plan 兼容。
- `docs/appendix/07_AI舆情打标与分析实现.md`、Analysis README：同步本地 LLM Capability 排障和外部 Secret 根事实。
- `docs/02_环境运行与部署.md`、`docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md`：同步源码 launcher 外部 Secret 排障与无付费 Provider 的 Plan 全栈验收链。

# 交付

- Commit：`54a54c49`（本地前端 launcher 标准输入修复）；`76685a72`（逐平台采集配置与 LLM 能力检测修复）；`391ad8e2`、`9cf6ad3f`（交付记录）。
- PR：[#206](https://github.com/dingyuwen777/AIMA_UGC/pull/206)，17/17 工作流成功，已合并。
- 发布：已通过 merge commit `95159e37` 合入远程 `main`；未执行应用部署。
