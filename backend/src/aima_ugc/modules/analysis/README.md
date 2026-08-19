# Analysis 模块

> 当前阶段：临时 P1 已闭环。Analysis 模块继续作为平台无关的正式业务能力，后续数据库/API/Job 接入必须复用这里的 Service、Port、Validator 与 Adapter 边界。

`aima_ugc.modules.analysis` 保存平台无关的内容处理与 AI 分析业务能力。当前已建立 Prompt/Taxonomy 运行时加载、本地 Validator、Analysis Service/Port、Fake、真实 OpenAI-compatible Adapter 的业务接线，以及离线 JSONL checkpoint/attempt/failed 审计、成功 Analysis 原子回写和 checkpoint 崩溃恢复。

## 1. 边界与业务事实源

`CanonicalContentV1` 只表示 Provider/平台可观察事实，不增加 AI 标签。筛选、去重和 AI 分析使用：

```text
UnifiedContentRecordV1
= content + matched_keywords + analysis
```

其中：

```text
analysis = null
或
ContentLabelAnalysisV2
```

P1 第一版不接数据库。AI 只读取并回写同一个：

```text
deduplicated/contents.jsonl
```

`analysis/checkpoints.jsonl`、`attempts.jsonl`、`failed.jsonl` 是恢复/费用安全/审计材料，不是第二业务事实源；最终业务消费者和最终 Excel 都读取回写后的 `deduplicated/contents.jsonl`。

## 2. Prompt / Taxonomy 唯一事实源

具体情感、一级标签、二级标签、一级/二级父子关系、覆盖内容、典型表达、边界规则、冲突优先级和示例只维护在：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v2.md
```

Prompt 中只有一个机器可读 Taxonomy JSON 区块：

````markdown
<!-- AIMA_TAXONOMY_START -->
```json
{...}
```
<!-- AIMA_TAXONOMY_END -->
````

`PromptTaxonomyLoader` 精确提取该 JSON 块，使用 `json.loads` 解析，并在任何模型调用前严格校验 schema、空值、重复值和父子结构。自然语言说明只用于模型理解，程序不会解析自然语言表格来猜标签闭集。

Python/Pydantic 只定义结构，不复制具体标签 Enum、Literal、父子关系常量或第二份 taxonomy JSON。因此仅增加、删除、重命名标签，调整父子关系或修改判断标准/示例时，只修改上述 Markdown；运行时 Validator 自动使用当前 Taxonomy。

Loader 同时计算：

- `taxonomy_sha256`：规范化机器 Taxonomy JSON 的 SHA-256；
- `prompt_sha256`：完整 Prompt Markdown UTF-8 内容的 SHA-256。

仅修改 Prompt 说明文字时只改变 `prompt_sha256`；修改机器 Taxonomy 时两个 Hash 都会随内容变化。

## 3. Analysis Contract

当前新成功结果是：

```text
ContentLabelAnalysisV2
```

当前成功结果使用：

```text
sentiment: str
labels: [
  {primary_label: str, secondary_label: str},
  ...
]
```

`sentiment` 恰好一个；`labels` 至少一个并允许多个。每个二级标签始终和所属一级标签成对保存，标签对不能重复。具体允许值仍由当前 `PromptTaxonomy` 动态校验，不写进 Python Enum/Literal。历史 `ContentLabelAnalysisV1` 保留只读兼容，新 Service 产生 `ContentLabelAnalysisV2`。

`ContentLabelAnalysisV2` 只表示**已经通过本地 Validator 的新成功结果**，`analysis_status` 固定为 `succeeded`；历史 `ContentLabelAnalysisV1` 具有相同成功语义。Validation Retry 达到上限仍失败时，不构造失败版 Analysis：Service 返回该 item 的 `analysis_status=failed`、`analysis=None` 和错误代码，离线编排把失败状态写入 `analysis/failed.jsonl`，业务 JSONL 中该记录仍保持 `analysis=null`。

## 4. 发给模型的最小业务输入

`ContentLabelingService` 从 `CanonicalContentV1` 只投影：

```text
title
text
author.display_name
```

缺失值统一填空字符串。批量请求额外带临时 `item_no` 做请求/响应配对；它不是业务字段。

不会发送内容 ID、平台 ID、URL、互动指标、粉丝数、Provider、`matched_keywords`、源 Excel 情感、Raw locator 或其他 Provider 私有字段。

## 5. 本地 Validator 与 Validation Retry

模型返回 JSON 后，即使 Adapter/Provider 使用 JSON mode 或 structured output，也不能跳过本地校验。Validator 检查：

- Prompt Taxonomy 本身合法；
- JSON 能否解析；
- 顶层和 item 固定字段是否正确、是否有额外字段；
- item 数量、顺序、唯一性与 `item_no` 配对；
- sentiment 必须是一个非空字符串；
- labels 必须是非空标签对数组；
- 标签对不能重复；
- 每个 primary 是否属于当前 Taxonomy；
- 每个 secondary 是否属于同一标签对中的 primary。

校验不做模糊匹配、近义标签替换或程序猜测填值。缺少必须字段、额外字段、item 缺失/重复/数量不一致、`item_no` 无法配对、未知 sentiment/一级标签、二级不属于一级、空 labels、重复标签对、未知标签、父子错配及其他结构错误都会进入 Validation Retry 或最终失败。

生产 `ContentLabelingService.label_contents()` 接收：

```python
max_validation_retries: int
```

要求为大于等于 0 的整数，精确定义：

```text
0 = 首次请求失败后不重试，总请求最多 1 次
1 = 额外重试 1 次，总请求最多 2 次
2 = 额外重试 2 次，总请求最多 3 次
```

Validation Retry 只处理**已经收到但本地校验不合法的模型响应**。每个重新请求都是独立 LLM attempt。重试请求只带当前仍未成功的 item，并携带上一响应的校验错误代码；同批已经成功并通过本地校验的 item 会从后续重试集合移除，不会因其他 item 错误重复调用/重复计费。

达到上限仍失败时：

```text
analysis_status = failed
analysis = None
```

不得填猜测标签；后续只能显式补跑。

## 6. OpenAI-compatible Adapter 与网络边界

真实 Adapter 位于：

```text
backend/src/aima_ugc/adapters/llm/openai_compatible.py
```

它实现 `ContentLabelingLLMPort`，使用仓库既有 `httpx` 依赖调用 OpenAI-compatible Chat Completions：

```text
POST <base_url>/chat/completions
```

当前只有这一种真实 LLM Adapter，因此调用方不需要再配置“Adapter 类型”。兼容相同 Chat Completions 协议的模型服务只需要更换 Base URL、API Key 和 Model，不为每个厂商复制一套 Adapter。

边界固定为：

- 一次 `complete()` 恰好一次 HTTP 请求；Adapter 不隐藏网络重试；
- Validation Retry 仍只由 `ContentLabelingService` 控制；
- 网络超时、连接错误、HTTP 错误属于 Transport/Provider 错误，不伪装成 Validation Retry；
- API key 使用 `SecretStr`，错误消息不回显 Provider body 或 Secret；
- 默认关闭环境代理继承、禁止自动 redirect；
- Adapter 默认 `use_json_mode=True`；当前离线内容打标人工入口直接使用该默认值，不把 JSON mode 暴露成 `.env` 必填/常规配置；即使启用 JSON mode 也仍执行本地 Validator；
- `timeout_seconds` 默认 60 秒，调用方只有确有环境差异时才覆盖；
- 未显式提供 `provider_name` 时，Adapter 从**实际请求 Base URL 的 hostname**生成稳定 `model_provider` 审计身份；显式非默认端口也进入该身份。显式 `provider_name` 参数继续作为程序级兼容覆盖，但人工 `.env` 不需要维护它；
- Provider 返回标准 token usage 时记录 input/output tokens；通用 Adapter 不猜测价格，所以没有明确费用字段时 `cost_amount/cost_currency` 保持空。

没有新增 OpenAI SDK，也没有新增网络重试库；复用锁文件中的 `httpx`。

## 7. 离线 JSONL 打标、checkpoint 恢复与原子回写

生产入口：

```python
label_unified_content_jsonl(...)
```

固定读取：

```text
deduplicated/contents.jsonl
```

成功结果通过本地 Validator 后依次执行：

```text
写 analysis/checkpoints.jsonl
→ flush + fsync
→ 将成功 Analysis 写入业务 JSONL 临时文件
→ 临时文件 flush + fsync
→ os.replace 原子替换 deduplicated/contents.jsonl
```

如果最终替换失败，临时业务文件会清理，原 `deduplicated/contents.jsonl` 不被破坏；已落盘 checkpoint 保留。

跨进程崩溃恢复：启动下一次打标时读取成功 checkpoint，但只有同时满足以下条件才允许恢复并跳过再次模型调用：

```text
platform 相同
external_content_id 相同
最小模型输入 input_hash 相同
prompt_sha256 等于当前完整 Prompt
taxonomy_sha256 等于当前 Taxonomy
model_provider 等于当前 Service 的模型服务身份
model 等于当前 Service 的模型
```

其中 `input_hash` 仍只由允许发送给模型的 `title`、`text`、`author.display_name` 计算。OpenAI-compatible Adapter 默认把实际 Base URL 的 endpoint host 作为 `model_provider`，因此更换服务 endpoint 或模型时旧 checkpoint 会安全失效；Prompt/Taxonomy 变化同理。旧 checkpoint 仍保留为历史审计。

恢复成功的记录直接把 checkpoint 中已验证的 `ContentLabelAnalysisV1` 或 `ContentLabelAnalysisV2` 写入业务临时 JSONL，再参与同一次原子 `os.replace`；checkpoint 本身始终不是业务事实源。`OfflineContentLabelingSummary.rows_recovered` 用于区分本次恢复数量和本次新模型成功数量。

checkpoint 中的 `analysis.schema_version` 决定 V1/V2 解析。历史 V1 checkpoint 可以被安全解析，但是否恢复仍必须同时通过当前 input、Prompt/Taxonomy Hash、Provider 和 Model 身份门禁；因此使用旧 V1 Prompt 生成的 checkpoint 在当前 V2 Prompt 下会自然失效。新模型成功结果只写 V2。

审计文件：

```text
analysis/checkpoints.jsonl
analysis/attempts.jsonl
analysis/failed.jsonl
```

`attempts.jsonl` 每次模型 attempt 记录 attempt_no、item_nos、validation_error_codes、model/provider、Prompt/Taxonomy Hash、时间和可获得的 token/费用；`checkpoints.jsonl` 只保存已通过 Validator 的成功 Analysis；`failed.jsonl` 显式记录 `analysis_status=failed` 与最终校验错误代码。失败 item 不会被猜测填入业务 Analysis。

## 8. Fake、调试与费用

`FakeContentLabelingLLM` 不访问网络、不产生真实模型费用，用预设原始响应驱动正式 Service 与 Validator。它适合验证非法 JSON、字段错误、item 配对错误、未知标签、父子错配、数组/空标签、Validation Retry、同批部分成功，以及 checkpoint 恢复与旧 Prompt/Taxonomy/Provider/模型 checkpoint 失效行为。

真实模型调试优先查看：

```text
analysis/attempts.jsonl
analysis/checkpoints.jsonl
analysis/failed.jsonl
```

再核对 `validation_error_codes`、`prompt_sha256`、`taxonomy_sha256`、`model_provider` 和 `model`。人工离线入口中的 `model_provider` 默认来自 `AIMA_LLM_BASE_URL` 的 endpoint host，`model` 来自 `AIMA_LLM_MODEL`。不要通过放宽 Validator、模糊匹配或自动改标签制造“成功”。Validation Retry 会产生额外真实模型调用和费用；checkpoint 恢复只复用与当前输入、当前 Prompt/Taxonomy 和当前模型身份完全匹配的成功结果。

## 9. 当前长期边界

临时 P1 已完成并验证：

- checkpoint 跨进程崩溃恢复，成功恢复不再次调用模型；
- 恢复绑定最小输入 Hash、当前 `prompt_sha256`、当前 `taxonomy_sha256`、`model_provider` 和 `model`；
- `imports_test.run_all()` 固定串联 convert → filter → deduplicate → label → final Excel；
- `run_summary.json` 原子写出；
- 最终 labeled Excel 只读取回写后的同一 `deduplicated/contents.jsonl`；
- Shared Exporter 正确投影 `record.analysis` 到现有 `UnifiedDataExcelV1` 分析列；
- `export_raw_excel()` 继续只是人工旁路，不进入默认 `run_all()`；
- 真实 OpenAI-compatible Adapter 继续是可替换外部边界，人工配置只暴露 Base URL、API Key、Model 和可选 timeout。

未来正式 Analysis Job/API/数据库接入必须复用同一 Service/Port/Adapter/Validator，不把 `imports_test` 复制成第二套正式实现。
