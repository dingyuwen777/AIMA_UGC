---
schema: rvc-change/v1
id: CHG-20260821-report-visual-fidelity
title: Word 报告视觉还原与信息密度优化
level: L2
status: in_progress
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
- [ ] 目标测试、相关回归、Ruff、Mypy 和 DOCX 结构校验取得最终 head 的新鲜证据，并完成最终页面级视觉检查。

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

- 用户明确要求以最新生成 DOCX 的真实效果为依据继续修改，而不是只满足 OOXML 结构测试。
- 目标视觉是 A4 横向专业研究/咨询报告，尽可能复现此前确认的“标题/说明 + KPI + 左侧 Top Ranking + 右侧词云”的视觉关系，避免默认 Excel 和 AI Dashboard 味。
- 不加入图标、奖牌、星标或逐行小饼图/圆环；这类装饰与信息语义无关，且会增强模板感。
- 对过长列表采用“Top 视觉 + 紧凑完整明细”两层表达；完整数据不裁剪。
- 对多系列趋势采用同一统计数据的分层 Office Chart，不使用第二 Y 轴、不图片化。
- 词云优先保留 Pillow 自定义 Editorial 布局。已核对 `wordcloud` 三方库可从 frequency dict 生成并支持水平偏好、固定随机种子和自定义颜色，但标准随机碰撞布局更适合密集传统词云；本报告更需要对 4—9 个少词场景的中心聚簇、层级和留白进行可控编辑式布局，因此本轮不新增依赖。
- 词云最多展示 36 个词，使用 sqrt 权重并进一步温和压缩字号差异；全部水平，第一名可使用系统 CJK 粗体，颜色以海军蓝/主蓝/青绿/柔紫/蓝灰为主，仅少量低饱和赭色点缀。每个词从视觉中心寻找最近空位，完成后按真实字形边界裁切并受限放大回固定画布，使少词不显空、多词不挤成一团。

# 任务

- [x] 重新读取规则、Blueprint、归档 Change、当前 reporting 实现和相关测试。
- [x] 实际渲染并检查用户最新 DOCX，确认长 Ranking、分页、留白和多系列标签重叠是主要视觉缺陷。
- [x] 先增加能表达目标视觉结构和紧凑数据展示的失败测试并确认 Red。
- [x] 实现更高保真的横向组合布局、紧凑 Ranking/完整明细、趋势分层和自适应词云布局。
- [x] 更新默认模板与 reporting README；Blueprint 13 同步正在最终收敛。
- [ ] 完成最终 head 的需求符合性、代码质量、目标/回归/静态/结构/视觉验证。
- [x] 创建 Draft PR #111；合并仍等待用户另行授权。

# 验证

## Red 证据

在 `fix/report-visual-fidelity` 初始 Red 实现树上，CI run `32455320249` 的 Stage 2 Platform 实际结果为 **4 failed, 74 passed**。四个失败分别证明目标能力尚不存在：

- `layout=primary-overview` / `layout=ranking-chart` 被 Markdown 转换器拒绝；
- `table-style=compact-daily` 未支持；
- `chart-presentation=dominant-split` 未支持。

失败原因与本 Change 目标一一对应，不是环境噪音。

## 当前实现与中间验证

- 新增 `ReportDocxBuilder`，以 Word 原生 OOXML 组合 KPI、Ranking、Office Chart、词云图片和紧凑明细。
- 默认模板把 5.1 组织为同一区域的 KPI + 左 Ranking + 右词云；长 Ranking 只给 Top 项使用进度条，剩余项目双列紧凑展示。
- 平台/一级/二级多系列趋势新增 `dominant-split`；情感趋势继续使用 `sentiment-split`。各组仍是 Office Chart + 内嵌 XLSX。
- 每日完整长表在 Markdown 中不变，Word 使用 `compact-daily` 透视为横向矩阵。
- 词云修复原实现“后续词随排名被强制推向外圈”的根因，加入真实 glyph bbox 碰撞、中心聚簇、自适应聚焦和克制多色层级。
- CI run `32458174357` 的 Stage 2 Platform 已 **success**，Stage 1 当时只剩词云 `textbbox` 静态类型不一致；该类型问题已按真实返回值修正，等待最终 head CI 重新确认。
- PR 视觉预览 run `32458174299` 已使用 Ubuntu 24.04 + Noto CJK + LibreOffice 实际生成并重新打开 `report.docx`，转换为 PDF 与 30 页 PNG 后成功上传 artifact `report-visual-preview`（ID `9437982007`）。代表性 5.1 页面实际呈现为 3 个 KPI、左侧 9 项 Ranking、右侧紧凑词云；长二级议题页面实际呈现 Top 8 + 横向条形图 + 双列完整剩余明细。该预览把同量级旧版长报告的约 60+ 页压缩到 30 页，同时未删除 Markdown 完整数据。

最终完成前仍需在最新生产代码 head 上重新取得 CI 与视觉 artifact；上面的预览只作为中间证据，不替代最终验证。

# 验证计划

目标测试至少覆盖：

- Word 原生左右组合布局同时包含 Ranking 与 PNG/Office Chart；
- 一级议题组合页具有 KPI 数据且保持文字/数字可编辑；
- 超长 Ranking 的 Top 展示和剩余紧凑完整明细不丢条目；
- 新的趋势 presentation 仍生成 Office Chart + XLSX，并减少单图系列数量；
- Word 日明细横向压缩/透视后仍与 Markdown 原始完整数据等价；
- 词云确定性、稀疏/稠密视觉密度、中文字体 fail-closed、PNG 打包继续成立；
- 既有 A4 Landscape、图表编辑、日期筛选、imports_test 等回归不变。

完成时记录本轮实际命令、退出码、失败数、CI 和视觉渲染证据。

# 文档影响

- `backend/src/aima_ugc/platform/reporting/README.md`：已同步组合布局、Top + 完整明细、分层趋势、紧凑每日矩阵和自适应 Editorial Word Cloud 的长期行为。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：正在同步同一长期边界；不记录修改流水账。

# Git / PR / 发布

- 分支：`fix/report-visual-fidelity`
- PR：#111 `改进横向 Word 报告视觉还原度`，Draft / Open / 未合并。
- Merge：未授权，当前不执行。
- 发布/部署：不属于本 Change。
