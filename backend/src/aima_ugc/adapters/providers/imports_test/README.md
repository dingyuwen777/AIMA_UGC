# Excel 离线导入、清洗与 AI 多标签打标

本目录提供一个可直接运行的人工入口，把本地舆情 Excel 依次完成：

```text
读取 Excel
→ 转为统一 Canonical JSONL
→ 按关键词过滤
→ 稳定身份去重
→ AI 情感 + 多个一级/二级标签对
→ 导出最终 Excel
```

入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

脚本复用系统正式 Excel Reader、Canonical Mapper、关键词处理、去重、Analysis Service、LLM Adapter 和共享 Excel Exporter，不需要数据库或 Scheduler。

## 1. 修改顶部配置

至少修改：

```python
INPUT_XLSX = Path(r"E:\path\to\source.xlsx")
OUTPUT_ROOT = Path(__file__).with_name("output")
KEYWORDS = ("爱玛",)
SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"

EXCEL_CONTENT_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "命中关键词",
    "情感标签",
    "一级标签",
    "二级标签",
)

ENABLE_REAL_LLM = True
MAX_VALIDATION_RETRIES = 2
LLM_BATCH_SIZE = 20
```

`EXCEL_CONTENT_COLUMNS` 的顺序就是“内容”Sheet 的列顺序。只能使用共享 Exporter 已定义的列；空、重复或未知列会直接报错。

## 2. 配置模型 `.env`

复制 `.env.example` 为 `.env`，填写：

```dotenv
AIMA_LLM_BASE_URL=
AIMA_LLM_API_KEY=
AIMA_LLM_MODEL=

# 可选；不配置默认 60 秒
# AIMA_LLM_TIMEOUT_SECONDS=60
```

只有 Base URL、API Key、Model 必填。当前入口固定使用 OpenAI-compatible Chat Completions Adapter；JSON mode 默认开启。真实 `.env` 已被 Git 忽略，不要把 API Key 写进源码、README、测试、日志或提交记录。

## 3. 运行

```powershell
D:\python314\python.exe E:\work\03_Aima\code\AIMA_UGC\backend\src\aima_ugc\adapters\providers\imports_test\test.py
```

直接执行会调用：

```text
run_all()
```

每次 `run_all()` 先创建一个独立 run 目录，再让所有阶段使用同一个目录。默认 run_id 使用北京时间并显式带 `+0800`：

```text
20260819T142000.123456+0800
```

输出结构：

```text
output/
└─ runs/
   └─ <run-id>/
      ├─ canonical/
      │  └─ contents.jsonl
      ├─ filtered/
      │  └─ contents.jsonl
      ├─ deduplicated/
      │  └─ contents.jsonl
      ├─ analysis/
      │  ├─ checkpoints.jsonl
      │  ├─ attempts.jsonl
      │  └─ failed.jsonl
      ├─ labeled_data.xlsx
      └─ run_summary.json
```

只有显式调用 `export_raw_excel(run_dir=...)` 时，当前 run 目录还会生成 `raw_data.xlsx`。

不同 run 不覆盖彼此。显式复用已经存在的 run_id 会直接报 `FileExistsError`，防止误覆盖旧结果。

## 4. 单步运行

如果需要逐阶段调试，先创建一次 run 目录，然后把同一个 `run_dir` 传给后续函数：

```python
run_dir = prepare_run_dir()

convert(run_dir=run_dir)
filter_keywords(run_dir=run_dir)
deduplicate(run_dir=run_dir)
label_sentiment(run_dir=run_dir)
export_labeled_excel(run_dir=run_dir)
```

不要分别无参数调用 `filter_keywords()`、`deduplicate()` 等依赖上一步输入的函数；它们需要读取同一次 run 的上游文件。

## 5. AI 多标签结构

每条内容仍只有一个整体情感：

```text
正面 / 中性 / 负面 / 混合
```

但可以有一个或多个一级/二级标签对。例如：

```text
骑行性能 / 舒适性
售后服务 / 客服与服务态度
```

系统保存的是成对结构，不是两个互不关联的数组，因此不会丢失“二级标签属于哪个一级标签”的关系。模型输出经过本地 Taxonomy Validator；未知标签、错误父子关系、空标签、重复标签对都不会被静默接受。

历史 `content-label-analysis.v1` 单标签 JSONL/checkpoint 仍可读取；新的模型成功结果写 `content-label-analysis.v2`。

## 6. Excel 怎么展示和筛选多标签

最终 Workbook 有三个 Sheet：

```text
内容
标签明细
评论
```

### 内容

仍保持“一条内容一行”，所以帖子数量不会因为标签多而被放大。

如果一条内容有两个标签对：

```text
骑行性能 / 舒适性
售后服务 / 客服与服务态度
```

“一级标签”单元格显示：

```text
骑行性能
售后服务
```

“二级标签”单元格显示：

```text
舒适性
客服与服务态度
```

两个单元格按同一标签对顺序逐行对应，并启用单元格换行。

### 标签明细

为了使用 Excel 普通下拉筛选，每个标签对单独一行：

```text
内容ID | 平台 | 标题 | 情感标签 | 一级标签 | 二级标签 | 内容链接
```

同一内容可以在该 Sheet 出现多行。因此筛选“一级标签 = 骑行性能”会命中它，筛选“一级标签 = 售后服务”也会命中同一内容。

做“内容总数”统计时以“内容”Sheet 为准；做标签筛选、标签频次、一级/二级组合统计时使用“标签明细”Sheet。

raw 导出也保留“标签明细”Sheet 表头，但 `include_analysis=False` 时不会伪造任何标签行。

## 7. 默认内容列与可选列

默认只显示：

```text
平台
标题
正文
作者
发布时间
内容链接
命中关键词
情感标签
一级标签
二级标签
```

想增加、删除或排序，只改 `EXCEL_CONTENT_COLUMNS`。当前可选内容列：

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

没有数据的列留空，不制造值。“标签明细”和“评论”Sheet 当前不使用 `EXCEL_CONTENT_COLUMNS` 做列裁剪。

## 8. Excel 公共格式

共享 Exporter 统一负责：

- 冻结首行 `A2`；
- 首行自动筛选；
- 表头 `#FFC000`；
- Calibri 11pt，表头粗体；
- 表头行高 16.5，正文默认行高 14.5；
- 显示网格线；
- 不合并单元格；
- HTTP/HTTPS 链接可点击；
- 多标签主表单元格使用换行；
- 页面纵向，左右页边距 0.7、上下 0.75；
- 使用固定有界列宽，不扫描 9 万行自动算宽度；
- openpyxl `write_only=True` 流式写出。

## 9. 源 Excel 输入要求

Profile：`aima-monitoring-excel.v1`，默认 Sheet：`文章`。必须存在以下 13 个表头，允许额外列：

```text
序号
监测项名称
文章编号
标题
内文
媒体名称（中文）
版面
出版日期
媒体类型
作者
全文情感
原文链接
粉丝数
```

平台字段会经过受控归一化；无法映射的平台、非法日期、非法粉丝数、缺稳定身份等都会写转换错误并 fail-closed，不发布半份 `contents.jsonl`。

## 10. 常见排错

- HTTP 401：模型服务认证失败，先独立验证 API Key；不要通过放宽 Analysis Validator 解决认证问题。
- `platform_unmapped`：源媒体/平台值无法映射到已知平台。
- `conversion_errors.jsonl`：先看转换阶段逐行错误。
- `analysis/attempts.jsonl`：看模型每次 Validation Attempt。
- `analysis/failed.jsonl`：看达到 Validation Retry 上限后仍失败的 item。
- `analysis/checkpoints.jsonl`：只保存已通过 Validator 的成功 Analysis，用于恢复和费用安全。
- run_id 已存在：说明该 run 已有历史产物；不要覆盖，使用新的 run_id。
