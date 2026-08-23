# Analysis 模块

`aima_ugc.modules.analysis` 负责**平台无关的内容 AI 分析**。

它回答的是：

```text
这条内容与爱玛是否真正相关？
是谁在发声？
情感是什么？
属于哪些一级/二级舆情标签？
```

Canonical/Content 只保存外部观察事实；这些结论属于后置 Analysis，不能塞进 Mapper 或 Canonical。

完整实现、Retry、离线并发/Checkpoint、正式 PostgreSQL Job 和排障见：

[`docs/appendix/07_AI舆情打标与分析实现.md`](../../../../../docs/appendix/07_AI舆情打标与分析实现.md)

---

## 1. 当前结果结构

当前新成功结果：

```text
ContentLabelAnalysisV3
```

每条结果包含：

```text
relevance
voice_type
sentiment
labels[]
```

约束：

```text
relevance = relevant
→ sentiment 必须有值
→ labels 至少一个合法 primary + secondary pair

relevance = irrelevant
→ sentiment = null
→ labels = []
```

历史 `ContentLabelAnalysisV1/V2` 只保留读取兼容，不再作为新写入格式。

当前 `voice_type`：

```text
user_voice
creator_marketing
brand_official
dealer_promotion
media_information
other_organization
unknown
```

真实用户发声唯一业务判断：

```text
voice_type == user_voice
```

不要再增加 `is_user_voice`/`is_real_user_voice` 平行字段。

---

## 2. Prompt / Taxonomy 唯一事实源

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

完整情感、9 个一级/39 个二级标签、父子关系、判断规则和示例只维护在这份 Prompt Markdown。

相关代码：

```text
prompt_taxonomy.py
→ 解析机器 Taxonomy JSON
→ 校验合法性
→ taxonomy_sha256

prompt_snapshot.py
→ 冻结 Prompt/Taxonomy 身份
```

Python 不维护第二套具体标签 Enum/映射；Blueprint/Appendix 也不复制完整 taxonomy。

修改标签体系时：

```text
Prompt
→ Prompt/Validator tests
→ 如果输出 Contract/DB 结构没有变化，不修改 Python 标签常量（因为不存在这套常量）
```

---

## 3. 模型实际看到什么

`ContentLabelingService` 只把允许字段投影给模型：

```text
title
text
author.display_name
author.bio
author.verification_label
```

不会发送：

- Content UUID；
- platform；
- Provider 私有字段；
- URL；
- 点赞/评论数；
- Raw 定位；
- 源 Excel 情感；
- 其他未批准元数据。

这样可以降低 token、减少无关信息干扰，并让 `input_hash` 和隐私边界可审计。

核心代码：

```text
content_labeling.py
→ ContentLabelingModelItem.model_payload()
```

---

## 4. 当前代码地图

### Contract

```text
backend/src/aima_ugc/contracts/analysis/content_label.py
backend/src/aima_ugc/contracts/analysis/content_record.py
```

### Service / Validator

```text
backend/src/aima_ugc/modules/analysis/content_labeling.py
```

核心：

```text
ContentLabelingService
ContentLabelingLLMPort
RuntimeTaxonomyValidator
ContentLabelingLLMRequest
ContentLabelingLLMResponse
```

### 正式 Job

```text
content_analysis_job.py
```

Job 类型：

```text
analysis.content-label.v1
```

### 正式 Worker 装配

```text
backend/src/aima_ugc/bootstrap/analysis_worker.py
```

### PostgreSQL 表

```text
backend/src/aima_ugc/modules/analysis/tables.py
```

当前正式表：

```text
analysis_content_results
analysis_content_requests
analysis_content_request_items
analysis_content_label_pairs
```

### PostgreSQL Repository

```text
backend/src/aima_ugc/adapters/persistence/postgres/analysis.py
```

### LLM Adapter

```text
backend/src/aima_ugc/adapters/llm/
```

### 离线执行

```text
offline_labeling.py
offline_content.py
backend/src/aima_ugc/adapters/providers/imports_test/
```

---

## 5. 正式 PostgreSQL Analysis 调用链

```text
POST /api/v1/content-analysis-requests
→ 冻结目标 Content Version
→ analysis_content_requests / items
→ analysis.content-label.v1 Job
→ Worker
→ ContentLabelingService
→ LLM Adapter
→ RuntimeTaxonomyValidator
→ Analysis Repository
→ analysis_content_results / label_pairs
```

正式 Analysis 已经不是“未来能力”。

当前 `analysis_content_results` 保存可复现的 Analysis 身份和业务结果，但**没有 token/cost 列**。

LLM 物理请求 usage/cost 由共享 `adapters/llm` 计算/审计；不要把运行时费用审计误写成 Analysis Result Schema。

---

## 6. Analysis 为什么绑定 Content Version

Content 正文/作者等发生变化后：

```text
Version A 的 Analysis
≠ Version B 的当前 Analysis
```

Current Analysis 身份会结合：

```text
content/version
analysis schema/version
prompt identity
taxonomy identity
model provider/model
```

因此查询/声音广场可以区分：

```text
completed
stale
pending
```

相关查询：

```text
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
backend/src/aima_ugc/bootstrap/content_http.py
```

不要在 Vue 里把旧 Analysis 强行当 current。

---

## 7. 规则 Relevance 与 AI Relevance 不是同一层

规则层：

```text
确定性关键词/配置粗筛
→ Collection / Import / Ingestion 前后
```

AI 层：

```text
已经进入 Content 的内容
→ LLM 做语义相关性判断
→ analysis_content_results.relevance
```

因此：

```text
规则筛过
≠ AI 一定 relevant
```

当前 `contents` 没有 `is_relevant` AI 投影列。

数据库默认业务列表/查询型 Analysis target/查询型 Export 会按当前 Analysis relevance 语义处理已经判定 irrelevant 的内容；显式审计查询仍可读取 Analysis 事实。

---

## 8. Validation Retry 与 Transport Retry

### Validation Retry

```text
HTTP 已成功
→ 模型 JSON/字段/taxonomy 不合法
→ Analysis Service 只重试失败 item
```

### Transport Retry

```text
连接/超时/408/429/部分5xx
→ adapters/llm/retrying.py
```

两者不能共用一个计数器。

Base LLM Adapter 一次 `complete()` 最多一次物理 HTTP 发送；Transport Retry 是显式 wrapper 产生的新物理请求。

详细错误码、次数、费用审计见 AI Appendix 和：

```text
backend/src/aima_ugc/adapters/llm/README.md
```

---

## 9. 正式模式与离线模式

### 正式模式

```text
PostgreSQL Content
→ Analysis Request/Job
→ PostgreSQL Analysis Result
```

### 离线模式

```text
Unified JSONL
→ Offline Labeling
→ checkpoint / attempts / llm_requests / failed
→ 最终 JSONL / Excel / Word
```

离线模式仍然复用：

```text
同一 Prompt
同一 Taxonomy Loader
同一 ContentLabelingService
同一 LLM Adapter
同一 Validator
```

`imports_test` 是人工/离线装配入口，不是 Analysis 唯一或主要生产装配者。

离线 250 有界并发、Canary、Checkpoint、单写者、顺序回写、物理请求审计等细节统一维护在：

```text
docs/appendix/07_AI舆情打标与分析实现.md
```

不在模块 README 复制第二份长说明。

---

## 10. 修改不同问题时改哪里

| 需求 | 正确入口 |
| --- | --- |
| 改业务标签/判断标准 | 当前 Prompt + Prompt/Validator tests |
| 改 V3 输出结构 | Analysis Contract + Service/Validator + DB/API/Export/Frontend + Migration（需要时） |
| 改 `voice_type` 值集合 | Prompt + Contract + Validator + DB Check/Migration + Excel/Frontend/tests |
| 改 current/stale/pending | Analysis Identity + Content Query Repository + API/Frontend tests |
| 改模型/Base URL | Platform Settings + `adapters/llm` + Pricing |
| 改网络 Retry | `adapters/llm/retrying.py` + audit tests |
| 改 Validation Retry | `content_labeling.py` + Analysis tests |
| 改正式 Job | `content_analysis_job.py` + `bootstrap/analysis_worker.py` + Job integration |
| 改离线并发/Checkpoint | `offline_labeling.py` + offline tests/Appendix |
| 改数据库字段 | `tables.py` + 新 Alembic Migration + Repository + integration |

---

## 11. 排障顺序

### Analysis 一直 pending

```text
analysis_content_requests
→ jobs
→ worker.log
→ analysis_content_request_items
→ 当前 Content Version / Analysis Identity
```

### Job failed

```text
Job error
→ worker.log
→ LLM Transport/Protocol
→ Validation Attempt
→ Analysis Repository
```

### 页面 stale

```text
Content Version
→ Prompt/Taxonomy/Model Identity
→ matching Analysis Result
→ Content Query current-analysis join
```

### Excel/Word 少数据

依次判断：

```text
规则 Relevance
→ 去重
→ AI relevance
→ Export/Report 输入默认过滤
```

SQL 排障见：

[`docs/appendix/01_PostgreSQL查询与调试实战.md`](../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md)

---

## 12. 当前明确没有

- 评论 AI 打标正式业务能力；
- Analysis Result token/cost 数据库列；
- 独立 Analysis 管理中心页面；
- 统一 request/amount Budget Guard；
- Monitoring/Alert/VOC/Ticket 业务域。

后续阶段看：

[`docs/roadmap/02_生产上线实施路线.md`](../../../../../docs/roadmap/02_生产上线实施路线.md)
