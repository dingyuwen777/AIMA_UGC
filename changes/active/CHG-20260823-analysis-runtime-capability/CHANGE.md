---
schema: rvc-change/v1
id: CHG-20260823-analysis-runtime-capability
title: 补齐 AI 运行配置能力前端提示
level: L3
status: in_progress
owner: chatgpt
branch: feature/analysis-runtime-capability
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on:
  - CHG-20260823-local-dev-bootstrap
affected_areas:
  - analysis
  - http-contract
  - frontend
  - documentation
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/content/http.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/voice-plaza/
  - frontend/e2e/voice-plaza.spec.ts
  - tests/api/
  - docs/API接口说明.md
  - docs/blueprint/04-后端任务API与前端.md
  - docs/环境运行与部署.md
contracts:
  - GET /api/v1/content-analysis-capabilities
data_changes: []
---

# 目标

补齐上一轮 Local Dev Bootstrap 上游方案中已确认但遗漏的用户可见行为：当当前运行环境未配置可执行的 LLM Analysis Runtime 时，声音广场应明确显示“AI 未配置”并禁止创建注定失败的 AI Analysis Job；配置完整时保持现有 AI 打标链不变。前端不读取 `env.local`、不猜 Secret，也不复制 Runtime 配置规则，而是消费后端安全的能力读模型。

# 成功标准

- [ ] 新增安全、只读的 `GET /api/v1/content-analysis-capabilities`，只返回当前 AI Analysis 是否 configured，不泄露 Base URL、Model Secret、API Key、文件路径或异常详情。
- [ ] configured 判定与正式 Analysis Worker 的最低运行前提一致：LLM Base URL、Model 和可读取的 `llm_api_key` Secret File 均存在；Provider Name 仍可由现有 Adapter 推导。
- [ ] Pydantic → OpenAPI → Orval generated client 全链同步，不手改 generated client。
- [ ] Voice Plaza 首次加载读取 Analysis Capability；未配置时 `AI 打标` 禁用，并有明确“当前环境尚未配置 AI 模型”的用户提示。
- [ ] configured=true 时，现有 selected/query Analysis Request、Job 轮询和结果刷新行为不变。
- [ ] 后端仍保留执行时最终配置校验；前端 disabled 只用于避免明显无效操作，不替代 Worker 守卫。
- [ ] Browser Mock 覆盖 configured/unconfigured 两种用户可见状态；API/Backend 测试覆盖 Secret 缺失/存在和不泄露配置详情。
- [ ] 文档同步说明本地 Backend Warning 与前端能力提示；不改变 TikHub 现有 Collection Capability 机制。

# 范围

- Analysis capability HTTP read model。
- Voice Plaza capability 读取、按钮状态与提示。
- Contract/generated/tests/docs 同步。

# 非目标

- 不新增 LLM Config 表、模型管理页面或运行时编辑 LLM 配置的 API。
- 不把 `env.local` 暴露给前端，也不返回 LLM URL/API Key/Secret path。
- 不改变 Analysis Request/Job Schema、结果 Schema、Prompt、Taxonomy、数据库表或 Migration。
- 不调用真实付费 LLM 作为普通 CI。
- 不新增 TikHub capability API；TikHub 继续使用现有 `collection-capabilities`。

# 必须保持不变

- 正式 Worker 继续以 `PlatformSettings + Secret File` 创建 LLM Adapter，并在配置不可用时返回 `analysis_configuration_unavailable`。
- AI Analysis 仍由用户显式创建 Job 才产生模型调用费用。
- HTTP Contract 继续由 Pydantic 单一事实源生成 OpenAPI/Orval。
- Frontend 不读取数据库、Secret 或本地配置文件。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | LLM 未配置时前端也应明确提示，并避免让 AI 打标看起来可正常执行 | user:local-dev-bootstrap-approved-scheme | not_satisfied | 待实现 capability → Voice Plaza disabled/notice |
| R2 | 本地启动未配置 TikHub/LLM 不应阻止基础功能；只影响对应可选能力 | user:local-dev-bootstrap-approved-scheme | not_satisfied | Local Dev 已提供 launcher warning；本 Change 补 AI 前端可见状态 |
| R3 | 前端不能读取 env.local/Secret 或复制配置规则，能力事实必须来自正式后端 Contract | docs/blueprint/04-后端任务API与前端.md | not_satisfied | 待新增安全 read model + generated client |
| R4 | Secret 不能进入 API Response/日志/前端 | AGENTS.md + docs/blueprint/05-日志安全部署与运维.md | not_satisfied | capability 只返回 bool；API tests 待证明 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | configured=false 禁用/提示；configured=true 保持现有 AI 提交流程 |
| Backend/API/PostgreSQL Integration | required | API capability 判定真实 Settings/Secret File；不需要新增数据库行为 |
| Contract / Generated Client | required | Pydantic/OpenAPI/Orval 同步与 drift check |
| Real Full-stack Golden Path | required | Stage 8F 现有 Excel Golden Path 不回归；不新增付费 LLM Full-stack |
| Real Provider Probe | not_applicable | 不修改或验证真实 LLM Provider endpoint；普通 CI 不发付费请求 |
| Docs / Governance / Other | required | API/Blueprint/运行文档与用户已确认方案同步 |

# Completion Audit

- [ ] upstream_re_read：重新读取用户批准方案、AGENTS/Skill、Blueprint、Analysis/Frontend 真实实现。
- [ ] change_coverage：确认“后端 capability → generated client → store/page → Browser Mock”完整覆盖。
- [ ] reverse_audit：从 AI 按钮反查 capability/Worker 最终守卫，从后端 configured fact 反查前端消费。
- [ ] unresolved_cleared：所有 not_satisfied 清零；无未解释延期。

# 任务

- [x] 复核上一 Change 与用户批准方案，确认前端 AI 未配置提示是遗漏。
- [ ] 增加 Contract / Service / Route 和 API 测试。
- [ ] 生成 OpenAPI 与 Orval Client。
- [ ] 接入 Voice Plaza API/Store/Page。
- [ ] 增加 Browser Mock configured/unconfigured 回归。
- [ ] 同步 API/Blueprint/运行文档。
- [ ] 完成 Completion Audit、Review、Ready Check 与永久 CI。

# 验证

- 待执行。

# 交付

- Branch：`feature/analysis-runtime-capability`
- PR：待创建
