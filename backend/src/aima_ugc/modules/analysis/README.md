# Analysis 模块

`aima_ugc.modules.analysis` 是平台无关的舆情内容分析能力。Canonical 只保存外部可观察事实，AI 情感和一级/二级标签属于后置 Analysis；文件导入、TikHub 和未来其他 Provider 都必须复用同一 Prompt、Taxonomy、Validator、Service 和 LLM Port。

## 1. 数据边界

统一处理记录：

```text
UnifiedContentRecordV1
= CanonicalContentV1
+ matched_keywords
+ analysis
```

当前新成功结果使用：

```text
ContentLabelAnalysisV2
```

每条结果：

- 恰好一个 `sentiment`；
- 至少一个 `labels` 标签对；
- 每个标签对保存 `primary_label + secondary_label`；
- 同一条内容可以有多个一级、多个二级标签；
- 二级标签始终和所属一级一起保存，父子关系不会丢失。

历史 `ContentLabelAnalysisV1` 只保留读取兼容。Canonical、Analysis V2 Contract 和 Excel Contract 不因为并发执行方式改变。

## 2. Prompt / Taxonomy

唯一 Prompt/Taxonomy 事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v2.md
```

具体情感标签、一级/二级标签、父子关系、判断标准和示例都只维护在该 Markdown。Python 只约束结构和合法性，不复制第二套业务标签枚举。

`PromptTaxonomyLoader` 会：

```text
读取完整 Markdown
→ 提取机器 Taxonomy JSON
→ 校验结构
→ 计算 prompt_sha256
→ 计算 taxonomy_sha256
```

真实离线 run 开始时只读取/解析一次 Prompt，然后使用 `FrozenPromptTaxonomyLoader` 把这一份不可变快照复用给整个 run。这样既避免 9 万条内容重复读取文件，也避免运行几小时期间 Prompt 文件被改动后同一 run 出现两套标签口径。

## 3. 发给模型的业务字段

`ContentLabelingService` 从 Canonical 只投影：

```text
title
text
author.display_name
```

不会发送内容 ID、URL、互动指标、Provider 私有字段、Raw 定位或源 Excel 情感。

Service 本身仍支持 `Sequence[CanonicalContentV1]`，便于测试和后续正式业务复用；但当前 `imports_test` 的真实模型离线路径固定为：

```text
1 条内容
→ 1 次 ContentLabelingService 调用
→ 1 个 ContentLabelingLLMRequest
→ 1 次 DeepSeek/OpenAI-compatible HTTP 请求
```

因此当前离线执行不存在“20 条内容拼成一个模型请求”的行为。

## 4. Validation Retry

模型 HTTP 成功后仍必须经过本地 Validator。Validator 检查：

- JSON 结构；
- item 对应；
- sentiment 合法；
- labels 非空；
- 标签对不重复；
- 一级标签存在；
- 二级标签属于对应一级。

`max_validation_retries` 表示**模型已经成功返回 HTTP 响应，但结果未通过本地校验**后的额外重试次数：

```text
0 = 最多请求 1 次
1 = 最多请求 2 次
2 = 最多请求 3 次
```

当前真实离线请求每次只有一条内容，所以某一条标签结构失败时，只重试这一条，不会导致其他已经成功的内容重新请求。

达到 Validation Retry 上限仍失败：

```text
analysis = null
→ 写 analysis/failed.jsonl
→ 继续处理其他内容
```

不猜测、不补造标签。

## 5. Transport Retry

真实 HTTP Base Adapter：

```text
backend/src/aima_ugc/adapters/llm/openai_compatible.py
```

它继续保持硬边界：

> 一次 `complete()` 恰好一次 HTTP 请求，不隐藏自动网络重试。

显式 Transport Retry 位于：

```text
backend/src/aima_ugc/adapters/llm/retrying.py
```

这样 Validation Retry 与网络 Retry 不会混为同一个计数器。

当前可恢复 Transport 错误：

```text
网络连接/超时类 httpx.HTTPError
HTTP 408
HTTP 429
HTTP 500
HTTP 502
HTTP 503
HTTP 504
```

使用有界指数退避 + jitter，当前人工入口默认：

```text
MAX_TRANSPORT_RETRIES = 4
```

也就是首次请求之外最多再尝试 4 次。

以下错误不会通过 Transport Retry 反复请求：

```text
HTTP 400
HTTP 401
HTTP 402
HTTP 403
HTTP 404
HTTP 422
以及 2xx 但响应协议本身非法
```

这类错误通常表示请求、认证、余额、权限、模型/参数或 Provider 协议需要人工修正。异常信息只保存状态和本地错误分类，不回显 API Key 或 Provider body。

如果可恢复 Transport 错误在当前内容上达到重试上限，当前离线 Analysis 阶段停止继续扩展新请求；此前已经 durable checkpoint 的成功内容不会丢失，修复网络/Provider 后重新运行会直接恢复这些成功项。这样避免 Provider 故障时继续向剩余数万条内容制造失败请求。

这里**没有预算上限、费用阈值或 Token 预算停止逻辑**。费用只作为外部模型调用的客观属性和可观察信息，不参与调度是否继续的判断。

## 6. 250 有界并发

当前离线生产入口：

```python
label_unified_content_jsonl(...)
```

默认：

```text
DEFAULT_OFFLINE_LLM_CONCURRENCY = 250
```

`imports_test` 显式使用：

```python
LLM_CONCURRENCY = 250
```

执行模型：

```text
deduplicated/contents.jsonl
        ↓
完整本地输入预检
        ↓
单条 canary 请求
        ↓
最多 250 个 in-flight Future
        ↓
任一完成立即补一个新任务
        ↓
checkpoint/attempt/failed 单协调线程写入
        ↓
全部模型阶段结束
        ↓
按原 JSONL 顺序第二遍回写
        ↓
os.replace 原子发布
```

关键点：

1. **单条请求**：每个 Worker 一次只处理一个 Content。
2. **滑动窗口**：最多只持有 `max_concurrency` 个 Future，不会一次创建 90,000 个 Future。
3. **没有批次屏障**：一个慢请求不会让其他 249 个槽位闲置；有完成项就继续补充。
4. **单写者**：Worker 只调用模型并返回结果；所有 audit/checkpoint 文件由主协调线程写，避免 250 线程争抢文件句柄和破坏 JSONL。
5. **共享 HTTP Client**：真实 OpenAI-compatible Adapter 复用同一个 `httpx.Client`，连接池 `max_connections` 和 `max_keepalive_connections` 与当前并发上限一致；不会为 9 万条内容重复创建 TLS Client。
6. **有界内存**：输入通过文件流扫描；除 checkpoint 索引、稳定身份预检集合和最多 250 个在飞任务外，不把 9 万条全部加载到任务列表。

旧内部 `batch_size` 参数暂时保留为兼容别名，只解释成并发上限；它不再控制“一个 HTTP 请求放多少条内容”。人工入口不再暴露 `LLM_BATCH_SIZE`。

## 7. 模型调用前全文件输入预检和 canary

并发开始前先完整扫描 `deduplicated/contents.jsonl`：

- 每行必须是合法 `UnifiedContentRecordV1`；
- 同一 `(platform, external_content_id)` 不允许在 deduplicated 文件重复；
- 已有 `analysis` 的内容直接跳过；
- 当前 Prompt/Taxonomy/Provider/Model/Input 全匹配的成功 checkpoint 标记为可恢复。

这个步骤只是**输入完整性和防重复检查**，不计算预算、不估算费用，也不会因为“花了多少钱”停止运行。

预检失败发生在第一次真实模型请求之前，避免处理到中途才发现输入结构有问题。

预检通过后，先只对第一条待处理内容做一个 canary。只有 canary 的模型链路可以正常工作，才创建 250 并发 Worker。因此 API Key 错误、余额/权限或请求配置错误不会在启动瞬间放大成 250 个无效请求。

## 8. 防重复和 checkpoint

成功恢复身份仍由以下事实共同决定：

```text
platform
external_content_id
input_hash
prompt_sha256
taxonomy_sha256
model_provider
model
```

其中 `input_hash` 只由允许发送给模型的 title/text/author 计算。

每条成功结果顺序：

```text
LLM 成功
→ 本地 Validator 成功
→ 追加 checkpoints.jsonl
→ flush + fsync
→ 才视为可恢复成功
```

业务 JSONL 不按并发完成顺序直接写。模型阶段结束后，程序重新顺序扫描原 `deduplicated/contents.jsonl`，使用成功 checkpoint 填回 Analysis，再写临时文件并 `os.replace`。因此：

- checkpoint 可以按 3、1、2 的完成顺序产生；
- 最终业务 JSONL 仍严格保持原始 1、2、3 行顺序；
- 程序在最终 `os.replace` 前崩溃时，重新运行会从 durable checkpoint 恢复，不重复请求已经成功持久化的内容。

已有业务 `analysis` 的记录同样直接跳过模型调用。

外部 HTTP 存在一个无法由客户端完全消除的边界：Provider 可能已经处理请求，但响应在网络途中丢失。没有 Provider 端幂等键时，客户端无法数学上证明该请求未执行；系统能保证的是只接受一个合法 Analysis，并通过成功 checkpoint 尽量缩小重复调用窗口。

## 9. audit 与运行指标

当前分析目录：

```text
analysis/checkpoints.jsonl
analysis/attempts.jsonl
analysis/llm_requests.jsonl
analysis/failed.jsonl
```

`attempts.jsonl` 表示逻辑 Validation Attempt；`llm_requests.jsonl` 表示真实物理 HTTP 请求。
一次 Validation Attempt 可能因为网络、429/可恢复 5xx 或空 `content` 产生多个物理请求，费用必须
按后者统计，不能只看最终成功响应。

物理请求审计不保存 Prompt、标题、正文、作者或 Provider 响应正文，只保存：

```text
http_request_id / logical_request_id
provider / model
started_at / completed_at
HTTP/协议结果
input / cache-hit / cache-miss / output tokens
每百万 token 单价
官方价格来源 URL
自动价格快照 SHA-256
计算费用或不可计算原因
```

包内 `adapters/llm/pricing.toml` 是最小价格目录。它按 `provider + model` 精确匹配，不使用
跨模型默认单价；价格内容本身生成 SHA-256，因此不维护没有计算作用的人工生效时间或版本号。
一次 `label_sentiment()` 开始时只加载一次不可变价格目录，运行中的文件修改不会改变已发请求的
单价快照。

价格、物理请求审计和复算的 Owner 是平台无关的 `adapters/llm`，不是 `imports_test`。当前人工
入口只是第一个装配者；任何后续 Analysis Job 或其他内容来源都必须复用同一 Adapter 能力，不能
按小红书、抖音、微博、快手、哔哩哔哩或 Excel 分别复制计费代码。

当前支持两类文本 token 计价：

```text
input + output
cache-hit input + cache-miss input + output
```

模型未配置、usage 缺少计价必需分类或响应在网络中丢失时，标签处理保持原有语义，费用明确记为
不可计算。这里的金额是按官方单价与 Provider usage 得到的可复算计算值，不冒充供应商最终账单。
`imports_test.recalculate_cost()` 可以用当前价格目录生成独立派生报告，但不会覆盖原物理请求审计、
checkpoint 或标签；用新价格复算旧 token 只能作为模拟重估。

`OfflineContentLabelingSummary` 记录：

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
llm_calculated_http_requests
llm_uncalculated_http_requests
llm_input_tokens
llm_input_cache_hit_tokens
llm_input_cache_miss_tokens
llm_output_tokens
llm_total_cost_amount
llm_cost_currency
```

`imports_test/run_summary.json` 会把该 Summary 一起保存，便于判断本次是否真正跑到 250 并发、发生多少 Transport Retry、多少内容来自 checkpoint 恢复。

## 10. 独立验证

Fake/测试不访问真实模型，也不产生真实 API 调用。重点测试：

- 一条内容一次请求；
- 有界滑动窗口并发峰值；
- 乱序完成后业务 JSONL 顺序不变；
- 重复稳定身份在模型调用前失败；
- 401 canary 只产生一个请求；
- 429/503 有界 Transport Retry；
- 401/402/422 不做 Transport Retry；
- Validation Retry 只重试当前单条；
- checkpoint 在业务 JSONL 原子替换失败后仍可恢复；
- 已有 Analysis 不重复请求；
- 连接池真正配置到目标并发数。

常用命令：

```bash
uv run pytest tests/unit/analysis -q
uv run ruff check backend tests scripts
uv run mypy backend/src
```

真实模型 Probe 默认不进入普通 CI，也不能打印 Secret。

## 11. Stage 8D 正式 Analysis Persistence

Stage 8D 已在不改变离线入口的前提下建立正式数据库链路：

```text
Prompt/Taxonomy
→ ContentLabelingService
→ LLM Port
→ OpenAI-compatible Adapter
→ 显式 Transport Retry
→ 本地 Validator
→ ContentLabelAnalysisV2
→ Analysis Result + ordered Label Pair PostgreSQL Owner Repository
→ current Analysis Query Read Model
```

用户在声音广场显式选择内容或当前查询后，HTTP 会冻结 Content ID + Version 并创建
`analysis.content-label.v1` durable Job。Worker 分批复用正式 Service/Validator；成功结果与全部有序标签
在验证当前 Job Fencing Token 的短事务中提交。精确输入/配置身份重试复用现有结果；配置或输入变化保留
历史。默认 Import/Collection 不自动调用付费模型，Secret 不进 Job Payload、数据库或日志。
