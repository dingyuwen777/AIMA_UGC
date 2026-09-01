---
schema: coding-change/v1
id: CHG-20260901-voice-plaza-taxonomy-filters
title: 声音广场文件 Taxonomy 与筛选一致性
level: L3
status: in_progress
owner: codex
branch: main
created: 2026-09-01
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - api
  - contracts
  - frontend
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py
  - backend/src/aima_ugc/bootstrap/analysis_taxonomy_http.py
  - backend/src/aima_ugc/entrypoints/api_main.py
  - backend/src/aima_ugc/contracts/http.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/voice-plaza/
  - frontend/src/shared/domain/
  - tests/
  - frontend/tests/
  - frontend/e2e/
  - docs/
contracts:
  - GET /api/v1/content-analysis-taxonomy
  - Pydantic HTTP Contract -> OpenAPI -> Orval generated client
data_changes: []
---

# 背景与现状

声音广场已有内容查询、详情、人工相关性复核、Analysis Run 和 Excel Export，但筛选 UI 仍在前端硬编码情感，缺少 `voice_type`，一级/二级标签仍是自由文本。当前情感、`voice_type` 和标签的唯一业务事实源是 `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md`，现有 `PromptTaxonomyLoader` 已负责严格解析、Hash 和 fail-closed 校验。

正式 Figma 文件 `EAPm8KVarUe7BFTSnzvOpT` 的 CURRENT 列表基线为 `3924:556`；`3923:559` 明确把车型、总数页码、自定义导出列、消息中心和第三方下架状态放在 Future Backlog。本 Change 只交付 VP0—VP2，不用静态数据伪造 Future 能力。

# 目标

- 复用当前 Prompt Loader，新增安全只读 Taxonomy HTTP 投影。
- 通过 Pydantic → OpenAPI → generated client 把情感、`voice_type` 和标签树交付给声音广场。
- 补齐 `voice_type` 查询，情感和标签改为动态选项与一级/二级级联。
- Taxonomy 不可用时 fail closed，禁用依赖分类的筛选，但内容列表和独立操作继续可用。
- 收敛真实重复的平台显示和北京时间整日边界，不创建第二套业务枚举。

# 范围与非目标

Included：只读 Contract/API、统一错误、生成物、Voice Plaza Store/API/筛选、共享平台/时间 helper、目标测试和文档同步。

Excluded：管理员配置页、可写 Scheme API/数据库、车型、动态内容类型 Facet、类型化来源目录、总数/页码、第三方可用状态、自定义导出列、消息中心、依赖升级和 Migration。

# 方案决定

采用独立 `GET /api/v1/content-analysis-taxonomy`。它与 `/api/v1/content-analysis-capabilities` 的运行可用性职责分离，也不让前端直接读 Prompt。响应只返回 `prompt_version`、`prompt_sha256`、`schema_version`、`taxonomy_sha256`、`sentiments`、`voice_types`、`labels`；不返回 Prompt 正文、判断规则、模型配置、Base URL 或 Secret。前端硬编码枚举和把 Taxonomy 塞进 Capability Response 均不采用。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 当前先依靠文件配置完成声音广场，不开发管理员配置页 | user:当前任务与前序确认 | satisfied | 未新增管理员 Route/Schema/Page；后期路线保留在 Roadmap U3/U4 |
| R2 | 情感、voice_type、标签和打标签 Prompt 继续共享当前 Prompt 事实源 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | `PromptTaxonomyLoader` → 只读 API → generated Client → Voice Plaza，无前端合法值枚举 |
| R3 | 新增安全只读 Taxonomy Contract，不泄露 Prompt 正文或 Runtime 配置 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | `tests/api/test_analysis_taxonomy.py` 覆盖精确安全投影、Loader 错误和 HTTP 投影错误的统一 503 |
| R4 | Pydantic、OpenAPI 与 generated client 保持唯一类型链 | AGENTS.md | satisfied | 生成前后 OpenAPI/Client SHA-256 一致；Contract 测试与兼容检查通过 |
| R5 | 声音广场补齐 voice_type、动态情感和一级/二级标签级联 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3924:556 | satisfied | Unit 与 Playwright 断言动态未来值、父子级联和查询参数；Figma 八个 CURRENT 筛选行已同步 |
| R6 | Taxonomy 失败时分类筛选不可用，但列表与独立操作可继续 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | API 统一 503；Unit/Browser 验证 request_id、禁用分类筛选、列表与导出入口保持可用 |
| R7 | 不实现 Figma Future Backlog 能力 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3923:559 | satisfied | 反向审计未发现车型、总数页码、下架、消息或自定义导出列进入生产页面 |
| R8 | 收敛已有多消费者的平台显示和北京时间边界 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | `frontend/src/shared/domain/` 与 `frontend/tests/shared-domain.spec.ts` |

# Validation Matrix

| 验证层 | 要求 | 计划证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Loader 投影、Store 快照、级联、共享 helper、Vue 组件测试 |
| Contract / Generated | required | Pydantic/OpenAPI/Orval 生成与漂移检查 |
| Backend/API/PostgreSQL | required | Taxonomy API 与 voice_type/sentiment/label 查询集成；无 Schema 变化 |
| Browser Mock Acceptance | required | Taxonomy 成功/失败、筛选提交/重置/禁用 |
| Real Full-stack Golden Path | required | Browser→Vue→API→PostgreSQL 的列表与分类筛选接线 |
| External Provider Probe | not_applicable | 本 Change 只读取 Git Prompt 和现有 PostgreSQL，不调用 TikHub/LLM |
| Build / Runtime | required | Python/前端目标测试、typecheck、build、API runtime |
| Docs / Governance / Figma | required | Roadmap/API/Analysis/Figma 六域一致性、质量门禁、Ready Check |

# 实施步骤

- [x] Red：新增只读 Contract/API 与动态筛选失败测试。
- [x] Green：实现 Loader 安全投影、API、统一错误和正式 assembly。
- [x] 生成 OpenAPI 与 Orval Client，确认无手改 generated 文件。
- [x] 实现 Taxonomy Store/API、voice_type 和标签级联、不可用状态。
- [x] 收敛平台显示和北京时间整日边界的真实公共 Owner。
- [ ] 执行目标、模块、Contract、Browser、Full-stack、Build 和治理验证。
- [ ] 重新读取上游，完成 Completion Audit 和两阶段 Review。

# Completion Audit

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [ ] unresolved_cleared

# 当前验证边界

Contract/API、前端 Unit、42 条 Browser Mock、类型检查、Build、Figma 和项目质量门禁已有本轮新鲜证据。PostgreSQL Integration 与 Real Full-stack Golden Path 因本机 Docker Desktop Linux Engine 未响应而尚未运行；这属于 required 证据缺口，所以 Change 继续保持 `in_progress`，不勾选 `unresolved_cleared`，也不进入 Ready。

# 独立 Review 记录

- Review Target：base/current-base `4115e94df5d1bc46aa5ca28068c993424469ed57` 上的未提交 working tree；模式 `review-and-fix`；深度 L3 Deep Review。
- Finding：Loader 允许超长一级标签，但 HTTP Response 有 256 字符上限，导致合法 Loader 输出在投影阶段返回 500，而不是统一 503。
- Red：新增回归测试后目标套件为 `1 failed, 2 passed`，失败值明确为 `500 != 503`。
- Green / re-review：显式捕获 Pydantic `ValidationError` 并映射为同一不可用异常；目标测试 `3 passed`，完整 API `41 passed`；未发现新的代码级 Finding。
- Review 结论：实现范围 `NO_FINDINGS_WITHIN_SCOPE`，但 required PostgreSQL/Real Full-stack 证据缺失，Change 状态仍是 `in_progress`，不能给出 Ready/可发布结论。

# 兼容、部署与回滚

新增接口和前端字段均为 additive；不改数据库、不迁移数据、不升级依赖。回滚可恢复旧应用版本，历史 Analysis/Export/Review 事实不受影响。Taxonomy 解析失败必须保持统一错误而非旧前端枚举回退。
