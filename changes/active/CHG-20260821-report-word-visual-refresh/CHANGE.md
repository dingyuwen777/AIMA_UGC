---
schema: rvc-change/v1
id: CHG-20260821-report-word-visual-refresh
title: 横向 A4 Word 舆情报告视觉重构
level: L2
status: ready_for_review
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
  - .github/workflows/ci.yml
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
contracts: []
data_changes: []
---

# 目标

在不改变统一 Excel、统计口径、AI 标签、数据库和既有报告入口语义的前提下，把离线 `report.docx` 重构为适合领导阅读、横屏/飞书预览和正式汇报的 A4 横向专业研究报告：正文、Editorial Table、Ranking、Office 原生 Chart、词云图片和分页统一使用克制的报告视觉体系。

# 成功标准

- [x] `report.docx` 使用 A4 Landscape，正文页边距和图表宽度适配横向页面。
- [x] 普通 Word 表格改为 Editorial Table：轻分隔、无深蓝整块表头、数字右对齐、表头可重复、单行不跨页。
- [x] Top 类统计可由 Markdown 元数据渲染为 Word 原生 Ranking，保留可编辑文字/数字和原生占比条。
- [x] bar / line 继续使用 Office 原生 Chart + 内嵌 XLSX，并显示可读数据标签；长分类使用横向 bar。
- [x] 情感每日趋势拆为正面+中性主趋势、负面+混合低量级趋势，不使用双 Y 轴，缺失系列合理降级。
- [x] 一级议题与热点关键词根据同一 `_ReportStats` 自动生成稳定的中文 Editorial Word Cloud PNG，并进入 `report.md` 和 DOCX `word/media/`。
- [x] 更换合法 `labeled_data.xlsx` 后，Ranking、Office Chart、Word Cloud、Markdown 和 DOCX 全部自动重生成；输入 Excel Hash 不变。
- [x] DOCX ZIP/XML/Chart/XLSX/media/relationships/图片结构均可校验，并实际生成样例做页面级渲染检查。
- [x] reporting 目标测试、imports_test 相关回归、Ruff、Mypy 和仓库适用质量门禁获得本轮新鲜证据。

# 范围

- 调整 reporting 的 OOXML 页面、样式、表格、Ranking、Chart 和图片打包能力。
- 在 Markdown 转 Word 子集内增加最小的 `<!-- aima:... -->` 展示元数据和 Markdown 图片解析。
- 增加独立的报告视觉 Token 与词云渲染实现。
- 调整默认报告模板和现有统计结果到视觉组件的映射。
- 只新增实际需要的 Python 图像依赖并同步锁文件。
- 同步 reporting README 与 Blueprint 13 的长期事实描述。
- Linux CI 为真实中文词云测试安装 Noto CJK；当前仓库没有 Dockerfile/Compose，未提前创建生产镜像配置。

# 非目标

- 不修改 UnifiedDataExcelV1、Excel 共享 Exporter、Canonical、Analysis Contract、taxonomy、数据库 Schema/Migration、API、前端、正式 Report Job、PDF 发布链、飞书上传或 LLM 结论生成。
- 不把 Office 柱状图/折线图/饼图改成 PNG，不创建第二套 Word 正文模板或第二套报告统计逻辑。
- 不引入 pandas、python-docx、Pandoc、在线 Mermaid/词云服务或浏览器截图链。
- 不在当前不存在 Dockerfile/Compose 的仓库里预造部署文件；未来生产镜像建立时需安装可用 CJK 字体。

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
- 中文词云不提交字体文件；运行时解析系统 CJK 字体，找不到可用字体时明确失败。CI 使用系统包 `fonts-noto-cjk` 验证 Linux 路径。
- 依赖只新增 Pillow 12.3.0，并由现有 uv 锁文件精确锁定；没有升级其他无关依赖。
- Git 从最新 main 建立本 feature 分支；验证通过后仍通过 PR 与仓库门禁集成，不绕过失败检查。

# 任务

- [x] 调查当前规则、Blueprint、reporting 实现、测试、依赖、Active Change 和 main 基线。
- [x] 建立页面/表格/Ranking/Chart/图片/词云的失败测试并确认正确 Red。
- [x] 实现横向 A4、主题、Editorial Table、Ranking 和分页规则。
- [x] 实现 Office Chart data labels、横向 bar 与情感每日趋势拆分。
- [x] 实现中文 Editorial Word Cloud、Markdown 图片和 DOCX media 打包校验。
- [x] 更新默认模板与视觉映射，保持统计和 imports_test 接线不变。
- [x] 同步受影响 README / Blueprint 长期事实。
- [x] 完成需求符合性复核、代码质量复核、目标/回归/静态/结构/视觉验证。
- [ ] 完成 PR 合并、main 合并后验证与 Change 归档。

# 验证

## Red 证据

- PR 初始 Red head 的 Stage 2 Platform 实际运行 `tests/unit/platform`：**65 passed, 6 failed**。6 个失败分别对应 A4 方向、折线数据标签、横向 bar、表格横向宽度、Ranking 和 PNG media/image_count，证明失败来自待实现行为而不是环境噪音。

## Green / Refactor 证据

GitHub Actions 集成验证 run `32450181453`（Python 3.14.7、uv 0.12.3、Noto CJK）：

- `uv lock`、`uv lock --check`、`uv sync --locked`：成功；新增并锁定 `pillow==12.3.0`。
- `uv run pytest tests/unit/platform/test_docx_package_structure.py tests/unit/platform/test_reporting_visuals.py tests/unit/platform/test_offline_reporting.py tests/unit/platform/test_reporting_default_template.py -q`：**19 passed**。
- `uv run pytest tests/unit/platform/test_imports_test_reporting.py tests/unit/collection/test_p1g_imports_run_all.py -q`：**11 passed**。
- `uv run ruff format --check backend tests scripts`：**421 files already formatted**。
- `uv run ruff check backend tests scripts`：**All checks passed**。
- `uv run mypy backend/src`：**Success: no issues found in 227 source files**。
- 实际生成 `report.md`、`report.docx`、`assets/primary_topics_wordcloud.png`、`assets/keyword_wordcloud.png`；artifact `report-visual-sample` ID `9435412615`，ZIP SHA-256 `06cf3a460754e0b93e4bfecf57867c5b7bb8f8beecac781b31a90db7a63eaf31`。

## 正式 PR 门禁

feature head `3a1e05e777bbdfe5a0dca9ae33b4c4a2987053c0`：

- CI run `32450508065`：`Stage 1`、`Stage 2 Platform`、`Stage 3A Database`、`Windows bootstrap` **全部 success**。
- `Stage 1-7 Audit Correctness` run `32450508017`：success。
- `Stage 6 XHS Vertical Slice` run `32450508027`：success。
- `Stage 7 Provider Config Routing` run `32450508023`：success。
- `Stage 7 Keyword Packs` run `32450508062`：success。
- `Stage 7 Plan Occurrence Run Snapshot` run `32450508042`：success。
- `Stage 7 Scheduler Runtime` run `32450508053`：success。

## 生成物与视觉验证

- 下载上述 `report-visual-sample` artifact，ZIP 中包含 `report.docx` 172851 bytes、`report.md` 11728 bytes 和两张词云 PNG。
- 使用 `/home/oai/skills/docx/render_docx.py report.docx --output_dir ... --emit_pdf` 由 LibreOffice 实际重新打开并渲染：**25 页 PNG + PDF 全部生成成功**。
- 逐页检查未发现空白页、中文乱码、文字/表格/图表裁切、明显遮挡、词云图片丢失或比例失真；重复表头、横向 bar、数值标签、情感语义色和两张词云均实际可见。
- 稀疏样例的词云页存在较多留白，来源于样例词条数量少，不是渲染失败。
- 当前环境没有 Microsoft Word、WPS 或飞书实机，因此未声称这些客户端的像素级一致性；LibreOffice + OOXML/ZIP/Relationship/XLSX/PNG 结构校验是本轮替代验证。

# 文档影响

- `backend/src/aima_ugc/platform/reporting/README.md`：已更新 A4 横向、Editorial Table、Ranking、Chart、词云资产、CJK 字体要求和验证事实。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：已更新离线 Report Renderer 的 Word 展示规则、图片边界和字体运行时要求。
- `imports_test` 调用方式与产物主入口没有变化，因此未做无关修改。
- 当前仓库实际没有 Dockerfile/Compose；生产镜像字体安装留到真实 Release/Docker 实现存在时处理，不提前造文件。

# 交付

- 实现 Commit：`8b7b7a042a91f53a0c60c0d91faf57bce7d17d4b`（`实现横向A4舆情报告视觉重构`）。
- CI/清理 Commit：`3a1e05e777bbdfe5a0dca9ae33b4c4a2987053c0`（`完善报告视觉CI环境并清理临时流程`）。
- PR：#106 `横向 A4 Word 舆情报告视觉重构`，当前等待从 Draft 转为 Review 后按门禁合并。
- Merge / main 合并后验证 / Change 归档：待执行。
- 发布/部署：未执行；本 Change 不包含生产发布。
