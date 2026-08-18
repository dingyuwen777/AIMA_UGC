---
id: CHG-20260818-p1-offline-excel-sentiment
title: 临时 P1 Excel 离线导入、去重与舆情 AI 打标
level: L3
status: in_progress
owner: AI coding agent
branch: feature/p1-offline-excel-sentiment
base_branch: main
created_at: 2026-08-18
updated_at: 2026-08-18
affected_paths:
  - docs/blueprint/README.md
  - docs/blueprint/07-技术决策与实施门禁.md
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - docs/blueprint/14-临时P1-Excel离线导入与舆情打标.md
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
  - backend/src/aima_ugc/adapters/llm/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - backend/src/aima_ugc/adapters/providers/tikhub_test/
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/contracts/analysis/
  - backend/src/aima_ugc/contracts/export/
  - backend/src/aima_ugc/platform/export/
  - contracts/analysis/
  - contracts/export/
  - scripts/contracts/
  - tests/unit/analysis/
  - tests/unit/collection/
  - tests/unit/platform/
  - .github/workflows/stage5a-provider-raw.yml
rollback:
  strategy: revert
  note: P1 未归档前统一回退本 Change 对应提交；不得修改数据库 Schema，不得覆盖其他 Active Change。
---

# 临时 P1 Excel 离线导入、去重与舆情 AI 打标

## 1. 目标与固定边界

Stage 1—7 已闭环，Stage 8 仍是正式下一阶段；P1 是 Stage 7 与 Stage 8 之间的临时最高优先级阶段。第一版不接数据库，业务中间事实源统一使用 JSONL。

固定主链：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ AI 打标
→ 本地结构/Taxonomy 校验
→ Validation Retry（有界）
→ analysis/checkpoints.jsonl
→ 原子回写同一个 deduplicated/contents.jsonl
→ labeled_data.xlsx
```

`analysis/checkpoints.jsonl` 只用于恢复、费用安全和审计，不是第二业务事实源；`raw_data.xlsx` 只是可选人工审阅旁路，不进入默认 `run_all()`。

数据边界保持：

```text
CanonicalContentV1 = Provider/平台可观察事实
UnifiedContentRecordV1 = content + matched_keywords + analysis
analysis = ContentLabelAnalysisV1 | null
```

Canonical 禁止增加 AI 标签。未来数据库中 `record.content` 归 Content Owner，`record.analysis` 归 Analysis Owner；不得把整条记录作为一坨 JSONB 写入 contents 表。

## 2. Prompt / Taxonomy / LLM 固定决策

唯一具体标签事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

Markdown 内唯一机器 Taxonomy JSON 使用 `AIMA_TAXONOMY_START/END` 标记。代码只做精确 JSON 提取、`json.loads`、Taxonomy 校验、`taxonomy_sha256`、完整 `prompt_sha256` 和运行时 membership/父子关系校验；不得解析自然语言表格猜闭集，也不得在 Python/Pydantic 复制具体标签 Enum、Literal、父子映射或第二份 taxonomy JSON。首版保持 Blueprint 15 的 9 个一级标签、39 个二级标签。

每条模型业务输入只允许：

```text
title
text
author.display_name
```

缺失填 `""`。临时 `item_no` 只做批次配对。内容 ID、平台、URL、指标、粉丝数、Provider、`matched_keywords`、源 Excel 情感、Raw locator 等不得发送。

模型每条固定返回 `item_no/sentiment/primary_label/secondary_label`。三个标签字段在 Contract 中使用 `str`，具体允许值由当前 PromptTaxonomy 动态校验。

本地 Validator 必须检查 JSON、固定/额外字段、item 数量/顺序/唯一性/配对、sentiment、primary、secondary→primary。非法输出不得模糊匹配、近义替换或程序猜值。

`max_validation_retries >= 0` 精确定义为额外 Validation Retry 次数：0/1/2 分别对应总模型请求最多 1/2/3 次。Validation Retry 与 Transport Retry 分离；同批已经成功的 item 不得因其他 item 失败重复调用。

## 3. imports / imports_test / Export 固定边界

正式 File Provider `backend/src/aima_ugc/adapters/providers/imports/` 只负责 XLSX → Reader/Profile/Identity/Mapper → `CanonicalContentV1`，不得承担关键词、去重、LLM、Excel 输出或数据库。

人工入口 `backend/src/aima_ugc/adapters/providers/imports_test/test.py` 保持单函数可独立调用；最终默认 `run_all()` 为 convert → filter → deduplicate → label → export labeled，`export_raw_excel()` 只为显式旁路。

长期只有 `UnifiedDataExcelV1 + backend/src/aima_ugc/platform/export/excel.py` 一套内容/评论 Excel Exporter；`tikhub_test`、`imports_test` 与未来正式导出共同复用。

性能保持既有 `openpyxl`；没有真实性能失败证据不引入 pandas。P1H 记录 90,000×13 的各阶段时间、rows/s、峰值 RSS 与文件大小。

## 4. 子阶段检查点

- [x] P1A：设计与阶段导航
- [x] P1B：Excel imports + imports_test + convert
- [x] P1C：关键词过滤 + UnifiedContentRecordV1 去重
- [x] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移
- [x] P1E：PromptTaxonomyLoader + Prompt + Analysis Contract/Service/Port + Fake + README + Retry tests
- [x] P1F：真实 OpenAI-compatible LLM Adapter + 最小输入 + Validation Retry + checkpoint + JSONL 原子回写
- [ ] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出
- [ ] P1H：90k 性能 + 真实模型小样 + Review/CI + 收口
- [ ] P1 全部结束后归档 Change、删除 Blueprint 14，并恢复 README 到 Stage 8 正式导航

**当前检查点：P1F 已闭环；下一最小正式单元为 P1G。不得在本轮继续进入 P1G。**

## 5. P1A—P1E 已闭环摘要

P1B 建立 `imports/` File Provider 和 `convert()`，使用 openpyxl read-only + `iter_rows(values_only=True)` 输出 Canonical JSONL；13 列 Profile、北京时间解释后转 UTC、稳定身份优先级、错误时不发布部分业务文件均有测试。

P1C 建立平台无关关键词过滤和 `(platform, external_content_id)` 去重；冲突 fail closed，filtered/deduplicated 都使用 `UnifiedContentRecordV1`，JSONL 临时文件 + flush/fsync + replace 原子发布。

P1D 建立 `UnifiedDataExcelV1` 与唯一共享 Exporter，并迁移 `tikhub_test`/`imports_test`；write-only Workbook、ID 文本化、URL、公式注入防护、北京时间展示和重新打开校验均有测试。

P1E 建立 `ContentLabelAnalysisV1`、唯一 Prompt/Taxonomy、`PromptTaxonomyLoader`、严格 Runtime Validator、`ContentLabelingService`/Port/Fake 和 Validation Retry；具体标签未复制到生产 Python。

P1E 最近专项证据：Stage 5A Run `32150865899` / Job `95756108571`，49 passed；Ruff/mypy、Analysis+Export Contract、Secret、Docs 成功；Architecture 只报告当时已有的 11 个 `operations/...` 缺失项。

## 6. P1F 已完成实现

P1F 在 P1E 的 Provider-neutral Port/Service 之上增加真实 OpenAI-compatible HTTP Adapter 和离线 JSONL 打标编排，没有修改 Prompt/Taxonomy 闭集、Canonical Contract、数据库或 Migration：

- `aima_ugc.adapters.llm.OpenAICompatibleContentLabelingLLM` 使用仓库既有 `httpx==0.28.1`，一次 `complete()` 恰好一次 `chat/completions` HTTP 请求；Adapter 不隐藏 Transport Retry；
- API key 使用 `SecretStr`，异常不回显 Secret 或 Provider body；`.env.example` 只保留空 key 示例；真实 `.env` 继续由根 `.gitignore` 忽略；
- 请求 system message 使用完整 Prompt；user message 只包含 P1E 已投影的 `item_no/title/text/author.display_name`，Validation Retry 时只附上一轮校验错误代码和重新返回当前批次的指令；
- 可选 JSON mode 只是 Provider 输出约束，本地 Validator 仍是最终成功门禁；
- `label_unified_content_jsonl()` 流式读取 `deduplicated/contents.jsonl`，按批调用正式 Service；失败 item 保持 `analysis=null`；
- 每次模型请求写 `analysis/attempts.jsonl`，包含 attempt、模型、prompt/taxonomy hash、时间、错误代码及可获得 token/费用；
- 通过本地 Validator 的成功 item 先追加 `analysis/checkpoints.jsonl` 并 flush/fsync，再写业务 JSONL 临时文件；
- `failed.jsonl` 只保存失败诊断，不伪造成功 Analysis；
- 完成后业务文件通过临时文件 + flush/fsync + `os.replace` 原子替换同一个 `deduplicated/contents.jsonl`；
- `imports_test.label_sentiment()` 默认 `ENABLE_REAL_LLM=False`，只有人工显式启用后才从 `.env` 建立真实 Adapter；`MAX_VALIDATION_RETRIES` 仍是唯一人工重试配置；
- P1F 不实现 `run_all()`、跨进程 checkpoint 恢复或最终 `labeled_data.xlsx`，这些属于 P1G。

## 7. P1F TDD 与新鲜验证

### 7.1 Red

Red commit：`79b44fd08b82ab97086be7d47a1467ec35e0f952`（`测试：锁定P1F真实模型与JSONL回写`）。

Stage 5A Run `32154648685` / Job `95768801659`：P1 pytest 退出码 2；新增 collection error 精确为缺少 `aima_ugc.adapters.llm` 和 `label_unified_content_jsonl`。依赖安装成功，Secret/Docs 同时成功，证明 Red 来自 P1F 尚未实现而不是环境或测试语法问题。

### 7.2 Green / Refactor

P1F 实现相对 Red 共 9 个后续提交，当前代码包括：

- `backend/src/aima_ugc/adapters/llm/openai_compatible.py` 与 `__init__.py`；
- `backend/src/aima_ugc/modules/analysis/offline_labeling.py` 与公共导出；
- `imports_test/test.py` 的 `label_sentiment()`、安全 `.env.example` 和 README；
- Stage 5A 对 `adapters/llm` 的触发、Ruff 和 mypy 覆盖；
- P1F 相关单元测试与阶段导航同步。

### 7.3 最新专项验证

当前 P1F head 前一文档检查点 `ada47610057d1aacbd0863f1df04d091cecdfd8a` 的 Stage 5A Run `32157763801` / Job `95779015906`：

```text
uv run pytest \
  tests/unit/collection/test_imports_excel.py \
  tests/unit/collection/test_imports_test_export.py \
  tests/unit/collection/test_tikhub_test_debug.py \
  tests/unit/analysis \
  tests/unit/platform/test_excel_export.py \
  -q
```

结果：退出码 0，`57 passed in 2.74s`。

```text
uv run ruff format --check <P1 scoped paths including adapters/llm>
uv run ruff check <P1 scoped paths including adapters/llm>
uv run mypy <P1 source paths including adapters/llm>
```

结果：退出码 0；Ruff `36 files already formatted`、`All checks passed!`；mypy `Success: no issues found in 24 source files`。

```text
uv run python scripts/contracts/generate.py
git diff --exit-code -- contracts/analysis contracts/export
uv run python scripts/contracts/generate.py --check
```

结果：退出码 0；Analysis/Export Contract 固定生成物同步。

```text
uv run python scripts/quality/check_architecture.py
```

结果：退出码 1；仍只报告 11 个既有 `ARCH001`，均为缺失 `backend/src/aima_ugc/operations/...` Stage 1—7 旧路径；P1F 的 `adapters/llm`、Analysis 和 imports_test 没有新增 Architecture 报错。

```text
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

结果：退出码 0；Secret 与 Docs gate 成功。

由于 Architecture step 失败，后续 Provider/Raw tests、Provider Contract drift 和整套 Stage 5A quality step 被 workflow 顺序跳过，不能记为本 head 已执行成功。

### 7.4 全仓 CI 状态

`ada4761...` 对应 11 个适用 PR workflow 均为 failure；Stage 5A 已确认 P1F 专项步骤成功、Architecture 为既有 11 个 `ARCH001`。其他工作流仍受仓库当前全仓基线问题影响，因此本轮不宣称 CI 全绿，也不绕过门禁。

## 8. 两阶段 Review

需求符合性 Review：通过 P1F 范围复核。

- 模型最小输入继续由 P1E Service 投影，Adapter 没有重新读取 Canonical 私有字段；
- Validation Retry 仍只由 Service 控制，Adapter 没有复制重试次数或标签闭集；
- 成功 Analysis 只有本地 Validator 通过后才进入 checkpoint 和业务 JSONL；
- checkpoint 先持久化再允许业务临时文件承载成功 Analysis；
- 真实模型默认关闭，不存在测试/CI 意外付费调用；
- 未进入 `run_all()`、跨进程恢复、最终 Excel 或 90k 性能阶段。

代码质量 Review：未发现阻塞 P1F 闭环的新增严重/重要问题。

- HTTP Client 生命周期可控，Adapter 不隐藏重试；
- Secret 不进入日志/异常或版本库示例；
- JSONL 采用流式读取和临时文件原子替换，不需要为 90k 行一次性构造完整业务文件内存副本；
- attempts/checkpoints/failed 与业务 JSONL 的角色分离明确；
- 没有新增依赖、数据库