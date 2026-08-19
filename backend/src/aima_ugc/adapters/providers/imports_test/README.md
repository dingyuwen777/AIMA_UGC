# Excel 离线导入测试 / 调试

本目录是临时 P1 的**人工入口**，用于在不接数据库、不接 Scheduler 的情况下验证本地 XLSX → JSONL → AI 分析 → 最终 Excel 全链路。它不是第二套实现：Excel Reader/Profile/Identity/Mapper 来自 `aima_ugc.adapters.providers.imports`，关键词过滤、去重和 AI 分析业务核心来自平台无关的 `aima_ugc.modules.analysis`，真实模型调用复用 `aima_ugc.adapters.llm`，Excel 输出统一复用 `aima_ugc.platform.export` 的共享 Exporter。

临时 P1 已闭环。当前默认主链：

```text
source.xlsx
→ convert()
→ output/canonical/contents.jsonl
→ filter_keywords()
→ output/filtered/contents.jsonl
→ deduplicate()
→ output/deduplicated/contents.jsonl      # analysis 初始为空
→ label_sentiment()
   ├─ output/analysis/checkpoints.jsonl
   ├─ output/analysis/attempts.jsonl
   ├─ output/analysis/failed.jsonl
   └─ 原子回写同一 output/deduplicated/contents.jsonl
→ export_labeled_excel()
→ output/<source>_<run-id>_labeled_data.xlsx
```

`run_all()` 严格执行上述主链，并原子写出 `output/run_summary.json`。`export_raw_excel()` 仍只是可选人工审阅旁路，不进入默认 `run_all()`，AI 也不会从 raw Excel 回读。

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

- `ENABLE_REAL_LLM=False` 是默认安全状态；不显式改成 `True`，`label_sentiment()` / `run_all()` 会在真实模型请求前拒绝继续；
- `MAX_VALIDATION_RETRIES` 是**额外 Validation Retry 次数**，推荐从 `2` 开始；
- `LLM_BATCH_SIZE` 控制每批交给正式 `ContentLabelingService` 的记录数，不改变单条模型业务字段；
- `ENV_FILE` 指向本目录 `.env`；真实 Secret 不写源码、不提交仓库。

`MAX_VALIDATION_RETRIES` 精确定义：

```text
0 = 首次请求失败后不重试，总请求最多 1 次
1 = 额外重试 1 次，总请求最多 2 次
2 = 额外重试 2 次，总请求最多 3 次
```

Validation Retry 会增加真实模型调用和费用。它只处理**已经收到但本地 Validator 判定不合法**的模型响应；网络超时、连接错误、HTTP 错误属于 Transport/Provider 错误，OpenAI-compatible Adapter 不隐藏网络重试。

## 2. `.env` 配置真实模型

复制：

```text
.env.example
→ .env
```

人工配置只保留真正需要环境/用户决定的值：

```dotenv
# 必填
AIMA_LLM_BASE_URL=
AIMA_LLM_API_KEY=
AIMA_LLM_MODEL=

# 可选；不配置时使用 Adapter 默认 60 秒
# AIMA_LLM_TIMEOUT_SECONDS=60
```

含义：

- `AIMA_LLM_BASE_URL`：OpenAI-compatible API 根地址；
- `AIMA_LLM_API_KEY`：真实 API key；
- `AIMA_LLM_MODEL`：目标模型名；
- `AIMA_LLM_TIMEOUT_SECONDS`：可选的单次 HTTP 请求超时，必须大于 0；省略时使用 `OpenAICompatibleContentLabelingLLM` 的默认 60 秒。

人工入口不再配置 `AIMA_LLM_PROVIDER` 或 `AIMA_LLM_JSON_MODE`：

- 当前真实模型调用固定复用 `OpenAICompatibleContentLabelingLLM`，没有第二个 Adapter 需要人工选择；
- 内容打标默认要求 JSON mode，人工入口直接使用 Adapter 的 `use_json_mode=True` 默认值；本地 Validator 仍是最终强制门禁；
- Analysis/checkpoint 所需的 `model_provider` 审计身份由 Adapter 根据实际 `base_url` 的 hostname 自动生成；显式非默认端口会包含在身份中。例如 `https://api.example.com/v1` 对应 `api.example.com`。该身份不包含 API key、query 或 fragment；
- Adapter 仍保留程序级 `provider_name` 显式覆盖以兼容既有调用，但它不是 `.env` 的人工配置项。

真实 `.env` 已由仓库根 `.gitignore` 忽略。不要把 API key 写到 `.env.example`、README、测试、日志、Change 或提交信息中。

## 3. 单步调用与 `run_all()`

可以在 IDE/调试器中逐步调用：

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
export_raw_excel()  # 可选旁路

# 确认真实模型配置和费用后：
# 1. test.py: ENABLE_REAL_LLM = True
# 2. 填写 .env
label_sentiment()
export_labeled_excel()
```

完整主链：

```python
run_all()
```

`test.py` 直接运行时也执行 `run_all()`。默认顺序固定为：

```text
convert
→ filter_keywords
→ deduplicate
→ label_sentiment
→ export_labeled_excel
```

不会隐式调用 `export_raw_excel()`。

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

过滤只消费 `canonical/contents.jsonl`。关键词先去首尾空白并去重；空关键词直接拒绝。

匹配范围固定为：

```text
title
+
text
```

首版采用**区分大小写的字面包含匹配**，不做模糊匹配、分词、同义词扩展或正则猜测。命中多个关键词时，`matched_keywords` 按 `KEYWORDS` 配置顺序保存。

输出：

```text
output/filtered/contents.jsonl
```

结构为 `UnifiedContentRecordV1`，此时 `analysis=null`。

## 7. `deduplicate()` 规则

去重只消费 `filtered/contents.jsonl`，稳定身份键为：

```text
(platform, external_content_id)
```

同一稳定身份下，只有**除 `content.source.item_locator` 外完全等价**的记录才视为重复；保留第一条并计入 `duplicates_removed`。

如果同一稳定身份的其他字段不同，则视为冲突：

- 不猜哪一条正确；
- 不合并字段；
- 不静默后写覆盖前写；
- 继续扫描收集冲突；
- 不发布部分 `deduplicated/contents.jsonl`。

冲突诊断写：

```text
output/deduplicated/deduplication_conflicts.jsonl
```

无冲突时输出：

```text
output/deduplicated/contents.jsonl
```

## 8. Prompt / Taxonomy 唯一事实源

唯一 Prompt/Taxonomy 事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

具体情感、一级标签、二级标签和父子关系不复制到 `test.py` 或其他 Python Enum/Literal/常量。`PromptTaxonomyLoader` 精确加载 Markdown 内唯一机器 JSON，并计算：

```text
prompt_sha256
taxonomy_sha256
```

以后仅修改标签增删/改名、父子关系、判断标准、典型表达或示例时，只改该 Markdown，不在人工入口维护第二份 taxonomy。

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

本地 Validator 严格检查 JSON、固定/额外字段、item 数量/顺序/唯一性与配对、sentiment membership、primary membership、secondary→primary 父子关系、数组/空标签等。非法输出不做模糊匹配、近义替换或自动猜标签。

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

当前人工入口固定使用 OpenAI-compatible Adapter；只要模型服务兼容该 Chat Completions 协议，切换服务时只改 `.env` 的 Base URL、API Key 和 Model，不需要为每个模型复制 Adapter。真实 Adapter 默认开启 JSON mode，一次 `complete()` 只发送一次 HTTP 请求。Validation Retry 由正式 `ContentLabelingService` 统一控制，`MAX_VALIDATION_RETRIES` 不会在 Adapter/Prompt 再复制一份。

可进入 Validation Retry 的典型错误包括非法 JSON、字段缺失/额外、item 缺失/重复/数量或顺序不一致、`item_no` 无法配对、未知 sentiment/一级标签、二级不属于一级、数组/多标签/空标签和其他结构不合法。

同批已经通过 Validator 的成功 item 会从后续重试集合移除。达到上限仍不合法时：

```text
analysis_status = failed
analysis = None
```

业务 JSONL 不会写猜测标签。

## 11. attempts / checkpoints / failed 与崩溃恢复

执行打标后查看：

```text
output/analysis/
├─ attempts.jsonl
├─ checkpoints.jsonl
└─ failed.jsonl
```

### `attempts.jsonl`

每个模型请求都是独立 attempt，记录 `batch_no`、`attempt_no`、item 配对身份、`validation_error_codes`、`model_provider`、`model`、`prompt_sha256`、`taxonomy_sha256`、时间及可获得的 token/费用。

其中 `model_provider` 是模型服务审计身份。人工入口不要求填写 Provider；OpenAI-compatible Adapter 默认由实际 Base URL 的 hostname（必要时带非默认端口）生成该值。`model` 仍来自 `AIMA_LLM_MODEL`。

### `checkpoints.jsonl`

只有通过本地 Validator 的成功 Analysis 才会先写 checkpoint 并 `flush/fsync`。checkpoint 是恢复/费用安全/审计依据，不是第二业务事实源。

启动下一次打标时会读取 checkpoint。只有以下身份全部与当前运行一致才允许恢复并跳过再次模型调用：

```text
platform
external_content_id
input_hash(title + text + author.display_name)
prompt_sha256
taxonomy_sha256
model_provider（默认由 Base URL endpoint host 派生）
model
```

Prompt、Taxonomy、模型服务 endpoint 身份或模型变化后，旧 checkpoint 仍保留用于审计，但不会被当作当前成功结果复用。

checkpoint 成功结果先持久化，随后 Analysis 写入业务 JSONL 临时文件；临时文件 `flush/fsync` 后通过 `os.replace` 原子替换：

```text
output/deduplicated/contents.jsonl
```

如果最终替换失败，原业务 JSONL 不被破坏；已成功 checkpoint 保留，下一次在身份完全一致时恢复，避免重复付费调用。

### `failed.jsonl`

达到 Validation Retry 上限仍失败的 item 记录：

```text
analysis_status = failed
validation_error_codes = [...]
```

不会构造假的 `ContentLabelAnalysisV1`。

## 12. 如何调试模型非法响应

优先按顺序查看：

1. `output/analysis/attempts.jsonl` 的 `validation_error_codes`；
2. `output/analysis/failed.jsonl` 的最终错误；
3. 本次 `prompt_sha256` / `taxonomy_sha256` 是否与当前 Prompt 一致；
4. `model_provider` 是否与当前 `AIMA_LLM_BASE_URL` 的 endpoint host 一致，`model` 是否与 `AIMA_LLM_MODEL` 一致；
5. HTTP 4xx/5xx、超时或连接错误是否来自目标模型服务本身；如果服务不兼容当前 OpenAI-compatible JSON mode，请先确认该服务的协议能力，而不是关闭本地 Validator。

不要通过关闭 Validator、模糊匹配或程序猜标签制造“成功”。真实 token 只有 Provider 返回时才记录；通用 OpenAI-compatible Adapter 不猜供应商价格。Validation Retry 会增加请求数与费用，checkpoint 恢复只减少身份完全一致的重复成功调用。

## 13. 最终 Excel 与共享 Exporter

唯一共享导出链：

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

`export_labeled_excel()` 只读取**已经回写 Analysis 的同一个**：

```text
output/deduplicated/contents.jsonl
```

输出：

```text
output/<source>_<run-id>_labeled_data.xlsx
```

工作簿固定为 `内容`、`评论` 两个 Sheet；外部 ID 以文本写入，HTTP(S) URL 可点击，文本经过公式注入防护，时间按北京时间展示。Exporter 使用 write-only Workbook 流式写出，并在发布目标文件前重新打开检查 Sheet、表头、行数和关键 ID。

`export_raw_excel()` 同样复用这一 Exporter，但 `include_analysis=False`，只是人工旁路。

## 14. `run_summary.json` 与 P1 边界

`run_all()` 为每次运行生成 `run_id`，最终 Excel 文件名与该 `run_id` 绑定，并原子写：

```text
output/run_summary.json
```

摘要记录 source/output、最终 Excel 路径以及 convert/filter/deduplicate/label/export 各阶段返回摘要。它是运行元数据，不是业务数据事实源。

临时 P1 已闭环；本目录继续作为文件导入、关键词处理、AI 打标和统一 Excel 的人工验证入口。后续正式数据库/API/Job 能力仍复用同一生产 Analysis Service、LLM Port/Adapter、Validator 与 Exporter，不把本目录扩展成第二套正式业务实现。
