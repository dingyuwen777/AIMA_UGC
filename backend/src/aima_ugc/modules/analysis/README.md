# Analysis 模块

`aima_ugc.modules.analysis` 负责**平台无关的内容 AI 分析**。

它回答的是：

```text
这条内容是否真正讨论电动车行业（包括爱玛与竞品）？
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

当前表格格式在持久化前要求内部 `source_type / content_intent / real_user_qualified`、各维度原文证据和 `decision_status`。它们供闭集、真实用户准入、表格组合及证据校验；对外结果仍是 V3。内部准入布尔字段不写入业务结果。

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

当前发声类型、情感、标签和判断标准直接维护在唯一 Markdown 中。程序直接校验、保存和查询文档中的实际分类值，不维护分类名称到另一套含义的映射。新增或改名发声类型时同时维护引用它的组合规则、正文及示例；新增或改名情感、标签时同步正文及示例。编译器拒绝重复名称、缺失引用、未覆盖组合和过期 JSON 示例，不会丢弃用户的判断说明。

---

## 2. Analysis Scheme 与 Git bootstrap

唯一编辑源是 [`backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md`](prompts/content_labeling.md)。[`backend/src/aima_ugc/modules/analysis/markdown_prompt.py`](markdown_prompt.py) 从六张定义表生成分类、父子关系和组合规则；自然语言指南与表格原样组成完整模型 Prompt。机器快照保存在 Scheme Definition 中，由 [`backend/src/aima_ugc/modules/analysis/schemes.py`](schemes.py) 管理双 Hash 和版本恢复。编译格式、输出协议与文档开头的内容修订号独立，改规则不要求每次升级程序。

维护操作：

1. 在 Markdown 中修改说明、发声类型、情感、两级标签或组合规则，同步正文与示例中的分类名称。保留六张定义表的标记和表头，说明单元格里的竖线写成 `\|`。
2. 在仓库根执行 `uv run python scripts/dev/compile_content_labeling.py`；可加 `--input <文件>` 和 `--output <生成 JSON>`。脚本复用生产编译器，不连接数据库或模型。生成 JSON 是校验产物，不是另一个编辑源。
3. 管理员配置中心导入 `.md` 或直接编辑完整 Markdown，保存草稿。服务端编译成功后回显只读分类和标签；错误保留当前生效版本。
4. 显式发布草稿后，仅后续新建 Run 使用新版本。运行中和历史 Run 使用创建时冻结的文本、编译快照及 Hash；回滚恢复完整历史版本。

Git 基线由首次配置读取建立 published/active Version。后续预览/创建 Run 仅对纯系统 Git lineage 的默认 Scheme 自动追加并激活新 Git Version；历史 Run 不阻塞刷新。出现其他未删除 Scheme、任何人工 Version 或显式回滚后，管理员发布成为生效路径，Git 文件修改不覆盖人工配置。

新格式无需 Taxonomy 占位符或手工机器 JSON。已经保存的 legacy v3.0 Version 保留旧编译及校验协议，按版本快照恢复；不把任意旧 Prompt 版本视为兼容。新格式恢复只读取已保存快照，禁止用最新 Markdown 或最新编译器重解释历史。`prompt_sha256` 标识完整文本，`taxonomy_sha256` 标识分类、组合和展示顺序；只调整自然语言解释可以只改变 Prompt Hash。

Scheme 复制、归档、恢复、条件删除继续复用既有生命周期；删除管理目录中的历史 Scheme 不删除已被 Run 引用的 Version。格式或结构输出协议变更属于代码变更，普通分类修改则通过相同发布链路生效。

声音广场人工纠正通过 `GET /api/v1/content-analysis-taxonomy` 读取 active Scheme 的安全只读投影；筛选下拉通过 `GET /api/v1/content-filter-options` 读取 active 分类与当前可见历史值的合并目录。历史值只用于检索，不进入 active Taxonomy。生产装配在 [`backend/src/aima_ugc/bootstrap/content_http.py`](../../bootstrap/content_http.py)，Response 机器事实在 [`backend/src/aima_ugc/contracts/http.py`](../../contracts/http.py)。接口不返回 Prompt 正文、自然语言规则、模型配置或 Secret；加载失败时返回统一 `503`，前端不会退回平行业务枚举。

人工 `voice_type`、情感和标签只纠正当前 Content Version 已完成的 AI Result；无当前结果时不能创建平行人工分类。人工值按维度锁定并用于声音广场筛选/详情及后续导出，原始 `analysis_content_results` 始终不改写。

---

## 3. 模型实际看到什么

`ContentLabelingService` 按冻结格式投影模型字段。当前只发送：

```text
platform
title
text
author.display_name
author.bio
author.verification_label
```

正式高并发路径为一条内容一个请求。`item_no` 只用于请求内输入输出配对，通常为 1；每个请求的 system 消息携带整个冻结 Prompt，user 消息携带 `{"items":[单条输入]}`。多个请求并发运行，不把多条帖子合成一个分析请求。`platform` 用于平台加作者名的官号白名单精确匹配，也参与内容输入 Hash；普通 evidence 仍只能来自其余五个文本字段，不能把平台名当证据。

不会发送：

- Content UUID；
- Provider 私有字段；
- URL；
- 点赞/评论数；
- 粉丝数；
- Raw 定位；
- 源 Excel 情感；
- 其他未批准元数据。

发给模型的字段全部作为不可信待分析数据处理；其中出现的提示、命令、URL 或“忽略规则”文字不得改变系统 Prompt 或输出协议。

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
- [`backend/src/aima_ugc/modules/analysis/adaptive_capacity.py`](adaptive_capacity.py)：新 Run 从成功入库速度派生 Shard Size；[`backend/src/aima_ugc/modules/analysis/sharding.py`](sharding.py) 保留历史固定 Snapshot 的算法。

历史固定协议的计算规则：

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

新 Run 的每片大小按历史成功吞吐、所需分片数和约 300 秒目标耗时派生，限制在 200–50,000 条，创建时写入 `analysis_content_runs.shard_size`。并发和资源边界见[共享自适应容量](#14-共享自适应容量)。冻结范围之后不随学习变化；`analysis.content-label.v1` 的 1800 秒 Attempt Deadline 仍是执行硬边界，恢复等待不能无限续期。

环境与数据库配置的新 Run 都使用同一自适应策略和并发执行器；环境里的旧人工执行值只供历史固定 Snapshot 兼容。旧静态 `AIMA_ANALYSIS_RUN_SHARD_SIZE` / `AIMA_ANALYSIS_BATCH_SIZE` 已移除。

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
- [`../../adapters/providers/imports_test/`](../../adapters/providers/imports_test/)：人工/离线入口；DeepSeek 示例仍可配置 250。`label_sentiment()` 直接读取本地环境配置（由 [`env.local.example`](../../../../../env.local.example) 创建）和 Git Prompt，调用共用的并发核心并写入 JSONL/Excel，不初始化数据库；`WRITE_TO_DATABASE=False` 时整条离线流程保持无数据库运行。

---

## 5. 正式 PostgreSQL Analysis 调用链

```text
管理员 Provider 配置
→ Base URL / Model / API Key；LLM 执行参数由系统管理
→ 新 Run 读取并冻结安全 Provider Snapshot

POST /api/v1/analysis/content-runs/preview
→ 预检目标数
→ 根据当前学习状态估计 shard_size；学习漂移不改变确认 hash
→ 返回目标数、Shard 数、Scheme/Prompt/Taxonomy/Model/配置身份

POST /api/v1/analysis/content-runs
→ 短事务创建 analysis_content_runs + Planner Job
→ 冻结连接身份、按历史派生的 timeout 和 shard_size

Planner
→ selected/query 集合式冻结
→ all 按稳定 Content UUID keyset、每批短事务连续写 target_ordinal
→ 完成后核对 Preview target_count
→ 从 shard_count / 已调度 Request 连续序号推导下一批 Shard

Analysis Shard Worker
→ 加载 Run 冻结 Provider/Scheme
→ 校验 Prompt/Taxonomy/Provider/Model 身份
→ 本地预检后首批并发，不串行等待第一条
→ 每秒刷新同 Provider/Model 跨 Run 的共享容量，分配有界本地目标
→ 每条 Content 独立 ContentLabelingService 调用
→ 动态 RPS 保护对每个物理 HTTP Attempt（含 Retry）生效
→ Transport Retry 仅重发当前 Content 的物理请求
→ Validation Retry 的单轮推理复用 ContentLabelingService，正式恢复由持久 Item ready-at 调度
→ 结构/Taxonomy 错误进入 repair；证据伪造、主体/意图/发声矛盾或 needs_judge 才进入条件 Judge
→ 已成功 Content 不随另一条复判而重发
→ 完成结果有界缓冲
→ 小任务或大任务尾部：已取完全部工作项且剩余未完成数不超过 max_concurrency，立即短事务提交
→ 其他阶段：满 200 条或首个结果等待约 1 秒即短事务提交
→ Heartbeat / Cancel / Job Fence
```

声音广场与任务中心共享 Analysis Run 状态和在途请求，活动 AI 每秒刷新，其他任务保持原周期。内容仅在状态或落库统计变化后刷新；终态后的最后结果和失败重试仍会补齐，不依赖人工点击刷新。

正式 `analysis_content_results` 仍只保存可复现 Analysis 身份和业务结果，没有新增 token/cost 列，也没有本次 Migration。

---

## 6. Analysis 为什么绑定 Content Version

成功 Result 永久保留实际分析的 Content Version、输入 Hash 和冻结的 Run 身份。正文或作者模型输入变化时，不能把旧 Result 的版本改成新版本，也不能复制成一次新的模型执行。

读取明确目标版本时，先按 `analysis_content_runs.sequence_no` 选择该版本的最新直接成功 Result。没有直接结果时，才读取 Analysis Owner 保存的等价复用关联。关联指向真实 Result，保留原 Prompt、Scheme、Model、生成配置和分析时间；它不代表发生了新模型调用。

等价证明只复用 [`backend/src/aima_ugc/modules/analysis/content_labeling.py`](content_labeling.py) 的 `content_labeling_input_hash()`：源不可变版本还原的生产 Hash、源成功 Result 实际保存的 Hash 与目标版本 Hash 必须一致，并且历史协议可证明兼容。输出格式版本本身不能证明输入协议；未知协议、失败结果或输入不同都不复用。连续版本直接指向原 Result，因此 `A → B → A` 不依赖递归复制相邻版本。

人工修正与模型原始结果分别读取。当前版本直接审核或解锁事实优先；否则使用关联中明确记录的等价历史人工来源。继承不新增人工操作，也不改历史账本。修改继承的锁定维度仍需显式解锁；当前版本 `inherit_ai` 撤销有效人工相关性覆盖，回到有效 AI 原判。直接重新分析继续保留既有人工锁语义。

补采及普通入库在 Content、Evidence 的同一事务内维护复用关联，不自动创建 Analysis Run。主动创建新 Run 仍冻结目标并正常调用模型。声音广场不会因为发布新 Prompt 就让全部历史成功结果失效；工作台继续限定其 active Scheme 范围。

版本作者输入来自 Content Owner 按观察字段及新鲜度合并的不可变快照，未观察的字段不会被稀疏详情清空；接受的作者模型输入变化有独立版本边界。AI Worker 持久化前锁定 Content，版本已变化时保留原 Run 的 stale 审计。统一来源选择、复用写入与冻结消费者入口分别为：

- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_effective.py`](../../adapters/persistence/postgres/analysis_effective.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_reuse.py`](../../adapters/persistence/postgres/analysis_reuse.py)
- [`migrations/versions/20261009_0083_analysis_version_reuse.py`](../../../../../migrations/versions/20261009_0083_analysis_version_reuse.py)

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

模型原始 `analysis_content_results.relevance` 是不可被人工复核覆盖的审计事实。人工相关性决定保存到 `analysis_content_relevance_reviews` 追加账本，同一 Content Version 以递增 `review_no` 记录 `relevant / irrelevant / inherit_ai`。默认业务列表、筛选、查询型 Analysis target 和查询型 Export 使用同一有效相关性来源选择；版本等价继承与直接撤销规则见上节。

---

## 8. Validation Retry、Transport Retry 与 RPS

### Validation Retry

```text
HTTP 已成功
→ 模型 JSON/字段/taxonomy 不合法
→ ContentLabelingService 对当前 Content 重新推理
```

新正式 Run 的 Validation Retry 没有固定轮数上限；每轮只处理 unresolved Item。历史 Run 的冻结 `max_retries` 和离线入口的显式上限继续有效。正式持久健康窗口和停止边界见[失败恢复](#15-正式-run-失败恢复)。

当前格式的 Validation Attempt 记录 `request_kind=primary/repair/judge`。Judge 不读取上一响应全文，只收到当前 unresolved item、稳定错误码、`platform` 与五个原始文本字段，并独立重新判断；同一轮同时出现结构错误与证据/协议问题时按 item 拆成 repair/judge 请求，每条 Content 仍只消耗一轮重试。没有触发校验错误的清晰内容保持单次调用。

### Transport Retry

```text
连接/超时/408/429/5xx
→ RetryingContentLabelingLLM
```

Base Adapter 一次 `complete()` 最多一次物理 HTTP 发送。Transport Retry 是显式 wrapper 的新物理 Attempt，每次逻辑调用最多四次重试（连同首次最多五次发送），不与 Validation Retry 共用计数器。新正式 Run 耗尽后仍 pending，按持久恢复协议重新探活；历史固定/离线协议继续遵守原终态边界。

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

### 4.1 代表性正负面内容筛选

代表性筛选是独立的离线入口，不改变正式 Analysis Result、数据库 Schema 或
[`backend/src/aima_ugc/adapters/providers/imports_test/test.py`](../../adapters/providers/imports_test/test.py) 的导入/打标/报告主流程：

- 读取一个或多个已打标 Excel 的 `内容` Sheet，按 `平台 + 内容ID` 跨文件去重；
- 只处理抖音和小红书，并且只从 `发声类型 = 真实用户发声` 且 `情感标签 = 正面/负面` 的记录中建立候选池；
- 使用 [`backend/src/aima_ugc/modules/analysis/prompts/zhengfu_shaixuan.md`](prompts/zhengfu_shaixuan.md) 在已有 `平台 + 发声类型 + 情感标签` 分组内选择代表性内容；不重新打标，不修改已有标签；
- 分别形成抖音正面、抖音负面、小红书正面、小红书负面四组，每组最多 10 条；严格筛选不足时保留实际数量，不用低质量内容凑数；
- 通过 [`backend/src/aima_ugc/adapters/feishu/bitable.py`](../../adapters/feishu/bitable.py) 以配置中的数据表作为模板，在同一 Base 内新建一个按生成时间命名的数据表，再写入本次结果；旧数据表和旧记录不更新、不删除。
- 写入字段严格按模板：原文列使用可点击链接，`典型评论示例`和`处理进展`留空；通过报告统一入口发布时，`处理建议`复用报告第 6 节的“行动建议”；一级/二级标签优先使用输入 Excel 已有值，缺少时留空。

运行入口：[`backend/src/aima_ugc/entrypoints/representative_selection_main.py`](../../entrypoints/representative_selection_main.py)

```powershell
uv run python -m aima_ugc.entrypoints.representative_selection_main `
  --input-xlsx "C:\path\to\douyin_labeled.xlsx" `
  --input-xlsx "C:\path\to\xiaohongshu_labeled.xlsx" `
  --prompt "backend\src\aima_ugc\modules\analysis\prompts\zhengfu_shaixuan.md" `
  --dry-run
```

该入口直接消费已经完成打标的 Excel，不会调用 [`backend/src/aima_ugc/adapters/providers/imports_test/test.py`](../../adapters/providers/imports_test/test.py) 的全量导入和打标流程。
每个文件都只读取 `内容` Sheet；多个文件按传入顺序合并，重复的 `平台 + 内容ID` 保留第一条。
合并后再按 `发声类型 = 真实用户发声` 且 `情感标签 = 正面/负面` 筛选，因此不会把其他发声类型或中性等非目标情感送入代表性筛选。

Dry Run 会在输入 Excel 同目录生成带时间戳的运行目录，包含候选、已有标签包装结果、最终选择、分组选择失败项、LLM 请求审计和 `selection_summary.json`；它不会请求飞书，也不会修改输入 Excel。确认结果后，可以在 `adapters/providers/imports_test/.env` 配置 `AIMA_FEISHU_APP_ID`、`AIMA_FEISHU_APP_TOKEN`（或 `AIMA_FEISHU_WIKI_TOKEN`）、`AIMA_FEISHU_TABLE_ID` 和外部 Secret 文件，再使用 `--write-feishu-from-run` 指向该运行目录，只同步已有 `selected_results.jsonl`，不会再次调用大模型。入口默认读取该 `.env`，也支持 `--env-file` 指定其他配置文件。若需要重新执行代表性选择并立即同步，才使用 `--write-feishu`。

飞书写入前会动态读取字段定义和已有记录，关键字段缺失、已有幂等键重复或字段类型无法安全转换时失败关闭；写入后会回读本次记录并核对写入字段。飞书字段不存在、类型不支持、原始数据为空或 URL/日期/单选值不合法时，该字段保持空白，其他可写字段仍按映射写入。写入前快照保存在本次运行目录中；程序不删除记录，也不清空未参与本次映射的字段。

---

## 10. 修改不同问题时改哪里

| 需求 | 正确入口 |
| --- | --- |
| 改情感 / `voice_type` / 一级二级标签合法值、判断标准、边界或学习示例 | 管理员 Analysis Scheme 草稿 → 校验 → 发布；Git Prompt 只在要改变新环境 bootstrap 基线时同步 |
| 改 Scheme 编译、发布或回滚 | [`backend/src/aima_ugc/modules/analysis/schemes.py`](schemes.py) + Administration Service/Repository + Migration/API/审计/Integration tests |
| 改当前表格输出协议或 Judge 路由 | [`backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md`](prompts/content_labeling.md) + [`backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py`](prompt_taxonomy.py) + [`backend/src/aima_ugc/modules/analysis/content_labeling.py`](content_labeling.py) + LLM Adapter + 当前格式/离线回归 |
| 改持久化 `ContentLabelAnalysisV3` 结构 | Analysis Contract + Service/Validator + DB/API/Export/Frontend + Migration（需要时） |
| 改模型/Base URL/API Key | 管理员 Provider 配置 + [`backend/src/aima_ugc/contracts/administration.py`](../../contracts/administration.py) + [`backend/src/aima_ugc/bootstrap/runtime_config.py`](../../bootstrap/runtime_config.py) |
| 改容量/Shard/Timeout 策略 | [`backend/src/aima_ugc/modules/analysis/adaptive_capacity.py`](adaptive_capacity.py) + Capacity Repository + Preview/Create + Worker/Planner tests；[`backend/src/aima_ugc/modules/analysis/sharding.py`](sharding.py) 保留历史固定策略验证 |
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
→ worker-*.log
→ analysis_content_run_targets 连续 ordinal
→ analysis_content_requests / Shard jobs
→ analysis_llm_capacity_profiles + Run 冻结 timeout/shard_size
→ analysis_content_request_items
```

### 吞吐明显低于直接 Python 调用

按顺序检查：

```text
Profile current / last_safe / reason
→ 实际 peak in-flight / Provider latency
→ 共享 RPS 是否主动限速，历史固定 Run 是否尚未排空
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

新正式 Run 的临时 Transport 错误进入持久 pending；系统硬错误或连续五分钟真实网络不可用停止父 Run。格式错误持续修复，429、HTTP 错误响应和本地等待不计断网。历史固定 Run 保留单条 Transport 耗尽终结对应 Content 的行为；已成功内容始终不重发。

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

## 12. Analysis Run 的 selected / query / all 范围

声音广场正式 Run 的公共 Scope：

```text
selected
→ 1—1000 个显式 Content ID

query
→ 当前已经应用的 ContentFilterSnapshot 命中全集
→ 不受声音广场分页、已加载条数或列表排序影响
→ HTTP 只提交筛选快照，不提交全量 Content ID

all
→ 数据库当前全部 Content Current
→ 不受声音广场当前筛选或已加载分页影响
→ HTTP 请求不携带全量 Content ID
```

`query` 和 `all` 在数据库都复用既有 `analysis_content_runs.scope = query`；`all` 继续用专用内部快照标记区分。Planner 对二者都按稳定 Content UUID keyset、连续 `target_ordinal` 分批冻结 `content_id + current_version`，全部冻结后才调度 Shard。

Query Preview 返回服务端权威目标数；用户确认 Create 时，服务端在一个 PostgreSQL Statement Snapshot 内重新统计并对 `content_id + current_version` 目标全集计算双 64-bit 聚合集合指纹，再把该指纹与筛选快照一起冻结到 Run。若 Preview 后数量已经变化，Create 返回 `content_analysis_target_changed`，前端重新 Preview 后必须由用户再次确认。Planner 虽然跨短事务分批读取，但结束时会对已冻结 Target 再计算同一集合指纹；数量相同但成员发生替换也会 fail closed，不会启动 Shard。历史没有指纹的 query Run 保持原数量核对兼容语义。

因此新 query Run 不需要跨全部批次持有长事务或单一 MVCC Snapshot，同时仍能证明 Planner 最终冻结集合与确认 Create 时集合一致；确认完成后的后续内容或 Analysis 变化不会改写已冻结目标。

新 Run 使用 `adaptive.v2`：Shard size 从历史成功入库速率与约 300 秒目标时长推导，并在 Create 冻结。没有历史时使用内部冷启动估计；运行中不修改已有 `shard_size` 或 `shard_no × shard_size` 范围。环境配置与数据库配置走同一规则；历史 Run 保留自己的快照。

---

## 13. 当前明确没有

- 评论 AI 打标正式业务能力；
- Analysis Result token/cost 数据库列；
- 独立 Analysis 管理中心页面；
- 统一 request/amount Budget Guard；
- Redis/Kafka/RabbitMQ/Celery 等第二任务系统；
- Monitoring/Alert/VOC/Ticket 业务域。
- 已人工复核的 Gold Set 与量化准确率门禁；当前没有依据调整模型、thinking 或生成参数。

当前高吞吐实现仍使用同一个 PostgreSQL durable Job Runtime。实际可用容量受 Worker、数据库和服务商限制，精确上限由下节实现维护。Simulator 只证明控制算法，不能证明实际模型或服务器的吞吐收益。

## 14. 共享自适应容量

规则在 [`backend/src/aima_ugc/modules/analysis/adaptive_capacity.py`](adaptive_capacity.py)，单表 Owner 在 [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_capacity.py`](../../adapters/persistence/postgres/analysis_capacity.py)，Worker 装配在 [`backend/src/aima_ugc/bootstrap/analysis_capacity.py`](../../bootstrap/analysis_capacity.py)。`analysis_llm_capacity_profiles` 按 Provider Config UUID + Model 保存当前 C、已确认/历史安全容量、拥塞上界、从属 RPS、吞吐/延迟、冷却和有限收敛状态。Revision 或 Prompt 变化保守热启动，旧身份反馈不覆盖新状态。端点从官方切换为未知时清除旧声明；切换到已核验端点时，新发容量受当前声明上界约束，旧在途预留仍排空。

控制器从有界初值指数探索，稳定后周期重探。已核验的官方端点/精确模型声明用于初值和上界，代理或未知模型继续从响应反馈学习；声明不等于账号实时可用额度。单次超时或低负载尾部不缩容，连续服务拥塞或并发 429 才退避；请求速率 429 优先收紧 RPS，未知 429 同时保守保护发送速率。健康恢复按经过秒数控制，不再等待三个随 P95 延长的窗口。当前阶段未完成的请求不作为该阶段容量证明；本地瓶颈也不写成模型 unsafe。成功吞吐无提升时仍保留平台判定与有限收敛。

控制版本3以同一档位的跨窗累计成功数/墙钟时间判断吞吐，结合已学习延迟和样本量形成证据块，连续两个不足收益的证据块才回退；单窗峰值不作基线。稀疏格式修复不重置升档，较多格式失败暂停探测但仍逐条严格修复。明确请求数/token的429响应优先于模型并发声明。具体形成条件与安全诊断字段见[AI实现专题](../../../../../docs/appendix/07_AI舆情打标与分析实现.md)。旧控制器升级只清除搜索证明，保留未过期物理/RPS预留，不需要新增Migration。

有效 Lease/Deadline 的运行分片跨 Run 共享整数份额，余数按稳定 Job ID 分配，允许零份额和尾部借出不用的额度。Profile 行锁原子预留，每秒刷新，本地许可约束每次物理发送及 Retry。C 与 RPS 在同一准入点都允许立即发送才占位，等待许可不预先消费发送时隙，也不计入物理在途。降档保留旧占用直到排空，退出仅删除本 Fence；崩溃/换 Fence 的旧占用到期后回收。HTTP 超时后上游是否还在执行未知，不能保证服务端绝无重叠。新 Run 每片物理上限 1024、全局保护上限 5000；实际值还受目标数和资源限制，不预建全部线程。历史 v1 保留 256 的冻结上限，固定 Run 保留原参数，新协议等待同 Provider/Model 的历史固定工作排空，终态回调唤醒待执行 Run。

HTTP 线程只更新有界计数、延迟桶和实际在途积分，调度线程持有 Job Fence 后合并共享墙钟窗。最短两秒且需足够结果，首批仍未完成时不误判健康；Profile 行锁保证同窗只推进一次，并发 Shard 不重复累计墙钟时间。阶段序号隔离旧请求反馈，最后一片退出清空不足窗的尾部和空闲分母。P95 是固定桶上界估计。成功吞吐只计事务提交后的新增 succeeded；stale、失败、取消和重复回调不计成功。物理 Attempt 与逻辑结果分母独立，pending 重试不能算成功。

容量学习需要未发送且当前可发送的工作，以及足以覆盖当前探测档位的实际占用。数据库 pending 中的在途请求、未提交结果和未来退避项都不当作新增需求；即使部分分片仍报告需求，明显未装满目标的共享窗口也不能更新吞吐基线或模型 unsafe。退避资格与实际取项使用同一查询规则。父 Run 已因最后一批结果变为终态时，分片先检查自身是否还有 pending，再判断探活资格，避免已完成的 Worker 等待到 Deadline。

Job 投放复用 `runtime.job_window()`，结合 Provider 需求、全局投放量、DB 连接余量与剩余分片；有后续分片时保留一个有界衔接位置，旧片等待慢尾请求时，新片可借用实际释放的共享许可，不提高 HTTP 总上限。每片 HTTP 许可再读取有效 CPU、实时可用内存、CPU 压力和结果事务吞吐，保留其他进程的内存余量；资源入口在 [`backend/src/aima_ugc/platform/capacity.py`](../../platform/capacity.py)。本地瓶颈按当前分片应得份额判断，不能把正常跨片分配误认为模型能力不足。零 DB 余量时保留一片持久 Job，压力恢复后仍可领取。

Windows 原生运行读取系统 CPU 差值与实时可用内存；Linux 容器优先按 cgroup v1/v2 的使用时间除以有效 CPU 核配额计算压力，避免宿主空闲掩盖容器饱和。配额变化、计数回退或缺失时先重建基线，不沿用旧压力或伪造零负载。更多核数和可用内存提供更大的探索空间，是否真正升档仍由模型响应、成功入库吞吐和压力护栏决定。同一代码不按操作系统设置固定机器档位。

正式进程池入口在 [`backend/src/aima_ugc/entrypoints/worker_main.py`](../../entrypoints/worker_main.py)。父进程分配稳定 Lease 身份并传给子进程，扩容和空闲缩容都按该身份匹配数据库 Lease；启动包装层 PID 和实际解释器 PID 只用于进程控制及诊断。`capacity.worker_process_spawned` 与 `worker.started` 可用同一 `worker_id` 对齐，分别查看启动 PID 和实际 `process_pid`。这样 Windows 虚拟环境启动器与 Linux 直接解释器都能准确计数忙碌 Worker。

v2 在创建时保存初始 Read Timeout：冷启动 120 秒，历史延迟可派生更短等待；运行中仅对下一次请求按成功 P95/真实 Read 或 Write 超时下界有界延长，最多 180 秒。Connect/Pool 超时另记阶段，不用于延长模型等待。历史 v1 的 Timeout 保持冻结。没有改变 thinking、reasoning effort、输出长度或 Prompt。代码回退到仅支持 v1 的版本前须排空 v2 Run，并按回滚流程重建派生 Profile JSON；不删除业务结果。

`analysis.capacity_window` 输出真实 `average_in_flight`、报告/接受的需求、当前阶段样本、成功吞吐、CPU 压力来源、限流分类和剩余冷却秒数；`analysis.capacity_adjusted` 记录目标与实际本地上限；执行收尾记录 HTTP 峰值和数据库/控制耗时。请求错误日志区分 Connect/Read/Write/Pool，不记录 Prompt 或响应正文。

LLM 管理 Create/Update 拒绝显式 timeout/retry/concurrency/RPS；这些字段只继续服务 Collection。LLM 页面每 3 秒读取安全只读投影，轮询不覆盖未保存草稿。学习不改变模型、Prompt、Taxonomy、生成参数或 Job timeout；新 Run 的 Primary/Repair/Judge 与持久恢复配合，详见下节。

## 15. 正式 Run 失败恢复

新 Run 在创建时冻结 `recovery.v2`：格式、字段、Taxonomy 和证据校验失败持续重试，没有五分钟截止；只有真实网络失败观测跨越五分钟且没有任何 HTTP 响应才停止。历史 `recovery.v1` 保持原冻结语义，旧失败 Item 不自动重新排队。详细计时、探活与兼容边界由[AI 实现专题](../../../../../docs/appendix/07_AI舆情打标与分析实现.md#295-正式-run-持久恢复)解释。机器入口为 [`backend/src/aima_ugc/adapters/persistence/postgres/analysis_recovery.py`](../../adapters/persistence/postgres/analysis_recovery.py)、[`backend/src/aima_ugc/bootstrap/analysis_concurrent_worker.py`](../../bootstrap/analysis_concurrent_worker.py) 和现有 Run/Request Item 表。

新任务只有成功数等于目标数才显示成功；打标期间内容版本变化产生的stale保留原事实，任务显示partial_failed/failed，不把旧标签写入新版本。pending和未投放内容继续推进，余额/鉴权等硬错误及手动取消仍显式停止。

退避项留在 PostgreSQL，只有 ready-at 到期才进入有界执行器；取消、Fence 与 Deadline 在等待期间仍持续检查。逻辑 Retry 不消耗新的 Job attempt；进程失权由原 Job 接管恢复。每次 Attempt 仍限 1800 秒、每个 Job 仍限三次；v2 周期因 Deadline 耗尽且仍有 pending 时，正式终态回调同事务创建后继 Job 并绑定原 Request。成功项、Item 身份和断点保留，旧 Fence/旧回调不能写后继结果，取消和终态 Run 不续接。恢复回归见 [`tests/integration/content/test_analysis_retry_recovery.py`](../../../../../tests/integration/content/test_analysis_retry_recovery.py)。

容量预留使用实际 HTTP 在途数，等待 Future 只表示待处理需求；没有 ready 或已派发工作时不保留最低一个份额。空闲份额连同余数可借给 ready 分片，旧 Fence 的未知占用继续保护。C 调整或 RPS 收紧切换发送阶段，迟到旧错误保留原始日志但不反复压低新容量；观察窗日志以 `control_*` 显示实际参与决策的错误数。

同一预留还保存本 Fence 的派生 RPS，Feedback 在同事务取得 C/RPS 后一次安装到本地联合准入。零 ready 分片归还未来发送速率；其他分片按实际可发送份额借额，不按活动 Job 数均分，也不按本机 C 占全局 C 的比例损失速率。所有新分配扣除 peer 尚未归还的旧承诺；需求恢复或全局降档通过后续刷新收敛，不能把其他进程旧许可当成已经归还。旧记录缺失 RPS 或旧 Fence 未过期时保守保护，控制版本升级保留原有承诺。每秒批量短事务，无逐 HTTP 数据库写入。
