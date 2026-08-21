# AI 舆情分析与打标

这篇文档回答：**一条内容进入 AI 后，模型到底判断什么；“真实用户发声”怎么表达；无关内容怎么处理；这些结果为什么单独属于 Analysis，而不是 Canonical。**

## 1. 先看完整流程

当前 Content Labeling V3 一次模型调用完成四件事：

```text
标题 + 正文 + 最小作者公开信息
        ↓
      LLM
        ↓
1. relevance   是否与爱玛舆情有实质语义关系
2. voice_type  这条内容属于哪类发声
3. sentiment   对爱玛的情感
4. labels      一级/二级业务标签
        ↓
结构校验 + 业务校验
        ↓
离线结果 或 PostgreSQL Analysis Result
```

为什么放在一次调用里？因为四个判断依赖同一段语义。拆成几次模型请求会重复读取同一内容，也更容易出现前后判断互相矛盾。

## 2. 为什么 AI 结果不放进 Canonical

Canonical 保存的是外部可以观察到的事实，例如：

```text
标题
正文
作者展示名
发布时间
点赞数
评论数
```

AI 分析是系统根据某个 Prompt、Taxonomy 和模型推导出来的结论。同一条内容以后换 Prompt 或模型，结果可能变化。

因此长期边界是：

```text
Canonical = 外部事实
Analysis  = 派生判断
```

不要给 `CanonicalContentV1` 增加 sentiment、labels、voice_type 或 AI relevance。

## 3. 模型实际看到什么

当前 V3 Prompt 的每个 item 只提供：

```text
title
text
author.display_name
author.bio
author.verification_label
```

不会因为数据库里还有平台、URL、互动指标、粉丝数等字段，就全部送给模型。

原因很实际：

- 降低无关噪音；
- 减少 Token；
- 避免模型根据未授权字段“猜身份”；
- 让同一 Prompt 在不同平台保持一致输入语义。

`item_no` 只用于当前批次请求/响应配对，不是业务 ID。

## 4. Prompt 是业务规则唯一事实源

当前正式 Prompt：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

它定义：

- `relevant / irrelevant`；
- 7 类 `voice_type`；
- 4 类 sentiment；
- 9 个一级、39 个二级标签；
- 一级/二级合法配对；
- 输出结构和判断规则。

本文不复制完整 taxonomy。否则 Prompt 改了、附录没改，就会形成两套业务真相。

Python 的职责是：

```text
加载当前 Prompt
→ 调模型
→ 解析 JSON
→ 校验结构/枚举/taxonomy 关系
→ 保存结果
```

Python 不应该再硬编码另一份完整 taxonomy。

## 5. 两层 Relevance 不要混在一起

### 5.1 规则 Relevance

在 Canonical 后、正式 Content Ingestion 前执行：

```text
Canonical
→ Global Relevance Service
→ relevant：继续 Ingestion
→ filtered：来源账本记录 filtered，不写成 Content
```

这层是低成本、可解释的关键词/规则过滤，Excel 和 TikHub 共用同一正式服务。

### 5.2 AI Semantic Relevance

AI V3 对已经进入 Analysis 的内容做语义复核：

```text
relevance = relevant | irrelevant
```

它解决“关键词碰撞但正文其实无关”等规则过滤难以判断的问题。

数据库事实在：

```text
analysis_content_results.relevance
```

当前 `contents` 表没有 `is_relevant` 这类 AI 投影列。HTTP `ContentFilterSnapshot.relevance` 可以显式筛选相关性，但是否默认应用某个筛选条件要看当前调用方/Query Service，不能从字段存在推断默认行为。

## 6. 无关内容怎么处理

必须区分离线文件链路和正式数据库 Analysis。

### 离线处理

当前离线分析链路对 `irrelevant`：

```text
最终业务 JSONL / Excel / report
→ 不再输出这条业务记录

checkpoint
→ 保留恢复所需的最小处理决策

原始输入 / Raw
→ 不因为业务过滤而被销毁
```

这里的“删除”是从**最终业务结果文件**中排除，不等于把原始证据永久删掉。

### 正式数据库 Analysis

正式分析会把结果保存进 `analysis_content_results`，包括 `relevance=irrelevant` 的审计事实。

不能因为 AI 一次判定无关，就直接 `DELETE contents` 或删除来源 Raw。

## 7. voice_type：真实用户发声现在怎么表达

当前 `voice_type` 只有以下 7 个合法机器值：

```text
user_voice
creator_marketing
brand_official
dealer_promotion
media_information
other_organization
unknown
```

白话解释：

| 值 | 含义 |
| --- | --- |
| `user_voice` | 普通个人的真实体验、观点、咨询、投诉、购买/推荐意愿等非组织化表达 |
| `creator_marketing` | 达人/KOL/KOC/博主以合作、种草、带货、导购、转化为主要目的的内容 |
| `brand_official` | 爱玛品牌或明确品牌官方/工作人员身份发布的品牌传播 |
| `dealer_promotion` | 经销商、门店、销售围绕报价、优惠、现车、到店、留资、成交等获客内容 |
| `media_information` | 媒体、新闻、行业资讯号、聚合号的报道、转载或资讯内容 |
| `other_organization` | 政府、协会、学校、非品牌企业等其他机构的通知/合作/公共事务传播 |
| `unknown` | 综合可见证据仍无法可靠判断 |

### 为什么不再加“是否真实用户”布尔字段

因为它和 `voice_type` 会重复表达同一业务事实。

当前规则：

```text
真实用户发声
→ voice_type = user_voice
```

页面/报表需要“真实用户占比”时，从 `voice_type` 统计，不再保存平行 bool。

### 为什么不能只看账号名分类

Prompt 明确要求组合两类证据：

```text
主体证据
→ 展示名、简介、认证文案看起来像谁

表达目的证据
→ 当前标题/正文为什么这样说
```

例如一个“骑行博主”写自费长期使用体验，没有合作/导购证据，仍可判 `user_voice`；不能因为作者是博主就自动判营销。

## 8. sentiment 和 labels 的关系

当前 sentiment 只有：

```text
正面
中性
负面
混合
```

V3 约束：

```text
relevance = relevant
→ sentiment 必须是上面四类之一
→ labels 至少一个合法一级/二级标签对

relevance = irrelevant
→ sentiment = null
→ labels = []
```

这样不会出现“内容已经无关，却硬给一个负面标签”的假数据。

## 9. 数据库里怎么保存 Analysis

当前正式表：

```text
analysis_content_results
analysis_content_requests
analysis_content_request_items
analysis_content_label_pairs
```

### `analysis_content_results`

一条已完成分析结果，主要保存：

- `content_id + content_version`；
- `job_id`；
- `schema_version`；
- `relevance`；
- `voice_type`；
- `sentiment`；
- `prompt_version / prompt_sha256 / taxonomy_sha256`；
- `model_provider / model`；
- `input_hash`；
- `analyzed_at / created_at`。

这些字段让系统以后能够回答：

> 这条结论是针对内容哪一版、用哪个 Prompt/Taxonomy/模型得到的？

### `analysis_content_label_pairs`

保存一个结果里的有序一级/二级标签对：

```text
analysis_result_id
ordinal
primary_label
secondary_label
```

不把多个标签塞成逗号字符串。

### `analysis_content_requests` / `analysis_content_request_items`

一次正式批量 Analysis 请求先冻结目标 Content 和版本，再交给 Job 执行，避免任务运行期间查询集合变化。

精确列/约束以 `modules/analysis/tables.py` 和 Migration 为准。

## 10. 正式数据库分析怎么走

当前正式 Job：

```text
analysis.content-label.v1
```

流程：

```text
用户/系统创建 Analysis 请求
→ 冻结 request items
→ 创建 Job
→ Worker 读取目标 Content 版本
→ 调 Content Labeling V3
→ Validator 校验
→ Analysis Owner 写 Result + Label Pairs
→ Request Item 收敛 succeeded / failed / stale
```

Router 不在一个 HTTP 请求里同步等待大批量 LLM。

## 11. Validation Retry 和 Transport Retry 不是一回事

### Validation Retry

模型 HTTP 已成功返回，但结果不合法，例如：

- 不是要求的 JSON；
- `voice_type` 不在 7 类里；
- `relevant` 却没有 sentiment；
- `irrelevant` 却返回 labels；
- 一级/二级标签组合非法。

上层可以带着校验错误要求模型修正。

### Transport Retry

网络层失败，例如连接失败、超时、5xx。

基础 OpenAI-compatible Adapter 的一次 `complete()` 对应一次 HTTP 请求，不在内部偷偷重发。是否重试由上层明确决定。

把两种 Retry 混起来，会让请求次数和失败原因无法解释。

## 12. 离线批量分析为什么需要 checkpoint

处理大量 Excel 数据时，不能因为最后一条失败就全部重跑。

当前离线思路：

```text
输入记录
→ 有界并发调用
→ 校验
→ 持久 checkpoint
→ 单写入器输出
```

重启后从 checkpoint 恢复，已经完成的稳定身份不重复调用模型。

## 13. 成本信息怎么理解

当前正式 `analysis_content_results` 表**没有** token/cost 列，所以不能写成“数据库 Analysis Result 已保存本次 token 和价格”。

离线 LLM 处理与价格计算能力应以当前 Analysis 模块、Provider Adapter、运行产物和价格配置实现为准；如果以后要把 token/cost 作为正式数据库业务事实，需要新的明确 Schema/Migration，而不是只改文档。

当前也没有 AI 金额 Budget Guard。能计算/显示费用不等于“超过金额会禁止调用”。

## 14. 最小例子

输入：

```text
标题：爱玛这车刹车手感怎么样？
正文：我骑了三个月，续航还行，但是后刹有点软……
作者：普通昵称；简介主要是日常生活；没有明显机构/营销证据
```

一个合法的结果形态可能是：

```text
relevance = relevant
voice_type = user_voice
sentiment = 混合
labels = [当前 Prompt taxonomy 中合法的一组一级/二级标签]
```

这里不复制具体标签列表，避免示例变成第二套 taxonomy。

## 15. 当前代码入口

| 想看什么 | 位置 |
| --- | --- |
| 模块当前实现 | `backend/src/aima_ugc/modules/analysis/README.md` |
| V3 Prompt | `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md` |
| 表结构 | `backend/src/aima_ugc/modules/analysis/tables.py` |
| relevance/voice_type Migration | `migrations/versions/20260821_0023_analysis_relevance_voice_type.py` |
| 正式 Job | `backend/src/aima_ugc/modules/analysis/content_analysis_job.py` |
| HTTP Contract | `backend/src/aima_ugc/contracts/http.py` |
| 数据库调试 | [`PostgreSQL调试与常用SQL.md`](PostgreSQL调试与常用SQL.md) |

## 16. 常见误区

- 把 AI 标签塞进 Canonical；
- Python/文档再维护一份完整 taxonomy；
- 为“真实用户”再加第二个 bool；
- 把 `voice_type` 写成已经过期的三分类或其他历史分类；
- 把规则 Relevance 和 AI Semantic Relevance 混成一个字段；
- 假设 `contents.is_relevant` 存在；
- AI 判无关后直接 DELETE Content/Raw；
- 让 Router 同步跑大批量 LLM；
- 一个 Adapter 调用内部悄悄发多次 HTTP；
- 把离线成本计算写成数据库已持久化 token/cost。

长期边界见 [`../blueprint/07-技术决策与实施门禁.md`](../blueprint/07-技术决策与实施门禁.md) 和 [`../blueprint/02-采集系统与数据标准化.md`](../blueprint/02-采集系统与数据标准化.md)。
