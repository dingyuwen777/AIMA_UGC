# Excel 统一数据导出与离线调试

本文解释 AIMA_UGC 为什么只有一套 Provider-neutral Excel 数据明细格式，以及：

- 正式 PostgreSQL Export；
- `imports_test` 离线输出；
- TikHub 调试输出；

怎样复用同一个共享 Exporter，而不是各写一套 Workbook。

当前机器入口：

```text
统一 Excel Contract
→ backend/src/aima_ugc/contracts/export/models.py

共享 Exporter
→ backend/src/aima_ugc/platform/export/excel.py

正式 PostgreSQL Export
→ backend/src/aima_ugc/modules/reporting/
→ backend/src/aima_ugc/bootstrap/reporting_http.py
→ backend/src/aima_ugc/bootstrap/export_worker.py

离线 imports_test
→ backend/src/aima_ugc/adapters/providers/imports_test/
```

---

## 1. 为什么需要统一 Excel Contract

如果每个平台自己输出：

```text
xiaohongshu.xlsx
 douyin.xlsx
weibo.xlsx
```

并各自定义字段，后续：

- AI 列无法统一；
- 报告要写五套 Reader；
- 前端/人工审阅对字段理解不一致；
- 平台新增/切换 Provider 会影响整个下游。

所以当前先统一成：

```text
UnifiedDataExcelV1
```

精确定义：

```text
backend/src/aima_ugc/contracts/export/models.py
```

它由：

```text
UnifiedDataExcelContentV1
UnifiedDataExcelCommentV1
UnifiedDataExcelAnalysisV1
UnifiedDataExcelLabelPairV1
```

组成。

这些 Model `extra="forbid"`，调用方不能随便塞私有字段形成第二套 Workbook Schema。

---

## 2. 当前 Workbook 固定三张 Sheet

```text
内容
标签明细
评论
```

共享实现：

```text
backend/src/aima_ugc/platform/export/excel.py
```

### 2.1 内容 Sheet

当前完整默认列由 `_CONTENT_HEADERS` 定义：

```text
平台
内容ID
来源项ID
内容类型
标题
正文
作者
发布时间
内容链接
作者粉丝数
作者关注数
作者内容数
作者获赞数
点赞
评论数
收藏数
分享数
转发数
浏览数
播放数
弹幕数
投币数
下载数
命中关键词
发声类型
情感标签
一级标签
二级标签
分析模型
Prompt版本
Taxonomy版本
来源Provider
Raw/来源定位
评论覆盖
```

精确顺序直接看 `_CONTENT_HEADERS`，文档只用于人类快速理解。

### 2.2 标签明细 Sheet

默认：

```text
内容ID
平台
标题
情感标签
一级标签
二级标签
内容链接
```

一条 Content 可以有多个合法标签对：

```text
内容 Sheet
→ 一条 Content 一行
→ 一级/二级标签单元格按同一标签对顺序换行

标签明细 Sheet
→ 一个标签对一行
```

这样既适合人工快速看内容，又适合 Excel 透视/筛选标签关系。

### 2.3 评论 Sheet

默认：

```text
平台
内容ID
评论层级
评论ID
根评论ID
父评论ID
作者
评论内容
评论时间
评论点赞
回复数
来源Provider
Raw/来源定位
```

评论和内容通过稳定：

```text
platform
external_content_id
```

关联，不依赖 Excel 行号。

---

## 3. `UnifiedDataExcelV1` 和 Workbook 展示列不是一回事

Contract 保存统一业务投影；Excel 列配置只是**展示投影**。

共享入口：

```python
export_unified_data_excel(
    records,
    output_path,
    include_analysis=...,
    content_columns=...,
    label_detail_columns=...,
    comment_columns=...,
)
```

三个列参数：

```text
None
→ 使用该 Sheet 默认完整列

传入有序列名序列
→ 只输出这些已知列
→ 顺序按传入值
```

当前 `_resolve_columns()` 会拒绝：

- 单个字符串冒充序列；
- 空列配置；
- 重复列；
- 未知列。

所以调用方可以：

```text
选列
调顺序
```

但不能：

```text
自己新增“平台私有列”
自己改列语义
自己再维护一份表头字典
```

---

## 4. Canonical 怎样投影到 Excel

内容：

```python
project_canonical_content(...)
```

评论：

```python
project_canonical_comment(...)
```

位置：

```text
platform/export/excel.py
```

例如：

```text
CanonicalContentV1.metrics.like_count
→ Excel “点赞”

CanonicalContentV1.author.display_name
→ Excel “作者”

CanonicalCommentV1.root_comment_id
→ Excel “根评论ID”
```

Exporter 不修改 Canonical，也不从 Excel 反推业务事实。

---

## 5. Analysis 怎样进入 Excel

Excel 展示使用：

```text
UnifiedDataExcelAnalysisV1
```

当前包括：

```text
relevance
voice_type
sentiment
primary_label
secondary_label
label_pairs
model
prompt_version
taxonomy_version
```

但 Workbook 当前**不展示“相关性”列**。

原因：

- 正式查询型导出默认排除当前 Analysis 明确 irrelevant 的内容；
- 离线最终业务 JSONL 也可根据离线处理语义排除 irrelevant；
- 重复展示一个几乎恒为 relevant 的列价值低。

`voice_type` Excel 中文投影可通过 `_VOICE_TYPE_DISPLAY_NAMES` 为既有机器值提供展示别名，但这张映射不是合法 Taxonomy 白名单。合法值只由当前 Prompt 的机器 Taxonomy 决定；已有值继续保持既有中文展示，Prompt 新增而尚未配置展示别名的机器值会在 Excel 中原样输出，不会因为导出层未认识该值而失败。数据库/Contract 继续保存稳定机器值。

AI 完整业务语义见：

[`07_AI舆情打标与分析实现.md`](07_AI舆情打标与分析实现.md)

---

## 6. raw / labeled 为什么共用一个 Exporter

离线调试时可能需要：

```text
raw_data.xlsx
labeled_data.xlsx
```

不能因此写两套 Workbook。

当前做法：

```text
include_analysis = false
→ Analysis 列留空

include_analysis = true
→ 从 record.analysis 填入 Analysis
```

Sheet、列定义、ID 文本格式、样式、安全规则全部共用。

这样 AI 改列或 Workbook 改样式时只改一处。

---

## 7. `UnifiedContentRecordV1` JSONL 怎样直接导出 Excel

当前入口：

```python
export_unified_content_jsonl_to_excel(...)
```

它逐行读取：

```text
UnifiedContentRecordV1 JSONL
```

并转换成 `UnifiedDataExcelV1`。

空行直接失败：

```text
第 N 行为空，拒绝导出
```

非法 JSON/Contract 直接失败：

```text
第 N 行不是合法 UnifiedContentRecordV1
```

不会“跳过坏行继续生成看似成功的 Excel”。

---

## 8. 离线 JSONL 的业务链

`imports_test` 当前典型链：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ 可选 AI 回写/过滤
→ shared Excel Exporter
```

AI checkpoint 可以存在：

```text
analysis/checkpoints.jsonl
```

用于恢复和调用审计，但它不是下游业务数据源。

最终 Excel 直接从统一 JSONL 读取，不需要 join 第二份 Excel/CSV 标签文件。

---

## 9. 正式 PostgreSQL Export 怎样复用同一个 Excel

正式 API：

```text
POST /api/v1/data-exports
```

主链：

```text
冻结 content_id + content_version
→ reporting_data_export_items
→ reporting.content-export-excel.v1 Job
→ PostgresDataExportRepository.load_records()
→ UnifiedDataExcelV1
→ export_unified_data_excel()
→ Artifact
```

所以：

```text
正式数据库导出
imports_test 离线导出
```

最终都进入：

```text
platform/export/excel.py
```

这就是“一套 Excel 实现”的实际代码边界。

正式 Reporting 说明：

```text
backend/src/aima_ugc/modules/reporting/README.md
```

---

## 10. 正式 Export 为什么能拿到指定 Content Version

数据库 Export 创建时冻结：

```text
content_id
content_version
ordinal
```

Worker 读取 `content_versions` 的指定版本正文，而不是执行时的最新正文。

同时互动指标当前来自 Content Current；Analysis 只读取指定版本且匹配当前 Analysis Identity 的最新结果。

所以一个正式 Export Record 实际可能组合：

```text
冻结版本的标题/正文/作者快照
+ 当前互动指标
+ 冻结版本的当前合法 Analysis
+ 评论
+ 评论 Coverage
+ 来源 Provider/Raw
```

精确投影：

```text
backend/src/aima_ugc/adapters/persistence/postgres/reporting.py
```

---

## 11. 当前 Excel 样式

样式也由共享 Exporter 统一维护。

当前主要规则：

```text
冻结首行 = A2
显示网格线 = true
自动筛选 = 首行到实际数据区
表头填充 = #FFC000
表头字体 = Calibri 11 bold
正文字体 = Calibri 11
表头行高 = 16.5
正文默认行高 = 14.5
```

列宽由：

```text
_CONTENT_COLUMN_WIDTHS
_LABEL_COLUMN_WIDTHS
_COMMENT_COLUMN_WIDTHS
```

维护。

二级标签支持按中文/宽字符显示宽度估算换行行数，并自适应行高，最大不会无限增长。

如果只是调整 Workbook 视觉，优先改这些共享常量/函数，而不是在 `imports_test` 或 `export_worker.py` 复制格式代码。

---

## 12. 大文件为什么用 write-only Workbook

当前：

```python
Workbook(write_only=True)
```

原因：大量 Content/Comment 导出时，普通 Workbook 会把全部 Cell 对象长期留在内存。

正式 Export Worker 本身也分页从 PostgreSQL 读取，然后让共享 Exporter 流式写 Workbook。

因此“大量数据导出”有两层内存控制：

```text
PostgreSQL 分页读
+ openpyxl write-only 写
```

---

## 13. Formula Injection 防护

Excel 中字符串如果以这些字符开始：

```text
=
+
-
@
Tab
CR
```

某些办公软件可能把它解释为公式。

当前 `_safe_excel_value()` 会自动前置单引号：

```text
=1+1
→ '=1+1
```

这个保护适用于所有字符串数据。

不要在调用方“预先 escape”一套，否则容易出现双重转义/遗漏。

---

## 14. ID 为什么强制文本格式

外部 ID 可能：

- 超过 Excel/JavaScript 安全整数；
- 有前导零；
- 看起来像科学计数法。

当前 ID 列使用：

```text
number_format = "@"
```

主要包括：

```text
内容ID
来源项ID
评论ID
根评论ID
父评论ID
```

Exporter 不把这些 ID 转成 int。

---

## 15. URL 为什么只允许 HTTP/HTTPS 超链接

当前 `_is_http_url()` 只对：

```text
http://
https://
```

且存在 `netloc` 的值创建 Excel Hyperlink。

这样不会把任意自定义 scheme 或奇怪文本自动变成可点击链接。

---

## 16. 时间怎样显示

统一 Excel 展示使用北京时间：

```text
YYYY-MM-DD HH:MM:SS
Asia/Shanghai
```

函数：

```text
_display_datetime()
```

输入 Contract 仍要求 aware datetime；Excel 的北京时间是人工展示投影，不改变数据库 UTC 时间语义。

---

## 17. 导出为什么先写临时文件再原子替换

当前流程：

```text
.<name>.tmp.xlsx
→ workbook.save()
→ _verify_workbook()
→ os.replace(temp, target)
```

失败时删除临时文件。

这样可以避免：

- 生成中途崩溃却留下一个看起来像最终结果的半文件；
- 保存成功但 Workbook 结构不完整仍覆盖旧文件。

---

## 18. 保存后会再验证什么

`_verify_workbook()` 会重新：

```text
load_workbook(read_only=True)
```

并检查：

- Sheet 名和顺序；
- 表头；
- 实际行数；
- 关键第一条 ID。

验证通过才 `os.replace()` 成最终目标。

这不是“openpyxl save 没报错就算成功”。

---

## 19. 源 Excel Reader 和输出 Excel 是两回事

File Import 的源 Excel Reader 负责：

```text
Excel 文件
→ Canonical
```

共享 Exporter 负责：

```text
UnifiedDataExcelV1
→ .xlsx
```

不要让 Exporter 反过来承担导入 Profile 解析。

当前 File Import 详细入口：

```text
backend/src/aima_ugc/adapters/providers/imports/
backend/src/aima_ugc/bootstrap/import_worker.py
```

统一入库见：

[`08_数据入口与统一入库实现.md`](08_数据入口与统一入库实现.md)

---

## 20. 修改 Excel 时应该改哪里

### 改公共列

```text
contracts/export/models.py
→ platform/export/excel.py
→ Export tests
→ 正式 Reporting Projection（如果新增数据源字段）
→ imports_test / Report（按影响）
```

### 只改默认显示列

如果只是某个人工入口的展示配置：

```text
调用方 content_columns / label_detail_columns / comment_columns
```

不要删 Contract 字段。

### 改 `voice_type` 中文显示

```text
platform/export/excel.py
→ _VOICE_TYPE_DISPLAY_NAMES
→ 当前 Analysis Contract/Prompt 是否一致
→ Excel tests
```

### 改 Workbook 视觉

```text
_HEADER_FONT
_BODY_FONT
_HEADER_FILL
*_COLUMN_WIDTHS
_configure_sheet()
```

### 改安全规则

```text
_safe_excel_value()
_is_http_url()
```

必须补安全回归，不允许为了显示方便移除 Formula Injection 保护。

---

## 21. 调试输出 Excel

如果生成文件不对，先分层定位。

### 数据缺失

```text
先看输入 UnifiedDataExcelV1 / UnifiedContentRecordV1
→ 数据是否本来就没有
```

### Analysis 列空

```text
include_analysis 是否 true
→ record.analysis 是否存在
→ 正式 Export 是否匹配当前 Analysis Identity
```

### Sheet/行数不对

```text
ExcelExportSummary
→ _verify_workbook()
→ 输入 record 数量 / comment 数量 / label_pairs
```

### 某列没显示

```text
content_columns / label_detail_columns / comment_columns
→ 是否主动做了列投影
```

### ID 变科学计数法

应该检查共享 Exporter 的文本 ID 格式，不要在业务层把 ID 改成前缀字符串。

---

## 22. 测试应该覆盖什么

- 三个固定 Sheet；
- 默认表头和自定义列投影；
- 空/重复/未知列关闭失败；
- `include_analysis=false/true`；
- 多标签一对多标签明细；
- `voice_type` 中文映射；
- ID 文本格式；
- Formula Injection；
- HTTP/HTTPS Hyperlink；
- 北京时间显示；
- write-only 大数据写出；
- 临时文件 + reopen verification；
- 正式 Export / imports_test 复用同一实现。

目标测试以当前 `tests/unit/` 中 Excel/Reporting/Imports 相关文件为准；最终以 PR 最新 HEAD CI 为准。
