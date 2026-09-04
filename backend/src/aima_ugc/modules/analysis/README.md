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

当前 `voice_type` 合法值集合不在本文复制。机器值直接使用中文业务名称，运行时唯一机器事实来自 Analysis Run 冻结的 Scheme Version；当前结果继续以字符串 `voice_type` 保存，由 `RuntimeTaxonomyValidator` 对冻结 Taxonomy 严格校验 membership。

真实用户发声唯一业务判断：

```text
voice_type == "真实用户发声"
```

不要再增加 `is_user_voice`/`is_real_user_voice` 平行字段。

---

## 2. Analysis Scheme 与 Git bootstrap

- [`backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md`](prompts/content_labeling_v3.md)
- [`backend/src/aima_ugc/modules/analysis/schemes.py`](schemes.py)
- [`backend/src/aima_ugc/modules/analysis/scheme_tables.py`](scheme_tables.py)

空数据库第一次读取 Analysis 配置时，会把 Git Prompt 转成一个已发布 Scheme Version 并记录系统审计。此后运行时唯一事实是数据库中唯一 active Scheme Version；Git Prompt 只负责 bootstrap/灾备，不与数据库双写。

一个 Scheme Version 原子包含 Prompt 模板、情感、发声类型、标签父子树和相关性/分类判断规则。模板只允许一个受控 Taxonomy 占位符；编译后再计算 `prompt_sha256 / taxonomy_sha256`。草稿保存追加新 Version，发布或回滚只切换完整版本，不能分别激活 Prompt 与枚举。

相关代码：

- [`backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py`](prompt_taxonomy.py)：解析并校验 sentiments / voice_types / labels 机器 Taxonomy JSON，计算 `taxonomy_sha256`。
- [`backend/src/aima_ugc/modules/analysis/schemes.py`](schemes.py)：编译受控模板并核对数据库快照 Hash。
- [`backend/src/aima_ugc/bootstrap/analysis_identity.py`](../../bootstrap/analysis_identity.py)：读取/初始化 active Version 并形成运行身份。

Python、前端和 Blueprint/Appendix 不维护第二套具体 AI 业务 Taxonomy 列表。

修改情感、发声类型、一级/二级标签、判断边界或学习示例时：

```text
管理员配置中心创建/保存完整 Scheme 草稿
→ 编译/Validator tests
→ 原子发布并写 audit_events
→ 只影响之后新建的 Analysis Run
→ 固定输出 JSON 结构没有变化时，不修改 Python Contract 或数据库 Schema
```

`prompt_sha256` 标识完整 Prompt 变化；`taxonomy_sha256` 只随机器 Taxonomy 变化。因此只优化判断规则/示例时，可以出现 Prompt Hash 变化而 Taxonomy Hash 不变。

声音广场通过 `GET /api/v1/content-analysis-taxonomy` 读取 active Scheme 的安全只读投影。生产装配在 [`backend/src/aima_ugc/bootstrap/content_http.py`](../../bootstrap/content_http.py)，投影函数在 [`backend/src/aima_ugc/bootstrap/analysis_taxonomy_http.py`](../../bootstrap/analysis_taxonomy_http.py)，Response 机器事实在 [`backend/src/aima_ugc/contracts/http.py`](../../contracts/http.py)。该接口不返回 Prompt 正文、自然语言规则、模型配置或 Secret；加载失败时返回统一 `503`，前端不会退回平行硬编码。

人工 `voice_type`、情感和标签只纠正当前 Content Version 已完成的 AI Result；无当前结果时不能创建平行人工分类。人工值按维度锁定并用于声音广场筛选/详情及后续导出，原始 `analysis_content_results` 始终不改写。

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
- 粉丝数；
- Raw 定位；
- 源 Excel 情感；
- 其他未批准元数据。

这样可以降低 token、减少无关信息干扰，并让 `input_hash` 和隐私边界可审计。

核心代码：

- [`backend/src/aima_ugc/modules/analysis/content_labeling.py`](content_labeling.py)：`ContentLabelingModelItem.model_payload()`

任何正式或离线高并发路径都继续保持：

```text
1 Content = 1 个独立逻辑 LLM 请求
```

不得通过把多条 Content 拼进一个请求来虚增吞吐。

---

## 4. 当前代码地图

### Contract

- [`backend/src/aima_ugc/contracts/analysis/content_label.py`](../../contracts/analysis/content_label.py)
- [`backend/src/aima_ugc/contracts/analysis/content_record.py`](../../contracts/analysis/content_record.py)
- [`backend/src/aima_ugc/contracts/administration.py`](../../contracts/administration.py)：Provider `max_concurrency / max_rps`

### Service / Validator

- [`backend/src/aima_ugc/modules/analysis/content_labeling.py`](content_labeling.py)

核心：

```text
ContentLabelingService
ContentLabelingLLMPort
RuntimeTaxonomyValidator
ContentLabelingLLMRequest
ContentLabelingLLMResponse
```

### 公共有界并发与自动 Shard

- [`backend/src/aima_ugc/modules/analysis/concurrent_labeling.py`](concurrent_labeling.py)：Offline / Formal 共用首批并发、bounded in-flight、`FIRST_COMPLETED`、停止调度和 backpressure。
- [`backend/src/aima_ugc/modules/analysis/sharding.py`](sharding.py)：根据 Run 冻结 Provider `max_concurrency / max_rps` 自动计算 Shard Size。

当前数据库 Provider 的默认计算规则：

```text
shard_size = clamp(min(max_concurrency × 20, max_rps × 900 秒〔仅配置 max_rps 时〕), 20, 50_000)
```

例如：

```text
max_concurrency = 250,  max_rps = null → shard_size = 5,000
max_concurrency = 1000, max_rps = null → shard_size = 20,000
max_concurrency = 1000, max_rps = 1    → shard_size = 900
max_concurrency = 250,  max_rps = 5    → shard_size = 4,500
```

Shard Size 是 Worker 内部调度参数，不在管理员界面单独配置。未配置 `max_rps` 时仍以 20 个并发波次为基线；配置 `max_rps` 时再用 900 秒物理 Attempt 启动预算收紧，低于 `analysis.content-label.v1` 的 1800 秒 Job timeout，为 Retry、数据库批量提交、Heartbeat 和取消留出余量。异常高重试仍可能触发 Job timeout，因此该预算不是吞吐承诺。计算结果在创建 Run 时写入 `analysis_content_runs.shard_size`，以后修改 Provider 不改变已创建 Run。

环境配置与数据库配置都使用同一自动分片公式和并发执行器。旧静态 `AIMA_ANALYSIS_RUN_SHARD_SIZE` / `AIMA_ANALYSIS_BATCH_SIZE` 已移除；环境配置的容量来自 `AIMA_LLM_MAX_CONNECTIONS`。

### 正式 Job

- [`backend/src/aima_ugc/modules/analysis/content_analysis_job.py`](content_analysis_job.py)

当前 Job 类型：

```text
analysis.content-run-plan.v1
→ Analysis Run Planner：冻结 Run Target，并有界创建 Shard Job

analysis.content-label.v1
→ 对冻结 Request/Shard 执行实际 LLM 分析并持久化结果
```

### 正式 Worker / Planner

- [`backend/src/aima_ugc/bootstrap/analysis_concurrent_worker.py`](../../bootstrap/analysis_concurrent_worker.py)：Provider `max_concurrency` 真正控制同时在途的单内容模型请求；首批即按容量并发；LLM worker thread 不持有数据库事务；完成结果在调度线程有界缓冲并短事务批量提交。
- [`backend/src/aima_ugc/bootstrap/analysis_high_throughput_planner.py`](../../bootstrap/analysis_high_throughput_planner.py)：`all` Scope 用连续 ordinal 恢复，下一 Shard 从 Run `shard_count` + 已调度 Request 序号推导，Terminal Callback 使用高吞吐 Run 统计。

正式 Registry 以 [`backend/src/aima_ugc/bootstrap/worker.py`](../../bootstrap/worker.py) 为准。

### PostgreSQL 表 / Repository

- [`backend/src/aima_ugc/modules/analysis/tables.py`](tables.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis.py`](../../adapters/persistence/postgres/analysis.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_batch.py`](../../adapters/persistence/postgres/analysis_batch.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_high_throughput.py`](../../adapters/persistence/postgres/analysis_high_throughput.py)

批量路径一个短事务内：

```text
一次 Job Fence 校验
→ 一次 Request/Job 归属校验
→ 一次 Current Version 批量读取
→ 多行 Analysis Result INSERT ... ON CONFLICT ... RETURNING
→ 批量 Label Pair 写入
→ executemany 更新 succeeded / failed / stale Request Item
```

1000 个 LLM in-flight 不对应 1000 个 PostgreSQL 连接。数据库写只发生在调度线程的短事务中；外部 LLM HTTP 始终在事务外。

### LLM Adapter

- [`backend/src/aima_ugc/adapters/llm/openai_compatible.py`](../../adapters/llm/openai_compatible.py)：一次 `complete()` 恰好一次物理 HTTP 发送。
- [`backend/src/aima_ugc/adapters/llm/rate_limited.py`](../../adapters/llm/rate_limited.py)：`max_rps` 限制物理 HTTP Attempt 的启动速率。
- [`backend/src/aima_ugc/adapters/llm/retrying.py`](../../adapters/llm/retrying.py)：显式 Transport Retry；每次 Retry 重新经过 RPS limiter。

### 离线执行

- [`backend/src/aima_ugc/modules/analysis/offline_concurrent_labeling.py`](offline_concurrent_labeling.py)：公共离线入口，复用 [`backend/src/aima_ugc/modules/analysis/concurrent_labeling.py`](concurrent_labeling.py) 并保留原 preflight/checkpoint/attempt/failed/rewrite 语义。
- [`backend/src/aima_ugc/modules/analysis/offline_labeling.py`](offline_labeling.py)：保留文件预检、checkpoint、原子回写和恢复 helper；旧独立调度循环已删除，离线入口只接受 `max_concurrency`，不再提供 `batch_size` 别名。
- [`../../adapters/providers/imports_test/`](../../adapters/providers/imports_test/)：人工/离线入口；DeepSeek 示例仍可配置 250。`label_sentiment()` 直接读取本地 `env.local`（由 [`env.local.example`](../../../../../env.local.example) 创建）和 Git Prompt，调用共用的并发核心并写入 JSONL/Excel，不初始化数据库；`WRITE_TO_DATABASE=False` 时整条离线流程保持无数据库运行。

---

## 5. 正式 PostgreSQL Analysis 调用链

```text
管理员 Provider 配置
→ Base URL / Model / API Key / max_concurrency / max_rps / timeout / Validation Retry
→ 新 Run 读取并冻结安全 Provider Snapshot

POST /api/v1/analysis/content-runs/preview
→ 预检目标数
→ 根据 Provider max_concurrency 计算 shard_size
→ 返回目标数、Shard 数、Scheme/Prompt/Taxonomy/Model/配置身份

POST /api/v1/analysis/content-runs
→ 短事务创建 analysis_content_runs + Planner Job
→ 冻结同一 Provider Snapshot 与计算后的 shard_size

Planner
→ selected/query 集合式冻结
→ all 按稳定 Content UUID keyset、每批短事务连续写 target_ordinal
→ 完成后核对 Preview target_count
→ 从 shard_count / 已调度 Request 连续序号推导下一批 Shard

Analysis Shard Worker
→ 加载 Run 冻结 Provider/Scheme
→ 校验 Prompt/Taxonomy/Provider/Model 身份
→ 本地预检后首批并发，不串行等待第一条
→ bounded concurrency，最大 in-flight = Provider.max_concurrency
→ 每条 Content 独立 ContentLabelingService 调用
→ max_rps 对每个物理 HTTP Attempt 生效
→ Transport Retry 仅重发当前 Content 的物理请求
→ Validation Retry 仍由 ContentLabelingService 处理当前 Content
→ 完成结果有界缓冲
→ 小任务或大任务尾部：已取完全部工作项且剩余未完成数不超过 max_concurrency，立即短事务提交
→ 其他阶段：满 200 条或首个结果等待约 1 秒即短事务提交
→ Heartbeat / Cancel / Job Fence
```

声音广场与任务中心共享 Analysis Run 状态和在途请求，活动 AI 每秒刷新，其他任务保持原周期。内容仅在状态或落库统计变化后刷新；终态后的最后结果和失败重试仍会补齐，不依赖人工点击刷新。

正式 `analysis_content_results` 仍只保存可复现 Analysis 身份和业务结果，没有新增 token/cost 列，也没有本次 Migration。

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

兼容入口 `POST /api/v1/content-analysis-requests` 为保持既有 `request_id/job_id` Response，仍同步冻结 selected/query 目标并创建首个 Shard；新版 Run API 不在 HTTP 请求内扫描或冻结海量目标。公开 `all` 使用内部专用快照标记，与历史空筛选 `query` 明确区分；Planner 分批短事务冻结全部 Content Current（包含 irrelevant），全部目标校验完成后才创建首批 Shard。Lease 重试从已提交 Target 的最后 Content ID 与连续 ordinal 续跑，避免重复扫描或重复计数已冻结批次。

不同 Run 的 Scheme Version、Prompt/Taxonomy/Model/生成配置和 Provider Runtime Snapshot 均完整冻结。发布新 Scheme 或修改 Provider concurrency 不会把已成功/已创建 Run 静默改写。

Migration 0027 无法从旧 Request 还原当时实际 generation config，因此 `legacy-request:*` Run 保留明确兼容执行；新 Run 严格执行调用前与持久化前身份校验。

```text
completed
stale
pending
```

相关查询：

- [`backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`](../../adapters/persistence/postgres/content_queries.py)
- [`backend/src/aima_ugc/bootstrap/content_http.py`](../../bootstrap/content_http.py)

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

模型原始 `analysis_content_results.relevance` 是不可被人工复核覆盖的审计事实。人工相关性决定保存到 `analysis_content_relevance_reviews` 追加账本，同一 Content Version 以递增 `review_no` 记录 `relevant / irrelevant / inherit_ai`。默认业务列表、筛选、查询型 Analysis target 和查询型 Export 继续复用同一有效相关性表达式。

---

## 8. Validation Retry、Transport Retry 与 RPS

### Validation Retry

```text
HTTP 已成功
→ 模型 JSON/字段/taxonomy 不合法
→ ContentLabelingService 对当前 Content 重新推理
```

管理员 Provider 的 `max_retries` 当前表示这类 **Validation Retry** 上限。

### Transport Retry

```text
连接/超时/408/429/部分 5xx
→ RetryingContentLabelingLLM
```

Base Adapter 一次 `complete()` 最多一次物理 HTTP 发送。Transport Retry 是显式 wrapper 的新物理 Attempt，不与 Validation Retry 共用计数器。

### max_rps

如果 Provider 配置 `max_rps`：

```text
每个物理 HTTP Attempt
包括 Transport Retry
→ 先经过 RateLimitedContentLabelingLLM
→ 再发送
```

这样 429/5xx 下不会因为 Retry 绕过限速形成请求风暴。

---

## 9. 正式模式与离线模式

### 正式模式

```text
PostgreSQL Content
→ Analysis Run / High-throughput Planner / Shard Job
→ Shared Bounded Executor
→ PostgreSQL Batch Result
```

### 离线模式

```text
Unified JSONL
→ Preflight / Checkpoint
→ Shared Bounded Executor
→ checkpoint / attempts / failed
→ 最终 JSONL / Excel / Word
```

两者复用：

```text
同一 Prompt / Taxonomy
同一 ContentLabelingService / Validator
同一单内容单请求语义
同一 bounded concurrency core
同一 OpenAI-compatible Adapter 能力
```

差异只在输入、恢复事实源和结果持久化：正式模式使用 PostgreSQL Job/Fence，离线模式使用 JSONL Checkpoint。

---

## 10. 修改不同问题时改哪里

| 需求 | 正确入口 |
| --- | --- |
| 改情感 / `voice_type` / 一级二级标签合法值、判断标准、边界或学习示例 | 管理员 Analysis Scheme 草稿 → 校验 → 发布；Git Prompt 只在要改变新环境 bootstrap 基线时同步 |
| 改 Scheme 编译、发布或回滚 | [`backend/src/aima_ugc/modules/analysis/schemes.py`](schemes.py) + Administration Service/Repository + Migration/API/审计/Integration tests |
| 改 V3 输出结构 | Analysis Contract + Service/Validator + DB/API/Export/Frontend + Migration（需要时） |
| 改模型/Base URL/API Key/模型并发/RPS | 管理员 Provider 配置 + [`backend/src/aima_ugc/contracts/administration.py`](../../contracts/administration.py) + [`backend/src/aima_ugc/bootstrap/runtime_config.py`](../../bootstrap/runtime_config.py) + `adapters/llm` |
| 改自动 Shard 策略 | [`backend/src/aima_ugc/modules/analysis/sharding.py`](sharding.py) + Preview/Create + Planner tests |
| 改网络 Retry | [`backend/src/aima_ugc/adapters/llm/retrying.py`](../../adapters/llm/retrying.py) + [`backend/src/aima_ugc/adapters/llm/rate_limited.py`](../../adapters/llm/rate_limited.py) + audit/retry tests |
| 改 Validation Retry | [`backend/src/aima_ugc/modules/analysis/content_labeling.py`](content_labeling.py) + Analysis tests |
| 改正式 LLM 并发 | [`backend/src/aima_ugc/modules/analysis/concurrent_labeling.py`](concurrent_labeling.py) + [`backend/src/aima_ugc/bootstrap/analysis_concurrent_worker.py`](../../bootstrap/analysis_concurrent_worker.py) |
| 改正式 Planner/Run 统计 | [`backend/src/aima_ugc/bootstrap/analysis_high_throughput_planner.py`](../../bootstrap/analysis_high_throughput_planner.py) + [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_high_throughput.py`](../../adapters/persistence/postgres/analysis_high_throughput.py) |
| 改批量数据库写 | [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_batch.py`](../../adapters/persistence/postgres/analysis_batch.py) + PostgreSQL integration |
| 改离线并发/Checkpoint | [`backend/src/aima_ugc/modules/analysis/offline_concurrent_labeling.py`](offline_concurrent_labeling.py) / [`backend/src/aima_ugc/modules/analysis/offline_labeling.py`](offline_labeling.py) + offline tests |
| 改数据库字段 | [`backend/src/aima_ugc/modules/analysis/tables.py`](tables.py) + 新 Alembic Migration + Repository + integration |

---

## 11. 排障顺序

### Analysis 一直 pending

```text
analysis_content_runs / planner Job
→ worker.log
→ analysis_content_run_targets 连续 ordinal
→ analysis_content_requests / Shard jobs
→ Provider snapshot max_concurrency / max_rps
→ analysis_content_request_items
```

### 吞吐明显低于直接 Python 调用

按顺序检查：

```text
Run runtime_config_snapshot.max_concurrency
→ 实际 peak in-flight / Provider latency
→ max_rps 是否主动限速
→ Transport/Validation Retry 数
→ PostgreSQL batch flush 延迟
→ Worker 是否持续有可处理 Shard
```

不要通过缩短前端轮询、单纯提高 `httpx.max_connections` 或增加大量通用 Worker 来冒充 LLM 并发提升。

### Job failed / partial_failed

```text
Job error / Request Item error_code
→ LLM Transport/Protocol
→ Validation Attempt
→ Batch Repository / Fence / Content Version
```

并发阶段单条可识别 Transport 错误只终结对应 Content，不把整个大 Shard 重新请求。

### 页面提示 LLM Runtime 未配置

先检查 `GET /api/v1/content-analysis-capabilities` 的 `configured`，再检查管理员默认 LLM Provider 的 Base URL、Model 和不可变 Secret 引用。数据库尚未创建过任何 LLM Provider 时，也可以由环境配置提供同一种 Provider；配置来源不改变分片和执行策略。

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

## 12. Analysis Run 的 selected / all 范围

声音广场正式 Run 的公共 Scope：

```text
selected
→ 1—1000 个显式 Content ID

all
→ 数据库当前全部 Content Current
→ 不受声音广场当前筛选或已加载分页影响
→ HTTP 请求不携带全量 Content ID
```

`all` 在 HTTP Contract 中是独立语义；服务端持久化时复用既有 `analysis_content_runs.scope = query`，并保存内部 all 快照标记。Planner 按稳定 Content UUID keyset、连续 `target_ordinal` 分批冻结 `content_id + current_version`。

所有配置来源的 Provider 下，Shard Size 不由用户配置，而由 Run 创建时冻结的 `max_concurrency` 自动推导；`analysis_content_runs.shard_size` 保存最终值，后续 Provider 修改不影响旧 Run。环境配置同样遵守上述规则。

---

## 13. 当前明确没有

- 评论 AI 打标正式业务能力；
- Analysis Result token/cost 数据库列；
- 独立 Analysis 管理中心页面；
- 统一 request/amount Budget Guard；
- Redis/Kafka/RabbitMQ/Celery 等第二任务系统；
- Monitoring/Alert/VOC/Ticket 业务域。

当前高吞吐实现仍使用同一个 PostgreSQL durable Job Runtime。1000 并发的代码容量由 Provider 配置、HTTP 连接池和 bounded executor 支持；某台真实服务器/模型部署是否能稳定跑满 1000，必须由对应部署环境的 CPU、内存、网络、Provider/GPU 与 PostgreSQL 压测证明，不能从 CI Runner 的线程测试推断。
