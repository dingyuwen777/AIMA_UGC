---
schema: rvc-change/v1
id: CHG-20260823-analysis-runtime-capability
title: 补齐 AI 运行配置能力前端提示
level: L3
status: done
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
  - backend/src/aima_ugc/contracts/runtime.py
  - backend/src/aima_ugc/bootstrap/analysis_capability_http.py
  - backend/src/aima_ugc/entrypoints/api_main.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/e2e/voice-plaza.spec.ts
  - frontend/tests/voice-plaza.spec.ts
  - tests/api/test_analysis_runtime_capability.py
  - docs/API接口说明.md
  - docs/blueprint/04-后端任务API与前端.md
  - docs/环境运行与部署.md
contracts:
  - GET /api/v1/content-analysis-capabilities
data_changes: []
---

# 目标

补齐上一轮 Local Dev Bootstrap 上游方案中已确认但遗漏的用户可见行为：当当前运行环境未配置可执行的 LLM Analysis Runtime 时，声音广场明确显示“AI 未配置”并禁止创建注定失败的 AI Analysis Job；配置完整时保持现有 AI 打标链不变。前端不读取 `env.local`、不猜 Secret，也不复制 Runtime 配置规则，而是消费后端安全的能力读模型。

# 成功标准

- [x] 新增安全、只读的 `GET /api/v1/content-analysis-capabilities`，只返回当前 AI Analysis 是否 configured，不泄露 Base URL、Model、API Key、Secret 文件路径或异常详情。
- [x] configured 判定与正式 Analysis Worker 的最低运行前提一致：LLM Base URL、Model 和可读取的 `llm_api_key` Secret File 均存在；Provider Name 仍可由现有 Adapter 推导。
- [x] Pydantic → OpenAPI → Orval generated client 全链同步，生成物由仓库正式生成命令产生并通过 drift/compatibility 检查。
- [x] Voice Plaza 首次加载读取 Analysis Capability；未配置时 `AI 打标` 禁用，并有明确用户提示。
- [x] configured=true 时，现有 selected/query Analysis Request、Job 轮询和结果刷新行为不变。
- [x] 后端仍保留执行时最终配置校验；前端 disabled 只用于避免明显无效操作，不替代 Worker 守卫。
- [x] Browser Mock 覆盖 configured/unconfigured 两种用户可见状态；API 测试覆盖 Secret 缺失/存在和不泄露配置详情。
- [x] API 实现说明、Blueprint 04 和本地运行文档已同步；TikHub 继续使用现有 Collection Capability 机制。

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
- Frontend 不读取数据库、Secret、本地配置文件或复制后端配置规则。
- PostgreSQL Schema、Migration、Prompt/Taxonomy、Analysis Result 身份语义均不变化。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | LLM 未配置时前端也应明确提示，并避免让 AI 打标看起来可正常执行 | user:local-dev-bootstrap-approved-scheme | satisfied | `GET /api/v1/content-analysis-capabilities` → Voice Plaza `analysisConfigured`；Browser Mock 断言 warning + disabled；Store 在 false 时不调用 `createContentAnalysis` |
| R2 | 本地启动未配置 TikHub/LLM 不应阻止基础功能；只影响对应可选能力 | user:local-dev-bootstrap-approved-scheme | satisfied | capability 是独立只读 GET；false 仅禁用 AI 分析，Excel Import/Voice Plaza 浏览/Excel Export 链未改；Final Ready HEAD Local Dev Bootstrap #46 与 Stage 8F #350 success |
| R3 | 前端不能读取 env.local/Secret 或复制配置规则，能力事实必须来自正式后端 Contract | docs/blueprint/04_后端任务API与前端.md | satisfied | `contracts/runtime.py` + `analysis_capability_http.py` → OpenAPI → Orval `getContentAnalysisCapabilities()` → Voice Plaza API/Store/Page；Blueprint 明确禁止前端读取本地配置/Secret |
| R4 | Secret 不能进入 API Response/前端，运行能力只公开安全必要事实 | docs/blueprint/05_日志安全部署与运维.md | satisfied | Response 只有 `configured: bool`；API tests 断言 API Key/Base URL/Model 不出响应；Final Ready HEAD CI #2223 API/secret/docs gates success |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | `frontend/e2e/voice-plaza.spec.ts` 覆盖 configured=false warning/disabled 与 configured=true 现有 Analysis Job；Final Ready HEAD CI #2223 Frontend checks success |
| Backend/API/PostgreSQL Integration | required | `tests/api/test_analysis_runtime_capability.py` 覆盖缺配置、缺 Secret、完整配置与响应脱敏；不新增数据库行为；Final Ready HEAD CI #2223 Backend/API checks success |
| Contract / Generated Client | required | `contracts/runtime.py` → OpenAPI → Orval；Final Ready HEAD CI #2223 generated drift + compatibility success |
| Real Full-stack Golden Path | required | Stage 8F #350 success，证明新增最终 API Assembly 后 Browser→Vue→FastAPI→PostgreSQL→Worker→Voice Plaza 既有 Golden Path 不回归；不增加付费 LLM Full-stack |
| Real Provider Probe | not_applicable | 不修改 LLM Provider endpoint/请求/响应/计费事实；本任务只判断本应用本地配置是否具备发起请求的前提，普通 CI 不发付费请求 |
| Docs / Governance / Other | required | `docs/API接口说明.md`、Blueprint 04、`docs/环境运行与部署.md` 已同步；Final Ready HEAD Change Completion Gate #69、Local Dev #46、Stage 6 #220、Stage 7 Keyword #1832 / Plan #1830 / Provider #1945 / Scheduler #2172 均 success |

# Completion Audit

- [x] upstream_re_read：进入 Ready 前重新读取用户批准行为、`AGENTS.md`、Skill 规则、Blueprint 04、正式 Analysis Worker、Voice Plaza 当前实现和运行文档，并独立重建完成定义。
- [x] change_coverage：确认 Change 覆盖“安全 capability Contract → generated client → Store/Page → configured/unconfigured Browser Mock → API/架构/运行文档”，没有把 Change 自身当成需求全集。
- [x] reverse_audit：从 AI 按钮反查 capability 与 Worker 最终守卫；从后端 `configured` fact 反查 generated client、Store/Page 和 Browser Mock；未发现后端能力无前端消费者或前端动作无后端真实支持。
- [x] unresolved_cleared：R1—R4 全部 satisfied；Real Provider Probe 的不适用依据已记录；无 `not_satisfied` 或未解释延期。

# 两阶段 Review

## Review A1：上游要求 → 当前 Change

- 用户批准方案要求“LLM 未配置时启动器提示，同时前端不把明显不可执行的 AI 功能表现成正常可用”；R1/R2 已覆盖。
- Contract-First 与 Secret 边界要求前端不能读取 `env.local`/Secret，且共享语义必须经 Pydantic/OpenAPI/generated Client；R3/R4 已覆盖。
- 上游没有要求增加 LLM 配置编辑、Provider 在线 Probe、数据库配置表或自动模型调用，因此这些保持非目标。

结论：未发现上游要求遗漏。

## Review A2：当前 Change → 实现 / 测试 / 文档

- R1：后端 capability + Voice Plaza disabled/warning + Store POST guard + Browser Mock。
- R2：能力 GET 与基础业务解耦；Stage 8F/Local Dev 回归证明基础链未被破坏。
- R3：`contracts/runtime.py`、最终 API Assembly、生成 OpenAPI/Orval、Feature API/Store/Page 全链接通。
- R4：响应只有 bool；API 脱敏测试和现有 Secret 扫描门禁通过。
- 文档：API 实现说明、Blueprint 04、环境运行文档均与当前代码一致。

结论：未发现 Change 要求缺实现、缺测试或缺文档。

# 任务

- [x] 复核上一 Change 与用户批准方案，确认前端 AI 未配置提示是遗漏。
- [x] 增加安全 Runtime Contract / Route 和 API 测试。
- [x] 使用正式生成链同步 OpenAPI 与 Orval Client。
- [x] 接入 Voice Plaza API/Store/Page。
- [x] 增加 Browser Mock configured/unconfigured 回归。
- [x] 同步 API/Blueprint/运行文档。
- [x] 完成 Completion Audit 与两阶段语义 Review。
- [x] 取得主 CI、Stage 8F、Local Dev 和相关永久 Stage 门禁的新鲜实现证据。
- [x] Final Ready HEAD 的 Completion Gate 与全部永久 CI success；PR #160 转 Ready 并正常合并。

# 验证

## Final Ready HEAD `8550ca933de2f01efbee7264143746b3d858889f`

- Change Completion Gate #69 / run `32618674181`：success。
- CI #2223 / run `32618674195`：success。
  - Contract/generated drift + compatibility：success。
  - Ruff / mypy / unit / contract / API / architecture / table ownership / secret scan / docs：success。
  - Wheel：success。
  - Frontend lint / typecheck / unit / build / Playwright：success。
- Stage 8F Full-stack #350 / run `32618674207`：success。
- Local Dev Bootstrap #46 / run `32618674175`：success。
- Stage 6 #220、Stage 7 Keyword #1832、Plan #1830、Provider Config #1945、Scheduler #2172：全部 success。

## 合并

- PR：#160 `补齐 AI 运行配置能力前端提示`
- Final Ready HEAD：`8550ca933de2f01efbee7264143746b3d858889f`
- Merge commit：`fdae845e65e3054a899384f24698d4461426df43`
- 合并方式：正常 PR merge；未绕过任何 CI/Review/Completion Gate。

# 文档影响

- `docs/API接口说明.md`：新增 Analysis Capability API 的安全语义、最低配置和非健康探测边界。
- `docs/blueprint/04-后端任务API与前端.md`：固化 capability 的 Contract-First 链、最终 API Assembly 和前端不得读取配置/Secret 的边界。
- `docs/环境运行与部署.md`：说明 LLM 未配置时 Backend Warning 与 Voice Plaza disabled/warning 的一致行为。

# 交付

- Branch：`feature/analysis-runtime-capability`
- PR：#160，已合并。
- Merge commit：`fdae845e65e3054a899384f24698d4461426df43`。
- Change：归档于 `changes/archive/2026-08/CHG-20260823-analysis-runtime-capability/CHANGE.md`。
- 发布：不涉及生产部署、Schema/Migration 或真实 LLM Probe；当前 Roadmap 下一正式单元仍为 Internal V1-A。
