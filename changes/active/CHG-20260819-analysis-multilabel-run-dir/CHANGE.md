---
schema: rvc-change/v1
id: CHG-20260819-analysis-multilabel-run-dir
title: 多标签分析与 imports_test 独立运行目录
level: L3
status: in_progress
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

# 目标

1. 允许同一条内容命中多个一级/二级标签，同时保留每个二级标签对应的一级父标签。
2. 不修改五个平台归一化后的 `CanonicalContentV1`；多标签仍然属于 Canonical 之后的派生 Analysis。
3. 最终 Excel 的“内容”Sheet 继续一条内容一行；多个一级/二级标签在各自单元格中按标签对顺序逐行显示。
4. Excel 增加“标签明细”Sheet，一个合法一级/二级标签对一行，使普通 Excel 下拉筛选能够让同一内容同时出现在任意命中标签的筛选结果中。
5. `imports_test.run_all()` 每次运行按运行开始时间创建独立 `output/runs/<run-id>/`，该次 canonical、filtered、deduplicated、analysis、Excel 与 `run_summary.json` 全部只写入该目录。

# 成功标准

- [ ] 新 Analysis 成功结果使用 `content-label-analysis.v2`，保存 `sentiment + labels[]`；每个 `labels[]` 元素同时保存 `primary_label` 与 `secondary_label`。
- [ ] `labels[]` 至少一个、不得重复标签对；一级/二级必须来自当前 Prompt Taxonomy，二级必须属于对应一级。
- [ ] 历史 `ContentLabelAnalysisV1` / checkpoint / JSONL 仍可读取；新 Service 只产生 V2，不重写历史 V1 文件。
- [ ] Prompt 要求每条结果返回一个 sentiment 和一个或多个合法标签对，不再以“只选主标签”为规则。
- [ ] Validation Retry 对非法 JSON、空 labels、重复标签对、未知一级、非法父子组合继续 fail-closed。
- [ ] “内容”Sheet 一级/二级单元格按相同标签对顺序用换行符展示，行与行一一对应；正文/标签单元格启用换行显示。
- [ ] 新“标签明细”Sheet 一标签对一行，至少包含内容ID、平台、标题、情感标签、一级标签、二级标签、内容链接，并启用冻结首行和自动筛选。
- [ ] 原始/无 Analysis 导出保留“标签明细”Sheet 表头但没有伪造标签数据；TikHub/其他调用方仍复用唯一共享 Exporter。
- [ ] `imports_test.run_all()` 的一次执行只使用一个 run_id，并组织为 `output/runs/<run-id>/...`；不再覆盖根 `output/canonical`、`output/analysis`、根 `run_summary.json` 或根最终 Excel。
- [ ] 默认 run_id 采用 `Asia/Shanghai` 可读时间格式，沿用 `tikhub_test` 的 `YYYYMMDDTHHMMSS.ffffff+0800` 形式；显式 run_id 仍受安全字符校验。
- [ ] README 与 Blueprint 13/15 描述当前真实使用方式与长期 Contract，不以历史阶段流水账代替使用说明。
- [ ] 目标测试、相关回归、Ruff、mypy、Contract drift、架构、Secret、Docs 和适用 CI 全部通过。

# 已确认关键决策

用户已在本次对话确认按以下方案实施，无需再次询问：

- Canonical 层不变，多标签只修改 Analysis/Export 层。
- 情感标签仍保持单值；一级/二级允许多值。
- Analysis 不使用两个彼此独立的数组，而使用 `labels[]` 标签对，避免丢失一级/二级父子关系。
- 内容 Sheet 保持“一内容一行”，标签在单元格内逐行显示。
- 另建“标签明细”Sheet 一标签对一行，承担 Excel 原生筛选/统计视图。
- `imports_test` 每次完整运行使用独立时间 run 目录。

# 方案比较

## 方案 A：直接把 V1 的 `primary_label/secondary_label` 改成数组

优点：字段少。缺点：破坏既有 V1 Contract；两个数组容易失去父子对应关系；历史 checkpoint/JSONL 兼容差。**不采用。**

## 方案 B：新增 V2，使用 `labels[]` 标签对；旧 V1 保持可读

优点：父子关系完整；历史兼容清楚；新旧结果可通过 `schema_version` 判别；回滚明确。增加少量版本兼容代码。**采用。**

## 方案 C：Analysis 仍单标签，只在 Excel/展示层制造多标签

优点：代码改动少。缺点：业务事实层无法保存多标签，模型/Validator/checkpoint/未来数据库都会丢信息。**不采用。**

# 公共兼容策略

- `ContentLabelAnalysisV1` 类和 `content-label-analysis.v1.schema.json` 保留不变。
- 新增 `ContentLabelAnalysisV2` 与 `content-label-analysis.v2.schema.json`。
- `UnifiedContentRecordV1.analysis` 向前兼容接收 V1 或 V2；已有 V1 JSON 继续合法，新写入使用 V2。
- Excel 共享输入 Contract 只做兼容扩展以承载 V2 标签对；既有无 Analysis/TikHub raw 导出调用不需要改业务字段来源。
- 不修改 Canonical Schema、数据库 Migration、五平台 Mapper 或 Content Repository。

# 输入与输出

输入仍为：

```text
CanonicalContentV1 title/text/author.display_name
+ 当前 Prompt/Taxonomy
```

模型目标输出：

```json
{
  "items": [
    {
      "item_no": 1,
      "sentiment": "混合",
      "labels": [
        {"primary_label": "骑行性能", "secondary_label": "舒适性"},
        {"primary_label": "售后服务", "secondary_label": "客服与服务态度"}
      ]
    }
  ]
}
```

一次 `imports_test` 目标目录：

```text
output/
└─ runs/
   └─ <run-id>/
      ├─ canonical/contents.jsonl
      ├─ filtered/contents.jsonl
      ├─ deduplicated/contents.jsonl
      ├─ analysis/checkpoints.jsonl
      ├─ analysis/attempts.jsonl
      ├─ analysis/failed.jsonl
      ├─ raw_data.xlsx              # 仅显式 export_raw_excel() 时产生
      ├─ labeled_data.xlsx
      └─ run_summary.json
```

# 非目标

- 不修改情感为多值。
- 不增加三级标签、置信度、理由、实体抽取等字段。
- 不启动 Stage 8。
- 不建立 Analysis 数据库表或 Migration。
- 不让 Excel 成为 Analysis 事实源；Excel 仍只消费统一 JSONL/Export Read Model。
- 不复制第二套 Excel Exporter。

# 必须保持不变

- Provider → Mapper → Canonical → Ingestion 的五平台统一数据链不变。
- 模型最小业务输入仍只有 title、text、author.display_name。
- Prompt Markdown 仍是具体 Taxonomy 唯一事实源；Python 不复制 9/39 标签枚举。
- Validation Retry、checkpoint 先落盘、原子回写、模型身份/Prompt/Taxonomy Hash 恢复门禁继续存在。
- 真实模型 Probe 默认关闭，不进入普通 CI，不打印 Secret。
- openpyxl write-only 仍是唯一共享 Excel 写出实现。

# Migration / 部署 / 回滚

- 数据库 Migration：不适用，本次没有 Analysis 持久化表。
- 文件兼容：历史 V1 JSONL/checkpoint 继续可读；新运行写 V2。
- 部署：普通代码发布，无额外基础设施或依赖。
- 回滚：代码可回滚到旧 Service；V2 结果不会被旧代码识别，因此回滚后不得拿已经写出 V2 的 run 目录继续旧流程，应保留该 run 目录作为独立历史产物并重新运行旧版本。

# 风险

- 多标签会增加模型输出长度与 token 成本；当前不设置额外标签数量上限，真实模型调用仍由批次大小与 Validation Retry 控制。若未来观察到成本/质量问题，再单独批准上限策略。
- 标签明细 Sheet 会按标签对展开行数，但主“内容”Sheet 不重复内容，因此内容条数统计不会被标签数放大。
- 旧 V1 checkpoint 恢复为旧 V1 Analysis 时可以继续写入统一 JSONL；新 Service 新生成的结果为 V2。Exporter 必须同时正确展示 V1/V2。

# 任务

1. Red：新增 V2 Contract/Validator/Excel/运行目录失败测试并观察正确失败。
2. Green：实现 Analysis V2、Prompt、多标签 Runtime Validator 与 Service。
3. Green：同步离线 checkpoint/JSONL 对 V1/V2 的兼容读写。
4. Green：扩展统一 Excel 投影，主表换行 + 标签明细 Sheet。
5. Green：把 imports_test 全链路改为每次独立 run 目录，并保持单函数独立调用可显式指定 run_id/run_dir。
6. 生成/同步 Contract Schema，更新 Analysis/Imports README 与 Blueprint 13/15。
7. 两阶段 Review + 新鲜完整验证；PR Ready 后按门禁合并并归档 Change。

# 验证计划

- `uv run pytest tests/unit/analysis tests/unit/platform/test_excel_export.py tests/unit/platform/test_p1g_labeled_excel.py tests/unit/collection/test_imports_test_export.py tests/unit/collection/test_p1g_imports_run_all.py -q`
- `uv run ruff check backend/src tests scripts`
- `uv run ruff format --check backend/src tests scripts`
- `uv run mypy backend/src`
- `uv run python scripts/contracts/generate.py --check`
- `uv run python scripts/quality/check_architecture.py`
- `uv run python scripts/quality/scan_secrets.py`
- `uv run python scripts/quality/check_docs.py`
- PR 最终 head 的所有适用 GitHub Actions workflows 必须成功。

# 新鲜证据

尚未执行 Red/Green。

# 文档影响

- `docs/blueprint/15-舆情AI打标与统一分析契约.md`：从单标签长期规则升级到一个 sentiment + N 个一级/二级标签对，说明 V1/V2 兼容。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：Workbook 增加标签明细视图，说明主表换行与筛选语义。
- `backend/src/aima_ugc/modules/analysis/README.md`：更新模型输出、Validator、checkpoint 兼容与调试说明。
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`：更新 run 目录、产物位置、多标签 Excel 使用与筛选方法。

# Git / PR 状态

- base main: `3909b32a3bebfd3483776ecd4cb41dd1f75cc458`
- branch: `feature/analysis-multilabel-run-dir`
- PR: 尚未创建
