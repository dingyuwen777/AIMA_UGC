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
affected_paths: [docs/blueprint/README.md, docs/blueprint/13-统一数据Excel导出与调试复用.md, docs/blueprint/14-临时P1-Excel离线导入与舆情打标.md, backend/src/aima_ugc/adapters/providers/imports/, backend/src/aima_ugc/adapters/providers/imports_test/, backend/src/aima_ugc/adapters/providers/tikhub_test/, backend/src/aima_ugc/adapters/llm/, backend/src/aima_ugc/modules/analysis/, backend/src/aima_ugc/contracts/analysis/, backend/src/aima_ugc/contracts/export/, backend/src/aima_ugc/platform/export/, tests/]
contracts: [UnifiedDataExcelV1]
data_changes: []
---

# 目标

在 Stage 8 正式开发前插入临时优先阶段 P1，以无数据库离线方式处理每批约 9 万条本地 XLSX：转换为 Canonical JSONL、按“爱玛”等关键词筛选、按稳定内容身份去重、调用可替换 LLM 做正面/中性/负面打标，并通过全平台唯一共享 Excel Exporter 生成最终 `labeled_data.xlsx`。

P1 完成后删除临时 Blueprint 阶段导航，但保留 File Import、Analysis/LLM、JSONL 调试能力、`UnifiedDataExcelV1` 和唯一共享 Exporter 等长期可复用能力。

# 成功标准

- [x] Blueprint 明确 P1 是 Stage 7 与 Stage 8 之间的临时最高优先级，P1 完成前暂停 Stage 8。
- [x] Blueprint 明确业务数据主链为 `XLSX → canonical JSONL → filtered JSONL → deduplicated JSONL → analysis JSONL → labeled XLSX`。
- [x] Blueprint 明确 `raw_data.xlsx` 只是可选人工审阅旁路，不是 `label_sentiment()` 或默认 `run_all()` 的前置依赖。
- [x] Blueprint 明确 `label_sentiment()` 直接消费 `deduplicated/contents.jsonl` 并输出 `analysis/results.jsonl`。
- [x] Blueprint 明确整个后端只维护一个 `UnifiedDataExcelV1` 和一个共享 Excel Exporter；`tikhub_test`、`imports_test`、未来正式导出必须复用它。
- [ ] `imports/` 正式 File Provider/Reader/Mapper 实现并通过自动测试。
- [ ] `imports_test/README.md`、`.env.example`、`test.py` 建立；单步函数和 `run_all()` 都只调用生产实现。
- [ ] `convert()` 生成 `canonical/contents.jsonl`，输入错误逐行可定位。
- [ ] `filter_keywords()` 生成 `filtered/contents.jsonl` 并保留 `matched_keywords`，不修改 Canonical 原文。
- [ ] `deduplicate()` 按 `(platform, external_content_id)` 生成 `deduplicated/contents.jsonl`，冲突单独记录且不静默覆盖。
- [ ] `UnifiedDataExcelV1` 与唯一共享 Exporter 落地；`tikhub_test` 删除平行 Excel 生成逻辑并复用共享实现。
- [ ] `export_raw_excel()` 可选消费 deduplicated JSONL，但默认 `run_all()` 不调用它。
- [ ] Analysis Contract/Service/Port 与 Fake Classifier 建立，正/中/负语义固定为“对爱玛品牌/产品/服务的态度”。
- [ ] OpenAI-compatible LLM Adapter 建立；Secret 不泄漏；真实调用默认关闭；非法结构化结果关闭失败。
- [ ] `label_sentiment()` 直接读取 deduplicated JSONL，支持基于稳定 `analysis_key` 的断点恢复，不重复已成功付费调用。
- [ ] `export_labeled_excel()` 用 deduplicated JSONL + analysis JSONL 生成最终统一 XLSX；生成后重新打开验证。
- [ ] `run_all()` 默认顺序固定为 convert → filter → deduplicate → label → final Excel。
- [ ] `90,000 × 13` 真实相似 Fixture 在目标 Windows 环境取得 wall time、rows/s、峰值 RSS 和文件大小证据；无失败证据不引入 pandas。
- [ ] 100—200 条人工确认样本完成受控真实 LLM Probe，并记录结构化响应成功率、标签差异、延迟、token/费用和失败边界。
- [ ] P1 完整质量门禁、需求符合性 Review 和代码质量 Review 无严重/重要问题。
- [ ] P1 完成后删除临时 Blueprint 14 和 README P1 导航，归档 Change，Stage 8 恢复为下一正式阶段。

# 范围

1. File Import Excel Profile/Reader/Identity/Mapper。
2. 无数据库 `imports_test` 人工入口和 JSONL 运行目录。
3. Provider-neutral 关键词筛选和稳定内容去重。
4. Analysis Contract/Service/LLM Port/Adapter 与断点恢复。
5. `UnifiedDataExcelV1` 和唯一共享 Excel Exporter。
6. `tikhub_test` Excel 实现收敛到共享 Exporter。
7. 90k 本地性能验证与受控真实模型小样 Probe。
8. P1 临时 Blueprint 生命周期和多网页对话续接。

# 非目标

- 不写 PostgreSQL；
- 不新增 Alembic Migration；
- 不新增正式 HTTP API/前端页面；
- 不接 Scheduler；
- 不把 JSONL 状态伪装成正式 PostgreSQL Job Runtime；
- 不做评论情感分析；
- 不恢复 Budget/Cost Guard；
- 不新增 Redis/Kafka/Celery/SQLite；
- 不默认新增 pandas；
- 不让 File Provider/Mapper 直接调用 LLM；
- 不把源 Excel 的 `全文情感` 当系统模型结果；
- 不开始 Stage 8。

# 必须保持不变

- 模块化单体和既有 Provider → Canonical 边界；
- Mapper 保持纯转换，不读数据库、不发 HTTP、不做业务分类；
- 真实 Secret 不进入代码、Git、日志、JSONL、Excel；
- 正式批量导入/AI/导出未来仍进入持久化 Job；P1 无数据库只是一条独立验证/紧急离线路径；
- 外部 ID 使用字符串；时间继续遵守 Canonical/UTC 与人工显示时区规则；
- `tikhub_test`、`imports_test` 和未来正式导出不能长期维护平行 Workbook Contract 或 Exporter；
- 不升级无关依赖，不覆盖其他 Active Change 或用户修改。

# 已确认关键决策

## A. 中间数据格式

- 方案 A1：每一步都写 XLSX。人工可读，但 Excel 成为隐式业务中间层，重复 IO、难断点、强耦合 Exporter，否决。
- 方案 A2：全流程在内存 list/DataFrame 中传递。实现短，但 9 万行长链路内存/断点/单步复核较差，否决。
- **方案 A3（采用）**：业务数据中间产物统一 JSONL，只有输入是源 XLSX、最终交付默认生成 labeled XLSX；`run_summary.json` 等运行元数据例外使用 JSON。

## B. raw Excel

- 方案 B1：去重后强制生成 raw Excel，再从它进入 LLM。增加无价值中间层且让分析依赖展示格式，否决。
- **方案 B2（采用）**：`export_raw_excel()` 保留为可选人工审阅旁路；`label_sentiment()` 直接依赖 `deduplicated/contents.jsonl`，默认 `run_all()` 不生成 raw Excel。

## C. Excel Exporter

- 方案 C1：`tikhub_test`、`imports_test`、正式系统各自维护 Exporter。字段/样式/安全规则会漂移，否决。
- **方案 C2（采用）**：建立一个 Provider-neutral `UnifiedDataExcelV1` 和一个共享 `platform/export/excel.py` 核心函数；所有调用方复用。若最新 Architecture Check 证明目录不合法，只调整共享目录，不改变“一 Contract + 一 Exporter”。

## D. 无数据库优先实现

- **方案 D1（采用）**：P1 用 JSONL 做可恢复离线编排，核心 Reader/Mapper/Analysis/Exporter 都按未来正式实现复用边界编写；最快满足当前业务且不污染数据库。
- 方案 D2：直接接现有 PostgreSQL/Job。长期更完整，但扩大当前紧急范围、增加 Migration/事务/运行门禁，延期到后续正式阶段。

## E. Excel 库

- **方案 E1（采用）**：继续使用仓库已锁定 `openpyxl` 的 read-only/write-only 模式，并以 90k 性能证据决定是否需要替代。
- 方案 E2：直接引入 pandas。当前数据流不需要 DataFrame 核心能力且会扩大依赖/兼容/内存验证，在无性能失败证据前不采用。

# 兼容与数据

- 本 Change 第一版无数据库 Schema/Migration，`data_changes=[]`。
- 输入源 Excel 通过版本化 Profile 适配，不反向修改 Canonical Contract 以迎合供应商私有列。
- `UnifiedDataExcelV1` 是输出展示 Contract，不成为 Canonical 或分析事实源。
- raw/labeled Workbook 使用同一 Sheet/列/顺序；raw 的分析列为空，labeled 填结构化分析结果。
- 后续正式系统导出可以直接复用同一 Exporter，不允许重新发明平台级函数。

# 安全、性能、部署与回滚

- 安全：真实模型默认关闭；API Key 只从未提交 `.env`/Secret 边界读取；公式注入、ID 精度、URL 和长文本由共享 Exporter 统一处理。
- 性能：业务数据逐行读取/写 JSONL；最终 XLSX 使用流式写出；90k 先实测再决定依赖。
- 部署：P1 不改变生产部署、数据库或 Migration；只在开发/离线环境人工运行。
- 回滚：P1 branch/PR 未合并时直接停止使用即可；无数据库迁移。合并后代码可按普通 Git revert 回滚，历史离线输出文件不自动删除。

# 任务

- [x] P1A：建立 P1 Blueprint/导航和统一 Excel 长期边界。
- [ ] P1B：实现 Excel imports + imports_test + convert。
- [ ] P1C：实现关键词筛选、去重和 JSONL 冲突记录。
- [ ] P1D：实现 `UnifiedDataExcelV1` + 唯一共享 Exporter，迁移 `tikhub_test`。
- [ ] P1E：实现 Analysis Contract/Service/Port + Fake。
- [ ] P1F：实现真实 OpenAI-compatible LLM Adapter 与 `label_sentiment()`。
- [ ] P1G：实现 `run_all()`、断点恢复和 run summary。
- [ ] P1H：90k 性能、真实小样、最终 Review/CI 和 P1 收口。

# 当前 checkpoint

P1A 已完成设计固化。**下一最小正式单元是 P1B**；后续新网页对话不得直接进入 P1C/P1D 或 Stage 8。

P1B 开始前必须重新读取最新目标分支 `AGENTS.md`、RVC Skill、Blueprint README、临时 P1 Blueprint、13、本文以及当时的分支/PR/代码/测试事实。

# 验证

## P1A 本轮验证计划

本轮只有文档/设计写入，不伪造 Red-Green。替代验证：

- 重新读取 branch 上新增/修改文档；
- 核对 Blueprint 链接、P1 当前优先级、JSONL 主链和唯一 Exporter 表述；
- 比较 branch 与 `main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf` 只包含 P1A 授权范围文档；
- 检查 GitHub 可用 CI/状态；没有执行过的本地 `check_docs.py` 不宣称通过。

## 新鲜证据

- 已重新读取 `docs/blueprint/README.md`、`13-统一数据Excel导出与调试复用.md`、`14-临时P1-Excel离线导入与舆情打标.md` 和本文，确认 P1 当前优先级、JSONL 主链、raw Excel 可选旁路、`label_sentiment()` 输入和唯一共享 Exporter 表述一致。
- `compare main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf...feature/p1-offline-excel-sentiment`：branch `ahead_by=4`、`behind_by=0`；创建 Draft PR 前只有 4 个授权文档发生变化：新增 P1 Change、修改 Blueprint README、修改 Blueprint 13、新增 Blueprint 14；没有功能代码、依赖、Migration 或无关文件变化。
- Draft PR `#66` 已创建，创建时 head 为 `d9d669c93f0d55a6ef10d3459508ec6a5a35f7a1`，状态 `Open / Draft / 未合并`。
- PR 创建后 GitHub Actions 已触发，检查时 `CI`、Stage 6/7 相关 workflow 均为 `in_progress`；尚无完成结论，因此**当前不能宣称 CI 通过**。
- 本轮没有本地仓库终端，未实际执行 `uv run python scripts/quality/check_docs.py`、Ruff 或其他本地质量命令；P1A 只能声明 GitHub re-fetch/compare 和 PR/CI 状态已验证。
- 功能、90k 性能、真实 LLM 均未开始验证。

# 文档影响

P1 进行期间：

- `docs/blueprint/README.md` 保存当前 P1 临时导航；
- `docs/blueprint/14-临时P1-Excel离线导入与舆情打标.md` 保存 P1 设计与子阶段；
- `docs/blueprint/13-统一数据Excel导出与调试复用.md` 永久保存唯一 Excel Contract/Exporter 长期规则。

P1 完成后删除临时 14 和 README 的 P1 导航，但 13 的长期设计保留。

# Git / PR / 发布

- 基线：`main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`。
- 分支：`feature/p1-offline-excel-sentiment`。
- P1A 当前最新提交：本次验证记录提交后以 branch 最新 head 为准。
- PR：`#66 P1：离线 Excel 导入与舆情打标`，`Open / Draft / 未合并`；后续 P1B—P1H 继续同一 PR。
- CI：已触发且当前仍在运行；未宣称通过。
- 合并：未授权自动合并，不执行。
- 发布：P1A 仅设计文档，不涉及部署。