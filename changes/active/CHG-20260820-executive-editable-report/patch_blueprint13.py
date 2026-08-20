from pathlib import Path

path = Path("docs/blueprint/13-统一数据Excel导出与调试复用.md")
text = path.read_text(encoding="utf-8")

old_stats = """### 13.3 统计口径

完整统计遵循现有 Workbook 语义：

```text
内容总量、平台、情感、关键词、按日趋势
→ 内容 Sheet

一级/二级总体频次、一级→二级标签对
→ 标签明细 Sheet

评论总量、平台评论量
→ 评论 Sheet
```

一级/二级标签的每日趋势需要时间维度，因此从“内容”Sheet 的 `发布时间` 与对应换行标签列统计；一级/二级总体频次仍以“标签明细”Sheet 为准。

报告必须保留完整平台、标签、标签对、关键词和每日非零数据表格。图表允许为了阅读性只显示 Top N 序列，但不得因为图表裁剪丢失完整表格数据，也不得修改上游数据。
"""
new_stats = """### 13.3 统计口径与默认管理层视图

完整统计继续遵循现有 Workbook 语义：

```text
内容总量、平台、情感、关键词、按日趋势
→ 内容 Sheet

一级/二级总体频次、一级→二级标签对
→ 标签明细 Sheet

评论总量、平台评论量
→ 评论 Sheet
```

一级/二级标签的每日趋势需要时间维度，因此从“内容”Sheet 的 `发布时间` 与对应换行标签列统计；一级/二级总体频次仍以“标签明细”Sheet 为准。

默认共享报告面向营销管理层直接阅读和汇报，不再把实现过程、模板、Workbook/Sheet、Markdown/Word 转换等技术说明放进最终正文。默认正文先展示确定性管理摘要和风险关注，再展开完整统计：

```text
管理摘要
→ 内容/评论声量、覆盖平台、负面占比、声量峰值、主要平台、首要议题、热点关键词

风险关注
→ 负面平台分布、负面一级议题、负面二级议题

平台与情感
→ 平台声量、平台 × 情感交叉结构、平台每日趋势

整体情感
→ 情感结构、情感每日趋势

核心议题与关键词
→ 一级/二级/标签对、关键词及对应趋势

完整统计与数据质量
→ 全量明细、缺失/异常计数和业务口径说明
```

这些摘要全部由既有结构化字段确定性计算，不新增 LLM 请求，不生成脱离数据的主观结论。报告必须保留完整平台、标签、标签对、关键词和每日非零数据表格；图表允许为了阅读性只显示 Top N 序列，但不得因为图表裁剪丢失完整表格数据，也不得修改上游数据。
"""

old_word = """### 13.5 Mermaid 与 Word

Markdown 图表使用 Mermaid fenced block。当前模板只使用：

```text
pie
xychart
```

Word 转换器只承诺支持本报告实际使用的 Mermaid 子集，并将其转换为 DOCX 内嵌 PNG；Markdown 仍保留 Mermaid 源码。对于未支持的 Mermaid 类型必须 fail closed，不能静默忽略导致 Markdown 与 Word 内容不一致。

当前实现不引入 Pandoc、LibreOffice、Matplotlib、pandas 或在线 Mermaid 服务作为运行时依赖；DOCX/PNG 由已有 Python 运行时和标准库生成。LibreOffice 只可作为开发/交付验证工具，不是生产报告生成依赖。
"""
new_word = """### 13.5 Mermaid 与可编辑 Word 图表

Markdown 图表使用 Mermaid fenced block。当前模板只使用：

```text
pie
xychart
```

Markdown 仍保留 Mermaid 源码，并以受控注释保存 xychart 的系列名称，使“同一份 Markdown → Word”时不会丢失平台/情感等业务图例。Word 转换器只承诺支持本报告实际使用的 pie/bar/line 子集；对于未支持的 Mermaid 类型必须 fail closed，不能静默忽略导致 Markdown 与 Word 内容不一致。

Word 当前不再把图表写成静态 PNG，而是生成 Office 原生 Chart，并为每张图嵌入对应的 XLSX 数据包：

```text
word/charts/chartN.xml
word/charts/_rels/chartN.xml.rels
word/embeddings/chartN.xlsx
```

因此支持 Office Chart 编辑的 Word 可以直接“编辑数据”，人工校验或调整分类、系列、数值、标题、图例和样式；报告仍以 Office 原生图表引擎保证正常展示。图表的业务数据必须与 Markdown 中同一份统计数据一致，禁止为了 Word 再计算第二套统计。

当前实现不引入 Pandoc、LibreOffice、Matplotlib、pandas 或在线 Mermaid 服务作为运行时依赖；内嵌图表数据复用仓库已经锁定的 openpyxl，OOXML 包由现有 Python 运行时生成。LibreOffice/Office 只可作为开发或交付视觉验证工具，不是生产报告生成依赖。不同办公软件版本允许存在主题颜色、字体和分页的轻微渲染差异，但不能影响图表数据、可编辑性或正文信息完整性。
"""

old_failure = """- DOCX 生成后重新打开 ZIP/XML 校验最低包结构和媒体数量；
"""
new_failure = """- DOCX 生成后重新打开 ZIP/XML，校验最低包结构、Office Chart、Relationship 数量，并验证每张图内嵌 XLSX 数据包可打开；
"""

for old, new in ((old_stats, new_stats), (old_word, new_word), (old_failure, new_failure)):
    if old not in text:
        raise SystemExit("Blueprint 13 目标段落与预期不一致，停止修改")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8", newline="\n")
