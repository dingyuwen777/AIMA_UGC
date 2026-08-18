# Analysis 模块

> 当前阶段：P1E 已闭环；下一最小 P1 单元为 P1F。P1F 未完成前，本模块不把真实 OpenAI-compatible Adapter、checkpoint 或业务 JSONL AI 回写描述为已实现。

`aima_ugc.modules.analysis` 保存平台无关的内容处理与 AI 分析业务能力。P1E 在这里建立 Prompt/Taxonomy 运行时加载、本地 Validator、Analysis Service/Port 和无网络 Fake；真实 OpenAI-compatible Adapter、checkpoint 与业务 JSONL 原子回写属于 P1F，不在本阶段提前实现。

## 1. Prompt / Taxonomy 唯一事实源

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

`PromptTaxonomyLoader` 精确提取这个 JSON 块，使用 `json.loads` 解析，并在任何模型调用前严格校验 schema、空值、重复值和父子结构。自然语言表格只用于模型理解，程序不会解析自然语言表格猜标签闭集。

Python/Pydantic 只定义结构，不复制具体标签 Enum、Literal、父子关系常量或第二份 taxonomy JSON。因此以后仅增加、删除、重命名标签，调整父子关系或修改判断标准/示例时，业务标签事实只改上述 Markdown；运行时 Validator 会立即使用新 Taxonomy。

Loader 同时计算：

- `taxonomy_sha256`：规范化机器 Taxonomy JSON 的 SHA-256；
- `prompt_sha256`：完整 Prompt Markdown UTF-8 内容的 SHA-256。

仅修改 Prompt 说明文字时只改变 `prompt_sha256`；修改机器 Taxonomy 时两个 Hash 都会随文件内容变化。

## 2. Analysis Contract

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

`ContentLabelAnalysisV1` 只表示**已经通过本地 Validator 的成功结果**，所以 `analysis_status` 固定为 `succeeded`。Validation Retry 达到上限仍失败时，Service 返回该 item 的 `analysis_status=failed`、`analysis=None` 和错误代码；不会构造一条带猜测标签的 `ContentLabelAnalysisV1`。

`UnifiedContentRecordV1.analysis` 现在允许：

```text
null
或
ContentLabelAnalysisV1
```

CanonicalContentV1 没有增加 AI 标签。

## 3. 发给模型的最小业务输入

Service 从 `CanonicalContentV1` 只投影：

```text
title
text
author.display_name
```

缺失值统一填空字符串。批量请求额外带临时 `item_no` 做请求/响应配对；它不是业务字段。

不会发送内容 ID、平台 ID、URL、互动指标、粉丝数、Provider、`matched_keywords`、源 Excel 情感、Raw locator 或其他 Provider 私有字段。

## 4. 本地 Validator

模型返回 JSON 后，不因 JSON mode / structured output 而跳过本地校验。Validator 检查：

- JSON 能否解析；
- 顶层和 item 固定字段是否正确、是否有额外字段；
- item 数量、顺序、唯一性与 `item_no` 配对；
- 标签必须是非空单字符串，不能是数组；
- sentiment 是否属于当前 Taxonomy；
- primary 是否属于当前 Taxonomy；
- secondary 是否属于当前 primary。

校验不做模糊匹配、近义标签替换或程序猜测填值。未知标签、父子关系错误、缺失/重复 item、额外字段等都会进入 Validation Retry 或最终失败。

## 5. max_validation_retries

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

Validation Retry 只处理**已经收到但本地校验不合法的模型响应**。网络超时、连接错误、限流等 Transport Retry 不在这一层偷偷重试，真实 Adapter 的底层网络策略在 P1F 单独实现和验证。

每次重新请求都是独立 LLM attempt，记录：

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

重试请求会携带上一响应的校验错误代码，要求模型重新返回当前未成功 item。**同批已经成功并通过本地校验的 item 会从后续重试集合移除**，不会因为其他 item 格式错误而重复调用、重复计费。

达到上限仍失败时，不填猜测标签；后续可以显式补跑。

## 6. Fake 与调试

`FakeContentLabelingLLM` 不访问网络、不产生真实模型费用，用预设原始响应驱动正式 Service 与 Validator。它适合验证：

- 非法 JSON；
- 必填字段缺失或额外字段；
- item 缺失、重复、顺序错误或无法配对；
- 未知 sentiment / 一级标签；
- 二级标签不属于一级；
- 数组标签、空标签；
- `max_validation_retries` 的 0/1/2 精确请求次数；
- 同批成功 item 不重复重试。

调试模型非法响应时优先查看 `ContentLabelingBatchResult.attempts[*].validation_error_codes` 和失败 item 的 `validation_error_codes`，再核对本次 `prompt_sha256` / `taxonomy_sha256`。不要通过放宽 Validator 或自动改标签制造“成功”。

## 7. P1E 与后续边界

P1E **不包含**：

- 真实 OpenAI-compatible LLM Adapter；
- `.env` 中真实模型配置；
- checkpoint 持久化；
- `deduplicated/contents.jsonl` 原子回写；
- `label_sentiment()` 人工入口接线；
- `run_all()`；
- 90k 性能与真实模型小样。

这些按 Blueprint 14 的 P1F—P1H 顺序继续实现。P1E 的目的只是先把动态标签事实源、严格校验、重试语义、成功 Analysis Contract 和可无网络测试的业务核心固定下来。
