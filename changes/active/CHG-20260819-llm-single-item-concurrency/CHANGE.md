---
schema: rvc-change/v1
id: CHG-20260819-llm-single-item-concurrency
title: 单条内容 250 并发 AI 打标与可靠重试
level: L2
status: in_progress
owner: ChatGPT
branch: feature/llm-single-item-concurrency
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - analysis_offline_labeling
  - llm_adapter
  - imports_test
affected_paths:
  - backend/src/aima_ugc/modules/analysis/offline_labeling.py
  - backend/src/aima_ugc/modules/analysis
  - backend/src/aima_ugc/adapters/llm
  - backend/src/aima_ugc/adapters/providers/imports_test
  - tests/unit/analysis
  - tests/unit/collection
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
contracts: []
data_changes: none
---

# 目标

1. 当前离线真实模型路径改为“一条内容 = 一次独立 LLM 请求”，不再把 20 条内容拼入同一个请求。
2. `imports_test` 默认最大并发固定为 250，并保留一个明确 Python 配置项便于后续调整；同一时刻实际在飞请求不得超过该值。
3. 9 万条级别运行保持有界内存和高吞吐：不一次性把全部记录/Future 加入内存，不用批次屏障等待最慢请求，不让文件写锁成为 250 个 Worker 的竞争点。
4. 保持成功结果不重复打标：已有业务 Analysis 和与当前输入/Prompt/Taxonomy/Provider/Model 完全匹配的成功 checkpoint 均跳过真实请求；同一 deduplicated 输入不得产生重复模型提交。
5. Validation Retry 与 Transport Retry 分离：模型 HTTP 成功但本地校验失败时只重试当前单条；网络/429/可恢复 5xx 使用有界指数退避+jitter；401/402/400/422 等配置/账户/请求错误立即停止阶段。
6. 并发完成顺序不影响最终 `deduplicated/contents.jsonl` 顺序；checkpoint/attempt/failed 仍由单一协调者串行写入并先于业务 JSONL 发布。
7. 运行开始前先完成本地输入/身份/checkpoint/Prompt 预检，再产生付费请求；全部模型阶段结束后第二遍按原顺序原子回写业务 JSONL。
8. 共享 HTTPX Client 连接池容量跟随 250 并发并复用 keep-alive；同一 run 冻结 Prompt/Taxonomy 快照，避免 9 万次重复解析及运行中口径漂移。

# 成功标准

- [ ] `imports_test/test.py` 使用 `LLM_CONCURRENCY = 250`，不再使用 `LLM_BATCH_SIZE` 控制“每请求内容数”。
- [ ] 当前真实离线模型路径中，每次 `ContentLabelingService.label_contents()` 只收到 1 条 `CanonicalContentV1`，因此每个 Validation Attempt 只对应一个模型 item。
- [ ] 并发调度为有界滑动窗口，任意时刻提交中的 Future/请求不超过配置值；不预提交 90,000 个 Future。
- [ ] 输入全量预检发生在首次真实模型调用前；deduplicated 输入出现重复稳定身份或非法 JSONL 时 fail closed，不产生第二次重复模型提交。
- [ ] 250 并发时共享 HTTPX 连接池至少允许 250 connections/keep-alive connections；Client 仍复用且统一关闭。
- [ ] 网络错误、HTTP 408/429/500/502/503/504 进行最多 4 次额外 Transport Retry，并采用 exponential backoff + jitter；HTTP 400/401/402/403/404/422 和 Provider 协议错误不重试。
- [ ] Transport Retry 用显式外层组件实现；底层 `OpenAICompatibleContentLabelingLLM.complete()` 仍保持一次调用恰好一次 HTTP 请求。
- [ ] Validation Retry 继续由现有 `ContentLabelingService` 控制；单条失败只重试自己，不牵连其他成功条目。
- [ ] 任一 Transport/认证/余额等基础设施错误最终无法恢复时停止 Analysis 阶段，停止继续调度新内容；已经 durable checkpoint 的成功结果在下次运行直接恢复。
- [ ] 新成功结果按完成顺序先写 checkpoint 并 fsync；最终业务 JSONL 通过第二遍顺序扫描按原始行序回写并 `os.replace`。
- [ ] 已有 checkpoint 崩溃恢复测试继续成立：业务 JSONL 尚未发布但 checkpoint 已成功时，重新运行不再次调用 LLM。
- [ ] Prompt/Taxonomy 每个 run 只解析一次并作为不可变快照供所有并发请求复用。
- [ ] 目标并发/重试/顺序/防重复测试、现有 Analysis/P1 回归、Ruff、mypy、Contract drift、Architecture、Secret/Docs 和最终适用 GitHub Actions workflows 全部通过。

# 范围

- 离线 Analysis 编排并发化；
- OpenAI-compatible HTTP 连接池参数与错误分类；
- 显式 Transport Retry 包装层；
- Prompt/Taxonomy 快照复用；
- `imports_test` 的并发/重试配置与 README；
- Analysis README、Blueprint 15 长期规则；
- 单元/回归测试。

# 非目标

- 不修改 Canonical、ContentLabelAnalysisV2、UnifiedDataExcelV1 或数据库 Schema/Migration。
- 不启动 Stage 8，不实现正式 Analysis Job/API/PostgreSQL Repository。
- 不自动切换 DeepSeek 模型、Provider 或 API Key。
- 不修改 DeepSeek thinking mode；当前请求语义保持不变，性能优化只处理并发、连接池、重试和本地编排。
- 不承诺外部 API 在“服务端已处理但响应途中断线”的不可判定窗口绝对零重复计费；系统只接受一个合法 Analysis，并通过 durable checkpoint 缩小重复窗口。

# 必须保持不变

- Base OpenAI-compatible Adapter 一次 `complete()` 恰好一次 HTTP 请求，不隐藏自动重试。
- 本地 Validator、Prompt/Taxonomy 闭集、多标签 V2 Contract 和 Validation Retry 语义保持。
- 成功 checkpoint 的恢复身份仍绑定 `(platform, external_content_id, input_hash)` + Prompt/Taxonomy Hash + Provider + Model。
- 成功 checkpoint 先于业务 JSONL 发布；失败不填猜测 Analysis。
- 真实 Secret 不进入源码、日志、测试、Change 或 PR。

# 已确认关键决策

- 用户确认模型调用改为“一条内容一个请求”。
- 用户确认最大并发数直接使用 250，并要求同时考虑 90,000 条数据的性能和稳定性。
- DeepSeek 2026-08-19 官方文档当前显示 `deepseek-v4-pro` 账号级并发上限为 500；250 为当前上限的一半。429 仍可能因账号并发/RPM/TPM 触发，因此必须保留有界退避重试。
- HTTPX 官方文档确认同步 `Client` 可跨线程共享，默认 `max_connections=100`，因此必须显式扩到与 250 并发一致；不为本次任务引入 asyncio 全链重构。
- 采用 ThreadPoolExecutor + 共享 HTTPX Client：当前调用是 I/O bound，能复用现有同步 Port/Service/Validator，改动和回归风险显著小于把整个 Analysis 边界异步化。
- 采用“预检 → 并发请求/checkpoint → 顺序二次回写”三阶段，而不是按完成结果在内存做大规模 reorder buffer；这样并发槽位可持续补充且最终顺序天然稳定。

# 实施步骤

1. Red：新增并发、单条请求、250 配置、连接池和 Transport Retry 目标测试，确认当前实现因仍为批量串行/缺少能力而失败。
2. Green：实现显式 Transport Retry 包装层与 OpenAI-compatible 错误分类/250 连接池。
3. Green：重写离线编排为全量预检 + 250 有界滑动窗口 + 单写者 durable checkpoint + 第二遍顺序原子回写。
4. Green：增加 PromptTaxonomy 快照 Loader，当前 run 只解析一次 Prompt/Taxonomy。
5. 接入 `imports_test`：`LLM_CONCURRENCY=250`、`MAX_TRANSPORT_RETRIES=4`，移除批量请求配置。
6. 同步 Analysis/imports_test README 与 Blueprint 15。
7. 两阶段 Review，跑目标测试、全仓质量门禁和 PR workflows；全绿后正常 merge，随后单独归档 Change。

# 验证计划

- `uv run pytest tests/unit/analysis -q`
- `uv run pytest tests/unit/collection/test_p1g_imports_run_all.py tests/unit/collection/test_imports_test_run_directory.py -q`
- `uv run ruff format --check backend tests scripts`
- `uv run ruff check backend tests scripts`
- `uv run mypy backend/src`
- `uv run python scripts/contracts/generate.py --check`
- `uv run python scripts/quality/check_architecture.py`
- `uv run python scripts/quality/check_table_ownership.py`
- `uv run python scripts/quality/scan_secrets.py`
- `uv run python scripts/quality/check_docs.py`
- 最终 PR head 所有适用 GitHub Actions workflows 必须成功。

# 文档影响

- `backend/src/aima_ugc/modules/analysis/README.md`：当前真实离线执行模型、重试、checkpoint、并发与 Prompt 快照。
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`：用户配置、250 默认并发、失败/恢复说明。
- `docs/blueprint/15-舆情AI打标与统一分析契约.md`：长期 Analysis 执行/Transport/Checkpoint 边界。

# Git / PR 状态

- 分支：`feature/llm-single-item-concurrency`
- PR：待 Red 测试提交后创建 Draft PR。
