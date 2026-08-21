# Word 舆情报告

这篇文档解释：**统一 Excel 怎么变成 `report.md + report.docx`，为什么 Markdown 是正文结构事实源，Word 里又为什么还能保留可编辑图表。**

## 1. 当前报告链路

离线报告入口消费统一数据 Excel：

```text
UnifiedDataExcelV1
→ 读取并计算统计
→ 报告上下文
→ Markdown 模板
→ report.md
→ Word Renderer
→ report.docx
```

它不会：

- 调 PostgreSQL；
- 调 HTTP API；
- 创建 Job；
- 再调用 LLM 生成结论。

所以它适合作为稳定的离线报告能力，也能被 `imports_test` 直接复用。

## 2. 为什么 Markdown 是正文结构事实源

如果 Word 的标题、段落和章节全部写死在 Python 中，后续想改报告结构就必须改代码。

当前做法：

```text
Markdown 模板
→ 决定正文有哪些章节、标题、说明和占位内容

Python Renderer
→ 负责把这些内容变成 Word，并插入表格、Office Chart、词云等复杂对象
```

这样可以做到：

- 文字和章节结构主要维护 Markdown；
- Word 视觉实现集中在 Renderer；
- 统计数字仍来自同一份程序计算，不在模板里手填。

## 3. report.md 和 report.docx 的关系

`report.md` 是完整的人类可读数据报告；`report.docx` 是正式汇报版视觉投影。

两者允许展示方式不同，但统计事实必须一致。

例如：

```text
二级议题有 39 项

report.md
→ 可以保留完整长表

report.docx
→ 正文重点展示 Top 8
→ 剩余 31 项用紧凑可编辑明细继续保留
```

“Top N”只改变视觉重点，不能把完整统计数据删除。

## 4. 当前 Word 设计目标

当前报告面向：

- A4 横向；
- 领导/管理层阅读；
- 飞书上传预览；
- 正式汇报；
- Word 后续仍可编辑。

设计原则：

```text
信息密度适中
重点明确
少装饰
不使用默认 Excel 图表感
不过度 Dashboard 化
不为了“AI 味”堆图标和花哨卡片
```

## 5. 为什么 Office Chart 不直接画成 PNG

柱状图、折线图、饼图等使用 Word/Office 原生 Chart，并内嵌 XLSX 数据。

好处：

- 打开 Word 后仍能编辑数据/图表；
- 字体和主题能跟随 Office；
- 不需要为每个图表再维护一张图片；
- 报告数据可验证。

词云是例外：Word 没有合适的原生词云对象，所以使用 PNG。

## 6. 当前主要版式

### 一级议题

一页尽量组织成：

```text
标题/说明
3 个 KPI
左侧：9 项紧凑 Ranking
右侧：词云
```

不使用逐行小饼图、奖牌、星标等无业务含义装饰。

### 长 Ranking

```text
Top N 重点视觉
+ 完整剩余明细
```

避免几十条进度条连续占很多页。

### 多系列趋势

当平台/一级/二级系列太多时，不把所有数据标签挤在同一张图。

当前仍使用同一统计数据的可编辑 Office Chart，但按主序列/低量级序列分层展示；不靠第二 Y 轴制造难读的视觉比例。

### 每日明细

Markdown 保留完整长表；Word 利用 A4 横向宽度投影为更紧凑的矩阵，减少重复日期造成的页数浪费。

## 7. 词云为什么没有直接使用随机 wordcloud 默认布局

当前报告的词云场景常常只有 4～9 个一级议题，也可能有几十个热点词。

传统随机碰撞词云在“词很少”时容易显得空、散、廉价。当前实现使用 Pillow 做确定性的 Editorial 布局：

- 最多 36 个词；
- sqrt 权重压缩字号差异；
- 全水平；
- 从视觉中心寻找最近可用位置；
- 真实字形边界碰撞；
- 少词场景自动聚焦/放大；
- 克制的蓝/青绿/柔紫/蓝灰等色彩；
- 固定结果，不因每次运行随机变化。

这里的目标是“可读、稳定、不过度抢视觉”，不是追求炫技。

## 8. 统计事实从哪里来

Word Renderer 不能自己重新算一套数据。

当前报告使用统一统计上下文/内部统计对象作为数字事实源：

```text
输入 Excel
→ 一次统计
→ Markdown / Ranking / Chart / KPI / Word Cloud 都消费同一结果
```

这样避免：

```text
表格说 120
图表说 118
KPI 又说 121
```

## 9. 报告不应该修改输入 Excel

生成前后输入 Workbook 必须保持只读语义。

正确：

```text
读取 input.xlsx
→ 生成 report.md / report.docx / 图片等新产物
```

错误：

```text
为了做图
→ 在用户输入 workbook 新增隐藏 sheet / 改数据
```

Office Chart 自己需要的内嵌 XLSX 放在 DOCX 包内部，不修改原始输入文件。

## 10. 一个最小使用流程

假设离线处理已经得到统一数据文件：

```text
output/labeled.xlsx
```

报告函数接收该路径后：

```text
1. 读取统一数据
2. 校验报告日期范围
3. 计算平台/情感/一级/二级/关键词/每日趋势
4. 渲染 report.md
5. 渲染 Office Chart / Word Cloud
6. 生成 report.docx
7. 返回输出路径
```

实际函数名、参数和输出目录以 `backend/src/aima_ugc/platform/reporting/README.md` 和当前代码为准。

## 11. 日期范围为什么必须 fail closed

如果用户指定 8 月 1 日到 8 月 7 日，而输入文件实际包含 8 月 8 日数据，报告不能悄悄把它也算进去。

当前报告对日期范围使用北京时间闭区间并做一致性检查。无法可靠判断的数据不能通过猜测静默混入。

## 12. 飞书/不同 Office 渲染为什么可能略有差异

DOCX 是 OOXML 文档，不是固定像素画布。不同 Word/LibreOffice/飞书预览器可能在：

- 字体替代；
- 行高；
- 图表主题；
- 分页；
- 文本度量；

上有轻微差异。

所以报告验证不能只检查“DOCX ZIP 能打开”，还需要代表性数据做实际页面级预览。

当前仓库已经使用 DOCX 结构检查 + LibreOffice/PDF/PNG 视觉预览作为自动化/半自动验证手段；Microsoft Word 不在 CI 中时，不宣称像素级完全一致。

## 13. 正式数据库 Export 和 Word 报告不要混成一个 Job

当前两种能力职责不同：

```text
Reporting Domain Export Job
→ 从 PostgreSQL 冻结内容集合
→ 生成 UnifiedDataExcelV1 Artifact

platform/reporting 离线报告
→ 从 UnifiedDataExcelV1 生成 report.md / report.docx
```

未来若产品需要“数据库一键生成正式报告”，可以在既有边界上编排 Job，但不需要把离线 Renderer 改成直接查数据库。

## 14. 主要代码位置

| 能力 | 位置 |
| --- | --- |
| 离线报告说明 | `backend/src/aima_ugc/platform/reporting/README.md` |
| 报告实现 | `backend/src/aima_ugc/platform/reporting/` |
| 正式 Excel Export Domain | `backend/src/aima_ugc/modules/reporting/` |
| Excel 离线入口 | `backend/src/aima_ugc/adapters/providers/imports_test/` |
| 统一 Excel 说明 | [`Excel导入导出与离线处理.md`](Excel导入导出与离线处理.md) |

## 15. 常见误区

- 把 Word 文案和章节全部写死在 Python；
- 为了好看把完整数据裁成 Top N；
- 把所有图表截图成图片，失去编辑能力；
- 让 Word Renderer 再算一套统计；
- 修改输入 Excel 来给 Chart 准备数据；
- 为少量词使用不可控随机词云；
- 只跑 OOXML 结构测试就宣称视觉已经正确；
- 把报告 Renderer 直接耦合 PostgreSQL、HTTP 或 LLM。
