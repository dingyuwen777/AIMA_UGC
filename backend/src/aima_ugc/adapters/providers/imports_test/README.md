# Excel 离线导入、清洗、AI 多标签打标与报告

本目录提供一个可以直接运行的人工入口：

```text
本地 Excel
→ Canonical JSONL
→ 词包相关性清洗
→ 稳定身份去重
→ 可选 PostgreSQL 正式入库
→ DeepSeek / OpenAI-compatible AI 多标签打标
→ 最终 Excel
→ Markdown / Word 数据报告
```

入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

脚本复用系统正式 Reader、Mapper、关键词过滤、去重、Analysis Service、LLM Adapter、共享 Excel Exporter 和 Provider-neutral Report Renderer。默认 `WRITE_TO_DATABASE = False`，因此普通人工文件调试不要求数据库或 Scheduler；只有显式开启数据库模式时才连接已经由开发者准备好的 PostgreSQL 18，并调用正式 File Import / Content Ingestion 实现。报告阶段只读最终统一 Excel，不反向修改 Canonical、Analysis、数据库或 Excel 数据。

## 1. 先修改 `test.py` 顶部配置

常用配置：

```python
# 单文件：自动走单文件转换。
INPUT_XLSX_FILES = Path(r"E:\path\to\source.xlsx")

# 多文件：改为 Path 元组，按顺序合并到同一个 run。
INPUT_XLSX_FILES = (
    Path(r"E:\path\to\source-1.xlsx"),
    Path(r"E:\path\to\source-2.xlsx"),
)

OUTPUT_ROOT = Path(__file__).with_name("output")
KEYWORD_PACK_FILE = Path(__file__).with_name("keyword_pack.txt")

# None 表示自动扫描所有 Sheet；也可填写精确 Sheet 名强制指定。
SHEET_NAME = None
PROFILE = "aima-monitoring-excel.v1"
WRITE_TO_DATABASE = False

# 仅限制报告统计；范围包含开始日和结束日。None 表示报告使用全部日期。
REPORT_DATE_RANGE = (
    date(2026, 8, 13),
    date(2026, 8, 19),
)

ENABLE_REAL_LLM = True

# 一条内容 = 一次独立 LLM 请求；最多同时 250 个请求。
LLM_CONCURRENCY = 250

# HTTP/网络/429/可恢复 5xx 的额外重试次数。
MAX_TRANSPORT_RETRIES = 4

# HTTP 成功但模型 JSON/标签校验失败的额外重试次数。
MAX_VALIDATION_RETRIES = 2
```

报告默认模板由 `aima_ugc.platform.reporting` 统一维护在
`backend/src/aima_ugc/platform/reporting/report_template.md`，人工入口不再维护第二份模板路径。

Excel 输入只有 `INPUT_XLSX_FILES` 一个配置入口。它接受一个 `Path` 或非空的
`Path` 元组；空元组会在转换前报错，其他类型不受支持。

当前没有 `LLM_BATCH_SIZE` 配置。**不会把 20 条内容拼进一次模型请求。**

`LLM_CONCURRENCY = 250` 表示最大在飞 HTTP 请求数，不是每个请求包含 250 条数据。

`ENABLE_REAL_LLM = True` 表示人工执行到 AI 打标阶段时默认发送真实付费请求；仅导入模块或
运行普通自动测试不会触发模型。若本次只想处理到去重/导出，请不要调用打标阶段，或先将该
开关改为 `False`。模型费用仍按实际请求、重试和服务商计费规则产生。

多 Excel 固定采用：

```text
按 INPUT_XLSX_FILES 顺序读取
→ 合并到同一 canonical/contents.jsonl
→ 全局关键词过滤
→ 全局稳定身份去重
→ 一次 AI 打标阶段
→ 一个 labeled_data.xlsx
→ 按 REPORT_DATE_RANGE 统计的一份 Markdown / Word 报告
```

`REPORT_DATE_RANGE` 只在最终报告生成时生效。Canonical、关键词过滤、去重、数据库写入、
AI 打标和 `labeled_data.xlsx` 始终处理全部输入数据；报告不会因此减少模型请求或修改最终
Excel。报告周期使用北京时间自然日闭区间。

同一稳定身份由配置中靠前文件的记录代表。不同目录下也不允许使用相同文件名，因为
Canonical `source_value` 使用文件名保存来源；文件名重复会在合并前直接失败，避免来源混淆。
任一文件出现坏行时，整个合并 Canonical JSONL 都不会发布。

## 2. 配置最终 Excel 三个 Sheet 的列

默认“内容”Sheet 只显示：

```python
EXCEL_CONTENT_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "命中关键词",
    "发声类型",
    "情感标签",
    "一级标签",
    "二级标签",
)
```

默认“标签明细”Sheet 显示：

```python
EXCEL_LABEL_DETAIL_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "命中关键词",
    "发声类型",
    "情感标签",
    "一级标签",
    "二级标签",
)
```

默认“评论”Sheet 显示：

```python
EXCEL_COMMENT_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "评论内容",
    "作者",
    "评论时间",
    "评论点赞",
    "回复数",
    "评论层级",
    "评论ID",
    "根评论ID",
    "父评论ID",
)
```

三个元组分别控制对应 Sheet，元组顺序就是 Excel 列顺序。可以删除、增加或调整该 Sheet 的已有共享列；空配置、重复列或未知列会直接报错。

当前可选内容列：

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

“标签明细”可以选择全部内容共享列；其中“一级标签”“二级标签”按当前标签对逐行展开，其他列来自同一个归一化内容记录。

“评论”可以选择全部评论共享列，也可以选择对应归一化内容的共享列。重名列沿用评论语义：`作者`、`来源Provider`、`Raw/来源定位` 分别表示评论作者和评论来源；`平台`、`内容ID` 是内容与评论共享的稳定关联。

标签明细的完整默认列为：

```text
内容ID
平台
标题
情感标签
一级标签
二级标签
内容链接
```

评论的完整默认列为：

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

报告当前依赖：

- “内容”：`平台`、`发布时间`、`命中关键词`、`情感标签`、`一级标签`、`二级标签`；
- “标签明细”：`平台`、`情感标签`、`一级标签`、`二级标签`；
- “评论”：`平台`。

使用默认列可以直接生成报告；如果删除这些依赖列，报告会明确拒绝，而不会猜测或伪造统计字段。

## 3. 配置清洗词包

默认文件：

```text
backend/src/aima_ugc/adapters/providers/imports_test/keyword_pack.txt
```

规则：

```text
一行一个标准词
空行忽略
# 开头的行是注释
```

例如：

```text
# 品牌词
爱玛

# 车型
元宇宙Pony
F2Lite-碟刹
马赫U7Pro
```

当前文件已经包含“爱玛”和已提供的 102 条车型原始清单。

匹配前会自动执行：

```text
Unicode NFKC
→ casefold 大小写折叠
→ 删除空白
→ 忽略 - _ ·
```

因此只需要配置标准词：

```text
F2Lite-碟刹
```

以下机械变体都可以命中：

```text
F2Lite-碟刹
f2lite-碟刹
F2 Lite_碟刹
Ｆ２Ｌｉｔｅ·碟刹
```

最终 `matched_keywords` 和 Excel“命中关键词”仍保存词包标准名称，不保存帖子里的变体文本。

当前清洗只检查：

```text
title
text
```

不自动推导真正俗称、别名、错别字、拼音或同义词。真正业务别名目前应显式再加一条词；未来正式网页关键词管理如何建模别名，仍留到对应正式 Change 决策。

## 4. 配置模型 `.env`

复制：

```text
.env.example
```

为：

```text
.env
```

填写：

```dotenv
AIMA_LLM_BASE_URL=
AIMA_LLM_API_KEY=
AIMA_LLM_MODEL=

# 可选；不配置默认 60 秒
# AIMA_LLM_TIMEOUT_SECONDS=60
```

只有 Base URL、API Key、Model 必填。真实 `.env` 已被仓库忽略；不要把 API Key 写进源码、README、测试、日志或提交记录。

每个配置项的含义和取值来源：

| 配置 | 含义 | 从哪里查看 |
| --- | --- | --- |
| `AIMA_LLM_BASE_URL` | OpenAI-compatible API 根地址；代码从它提取 provider host | 模型供应商官方 API 接入文档；DeepSeek 为 `https://api.deepseek.com` |
| `AIMA_LLM_API_KEY` | 调用模型的 Secret | 模型供应商控制台创建；不能从价格页复制，也不能提交 Git |
| `AIMA_LLM_MODEL` | 请求使用的精确模型 ID | 供应商官方模型/价格页；必须与价格目录的 `model` 完全一致 |
| `AIMA_LLM_TIMEOUT_SECONDS` | 单个 HTTP 请求超时秒数 | 根据实际响应延迟调整；未配置使用代码默认 60 秒 |

`.env` 不保存单价、生效时间或人工价格版本。运行时调用参数与公开价格事实职责不同，混在一起
既不能提高计算精度，也会增加误配置。

当前入口使用 OpenAI-compatible Chat Completions Adapter，JSON mode 默认开启，本地 Validator 仍会再次严格校验模型结果。

### 4.1 价格配置与其他模型

价格目录：

```text
backend/src/aima_ugc/adapters/llm/pricing.toml
```

计费与请求审计由全平台共享 LLM Adapter 持有，完整边界见
`backend/src/aima_ugc/adapters/llm/README.md`。本入口只提供当前人工 run 的配置和审计文件位置，
不维护一套 Excel 专用计费实现。

一个文本模型只配置计算和核验真正需要的字段：

| 字段 | 含义 | 从哪里查看 |
| --- | --- | --- |
| `provider` | Base URL 的小写 host，例如 `api.deepseek.com` | 供应商官方 API 地址；网关有自己的 host 和可能不同的价格，不能冒用原厂价格 |
| `model` | 精确模型 ID | 供应商官方模型/价格页 |
| `currency` | 价格页使用的三字母币种，例如 `CNY` | 官方价格页 |
| `input_per_million` | 无缓存拆分模型每百万输入 token 单价 | 官方价格页；与下面两项二选一 |
| `input_cache_hit_per_million_tokens` | 输入（缓存命中），每百万 tokens 单价 | 官方价格页和 API usage 定义 |
| `input_cache_miss_per_million_tokens` | 输入（缓存未命中），每百万 tokens 单价 | 官方价格页和 API usage 定义 |
| `output_per_million_tokens` | 输出，每百万 tokens 单价 | 官方价格页 |
| `source_url` | 上述价格的官方依据 | 供应商官方价格页面，不使用二手报价 |
| `effective_date` | 本条价格在 AIMA 价格目录中的生效日期，格式 `YYYY-MM-DD` | 价格维护变更的启用日期；若供应商没有单独公布生效日，不得写成“供应商公告日” |
| `timezone` | 分时价格使用的 IANA 时区，例如 `Asia/Shanghai` | 官方价格页公布的计费时区；全天固定价格不配置 |
| `price_periods.name` | 价格时段的可读名称，例如 `off_peak`、`peak` | 本地稳定名称，不参与费用公式 |
| `price_periods.time_ranges` | 该时段适用的 `HH:MM-HH:MM` 半开区间 | 官方价格页；无此字段的一项是全天默认价 |

`schema_version` 只是 TOML 解析格式，正常换模型时不修改。代码根据规范化后的 provider、model、
币种、单价和来源 URL 自动计算价格快照 SHA-256，不需要手工维护 `pricing_version`。
`effective_date` 是可读、可校验的目录元数据，不参与 token 费用公式或既有审计快照 Hash。

旧 TOML 的 `input_cache_hit_per_million`、`input_cache_miss_per_million`、
`output_per_million` 可在兼容期读取，但运行时会发出 `FutureWarning`；新配置不要继续使用旧字段。

更换模型时只做两件事：

1. 把 `.env` 的 `AIMA_LLM_MODEL` 改为供应商官方模型 ID；
2. 如果 `pricing.toml` 还没有该 `provider + model`，按官方价格页增加一项并运行价格测试。

全天固定价格可以直接把单价写在 `[[models]]` 下。供应商存在分时价格时，在模型级配置
`timezone`，并把各时段单价写入 `[[models.price_periods]]`；无 `time_ranges` 的一项是默认价，其他
时段优先匹配且不能重叠。该结构按 provider/model 独立配置，不是 DeepSeek 特例，其他模型既可以
只有一个全天价格，也可以定义自己的时区和时段。普通输入/输出两档计价，以及缓存命中/未命中/
输出三档计价的文本模型可以直接配置。图片、音频、按请求、阶梯折扣或其他 token 分类不能套用
这个公式，需要先扩展计费维度和测试。
没有匹配价格或 API usage 缺少必要分类时，标签处理仍继续，但费用明确记为不可计算，不使用
默认价格猜测。

DeepSeek 当前价格和 usage 字段以以下官方页面为准：

- <https://api-docs.deepseek.com/zh-cn/quick_start/pricing/>
- <https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/>

2026-08-20 直接核验的 `deepseek-v4-pro` 人民币价格为：空闲时段输入（缓存命中）0.15、输入
（缓存未命中）4.5、输出 13.5 CNY / 百万 tokens；高峰时段分别为 0.30、9.0、27.0 CNY /
百万 tokens。高峰时段是北京时间 09:00–12:00、14:00–18:00，区间按 `[start, end)` 解释，
其余时间使用空闲价格。当前 `pricing.toml` 已与该一手价格页一致。

## 5. 250 并发实际怎么运行

AI 阶段不是“250 条一次发给模型”，而是：

```text
内容 1 → HTTP Request 1
内容 2 → HTTP Request 2
...
内容 N → HTTP Request N
```

最多同时：

```text
250 个独立请求
```

执行前先完成整个 `deduplicated/contents.jsonl` 的本地预检：

- 每行 JSONL 合法；
- 稳定身份不重复；
- 已有 `analysis` 的内容不再请求；
- 可用 checkpoint 先标记为恢复项。

预检通过以后先只发 **1 个 canary 请求**。认证、余额、权限、请求参数等基础问题在 canary 就会暴露，不会一启动就放大成 250 个无效请求。

canary 正常后进入有界滑动窗口：

```text
最多 250 个 Future 在飞
→ 任一请求完成
→ 立即补入下一条
```

不会等“这一组 250 全部完成”才继续，也不会一次创建 90,000 个 Future。

HTTP 使用一个共享 `httpx.Client`，连接池容量与 `LLM_CONCURRENCY` 一致并复用 keep-alive，不为每条数据重新建立 Client/TLS 连接。

同一次 run 的 Prompt/Taxonomy 也只读取解析一次，然后冻结为同一份快照供所有请求复用。

## 6. 两种重试不要混淆

### 6.1 Transport Retry

属于 HTTP/网络层，例如：

```text
网络连接/超时类 httpx.HTTPError
HTTP 408
HTTP 429
HTTP 500
HTTP 502
HTTP 503
HTTP 504
```

默认：

```python
MAX_TRANSPORT_RETRIES = 4
```

使用指数退避 + jitter。

以下错误不做无意义网络重试：

```text
HTTP 400
HTTP 401
HTTP 402
HTTP 403
HTTP 404
HTTP 422
Provider 返回的成功 HTTP 但协议结构本身非法
```

如果 canary 遇到这类问题，AI 阶段只会产生该一个请求，然后立即停止。

如果正式并发阶段出现 Transport 错误并在当前内容上达到重试上限，程序停止继续调度新的模型请求；已经成功写入 checkpoint 的结果保留。修复网络/Provider 后重新运行，会直接恢复已成功项，而不是重新打标。

### 6.2 Validation Retry

属于 HTTP 已经成功，但模型结果不符合本地规则，例如：

```text
JSON 不合法
缺字段
未知情感
未知一级标签
二级标签不属于对应一级
重复标签对
```

默认：

```python
MAX_VALIDATION_RETRIES = 2
```

当前一条内容就是一个请求，因此 Validation Retry 只重新请求这条内容，不会牵连别的成功内容。

达到 Validation Retry 上限仍失败：

```text
analysis = null
→ 写 analysis/failed.jsonl
→ 继续处理其他内容
```

## 7. 为什么不会因为并发把数据写乱

250 个模型请求完成顺序可能是：

```text
3 → 1 → 5 → 2 → 4
```

但 Worker 不直接写业务 JSONL。

成功结果先由单一协调线程写：

```text
analysis/checkpoints.jsonl
```

并执行 `flush + fsync`。

全部模型阶段结束后，再重新按原始顺序扫描：

```text
deduplicated/contents.jsonl
```

用成功 checkpoint 填回 Analysis，写临时 JSONL，再用 `os.replace` 原子替换。

所以最终业务文件仍是：

```text
1 → 2 → 3 → 4 → 5
```

不会按网络返回顺序重排。

## 8. 怎么防止重复打标

在真实请求前依次排除：

```text
已有业务 analysis
→ 跳过

当前输入 + Prompt + Taxonomy + Provider + Model 全匹配的成功 checkpoint
→ 恢复

同一 deduplicated 文件出现重复稳定身份
→ 付费调用前直接失败
```

成功 checkpoint 身份绑定：

```text
platform
external_content_id
input_hash
prompt_sha256
taxonomy_sha256
model_provider
model
```

程序如果在最终业务 JSONL `os.replace` 前崩溃，下一次执行会读取成功 checkpoint，不会再次调用已经 durable 成功的内容。

需要注意一个外部 API 客观边界：如果模型服务端已经执行请求，但响应在网络途中丢失，而 Provider 没有提供业务幂等键，客户端无法证明该请求是否已执行。程序能保证只接受一个合法 Analysis，并通过 checkpoint 把重复窗口缩到最小。

## 9. 每次运行的目录

直接运行：

```powershell
D:\python314\python.exe E:\work\03_Aima\code\AIMA_UGC\backend\src\aima_ugc\adapters\providers\imports_test\test.py
```

会调用：

```text
run_all()
```

每次自动创建独立目录：

```text
output/
└─ runs/
   └─ <run-id>/
      ├─ canonical/
      │  ├─ contents.jsonl
      │  └─ conversion_summary.json
      ├─ filtered/
      │  └─ contents.jsonl
      ├─ deduplicated/
      │  └─ contents.jsonl
      ├─ analysis/
      │  ├─ checkpoints.jsonl
      │  ├─ attempts.jsonl
      │  ├─ llm_requests.jsonl
      │  └─ failed.jsonl
      ├─ labeled_data.xlsx
      ├─ reports/
      │  ├─ report.md
      │  └─ report.docx
      └─ run_summary.json
```

默认 run ID 是带 `+0800` 的北京时间。不同 run 不互相覆盖；重复使用同一 run ID 会直接 `FileExistsError`。

`run_summary.json` 中 Analysis 摘要包括：

```text
rows_seen
rows_already_labeled
rows_recovered
rows_succeeded
rows_failed
llm_attempts
peak_in_flight
llm_http_requests
transport_retries
llm_request_audit_path
llm_calculated_http_requests
llm_uncalculated_http_requests
llm_input_tokens
llm_input_cache_hit_tokens
llm_input_cache_miss_tokens
llm_output_tokens
llm_total_cost_amount
llm_cost_currency
```

这些字段可以用来确认实际请求量、重试量、并发峰值和本次 run 的可计算费用。

报告完成后，`run_summary.json` 顶层还会增加：

```text
report_markdown
report_word
report_date_range
```

`stages` 最后一项是 `generate_report`，包含周期内的内容、标签、评论行数、报告日期范围、
周期外排除行数和 Word 图表数量。

费用公式：

```text
普通模型费用
= input_tokens × input_per_million / 1,000,000
+ output_tokens × output_per_million_tokens / 1,000,000

缓存拆分模型费用
= cache_hit_tokens × input_cache_hit_per_million_tokens / 1,000,000
+ cache_miss_tokens × input_cache_miss_per_million_tokens / 1,000,000
+ output_tokens × output_per_million_tokens / 1,000,000
```

公式中的单价是系统按该物理 HTTP 请求 `started_at` 选中的价格时段，不是 run 启动时一次固定的
价格，也不是生成汇总时的当前价格。

`analysis/llm_requests.jsonl` 一行对应一个物理 HTTP 请求，包含空 `content`、Validation Retry
和 Transport Retry，保存 token 分类、实际使用的单价、价格来源、自动快照哈希与计算费用；
不保存 Prompt、标题、正文、作者或 Provider 响应正文。`attempts.jsonl` 仍表示逻辑 Validation
Attempt，两者不能混为一个计数。

本地结果是按官方单价和 Provider 返回 usage 得到的可复算计算值，不是供应商账单。如果服务端
已经处理请求但响应在网络中丢失，本地拿不到 usage，会把该请求记为费用未知；最终扣款仍以
供应商账单为准。

## 10. 单步运行

```python
run_dir = prepare_run_dir()

convert(run_dir=run_dir)
filter_keywords(run_dir=run_dir)
deduplicate(run_dir=run_dir)

# 可选：显式写入 PostgreSQL；默认不调用。
ingest_database(run_dir=run_dir)

label_sentiment(run_dir=run_dir)
export_labeled_excel(run_dir=run_dir)
generate_report(run_dir=run_dir, report_date_range=REPORT_DATE_RANGE)

# 可选：价格目录变化后生成派生复算报告；不覆盖原请求审计。
recalculate_cost(run_dir=run_dir)
```

依赖上一步产物的函数必须传同一个 `run_dir`。`run_all(write_to_database=True)` 会在去重完成后、AI 打标前执行同一个 `ingest_database()` 正式数据库阶段；报告始终位于最终 Excel 之后。

复算输出为 `analysis/cost_recalculation.json`。它读取原始 token 事实并使用当前
`pricing.toml` 计算，不修改 `llm_requests.jsonl`、checkpoint、标签或业务 JSONL。用新价格复算
旧请求只能解释为“按新价格模拟重估”，不能改写成调用当时的实际费用；本功能上线前的历史
attempt 没有缓存拆分 token，无法准确补算。

## 11. AI 多标签与 Excel

每条内容一个整体情感：

```text
正面 / 中性 / 负面 / 混合
```

并允许一个或多个标签对：

```text
骑行性能 / 舒适性
售后服务 / 客服与服务态度
```

最终 Workbook：

```text
内容
标签明细
评论
```

“内容”Sheet 保持一条内容一行；多个一级/二级标签在各自单元格内换行，并按标签对顺序对应。

“标签明细”Sheet 直接从同一个归一化 `UnifiedContentRecordV1` 的内容事实和 Analysis 标签对派生，一个标签对一行，适合直接使用 Excel 普通筛选。例如同一内容同时属于两个一级标签，在两个标签各自筛选时都会出现。

“内容ID”是归一化记录的 `external_content_id` 的展示列，不是导出时临时创建的数据库内部 ID。隐藏该列只改变 Excel 展示，不影响内容、标签明细和评论的关联。

统计帖子总数以“内容”Sheet 为准；做标签筛选/频次/组合统计使用“标签明细”Sheet。

## 12. Excel 格式

共享 Exporter 统一负责：

- 冻结首行 `A2`；
- 首行自动筛选；
- 表头背景 `#FFC000`；
- Calibri 11pt，表头粗体；
- 表头行高 16.5，正文默认行高 14.5；
- “内容”和“标签明细”显示“二级标签”时，按该单元格的换行和显示宽度设置 14.5–409 的确定性行高并自动换行；隐藏该列时不设置数据行高度；
- 显示网格线；
- 不合并单元格；
- HTTP/HTTPS 链接可点击；
- 多标签单元格换行；
- 固定有界列宽；
- `openpyxl write_only=True` 流式写出。

## 13. 源 Excel 要求

工作表选择：

```text
SHEET_NAME = None
→ 扫描所有 Sheet
→ “文章”符合表头要求时优先选择
→ 否则选择唯一符合要求的 Sheet
→ 多个非默认 Sheet 同时符合时拒绝猜测，需要显式配置 SHEET_NAME

SHEET_NAME = "具体 Sheet 名"
→ 只校验和读取指定 Sheet，不自动切换
```

Profile：

```text
aima-monitoring-excel.v1
```

只强制校验生成平台、标题、正文、作者、发布时间和内容链接所需的 6 个源表头：

```text
媒体名称（中文）
标题
内文
作者
出版日期
原文链接
```

它们分别映射为“平台 / 标题 / 正文 / 作者 / 发布时间 / 内容链接”。这里校验的是第一行列名是否存在，不新增“每个单元格都必须非空”的规则。

“文章编号”和“粉丝数”存在时仍会按现有 Mapper 使用，但不是 Sheet 资格的必需列。序号、监测项名称、版面、媒体类型和全文情感等无关列可缺失，额外列也允许存在；无关列即使重名也不阻断导入，只有 6 个必需列自身重名才会因语义歧义报错。导入器不读取或校验字体、字号、颜色、边框和其他视觉样式。

部分来源工具会把 XLSX 的 Worksheet dimension 错写为 `A1:A1`。Reader 在流式读取前会重置这个不可信元数据，再以实际首行表头判断 Sheet，不会因错误范围只看到 A 列。

无法映射的平台、非法日期/粉丝数、缺稳定身份等都会 fail closed，不发布半份 canonical 业务 JSONL。

多文件还要求每个输入 Excel 的文件名唯一。`canonical/conversion_summary.json` 保存本次实际输入
路径和各文件行数，使后续单步数据库入库不依赖再次手工传入行数。

## 14. 常见排错

- **HTTP 401**：API Key/认证失败；canary 后立即停止，不会扩到 250。
- **HTTP 402**：模型服务余额不足；立即停止。
- **HTTP 429**：进入有界 Transport Retry；持续超过限制时停止新调度，保留成功 checkpoint。
- **HTTP 5xx / 网络错误**：按 Transport Retry 处理。
- **HTTP 200 但 `message.content` 为空**：Provider 的 JSON Output 偶发空结果按 Transport Retry 处理；超过限制仍停止新调度，避免无限调用和费用失控。
- **标签校验失败**：查看 `analysis/attempts.jsonl` 和 `analysis/failed.jsonl`。
- **程序中途终止**：不要删除 `analysis/checkpoints.jsonl`；修复问题后在同一 run 上继续 `label_sentiment(run_dir=...)` 可恢复成功项。
- **费用不可计算**：查看 `analysis/llm_requests.jsonl` 的 `cost.unavailable_reason`；通常是价格目录没有对应模型、usage 缺字段或网络未返回响应。
- **费用复算**：更新官方单价后调用 `recalculate_cost(run_dir=...)`；它生成派生报告，不覆盖历史单价快照。
- **多 Excel 文件名重复**：重命名文件使 basename 唯一；系统不会用绝对路径污染 Canonical 来源字段来绕过冲突。
- **未找到符合要求的 Sheet**：根据错误中列出的 Sheet 和缺失列，确认首行包含 6 个必需源表头；样式不会导致该错误。
- **自动发现到多个 Sheet**：把 `SHEET_NAME` 改为要使用的精确 Sheet 名，避免系统猜测业务页。
- **run_id 已存在**：不要覆盖旧 run，使用新 run ID。
- **词包为空**：检查 `KEYWORD_PACK_FILE` 是否正确、文件是否只剩注释和空行。
- **数据库连接失败**：只影响显式数据库阶段；已经生成的 Canonical/filtered/deduplicated 文件保留。启动既定 PostgreSQL 18 开发实例并修复 `AIMA_DB_*` / Secret 配置后重试，不要让脚本自动管理容器。
- **Stage 8A Schema 不匹配**：先由开发者显式运行仓库 Alembic Migration，再重试；`imports_test` 自身不会执行 Migration。
- **报告缺少必要列**：恢复最终 Excel 的默认报告依赖列，不要让报告层猜测或伪造统计字段。
- **Word 转换提示不支持 Mermaid**：当前只支持本报告使用的 `pie` 和 `xychart`；新增类型前先扩展转换器和测试。

## 15. 未来正式网页关键词配置

当前 `keyword_pack.txt` 只是本地人工入口配置来源。正式系统已经有 PostgreSQL：

```text
keyword_packs
keywords
keyword_pack_items
```

未来开发关键词管理 API/前端页面前，仍必须明确：

1. 采集发现词包和结果相关性清洗词包是否使用相同角色；
2. 真正车型俗称/别名是否建立“标准词 → 多别名”关系；
3. 正式数据库 `keywords.normalized_text` 的写入规范化算法和历史冲突处理。

当前本地 NFKC/casefold/去空白/连接符规则只定义离线清洗匹配，不自动成为数据库唯一键 Contract。

## 16. 稳定身份去重规则

过滤后的统一记录按以下身份去重：

```text
(platform, external_content_id)
```

该规则对小红书、抖音、微博、B站、快手和后续合法平台一致生效：

- 同一身份只输出源文件中首次出现的一条记录；
- 后续完全等价记录直接计入 `duplicates_removed`；
- 后续记录即使正文、发布时间、来源文章编号或其他业务字段不同，也仍计入
  `duplicates_removed`，不会再次进入 LLM；
- 非等价重复同时写入 `deduplicated/deduplication_conflicts.jsonl`，记录首次行、
  丢弃行和差异字段，作为数据质量审计，但不再中止任务；
- 去重不会按字段拼接记录，也不会根据发布时间、文本长度或平台私有规律猜测哪条更正确。

因此最终 `deduplicated/contents.jsonl` 和 Excel 中同一平台的同一内容最多出现一次，代表记录及
输出顺序由源文件首次出现顺序确定。

## 17. Stage 8A 可选数据库写入（已实现）

Stage 8A 已保留 `imports_test` 的默认 file-only 行为，并实现显式 PostgreSQL 入库：

```text
默认：WRITE_TO_DATABASE = False
→ convert / filter / deduplicate 按原行为生成文件
→ 不装配数据库 Runtime
→ 不要求 PostgreSQL

显式：run_all(write_to_database=True)
或在同一 run 上单独调用 ingest_database(run_dir=...)
→ 原始 XLSX 先通过 ArtifactService 保存为 Input Artifact
→ 建立 Processing / Import Batch
→ 建立 import-parent Provider Request + non-billable Attempt
→ Attempt 绑定该 Input Artifact 作为真实来源证据
→ 读取 deduplicated/contents.jsonl 中的 UnifiedContentRecordV1.content
→ 用真实 Request / Attempt / Artifact 补齐 Canonical Source
→ ContentIngestionService
→ PostgresCompleteContentRepository / PostgresContentRepository
→ PostgreSQL Current / Version / Metric / 来源历史
```

多 Excel run 在文件阶段先全局过滤和去重；显式数据库阶段再按保留下来的
`content.source.source_value` 分配记录，并为每个源 Excel 分别建立 Input Artifact、Processing
Import Batch 和 import-parent Request/Attempt。某个文件的记录如果全部在过滤/去重阶段被移除，
它仍有自己的成功 Import Batch，`rows_ingested=0`，不会把其他文件记录错误绑定到该 Artifact。
各源文件 Batch 按配置顺序独立提交；如果后一个 Batch 失败，前面已成功的 Batch 不回滚。修复原因后
可对同一 `run_dir` 重跑数据库阶段，正式内容身份与唯一约束会幂等收敛，不会制造第二条 Current。

数据库模式的前置条件：

- 开发者已经启动可访问的 PostgreSQL 18；
- `AIMA_DB_*` 与数据库密码 Secret 使用仓库正式配置；
- Schema 已由开发者通过正常 Alembic 流程升级到当前 head；
- 本调试入口**不**自动 `docker compose up/down`，**不**创建/删除数据库，**不**自动运行 Migration。

来源和兼容规则：

- 不制造假的 Collection Run/Scope/Candidate；Excel 使用真实 Input Artifact + Processing Import Batch + import-parent Request/Attempt；
- 不伪造 `provider_attempt_id/raw_artifact_id`，也不放松 Content Owner 的来源校验；
- 不建立 `ExcelDatabaseWriter` 或 `imports_test` 私有 Repository；
- Canonical 之后仍统一走正式 Content Ingestion；
- PostgreSQL 最终按 `(platform, external_content_id)` 做跨批次、跨来源收敛；重复导入不创建第二条 Current；
- 文件阶段已经写出的 Canonical/filtered/deduplicated 产物不会因数据库阶段失败被删除；数据库失败会直接向调用方抛错，不静默降级为“文件模式成功”；
- 修复数据库/Schema/输入后可重新执行数据库阶段，正式唯一约束和 Ingestion 保证业务 Current 幂等收敛。

注意：`run_all()` 的数据库阶段位于 AI 打标之前。如果数据库阶段失败，本次在它之前已经生成的文件会保留，但后续 AI/最终 labeled Excel/报告不会继续执行；需要保留并继续后续阶段时，修复问题后使用同一 `run_dir` 继续调用对应单步函数。

## 18. 报告生成、模板和 Word 转换

### 18.1 `run_all()` 自动生成什么

最终 Excel 成功后，`run_all()` 自动调用：

```python
generate_report(
    excel_path=run_dir / "labeled_data.xlsx",
    output_dir=run_dir / "reports",
    report_date_range=REPORT_DATE_RANGE,
)
```

生成：

```text
reports/report.md
reports/report.docx
```

报告不会再次调用 LLM，也不会写数据库。它只以 `labeled_data.xlsx` 为输入，统计后生成派生文件。

### 18.2 可以直接指定已经处理好的 Excel

不需要重跑 convert/filter/deduplicate/LLM：

```python
from datetime import date
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import generate_report

result = generate_report(
    excel_path=Path(r"E:\path\to\labeled_data.xlsx"),
    output_dir=Path(r"E:\path\to\reports"),
    report_date_range=(date(2026, 8, 13), date(2026, 8, 19)),
)

print(result.markdown_path)
print(result.word_path)
```

`output_dir` 可以省略。省略时，显式 Excel 的报告默认写到该 Excel 同目录下的 `reports/`。
`report_date_range` 是包含首尾日期的闭区间；传 `None` 时保持原有全量报告行为。

如果使用本目录的 `generate_report.py`，直接修改文件顶部的 `INPUT_EXCEL` 和
`REPORT_DATE_RANGE`。脚本按周期写入 `output/reports/YYYYMMDD-YYYYMMDD/`，避免不同周期
报告互相覆盖；全量报告写入 `output/reports/all/`。

### 18.3 报告统计内容

默认模板展示：

- 内容总量、评论总量、标签对总量、平台数、一级/二级标签数、日期范围；
- 每个平台内容量、占比、评论量；
- 各平台每日内容量；
- 情感分布与每日趋势；
- 全部一级标签数量/占比及每日趋势；
- 全部二级标签数量/占比及每日趋势；
- 完整一级 → 二级标签对数量；
- 命中关键词数量/占比；
- 报告依赖字段的缺失、时间解析和一级/二级标签行数一致性检查。

统计口径：

```text
内容总量、平台、情感、每日趋势、关键词
→ “内容” Sheet

一级/二级标签总体频次、标签对频次
→ “标签明细” Sheet

评论总量、各平台评论量
→ “评论” Sheet
```

指定 `report_date_range` 后：

```text
内容 → 按“发布时间”筛选
标签明细 → 优先按“发布时间”筛选；旧版表格可用两页“内容ID”关联
评论 → 按“评论时间”筛选
```

指定周期时，参与筛选的日期缺失或无法解析会明确失败；“内容”和“标签明细”在周期内的
标签记录数、平台、情感、一级/二级标签和标签对必须完全一致，否则拒绝生成报告。周期外
排除数量进入报告数据质量表，不会混入任何统计或图表。

完整统计始终保留在 Markdown 表格里。一级/二级标签折线图和 Top 图为了可读性限制展示序列数量，但不会删除表格中的完整数据。

### 18.4 只维护 Markdown 模板

报告正文模板只有：

```text
backend/src/aima_ugc/platform/reporting/report_template.md
```

固定链路：

```text
report_template.md
→ 填充统计值
→ report.md
→ Word 转换器读取 report.md
→ report.docx
```

因此修改模板正文、标题或章节顺序后，下一次 Markdown 和 Word 会一起变化。不得再维护一份平行 Word 正文模板。

### 18.5 Mermaid 与 Word 图表

Markdown 当前使用 Mermaid `pie` 与 `xychart-beta`，分别承载饼图、柱状图和折线图。Word
转换器同时兼容历史 `xychart` 输入，解析模板实际使用的两类 Mermaid，写入 Office 原生
Chart，并为每张图内嵌对应的 XLSX 数据；图表数据与 Markdown 使用同一份统计结果。Word
中的所有饼图百分比固定显示小数点后两位。

统一 Excel 和报告只在展示层把 `xiaohongshu`、`douyin`、`weibo`、`bilibili`、
`kuaishou` 显示为“小红书”“抖音”“微博”“哔哩哔哩”“快手”；Canonical JSONL、
分析输入和数据库仍使用英文稳定平台 ID。未知平台保持原值，不因缺少展示映射而丢失。

运行时不依赖 Mermaid 在线服务、Pandoc、LibreOffice、Matplotlib、pandas 或额外 Python 文档库。当前 Word 转换器不是通用 Markdown/Mermaid 排版引擎；模板如果加入未支持的 Mermaid 类型会明确失败，不会静默生成缺图 Word。

### 18.6 失败边界

- 报告使用只读方式打开输入 Excel；
- 不对输入 Workbook 保存、修复或二次格式化；
- 报告失败会向调用方抛错，不能把 `run_all()` 伪装成完整成功；
- 已经成功生成的 `labeled_data.xlsx` 不会因报告失败被删除或回滚；
- 修复模板或输入后，可以直接对同一个 Excel 重新调用 `generate_report(...)`。


## AI 语义相关性与发声类型

`label_sentiment()` 复用正式 `ContentLabelingService`，每条内容一次 LLM 请求同时完成相关性、发声类型、情感和多标签判断。判定为 `irrelevant` 的完整内容行会在最终原子回写时从 `deduplicated/contents.jsonl` 删除；checkpoint 仅保留最小恢复决策，不作为业务数据源。最终 Excel 不显示“相关性”列，发声分类只显示中文“发声类型”。
