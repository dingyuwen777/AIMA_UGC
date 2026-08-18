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
  - docs/blueprint/
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
  - tests/unit/analysis/
  - tests/unit/collection/
  - tests/unit/platform/
  - .github/workflows/stage5a-provider-raw.yml
rollback:
  strategy: revert
  note: P1 未归档前统一回退本 Change 对应提交；不得修改数据库 Schema，不得覆盖其他 Active Change。
---

# 临时 P1 Excel 离线导入、去重与舆情 AI 打标

## 1. 目标与不变量

P1 是 Stage 7 与 Stage 8 之间的临时最高优先级阶段，不改变正式 Stage 编号。第一版不接数据库，业务中间事实源统一使用 JSONL：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ AI 打标
→ 本地结构/Taxonomy 校验
→ Validation Retry
→ analysis/checkpoints.jsonl
→ 原子回写同一个 deduplicated/contents.jsonl
→ labeled_data.xlsx
```

`analysis/checkpoints.jsonl` 只用于恢复、费用安全和审计，不是第二业务事实源；`raw_data.xlsx` 只是可选人工审阅旁路。

```text
CanonicalContentV1 = Provider/平台可观察事实
UnifiedContentRecordV1 = content + matched_keywords + analysis
analysis = ContentLabelAnalysisV1 | null
```

Canonical 禁止增加 AI 标签。未来数据库中 `record.content` 归 Content Owner，`record.analysis` 归 Analysis Owner；不得把整条统一记录作为一坨 JSONB 写入 contents 表。

## 2. Prompt / Taxonomy / LLM 固定决策

唯一具体标签事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

程序只精确提取其中 `AIMA_TAXONOMY_START/END` 机器 JSON，执行 `json.loads`、Taxonomy 校验、`taxonomy_sha256`、完整 `prompt_sha256` 和运行时 membership/父子关系校验。不得解析自然语言表格猜闭集，也不得在 Python/Pydantic 复制具体标签 Enum、Literal、父子映射或第二份 taxonomy JSON。首版保持 Blueprint 15 的 9 个一级标签、39 个二级标签。

每条模型业务输入只允许 `title`、`text`、`author.display_name`，缺失填空字符串；临时 `item_no` 只做批次配对。内容 ID、平台、URL、指标、粉丝数、Provider、`matched_keywords`、源 Excel 情感和 Raw locator 等不得发送。

模型每条固定返回 `item_no/sentiment/primary_label/secondary_label`。三个业务标签字段使用 `str`，具体允许值由当前 PromptTaxonomy 动态校验。本地 Validator 必须检查 JSON、固定/额外字段、item 数量/顺序/唯一性/配对、sentiment、primary 和 secondary→primary；非法输出不得模糊匹配、近义替换或程序猜值。

`max_validation_retries >= 0` 表示额外 Validation Retry 次数：0/1/2 分别对应总模型请求最多 1/2/3 次。Validation Retry 与 Transport Retry 分离；同批已经成功的 item 不得因其他 item 失败重复调用。

## 3. 子阶段检查点

- [x] P1A：设计与阶段导航
- [x] P1B：Excel imports + imports_test + convert
- [x] P1C：关键词过滤 + UnifiedContentRecordV1 去重
- [x] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移
- [x] P1E：PromptTaxonomyLoader + Prompt + Analysis Contract/Service/Port + Fake + README + Retry tests
- [x] P1F：真实 OpenAI-compatible LLM Adapter + 最小输入 + Validation Retry + checkpoint + JSONL 原子回写
- [ ] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出
- [ ] P1H：90k 性能 + 真实模型小样 + Review/CI + 收口
- [ ] P1 全部结束后归档 Change、删除 Blueprint 14，并恢复 README 到 Stage 8 正式导航

**当前检查点：P1F 已闭环；下一最小正式单元为 P1G。本轮不得继续进入 P1G。**

## 4. P1A—P1E 闭环摘要

P1B 建立 `imports/` File Provider 和 `convert()`，使用 openpyxl read-only + `iter_rows(values_only=True)` 输出 Canonical JSONL，并锁定 13 列 Profile、时间转换、稳定身份优先级和错误时不发布部分业务文件。

P1C 建立平台无关关键词过滤和 `(platform, external_content_id)` 去重；冲突 fail closed，filtered/deduplicated 都使用 `UnifiedContentRecordV1`，JSONL 通过临时文件 + flush/fsync + replace 原子发布。

P1D 建立 `UnifiedDataExcelV1` 与唯一共享 Exporter，并迁移 `tikhub_test`/`imports_test`；write-only Workbook、ID 文本化、URL、公式注入防护、北京时间展示和重新打开校验均有测试。

P1E 建立 `ContentLabelAnalysisV1`、唯一 Prompt/Taxonomy、`PromptTaxonomyLoader`、严格 Runtime Validator、`ContentLabelingService`/Port/Fake 和 Validation Retry；具体标签未复制到生产 Python。P1E 最近专项证据为 Stage 5A Run `32150865899` / Job `95756108571`：49 passed，Ruff/mypy、Analysis+Export Contract、Secret、Docs 成功；Architecture 只报告当时已有的 11 个 `operations/...` 缺失项。

## 5. P1F 实现

P1F 在 P1E Provider-neutral Port/Service 之上增加真实 OpenAI-compatible HTTP Adapter 和离线 JSONL 打标编排，没有修改 Prompt/Taxonomy 闭集、Canonical Contract、数据库或 Migration：

- `aima_ugc.adapters.llm.OpenAICompatibleContentLabelingLLM` 复用锁定的 `httpx==0.28.1`；一次 `complete()` 恰好一次 `chat/completions` HTTP 请求，Adapter 不隐藏 Transport Retry；
- API key 使用 `SecretStr`；异常不回显 Secret 或 Provider body；`.env.example` 只保留空 key 示例，真实 `.env` 继续由根 `.gitignore` 忽略；
- system message 使用完整 Prompt；user message 只包含 P1E 已投影的 `item_no/title/text/author.display_name`；Validation Retry 时只附上一轮错误代码和重新返回当前批次的指令；
- JSON mode 只是 Provider 输出约束，本地 Validator 仍是最终成功门禁；
- `label_unified_content_jsonl()` 流式读取 `deduplicated/contents.jsonl`，按批调用正式 Service；失败 item 保持 `analysis=null`；
- 每次模型请求写 `analysis/attempts.jsonl`；成功 item 先写 `analysis/checkpoints.jsonl` 并 flush/fsync，再写业务 JSONL 临时文件；失败诊断写 `analysis/failed.jsonl`；
- 完成后业务文件通过临时文件 + flush/fsync + `os.replace` 原子替换同一个 `deduplicated/contents.jsonl`；
- `imports_test.label_sentiment()` 默认 `ENABLE_REAL_LLM=False`，人工显式启用后才读取 `.env` 建立真实 Adapter；`MAX_VALIDATION_RETRIES` 仍是人工入口唯一 Validation Retry 配置；
- P1F 不实现 `run_all()`、跨进程 checkpoint 恢复或最终 `labeled_data.xlsx`，这些属于 P1G。

## 6. P1F TDD 与新鲜验证

### Red

Red commit：`79b44fd08b82ab97086be7d47a1467ec35e0f952`（`测试：锁定P1F真实模型与JSONL回写`）。Stage 5A Run `32154648685` / Job `95768801659`：P1 pytest 退出码 2；新增 collection error 精确为缺少 `aima_ugc.adapters.llm` 和 `label_unified_content_jsonl`。依赖安装成功，Secret/Docs 同时成功，因此 Red 来自 P1F 尚未实现。

### Green / Refactor

P1F 在 Red 后新增真实 LLM Adapter、`offline_labeling.py`、`label_sentiment()`、安全 `.env.example`、README、Stage 5A LLM 路径门禁和专项测试；当前 P1F 导航 head 为 `ada47610057d1aacbd0863f1df04d091cecdfd8a`。

### 最新专项验证

Stage 5A Run `32157763801` / Job `95779015906`：

- P1 目标/回归 pytest：退出码 0，`57 passed in 2.74s`；
- Ruff format：退出码 0，`36 files already formatted`；
- Ruff check：退出码 0，`All checks passed!`；
- mypy：退出码 0，`Success: no issues found in 24 source files`；
- Analysis + Export Contract drift：退出码 0；
- Secret / Docs：退出码 0；
- Architecture：退出码 1，仍只报告 11 个既有 `ARCH001`，均为缺失 `backend/src/aima_ugc/operations/...` Stage 1—7 旧路径；P1F 没有新增 Architecture 报错。

Architecture step 失败后，Provider/Raw tests、Provider Contract drift 和整套 Stage 5A quality step 按 workflow 顺序被跳过，不能记为本 head 已执行成功。

`ada4761...` 的 11 个适用 PR workflow 均为 failure，因此本轮不宣称全仓 CI 全绿，也不绕过门禁。

## 7. 两阶段 Review

需求符合性 Review：通过 P1F 范围复核。模型最小输入继续由 P1E Service 投影；Validation Retry 仍只由 Service 控制；成功 Analysis 只有本地 Validator 通过后才进入 checkpoint 和业务 JSONL；真实模型默认关闭；未进入 P1G/P1H。

代码质量 Review：未发现阻塞 P1F 闭环的新增严重/重要问题。HTTP Client 生命周期可控，Adapter 不隐藏重试；Secret 不进入异常或版本库示例；JSONL 使用流式读取和原子替换；attempts/checkpoints/failed 与业务 JSONL 角色分离；未新增依赖、数据库或 Migration。

## 8. 依赖、费用、Migration、回滚

- Python/Node/uv 版本保持仓库锁定版本；P1F 未新增、升级或降级依赖；复用 `httpx==0.28.1`；
- 无数据库写入、Migration、部署或生产数据迁移；
- 自动测试没有真实外部模型调用，真实 token/费用为 0；
- 实际人工启用真实 LLM 后，每次 Validation Retry 都会产生额外模型调用和费用；Adapter 不做隐藏 Transport Retry；
- 回滚方式为 revert P1F Adapter/离线打标/人工入口/测试/文档提交，不涉及数据库回滚。

## 9. Git / PR

- `main`：`0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`（本轮核验时）；
- branch：`feature/p1-offline-excel-sentiment`；
- Draft PR：#66，Open，未合并；
- P1F 已闭环；下一最小单元 P1G；
- 禁止直接推 main、自动合并、强制推送或新建平行 P1 Change。
