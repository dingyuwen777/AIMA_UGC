# AIMA_UGC 舆情数据分析报告

> 本报告由处理完成的统一数据 Excel 自动生成。Markdown 是报告正文的唯一维护模板；Word 文档由本 Markdown 结果转换得到，不维护第二套正文。
>
> 图表用于快速识别分布和趋势；涉及 Top N 的图只做视觉裁剪，完整统计仍保留在对应表格中。

**生成时间：** {{GENERATED_AT}}  
**数据源：** `{{SOURCE_FILE}}`

---

## 1. 数据总览

### 1.1 核心规模

{{OVERVIEW_TABLE}}

### 1.2 数据完整性

下表只检查报告依赖字段是否缺失、时间是否可解析，以及内容中的一级/二级标签行数是否一致；它不替代上游 Canonical、Analysis 或 Excel Exporter 的正式校验。

{{DATA_QUALITY_TABLE}}

## 2. 平台分布与每日变化

### 2.1 各平台数据量

`内容量` 以“内容”Sheet 一帖一行为口径；`评论量` 以“评论”Sheet 一评论一行为口径。

{{PLATFORM_TABLE}}

### 2.2 各平台内容占比

{{PLATFORM_PIE_CHART}}

### 2.3 各平台每日内容量

{{PLATFORM_DAILY_LEGEND}}

{{PLATFORM_DAILY_CHART}}

### 2.4 各平台每日完整明细

{{PLATFORM_DAILY_TABLE}}

## 3. 情感分布与每日变化

### 3.1 情感标签分布

{{SENTIMENT_TABLE}}

{{SENTIMENT_PIE_CHART}}

### 3.2 情感标签每日趋势

{{SENTIMENT_DAILY_LEGEND}}

{{SENTIMENT_DAILY_CHART}}

### 3.3 情感标签每日完整明细

{{SENTIMENT_DAILY_TABLE}}

## 4. 一级标签分析

一级标签总量以“标签明细”Sheet 的标签对行数为统计口径；同一内容命中多个合法标签对时会贡献多条标签记录。

### 4.1 一级标签完整分布

{{PRIMARY_TABLE}}

### 4.2 一级标签 Top 分布

{{PRIMARY_BAR_CHART}}

### 4.3 一级标签每日趋势

为控制折线数量，图中只展示总体数量最高的一级标签；下方每日明细保留全部一级标签非零记录。

{{PRIMARY_DAILY_LEGEND}}

{{PRIMARY_DAILY_CHART}}

### 4.4 一级标签每日完整明细

{{PRIMARY_DAILY_TABLE}}

## 5. 二级标签分析

二级标签总量同样以“标签明细”Sheet 的标签对行数为统计口径。

### 5.1 二级标签完整分布

{{SECONDARY_TABLE}}

### 5.2 二级标签 Top 分布

{{SECONDARY_BAR_CHART}}

### 5.3 二级标签每日趋势

为控制折线数量，图中只展示总体数量最高的二级标签；下方每日明细保留全部二级标签非零记录。

{{SECONDARY_DAILY_LEGEND}}

{{SECONDARY_DAILY_CHART}}

### 5.4 二级标签每日完整明细

{{SECONDARY_DAILY_TABLE}}

## 6. 一级 → 二级标签结构

该表保留每个实际出现的一级/二级标签对及数量，可用于定位具体舆情主题结构；父子关系仍以 Analysis Prompt Taxonomy 为事实源，本报告不重新定义标签体系。

{{LABEL_PAIR_TABLE}}

## 7. 命中关键词

关键词数量表示有多少条内容命中该关键词；同一条内容中的同一关键词只计一次，因此多个关键词占比相加可以超过 100%。

{{KEYWORD_TABLE}}

{{KEYWORD_BAR_CHART}}

---

## 8. 统计口径说明

- **内容总量：** “内容”Sheet 的实际内容行数，一帖一行。
- **评论总量：** “评论”Sheet 的实际评论行数。
- **标签对总量：** “标签明细”Sheet 的实际标签对行数；一条内容可以对应多个标签对。
- **一级/二级标签总体分布：** 从“标签明细”Sheet 统计，确保多标签内容按标签对完整计数。
- **一级/二级标签每日趋势：** 从“内容”Sheet 的“发布时间”与换行标签列统计；该列由同一 Analysis 标签对按顺序投影，因此不会反向修改上游数据。
- **每日趋势日期：** 取“发布时间”的自然日；无法解析的时间不进入趋势图，并在“数据完整性”中单独计数。
- **Word 图表：** Word 转换器把本模板使用的 Mermaid `pie` 与 `xychart` 图转换为文档内嵌图片；Markdown 中仍保留原 Mermaid 源码。
