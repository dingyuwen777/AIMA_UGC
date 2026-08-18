# Excel 离线导入测试 / 调试

本目录是临时 P1 的**人工入口**，用于在不接数据库、不接 Scheduler 的情况下逐步验证本地 XLSX → JSONL → AI 分析链。它不是第二套实现：Excel Reader/Profile/Identity/Mapper 来自 `aima_ugc.adapters.providers.imports`，关键词过滤、去重和 AI 分析业务核心来自平台无关的 `aima_ugc.modules.analysis`，真实模型调用复用 `aima_ugc.adapters.llm`，Excel 人工审阅视图复用 `aima_ugc.platform.export` 的唯一共享 Exporter。

当前 P1A—P1F 已闭环。已可单步执行：

```text
source.xlsx
→ convert()
→ output/canonical/contents.jsonl        # CanonicalContentV1
→ filter_keywords()
→ output/filtered/contents.jsonl         # UnifiedContentRecordV1
→ deduplicate()
→ output/deduplicated/contents.jsonl     # analysis 初始为空
     ├─ export_raw_excel()               # 可选人工审阅旁路
     │  → output/raw_data.xlsx
     └─ label_sentiment()                # 显式启用真实模型后执行
        → output/analysis/checkpoints.jsonl
        → output/analysis/attempts.jsonl
        → output/analysis/failed.jsonl
        → 原子回写同一 output/deduplicated/contents.jsonl
```

P1F 尚**没有**建立 `run_all()`、checkpoint 自动崩溃恢复、`run_summary.json` 或最终 `labeled_data.xlsx` 串联；这些属于 P1G。`export_raw_excel()` 只是可选旁路，不进入未来默认 `run_all()`，AI 也不会从 raw Excel 回读。

## 1. 顶部人工配置

编辑 `test.py` 顶部：

```python
INPUT_XLSX = Path(r"E:\path\to\source.xlsx")
OUTPUT_ROOT = Path(__file__).with_name("output")

KEYWORDS = ("爱玛",)

SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"

ENABLE_REAL_LLM = False
MAX_VALIDATION_RETRIES = 2
LLM_BATCH_SIZE = 20

ENV_FILE = Path(__file__).with_name(".env")
```

说明：

- `ENABLE_REAL_LLM=False` 是默认安全状态；不显式改成 `True`，`label_sentiment()` 会在读取 `.env` 或发网络请求前直接拒绝；
- `MAX_VALIDATION_RETRIES` 是**额外 Validation Retry 次数**，推荐从 `2` 开始；
- `LLM_BATCH_SIZE` 控制每批送入正式 `ContentLabelingService` 的业务记录数量，不改变单条业务字段；
- `ENV_FILE` 指向本目录 `.env`；真实 Secret 不写源码、不提交仓库。

`MAX_VALIDATION_RETRIES` 精确定义：

```text
0 = 首次请求失败后不重试，总请求最多 1 次
1 = 额外重试 1 次，总请求最多 2 次
2 = 额外重试 2 次，总请求最多 3 次
```

Validation Retry 会增加真实模型调用和费用。它只针对**模型已经返回、但本地 Validator 判定不合法**的响应；网络超时、连接错误、HTTP 错误属于 Transport/Provider 错误，当前 OpenAI-compatible Adapter 不隐藏网络重试。

## 2. `.env` 配置真实模型

复制：

```text
.env.example
→ .env
```

当前示例变量：

```dotenv
AIMA_LLM_BASE_URL=https://api.openai.com/v1
AIMA_LLM_API_KEY=
AIMA_LLM_MODEL=
AIMA_LLM_PROVIDER=openai-compatible
AIMA_LLM_TIMEOUT_SECONDS=60
AIMA_LLM_JSON_MODE=true
```

含义：

- `AIMA_LLM_BASE_URL`：OpenAI-compatible API 根地址；
- `AIMA_LLM_API_KEY`：真实 API key；
- `AIMA_LLM_MODEL`：目标模型名；
- `AIMA_LLM_PROVIDER`：用于 Analysis 审计的稳定 Provider 名称；
- `AIMA_LLM_TIMEOUT_SECONDS`：单次 HTTP 请求超时，必须大于 0；
- `AIMA_LLM_JSON_MODE`：`true/false`。Provider 支持 JSON mode 时可保持 `true`；不支持时设为 `false`。

真实 `.env` 已由仓库根 `.gitignore` 忽略。不要把 API key 写到 `.env.example`、README、测试、日志、Change 或提交信息中。

即使 Provider 支持 JSON mode，本地 Validator 仍是强制边界，不会因模型声明“结构化输出”而跳过校验。

## 3. 单步调用

本工具不增加 CLI 参数。可以在 IDE/调试器中按顺序单独调用：

```python
from aima_ugc.adapters.providers.imports_test.test import (
    convert,
    deduplicate,
    export_raw_excel,
    filter_keywords,
    label_sentiment,
)

convert()
filter_keywords()
deduplicate()
export_raw_excel()  # 可选，不属于默认主链

# 确认真实模型配置和费用后：
# 1. test.py: ENABLE_REAL_LLM = True
# 2. 填写 .env
label_sentiment()
```

当前 `__main__` 仍只执行 `convert()`；完整 `run_all()` 由 P1G 建立，P1F 不提前串联后续步骤。

## 4. Excel Profile 与 Canonical 映射

首版 Profile：`aima-monitoring-excel.v1`，默认 Sheet：`文章`。

要求存在以下 13 列，允许额外列：

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

Reader 使用：

```python
load_workbook(path, read_only=True, data_only=True)
iter_rows(values_only=True)
```

因此不会为了约 9 万行数据构造普通可写 Workbook，也没有引入 pandas。

P1 保持 `CanonicalContentV1` 不变，不向 Canonical 增加 AI 标签。主要映射：标题→`title`、内文→`text`、媒体名称→`platform`、出版日期按 `Asia/Shanghai` 解释后转 UTC、作者→`author.display_name`、粉丝数→`author.follower_count`、原文链接→`canonical_url`。源“全文情感”不写成系统 AI Analysis。

稳定身份严格按：

```text
平台 URL 中可验证的原生内容 ID
→ 文章编号
→ 规范化 URL 的 SHA-256
→ 无法构造则拒绝该行
```

## 5. `convert()` 输出与错误

成功输出：

```text
output/canonical/
├─ contents.jsonl
└─ conversion_errors.jsonl
```

`contents.jsonl` 每行都可由 `CanonicalContentV1` 重新校验。任何一行不合法时转换继续扫描并记录安全的行号诊断，但**不会发布部分业务 `contents.jsonl`**。

## 6. `filter_keywords()` 规则

过滤只消费 `canonical/contents.jsonl`。关键词配置先执行最小清洗：去掉首尾空白、去除重复项；空关键词直接拒绝，避免产生“匹配所有内容”的错误结果。

匹配范围固定为：

```text
title
+
text
```

首版采用**区分大小写的字面包含匹配**，不做模糊匹配、分词、同义词扩展或正则猜测。命中多个关键词时，`matched_keywords` 按 `KEYWORDS` 的配置顺序保存。

输出：

```text
output/filtered/contents.jsonl
```

每行结构：

```json
{
  "schema_version": "content-record.v1",
  "content": {"schema_version": "content.v1"},
  "matched_keywords": ["爱玛"],
  "analysis": null
}
```

## 7. `deduplicate()` 规则

去重只消费 `filtered/contents.jsonl`，稳定身份键为：

```text
(platform, external_content_id)
```

同一稳定身份下，只有**除 `content.source.item_locator` 外完全等价**的记录才视为重复；保留第一条并计入 `duplicates_removed`。忽略 `item_locator` 只是因为同一来源内容重复出现在 Excel 不同行时行定位天然不同，不代表其他业务字段可以被忽略。

如果同一稳定身份的其他字段不同，则视为冲突：

- 不猜哪一条正确；
- 不合并字段；
- 不静默“后写覆盖前写”；
- 继续扫描以收集冲突；
- 不发布部分 `deduplicated/contents.jsonl`。

安全诊断写入：

```text
output/deduplicated/deduplication_conflicts.jsonl
```

没有冲突时输出：

```text
output/deduplicated/contents.jsonl
```

## 8. Prompt / Taxonomy 唯一事实源

唯一 Prompt/Taxonomy 事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

具体情感、一级标签、二级标签和父子关系不复制到 `test.py` 或其他 Python Enum/Literal/常量。`PromptTaxonomyLoader` 从 Markdown 中唯一机器 JSON 块加载当前闭集，并计算：

```text
prompt_sha256
taxonomy_sha256
```

以后仅修改标签增删/改名、父子关系、判断标准、典型表达或示例时，只改该 Markdown，不在本人工入口维护第二份 taxonomy。

## 9. 模型最小输入与本地 Validator

每条内容发给模型的业务字段只允许：

```text
title
text
author.display_name
```

缺失填 `""`。临时 `item_no` 只用于批次配对。

禁止发送内容 ID、平台 ID、URL、点赞/评论/转发/粉丝等指标、Provider、`matched_keywords`、源 Excel 全文情感、Raw locator 或其他 Provider 私有字段。

模型每条只允许返回：

```json
{
  "item_no": 1,
  "sentiment": "...",
  "primary_label": "...",
  "secondary_label": "..."
}
```

本地 Validator 严格检查：JSON、固定字段、额外字段、item 数量/顺序/唯一性与配对、sentiment membership、primary membership、secondary→primary 父子关系、数组/空标签等。非法输出不做模糊匹配、近义替换或自动猜标签。

## 10. `label_sentiment()` 与 Validation Retry

`label_sentiment()` 只读取：

```text
output/deduplicated/contents.jsonl
```

并组装：

```text
PromptTaxonomyLoader
→ ContentLabelingService
→ OpenAICompatibleContentLabelingLLM
→ label_unified_content_jsonl
```

真实 Adapter 一次 `complete()` 只发送一次 HTTP 请求，不隐藏 Transport Retry。Validation Retry 由正式 `ContentLabelingService` 统一控制，`MAX_VALIDATION_RETRIES` 不会在 Adapter/Prompt 再复制一份。

可进入 Validation Retry 的典型错误包括：

- 非法 JSON；
- 缺少必须字段；
- 额外未声明字段；
- item 缺失/重复/数量不一致；
- `item_no` 无法配对；
- 未知 sentiment；
- 未知一级标签；
- 二级标签不属于一级；
- 数组、多标签、空标签；
- 其他结构不合法。

同批已经通过 Validator 的成功 item 会从后续重试集合移除，不会因其他 item 失败重复调用。达到上限仍不合法时：

```text
analysis_status = failed
analysis = None
```

业务 JSONL 不会写猜测标签。

## 11. attempts / checkpoints / failed

执行 `label_sentiment()` 后查看：

```text
output/analysis/
├─ attempts.jsonl
├─ checkpoints.jsonl
└─ failed.jsonl
```

### `attempts.jsonl`

每个模型请求都是独立 attempt，记录：

```text
batch_no
attempt_no
item_nos
validation_error_codes
model_provider
model
prompt_sha256
taxonomy_sha256
started_at
completed_at
input_tokens / output_tokens（Provider 返回时）
cost_amount / cost_currency（可获得时）
```

还包含安全的 item 配对身份和 `input_hash`，用于确认哪条记录发生了哪次调用。

### `checkpoints.jsonl`

只有通过本地 Validator 的成功 Analysis 才会先写 checkpoint，并执行 `flush/fsync`。随后才把 Analysis 写入业务 JSONL 临时文件，临时文件 `flush/fsync` 后再原子替换：

```text
output/deduplicated/contents.jsonl
```

checkpoint 是恢复/费用安全/审计依据，不是第二业务事实源。

### `failed.jsonl`

达到 Validation Retry 上限仍失败的 item 会记录：

```text
analysis_status = failed
validation_error_codes = [...]
```

不会构造假的 `ContentLabelAnalysisV1`。

### 崩溃恢复边界

P1F 已保证：成功 checkpoint 在业务 JSONL 发布前落盘；最终 `os.replace` 失败时原业务 JSONL 不被破坏，checkpoint 仍保留。

P1F **尚未**实现从 checkpoint 自动恢复中断、跨进程重启跳过“checkpoint 已成功但业务 JSONL 尚未发布”的 item。该恢复闭环属于 P1G；当前不要手工把 checkpoint 当成第二业务 JSONL 覆盖原文件。

## 12. 如何调试模型非法响应

优先按顺序查看：

1. `output/analysis/attempts.jsonl` 的 `validation_error_codes`；
2. `output/analysis/failed.jsonl` 的最终错误；
3. 本次 `prompt_sha256` / `taxonomy_sha256` 是否与当前 Prompt 一致；
4. `model_provider` / `model` 是否是预期配置；
5. Provider 是否支持当前 `AIMA_LLM_JSON_MODE` 设置。

如果输出不合法，应修 Prompt、模型配置或 Provider 兼容性，不要关闭 Validator、模糊匹配或在程序里猜测标签。

真实 token 只有 Provider 返回时才会记录。通用 OpenAI-compatible Adapter 不猜测供应商价格，因此未提供真实价格时费用字段可以为空；Validation Retry 本身会增加模型请求数量和费用。

## 13. 共享 Excel Exporter

P1D 建立唯一共享导出链：

```text
UnifiedDataExcelV1
→ aima_ugc.platform.export.excel
→ .xlsx
```

Contract 与实现位置：

```text
backend/src/aima_ugc/contracts/export/
contracts/export/unified-data-excel.v1.schema.json
backend/src/aima_ugc/platform/export/excel.py
```

工作簿固定为 `内容`、`评论` 两个 Sheet；外部 ID 以文本写入，HTTP(S) URL 可点击，文本经过公式注入防护，时间统一按北京时间展示。`raw_data.xlsx` 与未来 `labeled_data.xlsx` 使用同一列 Schema；raw 导出只把分析列留空，不创建另一套业务事实源。

Exporter 使用 write-only Workbook 流式写出，并在发布目标文件前重新打开检查 Sheet、表头、行数和关键 ID。完整业务数据仍以 JSONL 为事实源，Excel 只用于人工查看和交付。

## 14. 当前 P1F / P1G 边界

P1F 已实现并可单步验证：

```text
convert()
filter_keywords()
deduplicate()
export_raw_excel()  # 可选
label_sentiment()   # 显式真实模型开关
```

下一单元 P1G 才实现：

```text
run_all()
checkpoint 自动崩溃恢复
run_summary.json
export_labeled_excel()
最终 Excel 只读取回写后的同一 deduplicated/contents.jsonl
```

不要在 P1F 人工入口中自行复制第二套 `run_all()`、恢复算法或 Excel 写出逻辑。