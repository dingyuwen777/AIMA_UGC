---
schema: rvc-change/v1
id: "CHG-20260828-voice-type-chinese-values"
title: "发声类型直接使用中文业务名称作为机器值"
level: L3
status: in_progress
owner: "chatgpt"
branch: "feature/voice-type-chinese-values"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "analysis"
  - "export"
  - "docs"
  - "tests"
affected_paths:
  - "backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md"
  - "backend/src/aima_ugc/modules/analysis/README.md"
  - "backend/src/aima_ugc/platform/export/excel.py"
  - "README.md"
  - "docs/01_代码结构与修改导航.md"
  - "docs/appendix/01_PostgreSQL查询与调试实战.md"
  - "docs/appendix/06_Excel统一数据导出与离线调试.md"
  - "docs/appendix/07_AI舆情打标与分析实现.md"
  - "docs/appendix/13_AI大规模打标与成本优化方案.md"
  - "docs/blueprint/03_数据库与文件存储.md"
  - "docs/blueprint/07_技术决策与实施门禁.md"
  - "frontend/tests"
  - "frontend/e2e"
  - "scripts/performance"
  - "tests"
contracts: []
data_changes:
  - "analysis_content_results.voice_type 新写入值语义"
---

# 目标

将当前 `voice_type` 与 sentiment、一级/二级标签统一：合法机器值直接使用中文业务名称，不再维护英文稳定 ID 或英文→中文展示映射。

目标七类：

```text
真实用户发声
品牌官方发声
门店经销商发声
营销推广发声
行业从业发声
媒体机构发声
无法判断
```

用户明确要求：不需要旧英文 `voice_type` 的历史兼容读取。本次不回填、不迁移、不翻译已有数据库历史值，也不保留 `user_voice -> 真实用户发声` 等专门兼容映射。

# 方案比较与已确认决定

## 方案 A：继续英文机器 ID + 中文展示名

优点：历史字符串稳定、改中文名称时无需改变机器值。

缺点：与 sentiment/labels 当前直接使用中文业务值的模式不一致；Prompt/Excel 需要维护额外映射。

结论：不采用。

## 方案 B：`value + name` 结构化 voice type

优点：稳定 ID 与中文名称显式分离。

缺点：增加 Taxonomy 结构、Loader 和消费者复杂度；当前业务没有多语言/独立显示名生命周期需求。

结论：不采用。

## 方案 C：中文业务名称直接作为合法机器值

优点：与 sentiment/labels 完全一致；Prompt、LLM 输出、数据库新写入、API、Excel 不再需要英文→中文映射；后续业务修改入口更直接。

代价：中文业务名称本身成为持久化值；改名就是值变化。用户已明确接受，同时明确不需要旧英文历史兼容读取。

结论：采用。

# 成功标准

- [x] Prompt `voice_types` 只包含七个中文业务名称，不包含当前英文机器 ID。
- [x] 发声类型判断表删除“机器值”列，正文、高混淆场景、示例直接使用中文分类名称。
- [x] 新 LLM 输出、RuntimeTaxonomyValidator 合法值校验、`ContentLabelAnalysisV3.voice_type` 新写入语义均直接使用中文业务名称。
- [x] Excel 不再维护当前或历史英文 `voice_type` 的专门中文展示映射，直接输出 `voice_type` 字符串。
- [x] 不保留旧英文值兼容读取/映射，不新增数据回填或 Alembic Migration；历史 Migration 保持原样。
- [x] 当前 README / Blueprint / Appendix / Analysis README 已同步，不再把英文机器值描述成当前事实。
- [x] Contract/OpenAPI/generated client 字段结构不变，预期生成物零漂移；等待最终永久 CI 复验。
- [ ] 最终 HEAD 的目标测试、完整永久 CI、两阶段 Review、Ready Gate 全绿后正常合并 `main`，再验证 main push CI 并独立归档 Change。

# 范围

- 修改 Prompt Taxonomy 与自然语言发声类型判断文本。
- 删除 Excel 英文 `voice_type` 展示映射/兼容逻辑。
- 更新直接依赖旧英文值的测试、Fixture、性能脚本、前端 Mock/Acceptance 数据和当前技术文档。
- 全仓审计旧英文 voice type 是否仍被生产逻辑、测试、文档、Fixture 或生成物依赖。

# 非目标

- 不修改 `voice_type` 字段名或 V3 JSON 结构。
- 不把 `voice_type` 改成 enum/对象结构。
- 不修改 PostgreSQL 列类型或新增 Migration。
- 不迁移、不重写数据库中已有英文历史值。
- 不新增旧英文→中文兼容层。
- 不批量重新执行历史 AI 打标。
- 不修改 sentiment、一级/二级标签集合。
- 不新增前端页面功能。

# 兼容、Migration、部署与回滚

## 兼容策略

这是用户明确批准的破坏性业务值切换：从本变更生效后的新 Analysis Result 开始，`voice_type` 使用中文值。旧英文历史值不属于当前 Taxonomy，也不提供专门兼容读取或展示映射；若旧值仍被读取或导出，只按原始字符串处理。

## Migration / 数据

- PostgreSQL `voice_type` 已是通用非空字符串结构，本次不需要 Schema Migration。
- 不执行数据 backfill/update；已有英文值保持原样。
- 历史 Alembic Migration 中的旧英文 CHECK 是历史迁移事实，保持不改，确保空库可以完整重放迁移链。
- `taxonomy_sha256` / `prompt_sha256` 继续区分新旧规则版本。

## 部署顺序

无 Schema 依赖，应用代码与 Prompt 同版本部署即可；不需要先跑 Alembic。

## 回滚

回滚到上一应用/Prompt 版本即可，不需要数据库 downgrade。回滚期间已经产生的中文 `voice_type` 行不做数据改写；旧版本若通过通用字符串读取这些结果，按原始字符串处理，不新增临时兼容机制。

# 风险

- 历史查询可能同时看到旧英文字符串和新中文字符串；这是本轮明确接受的无兼容结果，不做统一展示。
- 修改 Prompt 会改变 `prompt_sha256` 和 `taxonomy_sha256`；既有 stale/current 语义按现有 Analysis 机制处理，不重写历史结果。
- 当前 Excel V1/V2 投影过去借助英文 `unknown` + 展示映射得到“无法判断”；删除映射后必须显式使用中文 `无法判断`，已增加回归测试锁定。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 所有当前发声类型直接使用中文业务名称作为合法机器值，不维护英文机器 ID | user:2026-08-28-中文voice-type机器值 | not_satisfied | Prompt/Fixture/测试已实施中文值；有效 Red 已证明旧实现失败，等待最终 Green CI |
| R2 | 不需要旧英文 `voice_type` 的历史兼容读取/映射 | user:2026-08-28-删除英文历史兼容 | not_satisfied | Excel 映射常量/helper 已删除；Red 明确证明旧 `user_voice`/`other_organization` 会被翻译，Green 改为原样输出；等待最终 CI |
| R3 | 与 sentiment、一级/二级标签保持同一种 Taxonomy 维护模式 | user:2026-08-28-统一Taxonomy模式 | not_satisfied | Prompt `voice_types` 已变为中文字符串数组，发声类型表删除机器值列；等待 Validator/Contract/CI 最终验证 |
| R4 | 修改所有真实受影响代码/测试/文档，不假设只改 Prompt | AGENTS.md + user:完成后推送主分支 | not_satisfied | 两轮全仓 Runner 扫描确认生产代码额外影响为 Excel；并发现实时 README/Blueprint/Appendix、前端/Full-stack/测试 Fixture 与 10 处 `unknown` 当前值，均已同步；等待最终扫描/CI |
| R5 | 正常推送并合并 `main`，不绕过仓库门禁 | user:2026-08-28-推送主分支 | not_satisfied | Draft PR #263 已建立，等待 Green/Review/Ready/merge/main push CI |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Prompt Loader/Validator、新七类中文值、英文值不再合法、Excel 原样输出且无英文兼容映射、V1/V2 缺省“无法判断” |
| 接口 / Contract | required | `voice_type` 字段结构仍为字符串；Pydantic/OpenAPI/generated client 无意外结构漂移 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 真实回归证明通用字符串列可保存中文且既有 Migration 链无变化 |
| 用户 / Workflow Acceptance | required | 现有真实 Excel/声音广场相关工作流不因中文值切换破坏 |
| 跨组件 Golden Path | required | 现有 Full-stack Golden Path 证明 API/Worker/DB/Excel 接线保持可用 |
| 外部依赖 Probe | not_applicable | 不修改 LLM HTTP 协议、Provider 字段或外部服务能力，无需真实付费 Probe |
| Build / Package / Runtime | required | 仓库正式 CI 的 Ruff/mypy/Wheel/frontend build/runtime/tooling |
| Docs / Governance / Other | required | README/Blueprint/Appendix/Change、Secret/docs、Ready Gate、两阶段 Review |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

- [x] 重新读取最新 `main` 的 AGENTS、Coding/Review、Blueprint 导航与 AI 领域当前事实。
- [x] 检查并发 Figma Change/归档；与本任务生产路径和业务语义无冲突。
- [x] 全仓扫描旧英文 voice type 依赖，建立精确影响清单；确认当前核心 Contract/DB/API 无具体七值硬编码，历史 Migration 保持不改。
- [x] Red：CI run `33159875378` 的 Repository Quality job `98811507063` 在 generated/Ruff/mypy 全绿后取得 `4 failed, 701 passed`，失败精确来自旧英文 Prompt Taxonomy/机器值列和 Excel 英文兼容翻译。
- [x] Green：更新 Prompt、Excel、实时文档、当前测试/Fixture/Full-stack/前端 Mock/性能脚本。
- [x] 收口扫描发现 10 处 `voice_type="unknown"` 当前夹具，已全部同步为 `无法判断`；两处 `user_voice` 命中仅为测试函数英文名称，不是机器值。
- [ ] 运行最终 HEAD 目标测试与完整永久 CI，确认 generated drift、PostgreSQL、Full-stack、Runtime、Tooling 全绿。
- [ ] 执行最终无旧英文当前机器值扫描、A1/A2 Review、独立代码质量 Review与 Completion Audit。
- [ ] Change 进入 `ready_for_review`，最终 HEAD 永久门禁全绿。
- [ ] PR 转 Ready 后 squash merge `main`，验证 main push CI。
- [ ] 独立 docs-only PR 归档 Change。

# Red / 调试证据

## 有效业务 Red

- Red HEAD：`7037b90d5acc518f577ff6f98c10488ec9154a82`；PR #263 CI run `33159875378`，Repository Quality job `98811507063`。
- generated Contract/Orval drift、Ruff、mypy 在 Unit 前全部 success，Red 不是格式、类型或生成物噪声。
- Unit：`4 failed, 701 passed`：
  1. Prompt Taxonomy 仍返回英文七值，而测试要求七个中文业务名称；
  2. Prompt 发声类型表仍存在“推荐名称/机器值”双层；
  3. Excel 把 `user_voice` 翻译为“真实用户发声”，违反“无历史兼容翻译”；
  4. Excel 把 `other_organization` 翻译为“其他机构传播”，违反“无历史兼容翻译”。
- V1/V2 缺省“无法判断”测试在 Red 阶段被旧 `unknown -> 无法判断` 展示映射间接满足；删除映射后由同一测试保证底层投影必须直接使用中文 `无法判断`。

# 实现事实

- Prompt `voice_types` 当前目标实现：`真实用户发声 / 品牌官方发声 / 门店经销商发声 / 营销推广发声 / 行业从业发声 / 媒体机构发声 / 无法判断`。
- 发声类型自然语言表格当前只有 `发声类型 / 核心定义 / 说明` 三列，高混淆场景和示例直接引用中文分类值。
- `ContentVoiceType` 继续是长度受限字符串；Runtime Validator 继续按当前 Prompt Taxonomy membership fail closed。
- Excel `_VOICE_TYPE_DISPLAY_NAMES` 和 `_voice_type_display_name()` 已删除；`analysis.voice_type` 直接输出；V1/V2 无 voice type 时投影为 `无法判断`。
- 不新增 Migration，不修改历史 Migration，不回填历史数据库值。

# 文档影响

已同步当前实时事实源/导航：

- `README.md`
- `docs/01_代码结构与修改导航.md`
- `backend/src/aima_ugc/modules/analysis/README.md`
- `docs/appendix/01_PostgreSQL查询与调试实战.md`
- `docs/appendix/06_Excel统一数据导出与离线调试.md`
- `docs/appendix/07_AI舆情打标与分析实现.md`
- `docs/appendix/13_AI大规模打标与成本优化方案.md`
- `docs/blueprint/03_数据库与文件存储.md`
- `docs/blueprint/07_技术决策与实施门禁.md`

完整七类业务定义仍只在 Prompt 维护；其他文档只描述当前边界/示例，不复制第二份完整 Taxonomy。

# Git / 交付

- 分支：`feature/voice-type-chinese-values`
- Draft PR：#263 `调整：发声类型直接使用中文业务机器值`
- 合并：只有最终 HEAD 的 Change Gate / CI / Runtime / Full-stack / Tooling 全部成功后才允许正常 squash merge
- 生产部署：不在本任务执行
