---
schema: rvc-change/v1
id: CHG-20260819-llm-single-item-concurrency
title: 单条内容 250 并发 AI 打标与可靠重试
level: L2
status: ready_for_review
owner: ChatGPT
branch: feature/llm-single-item-concurrency
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - analysis_offline_labeling
  - llm_adapter
  - imports_test
  - performance_benchmark
affected_paths:
  - backend/src/aima_ugc/modules/analysis
  - backend/src/aima_ugc/adapters/llm
  - backend/src/aima_ugc/adapters/providers/imports_test
  - scripts/performance/benchmark_p1_offline.py
  - tests/unit/analysis
  - tests/unit/collection/test_p1g_imports_run_all.py
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
contracts: []
data_changes: none
---

# 目标

1. 当前离线真实模型路径改为“一条内容 = 一次独立 LLM 请求”，不再把多条内容拼入同一个 DeepSeek/OpenAI-compatible 请求。
2. `imports_test` 默认最大并发固定为 `LLM_CONCURRENCY = 250`；同一时刻实际在飞请求不得超过该值。
3. 9 万条级别运行保持有界内存和高吞吐：不一次性创建 90,000 个 Future，不用批次屏障等待最慢请求，不让 250 个 Worker 并发写同一 audit/checkpoint 文件。
4. 保持成功结果不重复打标：已有业务 Analysis 和与当前输入/Prompt/Taxonomy/Provider/Model 完全匹配的成功 checkpoint 均跳过真实请求；重复稳定身份在模型调用前 fail closed。
5. Validation Retry 与 Transport Retry 分离：模型 HTTP 成功但本地校验失败时只重试当前单条；网络/429/可恢复 5xx 使用有界指数退避+jitter；认证/余额/请求/协议类不可恢复错误不做无意义重试。
6. 并发完成顺序不影响最终 `deduplicated/contents.jsonl` 顺序；checkpoint/attempt/failed 只由单一协调线程写，成功 checkpoint 先 durable，业务 JSONL 最后按原始行序原子回写。
7. 运行开始前先完成本地输入/身份/checkpoint/Prompt 预检，再产生真实模型请求；该预检只做完整性和防重复检查，不实现预算上限、费用阈值或 Token 预算停止功能。
8. 共享 HTTPX Client 连接池容量跟随 250 并发并复用 keep-alive；同一 run 冻结 Prompt/Taxonomy 快照，避免 90,000 次重复解析及运行中口径漂移。

# 成功标准

- [x] `imports_test/test.py` 使用 `LLM_CONCURRENCY = 250`，正式人工入口不再暴露 `LLM_BATCH_SIZE`。
- [x] 当前真实离线模型路径中，每次 `ContentLabelingService.label_contents()` 只收到 1 条 `CanonicalContentV1`，因此每个 Validation Attempt 只对应当前单条内容。
- [x] 并发调度为有界滑动窗口，任意时刻在飞 Future 不超过配置值；不会预提交 90,000 个 Future。
- [x] 输入全量预检发生在首次真实模型调用前；非法 JSONL 或重复稳定身份 fail closed。
- [x] canary 先只请求第一条待处理内容；401 等基础错误不会启动 250 并发扩散。
- [x] 250 并发时共享 HTTPX 连接池配置 `max_connections=250`、`max_keepalive_connections=250`；Client 复用并统一关闭。
- [x] 网络错误、HTTP 408/429/500/502/503/504 进行最多 4 次额外 Transport Retry，并采用 exponential backoff + jitter。
- [x] HTTP 400/401/402/403/404/422 和 Provider 成功 HTTP 下的协议结构错误不做 Transport Retry。
- [x] Transport Retry 用显式外层组件实现；底层 `OpenAICompatibleContentLabelingLLM.complete()` 仍保持一次调用恰好一次 HTTP 请求。
- [x] Validation Retry 继续由 `ContentLabelingService` 控制；单条失败只重试自己，不牵连其他成功内容。
- [x] Transport/认证/余额等基础设施错误最终无法恢复时停止继续调度新内容；已经 durable checkpoint 的成功结果下次运行直接恢复。
- [x] 新成功结果按完成顺序先写 checkpoint 并 fsync；最终业务 JSONL 第二遍顺序扫描后 `os.replace`，网络完成乱序不改变业务行序。
- [x] checkpoint 崩溃恢复测试继续成立：业务 JSONL 尚未发布但 checkpoint 已成功时，重新运行不再次调用 LLM。
- [x] Prompt/Taxonomy 每个 run 只解析一次，并作为不可变快照供并发请求复用。
- [x] 90,000 条生产链无网络基准实际完成，Analysis 峰值 in-flight 为 250，没有出现 Future 全量入内存或业务输出损坏。
- [x] 本次没有新增任何预算限制、费用上限或 Token 预算停止逻辑。
- [x] Analysis/Imports README 与 Blueprint 15 已同步当前多标签 V2、单条请求、250 并发、重试、防重复与预检语义。
- [x] 目标测试、Ruff、mypy、Contract drift、Architecture、Secret/Docs 和适用 GitHub Actions workflows 已通过。

# 范围

- 离线 Analysis 编排并发化；
- OpenAI-compatible HTTP 连接池参数和错误分类；
- 显式 Transport Retry 包装层；
- Prompt/Taxonomy 快照复用；
- `imports_test` 的并发/重试配置与 README；
- 90k 离线生产链 benchmark 的并发语义；
- Analysis README、Blueprint 15 长期事实；
- 单元/回归/性能验证。

# 非目标

- 不修改 Canonical、`ContentLabelAnalysisV2`、`UnifiedDataExcelV1` 或数据库 Schema/Migration。
- 不启动 Stage 8，不实现正式 Analysis Job/API/PostgreSQL Repository。
- 不自动切换 DeepSeek 模型、Provider 或 API Key。
- 不修改模型标签 Taxonomy 或多标签 V2 数据结构。
- 不新增预算上限、费用阈值、Token 预算或“达到费用后停止”功能。
- 不承诺外部 API 在“服务端已处理但响应途中断线”的不可判定窗口绝对零重复执行；系统只接受一个合法 Analysis，并通过 durable checkpoint 缩小重复窗口。

# 必须保持不变

- Base OpenAI-compatible Adapter 一次 `complete()` 恰好一次 HTTP 请求，不隐藏自动重试。
- 本地 Validator、Prompt/Taxonomy 闭集、多标签 V2 Contract 和 Validation Retry 语义保持。
- 成功 checkpoint 恢复身份继续绑定 `(platform, external_content_id, input_hash)` + Prompt/Taxonomy Hash + Provider + Model。
- 成功 checkpoint 先于业务 JSONL 发布；失败不填猜测 Analysis。
- 真实 Secret 不进入源码、日志、测试、Change 或 PR。

# 已确认关键决策

- 用户确认模型调用改为“一条内容一个请求”。
- 用户确认最大并发数直接使用 250，同时要求考虑约 90,000 条数据的性能和稳定性。
- 用户确认当前不需要预算限制功能；输入预检只用于完整性、防重复和 checkpoint 恢复判断。
- DeepSeek 2026-08-19 官方文档当前显示 `deepseek-v4-pro` 账号级并发上限为 500；250 为当前上限的一半。429 仍必须按运行时实际响应处理。
- HTTPX 同步 `Client` 可跨线程共享；默认连接池 100 不足以承载 250，因此自建 Client 时显式把 connection/keep-alive pool 扩到 250。
- 采用 `ThreadPoolExecutor` + 共享 HTTPX Client，不为本次 I/O-bound 离线任务把整个 Analysis Port/Service 改成 asyncio。
- 采用“全文件输入预检 → 单条 canary → 250 有界滑动窗口/checkpoint → 原序二次回写”三阶段，避免大规模 reorder buffer 和批次屏障。
- 旧 `batch_size` Python 参数仅保留内部兼容，解释成并发上限；正式 `imports_test` 和性能基准都改用 concurrency 命名，任何情况下一个模型请求只包含一条内容。

# 兼容 / Migration / 部署 / 回滚

- Canonical、Analysis V2 JSON Schema、Excel Contract、数据库和 Migration：无变化。
- 旧 Python 内部调用若仍传 `batch_size=N` 可继续运行，但语义改为“并发上限 N”，不再表示每次 LLM 请求包含 N 条内容。
- `.env` 不新增并发或预算配置；`imports_test/test.py` 顶部 `LLM_CONCURRENCY=250` 是当前人工入口配置。
- 部署顺序：普通代码合并即可，无数据库迁移或环境变量迁移。
- 回滚：正常 revert 本实现 PR；不会留下需要逆向 Migration 的数据结构变化。

# 性能与可靠性设计

```text
deduplicated/contents.jsonl
→ 完整输入预检
→ 恢复已有 analysis/checkpoint
→ 第一条 canary
→ ThreadPoolExecutor(max_workers=250)
→ 每个 Future 只处理一条 Content
→ 共享 HTTPX Client（pool=250）
→ 显式 Transport Retry
→ 本地 Validator / Validation Retry
→ 主协调线程写 checkpoint/attempt/failed
→ checkpoint 成功先 fsync
→ 模型阶段结束后按原 JSONL 顺序回写
→ temp + fsync + os.replace
```

输入文件按流扫描；不保留 90,000 个完整业务记录或 Future。预检需要保留稳定身份集合，checkpoint 恢复需要保留成功 checkpoint 索引，因此内存不是严格 O(250)，但 90k 实测峰值 RSS 在 GitHub Ubuntu runner 上约 296 MB。

# 验证证据

## Red

PR #86 早期 head：`4d30ac9fef6108958fe6343d037f905d0bf98ffa`

Stage 5A Provider Raw：`32234665994`

```text
4 failed, 86 passed
```

四个失败全部是目标能力尚不存在：

- 无 `LLM_CONCURRENCY=250`；
- `label_unified_content_jsonl()` 无 `max_concurrency`；
- OpenAI-compatible Adapter 无可配置 `max_connections`；
- 无显式 Transport Retry wrapper。

Secret/Docs 同轮通过，证明 Red 不是环境或 Secret 故障。

## Green 行为与质量

实现候选 head：`2a7d5674c19e4edfae44668504e2c8089448b1f8`

Stage 5A Provider Raw：`32238113080`，全部步骤 success，包括：

- P1 Excel/Analysis/Export tests；
- Ruff format/check；
- mypy；
- Analysis/Export Contract drift；
- Architecture；
- Secret/Docs；
- Provider/Raw；
- 全仓质量门禁。

新增回归覆盖：

- 单条请求；
- 250/可配置有界滑动窗口；
- 业务 JSONL 原序；
- 重复稳定身份模型调用前 fail closed；
- 401 canary 只请求一次；
- 429/503 Transport Retry；
- 401/402/422 fail fast；
- 真实 HTTPX Client 连接池容量；
- Validation Retry 只重试当前单条；
- checkpoint 崩溃恢复和已有 Analysis 跳过。

## 90,000 条专项性能验证

临时 workflow 已执行后删除，不进入最终 PR。

Workflow：`Temporary LLM Concurrency 90k`
Run：`32237609532`
Job：`96020967266`
结论：success。

实际输出：

```text
row_count = 90000
label_concurrency = 250
analysis llm_attempts = 90000
analysis_peak_in_flight = 250
pipeline_elapsed_seconds = 215.698
pipeline_rows_per_second = 417.25
peak_rss_bytes = 296001536
```

该 benchmark 使用生产 Excel→JSONL→filter→deduplicate→Analysis→checkpoint→原序回写→Excel 链路和无网络 Fake LLM，不调用 DeepSeek、不产生真实模型费用；因此它证明的是本地编排/内存/文件正确性，不宣称真实 DeepSeek 网络吞吐等于 417 rows/s。

## Blueprint 一致性

发现 Blueprint 15 遗留旧单标签文字和 `content_labeling_v1.md` 路径后，本轮同步为当前事实：

- `content_labeling_v2.md`；
- 一个情感 + N 个一级/二级标签对；
- 当前 imports_test 单条请求 + 250 并发；
- 输入预检不是预算控制。

同步 workflow：`32237920858`，结论 success；临时 workflow 已自删除。

## 标准 PR workflows

head `2a7d5674c19e4edfae44668504e2c8089448b1f8`：11/11 success。

- CI `32238113101`
- Stage 1-7 Audit Correctness `32238113060`
- Stage 5A Provider Raw `32238113080`
- Stage 5B Collection Execution `32238113046`
- Stage 5C Provider Persistence `32238113053`
- Stage 5D Provider Dispatch `32238113061`
- Stage 6 XHS Vertical Slice `32238113203`
- Stage 7 Keyword Packs `32238113122`
- Stage 7 Plan Occurrence Run Snapshot `32238113005`
- Stage 7 Provider Config Routing `32238113022`
- Stage 7 Scheduler Runtime `32238113200`

# 两阶段 Review

## 需求符合性

- 用户确认的一条内容一个请求和最大并发 250 已实现。
- 成功结果 checkpoint 防重复、单条 Validation Retry、Transport Retry、原序回写、run Prompt 快照均实现并有测试。
- 不包含预算限制功能。
- 90k 本地生产链专项验证成功。
- Canonical/Analysis V2/Excel/DB/Stage 8 未改变。

## 代码质量

- Worker 不写共享文件，audit/checkpoint 由主协调线程串行写，避免 JSONL 并发写损坏。
- 共享 HTTPX Client 与 Retry metrics 的线程安全边界明确；Retry metrics 使用 Lock。
- 并发窗口最多持有 250 个 Future；全量记录不入 Future 队列。
- checkpoint durable 先于业务 JSONL；最终二次顺序扫描天然消除网络完成乱序。
- fatal Provider/Transport 错误停止新调度，并尽量持久化已经提交任务中的成功结果。
- 未新增第三方依赖、Contract/Migration/Secret。

# 文档影响

- `backend/src/aima_ugc/modules/analysis/README.md`：单条请求、250 有界并发、两类 Retry、checkpoint、Prompt 快照、无预算控制。
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`：人工配置、运行、250 并发、防重复、错误恢复和指标说明。
- `docs/blueprint/15-舆情AI打标与统一分析契约.md`：修正多标签 V2 当前事实、Prompt V2 路径和离线单条并发执行边界。
- `scripts/performance/benchmark_p1_offline.py`：正式性能参数改为 `label_concurrency`，复用 frozen Prompt 快照并记录 `peak_in_flight`。

# Git / PR 状态

- 分支：`feature/llm-single-item-concurrency`
- Draft PR：#86 `将离线 AI 打标改为单条 250 并发`
- 实现尚未合并；只有最终 `ready_for_review` head 再取得新鲜标准 workflows 后才允许转 Ready/merge。
