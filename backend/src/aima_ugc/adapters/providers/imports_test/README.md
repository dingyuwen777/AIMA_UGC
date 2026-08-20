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
REPORT_TEMPLATE_FILE = Path(__file__).with_name("report_template.md")

SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"
WRITE_TO_DATABASE = False

ENABLE_REAL_LLM = False

# 一条内容 = 一次独立 LLM 请求；最多同时 250 个请求。
LLM_CONCURRENCY = 250

# HTTP/网络/429/可恢复 5xx 的额外重试次数。
MAX_TRANSPORT_RETRIES = 4

# HTTP 成功但模型 JSON/标签校验失败的额外重试次数。
MAX_VALIDATION_RETRIES = 2
```

Excel 输入只有 `INPUT_XLSX_FILES` 一个配置入口。它接受一个 `Path` 或非空的
`Path` 元组；空元组会在转换前报错，其他类型不受支持。

当前没有 `LLM_BATCH_SIZE` 配置。**不会把 20 条内容拼进一次模型请求。**

`LLM_CONCURRENCY = 250` 表示最大在飞 HTTP 请求数，不是每个请求包含 250 条数据。

多 Excel 固定采用：

```text
按 INPUT_XLSX_FILES 顺序读取
→ 合并到同一 canonical/contents.jsonl
→ 全局关键词过滤
→ 全局稳定身份去重
→ 一次 AI 打标阶段
→ 一个 labeled_data.xlsx
→ 一份 Markdown / Word 报告
```

同一稳定身份由配置中靠前文件的记录代表。不同目录下也不允许使用相同文件名，因为
Canonical `source_value` 使用文件名保存来源；文件名重复会在合并前直接失败，避免来源混淆。
任一文件出现坏行时，整个合并 Canonical JSONL 都不会发布。

## 2. 配置最终 Excel 列

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
    "情感标签",
    "一级标签",
    "二级标签",
)
```

元组顺序就是 Excel 列顺序。可以删除、增加或调整已有共享列；空配置、重复列或未知列会直接报错。

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

报告当前依赖最终 Excel 的以下内容列：`平台`、`发布时间`、`命中关键词`、`情感标签`、`一级标签`、`二级标签`。使用默认列可以直接生成报告；如果手工删除这些列，报告会明确拒绝，而不会猜测或伪造统计字段。

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
| `input_cache_hit_per_million` | 每百万缓存命中输入 token 单价 | 官方价格页和 API usage 定义 |
| `input_cache_miss_per_million` | 每百万缓存未命中输入 token 单价 | 官方价格页和 API usage 定义 |
| `output_per_million` | 每百万输出 token 单价 | 官方价格页 |
| `source_url` | 上述价格的官方依据 | 供应商官方价格页面，不使用二手报价 |

`schema_version` 只是 TOML 解析格式，正常换模型时不修改。代码根据规范化后的 provider、model、
币种、单价和来源 URL 自动计算价格快照 SHA-256，不需要手工维护 `pricing_version` 或
`effective_from`。

更换模型时只做两件事：

1. 把 `.env` 的 `AIMA_LLM_MODEL` 改为供应商官方模型 ID；
2. 如果 `pricing.toml` 还没有该 `provider + model`，按官方价格页增加一项并运行价格测试。

普通输入/输出两档计价，以及缓存命中/未命中/输出三档计价的文本模型可以直接配置。图片、
音频、按请求、阶梯折扣或其他 token 分类不能套用这个公式，需要先扩展计费维度和测试。
没有匹配价格或 API usage 缺少必要分类时，标签处理仍继续，但费用明确记为不可计算，不使用
默认价格猜测。

DeepSeek 当前价格和 usage 字段以以下官方页面为准：

- <https://api-docs.deepseek.com/zh-cn/quick_start/pricing/>
- <https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/>

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
```

`stages` 最后一项是 `generate_report`，包含本次报告读取的内容、标签、评论行数、日期范围和 Word 图表数量。

费用公式：

```text
普通模型费用
= input_tokens × input_per_million / 1,000,000
+ output_tokens × output_per_million / 1,000,000

缓存拆分模型费用
= cache_hit_tokens × cache_hit_price / 1,000,000
+ cache_miss_tokens × cache_miss_price / 1,000,000
+ output_tokens × output_price / 1,000,000
```

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
generate_report(run_dir=run_dir)

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

“标签明细”Sheet 一个标签对一行，适合直接使用 Excel 普通筛选。例如同一内容同时属于两个一级标签，在两个标签各自筛选时都会出现。

统计帖子总数以“内容”Sheet 为准；做标签筛选/频次/组合统计使用“标签明细”Sheet。

## 12. Excel 格式

共享 Exporter 统一负责：

- 冻结首行 `A2`；
- 首行自动筛选；
- 表头背景 `#FFC000`；
- Calibri 11pt，表头粗体；
- 表头行高 16.5，正文默认行高 14.5；
- 显示网格线；
- 不合并单元格；
- HTTP/HTTPS 链接可点击；
- 多标签单元格换行；
- 固定有界列宽；
- `openpyxl write_only=True` 流式写出。

## 13. 源 Excel 要求

默认 Sheet：

```text
文章
```

Profile：

```text
aima-monitoring-excel.v1
```

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
generate_report(run_dir=run_dir)
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
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import generate_report

result = generate_report(
    excel_path=Path(r"E:\path\to\labeled_data.xlsx"),
    output_dir=Path(r"E:\path\to\reports"),
)

print(result.markdown_path)
print(result.word_path)
```

`output_dir` 可以省略。省略时，显式 Excel 的报告默认写到该 Excel 同目录下的 `reports/`。

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

完整统计始终保留在 Markdown 表格里。一级/二级标签折线图和 Top 图为了可读性限制展示序列数量，但不会删除表格中的完整数据。

### 18.4 只维护 Markdown 模板

报告正文模板只有：

```text
backend/src/aima_ugc/adapters/providers/imports_test/report_template.md
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

Markdown 当前使用 Mermaid `pie` 与 `xychart`，分别承载饼图、柱状图和折线图。Word 转换器解析本模板实际使用的两类 Mermaid，把图表转换为 DOCX 内嵌 PNG，同时用 Word 表格保留完整中文图例和数据。

运行时不依赖 Mermaid 在线服务、Pandoc、LibreOffice、Matplotlib、pandas 或额外 Python 文档库。当前 Word 转换器不是通用 Markdown/Mermaid 排版引擎；模板如果加入未支持的 Mermaid 类型会明确失败，不会静默生成缺图 Word。

### 18.6 失败边界

- 报告使用只读方式打开输入 Excel；
- 不对输入 Workbook 保存、修复或二次格式化；
- 报告失败会向调用方抛错，不能把 `run_all()` 伪装成完整成功；
- 已经成功生成的 `labeled_data.xlsx` 不会因报告失败被删除或回滚；
- 修复模板或输入后，可以直接对同一个 Excel 重新调用 `generate_report(...)`。
