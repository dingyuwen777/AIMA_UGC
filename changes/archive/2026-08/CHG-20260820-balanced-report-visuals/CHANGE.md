---
schema: rvc-change/v1
id: "CHG-20260820-balanced-report-visuals"
title: "舆情报告客观内容与视觉优化"
level: L2
status: done
owner: "codex"
branch: "main"
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - "platform-reporting"
  - "platform-export"
affected_paths:
  - "backend/src/aima_ugc/platform/presentation.py"
  - "backend/src/aima_ugc/platform/export"
  - "backend/src/aima_ugc/platform/reporting"
  - "backend/src/aima_ugc/adapters/providers/imports_test/README.md"
  - "tests/unit/platform"
  - "docs/blueprint/13-统一数据Excel导出与调试复用.md"
contracts: []
data_changes: []
---

# 目标

在不改变报告生成入口、输入数据结构和导出文件结构的前提下，使默认舆情报告同时呈现正面价值与负面风险，并统一提升 Markdown 与 Word 的图表、表格可读性。

# 成功标准

- [x] 默认报告的“舆情重点关注”同时给出正面表现和负面风险，统计口径与全量处理数据一致。
- [x] 默认 Markdown 使用当前项目目标阅读器可识别、Word 转换器也兼容的 Mermaid XY 图语法。
- [x] Word 饼图和折线图无外边框；所有折线系列宽度为 2.25 磅。
- [x] Word 表格使用全页宽度、稳定列宽、品牌色表头、隔行底色、合理内边距及数值对齐，内容不再挤在左侧窄列中。
- [x] Word 报告所有饼图的百分比标签显式固定为小数点后两位。
- [x] 统一 Excel 和 Markdown/Word 报告中的已知平台显示名统一使用中文，未知平台保持原值；底层平台 ID 和分组数据不变。
- [x] 既有自定义模板、公开 Python 调用入口、Excel 输出和报告数据 Contract 保持兼容。

# 范围

- 报告统计聚合与默认 Markdown 模板。
- Markdown 到 Word 的 Mermaid 兼容解析与 OOXML 图表、表格样式。
- 统一 Excel 与报告中的平台展示投影。
- 上述行为的单元测试、模块说明和阶段事实文档。

# 非目标

- 不调整 AI 打标逻辑、标签定义或原始数据清洗口径。
- 不修改公开 API、Pydantic Contract、数据库 Schema、Migration 或依赖版本。
- 不新增前端页面、图表渲染依赖或报告配置项。
- 不创建 PR、不推送远程、不发布。

# 必须保持不变

- `generate_excel_report()`、`convert_markdown_to_docx()` 等公开入口及参数保持不变。
- `labeled_data.xlsx` 的三个 Sheet、既有列名和报告周期过滤语义保持不变。
- Canonical、统一 Excel 输入 Contract 和内部平台 ID 继续使用英文稳定标识；中文化只发生在最终展示值。
- 自定义模板仍可继续使用既有 `RISK_SUMMARY`、负面统计占位符；新增正面占位符不要求旧模板采用。
- Word 文件仍由仓库内置 OOXML 生成器创建，不引入 `python-docx` 或外部图表依赖。

# 关键决策

- 采用正负面并列方案：正面与负面均按平台、一级标签、二级标签统计；摘要同时说明正面价值、负面风险和中性基盘，避免把“风险关注”误写成只有负面消息。
- Mermaid 输出采用 `xychart-beta` 作为兼容语法；仓库 Word 解析器继续同时接受 `xychart` 与 `xychart-beta`，避免破坏已有 Markdown。
- Word 图表在 ChartSpace 层显式设置无轮廓，折线系列按 DrawingML 宽度 `28575 EMU`（2.25 磅）输出。
- 表格视觉优化在通用 Word 表格生成器中一次实现，所有报告表格获得一致样式，但不改变单元格文本和表格数据。
- 平台中文名由平台层共享展示函数统一投影，Excel 导出和报告读取共同复用；已知中英文别名聚合到同一个中文展示名，未知平台原样保留。
- Word 饼图在共享 OOXML `dLbls` 中显式设置 `0.00%`，一次覆盖报告中的所有饼图，不增加配置项。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据
- [x] 为新增验收项建立失败测试并完成 Red/Green
- [x] 同步新增平台展示与饼图精度文档
- [x] 对新增范围取得新鲜验证证据

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/platform/test_offline_reporting.py tests/unit/platform/test_reporting_default_template.py tests/unit/platform/test_docx_package_structure.py -q`
- 相关测试：`uv run pytest tests/unit/platform -q`
- 静态检查/构建：`uv run ruff check backend/src/aima_ugc/platform/reporting tests/unit/platform`；四项仓库质量脚本。
- 样例验证：用真实 `labeled_data.xlsx` 生成报告，解包检查 OOXML，并通过本机可用的 Word/LibreOffice 渲染链路检查页面视觉；若本机缺少可用渲染器，明确记录未验证风险。

## 新鲜证据

- Red：目标用例在实现前为 `5 failed, 7 passed`，分别命中客观报告、`xychart-beta`、图表轮廓/折线宽度和表格样式断言。
- 目标测试：`12 passed in 1.59s`。
- 平台模块：`55 passed, 1 skipped in 4.16s`。
- `imports_test` 接线：`11 passed in 0.73s`。
- 全量单元测试：`442 passed, 1 skipped in 9.37s`。
- Ruff：检查通过，11 个目标文件格式检查通过。
- 质量门禁：架构、表 Owner、Secret 扫描、文档入口四项均退出码 0。
- 真实数据：按 2026-08-13 至 2026-08-19 生成 44,232 条内容、62,513 条标签记录的 Markdown/Word 样例，共 17 张 Office Chart。
- Microsoft Word：后台无警告打开 DOCX 并成功导出 38 页 A4 PDF；关键页及 38 页缩略总览未见空白页、遮挡、裁切或越界，表格与图表样式生效。
- 完整 `pytest -q` 未通过：`489 passed, 1 skipped, 8 failed, 99 errors`；失败均位于真实 PostgreSQL 集成测试，环境缺少 `.runtime/secrets/postgres_password`，未伪造 Secret 或绕过测试。

### 新增平台中文展示与饼图精度

- Red 1：新增共享展示函数测试在实现前因 `ModuleNotFoundError` 中止收集。
- Red 2：函数存在但未接线时，目标范围为 `6 failed, 32 passed`；失败分别命中 Excel 三个 Sheet、英文平台报告和 Word 饼图缺少 `numFmt`。
- 目标测试：`38 passed in 2.33s`。
- 平台模块：`63 passed, 1 skipped in 2.74s`。
- 全量单元测试：`467 passed, 1 skipped in 9.55s`。
- Ruff：受影响范围 `ruff check` 通过，15 个文件 `ruff format --check` 通过。
- mypy：8 个受影响源码文件无类型问题。
- 质量门禁：架构、表 Owner、Secret 扫描、文档入口四项均退出码 0。
- Wheel：`uv build --wheel` 成功；构建包包含共享平台展示模块、Excel Exporter 与报告模板。
- 完整 `pytest -q`：`514 passed, 1 skipped, 8 failed, 99 errors`；失败和错误仍全部位于需要真实 PostgreSQL 的集成测试，根因是本机缺少 `.runtime/secrets/postgres_password`，与本次展示层修改无关。
- 提交前最终验证：全量单元测试 `467 passed, 1 skipped in 10.63s`；受影响范围 Ruff 与格式检查通过；mypy 检查 186 个源码文件无问题；Wheel 和四项质量门禁通过。
- 全仓库 `ruff check .` 仍有 59 个既有问题，全部位于本次未修改的 `.agents` 工具和历史 Migration；本 Change 未混入无关格式修复。

# 文档影响

- 更新 `backend/src/aima_ugc/platform/reporting/README.md` 的报告结构、Mermaid 兼容语法和 Word 样式说明。
- 更新 `backend/src/aima_ugc/adapters/providers/imports_test/README.md` 的 Mermaid 当前语法、平台展示和饼图精度说明。
- 更新 `docs/blueprint/13-统一数据Excel导出与调试复用.md` 中受影响的报告当前事实。

# 交付

- Commit：`b8539b6`（报告内容与 Word 视觉）、`3f59d0a`（Excel 平台中文展示）、`066ca4f`（正式文档）；Change 归档由当前提交完成。
- PR：不创建。
- 远程推送：未执行。
- 发布：未执行。
