---
schema: rvc-change/v1
id: "CHG-20260828-voice-type-classification-tables"
title: "统一发声类型中文 Taxonomy 与判断标准表格"
level: L2
status: in_progress
owner: "chatgpt"
branch: "feature/voice-type-classification-tables"
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
  - "backend/src/aima_ugc/platform/export/excel.py"
  - "backend/src/aima_ugc/modules/analysis/README.md"
  - "docs/appendix/06_Excel统一数据导出与离线调试.md"
  - "docs/appendix/07_AI舆情打标与分析实现.md"
  - "tests/unit/analysis/"
  - "tests/unit/platform/"
contracts: []
data_changes: []
---

# 目标

把 `voice_type` 统一为直接可展示的中文业务值，并把 Prompt 中相关性、发声类型、情感、一级/二级标签等判断标准统一整理为易读、易修改的 Markdown 表格；每个判断标准后保留或补充高混淆场景与示例，让模型既知道“有哪些合法值”，也知道“应该怎么判”。

后续修改发声类型的名称、数量、定义、边界和示例时，业务维护入口只保留当前 Prompt，不再要求同步 Python Contract、数据库 Schema、API、generated client 或 Excel 映射。

# 成功标准

- [ ] 机器 Taxonomy `voice_types` 直接使用 7 个中文实际值：`真实用户发声 / 品牌官方发声 / 门店经销商发声 / 营销推广发声 / 行业从业发声 / 媒体机构发声 / 无法判断`。
- [ ] `voice_type` 的 LLM 输出、数据库保存、API 返回和 Excel 展示均使用同一个实际值，不再维护英文机器名与中文展示名两套命名。
- [ ] `语义相关性判断标准` 使用表格，并在表格后保留高混淆场景/示例。
- [ ] `发声类型判断标准` 使用用户本轮提供的“推荐名称 / 核心定义 / 说明”表格，并保留两层证据、七类边界、高混淆场景和示例。
- [ ] `情感判断标准` 使用表格，并在表格后补充高混淆场景/示例。
- [ ] `一级/二级标签判断标准` 保持现有完整表格；其后继续保留多主题/边界冲突规则和标签示例，不改变 9 个一级/39 个二级标签集合或父子关系。
- [ ] 删除 Excel `_VOICE_TYPE_DISPLAY_NAMES` 与 `_voice_type_display_name()`，Excel 直接输出 `analysis.voice_type`。
- [ ] 历史 Analysis Result 不迁移、不重写；历史旧英文 `voice_type` 保持原值，若再次导出则原样显示，不静默改义。
- [ ] Pydantic Contract、PostgreSQL Schema/Migration、HTTP API、OpenAPI/generated client 不修改。
- [ ] Analysis README、AI Appendix、Excel Appendix 只同步会因本次设计过期的说明/示例；Blueprint 未复制具体分类时不机械修改。
- [ ] 目标 Unit、完整 PR CI、Completion Gate 取得本轮新鲜绿色证据；两阶段 Review 无未解决严重/重要 Finding。

# 范围

- 修改 `content_labeling_v3.md` 的机器 Taxonomy、判断标准排版、发声类型定义/边界/示例及相关输出示例。
- 删除 Excel 发声类型翻译层，直接输出实际值。
- 更新直接依赖上述事实的测试。
- 更新确实会过期的模块 README / Appendix。

# 非目标

- 不修改固定输出字段 `item_no/relevance/voice_type/sentiment/labels`。
- 不修改 `relevance` 的合法值。
- 不修改 sentiment 当前四值。
- 不修改一级/二级标签机器 Taxonomy。
- 不修改 Contract、OpenAPI、generated TypeScript Client、数据库表或 Alembic Migration。
- 不迁移历史 Analysis Result。
- 不新增前端发声类型筛选/展示 UI。
- 不升级依赖或 Runtime。

# 已确认关键决策

1. `voice_type` 不再使用英文机器值；中文推荐名称就是实际业务值和最终展示值。
2. 当前 7 类为：真实用户发声、品牌官方发声、门店经销商发声、营销推广发声、行业从业发声、媒体机构发声、无法判断。
3. “媒体机构发声”覆盖新闻媒体、资讯号、政府、协会、学校、企业机构等报道、资讯、公告和公共事务内容。
4. “营销推广发声”覆盖非官方、非门店主体的品牌活动、达人/KOC 种草、合作推广、任务打卡、爱玛骑遇团等组织化营销。
5. “行业从业发声”覆盖修车、电动车行业、二手车、车行、竞品从业者等维修、行业讨论、交易或专业视角发声。
6. 旧英文值属于历史结果事实，不迁移、不重新解释；本次只改变新 Prompt 产生的新结果。
7. Excel 不解析 Prompt，也不维护映射，直接展示 Analysis Result 的实际 `voice_type` 值。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 使用用户提供的 7 类发声类型定义 | user:本轮发声类型分类 | not_satisfied | Prompt 待修改 |
| R2 | `voice_type` 实际值直接使用中文推荐名称，不要两套命名 | user:展示名称就是实际值 | not_satisfied | Taxonomy/Prompt 待修改 |
| R3 | 情感、发声类型等判断标准都像一级/二级标签一样使用表格 | user:判断标准统一表格展示 | not_satisfied | Prompt 待重排 |
| R4 | 每个判断标准表格后保留示例或高混淆场景帮助 AI 判断 | user:表格后保留示例/高混淆场景 | not_satisfied | Prompt 待整理 |
| R5 | 其他代码后续不应因发声类型变化而修改，并删除已经失去职责的旧转换代码 | user:其他代码零影响并删除无关代码 | not_satisfied | Excel 映射待删除，核心 Contract/DB/API 已确认动态 |
| R6 | 审计其他文档，只同步真实过期事实，不复制第二套 Taxonomy | user:检查其他文档 | not_satisfied | README/Appendix 已定位，待最终 diff 复核 |
| R7 | 修改完成后正常合并到 `main` | user:改完合并主分支 | not_satisfied | PR/CI/merge 待完成 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 新中文 voice_types、Prompt 表格/边界/示例、Excel 原样输出、旧映射代码删除 |
| 接口 / Contract | required | 固定 JSON 结构必须保持不变；Contract/generated drift 证明未误改公共接口 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改 DB Schema/Migration/Repository；历史值不迁移 |
| 用户 / Workflow Acceptance | not_applicable | 不修改页面/按钮/用户操作入口 |
| 跨组件 Golden Path | not_applicable | 不改 API/Worker/Job 接线，完整 CI 作为额外回归证据 |
| External Dependency / Provider Probe | not_applicable | 不修改 LLM/TikHub HTTP 协议或外部字段 |
| Build / Package / Runtime | required | Repository Quality、Wheel、frontend build 等完整 PR CI 不回归 |
| Docs / Governance / Other | required | Completion Gate、docs/secret/architecture gates；文档影响审计 |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取本轮用户决定、AGENTS、当前 Prompt、Analysis README、AI/Excel Appendix 与实际代码。
- [ ] change_coverage：逐项核对中文实际值、表格化、示例/高混淆场景、零下游映射维护、历史不迁移。
- [ ] reverse_audit：按 Prompt → Loader/Validator → Result → DB/API → Excel 正反向检查，确认分类变化没有额外代码维护点。
- [ ] unresolved_cleared：Ready 前清零 `not_satisfied`，合并动作按门禁顺序执行。

# 任务

- [x] 从最新 main 恢复仓库事实并完成代码/文档影响审计。
- [x] 创建专用分支与 L2 Change。
- [ ] Red：新增当前设计回归测试并取得因旧 Prompt/旧 Excel 映射而失败的证据。
- [ ] Green：更新 Prompt Taxonomy、表格、边界和示例。
- [ ] Green：删除 Excel 发声类型翻译层。
- [ ] 同步必要 README/Appendix，不机械修改 Blueprint。
- [ ] 运行目标测试和完整 CI。
- [ ] 完成 Completion Audit 与 A1/A2 Review，切换 `ready_for_review`。
- [ ] PR 正常合并 main，并验证 main push CI。
- [ ] 独立归档 Change。

# 文档影响

预计需要同步：

- `backend/src/aima_ugc/modules/analysis/README.md`：旧 `voice_type == user_voice` 示例会过期。
- `docs/appendix/07_AI舆情打标与分析实现.md`：V3 JSON 示例仍使用旧英文 voice type。
- `docs/appendix/06_Excel统一数据导出与离线调试.md`：当前仍描述 `_VOICE_TYPE_DISPLAY_NAMES` 展示映射。

当前 Blueprint/导航文档没有复制具体 7 类业务定义，原则上无需修改；最终以 PR diff 和全仓事实扫描为准。

# 交付

- 分支：`feature/voice-type-classification-tables`
- PR：待创建
- 发布/部署：本任务不执行生产部署。
