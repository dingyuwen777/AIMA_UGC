---
schema: rvc-change/v1
id: CHG-20260818-p1-offline-excel-sentiment
title: P1 Excel离线导入与舆情打标
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/p1-offline-excel-sentiment
created: 2026-08-18
updated: 2026-08-18
depends_on: []
affected_areas: [provider, analysis, export, testing, documentation]
affected_paths: [docs/blueprint/README.md, docs/blueprint/13-统一数据Excel导出与调试复用.md, docs/blueprint/14-临时P1-Excel离线导入与舆情打标.md, docs/blueprint/15-舆情AI打标与统一分析契约.md, backend/src/aima_ugc/adapters/providers/imports/, backend/src/aima_ugc/adapters/providers/imports_test/, backend/src/aima_ugc/adapters/providers/tikhub_test/, backend/src/aima_ugc/adapters/llm/, backend/src/aima_ugc/modules/analysis/, backend/src/aima_ugc/contracts/analysis/, backend/src/aima_ugc/contracts/export/, backend/src/aima_ugc/platform/export/, tests/]
contracts: [UnifiedContentRecordV1, ContentLabelAnalysisV1, UnifiedDataExcelV1]
data_changes: []
---

# 目标

在 Stage 8 正式开发前插入临时优先阶段 P1，以无数据库离线方式处理约 9 万条/批本地 XLSX：转换为 Canonical JSONL、关键词筛选、稳定身份去重、调用**全平台通用** AI 打标，把通过严格本地校验的分析结果回写同一 Provider-neutral JSONL，并通过全平台唯一共享 Excel Exporter 生成最终 `labeled_data.xlsx`。

P1 完成后删除临时 Stage 导航，但保留 File Import、Analysis/LLM、可编辑 Markdown Prompt/Taxonomy、JSONL 回写恢复、`UnifiedDataExcelV1` 和唯一共享 Exporter 等长期能力。

# 当前已确认设计

## JSONL 主链

```text
XLSX
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ AI + 本地校验 + 有界重试
→ 原子回写 deduplicated/contents.jsonl.analysis
→ labeled_data.xlsx
```

`raw_data.xlsx` 只是可选人工审阅旁路，不是 AI 或默认 `run_all()` 前置。

## Canonical / Analysis 边界

- `CanonicalContentV1` 继续只表达外部可观察事实；
- 去重后形成 `UnifiedContentRecordV1`；
- AI 派生结果放 `ContentLabelAnalysisV1`；
- 未来数据库由 Content Owner / Analysis Owner 分开持久化。

## Prompt 是具体标签体系唯一事实源

正式唯一文件：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

具体情感、一级、二级、父子关系、覆盖内容、典型表达、优先级和示例都只维护在这个 Markdown。

Markdown 内含机器可读 Taxonomy JSON；Python/Pydantic 不复制具体标签 `Enum/Literal` 或父子字典。

当前截图基线严格为：

```text
9 个一级标签
39 个二级标签
```

完整名称和判断标准见 Blueprint 15。

未来只是增删/改名标签、调整父子关系或判断标准时，只改 Prompt Markdown；代码无需改标签枚举。

## 本地校验必须存在

模型结果只有经过：

```text
JSON解析
→ 固定字段结构
→ item一一对应
→ 当前Prompt情感闭集
→ 当前Prompt一级闭集
→ 当前一级下二级闭集
→ 父子关系
```

全部通过后才能落盘。

大模型 Provider 的 JSON mode / structured output 只是辅助，不能替代本地 Validator。

## 可配置 Validation Retry

如果模型返回格式、字段、标签或父子关系不符合 Contract，Analysis Service 在配置上限内重新请求，直到合法或达到上限。

配置：

```text
max_validation_retries: int >= 0
```

语义：首次失败后允许额外重试次数，因此 0/1/2 对应最多总请求 1/2/3 次。

P1 人工入口暴露：

```python
MAX_VALIDATION_RETRIES = 2
```

`2` 是 README 推荐起始示例，可配置，不是不可修改长期常量。重试会产生额外模型调用/费用。

达到上限仍失败：记录 `analysis_status=failed` 和 attempt/error 事实，不猜标签、不写伪成功。

# 成功标准

- [x] Blueprint 明确 P1 是 Stage 8 前临时最高优先级。
- [x] Blueprint 明确 JSONL 主链、AI 回写同一 deduplicated JSONL、最终 Excel 同源。
- [x] Blueprint 明确 raw Excel 只是可选旁路。
- [x] Blueprint 13 明确唯一 `UnifiedDataExcelV1` + 唯一共享 Exporter。
- [x] Blueprint 15 明确 Prompt Markdown 是标签体系唯一事实源，Python 不硬编码具体标签枚举。
- [x] Blueprint 15 完整包含截图当前 9 一级 / 39 二级及优化判断标准。
- [x] Blueprint 15 明确模型业务输入只有 title/text/author.display_name，缺失填空字符串。
- [x] Blueprint 15 明确本地 Validator 强制存在，不能依赖模型保证。
- [x] Blueprint 15 明确 Validation Retry 有界且次数可配置，达到上限 fail closed。
- [x] Blueprint 14 同步 P1 的动态 Taxonomy、本地校验、重试和 README 门禁。
- [ ] `imports/` File Provider/Reader/Mapper 实现并通过自动测试。
- [ ] `imports_test/README.md`、`.env.example`、`test.py` 建立；单步函数和 `run_all()` 只调用生产实现。
- [ ] `convert()` 生成 `canonical/contents.jsonl`，错误逐行可定位。
- [ ] `filter_keywords()` 生成 `filtered/contents.jsonl`，保留 `matched_keywords`。
- [ ] `deduplicate()` 生成 `UnifiedContentRecordV1` 格式 `deduplicated/contents.jsonl`，冲突不静默覆盖。
- [ ] `UnifiedDataExcelV1` + 唯一共享 Exporter 落地，`tikhub_test` 删除平行 Excel 实现。
- [ ] `export_raw_excel()` 可选消费同一 deduplicated JSONL，默认 `run_all()` 不调用。
- [ ] `content_labeling_v1.md` 正式落地，机器 JSON 与判断说明完整包含当前 9 一级/39 二级。
- [ ] `PromptTaxonomyLoader`、Runtime Validator、`ContentLabelAnalysisV1`、Analysis Service/Port、Fake 建立；Python 无第二份业务标签枚举。
- [ ] `modules/analysis/README.md` 说明 Prompt/Taxonomy、本地校验、`max_validation_retries`、失败和费用语义。
- [ ] `imports_test/README.md` 说明 `MAX_VALIDATION_RETRIES` 配置、推荐示例和失败/checkpoint 查看方式。
- [ ] Fake 验证非法 JSON、未知标签、父子错配、缺 item 等会按配置重试；0/1/2 对应总尝试 1/2/3；上限后 failed。
- [ ] OpenAI-compatible LLM Adapter 建立；真实 Secret 不泄漏；真实调用默认关闭。
- [ ] AI 只发送 title/text/author.display_name；禁止字段有自动测试。
- [ ] 每次 Validation Retry 作为独立可观察 attempt 记录，不在 Transport 中隐藏。
- [ ] 合法结果先 checkpoint，再 `.tmp + fsync + atomic replace` 回写同一 deduplicated JSONL；成功 item 不重复付费。
- [ ] 最终 Excel 只读取回写后的 deduplicated JSONL。
- [ ] `run_all()` = convert → filter → deduplicate → AI label/retry/write-back → final Excel。
- [ ] 90k 性能证据完成，无失败证据不引入 pandas。
- [ ] 真实模型小样记录首次合法率、重试后成功率、平均尝试次数、最终失败率、人工标签差异、延迟、token/费用。
- [ ] 最终需求符合性/代码质量 Review、适用门禁和 CI 闭环。
- [ ] P1 完成后删除临时 Blueprint 14/P1 导航，归档 Change，Stage 8 恢复；Blueprint 13/15 长期保留。

# 范围

1. File Import Excel Profile/Reader/Identity/Mapper。
2. `imports_test` 无数据库人工入口。
3. Provider-neutral 关键词筛选与去重。
4. `UnifiedContentRecordV1`。
5. 全平台 `ContentLabelAnalysisV1`、PromptTaxonomyLoader、Runtime Validator、Analysis Service/LLM Port/Adapter。
6. 当前截图 9 一级/39 二级 Prompt 基线及动态可编辑规则。
7. 可配置有界 Validation Retry 与 attempt/checkpoint。
8. `UnifiedDataExcelV1` + 唯一共享 Exporter，迁移 `tikhub_test`。
9. 90k 性能与受控真实模型 Probe。

# 非目标

- 不写 PostgreSQL/Migration；
- 不新增正式 HTTP API/前端/Scheduler；
- 不把 JSONL 状态冒充正式 PostgreSQL Job Runtime；
- P1 当前不实现评论 AI 打标执行链；未来评论复用同一 Taxonomy/Validator；
- 不恢复 Budget/Cost Guard；
- 不新增 Redis/Kafka/Celery/SQLite；
- 不默认增加 pandas；
- 不让 Provider/Mapper 调 LLM；
- 不把源 Excel `全文情感` 当系统模型结果；
- 不把 AI 标签加入 Canonical；
- 不开始 Stage 8。

# 必须保持不变

- 模块化单体与 Provider → Canonical 边界；
- Mapper 纯转换；
- Secret 不进入 Git/日志/JSONL/Excel；
- 正式大文件导入/AI/导出未来仍走持久化 Job；
- 外部 ID 字符串；
- `tikhub_test`、`imports_test`、正式导出只有一套 Excel Contract/Exporter；
- 平台差异不能进入平台通用 AI Taxonomy；
- 模型失败不能被猜测修复成业务成功；
- Validation Retry 必须有上限并显式可配置；
- 不升级无关依赖、不覆盖其他 Active Change。

# 方案比较与用户决定

## 标签事实源

- 方案 A：Python Enum + Markdown Prompt 双维护。强类型但标签变化需改代码，容易漂移，否决。
- **方案 B（采用）**：一个 Markdown 同时含机器 Taxonomy JSON + 人类判断说明；Python 动态加载并严格校验。满足“以后标签变化只改 Prompt”。

## 模型输出可靠性

- 方案 A：相信模型 structured output，直接落盘。无法保证业务闭集/父子/批次完整，否决。
- **方案 B（采用）**：structured output 可用则利用，但本地 Validator 永远再校验；不合法按配置做有界新请求。

## 重试

- 方案 A：无限重试直到合法。可能无限费用/卡死，否决。
- 方案 B：第一次失败立即终止。稳定但大量可修复格式错误需要人工补跑，否决。
- **方案 C（采用）**：`max_validation_retries` 显式有界；达到上限 fail closed。

## 中间数据

- **采用** JSONL 主链 + checkpoint 恢复；不以 raw Excel 作为 AI 中间层。

## Canonical

- **采用** Canonical 保持外部事实，AI 放独立 Analysis；不污染 `observed_fields`。

## Excel

- **采用**一个 `UnifiedDataExcelV1` + 一个共享 Exporter。

## Excel 库

- **采用**现有 openpyxl read-only/write-only，90k 实测失败前不新增 pandas。

# 当前 checkpoint

**P1A 设计事实已按最新决定重新固化；下一最小正式单元仍是 P1B。**

P1B 开始前必须重新读取最新 `AGENTS.md`、RVC Skill、Blueprint README、14、15、13、本文及当前 branch/PR/CI/相关代码与测试。

# P1 子阶段

- [x] P1A：设计与阶段导航（已随用户新决定更新：动态 Prompt Taxonomy + 本地 Validator + 可配置 Validation Retry）。
- [ ] P1B：Excel imports + imports_test + convert。
- [ ] P1C：关键词过滤 + 去重 + UnifiedContentRecordV1。
- [ ] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移。
- [ ] P1E：PromptTaxonomyLoader + 完整 Prompt + Analysis Contract/Service/Port + Fake + README + Retry tests。
- [ ] P1F：真实 LLM Adapter + 最小输入 + Validation Retry attempts + checkpoint + JSONL 原子回写。
- [ ] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出。
- [ ] P1H：90k + 真实模型小样 + Review/CI + P1 收口。

# 验证

本轮属于设计文档修正，TDD 不适用。实际验证应包括：

- 重新读取 Blueprint 14/15/Change；
- 搜索旧 `7 个一级/17 个二级` 和“Python 硬编码标签”表述，确保没有残留为当前设计；
- 核对当前 9 个一级、39 个二级逐项覆盖截图；
- 比较 P1 branch 与 main 只包含授权范围；
- CI 状态如实记录，不把未完成/无关基线失败宣称通过。

# Git / PR / 发布

- Branch：`feature/p1-offline-excel-sentiment`。
- Draft PR：#66，继续使用同一个 PR。
- 自动合并：禁止。
- 发布：P1A 仅设计，不涉及生产部署。