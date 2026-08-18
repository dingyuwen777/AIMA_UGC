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

## 1. 背景与原因

Stage 1—7 已闭环，Stage 8 仍是正式下一阶段；但当前需要插入一个最高优先级的临时 P1，用于把既有约 9 万行 Excel 舆情数据转换为 Canonical/统一内容 JSONL，执行关键词过滤、稳定身份去重、AI 情感与一级/二级标签分析，并最终导出统一 Excel 人工审阅文件。

本 Change 的约束是：

- P1 是临时阶段，不改变 Stage 8 的正式顺序；
- 第一版不接数据库，业务中间事实源统一使用 JSONL；
- `CanonicalContentV1` 只表示 Provider/平台可观察事实，不增加 AI 标签；
- `UnifiedContentRecordV1 = content + matched_keywords + analysis`；
- Analysis 标签事实源唯一来自 `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md`；
- Python/Pydantic 不复制具体标签枚举、Literal、父子映射常量或第二份 taxonomy JSON；
- P1 每个网页对话只闭环一个最小子阶段。

## 2. 固化业务决定

### 2.1 主链

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ AI 打标
→ 本地结构/Taxonomy 校验
→ Validation Retry（有界）
→ 成功 checkpoint
→ 原子回写同一个 deduplicated/contents.jsonl
→ labeled_data.xlsx
```

`analysis/checkpoints.jsonl` 只用于恢复、费用安全和审计，不是第二业务事实源。`raw_data.xlsx` 只是可选人工审阅旁路，不进入默认 `run_all()`；AI 不得依赖 raw Excel 回读。

### 2.2 Canonical / Unified Record / Analysis

```text
CanonicalContentV1
= Provider/平台可观察事实

UnifiedContentRecordV1
= content + matched_keywords + analysis
```

AI 成功后：

```text
analysis: ContentLabelAnalysisV1
```

未来数据库归属：

```text
record.content → Content Owner
record.analysis → Analysis Owner
```

禁止把整条统一记录作为一坨 JSONB 写入 `contents` 表。

### 2.3 Prompt / Taxonomy 唯一事实源

唯一标签事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

Markdown 中必须存在机器可读区块：

````markdown
<!-- AIMA_TAXONOMY_START -->
```json
{
  "schema_version": "aima-content-taxonomy.v1",
  "sentiments": ["正面", "中性", "负面", "混合"],
  "labels": {
    "...": ["..."]
  }
}
```
<!-- AIMA_TAXONOMY_END -->
````

代码流程固定：

```text
读取 Markdown
→ 精确提取 JSON 块
→ json.loads
→ 校验 taxonomy
→ taxonomy_sha256
→ 完整 prompt_sha256
→ 用当前 taxonomy 校验模型输出
```

自然语言表格不得用于猜测闭集。首版完整名称和判断标准以 Blueprint 15 为唯一设计事实源；当前为 9 个一级标签、39 个二级标签。

### 2.4 LLM 最小输入与固定输出

每条内容仅允许发送三个业务字段：

```text
title
text
author.display_name
```

缺失填空字符串。不得发送 ID、URL、平台/Provider、指标、`matched_keywords`、源 Excel 全文情感、Raw locator 或其他 Provider 私有字段。批量请求允许临时 `item_no` 配对，但它不是业务字段。

模型每条仅返回：

```json
{
  "item_no": 1,
  "sentiment": "...",
  "primary_label": "...",
  "secondary_label": "..."
}
```

`ContentLabelAnalysisV1` 的三个标签字段使用 `str`；具体值由当前 PromptTaxonomy 做 membership 和父子关系校验。

### 2.5 本地 Validator 与 Validation Retry

即使 Adapter 使用 JSON mode / structured output，也必须本地再次校验：

- Prompt Taxonomy 本身合法；
- JSON 可解析；
- 固定字段正确、无额外字段；
- `item_no` 数量、顺序、唯一性和配对正确；
- sentiment 属于当前 taxonomy；
- primary 属于当前 taxonomy；
- secondary 属于当前 primary。

非法输出不得模糊匹配、不得近义词替换、不得猜测补值、不得记成功。

生产 Analysis Service 接收：

```text
max_validation_retries: int >= 0
```

语义：

```text
0 = 总请求最多 1 次
1 = 总请求最多 2 次
2 = 总请求最多 3 次
```

Validation Retry 与网络重试分离。每次重请求都是独立 attempt，记录 attempt_no、错误代码、model/provider、prompt/taxonomy hash、时间及可获得的 token/费用。达到上限仍不合法时 `analysis_status = failed`，不得填猜测标签。

人工入口示例配置：

```python
MAX_VALIDATION_RETRIES = 2
```

### 2.6 imports / imports_test

正式 File Provider：

```text
backend/src/aima_ugc/adapters/providers/imports/
```

只负责 XLSX → Reader/Profile/Identity/Mapper → `CanonicalContentV1`，不得做关键词、去重、LLM、Excel 输出或数据库。

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/
├─ README.md
├─ .env.example
├─ test.py
└─ output/
```

`test.py` 顶部配置和函数边界按 Blueprint 14 固化；默认 `run_all()` 最终应为 convert → filter → deduplicate → label → export labeled，`export_raw_excel()` 只为显式旁路。

### 2.7 共享 Excel Exporter

长期只有：

```text
UnifiedDataExcelV1
+
backend/src/aima_ugc/platform/export/excel.py
```

`tikhub_test`、`imports_test` 和未来正式导出都必须复用该 Exporter；不得保留平行内容+评论 Workbook 生成逻辑。

### 2.8 性能

保留既有 `openpyxl`，没有真实性能失败证据时不引入 pandas。P1H 必须记录 90,000×13 的读取/转换、筛选、去重、JSONL AI 回写、最终 Excel 时间、rows/s、峰值 RSS 和文件大小。

## 3. 成功标准

- [x] P1A：设计与阶段导航固化；
- [x] P1B：Excel imports + imports_test + convert；
- [x] P1C：关键词过滤 + `UnifiedContentRecordV1` 去重；
- [x] P1D：`UnifiedDataExcelV1` + 唯一共享 Exporter + tikhub_test 迁移；
- [ ] P1E：PromptTaxonomyLoader + 完整 Prompt + Analysis Contract/Service/Port + Fake + README + Retry tests；
- [ ] P1F：真实 OpenAI-compatible LLM Adapter + 最小输入 + Validation Retry + checkpoint + JSONL 原子回写；
- [ ] P1G：`run_all()` + 崩溃恢复 + 最终同源 JSONL 导出；
- [ ] P1H：90k 性能 + 真实模型小样 + 全链路 Review/CI + P1 收口；
- [ ] P1 全部结束后归档 Change、删除 Blueprint 14，并恢复 README 到 Stage 8 正式导航。

## 4. 子阶段检查点

- [x] P1A：设计与阶段导航
- [x] P1B：Excel imports + imports_test + convert
- [x] P1C：关键词过滤 + UnifiedContentRecordV1 去重
- [x] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移
- [ ] P1E：PromptTaxonomyLoader + Prompt + Analysis Contract/Service/Port + Fake + README + Retry tests
- [ ] P1F：真实 LLM Adapter + 最小输入 + Validation Retry + checkpoint + 原子回写
- [ ] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出
- [ ] P1H：90k 性能 + 真实模型小样 + Review/CI + 收口

**当前检查点：P1D 已闭环；下一最小正式单元为 P1E。不得在本 Change 未闭环时跳到 Stage 8。**

## 5. P1B 已完成证据

P1B 建立了正式 `imports/` File Provider 与 `imports_test/test.py` 的 `convert()` 人工入口，使用 `openpyxl` read-only + `iter_rows(values_only=True)` 把指定 Excel Profile 转为 `CanonicalContentV1` JSONL；不接数据库、不做关键词/去重/LLM/Excel 输出。

关键行为：

- 13 列 Profile 校验，缺列关闭失败；
- 日期按 `Asia/Shanghai` 解释并转 UTC；
- 身份优先平台 URL 原生 ID，其次文章编号，再次规范化 URL SHA-256；
- 无稳定身份拒绝该行；
- 业务 JSONL 原子发布；有转换错误时不发布部分成功业务文件；
- 源 Excel “全文情感”不写入 Canonical Analysis。

TDD Red commit：`618459b680946554142f01d6fe054f94d5c23593`。

P1B 代码/文档提交：`c3e6d240e7f69936f7cb86a4d4c02518b69367cb`、`77ade299145d1be5be8d7f2130673b318693d5934`。

P1B 专项 CI：Run `32137347850` / Job `95711612819`：7 passed；Ruff format/check、mypy、Analysis Contract drift、Secret、Docs 均通过；Architecture 因仓库既有 11 个 `ARCH001` 缺 `operations/...` 路径失败。

## 6. P1C 已完成证据

P1C 新增 `UnifiedContentRecordV1` 与平台无关的离线过滤/去重生产函数：

- 过滤仅匹配 `title + text`，按配置顺序保存全部 `matched_keywords`；
- 空关键词/非法 JSONL/Contract 错误关闭失败；
- 去重键严格为 `(platform, external_content_id)`；
- 除 `content.source.item_locator` 外完全等价才视为重复；
- 同稳定身份其他字段不同则记录安全冲突并不发布部分 deduplicated 业务 JSONL；
- filtered/deduplicated 均使用 `UnifiedContentRecordV1`，`analysis=null`；
- 写入通过临时文件 + flush/fsync + replace 原子发布。

TDD Red commit：`8879f91a6313dfa13362ab0097374920b0ebd8e8`。

P1C Green/文档提交：`720e56d80a03b6e11e80a1f295da9e7ca0565879`、`b27949d679a6d092b5fa3813421981fd3af95add`、`064986fe16c25bed4fabda8694882393969f0299`、`d68e35925f759dd121793bfe85f2d3710d91eda3`。

P1C 专项 CI：Run `32137874253` / Job `95713331554`：9 passed；Ruff format/check、mypy、Analysis Contract drift、Secret、Docs 均通过；Architecture 仍因同一 11 个既有 `ARCH001` 失败。

## 7. P1D 已完成证据

P1D 建立了 Provider-neutral 的 `UnifiedDataExcelV1` 与唯一共享 Excel Exporter，并把 `tikhub_test`、`imports_test` 收口到同一导出实现：

- 新增 `backend/src/aima_ugc/contracts/export/` 和固定生成物 `contracts/export/unified-data-excel.v1.schema.json`；
- 新增唯一共享实现 `backend/src/aima_ugc/platform/export/excel.py`；
- 工作簿固定为 `内容`、`评论` 两个 Sheet，raw/labeled 共用同一列 Schema；
- Canonical 通过显式 projection helper 转为 Excel Contract，不向 `CanonicalContentV1` 增加 AI/展示字段；
- Analysis 占位字段是普通 `str`，没有具体标签 Enum/Literal/父子映射；
- `imports_test.export_raw_excel()` 只读取 `deduplicated/contents.jsonl`，不会回读源 XLSX，也不进入默认主链；
- `tikhub_test/core/excel.py` 已删除，TikHub 调试只投影 Canonical/评论/coverage/raw locator 并调用共享 Exporter；
- 共享 Exporter 使用 write-only Workbook，ID 强制文本、HTTP(S) 超链接、公式注入防护、北京时间展示，并在替换最终文件前重新打开检查 Sheet、表头、行数和关键 ID；
- 没有引入 pandas、LLM、数据库、Migration 或 `run_all()`。

### 7.1 初始 TDD Red

Red commit：`78810b47439745cc4c487b43d68a705c96ae4e2e`（`测试：锁定P1D统一Excel导出行为`）。

CI Run `32139833333` / Job `95719627231`：共享导出测试按预期因 `ModuleNotFoundError: No module named 'aima_ugc.contracts.export'` 在 collection 阶段失败，证明测试确实锁定了尚未实现的 P1D Contract/Exporter。该次同时暴露 `test_tikhub_test_debug.py` 的既有 `TikHubTestConfig` 公共导入错误；该错误与 P1D Excel 行为无关，未被当作 Red 成功依据，后续仅把测试改为从真实模块路径导入。

### 7.2 Green / Refactor

核心实现与测试提交：

- `d755ca3ed2cf60e0ba4ddf2baf366f7819312dad`：实现 P1D 统一 Excel 导出核心；
- `551c38dc875019d82b39a4289792d7f77e5b7bc9`：修正测试按扁平 Export Contract 构造；
- `07a82339521faa002cea439a267de61de529eeaa`、`be37a4fbfd1bc49a96f78e89546c7e12b9385ee8`：只按 Ruff 结果整理格式；
- `b8b213882f7f31727b497d76d7aefcc434f8cc4e`：收窄 Excel 单元格类型，解决 mypy 边界；
- `adb315fc020bbc437c10ff313eebcc131319e4b7`：同步 Export Schema 生成语义及 imports/tikhub_test README。

### 7.3 Review 回归 Red → Green

代码质量 Review 发现：Workbook 已成功写入临时 `.tmp.xlsx` 后，如果“重新打开校验”阶段抛异常，旧实现会遗留临时文件。该问题不会发布最终目标文件，但会给人工调试/后续运行留下无意义中间产物，因此按 TDD 补回归并修复。

回归 Red commit：`8afdf7777714f8c37fb7f51856b46c02724373a5`（`测试：覆盖P1D导出验证失败清理`）。

Red Stage 5A Run `32143537815` / Job `95731685410`：目标测试退出码 1，`1 failed, 18 passed in 2.54s`；唯一失败为 `test_shared_exporter_cleans_temp_file_when_reopen_verification_fails`，断言 `.raw_data.tmp.xlsx` 不存在时失败，证明缺陷因正确原因复现。

Green commit：`920c75c9117e0a4c4e2450b1d917e7df116dadf3`（`修复：清理P1D导出验证失败临时文件`）。实现仅把 post-save 验证与 `os.replace` 包进同一异常清理边界：失败时删除临时文件并原样重新抛出异常；最终目标在验证成功前仍不被替换。

接口文档/Contract 同步 commit：`18f3a1a1941d331ccc5c6a3d7e65f58e2db522ca`（`契约：补齐P1D统一Excel接口文档`）。恢复 Export 公共 Pydantic Contract 的 PEP 257 docstring，并同步 `contracts/export/unified-data-excel.v1.schema.json` 的生成描述；字段、标签类型、Workbook Schema 均未改变。

P1D 最新代码专项证据：Stage 5A Run `32143868628` / Job `95732774015`：

```text
uv run pytest \
  tests/unit/collection/test_imports_excel.py \
  tests/unit/collection/test_imports_test_export.py \
  tests/unit/collection/test_tikhub_test_debug.py \
  tests/unit/analysis/test_offline_content_processing.py \
  tests/unit/platform/test_excel_export.py \
  -q
```

结果：退出码 0，`19 passed in 2.78s`。

```text
uv run ruff format --check <P1D paths>
uv run ruff check <P1D paths>
uv run mypy <P1D source paths>
```

结果：退出码 0；Ruff `24 files already formatted`、`All checks passed!`；mypy `Success: no issues found in 18 source files`。

```text
uv run python scripts/contracts/generate.py
git diff --exit-code -- contracts/analysis contracts/export
uv run python scripts/contracts/generate.py --check
```

结果：退出码 0；Analysis 与 Export Contract 生成/固定文件一致。

```text
uv run python scripts/quality/check_architecture.py
```

结果：退出码 1；仍只报告本轮开始前已存在的 11 个 `ARCH001`：缺失 `backend/src/aima_ugc/operations/config/settings.py`、`security/secrets.py`、`logging/formatter.py`、`database/runtime.py`、`database/metadata.py`、`storage/ports.py`、`storage/tables.py`、`jobs/models.py`、`jobs/registry.py`、`jobs/tables.py`、`jobs/worker.py`。P1D 新增 Export Contract/Exporter 或迁移后的 `tikhub_test` 没有新增 Architecture 报错。

```text
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

结果：退出码 0；Secret 与 Docs gate 均通过。

### 7.4 两阶段 Review

需求符合性 Review：通过。

- P1D 差异只覆盖 Export Contract/Exporter、imports/tikhub_test 迁移、相关测试/门禁/README/Blueprint 同步；
- 删除旧 `tikhub_test/core/excel.py` 后只保留 `aima_ugc.platform.export.excel` 作为内容+评论 Excel 生成实现；
- `imports_test.export_raw_excel()` 明确从 deduplicated JSONL 派生；
- 没有进入 P1E，没有 Prompt/Taxonomy Loader、LLM Adapter、数据库、Migration、依赖升级或 `run_all()` 变化；
- 与并行 `douyin-detail-400` Change 同文件的 `tikhub_test/operations/runner.py` 仅替换 Excel 投影/写出，保留抖音 Detail HTTP 400 的既有降级语义；
- 与并行北京时间 Change 共享的 `tikhub_test/README.md` 保留其北京时间展示语义，仅同步共享 Excel Exporter 的现状。

代码质量 Review：通过 P1D 专项目标门禁，并补齐验证失败临时文件清理回归。

- write-only 输出和流式 Iterable 边界适合后续 P1H 90k 性能验证；
- 输出先写临时 XLSX、重新打开验证后再 `os.replace`，验证/替换异常会清理临时文件；
- ID 文本化、公式注入防护、URL scheme 限制、北京时间展示均有专项测试；
- raw/labeled 相同 Schema 的分析列空值/填值行为有专项测试；
- 公共 Export Contract 有 docstring，固定 Schema 由生成器维护；
- 没有平行 Workbook 规则和无关重构。

## 8. 当前全仓 CI 基线

P1D 在代码专项门禁闭环后，全仓 CI 仍不是全绿；已核实失败签名来自 P1D 开始前已存在的 Stage 1—7 基线，而非 Export 新增逻辑：

1. Stage 1：固定 Collection 生成物仍发生既有 `ProviderPlatformCapabilityV1.schema_version` 漂移：提交值 `provider-platform-capability.v1`，当前代码生成值 `provider-operations-capability.v1`；P1D Export Schema 已通过自身生成/漂移门禁。
2. Stage 2 Platform：测试收集时 `backend/src/aima_ugc/modules/content/tables.py:293` 访问不存在的 `contents_table.c.platform`，`AttributeError: platform`，1 个 collection error，退出码 2。
3. Stage 3A Database：同一 `contents_table.c.platform` 问题导致 1 个 collection error，退出码 2。
4. P1D 专项 Stage 5A 的唯一失败是上述 11 个既有 Architecture `ARCH001`；P1D 功能、Ruff、mypy、Export Contract、Secret、Docs 均通过。

这些基线问题不在 P1D 范围内，本 Change 没有通过删除测试、降低门禁或修改无关实现来制造“全绿”。另一个 Active Change `CHG-20260818-stage1-stage7-comprehensive-corrective` 元数据声明负责 Stage 1—7 全面整改；本轮未覆盖或修改其范围。

## 9. 依赖、Migration、模型与费用

- Python/Node/uv/openpyxl 等版本保持仓库锁定版本；P1D 未新增、升级或降级依赖；
- P1D 没有数据库写入、Migration、部署配置或生产数据迁移；
- P1D 没有调用任何真实或 Fake LLM；
- `Validation Retry` 尚未进入实现，因此重试次数为 0；
- 模型 token/费用为 0；
- P1D 回滚方式为按提交反向恢复 Export Contract/共享 Exporter/tikhub_test 迁移和本轮错误路径清理，不涉及数据库回滚。

## 10. Git / PR

- `main` 基线：`0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`；最终交付前重新核验当前 main；
- 功能分支：`feature/p1-offline-excel-sentiment`；
- Draft PR：#66；
- P1D 已闭环，当前下一最小单元为 P1E；
- 不自动合并、不直接推 main、不强制推送。
