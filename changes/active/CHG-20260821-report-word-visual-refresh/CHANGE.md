---
schema: rvc-change/v1
id: CHG-20260821-report-word-visual-refresh
title: 横向 A4 Word 舆情报告视觉重构
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/report-landscape-word-visuals
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas:
  - reporting
affected_paths:
  - backend/src/aima_ugc/platform/reporting
  - tests/unit/platform
  - pyproject.toml
  - uv.lock
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
contracts: []
data_changes: []
---

# 目标

在不改变统一 Excel、统计口径、AI 标签、数据库和既有报告入口语义的前提下，把离线 `report.docx` 重构为适合领导阅读、横屏/飞书预览和正式汇报的 A4 横向专业研究报告：正文、Editorial Table、Ranking、Office 原生 Chart、词云图片和分页统一使用克制的报告视觉体系。

# 成功标准

- [ ] `report.docx` 使用 A4 Landscape，正文页边距和图表宽度适配横向页面。
- [ ] 普通 Word 表格改为 Editorial Table：轻分隔、无深蓝整块表头、数字右对齐、表头可重复、单行不跨页。
- [ ] Top 类统计可由 Markdown 元数据渲染为 Word 原生 Ranking，保留可编辑文字/数字和原生占比条。
- [ ] bar / line 继续使用 Office 原生 Chart + 内嵌 XLSX，并显示可读数据标签；长分类使用横向 bar。
- [ ] 情感每日趋势拆为正面+中性主趋势、负面+混合低量级趋势，不使用双 Y 轴，缺失系列合理降级。
- [ ] 一级议题与热点关键词根据同一 `_ReportStats` 自动生成稳定的中文 Editorial Word Cloud PNG，并进入 `report.md` 和 DOCX `word/media/`。
- [ ] 更换合法 `labeled_data.xlsx` 后，Ranking、Office Chart、Word Cloud、Markdown 和 DOCX 全部自动重生成；输入 Excel Hash 不变。
- [ ] DOCX ZIP/XML/Chart/XLSX/media/relationships/图片结构均可校验，并实际生成样例做页面级渲染检查。
- [ ] reporting 目标测试、imports_test 相关回归、Ruff、Mypy 和仓库适用质量门禁获得本轮新鲜证据。

# 范围

- 调整 reporting 的 OOXML 页面、样式、表格、Ranking、Chart 和图片打包能力。
- 在 Markdown 转 Word 子集内增加最小的 `<!-- aima:... -->` 展示元数据和 Markdown 图片解析。
- 增加独立的报告视觉 Token 与词云渲染实现。
- 调整默认报告模板和现有统计结果到视觉组件的映射。
- 只新增实际需要的 Python 图像依赖并同步锁文件。
- 同步 reporting README 与 Blueprint 13 的长期事实描述。

# 非目标

- 不修改 UnifiedDataExcelV1、Excel 共享 Exporter、Canonical、Analysis Contract、taxonomy、数据库 Schema/Migration、API、前端、正式 Report Job、PDF 发布链、飞书上传或 LLM 结论生成。
- 不把 Office 柱状图/折线图/饼图改成 PNG，不创建第二套 Word 正文模板或第二套报告统计逻辑。
- 不引入 pandas、python-docx、Pandoc、在线 Mermaid/词云服务或浏览器截图链。

# 必须保持不变

- 公共 `generate_excel_report()` 的调用参数和核心入口语义。
- `imports_test.generate_report()`、`run_all()` 现有报告接线及显式 `report_excel_path` 行为。
- `report_date_range` 的北京时间闭区间筛选、fail-closed 和内容/标签明细交叉一致性检查。
- `_ReportStats` 或等价当前统计结果作为报告数字的唯一事实源。
- 输入 Workbook 只读；报告生成前后不得修改输入 Excel。
- Office Chart 的内嵌 XLSX 可编辑能力和未支持渲染类型 fail-closed 行为。
- Markdown 模板仍是正文结构的唯一长期维护入口。

# 关键决策

- 页面固定采用 A4 横向，约 15 mm 正文页边距；视觉参数集中在 reporting presentation/theme 层，不反向污染前端 Design Token。
- 采用混合渲染：正文/表格/Ranking 为 Word 原生 OOXML；bar/line/pie 为 Office Chart；词云为自动生成的高分辨率 PNG。
- Ranking 通过最小 Markdown HTML comment 元数据选择 Word 专属展示样式，Markdown 本身仍保留标准表格。
- 情感每日趋势固定拆分为主趋势（正面、中性）和低量级趋势（负面、混合），不使用双 Y 轴。
- 中文词云不提交字体文件；运行时解析系统 CJK 字体，找不到可用字体时明确失败。
- 依赖选择以当前 Python 3.14、官方兼容/许可证和最小依赖面为准；不因发现新版升级无关依赖。
- Git 从最新 main 建立本 feature 分支；完成后先通过仓库质量门禁，再按用户授权把验证通过的结果集成到远程 main，不绕过失败的 CI/PR 门禁。

# 任务

- [x] 调查当前规则、Blueprint、reporting 实现、测试、依赖、Active Change/OpenSpec 和 main 基线。
- [ ] 建立页面/表格/Ranking/Chart/图片/词云的失败测试并确认正确 Red。
- [ ] 实现横向 A4、主题、Editorial Table、Ranking 和分页规则。
- [ ] 实现 Office Chart data labels、横向 bar 与情感每日趋势拆分。
- [ ] 实现中文 Editorial Word Cloud、Markdown 图片和 DOCX media 打包校验。
- [ ] 更新默认模板与视觉映射，保持统计和 imports_test 接线不变。
- [ ] 同步受影响 README / Blueprint 长期事实。
- [ ] 完成需求符合性复核、代码质量复核、目标/回归/静态/结构/视觉验证。
- [ ] 完成 Git 集成并记录真实 commit / PR / CI / merge 状态。

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/platform/test_offline_reporting.py tests/unit/platform/test_docx_package_structure.py tests/unit/platform/test_reporting_default_template.py -q`
- 接线回归：`uv run pytest tests/unit/platform/test_imports_test_reporting.py tests/unit/collection/test_p1g_imports_run_all.py -q`
- 静态检查：`uv run ruff check .`；`uv run mypy backend/src tests`
- 仓库适用质量门禁：`uv run python scripts/quality/check_architecture.py`、`check_table_ownership.py`、`scan_secrets.py`、`check_docs.py`
- 生成物：实际生成 `report.md`、`report.docx`、`assets/*.png`；检查 ZIP CRC、XML、Chart、XLSX、media、relationships、图片解码、页面方向和输入 Excel Hash。
- 视觉：优先用可用的 LibreOffice 渲染 DOCX→PDF/页面图并逐页检查；无法实际运行 Microsoft Word/WPS/飞书时明确剩余兼容风险。

## 新鲜证据

- 尚未执行实现后的验证。
- 当前宿主 Git CLI 无法联网克隆 GitHub；仓库事实读取和远程 Git 写入使用已连接 GitHub App。后续代码执行/视觉验证需使用可用本地构造环境或 GitHub Actions，不能伪造本地仓库测试结果。

# 文档影响

- `backend/src/aima_ugc/platform/reporting/README.md`：需要更新当前 Word 页面、表格、Ranking、Chart、图片/词云和验证能力事实。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：需要更新当前离线 Report Renderer 的 Word 展示规则与新增词云/图片边界。
- `imports_test` README 仅在调用方式或产物目录事实变化时最小同步；不把视觉逻辑写入调试入口。

# 交付

- Commit：进行中。
- PR：未创建。
- 发布：未执行。
