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

当前 `voice_type` 合法值集合不在本文复制。唯一机器事实来自当前 Prompt 的机器 Taxonomy `voice_types`；各类型定义、边界、高混淆场景和学习示例也只在同一 Prompt 维护。当前结果继续以字符串 `voice_type` 保存，运行时由 `RuntimeTaxonomyValidator` 严格校验 membership。

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

完整情感、发声类型、9 个一级/39 个二级标签及其父子关系，以及自然语言判断标准、边界和学习示例，只维护在这份 Prompt Markdown。

相关代码：

```text
prompt_taxonomy.py
→ 解析 sentiments / voice_types / labels 机器 Taxonomy JSON
→ 校验合法性、唯一性与标签父子关系
→ taxonomy_sha256

prompt_snapshot.py
→ 冻结 Prompt/Taxonomy 身份
```

Python、数据库、前端和 Blueprint/Appendix 不维护第二套具体 AI 业务 Taxonomy 列表。

修改情感、发声类型、一级/二级标签、判断边界或学习示例时：

```text
Prompt 的自然语言规则 + 同文件机器 Taxonomy（需要改变合法值时）
→ Prompt/Validator tests
→ 固定输出 JSON 结构没有变化时，不修改 Python Contract 或数据库 Schema
```

`prompt_sha256` 标识完整 Prompt 变化；`taxonomy_sha256` 只随机器 Taxonomy 变化。因此只优化判断规则/示例时，可以出现 Prompt Hash 变化而 Taxonomy Hash 不变。

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

当前 Job 类型：

```text
analysis.content-run-plan.v1
→ Analysis Run Planner：在 PostgreSQL 中冻结 Run Target，并有界创建 Shard Job

analysis.content-label.v1
→ 对冻结的 Request/Shard 执行实际 LLM 分析并持久化结果
```

两类 Job 都由 `register_content_analysis_job()` 注册；`bootstrap/worker.py` 传入 Planner Handler，因此不能只把 `analysis.content-label.v1` 写成当前完整 Analysis Registry。

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
analysis_content_runs
analysis_content_run_targets
analysis_content_results
analysis_content_requests
analysis_content_request_items
analysis_content_label_pairs
analysis_content_relevance_reviews
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
POST /api/v1/analysis/content-runs/preview
→ 预检目标数和冻结的 Prompt/Taxonomy/Model/生成配置身份
→ 用户显式确认
POST /api/v1/analysis/content-runs
→ 短事务创建 analysis_content_runs + analysis.content-run-plan.v1 Planner
→ Planner 用 INSERT ... SELECT 冻结 run_targets 的 Content ID + Version
→ 校验 Preview 数量，变化时回滚并以可查询 error_code 失败关闭
→ 有界创建 analysis.content-label.v1 Shard Job
→ Worker
→ 校验实际 Prompt/Taxonomy/Provider/Model/生成配置与 Run 冻结身份一致
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

Current Analysis 先要求 Content Version 相同，再按 Analysis Run 的数据库创建顺序选择最新成功结果：

```text
content/version
analysis_content_runs.sequence_no
```

兼容入口 `POST /api/v1/content-analysis-requests` 为保持既有 `request_id/job_id` Response，仍同步冻结目标并创建首个 Shard；新版 Run API 不在 HTTP 请求内扫描或冻结海量目标。Planner 的 Target 冻结与首批 Shard 创建在同一事务，Lease 重试复用已提交的 Target/Shard。

不同 Run 的 Prompt/Taxonomy/Model/生成配置身份仍完整保存在 Run/Result 中。当前进程配置变化不会把已成功 Run 静默作废；尚未执行的 Shard 如果发现实际配置与冻结身份不同，会在调用 LLM 前以 `analysis_run_configuration_changed` 失败，不把新配置的结果写进旧 Run。最新 Run 失败或取消时，旧成功结果继续展示，API 另行返回最新 Run 状态。因此查询/声音广场可以区分：

Migration 0027 无法从旧 Request 还原当时实际 generation config，即使已有 Result 能推断 Prompt/Provider/Model，也不能把 `{}` 的回填哈希当作真实冻结配置。因此 `legacy-request:*` Run 保留兼容执行；Stage 12 新建 Run 全部严格执行上述调用前与持久化前双重校验。

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

模型原始 `analysis_content_results.relevance` 是不可被人工复核覆盖的审计事实。人工相关性决定保存到 `analysis_content_relevance_reviews` 追加账本，同一 Content Version 以递增 `review_no` 记录 `relevant / irrelevant / inherit_ai`，并用 `analysis_result_id` 保留操作所针对 AI Result 的精确来源。最新 `relevant/irrelevant` 覆盖业务有效相关性，`inherit_ai` 撤销覆盖并回到当前 AI 基线；直接从一种人工覆盖切换到相反覆盖必须先撤销。默认业务列表、`relevance` 筛选、查询型 Analysis target 和查询型 Export 都复用 `PostgresContentQueryRepository` 的同一有效相关性表达式。API 的 `effective_relevance / relevance_source` 是只读派生投影，因此当前 AI 进入 `stale` 后活动人工覆盖仍能被识别和撤销。Content 新版本不会继承旧人工决定。

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
→ Analysis Run / Planner / Shard Job
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
| 改情感 / `voice_type` / 一级二级标签合法值、判断标准、边界或学习示例 | 当前 Prompt + Prompt/Validator tests；固定输出结构未变时不改 Contract/DB Schema |
| 改 V3 输出结构 | Analysis Contract + Service/Validator + DB/API/Export/Frontend + Migration（需要时） |
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
analysis_content_runs / analysis_content_requests
→ Planner / Shard jobs
→ worker.log
→ analysis_content_run_targets / analysis_content_request_items
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

### 页面提示 LLM Runtime 未配置

先检查 `GET /api/v1/content-analysis-capabilities` 的 `configured`，再检查 Base URL、Model 和外部 `llm_api_key` 是否同时存在。源码开发 launcher 把 LLM Key 写入 `.runtime/secrets/llm_api_key`，并通过 `AIMA_EXTERNAL_SECRET_DIR` 暴露给 API/Worker；`.runtime/internal-secrets/` 只保存 PostgreSQL/Cursor Secret。能力接口和 Worker 必须使用同一个 `settings.external_secret_root`，不能分别读取不同目录。

### 页面 stale / 最新 Run 失败

```text
Content Version
→ 最新 Run Target/状态
→ 该版本最新成功 Result
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

当前声音广场已经提供 Analysis Run 预检、显式创建、历史列表和取消；这仍属于现有 voice-plaza Feature，不是独立管理中心。新版 Run 只接受显式选择的 1—1000 个 Content ID，查询范围 Run 暂不开放；兼容入口和历史数据仍可表达 query scope。默认 `AIMA_ANALYSIS_RUN_SHARD_SIZE=1` 与最大 1000 条边界都要等真实付费 Gold Set、费用和容量报告后才能重新决策。
