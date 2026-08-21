---
schema: rvc-change/v1
id: CHG-20260821-report-visual-fidelity
title: Word 报告视觉还原与信息密度优化
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/report-visual-fidelity
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas:
  - reporting
affected_paths:
  - backend/src/aima_ugc/platform/reporting
  - tests/unit/platform
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
contracts: []
data_changes: []
---

# 目标

在既有 A4 横向、Office 原生可编辑 Chart、Word 原生表格/Ranking 和 PNG 词云能力上，针对真实生成报告的视觉问题做第二轮收敛：让管理层正文更接近已确认的编辑式预览效果，显著减少超长 Ranking、巨大留白、多系列数据标签重叠和“自动报表”感，同时保持完整统计数据、Markdown 正文唯一模板和既有报告入口不变。

# 可观察成功标准

- [x] 一级议题页把 KPI、Top Ranking 与词云组织成紧凑的横向视觉组合，Ranking 与词云不再被分页拆开。
- [x] 正负面 Top、二级议题和热点关键词的正文只用 Top N 做重点视觉，剩余完整数据仍以紧凑可编辑明细保留，不丢统计。
- [x] 超长 Ranking 不再让 38/39/55 个条目各占一条宽进度条并跨多页。
- [x] 平台/一级/二级多系列每日趋势不再把所有数据标签挤在同一坐标区；主序列与低量级序列采用可编辑 Office Chart 分层展示。
- [x] 词云仍由同一统计 Counter 自动生成，但一级议题词云采用更接近编辑设计的稳定布局和克制多色强调。
- [x] 普通日明细在 Word 中提高横向 A4 的信息密度，减少重复日期造成的无意义长页，同时 report.md 的完整数据保持不变。
- [x] 输入 Excel、统计口径、日期筛选、imports_test 接线、Office Chart 内嵌 XLSX 和词云自动重生成语义不变。
- [x] 目标测试、相关回归、Ruff、Mypy、DOCX 结构校验和实际页面级视觉检查均取得本轮新鲜证据。

# 范围

- `platform/reporting` 的 Word 展示编排、Ranking、Chart presentation、词云布局、横向明细表视觉投影。
- 默认 `report_template.md` 的最小展示元数据调整。
- reporting 相关测试和长期文档同步。

# 非目标

- 不修改 UnifiedDataExcelV1、Canonical、Analysis Contract/taxonomy、数据库、Migration、API、前端或正式 Report Job。
- 不新增 LLM 结论，不把 Office Chart 改成图片，不把整份 Word 做成页面截图。
- 不删除完整统计数据；Top N 只改变管理正文的视觉重点，完整明细必须继续可访问。
- 当前改进可用现有 Pillow/OOXML 完成，不新增第三方依赖。

# 必须保持不变

- `generate_excel_report()`、`imports_test.generate_report()`、`run_all()` 的公共调用语义。
- `report_date_range` 的北京时间闭区间筛选和 fail-closed 一致性检查。
- `_ReportStats` 作为报告数字唯一统计事实源。
- Markdown 模板继续是正文结构唯一长期维护入口。
- Office bar/line/pie 继续是原生可编辑 Chart + 内嵌 XLSX；词云允许是 PNG。
- 输入 Workbook 只读且生成前后 Hash 不变。

# 已确认关键决策

- 用户明确要求以真实生成 DOCX 的效果为依据继续修改，而不是只满足 OOXML 结构测试。
- 目标视觉是 A4 横向专业研究/咨询报告，尽可能保持“标题/说明 + KPI + 左侧 Top Ranking + 右侧词云”的视觉关系，避免默认 Excel 和 AI Dashboard 味。
- 不加入图标、奖牌、星标或逐行小饼图/圆环；这类装饰与信息语义无关，且会增强模板感。
- 对过长列表采用“Top 视觉 + 紧凑完整明细”两层表达；完整数据不裁剪。
- 一级议题固定为 3 个 KPI + 9 项紧凑 Ranking + 右侧词云；为保证整页紧凑，一级议题 Ranking 不再逐项显示进度条，精确数量与占比仍保留。
- 对正负面等 Ranking + Chart 组合，图表高度根据 Top 条目数自适应；只有 1—2 项数据时不再使用接近半页高的图表。
- 对多系列趋势采用同一统计数据的分层 Office Chart，不使用第二 Y 轴、不图片化。
- 词云优先保留 Pillow 自定义 Editorial 布局。已核对 `wordcloud` 三方库可从 frequency dict 生成并支持水平偏好、固定随机种子和自定义颜色，但标准随机碰撞布局更适合密集传统词云；本报告更需要对 4—9 个少词场景的中心聚簇、层级和留白进行可控编辑式布局，因此本轮不新增依赖。
- 词云最多展示 36 个词，使用 sqrt 权重并进一步温和压缩字号差异；全部水平，第一名可使用系统 CJK 粗体，颜色以海军蓝/主蓝/青绿/柔紫/蓝灰为主，仅少量低饱和赭色点缀。每个词从视觉中心寻找最近空位，完成后按真实字形边界裁切并受限放大回固定画布，使少词不显空、多词不挤成一团。

# 任务

- [x] 重新读取规则、Blueprint、归档 Change、当前 reporting 实现和相关测试。
- [x] 实际渲染并检查生成 DOCX，确认长 Ranking、分页、留白和多系列标签重叠是主要视觉缺陷。
- [x] 先增加能表达目标视觉结构和紧凑数据展示的失败测试并确认 Red。
- [x] 实现更高保真的横向组合布局、紧凑 Ranking/完整明细、趋势分层和自适应词云布局。
- [x] 更新默认模板、reporting README 和 Blueprint 13 的长期设计说明。
- [x] 完成需求符合性、代码质量、目标/回归/静态/结构/视觉验证。
- [x] 创建 PR #111；合并仍等待用户另行授权。

# 验证

## Red 证据

在 `fix/report-visual-fidelity` 初始 Red 实现树上，CI run `32455320249` 的 Stage 2 Platform 实际结果为 **4 failed, 74 passed**。四个失败分别证明目标能力尚不存在：

- `layout=primary-overview` / `layout=ranking-chart` 被 Markdown 转换器拒绝；
- `table-style=compact-daily` 未支持；
- `chart-presentation=dominant-split` 未支持。

失败原因与本 Change 目标一一对应，不是环境噪音。

## 最终生产代码验证

生产代码最终视觉实现提交为 `da4afd15ae470535ded8e44626dae5cc865c4669`；其后的提交仅更新 Change/PR 交付记录或删除临时验证工作流，不改变 reporting 生产行为。

该提交对应 CI run `32461816373` 已完成且全部 Job 成功：

```text
Stage 1              success
Stage 2 Platform     success
Stage 3A Database    success
Windows bootstrap    success
```

Stage 1 实际执行结果：

```text
uv run ruff format --check backend tests scripts
→ 428 files already formatted

uv run ruff check backend tests scripts
→ All checks passed!

uv run mypy backend/src
→ Success: no issues found in 230 source files

uv run pytest tests/unit -q
→ 534 passed, 1 warning in 7.68s

uv run pytest tests/contracts -q
→ 54 passed in 3.30s

uv run pytest tests/api -q
→ 27 passed, 1 warning in 1.95s

scripts/quality/check_architecture.py
→ 通过

scripts/quality/check_table_ownership.py
→ 通过

scripts/quality/scan_secrets.py
→ 通过

scripts/quality/check_docs.py
→ 通过

uv build --wheel + 独立 venv 安装/导入
→ 通过，版本 0.1.0

frontend lint / typecheck / build
→ 全部通过

frontend unit
→ 22 passed

Playwright E2E
→ 8 passed
```

Stage 2 Platform 实际执行结果：

```text
uv run pytest tests/unit/platform -q
→ 79 passed in 4.88s

uv run pytest tests/integration/platform -q
→ 1 passed in 0.53s

真实 readiness HTTP smoke
→ 通过
```

同一生产代码提交关联的仓库工作流均成功：CI、Stage 6 XHS Vertical Slice、Stage 7 Scheduler Runtime、Stage 1-7 Audit Correctness、Stage 7 Plan Occurrence Run Snapshot、Stage 7 Keyword Packs、Stage 7 Provider Config Routing。

## DOCX / 页面级视觉验证

PR 视觉预览 run `32461816343` 在同一生产代码提交上使用 Ubuntu 24.04 + Noto CJK + LibreOffice 实际执行：

```text
生成代表性统一数据 Excel
→ generate_excel_report()
→ report.md
→ report.docx
→ LibreOffice headless 重新打开并转换 PDF
→ Poppler 渲染全部页面 PNG
→ artifact 上传成功
```

Artifact：`report-visual-preview`，ID `9439204556`。

实际结构检查：

```text
DOCX ZIP testzip        None
DOCX ZIP entries        75
Office Chart parts      22
Embedded XLSX           22
Embedded PNG            2
PDF pages               29
PDF page size           A4 Landscape
Wordcloud PNG           1600 × 900，约 300 DPI
```

29 页预览已逐页检查：未发现空白页、图片丢失、明显裁切、横向溢出或大规模数据标签互相遮挡。关键页面结果：

- 一级议题在同一页展示 3 个 KPI、左侧 9 项紧凑 Ranking、右侧词云，不再被分页拆开；
- 一级议题词云以“品牌评价”为主视觉中心，其余词使用蓝/青绿/柔紫/蓝灰和少量赭色，未发现词条重叠；
- 热点关键词词云在词较多时保持密度和呼吸感，没有随机旋转和彩虹配色；
- 长二级议题使用 Top 8 + 横向条形图 + 双列完整剩余明细，完整数据未丢失；
- 低数据量负面分布的图表高度按条目数缩减，避免单条数据占用半页；
- 完整每日明细在 Word 中转换为横向紧凑矩阵，Markdown 的完整长表仍保留。

未使用 Microsoft Word 实机做最终渲染，因此不能宣称 Microsoft Word 像素级完全一致；LibreOffice 实际重开/渲染、DOCX OOXML/ZIP 校验和 Office Chart 内嵌 XLSX 校验共同作为当前替代验证。不同 Office 版本仍可能产生轻微字体、主题色和分页差异。

# 文档影响

- `backend/src/aima_ugc/platform/reporting/README.md`：已同步组合布局、Top + 完整明细、分层趋势、紧凑每日矩阵和自适应 Editorial Word Cloud 的长期行为。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：已同步同一长期边界；不记录修改流水账。
- 不涉及 Contract、Migration、API 或依赖版本变更。

# Git / PR / 发布

- 分支：`fix/report-visual-fidelity`
- PR：#111 `改进横向 Word 报告视觉还原度`，Open / 未合并。
- Merge：未授权，当前不执行。
- 发布/部署：不属于本 Change。
