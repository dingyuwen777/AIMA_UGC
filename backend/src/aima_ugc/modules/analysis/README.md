# Analysis 模块

> 当前阶段：P1A—P1F 已闭环；下一最小 P1 单元为 P1G。P1G 未完成前，不把 checkpoint 自动恢复、`run_all()` 或最终 labeled Excel 串联描述为已实现。

`aima_ugc.modules.analysis` 保存平台无关的内容处理与 AI 分析业务能力。当前已建立 Prompt/Taxonomy 运行时加载、本地 Validator、Analysis Service/Port、Fake、真实 OpenAI-compatible Adapter 的业务接线，以及离线 JSONL checkpoint/attempt/failed 审计和成功 Analysis 原子回写。

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
ContentLabelAnalysisV1
```

P1 第一版不接数据库。AI 只读取并回写同一个：

```text
deduplicated/contents.jsonl
```

`analysis/checkpoints.jsonl`、`attempts.jsonl`、`failed.jsonl` 是恢复/费用安全/审计材料，不是第二业务事实源；最终业务消费者仍应读取回写后的 `deduplicated/contents.jsonl`。

## 2. Prompt / Taxonomy 唯一事实源

具体情感、一级标签、二级标签、一级/二级父子关系、覆盖内容、典型表达、边界规则、冲突优先级和示例只维护在：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
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

公共成功结果是：

```text
ContentLabelAnalysisV1
```

三个业务标签字段固定使用 `str`：

```text
sentiment
primary_label
secondary_label
```

具体允许值由当前 `PromptTaxonomy` 动态校验，不写进 Python Enum/Literal。

`ContentLabelAnalysisV1` 只表示**已经通过本地 Validator 的成功结果**，所以其中 `analysis_status` 固定为 `succeeded`。Validation Retry 达到上限仍失败时，不构造失败版 `ContentLabelAnalysisV1`：Service 返回该 item 的 `analysis_status=failed`、`analysis=None` 和错误代码，离线编排把失败状态写入 `analysis/failed.jsonl`，业务 JSONL 中该记录仍保持 `analysis=null`。

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
- 标签必须是非空单字符串，不能是数组；
- sentiment 是否属于当前 Taxonomy；
- primary 是否属于当前 Taxonomy；
- secondary 是否属于当前 primary。

校验不做模糊匹配、近义标签替换或程序猜测填值。缺少必须字段、额外字段、item 缺失/重复/数量不一致、`item_no` 无法配对、未知 sentiment/一级标签、二级不属于一级、数组/空标签及其他结构错误都会进入 Validation Retry 或最终失败。

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

边界固定为：

- 一次 `complete()` 恰好一次 HTTP 请求；Adapter 不隐藏网络重试；
- Validation Retry 仍只由 `ContentLabelingService` 控制；
- 网络超时、连接错误、HTTP 错误属于 Transport/Provider 错误，不伪装成 Validation Retry；
- API key 使用 `SecretStr`，错误消息不回显 Provider body 或 Secret；
- 默认关闭环境代理继承、禁止自动 redirect；
- 可配置 JSON mode；即使启用也仍执行本地 Validator；
- Provider 返回标准 token usage 时记录 input/output tokens；通用 Adapter 不猜测价格，所以没有明确费用字段时 `cost_amount/cost_currency` 保持空。

P1F 没有新增 OpenAI SDK，也没有新增网络重试库；复用锁文件中的 `httpx`。

## 7. 离线 JSONL 打标、attempt 与原子回写

生产入口：

```python
label_unified_content_jsonl(...)
```

固定读取：

```text
deduplicated/contents.jsonl
```

每批调用正式 `ContentLabelingService`。成功结果通过本地 Validator 后依次执行：

```text
写 analysis/checkpoints.jsonl
→ flush + fsync
→ 将成功 Analysis 写入业务 JSONL 临时文件
→ 临时文件 flush + fsync
→ os.replace 原子替换 deduplicated/contents.jsonl
```

如果最终替换失败，临时业务文件会清理，原 `deduplicated/contents.jsonl` 不被破坏；已落盘 checkpoint 保留，供后续恢复/审计使用。

审计文件：

```text
analysis/checkpoints.jsonl
analysis/attempts.jsonl
analysis/failed.jsonl
```

`attempts.jsonl` 每次模型 attempt 记录：

```text
attempt_no
item_nos
validation_error_codes
model_provider
model
prompt_sha256
taxonomy_sha256
started_at
completed_at
input_tokens / output_tokens（可获得时）
cost_amount / cost_currency（可获得时）
```

并保存安全的 item 配对身份与 `input_hash`，用于排查同一批次到底调用了哪些记录。

`checkpoints.jsonl` 只保存已经通过 Validator 的成功 Analysis；`failed.jsonl` 显式记录 `analysis_status=failed` 与最终校验错误代码。失败 item 不会被猜测填入业务 Analysis。

当前 P1F 会跳过业务 JSONL 中已经存在成功 `analysis` 的记录；**利用 checkpoint 自动恢复“checkpoint 已写但业务 JSONL 尚未发布”等崩溃场景属于 P1G**，当前不要把 checkpoint 文件手工当成第二业务事实源回读。

## 8. Fake、调试与费用

`FakeContentLabelingLLM` 不访问网络、不产生真实模型费用，用预设原始响应驱动正式 Service 与 Validator。它适合验证非法 JSON、字段错误、item 配对错误、未知标签、父子错配、数组/空标签、Validation Retry 次数以及同批成功 item 不重复调用。

真实模型调试优先查看：

```text
analysis/attempts.jsonl
analysis/checkpoints.jsonl
analysis/failed.jsonl
```

再核对对应 attempt 的：

```text
validation_error_codes
prompt_sha256
taxonomy_sha256
model_provider
model
```

不要通过放宽 Validator、模糊匹配或自动改标签制造“成功”。Validation Retry 会产生额外真实模型调用和费用；`max_validation_retries` 只是 Validation Retry 上限，不代表网络重试次数。

## 9. P1F 与后续边界

P1F 已实现：

- 真实 OpenAI-compatible LLM Adapter；
- `label_sentiment()` 的真实 Adapter 接线与显式费用开关；
- 最小业务输入；
- 可配置 Validation Retry；
- attempt/checkpoint/failed 审计；
- 成功 Analysis 原子回写同一 `deduplicated/contents.jsonl`；
- 无网络 Fake 与 HTTP Mock 自动测试。

P1F **未实现也不提前实现**：

- `run_all()` 完整串联；
- 从 checkpoint 自动恢复中断并保证跨进程重启不重复成功模型调用；
- `run_summary.json`；
- 最终 `labeled_data.xlsx` 串联；
- 90k 性能验证；
- 真实模型付费小样。

前三项和最终同源 Excel 串联属于 P1G；90k 与真实模型小样属于 P1H。