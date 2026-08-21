# AI 舆情分析与打标

这篇文档回答：**一条帖子进入 AI 后，系统到底让模型判断什么、为什么这些结果不直接塞进 Canonical、无关数据和“真实用户发声”现在怎么处理。**

## 1. 先看当前完整流程

当前 Content Labeling V3 一次模型调用完成四件事：

```text
内容 + 最小作者公开信息
        ↓
      LLM
        ↓
1. relevance   是否与当前监测主题相关
2. voice_type  谁在发声
3. sentiment   情感
4. labels      一级/二级业务标签
        ↓
结构校验 / 业务校验
        ↓
离线结果 或 PostgreSQL Analysis Result
```

这样做的原因不是“把越多任务塞一次调用越高级”，而是这四个判断高度依赖同一段语义。一次判断可以避免：

- 同一内容被模型重复读取多次；
- “先判相关、再判用户、再判情感”产生互相矛盾的上下文；
- 多次请求增加延迟和费用。

## 2. 为什么 AI 结果不属于 Canonical

Canonical 表达的是外部平台可以观察到的事实，例如：

```text
帖子正文
作者昵称
发布时间
点赞数
评论数
```

AI 标签是系统根据模型和 Prompt 推导出的结果。同一条帖子换模型、Prompt 或版本后，结果可能变化。

所以边界是：

```text
Canonical = 外部事实
Analysis  = 派生判断
```

不要给 `CanonicalContentV1` 增加情感、一级标签、二级标签、发声类型等字段。

## 3. 模型实际看到什么

当前模型输入刻意保持最小，只给判断真正需要的内容：

- 标题；
- 正文；
- 作者 display name；
- 作者 bio；
- 作者 verification label。

不会因为数据库里有更多字段就全部塞给模型。

这样能：

- 降低 Token；
- 减少不相关噪音；
- 让 Prompt 更稳定；
- 避免把没有必要的个人/平台信息送给模型。

## 4. Prompt 才是业务标签规则的唯一事实源

当前唯一正式 Prompt：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

里面定义：

- relevance 的判定要求；
- voice_type 证据规则；
- sentiment；
- 一级/二级 taxonomy；
- 输出格式和限制。

本文不复制“9 个一级、39 个二级”完整表。原因很直接：如果 Prompt 改了而附录忘了改，就会出现两份业务真相。

Python 代码负责：

```text
加载 Prompt
→ 调模型
→ 解析结构
→ 校验字段是否合法
→ 保存结果
```

Python 不应该偷偷维护另一套 taxonomy。

## 5. relevance：相关性怎么理解

`relevance` 不是“有没有命中一个字”。它回答：

> 这条内容是否真正属于当前监测主题，值得进入后续舆情分析。

系统现在有两层相关性能力：

### 5.1 规则 Relevance

Canonical 之后、正式 Ingestion 前使用全局 Relevance Keyword Pack 做统一规则过滤。

它的价值是：

- Excel 和 TikHub 走同一口径；
- 很明显无关的数据可以更早过滤；
- 结果可解释、成本低。

### 5.2 AI Semantic Relevance

AI V3 再根据完整语义判断内容是否真正相关，解决“关键词碰巧出现，但内容主题其实无关”的情况。

当前数据库 `contents` 有相关性投影字段；默认业务查询只看 `is_relevant=true`。审计时可以显式查看无关记录。

## 6. 无关数据怎么处理

这里要区分**离线文件结果**和**正式数据库事实**。

### 离线处理

AI 判定无关后：

```text
最终业务 JSONL / Excel / report
→ 不再保留这条业务记录

checkpoint
→ 保留最小处理决策，便于恢复

原始输入 / Raw
→ 不因为业务过滤被销毁
```

所以用户看到的最终文件会“删除无关记录”。

### 正式数据库

数据库需要保留来源和分析审计，因此不靠物理 DELETE 表达业务相关性：

```text
contents.is_relevant
→ 默认业务查询过滤
→ 显式审计查询仍可查看
```

这能避免 AI 一次误判就永久丢失原始事实。

## 7. voice_type：现在怎么判断“真实用户发声”

当前唯一业务字段是 `voice_type`：

```text
professional_media
influencer_self_media
ordinary_user
```

可以白话理解为：

```text
professional_media
→ 媒体、机构、官方等职业化发声

influencer_self_media
→ 达人、KOL、自媒体、营销型创作者等

ordinary_user
→ 没有明显职业传播/营销身份的普通用户发声
```

AI 会结合正文语气和最小作者公开信息判断，而不是只看昵称里有没有“官方”“测评”等字样。

### 为什么不再加 `is_real_user_voice` 布尔字段

因为它会和 `voice_type` 重复表达同一事实：

```text
ordinary_user → true ?
influencer_self_media → false ?
professional_media → false ?
```

如果同时保存两列，就可能出现互相矛盾的数据。

因此当前规则是：

> `voice_type` 是发声类型唯一事实；页面或报表需要“普通用户占比”时，在查询/统计层从它计算。

## 8. sentiment 和 labels 的关系

只有相关内容才需要完整舆情标签。

V3 业务语义：

```text
relevant
→ 必须有合法 sentiment
→ 必须有合法 labels

irrelevant
→ sentiment = null
→ labels = []
```

这样能避免“内容都无关，却还硬给一个负面标签”的假数据。

## 9. 为什么标签对要单独保存

数据库里：

```text
analysis_results
→ 一次分析父结果

analysis_label_pairs
→ 这次结果里的有序一级/二级标签对
```

不把多标签保存成：

```text
"品牌评价,产品质量,售后服务"
```

因为逗号字符串无法可靠表达一级/二级配对，也不方便查询和排序。

## 10. Analysis Result 为什么要带版本/模型/Prompt 信息

AI 结果不是永久真理。需要回答：

```text
用哪个模型？
哪个 Provider？
哪个 Prompt 版本？
输入/输出多少 Token？
成本多少？
什么时候完成？
失败是什么类型？
```

当前 `analysis_results` 保存这些执行事实。最新成功结果被选为当前业务 Analysis，但旧结果仍可以用于审计和比较。

## 11. Validation Retry 和 Transport Retry 不是一回事

### Validation Retry

模型请求已经成功返回，但内容不符合约定结构或业务规则，例如：

```text
JSON 格式错
voice_type 不在允许值
relevant=true 但没有 sentiment
一级/二级标签组合非法
```

这种情况可以带着校验错误再次让模型修正。

### Transport Retry

网络请求本身失败，例如超时、连接错误、5xx。

基础 OpenAI-compatible Adapter 的一次 `complete()` 就对应一次 HTTP 请求，不在内部偷偷自动重发。是否重试由上层明确决定和记录。

把两种 Retry 混起来，会让请求次数和费用无法解释。

## 12. 离线批量分析为什么需要 checkpoint

九万条数据这类批处理不应该因为第 89999 条失败就从头再来。

离线分析使用持久 checkpoint 记录已经完成的稳定身份及最小结果：

```text
输入记录
→ 有界并发请求
→ 校验
→ checkpoint
→ 单写入器输出
```

重启后从 checkpoint 恢复，已经成功的记录不重复调用模型。

## 13. 正式数据库分析怎么走

Stage 8D 后正式链路是：

```text
用户/系统创建 Analysis 请求
→ analysis.content-label.v1 Job
→ Worker 查询目标 Content
→ 调当前 Content Labeling V3
→ 校验
→ Analysis Owner 写 analysis_results / analysis_label_pairs
→ 更新当前相关性投影
```

Router 不在 HTTP 请求里直接等待批量 LLM。

## 14. 成本怎么看

Analysis 会保存：

- input/output token；
- provider/model；
- 价格快照/计算结果；
- cost amount/currency。

价格配置使用供应商官方“输入缓存命中/输入缓存未命中/输出、每百万 tokens”语义，不使用模糊的内部简称作为对外配置语言。

当前系统**没有 AI 金额预算硬上限**。有成本记录不等于有发送前 Budget Guard。

## 15. 最小例子

输入：

```text
标题：爱玛这车刹车手感怎么样？
正文：我骑了三个月，续航还行，但是后刹有点软……
作者：普通昵称，无机构认证，简介为日常生活内容
```

合理结果形态可能是：

```text
relevance = relevant
voice_type = ordinary_user
sentiment = mixed / 对应当前 Prompt 允许值
labels = [当前 taxonomy 中合法的一组一级/二级标签]
```

这里故意不手写具体 taxonomy 名称，避免示例变成第二事实源。

## 16. 当前代码入口

| 想看什么 | 位置 |
| --- | --- |
| 模块说明 | `backend/src/aima_ugc/modules/analysis/README.md` |
| V3 Prompt | `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md` |
| Analysis Contract/Validator | `backend/src/aima_ugc/modules/analysis/` |
| PostgreSQL 表 | `backend/src/aima_ugc/modules/analysis/tables.py` |
| relevance/voice_type Migration | `migrations/versions/20260821_0023_analysis_relevance_voice_type.py` |
| 正式 API 装配 | `backend/src/aima_ugc/bootstrap/api.py` |
| 数据库调试 | [`PostgreSQL调试与常用SQL.md`](PostgreSQL调试与常用SQL.md) |

## 17. 常见误区

- 把 AI 标签塞进 Canonical；
- Python 再维护一份 taxonomy；
- 为“真实用户”再加第二个 bool；
- AI 判无关后直接 DELETE 正式数据库来源事实；
- 让 Router 同步跑大批量 LLM；
- 一个 Adapter 调用内部悄悄发多次 HTTP；
- 只看模型自然语言输出，不做结构和业务校验；
- 用“模型看起来挺准”代替 Fixture/测试/人工抽样验证。

长期边界见 [`../blueprint/04-后端任务API与前端.md`](../blueprint/04-后端任务API与前端.md)；数据分层见 [`../blueprint/02-采集系统与数据标准化.md`](../blueprint/02-采集系统与数据标准化.md)。
