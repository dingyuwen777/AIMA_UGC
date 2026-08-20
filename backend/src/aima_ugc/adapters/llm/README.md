# 全平台共享 LLM Adapter、计费与请求审计

本目录是系统外部文本 LLM 的共享 Adapter Owner，不属于 `imports_test`，也不依赖 Excel、TikHub
或任何内容平台。小红书、抖音、微博、快手、哔哩哔哩及后续来源只要进入统一 Analysis 调用链，
都复用这里的模型调用、token 计费与物理请求审计。

## 职责

| 文件 | 职责 |
| --- | --- |
| `openai_compatible.py` | 发送一次 OpenAI-compatible Chat Completions 物理请求，解析 usage 并计算该请求费用 |
| `retrying.py` | 显式执行有界 Transport Retry，并让同一逻辑请求的多次物理请求共享 `logical_request_id` |
| `pricing.py` | 校验通用文本模型价格目录，按请求开始时间选择价格时段，再用 `Decimal` 计算费用和自动价格快照 |
| `pricing.toml` | 保存当前实际使用模型的最小官方单价、时区与价格时段事实 |
| `request_audit.py` | 追加物理请求费用审计、汇总整个 run，并生成非覆盖式复算报告 |

Analysis 业务层只定义 `ContentLabelingLLMPort`、标签语义和 Validation Attempt，不依赖具体模型
供应商或价格文件。调用入口负责选择 Secret、模型和本次 run 的审计文件位置，再把共享价格目录与
审计 Writer 注入 Adapter。当前 `imports_test` 是第一个装配入口，不是这些能力的 Owner。

## 当前价格与以后换模型

现阶段 `pricing.toml` 只配置实际使用的 `api.deepseek.com / deepseek-v4-pro`。文件不保存 API Key
或人工价格版本；每项价格保存它在 AIMA 价格目录中的 `effective_date`。每个物理请求按
`started_at` 选择当时价格时段，并冻结实际采用的单价、官方来源 URL 和由规范化价格内容自动生成的
SHA-256；日期、时区和时段名不进入费用公式，也不改变相同价格事实的既有快照 Hash。

2026-08-20 直接核验 DeepSeek 官方价格页后，当前人民币价格为：

| 官方价格项 | 空闲时段 | 高峰时段 |
| --- | ---: | ---: |
| 输入（缓存命中），每百万 tokens | 0.15 CNY | 0.30 CNY |
| 输入（缓存未命中），每百万 tokens | 4.5 CNY | 9.0 CNY |
| 输出，每百万 tokens | 13.5 CNY | 27.0 CNY |

高峰时段为北京时间 09:00–12:00、14:00–18:00，区间按 `[start, end)` 解释；其余时间使用空闲
价格。因此 09:00、14:00 进入高峰，12:00、18:00 回到空闲。

一手来源：<https://api-docs.deepseek.com/zh-cn/quick_start/pricing/>。

以后换其他文本模型时：

1. 从供应商官方 API 文档确认 Base URL、精确模型 ID 和 usage 字段；
2. 从官方价格页确认币种、每百万 token 单价，以及是否存在时区和分时价格；
3. 在 `pricing.toml` 新增准确的 `provider + model` 项；
4. 只有全天固定价格时，直接在 `[[models]]` 下配置单价。存在分时价格时，配置模型的 IANA
   `timezone`，并在多个 `[[models.price_periods]]` 中使用同样的单价字段；无 `time_ranges` 的一项
   是全天默认价，其他项以 `HH:MM-HH:MM` 半开区间覆盖默认价，重叠区间会被拒绝；
5. 普通模型配置 `input_per_million + output_per_million_tokens`，缓存拆分模型配置
   `input_cache_hit_per_million_tokens + input_cache_miss_per_million_tokens +
   output_per_million_tokens`；
6. 配置 `effective_date = "YYYY-MM-DD"`。它表示该价格项在 AIMA 目录中的生效日期；供应商页面
   没有单独公布价格生效日时，不得把核验日写成供应商公告日；
7. 增加价格解析、时段边界、usage 映射和费用计算测试。

旧 TOML 的 `input_cache_hit_per_million`、`input_cache_miss_per_million` 和
`output_per_million` 仍可兼容读取，但会产生 `FutureWarning`；新配置和 `LLMModelPrice` 只使用包含
`per_million_tokens` 的正式字段。`llm-http-request.v1` 历史审计 JSON 继续保留旧键名，这是已发布
审计格式，不是新的价格配置 Schema。

若图片、音频、按请求或阶梯折扣不符合现有两种文本公式，必须先扩展共享计费维度，不能把它们
伪装成文本 token 价格。没有匹配价格或 usage 分类不足时，模型业务处理保持兼容，但费用明确标记
为不可计算，不使用其他模型的默认价格。

## 准确性边界

`llm_requests.jsonl` 一行对应一次物理 HTTP 请求，包含成功响应、空 `content` 后重试、协议错误和
Transport Retry；它不保存 Prompt、标题、正文、作者或 Provider 响应正文。汇总金额依据 Provider
返回 usage 与冻结单价计算，可复算但不冒充供应商最终账单。服务端已经处理而响应在网络中丢失时，
本地没有 usage，只能记录费用未知。

`recalculate_llm_request_costs()` 读取原物理请求审计的 `started_at`，按同一时区规则选价并写独立
派生报告，不覆盖历史审计、checkpoint 或标签。用新价格复算旧 token 只能解释为模拟重估，不能
改写调用当时的单价事实。
