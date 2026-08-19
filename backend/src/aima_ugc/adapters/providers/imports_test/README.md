# Excel 离线导入、清洗与 AI 打标

本目录提供一个可直接运行的人工入口，把本地舆情 Excel 依次完成：

```text
读取 Excel
→ 转为统一内容 JSONL
→ 按关键词过滤
→ 稳定身份去重
→ AI 情感/一级/二级标签
→ 导出最终 Excel
```

入口文件：

```text
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

脚本复用系统正式的 Excel Reader、Canonical Mapper、关键词处理、去重、Analysis Service、LLM Adapter 和共享 Excel Exporter，不需要数据库或 Scheduler。

## 1. 最快使用方式

### 1.1 修改 `test.py` 顶部配置

至少修改输入文件、关键词，并在需要真实 AI 时开启模型调用：

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

ENV_FILE = Path(__file__).with_name(".env")
```

各项含义：

| 配置 | 用途 |
| --- | --- |
| `INPUT_XLSX` | 要处理的本地 Excel 路径 |
| `OUTPUT_ROOT` | JSONL、审计文件和最终 Excel 的输出目录 |
| `KEYWORDS` | 需要保留的关键词；命中标题或正文即可保留 |
| `SHEET_NAME` | 源 Excel Sheet 名，默认 `文章` |
| `PROFILE` | Excel 输入格式，当前使用 `aima-monitoring-excel.v1` |
| `EXCEL_CONTENT_COLUMNS` | 最终 Excel 内容列；**配置顺序就是导出顺序** |
| `ENABLE_REAL_LLM` | `False` 时禁止真实模型调用；需要 AI 打标时改为 `True` |
| `MAX_VALIDATION_RETRIES` | 模型返回不合法时最多额外重试次数 |
| `LLM_BATCH_SIZE` | 每个模型请求批次的内容条数 |
| `ENV_FILE` | LLM `.env` 文件位置 |

### 1.2 配置模型 `.env`

复制：

```text
.env.example
→ .env
```

填写：

```dotenv
AIMA_LLM_BASE_URL=
AIMA_LLM_API_KEY=
AIMA_LLM_MODEL=

# 可选；不配置时默认 60 秒
# AIMA_LLM_TIMEOUT_SECONDS=60
```

只有 Base URL、API Key、Model 是必填项。当前人工入口固定使用 OpenAI-compatible Chat Completions Adapter，JSON mode 默认开启；不需要再配置 Adapter 类型、Provider 名称或 JSON mode。

真实 `.env` 已被仓库 `.gitignore` 忽略。不要把真实 API Key 写进源码、README、测试、日志或提交记录。

### 1.3 运行

在仓库已安装环境中可直接运行：

```powershell
D:\python314\python.exe E:\work\03_Aima\code\AIMA_UGC\backend\src\aima_ugc\adapters\providers\imports_test\test.py
```

直接运行 `test.py` 会调用 `run_all()`，顺序固定为：

```text
convert()
→ filter_keywords()
→ deduplicate()
→ label_sentiment()
→ export_labeled_excel()
```

最终成功时控制台会输出 `run_id`、最终 Excel 路径和 `run_summary.json` 路径。

## 2. 最终 Excel 默认显示哪些列

默认 `EXCEL_CONTENT_COLUMNS` 为：

```python
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
```

因此最终 `内容` Sheet 默认只有这 10 列。

### 2.1 增加、删除或调整列顺序

只修改 `EXCEL_CONTENT_COLUMNS`，不需要改 Exporter。

例如想把“内容ID”放第一列，并增加点赞、评论数：

```python
EXCEL_CONTENT_COLUMNS = (
    "内容ID",
    "平台",
    "标题",
    "正文",
    "点赞",
    "评论数",
    "情感标签",
    "一级标签",
    "二级标签",
)
```

导出的列顺序会与这个 tuple 完全一致。

以下配置会直接报错，不会静默猜测：

- 空列配置；
- 同一个列名重复出现；
- 使用未支持的列名。

### 2.2 当前所有可选内容列

`EXCEL_CONTENT_COLUMNS` 只能使用下表中的列名：

| 列名 | 含义 |
| --- | --- |
| `平台` | 统一平台标识 |
| `内容ID` | 平台/导入映射后的稳定内容 ID |
| `来源项ID` | 源文件或 Provider 提供的来源项 ID |
| `内容类型` | image/video/text 等统一内容类型 |
| `标题` | 内容标题 |
| `正文` | 内容正文 |
| `作者` | 作者显示名称 |
| `发布时间` | 北京时间 `YYYY-MM-DD HH:mm:ss` |
| `内容链接` | 内容 HTTP/HTTPS 地址，可点击 |
| `作者粉丝数` | 作者公开粉丝数 |
| `作者关注数` | 作者公开关注数 |
| `作者内容数` | 作者公开内容数 |
| `作者获赞数` | 作者公开累计获赞数 |
| `点赞` | 内容点赞数 |
| `评论数` | 内容评论数 |
| `收藏数` | 内容收藏数 |
| `分享数` | 内容分享数 |
| `转发数` | 内容转发数 |
| `浏览数` | 内容浏览数 |
| `播放数` | 视频播放数 |
| `弹幕数` | 弹幕数 |
| `投币数` | B站等平台的投币数 |
| `下载数` | Provider 可提供时的下载数 |
| `命中关键词` | 本次过滤命中的关键词，多个值用 `；` 分隔 |
| `情感标签` | AI 情感标签 |
| `一级标签` | AI 一级分类 |
| `二级标签` | AI 二级分类 |
| `分析模型` | 本次成功 Analysis 使用的模型 |
| `Prompt版本` | Prompt 的人类可读版本 |
| `Taxonomy版本` | Taxonomy 内容 Hash/版本事实 |
| `来源Provider` | 原始数据来源 Provider |
| `Raw/来源定位` | 可追溯到原始来源项的位置 |
| `评论覆盖` | 评论抓取/覆盖情况摘要 |

没有对应数据的列会留空，不会填造值。

`评论` Sheet 的列目前不通过 `EXCEL_CONTENT_COLUMNS` 配置；`imports_test` 当前只处理帖子/内容，因此通常为空。共享 Exporter 仍保留评论 Sheet 结构，供其他数据入口使用。

## 3. Excel 输出格式

共享 Exporter 的格式参考当前业务 Excel `文章` Sheet，并固化为代码规则，不需要运行时携带模板文件：

- 冻结首行：`A2`；
- 首行开启筛选；
- 表头底色：`#FFC000`；
- 表头：Calibri、11pt、粗体；
- 正文：Calibri、11pt；
- 表头行高：16.5；
- 正文默认行高：14.5；
- 显示网格线；
- 不使用合并单元格；
- 合法 HTTP/HTTPS 内容链接为可点击超链接；
- 页面方向：纵向；
- 页边距：左右 0.7，上下 0.75，页眉/页脚 0.3；
- 标题、正文等长文本使用固定可读列宽，不扫描全表自动调整列宽。

大文件仍使用 openpyxl `write_only=True` 流式写出，避免为了样式把全部 Cell 长期保存在内存中。

## 4. 源 Excel 必须满足什么格式

当前输入 Profile：`aima-monitoring-excel.v1`，默认 Sheet：`文章`。

必须存在以下 13 个表头，允许额外列：

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

主要映射：

```text
标题 → title
内文 → text
媒体名称（中文） → platform 归一化
出版日期 → Asia/Shanghai 解释后转 UTC 保存
作者 → author.display_name
粉丝数 → author.follower_count
原文链接 → canonical_url
```

源 Excel 的“全文情感”不会直接写成系统 AI 标签；最终情感/一级/二级标签来自 Analysis Service。

Reader 使用：

```python
load_workbook(path, read_only=True, data_only=True)
iter_rows(values_only=True)
```

因此适合约 9 万行级别的顺序处理，不需要 pandas。

## 5. 各处理步骤做什么

### `convert()`：Excel → Canonical JSONL

输出：

```text
output/canonical/
├─ contents.jsonl
└─ conversion_errors.jsonl
```

稳定身份按以下优先级生成：

```text
平台 URL 中可验证的原生内容 ID
→ 文章编号
→ 规范化 URL 的 SHA-256
→ 都无法构造则拒绝该行
```

如果任意行转换失败，会继续扫描并把安全诊断写入 `conversion_errors.jsonl`，但不会发布部分 `contents.jsonl`。

### `filter_keywords()`：关键词过滤

匹配范围是标题 + 正文，采用字面包含匹配。关键词会先去首尾空白并去重；多个关键词命中时按 `KEYWORDS` 配置顺序保存。

输出：

```text
output/filtered/contents.jsonl
```

### `deduplicate()`：稳定身份去重

去重键：

```text
(platform, external_content_id)
```

完全等价的重复记录保留第一条；同一稳定身份但业务字段不同视为冲突，不猜哪条正确，也不静默覆盖。

冲突诊断：

```text
output/deduplicated/deduplication_conflicts.jsonl
```

无冲突时：

```text
output/deduplicated/contents.jsonl
```

### `label_sentiment()`：AI 打标签

模型只接收：

```text
title
text
author.display_name
```

不会发送 URL、互动指标、粉丝数、Provider、源 Excel 情感等无关字段。

模型每条必须返回：

```json
{
  "item_no": 1,
  "sentiment": "...",
  "primary_label": "...",
  "secondary_label": "..."
}
```

模型响应还会经过本地 Validator。JSON、字段、item 配对、情感标签、一级/二级标签及父子关系任一不合法，都会进入有界 Validation Retry；不会靠模糊匹配或程序猜标签制造成功。

`MAX_VALIDATION_RETRIES` 的定义：

```text
0 = 最多 1 次请求
1 = 最多 2 次请求
2 = 最多 3 次请求
```

成功 Analysis 会先写 checkpoint，再原子回写同一个：

```text
output/deduplicated/contents.jsonl
```

### `export_labeled_excel()`：最终 Excel

只读取已经回写 Analysis 的 `output/deduplicated/contents.jsonl`。

输出：

```text
output/<源文件名>_<run-id>_labeled_data.xlsx
```

最终列由 `EXCEL_CONTENT_COLUMNS` 决定。

## 6. 输出目录怎么看

完整运行后常见结构：

```text
output/
├─ canonical/
│  ├─ contents.jsonl
│  └─ conversion_errors.jsonl
├─ filtered/
│  └─ contents.jsonl
├─ deduplicated/
│  ├─ contents.jsonl
│  └─ deduplication_conflicts.jsonl
├─ analysis/
│  ├─ attempts.jsonl
│  ├─ checkpoints.jsonl
│  └─ failed.jsonl
├─ <source>_<run-id>_labeled_data.xlsx
└─ run_summary.json
```

说明：

- `contents.jsonl`：各阶段业务数据；
- `attempts.jsonl`：每次模型请求的审计信息；
- `checkpoints.jsonl`：已经成功且可恢复的 Analysis；
- `failed.jsonl`：达到 Validation Retry 上限仍不合法的 item；
- 最终 `.xlsx`：给人查看的数据；
- `run_summary.json`：本次完整运行的阶段摘要。

`export_raw_excel()` 是可选人工审阅函数，只把当前 `deduplicated/contents.jsonl` 导出成分析列为空的 Excel，不进入 `run_all()` 默认链路。

## 7. 也可以单步运行

在 Python/IDE 中：

```python
from aima_ugc.adapters.providers.imports_test.test import (
    convert,
    deduplicate,
    export_labeled_excel,
    export_raw_excel,
    filter_keywords,
    label_sentiment,
    run_all,
)

convert()
filter_keywords()
deduplicate()
export_raw_excel()  # 可选人工查看
label_sentiment()
export_labeled_excel()
```

完整执行：

```python
run_all()
```

单步方式便于确认到底是源 Excel、关键词、去重、模型还是最终导出出现问题；每一步仍调用同一套生产实现。

## 8. 常见问题怎么排查

### Excel 转换失败

查看 `output/canonical/conversion_errors.jsonl`。常见原因包括缺少必要表头、平台无法安全识别、日期/粉丝数格式非法或无法建立稳定内容身份。

### 去重失败

查看 `output/deduplicated/deduplication_conflicts.jsonl`。同一 `(platform, external_content_id)` 出现不同业务内容时脚本会 fail-closed，不自动选一条覆盖另一条。

### 模型 HTTP 401 / 4xx / 5xx / 超时

这是模型 Transport/Provider 错误，不属于 Validation Retry。优先确认：

1. `.env` 是否是当前脚本实际读取的文件；
2. Base URL 是否正确；
3. API Key 是否有效；
4. Model 名称是否是目标服务允许调用的模型；
5. 账号权限/余额/网络是否满足服务商要求。

Adapter 不会在错误信息中回显 API Key 或 Provider 原始响应正文。

### 模型有响应，但标签不合法

查看：

```text
output/analysis/attempts.jsonl
output/analysis/failed.jsonl
```

重点看 `validation_error_codes`。不要通过关闭 Validator 或程序猜标签绕过错误。

### 重新运行为什么有些内容不再调用模型

成功结果会写入 `output/analysis/checkpoints.jsonl`。只有输入内容、Prompt、Taxonomy、模型服务身份和模型都与当前运行一致时才恢复 checkpoint，避免重复付费；任一身份变化都会重新分析。

## 9. 标签规则在哪里修改

情感、一级标签、二级标签、父子关系和判断标准的唯一 Prompt/Taxonomy 文件：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

如果只是增加/删除/改名标签、调整父子关系或修改判断标准，不需要在 `test.py` 里复制一份标签表。运行时会读取当前 Markdown，并重新计算 Prompt/Taxonomy Hash。
