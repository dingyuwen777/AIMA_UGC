---
schema: rvc-change/v1
id: CHG-20260819-llm-single-item-concurrency
title: 单条内容 250 并发 AI 打标与可靠重试
level: L2
status: done
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

# 结果

本 Change 已完成并合入 `main`。

当前 `imports_test` 真实 AI 打标执行模型：

```text
1 条内容 = 1 次独立 LLM 请求
最大同时在飞请求 = 250
```

没有把多条内容拼成同一次 DeepSeek/OpenAI-compatible 请求，也没有新增预算上限、费用阈值或 Token 预算停止逻辑。

# 已完成能力

- [x] `imports_test/test.py` 使用 `LLM_CONCURRENCY = 250`，正式人工入口不再暴露 `LLM_BATCH_SIZE`。
- [x] 每次真实离线 `ContentLabelingService.label_contents()` 只处理 1 条 `CanonicalContentV1`。
- [x] `ThreadPoolExecutor` 使用有界滑动窗口，最多 250 个 in-flight Future，不一次性提交 90,000 个 Future。
- [x] 模型调用前完整扫描 JSONL，检查结构、稳定身份、已有 Analysis 和可恢复 checkpoint。
- [x] 第一条待处理内容先做 canary；401/余额/请求配置类错误不会启动 250 并发扩散。
- [x] OpenAI-compatible 自建 HTTPX Client 使用 `max_connections=250`、`max_keepalive_connections=250` 并复用 keep-alive。
- [x] 新增显式 Transport Retry wrapper；Base Adapter 一次 `complete()` 仍恰好一次 HTTP 请求。
- [x] 网络错误、HTTP 408/429/500/502/503/504 最多额外重试 4 次，使用 exponential backoff + jitter。
- [x] HTTP 400/401/402/403/404/422 和 Provider 成功 HTTP 下的协议错误不做无意义 Transport Retry。
- [x] Validation Retry 继续由 `ContentLabelingService` 控制，单条校验失败只重试自己。
- [x] Worker 不并发写 checkpoint/audit 文件；主协调线程统一写入。
- [x] 成功 checkpoint 先 `flush + fsync`，再允许最终业务 JSONL 发布。
- [x] 全部模型阶段结束后按原始 JSONL 行序二次扫描并 `os.replace`，网络完成乱序不会改变业务记录顺序。
- [x] 每个 run 只解析一次 Prompt/Taxonomy，并通过 `FrozenPromptTaxonomyLoader` 复用同一不可变口径。
- [x] 已有业务 Analysis 和完全匹配的成功 checkpoint 不再次请求模型。
- [x] Blueprint 15 已从历史单标签/V1 Prompt 描述同步到当前多标签 V2，并明确当前离线单条 250 并发执行语义。
- [x] 90,000 条生产链专项 benchmark 已实际完成。

# 关键设计

```text
deduplicated/contents.jsonl
→ 模型调用前全文件输入预检
→ 恢复已有 analysis/checkpoint
→ 第一条 canary
→ ThreadPoolExecutor(max_workers=250)
→ 每个 Future 只处理一条 Content
→ 共享 HTTPX Client（pool=250）
→ 显式 Transport Retry
→ 本地 Validator / Validation Retry
→ 主协调线程写 checkpoint/attempt/failed
→ 成功 checkpoint 先 fsync
→ 模型阶段结束后按原 JSONL 顺序回写
→ temp + fsync + os.replace
```

“全文件输入预检”只表示在模型调用前检查本地输入完整性与防重复，不是预算控制。

# 兼容与边界

- Canonical：未修改。
- `ContentLabelAnalysisV2`：未修改。
- `UnifiedDataExcelV1`：未修改。
- 数据库 Schema / Migration：未修改。
- `.env`：未新增并发或预算变量。
- Stage 8：未启动。
- 旧内部 Python 调用如果仍传 `batch_size=N` 可以继续运行；兼容语义为“并发上限 N”，不再表示一次模型请求包含 N 条内容。
- 外部模型 API 如果已经执行请求但响应在网络途中丢失，而 Provider 没有业务幂等键，客户端无法数学上保证 Provider 端绝对零重复执行；系统通过成功 checkpoint 只接受一个合法 Analysis 并缩小重复窗口。

# Red 证据

PR #86 早期 head：

```text
4d30ac9fef6108958fe6343d037f905d0bf98ffa
```

Stage 5A Provider Raw：

```text
run 32234665994
4 failed, 86 passed
```

失败正是目标能力不存在：

- 无 `LLM_CONCURRENCY=250`；
- `label_unified_content_jsonl()` 无 `max_concurrency`；
- Adapter 无 `max_connections`；
- 无显式 Transport Retry wrapper。

Secret/Docs 同轮通过。

# Green 与质量证据

实现候选 head：

```text
2a7d5674c19e4edfae44668504e2c8089448b1f8
```

Stage 5A Provider Raw `32238113080` 全部步骤 success，包括目标测试、Ruff、mypy、Contract drift、Architecture、Secret/Docs、Provider/Raw 和全仓质量门禁。

最终 `ready_for_review` head：

```text
823d32fb4851f103289e327972312887c01e08b3
```

标准 PR workflows 11/11 success：

- CI `32238374008`
- Stage 1-7 Audit Correctness `32238373976`
- Stage 5A Provider Raw `32238374169`
- Stage 5B Collection Execution `32238374045`
- Stage 5C Provider Persistence `32238373985`
- Stage 5D Provider Dispatch `32238374060`
- Stage 6 XHS Vertical Slice `32238374001`
- Stage 7 Keyword Packs `32238374052`
- Stage 7 Plan Occurrence Run Snapshot `32238374085`
- Stage 7 Provider Config Routing `32238374057`
- Stage 7 Scheduler Runtime `32238373892`

主 CI 的 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 均 success。

# 90,000 条专项性能验证

临时 `Temporary LLM Concurrency 90k` workflow 在验证后已删除，不进入最终实现 PR。

```text
run = 32237609532
job = 96020967266
conclusion = success
row_count = 90000
label_concurrency = 250
analysis llm_attempts = 90000
analysis_peak_in_flight = 250
pipeline_elapsed_seconds = 215.698
pipeline_rows_per_second = 417.25
peak_rss_bytes = 296001536
```

该 benchmark 使用正式 Excel→Canonical→filter→deduplicate→Analysis→checkpoint→原序回写→Excel 链路和无网络 Fake LLM，不调用 DeepSeek，因此用于证明本地编排、内存和文件正确性，不代表真实 DeepSeek 网络吞吐。

# Blueprint / 文档证据

Blueprint 15 历史遗留的单标签描述和 `content_labeling_v1.md` 路径已修正为当前事实：

- `content_labeling_v2.md`；
- 一个 sentiment + N 个一级/二级标签对；
- 当前 `imports_test` 一条内容一次请求、最大并发 250；
- 输入预检不是预算限制。

Blueprint 同步 workflow `32237920858` success，临时 workflow 已自删除。

长期说明同步到：

- `backend/src/aima_ugc/modules/analysis/README.md`
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`
- `docs/blueprint/15-舆情AI打标与统一分析契约.md`

# Git / PR

实现 PR：#86 `将离线 AI 打标改为单条 250 并发`

```text
head = 823d32fb4851f103289e327972312887c01e08b3
merged = true
merge_commit = 97fd0fd9d0f7bd1e7ef1492684ea9503a570140c
```

归档 PR：待创建并通过适用 workflows 后合入 `main`。
