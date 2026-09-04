# 全平台共享 LLM Adapter、计费与请求审计

这个目录负责的是**怎么可靠地调用外部文本模型**，而不是“爱玛内容应该打什么标签”。

如果把当前 AI 链路拆开：

```text
业务规则 / Prompt / Taxonomy / Validator
→ backend/src/aima_ugc/modules/analysis/

HTTP、usage、费用、Transport Retry、请求审计
→ backend/src/aima_ugc/adapters/llm/
```

这样做的目的很实际：以后把 DeepSeek 换成另一个 OpenAI-compatible 模型时，优先改 Adapter/配置，而不是复制一套舆情标签逻辑。

完整 AI 业务实现说明见：

- [`docs/appendix/07_AI舆情打标与分析实现.md`](../../../../../docs/appendix/07_AI舆情打标与分析实现.md)

## 1. 当前代码地图

| 文件 | 当前职责 | 修改它通常意味着什么 |
| --- | --- | --- |
| [`backend/src/aima_ugc/adapters/llm/openai_compatible.py`](openai_compatible.py) | 构造并发送一次 OpenAI-compatible Chat Completions 物理请求，解析响应/usage，形成请求审计 | 换兼容 Provider 协议、usage 解析、HTTP 错误语义 |
| [`backend/src/aima_ugc/adapters/llm/retrying.py`](retrying.py) | 在 Base Adapter 外显式做有界 Transport Retry；同一逻辑请求的多次物理请求共用 `logical_request_id` | 改网络重试条件/退避策略 |
| [`backend/src/aima_ugc/adapters/llm/pricing.py`](pricing.py) | 解析/校验价格目录，根据请求开始时间选价格时段，使用 `Decimal` 计算费用和价格快照 | 改计价公式或价格目录结构 |
| [`backend/src/aima_ugc/adapters/llm/pricing.toml`](pricing.toml) | 当前实际配置的模型官方价格事实 | 价格变化/新增模型 |
| [`backend/src/aima_ugc/adapters/llm/request_audit.py`](request_audit.py) | 定义物理 HTTP 请求审计、汇总和复算 | 改离线审计结构/费用汇总 |
| `README.md` | 解释上述边界和修改方法 | 不作为机器价格/协议事实源 |

精确导出符号看 [`backend/src/aima_ugc/adapters/llm/__init__.py`](__init__.py)；不要根据 README 猜类名。

## 2. 当前有两种真实装配方式

这套 Adapter 现在已经不是 `imports_test` 私有能力。

### 2.1 正式 PostgreSQL Analysis Job

生产链：

```text
POST /api/v1/content-analysis-requests
→ analysis_content_requests / items
→ analysis.content-label.v1 Job
→ bootstrap/analysis_concurrent_worker.py
→ ContentLabelingService
→ OpenAICompatibleContentLabelingLLM
→ Analysis Repository
```

正式装配位置：

- [`backend/src/aima_ugc/bootstrap/analysis_concurrent_worker.py`](../../bootstrap/analysis_concurrent_worker.py)

它从 `PlatformSettings` 读取非敏感模型配置，从：

```text
<AIMA_SECRET_DIR>/llm_api_key
```

读取 Secret，然后加载当前 Prompt/Taxonomy 和 [`backend/src/aima_ugc/adapters/llm/pricing.toml`](pricing.toml)。

正式 Analysis Job 的结果写入 `analysis_content_results` 等 Analysis 表；**token/cost 当前不会作为 Analysis Result 列写入数据库**。正式 Worker 当前把物理请求 usage/计算费用作为安全结构化日志审计字段输出。

### 2.2 离线 `imports_test` / JSONL Analysis

离线路径复用同一个业务 Service 和 LLM Adapter，但会额外维护：

```text
analysis/checkpoints.jsonl
analysis/attempts.jsonl
analysis/llm_requests.jsonl
analysis/failed.jsonl
```

这套文件用于大批量离线任务的崩溃恢复、物理请求计数和费用复算，不代表数据库 Analysis 表已经保存相同字段。

所以：

```text
共享 LLM Adapter
≠ imports_test 专用代码
≠ Analysis 数据库 Owner
```

## 3. 一次 `complete()` 为什么必须只有一次 HTTP 发送

[`backend/src/aima_ugc/adapters/llm/openai_compatible.py`](openai_compatible.py) 的重要边界是：

> 一次 Base Adapter 调用只做一次物理 HTTP 请求，不在底层偷偷重试网络。

原因是每次真实外部发送都有：

- 费用；
- usage；
- request ID；
- “Provider 可能已经处理但响应丢失”的不确定性。

如果 Base Adapter 内部静默重发，上层就无法准确知道实际发了几次请求。

需要重试时由 [`backend/src/aima_ugc/adapters/llm/retrying.py`](retrying.py) 显式建立：

```text
一个逻辑 LLM 请求
→ 物理请求 #1
→ 可恢复 Transport 错误
→ 物理请求 #2
→ ...
```

每个物理请求都进入请求审计。

这和 Analysis 的 **Validation Retry** 是两回事：

```text
Transport Retry
→ 网络/HTTP 层没有稳定完成

Validation Retry
→ HTTP 已成功，但模型 JSON/标签没有通过本地 Validator
```

不要把两个计数器合并。

## 4. 当前哪些 Transport 错误可重试

精确错误分类以 [`backend/src/aima_ugc/adapters/llm/retrying.py`](retrying.py) 和 [`backend/src/aima_ugc/adapters/llm/openai_compatible.py`](openai_compatible.py) 为准。当前长期原则是：

- 网络连接/超时类错误可以进入显式重试；
- 408、429、部分 5xx 可以重试；
- 认证、权限、请求参数、模型不存在等确定性 4xx 不应通过网络 Retry 反复烧请求；
- Provider 返回 2xx 但协议/业务内容非法，由 Analysis Validator/协议层处理，不伪装成网络失败。

改这个规则时至少同时检查：

```text
retrying.py
openai_compatible.py
request_audit.py
modules/analysis/content_labeling.py
相关 unit tests
AI 附录
```

## 5. 当前价格目录

机器事实：

- [`backend/src/aima_ugc/adapters/llm/pricing.toml`](pricing.toml)

当前配置项是：

```text
provider = api.deepseek.com
model = deepseek-v4-pro
currency = CNY
```

DeepSeek 当前官方价格页对 `deepseek-v4-pro` 使用北京时间分时价格。仓库在 `[[models.price_periods]]` 中配置 `off_peak / peak`：高峰仅适用于周一至周五 `09:00-12:00`、`14:00-18:00`（`Asia/Shanghai`），其余日期和时段使用空闲价。

当前正式字段使用供应商价格语义：

```text
input_cache_hit_per_million_tokens
input_cache_miss_per_million_tokens
output_per_million_tokens
```

### 5.1 当前人类可读价格快照

下面这张表是为了让开发者快速估算一次运行的大致费用；**运行时不会读取 README，真正计费只读取 [`backend/src/aima_ugc/adapters/llm/pricing.toml`](pricing.toml)。** 如果 TOML 发生价格变更，这张表也必须在同一任务同步，否则宁可删表也不能长期保留过期报价。

当前 [`backend/src/aima_ugc/adapters/llm/pricing.toml`](pricing.toml) 对应 DeepSeek V4-Pro 官方人民币价格：

| 官方价格项 | 空闲时段 | 高峰时段 |
| --- | ---: | ---: |
| 输入（缓存命中），每百万 tokens | `0.15 CNY` | `0.30 CNY` |
| 输入（缓存未命中），每百万 tokens | `4.5 CNY` | `9.0 CNY` |
| 输出，每百万 tokens | `13.5 CNY` | `27.0 CNY` |

高峰时段按北京时间计算，仅周一至周五 `09:00-12:00`、`14:00-18:00`；其余为 `off_peak`。

价格来源：

```text
https://api-docs.deepseek.com/zh-cn/quick_start/pricing/
```

`effective_date` 表示**这份价格配置从哪一天起在 AIMA 价格目录中生效**，不是对“供应商首次从哪一天开始执行该价格”的猜测。本次同步设置为 `2026-08-24`；DeepSeek 当前价格页没有为这组价格单独声明另一个价格生效日期。

运行时 `price_for()` 按请求 `started_at` 的 **UTC 日期**检查 `effective_date`。请求早于该日期时，这份价格被视为“该时点不可用”，不会把未来价格套到历史请求。正式 Adapter 仍继续发送 LLM 请求，只把本次费用记为不可计算；离线成本复算同样会把该请求标为 unavailable，除非调用方提供覆盖该历史时点的价格目录。

### 5.2 配置与历史兼容

旧配置字段：

```text
input_cache_hit_per_million
input_cache_miss_per_million
output_per_million
```

仅作为兼容读取路径；新配置不能继续使用旧名字。历史 `llm-http-request.v1` 审计结构中的旧键名如果属于已发布格式，则按兼容规则保留，不能因为价格配置字段改名就静默改历史审计格式。

## 6. 一次费用怎么计算

当前支持的文本模型计价大体有两种：

```text
普通输入 tokens + 输出 tokens
```

或：

```text
缓存命中输入 tokens
+ 缓存未命中输入 tokens
+ 输出 tokens
```

真正使用哪一种由当前价格项和 Provider usage 决定。

费用计算使用 `Decimal`，避免用 float 做货币计算。每个物理请求冻结：

- provider/model；
- started_at；
- usage；
- 实际选中的价格时段/单价；
- currency；
- 官方来源 URL；
- 规范化价格内容 SHA-256；
- 计算费用或“为什么不可计算”。

如果模型没有配置价格，或者 Provider usage 缺少当前公式必须的分类：

```text
业务 Analysis 可以按既有错误/成功语义继续
费用 = 明确不可计算
```

不能拿另一个模型的默认价格猜。

## 7. 请求审计到底记录什么

离线 `llm_requests.jsonl` 一行对应一次物理 HTTP 请求，包括：

- logical/http request ID；
- provider/model；
- 开始/完成时间；
- HTTP/协议结果；
- usage；
- 冻结单价；
- 价格来源和快照；
- 计算费用/不可计算原因。

它**不保存**：

- Prompt 原文；
- 标题/正文；
- 作者信息；
- API Key；
- Provider 完整响应正文。

服务端已经处理请求、但响应在网络中丢失时，本地拿不到权威 usage。这种请求的成本只能标记未知，不能为了报表好看猜一个数字。

## 8. 复算费用是什么意思

`recalculate_llm_request_costs()` 可以读取历史物理请求的 token/时间，按另一套当前价格目录计算一个**派生重估报告**。

它不能覆盖：

- 原始请求审计；
- 当时使用的冻结价格；
- checkpoint；
- Analysis 结果。

因此：

```text
“按今天价格重算历史 token”
```

只能解释为模拟重估，不是“历史请求当时实际应该收费多少”的新事实。

## 9. 要换模型时改什么

### 只换同协议模型 ID / Base URL

先确认 Provider 仍兼容当前 OpenAI-compatible 协议，再检查：

```text
PlatformSettings / env 配置
<AIMA_SECRET_DIR>/llm_api_key
pricing.toml
正式 Analysis Worker
目标模型真实 smoke/probe
```

不要把 model ID 硬编码进 Analysis Service。

### 新模型仍是 OpenAI-compatible，但 usage 不同

重点看：

- [`backend/src/aima_ugc/adapters/llm/openai_compatible.py`](openai_compatible.py)
- [`backend/src/aima_ugc/adapters/llm/request_audit.py`](request_audit.py)
- [`backend/src/aima_ugc/adapters/llm/pricing.py`](pricing.py)
- [`backend/src/aima_ugc/adapters/llm/pricing.toml`](pricing.toml)


先通过真实脱敏响应证明 usage 结构，再扩展解析；不要假定所有 Provider 都返回同一 token 字段。

### 模型计价不是文本 token

例如图片、音频、按请求、阶梯包月等，如果无法用当前文本公式表达：

> 扩展共享计费模型，而不是把非文本费用硬塞进 input/output token 字段。

这属于 Contract/业务审计语义变化，需独立 Change。

## 10. 要改价格时怎么做

普通价格变更不需要改 Python 公式时：

```text
1. 用供应商官方价格页确认精确模型 ID、币种和价格
2. 修改 pricing.toml 对应 provider + model
3. 保留/更新 source_url
4. 根据真实 AIMA 目录生效语义设置 effective_date，不把它冒充供应商未公布的调价日期
5. 如果有分时价格，确认 IANA timezone 和 [start, end) 边界
6. 跑 pricing / request audit 相关测试
7. 检查本 README 的人类可读快照和 AI 附录是否受影响
```

## 11. 排障顺序

### 正式 Analysis 一提交就失败

```text
PlatformSettings 的 LLM base_url/provider/model
→ <AIMA_SECRET_DIR>/llm_api_key
→ bootstrap/analysis_concurrent_worker.py
→ openai_compatible.py 错误分类
→ worker.log 中 analysis.llm_request_completed / Job 终态
```

### 离线任务模型请求数异常

```text
offline_labeling.py
→ attempts.jsonl（逻辑 Validation Attempt）
→ llm_requests.jsonl（物理 HTTP 请求）
→ retrying.py
→ failed/checkpoint
```

### 金额算不出来

```text
pricing.toml 是否精确匹配 provider + model
→ Provider usage 是否包含计价必需字段
→ request_audit.py 的不可计算原因
```

不要先加“默认单价”掩盖缺失配置。

## 12. 测试和验证

重点测试位置：

```text
tests/unit/analysis/
tests/unit/platform/        # LLM 价格/审计/离线相关按实际文件分布
tests/integration/content/  # 正式 Analysis 纵切由当前测试事实决定
```

定位某个行为时直接在 `tests/` 搜索对应类/函数名，不依赖 README 维护一份永远准确的测试文件清单。

完整 AI 业务规则和 PostgreSQL Analysis 路径见：

- [`docs/appendix/07_AI舆情打标与分析实现.md`](../../../../../docs/appendix/07_AI舆情打标与分析实现.md)
- [`backend/src/aima_ugc/modules/analysis/README.md`](../../modules/analysis/README.md)

## 13. 不要在这里做什么

- 不在 Adapter 里维护爱玛标签 taxonomy；
- 不根据平台写五套模型调用；
- 不在 HTTP Adapter 里决定 relevant/irrelevant；
- 不在 [`backend/src/aima_ugc/adapters/llm/pricing.toml`](pricing.toml) 保存 Secret；
- 不隐藏 Transport Retry；
- 不让请求审计保存 Prompt/用户完整正文；
- 不把计算金额冒充供应商最终账单；
- 不把离线文件审计误写成 Analysis 数据库字段。
