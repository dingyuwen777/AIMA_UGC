---
schema: rvc-change/v1
id: "CHG-20260828-voice-type-taxonomy"
title: "统一 voice_type 为 Prompt Taxonomy 驱动"
level: L3
status: done
owner: "chatgpt"
branch: "feature/voice-type-taxonomy"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "analysis"
  - "contracts"
  - "database"
  - "api"
  - "export"
  - "generated-client"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc/modules/analysis/"
  - "backend/src/aima_ugc/contracts/analysis/"
  - "backend/src/aima_ugc/contracts/export/"
  - "backend/src/aima_ugc/bootstrap/content_http.py"
  - "backend/src/aima_ugc/platform/export/excel.py"
  - "migrations/versions/20260828_0030_voice_type_taxonomy.py"
  - "contracts/"
  - "frontend/src/generated/api/"
  - "tests/unit/analysis/"
  - "tests/unit/database/"
  - "tests/unit/platform/"
  - "tests/integration/database/"
  - "docs/appendix/06_Excel统一数据导出与离线调试.md"
  - "docs/appendix/07_AI舆情打标与分析实现.md"
  - "docs/blueprint/03_数据库与文件存储.md"
  - "docs/blueprint/07_技术决策与实施门禁.md"
contracts:
  - "ContentVoiceType"
  - "ContentLabelAnalysisV3"
  - "ContentAnalysisResponse"
  - "UnifiedDataExcelAnalysisV1"
data_changes:
  - "analysis_content_results.voice_type"
---

# 目标

把 `voice_type` 的合法值集合统一交给 `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md` 中的机器可读 Taxonomy 管理，使它与 `sentiments`、一级/二级 `labels` 使用同一机制：输出 JSON 结构仍由代码固定，业务可选值由 Prompt Taxonomy 在运行时解析并由 `RuntimeTaxonomyValidator` 严格校验。

同时保留 Prompt 中完整的自然语言判断经验：主体证据、表达目的证据、`七类边界与高混淆场景`、具体正反例和后续用户补充的示例继续用于教模型“怎么判”，不压缩进机器 JSON，也不因本次结构调整删除。

# 成功标准

- [x] 机器 Taxonomy 增加 `voice_types`，当前 7 个机器值保持不变；Taxonomy schema 对新增字段显式版本化。
- [x] `PromptTaxonomyLoader` 解析、清洗、去重并把 `voice_types` 纳入 `taxonomy_sha256`；非法/重复值在调用 LLM 前 fail closed。
- [x] `RuntimeTaxonomyValidator` 像校验 `sentiment` 一样校验 `voice_type` membership，并提供稳定 `unknown_voice_type` Validation Retry 错误码。
- [x] Python Contract 不再复制当前 7 类为 `Literal`；只保留字符串结构约束，新增 Prompt voice type 不要求改 Python。
- [x] PostgreSQL 不再复制当前 7 类为业务枚举 `CHECK`；只保留非空/结构约束，新增 Prompt voice type 不要求 Schema Migration。
- [x] 新 Alembic Migration 保留已有数据原值，按“先扩数据库约束、再部署代码”可兼容升级；降级遇到旧 schema 不支持的新值时 fail closed，不静默改数据。
- [x] Prompt 的 `内容发声类型判断标准`、`七类边界与高混淆场景` 和示例完整保留；以后可继续在同一 Prompt 增加类别定义和学习示例。
- [x] 当前 7 类的机器值与业务判断语义不改变；历史 Analysis Result 不回写、不重分类，继续由既有 `prompt_sha256/taxonomy_sha256` 追溯当时规则。
- [x] OpenAPI / generated TypeScript Client 由正式生成流程同步；现有字段名、JSON 结构和接口路径不变。
- [x] Excel 既有 7 类继续使用原中文展示别名，但展示映射不再充当合法值白名单；未来 Prompt 新值可原样导出，不要求同步修改导出代码。
- [x] 目标 Unit、PostgreSQL Integration、Contract/generated drift、质量门禁和完整 PR CI 已取得新鲜绿色证据；PR #254 squash merge 后 `main` 提交 `911e52301ae179615a415e14c632caa17faf0d2a` 的 5 个 push 工作流也全部成功。

# 范围

- 扩展当前 `content_labeling_v3.md` 机器 Taxonomy 增加 `voice_types`。
- 保留 voice type 自然语言定义、边界、混淆场景和示例。
- 扩展 `PromptTaxonomy` / `PromptTaxonomyLoader`。
- 把模型响应 `voice_type` 的合法性校验移入 `RuntimeTaxonomyValidator`。
- 把 `ContentVoiceType` 从固定业务 Literal 收敛为受长度约束的字符串结构类型。
- 把 `analysis_content_results.voice_type` 从固定七值数据库 CHECK 收敛为字符串结构约束，并新增 Alembic Migration。
- 让 Excel 现有中文别名保持兼容，但对未配置别名的新合法机器值采用原样展示，不维护第二套合法 Taxonomy。
- 同步 Analysis README、Excel/AI Appendix、数据库/技术门禁 Blueprint 与正式 generated contracts/client。
- 增加运行时 Taxonomy、Contract、Excel 导出、数据库约束回归测试。

# 非目标

- 不改变 `relevance` 的 `relevant/irrelevant` 固定结构语义。
- 不修改当前 7 个 voice type 的名称、定义或分类边界。
- 不删除或简化 `七类边界与高混淆场景`、现有示例。
- 不新增独立 Taxonomy 数据库表、配置中心或前端 Taxonomy API。
- 不在本次给声音广场新增 voice type 筛选/展示 UI。
- 不重跑历史 AI 打标，不批量迁移历史结果值。
- 不升级 Python、Node、依赖或框架。

# 必须保持不变

- 模型输出字段仍固定为 `item_no/relevance/voice_type/sentiment/labels`。
- `relevance=relevant` 时仍必须有合法 sentiment 和至少一个合法标签对；`irrelevant` 时仍必须 `sentiment=null, labels=[]`。
- Prompt Markdown 继续是 AI taxonomy/判断规则唯一业务事实源，不新增 Python/DB/前端平行业务列表。
- Analysis Result 的 Prompt/Taxonomy/Model/Input 审计身份和 Current/History 选择语义保持不变。
- PostgreSQL 仍是唯一业务事实库，Schema 演进只通过 SQLAlchemy tables + Alembic Migration。
- 前端 generated client 继续由 Pydantic/OpenAPI → Orval 生成，禁止手写第二套类型。

# 关键决策与方案比较

## 方案 A：运行时 Prompt Taxonomy 驱动（采用）

- Prompt JSON 维护 `sentiments + voice_types + labels`。
- Python/Pydantic 只固定字段结构和字符串边界。
- Runtime Validator 对三个业务分类维度做 membership / 父子关系校验。
- PostgreSQL 只约束结构，不复制业务枚举。
- Excel 的中文映射只承担既有展示兼容；未配置别名的新值原样展示，因此不会成为合法值白名单。

优点：与现有 sentiment/labels 机制一致；以后增删 voice type 只需改同一 Prompt 的机器列表与自然语言判断/示例；无需普通 Schema Migration。风险：HTTP OpenAPI 不再暴露固定 voice type enum，但这是允许运行时 Taxonomy 演进所需的兼容边界。

## 方案 B：从 Prompt 在构建期生成 Python Enum 和数据库 CHECK（不采用）

能减少手工复制，但每次分类变化仍会改变公共 enum 和数据库 Schema，并要求生成/Migration；没有达到“后续只改 Prompt”的目标。

## 方案 C：新增数据库 Taxonomy 配置表（不采用）

可做运行时管理后台，但引入新的持久化 Owner、版本发布和配置一致性问题；当前唯一事实源已明确是 Prompt Markdown，本次没有后台动态配置需求，复杂度无证据支持。

# Migration / 部署 / 回滚

- Upgrade：先删除 `voice_type` 固定七值 CHECK，再增加非空/结构 CHECK；不修改任何现有行值。
- 部署顺序：Migration 可先于新代码执行；旧代码只写原 7 类，仍满足放宽后的数据库约束。随后部署新代码。
- 代码回滚：先回滚应用代码仍可读取/写入原 7 类；若新 Prompt 从未引入新值，可再安全 downgrade Migration。
- Migration downgrade：恢复 0029 之前的七值约束；如果数据库已经出现旧约束不支持的新 voice type，明确失败并列出阻塞值，不删除、不映射、不篡改数据。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | `voice_type` 与 sentiment/labels 一样由同一 Prompt 机器 Taxonomy 管理合法值，后续增删类别不再改 Python/DB 业务枚举 | user:统一发声类型为提示词驱动 | satisfied | Prompt `aima-content-taxonomy.v2` 已包含 `voice_types`；`PromptTaxonomyLoader` 与 `RuntimeTaxonomyValidator` 已接入，动态 `community_voice` Service 回归测试通过 |
| R2 | `内容发声类型判断标准` 保持自然语言形式，可在 Prompt 中增加类别和定义 | user:判断标准继续放提示词 | satisfied | `content_labeling_v3.md` 保留 `## 内容发声类型判断标准`、主体证据与表达目的证据；Unit 回归锁定这些章节 |
| R3 | `七类边界与高混淆场景` 必须保留，并保留/允许继续增加 AI 学习示例 | user:保留高混淆场景和示例 | satisfied | Prompt 保留 `### 七类边界与高混淆场景` 及“通勤小林”“品牌合作”“作者和正文都极少”等示例；`test_prompt_retains_voice_type_judgment_boundaries_and_learning_examples` 已通过 |
| R4 | 当前 7 类机器值和现有业务语义不改变，历史结果不被静默重分类 | backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md | satisfied | 当前 Prompt 仍是 `user_voice/creator_marketing/brand_official/dealer_promotion/media_information/other_organization/unknown`；Migration 不更新历史行，Analysis Result 继续保存 Prompt/Taxonomy Hash |
| R5 | AI taxonomy 不得在 Python、数据库和前端维护平行业务合法值列表 | AGENTS.md | satisfied | `ContentVoiceType` 已放宽为结构字符串，DB 只保留非空 CHECK，generated client 不再是固定 enum；Excel 旧中文别名使用 `.get(value, value)`，仅展示兼容而非合法值白名单 |
| R6 | Schema 变化必须通过 SQLAlchemy + Alembic，并用真实 PostgreSQL 验证 | AGENTS.md | satisfied | `20260828_0030` 已通过 PostgreSQL 18.4 空库 upgrade、`alembic check`、历史 Migration compatibility；Database/Job/Collection/Content/Ingestion 集成分别 25/13/90/33/17 passed |
| R7 | generated client 必须由正式 Pydantic/OpenAPI/Orval 流程同步，不手写第二套 Contract | docs/blueprint/07_技术决策与实施门禁.md | satisfied | CI run `33149645595` 执行 `scripts/contracts/generate.py`、Orval、`git diff --exit-code`、`generate.py --check`、compatibility check 全部成功 |
| R8 | 正常 PR/CI 后合并并推送到 `main` | user:改完推送主分支 | satisfied | PR #254 在最终 HEAD `c151deb56d2b4bd8268397dd5cd624d6639bfca9` 的 5 个永久工作流全绿后 squash merge；`main` 指向 `911e52301ae179615a415e14c632caa17faf0d2a`，其 Change Gate/CI/Runtime/Full-stack/Tooling push runs `33150977993/33150978020/33150977994/33150977999/33150978008` 均 completed/success |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Prompt Loader 解析/去重/hash、动态新增 voice type、`unknown_voice_type` Validation Retry、自然语言边界/示例保留、Excel 新值 fallback；CI Unit 694 passed |
| 接口 / Contract | required | `ContentVoiceType` 从固定 enum 放宽为结构字符串；CI Contract 92 passed、API 38 passed，generated compatibility/drift 通过 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 18.4 执行 Alembic head `20260828_0030`；固定七值 CHECK 已移除、结构 CHECK 存在；Database/Job/Collection/Content/Ingestion 全绿 |
| 用户 / Workflow Acceptance | not_applicable | 本次不新增页面入口、按钮或业务状态；额外真实 Full-stack 回归在最终 PR run `33150114971` 与合并后 `main` run `33150977999` 均成功 |
| 跨组件 Golden Path | not_applicable | 不改变 API 路径、Job 链或 Worker 装配；额外 Runtime 回归在最终 PR run `33150114876` 与合并后 `main` run `33150977994` 均成功 |
| External Dependency / Provider Probe | not_applicable | 不修改 TikHub/LLM 网络协议或真实 Provider 字段，不需要付费外部 Probe |
| Build / Package / Runtime | required | 最终 PR CI run `33150114931` 与合并后 `main` CI run `33150978020` 均 success；Ruff/mypy、Wheel build/install、frontend lint/type/build、Vitest/Playwright 全部通过 |
| Docs / Governance / Other | required | 最终 PR Change Completion Gate run `33150114872` success；合并后 `main` Change Completion Gate run `33150977993` success；architecture/ownership、Secret/docs、generated drift 均通过 |

# Completion Audit

- [x] upstream_re_read：完成前已重新读取本轮用户决定、目标分支与合并后 `main` 的 `AGENTS.md`、Coding Skill/相关 references、当前 Prompt、Analysis README、Excel/AI Appendix、Blueprint 与 PR/main CI 事实。
- [x] change_coverage：已逐项核对“只改 Prompt 即可演进 + 自然语言判断/边界/示例保留 + 当前 7 类不变 + DB/Contract/API/Excel 不维护平行合法值列表”，并为 Excel 第二白名单补充回归测试与修复。
- [x] reverse_audit：已按 Prompt → Loader → Validator → Contract → Repository/DB → API/generated consumer → Excel export 正反向审计，并复核 Migration upgrade/downgrade；未发现其他要求新增类别时同步改业务白名单的运行时路径。
- [x] unresolved_cleared：全部 Requirement 已满足；PR #254 已正常合并且合并后 `main` 5 个 push 工作流全部成功，无未解决严重/重要 Finding、失败门禁或延期事项。

# 任务

- [x] 从最新 `main` 恢复 AGENTS/Coding Skill/AI 实现/Contract/Schema/Migration/测试事实。
- [x] 创建 `feature/voice-type-taxonomy` 分支和 L3 Change。
- [x] Red：新增动态 voice type、非法 voice type、Contract/DB/Excel 平行枚举回归测试并取得有效失败证据。
- [x] Green：扩展 Prompt Taxonomy 与 Loader/Validator，保留自然语言边界和示例。
- [x] Green：移除 Python 固定七值 Literal，保留字符串结构约束。
- [x] Green：更新 tables.py + 新 Alembic Migration，保留数据与安全 downgrade。
- [x] Green：移除 Excel 导出层的合法值白名单语义，同时保持现有中文展示兼容。
- [x] 同步 generated contracts/client、Analysis README、Excel/AI Appendix 与相关 Blueprint。
- [x] 运行目标测试、PostgreSQL Integration、Contract、质量门禁和完整 CI。
- [x] 执行 Completion Audit、A1 需求符合性 Review 与 A2 代码质量 Review；无未解决严重/重要 Finding。
- [x] Change 进入 `ready_for_review` 并提交最终门禁复验。
- [x] PR #254 正常 squash merge 到 `main`；合并后 `main` push CI 已验证全绿。
- [x] 使用独立 `docs/archive-voice-type-taxonomy-change` 分支归档 Change，并记录实际 merge/main CI 证据。

# 验证

## Red 证据

- 有效业务 Red：commit `f1cdc0659da8e565978e77bcb572697dcc5dda10`，CI run `33149106150`，Repository Quality job `98776798241`。
- `tests/unit/platform/test_excel_voice_type_taxonomy.py` 中 `future_prompt_voice_type` 已通过结构 Contract，但旧 `_VOICE_TYPE_DISPLAY_NAMES` 把展示映射当白名单并抛出 `ValueError: 不支持的发声类型: future_prompt_voice_type`，证明只改 Prompt 时导出链仍会断裂。
- 同一 Unit 批次结果为 5 failed / 689 passed；其余 4 个失败分别来自旧固定 Pydantic enum、旧数据库七值 CHECK、字符串子串扫描误判 `unknown_voice_type`、旧文档措辞断言，均按新设计改为等价且更精确的约束，没有删除/跳过失败测试制造通过。

## Green / 回归证据

实现 HEAD `b1afd47c5529e358818b4c5a2376c65325babadb`：

- CI run `33149645595`：completed / success；CI Gate success。
- Repository Quality job `98778461981`：
  - `scripts/contracts/generate.py` + Orval + drift + compatibility 全部成功；
  - Ruff：`529 files already formatted`，`All checks passed!`；
  - mypy：`Success: no issues found in 254 source files`；
  - Unit：694 passed；Contract：92 passed；API：38 passed；
  - architecture / table ownership / Secret / docs 全部通过；
  - Wheel `aima_ugc-0.1.0-py3-none-any.whl` 构建、安装、import 成功；
  - frontend Vitest：44 passed；production build 成功；Playwright：31 passed。
- PostgreSQL Integration job `98778462011`：PostgreSQL 18.4；空库 `alembic upgrade head` 到 `20260828_0030 (head)`，`alembic check` 为 `No new upgrade operations detected.`；历史 Migration compatibility 成功；Platform 1 passed、Database 25 passed、Job 13 passed、Collection 90 passed、Content 33 passed、Ingestion 17 passed。
- Full-stack Acceptance run `33149645589`：success。
- Runtime Acceptance run `33149645638`：success。
- Developer Tooling Compatibility run `33149645695`：Windows Development/Compose 与 Linux Local Development 均 success。

最终 Ready HEAD `c151deb56d2b4bd8268397dd5cd624d6639bfca9`：

- Change Completion Gate run `33150114872`：completed / success，Coding completion-gate tests 与 changed-PR Ready Check 均通过。
- CI run `33150114931`、Runtime Acceptance `33150114876`、Full-stack Acceptance `33150114971`、Developer Tooling Compatibility `33150114894`：全部 completed / success。
- PR #254 无未解决 Review comment；由 Draft 转 Ready 后保持同一 HEAD，随后使用 `expected_head_sha` 正常 squash merge。

合并后 `main`：

- PR #254 squash merge commit：`911e52301ae179615a415e14c632caa17faf0d2a`；远程 `main` 已确认指向该提交。
- Change Completion Gate run `33150977993`：completed / success。
- CI run `33150978020`：completed / success；PostgreSQL Integration、Repository Quality 与 CI Gate 全部 success。
- Runtime Acceptance run `33150977994`：completed / success，canonical Compose、repository-relative host root、Windows overlay 全部通过。
- Full-stack Acceptance run `33150977999`：completed / success，真实 Excel Browser Full-stack 通过。
- Developer Tooling Compatibility run `33150978008`：completed / success，Windows 与 Linux 开发工具链均通过。

# 两阶段 Review

## A1 需求符合性 Review

- 当前 7 类机器值与 Prompt 自然语言七类一一对应，未改名、未增删、未迁移历史结果。
- `内容发声类型判断标准`、`先组合两层证据，再分类`、`七类边界与高混淆场景` 及用户要求保留的学习示例均仍在 Prompt；专门 Unit 测试锁定关键章节/示例。
- 动态修改测试 Prompt 新增 `community_voice` 后，正式 `ContentLabelingService` 无需修改 Python Literal 即可成功；非法值使用 `unknown_voice_type` 进入既有 Validation Retry。
- Python Contract、DB、OpenAPI/generated client 不再维护固定业务集合；DB 仍保留非空结构约束。
- Excel Review 发现并修复了第二套白名单：现有 7 类中文别名保持，未来新值原样透传。
- 结论：无未解决严重/重要需求偏差。

## A2 代码质量 Review

- Migration upgrade 只替换 CHECK，不 UPDATE 历史业务值；downgrade 对超出旧七值集合的数据 fail closed 并报告阻塞值。
- 新结构未引入依赖、配置中心、Taxonomy 表或额外抽象；无 Python/Node/lock 版本升级。
- generated Contract/client 使用仓库正式生成链，不手写 generated 文件作为事实源。
- AST 精确字符串测试替代子串扫描，避免错误码 `unknown_voice_type` 被误判为业务值硬编码。
- PR changed files 已复核，无临时 Workflow、`.tmp` 扫描结果或无关重构残留。
- CI 仅保留仓库既有 Pydantic/FastAPI/zipfile deprecation/negative-test warnings；没有本变更新增的测试失败或安全门禁失败。
- 结论：无未解决严重/重要代码质量 Finding。

# 文档影响

- `backend/src/aima_ugc/modules/analysis/README.md`：从“改 voice_type 必须改 Prompt+Contract+DB+Migration”更新为 Prompt Taxonomy 驱动。
- `docs/appendix/07_AI舆情打标与分析实现.md`：同步 Loader/Validator/DB 约束与后续修改入口。
- `docs/appendix/06_Excel统一数据导出与离线调试.md`：明确中文映射只负责展示兼容，新机器值未配置别名时原样导出。
- `docs/blueprint/03_数据库与文件存储.md`、`docs/blueprint/07_技术决策与实施门禁.md`：移除对当前七类业务列表的平行复制，明确 Prompt 唯一业务事实源和 DB/Contract 结构边界。
- 不复制完整 7 类业务定义到说明文档；业务定义、边界和示例继续只在当前 Prompt 保存。

# 交付

- 实现分支：`feature/voice-type-taxonomy`；PR merge 后已由仓库自动删除。
- 实现 PR：#254 `重构：统一 voice_type 为 Prompt Taxonomy 驱动`。
- 最终 PR HEAD：`c151deb56d2b4bd8268397dd5cd624d6639bfca9`。
- squash merge commit / `main` 实现基线：`911e52301ae179615a415e14c632caa17faf0d2a`。
- 归档分支：`docs/archive-voice-type-taxonomy-change`。
- 发布/部署：未执行生产部署；本 Change 只完成代码、Migration、Contract、文档、CI 与 Git 集成闭环。