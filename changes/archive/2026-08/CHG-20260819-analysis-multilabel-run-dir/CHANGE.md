---
schema: rvc-change/v1
id: CHG-20260819-analysis-multilabel-run-dir
title: 多标签分析与 imports_test 独立运行目录
level: L3
status: done
owner: ChatGPT
branch: feature/analysis-multilabel-run-dir
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - analysis_contract
  - analysis_runtime
  - platform_export
  - imports_test
affected_paths:
  - backend/src/aima_ugc/contracts/analysis
  - backend/src/aima_ugc/modules/analysis
  - backend/src/aima_ugc/contracts/export
  - backend/src/aima_ugc/platform/export/excel.py
  - backend/src/aima_ugc/adapters/providers/imports_test
  - contracts/analysis
  - contracts/export
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
  - tests/unit/analysis
  - tests/unit/platform
  - tests/unit/collection
contracts:
  - ContentLabelAnalysisV2
  - UnifiedContentRecordV1
  - UnifiedDataExcelV1
data_changes: analysis-jsonl-compatible-versioned
---

# 目标与结果

本 Change 已完成以下目标：

1. 单条内容允许命中多个一级/二级标签，Analysis 使用 `labels[]` 保存完整一级/二级父子对，不使用两个彼此独立的数组。
2. `CanonicalContentV1`、五平台 Mapper、Content Repository 与数据库 Migration 不变；多标签仍是 Canonical 之后的派生 Analysis。
3. 新成功结果使用 `content-label-analysis.v2`：一个 `sentiment` + 一个或多个合法标签对；标签对不能重复，一级/二级必须来自当前 Prompt Taxonomy，二级必须属于对应一级。
4. 历史 `ContentLabelAnalysisV1` 与 V1 JSONL 继续可读取，`content-label-analysis.v1.schema.json` 保持不变。V1 checkpoint 可解析，但恢复仍必须通过当前 input、Prompt/Taxonomy Hash、Provider、Model 身份门禁，因此旧 V1 Prompt checkpoint 在当前 V2 Prompt 下会安全失效。
5. Excel “内容”Sheet 保持一条内容一行；多个一级/二级标签按相同标签对顺序用单元格换行展示。
6. 共享 Workbook 新增“标签明细”Sheet，一标签对一行，列为内容ID、平台、标题、情感标签、一级标签、二级标签、内容链接，用于 Excel 原生筛选和标签统计。raw/无 Analysis 导出只保留表头，不伪造标签行。
7. `imports_test.run_all()` 每次创建独立 `output/runs/<run-id>/`，canonical、filtered、deduplicated、analysis、最终 Excel 与 `run_summary.json` 均只写入该次目录。默认 run id 使用 `Asia/Shanghai` 的 `YYYYMMDDTHHMMSS.ffffff+0800`。

# 已确认关键决策

采用新增 V2 而不是破坏 V1：

```text
ContentLabelAnalysisV1
= 历史单标签兼容读取

ContentLabelAnalysisV2
= 当前一个情感 + N 个一级/二级标签对
```

Excel 使用两个观察角度：

```text
内容 Sheet
= 一条内容一行
= 用于内容总数、阅读和常规明细

标签明细 Sheet
= 一个标签对一行
= 用于一级/二级标签筛选与统计
```

因此同一内容同时命中“标签1”和“标签2”时，在标签明细 Sheet 中会有两行；筛选任一标签均能命中该内容，而主内容 Sheet 不会因为多标签重复计算内容条数。

# 兼容、Migration、部署与回滚

- Canonical Schema：不变。
- 五平台 Mapper：不变。
- 数据库 Migration：不适用，本次没有 Analysis 持久化表。
- 依赖：未新增。
- `ContentLabelAnalysisV1` Schema：与变更前 `main` 零差异。
- `UnifiedContentRecordV1.analysis`：向前兼容接收 V1/V2，新 Service 只产生 V2。
- 部署：普通代码发布，无额外基础设施。
- 回滚：旧代码不能消费新 V2 run 目录；若回滚，应保留 V2 run 目录作为历史产物，并用旧版本重新执行所需流程，不在旧代码中继续写已含 V2 的目录。

# Red / Green 证据

## Red

PR #82 初始 Red head：

```text
3d91533b55f962fa7f89294fe24924031c48aa10
```

Stage 5A Provider Raw run `32223507870` 在收集 `tests/unit/analysis/test_multilabel_analysis_v2.py` 时因 `ContentLabelAnalysisV2` 尚不存在而失败；Secret/Docs 同轮成功。失败来自目标能力缺失，而不是 CI 环境。

## Green

实施过程中真实暴露并修正：

- 生成代码换行转义错误；
- 模型 JSON `labels` 应接收 list，再冻结为业务 tuple；
- header-only write-only Excel 的 read-only `max_row` 不适合作为断言；
- V1/V2 分支局部类型与 `TypeAdapter` mypy 表达问题。

没有通过删除测试、放宽 Taxonomy Validator 或绕过质量门禁取得绿色。

最终兼容性 runner `32225105921`：

- 目标回归 `69 passed`，失败 0；
- Ruff check 成功；
- Ruff format：`311 files already formatted`；
- mypy：`Success: no issues found in 168 source files`；
- Contract drift、Architecture、Secret、Docs 全部成功；
- `git diff --exit-code origin/main -- contracts/analysis/content-label-analysis.v1.schema.json` 成功，证明 V1 Schema 未漂移。

更早完整目标集合还取得过 `70 passed`；最终兼容性收口没有改变目标业务行为。

# 最终标准 CI 与回归修正

ready-for-review 候选 `75b34394dc519ad8abfd36b862389b1b95459e90` 首次触发标准全量 workflows 后，Stage 5B/5C 发现 3 个 TikHub 调试测试仍硬编码旧 Workbook 两 Sheet：

```text
["内容", "评论"]
```

而共享 Exporter 的新正式结构已经是：

```text
["内容", "标签明细", "评论"]
```

失败为旧测试期望未同步，不是生产逻辑错误。仅同步以下回归断言，没有修改生产实现：

- `tests/unit/collection/test_tikhub_test_debug_runtime.py`
- `tests/unit/collection/test_tikhub_test_douyin_http_errors.py`

最终实现 head：

```text
fc88c7d59ac9742629b6b81fbc2ef4c0360a47e0
```

该 head 的 11/11 标准 GitHub Actions workflows 全部成功：

- CI `32226702795`
- Stage 1-7 Audit Correctness `32226702870`
- Stage 5A Provider Raw `32226702883`
- Stage 5B Collection Execution `32226702881`
- Stage 5C Provider Persistence `32226702803`
- Stage 5D Provider Dispatch `32226702825`
- Stage 6 XHS Vertical Slice `32226702806`
- Stage 7 Provider Config Routing `32226702777`
- Stage 7 Keyword Packs `32226702852`
- Stage 7 Plan Occurrence Run Snapshot `32226702797`
- Stage 7 Scheduler Runtime `32226702782`

# 文档同步

长期事实已同步到：

- `docs/blueprint/15-舆情AI打标与统一分析契约.md`
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`
- `backend/src/aima_ugc/modules/analysis/README.md`
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`

使用说明包含多标签结构、Excel 主表/标签明细筛选语义、独立 run 目录与运行方法。

# Git / PR / 集成状态

- Change branch：`feature/analysis-multilabel-run-dir`
- 实现 PR：`#82 支持多标签 Analysis 与 imports_test 独立运行目录`
- 最终实现 head：`fc88c7d59ac9742629b6b81fbc2ef4c0360a47e0`
- 最终实现 head 标准 workflows：11/11 success
- PR #82：已正常 merge
- 实现 merge commit / 当时 main：`037968ff37479a7da1a0bf2b9c735c51a93736ed`
- 归档通过独立 PR 执行；归档 PR 只允许移动/更新本 Change 文件，不修改业务代码。

# 结论

成功标准全部完成。没有未解决的 Contract、Canonical、Migration、依赖、测试或文档问题；Stage 8 未启动。本文件在归档 PR 合并后作为该 L3 Change 的历史证据保留。
