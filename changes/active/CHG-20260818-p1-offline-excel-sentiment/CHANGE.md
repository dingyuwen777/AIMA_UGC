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

在 Stage 8 正式开发前插入临时优先阶段 P1，以无数据库离线方式处理每批约 9 万条本地 XLSX：转换为 Canonical JSONL、按“爱玛”等关键词筛选、按稳定内容身份去重、调用**全平台通用** AI 打标能力输出情感 + 一级 + 二级标签，把成功分析回写同一 Provider-neutral JSONL，并通过全平台唯一共享 Excel Exporter 生成最终 `labeled_data.xlsx`。

P1 完成后删除临时 Blueprint 阶段导航，但保留 File Import、Analysis/LLM、可编辑 Markdown Prompt、统一 JSONL 处理记录、`UnifiedDataExcelV1` 和唯一共享 Exporter 等长期可复用能力。

# 成功标准

- [x] Blueprint 明确 P1 是 Stage 7 与 Stage 8 之间的临时最高优先级，P1 完成前暂停 Stage 8。
- [x] Blueprint 明确主链为 `XLSX → canonical JSONL → filtered JSONL → deduplicated JSONL → AI 回写同一 deduplicated JSONL → labeled XLSX`。
- [x] Blueprint 明确 `raw_data.xlsx` 只是可选人工审阅旁路，不是 AI 或默认 `run_all()` 的前置依赖。
- [x] Blueprint 明确整个后端只维护一个 `UnifiedDataExcelV1` 和一个共享 Excel Exporter；`tikhub_test`、`imports_test`、未来正式导出必须复用它。
- [x] Blueprint 15 固化平台通用 AI 标签体系：情感只允许正面/中性/负面/混合；一级标签 7 个；二级标签 17 个；二级→一级严格父子映射。
- [x] Blueprint 15 明确首版每条内容只选择 1 个情感、1 个一级、1 个二级标签；具体业务主题优先于泛品牌形象，`其他/无明确分类` 最后兜底。
- [x] Blueprint 15 明确模型业务输入只有 `title`、`text`、`author.display_name`，缺失填空字符串；ID、URL、指标、Provider、命中关键词、源全文情感等不得发送给模型。
- [x] Blueprint 15 明确运行时 Prompt 必须为可编辑 Markdown 文件，并以实际 Prompt SHA-256 参与分析 identity。
- [x] Blueprint 明确 AI 成功结果回写 `deduplicated/contents.jsonl` 的 `analysis` 区块；`analysis/checkpoints.jsonl` 只用于恢复/费用安全，不作为下游事实源。
- [x] Blueprint 明确最终 Excel 只读取回写后的统一 JSONL；不再 join 独立 `analysis/results.jsonl`。
- [x] Blueprint 明确 `CanonicalContentV1` 不增加 AI 标签；未来数据库由 Content Owner 与 Analysis Owner 分别持久化内容事实和派生分析。
- [ ] `imports/` 正式 File Provider/Reader/Mapper 实现并通过自动测试。
- [ ] `imports_test/README.md`、`.env.example`、`test.py` 建立；单步函数和 `run_all()` 都只调用生产实现。
- [ ] `convert()` 生成 `canonical/contents.jsonl`，输入错误逐行可定位。
- [ ] `filter_keywords()` 生成 `filtered/contents.jsonl` 并保留 `matched_keywords`，不修改 Canonical 原文。
- [ ] `deduplicate()` 按 `(platform, external_content_id)` 生成 `UnifiedContentRecordV1` 格式的 `deduplicated/contents.jsonl`，冲突单独记录且不静默覆盖。
- [ ] `UnifiedDataExcelV1` 与唯一共享 Exporter 落地；`tikhub_test` 删除平行 Excel 生成逻辑并复用共享实现。
- [ ] `export_raw_excel()` 可选消费同一 deduplicated JSONL 并忽略 Analysis；默认 `run_all()` 不调用它。
- [ ] `ContentLabelAnalysisV1`、闭集 taxonomy、严格父子映射、Analysis Service/Port 与 Fake Classifier 建立。
- [ ] 建立 `modules/analysis/prompts/content_labeling_v1.md`，用户可直接修改调优；Prompt 内容 Hash 参与缓存/恢复身份。
- [ ] 构造 LLM 输入时只传 title/text/author.display_name；字段缺失填空字符串；自动测试证明无禁止字段泄漏。
- [ ] OpenAI-compatible LLM Adapter 建立；Secret 不泄漏；真实调用默认关闭；非法标签、父子错配、非法 JSON/批次映射全部 fail closed。
- [ ] AI 成功结果先安全 checkpoint，再通过临时文件 + fsync + atomic replace 回写同一个 deduplicated JSONL；崩溃恢复不重复已成功付费调用。
- [ ] `export_labeled_excel()` 只读取回写后的 deduplicated JSONL 生成最终统一 XLSX；生成后重新打开验证。
- [ ] `run_all()` 默认顺序固定为 convert → filter → deduplicate → AI label/write-back → final Excel。
- [ ] `90,000 × 13` 真实相似 Fixture 在目标 Windows 环境取得 wall time、rows/s、峰值 RSS 和文件大小证据；无失败证据不引入 pandas。
- [ ] 100—200 条人工确认样本完成受控真实 LLM Probe，覆盖 4 个情感、7 个一级标签和易混淆二级边界，并记录结构化成功率、标签差异、延迟、token/费用和失败边界。
- [ ] P1 完整质量门禁、需求符合性 Review 和代码质量 Review 无严重/重要问题。
- [ ] P1 完成后删除临时 Blueprint 14 和 README P1 导航，归档 Change，Stage 8 恢复为下一正式阶段；Blueprint 13/15 作为长期设计继续保留。

# 范围

1. File Import Excel Profile/Reader/Identity/Mapper。
2. 无数据库 `imports_test` 人工入口和 JSONL 运行目录。
3. Provider-neutral 关键词筛选和稳定内容去重。
4. `UnifiedContentRecordV1`：Canonical + matched keywords + 可空 Analysis 的处理/交换记录。
5. 平台通用 `ContentLabelAnalysisV1`、4 情感 + 7 一级 + 17 二级闭集 taxonomy、Markdown Prompt、Analysis Service/LLM Port/Adapter 与断点恢复。
6. `UnifiedDataExcelV1` 和唯一共享 Excel Exporter。
7. `tikhub_test` Excel 实现收敛到共享 Exporter。
8. 90k 本地性能验证与受控真实模型小样 Probe。
9. P1 临时 Blueprint 生命周期和多网页对话续接。

# 非目标

- 不写 PostgreSQL；
- 不新增 Alembic Migration；
- 不新增正式 HTTP API/前端页面；
- 不接 Scheduler；
- 不把 JSONL 状态伪装成正式 PostgreSQL Job Runtime；
- 不做评论 AI 打标；
- 不恢复 Budget/Cost Guard；
- 不新增 Redis/Kafka/Celery/SQLite；
- 不默认新增 pandas；
- 不让 File Provider/Mapper 直接调用 LLM；
- 不把源 Excel 的 `全文情感` 当系统模型结果；
- 不把 AI 标签加入 Canonical `observed_fields`；
- 不开始 Stage 8。

# 必须保持不变

- 模块化单体和既有 Provider → Canonical 边界；
- Mapper 保持纯转换，不读数据库、不发 HTTP、不做业务分类；
- `CanonicalContentV1` 只表达外部可观察事实；AI 标签由 Analysis 模块拥有；
- 真实 Secret 不进入代码、Git、日志、JSONL、Excel；
- 正式批量导入/AI/导出未来仍进入持久化 Job；P1 无数据库只是一条独立验证/紧急离线路径；
- 外部 ID 使用字符串；时间继续遵守 Canonical/UTC 与人工显示时区规则；
- `tikhub_test`、`imports_test` 和未来正式导出不能长期维护平行 Workbook Contract 或 Exporter；
- 平台/Provider 差异不能渗透到平台通用 AI Prompt；
- 不升级无关依赖，不覆盖其他 Active Change 或用户修改。

# 已确认关键决策

## A. 中间数据格式

- 方案 A1：每一步都写 XLSX。Excel 成为业务中间层，重复 IO、难断点、强耦合 Exporter，否决。
- 方案 A2：全流程在内存 list/DataFrame 中传递。9 万行长链路内存/断点/单步复核较差，否决。
- **方案 A3（采用）**：业务数据中间产物统一 JSONL，只有输入是源 XLSX、最终默认生成 labeled XLSX；运行元数据可使用 JSON。

## B. AI 结果存放

- 方案 B1：AI 单独输出 `analysis/results.jsonl`，最终导出/数据库再 join。可追溯但形成两个业务事实源，用户要求也不满足，否决。
- **方案 B2（采用）**：checkpoint 只做恢复；成功 Analysis 通过原子改写回填 `deduplicated/contents.jsonl.analysis`，最终 Excel/未来导入都从同一 Provider-neutral 记录读取。

## C. Canonical 是否增加标签

- 方案 C1：把 sentiment/一级/二级标签直接加进 `CanonicalContentV1`。会把模型派生判断伪装成 Provider 观察事实，污染 Mapper/observed_fields，否决。
- **方案 C2（采用）**：Canonical 保持不变；新增 `UnifiedContentRecordV1` 处理记录和独立 `ContentLabelAnalysisV1`。未来入库拆分 Content Owner 与 Analysis Owner。

## D. raw Excel

- 方案 D1：去重后强制生成 raw Excel，再从它进入 LLM。增加无价值中间层且让分析依赖展示格式，否决。
- **方案 D2（采用）**：`export_raw_excel()` 仅为可选人工审阅；AI 直接依赖 deduplicated JSONL，默认 `run_all()` 不生成 raw Excel。

## E. Excel Exporter

- 方案 E1：`tikhub_test`、`imports_test`、正式系统各自维护 Exporter。字段/样式/安全规则会漂移，否决。
- **方案 E2（采用）**：一个 Provider-neutral `UnifiedDataExcelV1` + 一个共享 `platform/export/excel.py` 核心函数；所有调用方复用。若 Architecture Check 证明目录不合法，只调整共享目录，不改变“一 Contract + 一 Exporter”。

## F. AI 标签数量

- **方案 F1（采用）**：每条内容输出且只输出 1 个情感标签 + 1 个一级标签 + 1 个二级标签；二级必须属于所选一级。多主题时按 Blueprint 15 的主题优先级选核心主题。
- 方案 F2：一级/二级允许多标签。当前会扩大 Contract、Excel/数据库字段和人工验收复杂度，用户未要求，暂不采用。

## G. Prompt 维护

- **方案 G1（采用）**：完整业务 Prompt 存 Markdown 文件，运行时加载并计算 `prompt_sha256`；用户可直接编辑调优。
- 方案 G2：Prompt 硬编码 Python。修改成本高且不可独立调优，否决。

## H. 模型输入最小化

- **方案 H1（采用）**：模型业务输入只有 title/text/author.display_name，缺失填空字符串；批量仅增加临时 item_no 做映射。
- 方案 H2：把平台、URL、指标、关键词、源标签等全部发送。增加隐私/成本并可能引入偏置，且违反用户明确要求，否决。

## I. 无数据库优先实现

- **方案 I1（采用）**：P1 用 JSONL 做可恢复离线编排，核心 Reader/Mapper/Analysis/Exporter 按未来正式实现复用边界编写。
- 方案 I2：直接接 PostgreSQL/Job。长期更完整但扩大当前紧急范围，延期到后续正式阶段。

## J. Excel 库

- **方案 J1（采用）**：继续使用仓库已锁定 `openpyxl` 的 read-only/write-only 模式，并以 90k 性能证据决定是否需要替代。
- 方案 J2：直接引入 pandas。当前数据流不需要 DataFrame 核心能力且扩大依赖/兼容/内存验证，在无性能失败证据前不采用。

# AI 标签闭集

长期机器定义由 Blueprint 15 和未来 `ContentLabelAnalysisV1` 维护，本 Change 只记录业务决定摘要。

情感：

```text
正面 / 中性 / 负面 / 混合
```

一级 → 二级：

```text
品牌形象 → 正面形象 / 负面形象 / 中性形象
产品反馈 → 性能/质量问题 / 功能/设计建议 / 使用体验
服务反馈 → 售后问题 / 门店服务 / 服务表扬
价格与政策 → 价格评价 / 促销/补贴政策
渠道与销售 → 线上购买体验 / 线下门店体验
品牌活动 → 活动反馈 / 营销内容评价
其他 → 竞品对比 / 无明确分类
```

# 兼容与数据

- 本 Change 第一版无数据库 Schema/Migration，`data_changes=[]`。
- 输入源 Excel 通过版本化 Profile 适配，不反向修改 Canonical Contract 以迎合供应商私有列。
- `UnifiedContentRecordV1` 是处理/交换结构；不是要求数据库一行保存一个大 JSON。
- `ContentLabelAnalysisV1` 是全平台派生分析 Contract；未来进入数据库时由 Analysis Owner 持久化到 `analysis_runs/content_analysis_results` 等正式结构。
- `UnifiedDataExcelV1` 是输出展示 Contract，不成为 Canonical 或分析事实源。
- raw/labeled Workbook 使用同一 Sheet/列/顺序；raw 忽略 Analysis，labeled 填结构化分析结果。
- 后续正式系统导出可以直接复用同一 Exporter，不允许重新发明平台级函数。

# 安全、性能、部署与回滚

- 安全：真实模型默认关闭；API Key 只从未提交 `.env`/Secret 边界读取；模型只接收三个批准业务字段；公式注入、ID 精度、URL 和长文本由共享 Exporter 统一处理。
- 性能：业务数据逐行读取/写 JSONL；AI checkpoint 后受控批次原子回写；最终 XLSX 流式写出；90k 先实测再决定依赖。
- 部署：P1 不改变生产部署、数据库或 Migration；只在开发/离线环境人工运行。
- 回滚：P1 branch/PR 未合并时直接停止使用即可；无数据库迁移。合并后代码可按普通 Git revert 回滚，历史离线输出文件不自动删除。

# 任务

- [x] P1A：建立 P1 Blueprint/导航、统一 Excel 长期边界和平台通用 AI 标签长期契约。
- [ ] P1B：实现 Excel imports + imports_test + convert。
- [ ] P1C：实现关键词筛选、`UnifiedContentRecordV1` 去重和 JSONL 冲突记录。
- [ ] P1D：实现 `UnifiedDataExcelV1` + 唯一共享 Exporter，迁移 `tikhub_test`。
- [ ] P1E：实现 `ContentLabelAnalysisV1`、闭集 taxonomy、Markdown Prompt、Analysis Service/Port + Fake。
- [ ] P1F：实现真实 OpenAI-compatible LLM Adapter、最小输入、checkpoint 与 JSONL 原子回写。
- [ ] P1G：实现 `run_all()`、断点恢复和 run summary；最终导出只读回写后的统一 JSONL。
- [ ] P1H：90k 性能、真实标签小样、最终 Review/CI 和 P1 收口。

# 当前 checkpoint

P1A 已按最新用户决定重新固化，包含附件标签体系、平台通用 Analysis、Markdown Prompt、最小模型输入、JSONL 同源回写和未来数据库 Owner 边界。**下一最小正式单元仍是 P1B**；后续新网页对话不得直接进入 P1C/P1D/P1E 或 Stage 8。

P1B 开始前必须重新读取最新目标分支 `AGENTS.md`、RVC Skill、Blueprint README、临时 P1 Blueprint 14、永久 AI Blueprint 15、Excel Blueprint 13、本文以及当时的分支/PR/代码/测试事实。

# 验证

## P1A 文档验证

本阶段只有设计/文档变化，不伪造 Red-Green。替代验证：

- 重新读取 branch 上新增/修改 Blueprint 和 Change；
- 核对 4 情感、7 一级、17 二级、父子映射与附件一致；
- 核对模型输入仅 title/text/author.display_name；
- 核对 deduplicated JSONL 回写和最终 Excel 同源读取；
- 比较 branch 与 main 只包含 P1A 授权文档；
- 检查 Draft PR/CI 状态；没有执行过的本地命令不宣称通过。

## 既有新鲜证据

- P1A 初版已建立 Draft PR `#66`，`Open / Draft / 未合并`。
- 初版 `compare main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf...feature/p1-offline-excel-sentiment` 只包含 P1 文档，无功能代码、依赖、Migration 或无关文件。
- 新需求固化后的最终 branch head、diff 和 CI 状态需在本轮文档更新完成后重新获取并记录。
- 功能、90k 性能、真实 LLM 均未开始验证。

# 文档影响

P1 进行期间：

- `docs/blueprint/README.md` 保存当前 P1 临时导航；
- `docs/blueprint/14-临时P1-Excel离线导入与舆情打标.md` 保存 P1 临时实施边界；
- `docs/blueprint/13-统一数据Excel导出与调试复用.md` 永久保存唯一 Excel Contract/Exporter 长期规则；
- `docs/blueprint/15-舆情AI打标与统一分析契约.md` 永久保存平台通用 AI taxonomy、Prompt、输入输出、JSONL/数据库边界。

P1 完成后删除临时 14 和 README 的 P1 导航，但 13/15 的长期设计保留。

# Git / PR / 发布

- 初始 P1 基线：`main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`；每轮开始仍需重新核验当前 main。
- 分支：`feature/p1-offline-excel-sentiment`。
- PR：`#66 P1：离线 Excel 导入与舆情打标`，`Open / Draft / 未合并`；后续 P1B—P1H 继续同一 PR。
- CI：每次 branch head 变化后以最新 workflow 事实为准，运行中不得宣称通过。
- 合并：未授权自动合并，不执行。
- 发布：P1A 仅设计文档，不涉及部署。