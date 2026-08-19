---
schema: rvc-change/v1
id: CHG-20260819-imports-excel-view-config
title: imports_test Excel 可配置列与统一样式
level: L3
status: in_progress
owner: ChatGPT
branch: feature/imports-excel-view-config
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - platform_export
  - imports_test
  - blueprint
  - tests
affected_paths:
  - backend/src/aima_ugc/platform/export/excel.py
  - backend/src/aima_ugc/platform/export/__init__.py
  - backend/src/aima_ugc/adapters/providers/imports_test/test.py
  - backend/src/aima_ugc/adapters/providers/imports_test/README.md
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - tests/unit/platform/test_excel_export.py
  - tests/unit/collection/test_imports_test_export.py
  - tests/unit/collection/test_p1g_imports_run_all.py
contracts: []
data_changes: none
---

# 目标

让 `imports_test` 最终导出的 Excel 默认只展示用户当前需要的 10 列，并允许在 `test.py` 中通过一个有序配置项自由增删已支持列、调整列顺序；同时把共享 Excel 的视觉格式统一调整为用户上传参考文件 `文章` Sheet 的可复现样式，让 README 以“怎么配置、怎么运行、怎么看结果、怎么排错”为核心，而不是继续讲临时阶段边界。

默认内容列顺序：

```text
平台
标题
正文
作者
发布时间
内容链接
命中关键词
情感标签
一级标签
二级标签
```

# 成功标准

- [ ] `imports_test` 的 raw/labeled Excel 默认内容 Sheet 都只展示上述 10 列，顺序完全一致。
- [ ] `test.py` 顶部有一个清楚的有序列配置；用户增删/重排配置即可改变导出列，不需要改 Exporter 代码。
- [ ] 列配置只能引用共享 Exporter 已定义的内容列；空配置、未知列、重复列 fail-closed，不静默猜测。
- [ ] `UnifiedDataExcelV1` Pydantic 数据契约、字段语义和生成 JSON Schema 不改变；TikHub/其他调用方不传列配置时仍得到现有完整内容列，保持向后兼容。
- [ ] raw/labeled 在同一次调用配置下仍保持相同 Sheet、列名、列顺序；仅分析值是否填充不同。
- [ ] 共享 Excel 样式复用用户附件 `文章` Sheet 的稳定格式事实：首行冻结、首行筛选、表头 `#FFC000`、11pt 粗体、正文 11pt、表头行高 16.5、正文默认行高 14.5、显示网格线、无合并单元格、链接可点击、页面方向与页边距按模板；对应已有字段的列宽按模板，新增展示字段使用有界可读宽度。
- [ ] 大文件仍使用 write-only 流式写出，不扫描全表做自动列宽，不增加 pandas 或第二套 Workbook 实现。
- [ ] `imports_test/README.md` 重写成人工使用说明，明确输入、配置、运行、输出、列配置、所有可选列、模型配置和常见失败；移除“P1 边界/临时阶段”式实施过程描述。
- [ ] Blueprint 13 更新为长期当前事实：一个数据契约 + 一个共享 Exporter；允许对既有列做受控展示投影，但禁止调用方新增私有字段或复制 Workbook 实现。

# 范围

- 共享 Excel Exporter 增加可选的内容列投影/排序参数，默认完整列。
- `imports_test` 设置默认 10 列并把同一配置用于 raw/labeled 导出。
- 共享 Excel 样式按附件 `文章` Sheet 调整。
- 更新相关测试、README 与 Blueprint 13。

# 非目标

- 不改变 `UnifiedDataExcelV1` / Canonical / Analysis 的业务字段和 Schema。
- 不允许任意自定义列名、公式列或调用方传 Python 回调生成私有列。
- 不新增第二个 Excel Exporter，也不在 `imports_test` 里后处理/重写 `.xlsx`。
- 不配置评论列；`imports_test` 当前没有评论，评论 Sheet 保持共享 Exporter 的既有完整字段。
- 不从源 Excel 样式文件运行时读取模板；附件只用于冻结可维护的样式事实，避免生产依赖本地模板文件。
- 不启动 Stage 8。

# 必须保持不变

- Provider-neutral 数据继续先投影为 `UnifiedDataExcelV1`，再由唯一 `platform/export/excel.py` 写出。
- TikHub/未来正式导出不传新参数时，内容列仍为当前完整顺序。
- 外部 ID 文本格式、Formula Injection 防护、合法 HTTP(S) 超链接、北京时间显示、原子发布与重新打开验证继续有效。
- 约 90k 行场景继续使用 `write_only=True`，不得为了样式或列配置把所有 Cell 常驻内存。
- `export_raw_excel()` 和 `export_labeled_excel()` 都只消费同一 deduplicated JSONL，不回读源 Excel。

# 方案比较

## 方案 A：`imports_test` 导出后再二次修改 Excel

做法：先调用共享 Exporter 生成完整 Workbook，再在 `imports_test` 删除列、调样式。

不采用。它会让 `imports_test` 成为第二个 Workbook Owner，重复列/样式/校验逻辑，违反 Blueprint 13 的单一共享 Exporter；9 万行还需要再次打开和重写大文件，增加时间和内存成本。

## 方案 B：把共享 Exporter 的全局默认列直接改成 10 列

做法：所有调用方都只输出用户当前 10 列。

不采用。会破坏 TikHub/正式导出的既有完整字段，丢失 ID、指标、来源和分析版本等审阅信息，是不必要的破坏性变化。

## 方案 C：共享 Exporter 支持“已知列的受控有序投影”，默认仍为完整视图

做法：`UnifiedDataExcelV1` 数据结构不变；Exporter 接受可选 `content_columns`，只允许从当前共享列集合中选择，顺序即输出顺序；不传参数仍输出完整列。`imports_test` 在 `test.py` 顶部传入用户确认的 10 列。公共样式仍只在共享 Exporter 维护，并统一调整为本次附件样式。

采用。它同时满足可配置、单一实现、向后兼容、低维护成本和大文件流式写出的约束；新增机制只有“列名校验 + 索引投影”，不建立新的 Contract 或插件系统。

# 已确认关键决策

用户已明确确认：

1. `imports_test` 最终默认只展示 10 列：平台、标题、正文、作者、发布时间、内容链接、命中关键词、情感标签、一级标签、二级标签；
2. 希望通过配置项决定显示哪些列以及列顺序；
3. README 应首先让使用者知道如何配置和运行脚本，不需要“与 P1 边界”等实施过程描述；
4. Excel 样式应参考本次上传文件 `文章` Sheet 的字体、字号、颜色、冻结首行等全部可复现格式。

附件实际格式调查结果：首行冻结 `A2`；AutoFilter 覆盖整个数据区；表头填充 `#FFC000`、粗体 11pt；正文 11pt；表头行高 16.5，正文默认 14.5；显示网格线；无合并；模板主要列宽 B=20、C=34、D/E=50、F=15、G=20、H=12，其余默认；页面为 portrait，页边距 left/right=0.7、top/bottom=0.75、header/footer=0.3。模板个别单元格存在字体差异，视为文件局部异常，不复制成列级规则，统一使用一致 11pt 字体。

# 公共接口与兼容策略

- 为 `export_unified_data_excel()` 与 `export_unified_content_jsonl_to_excel()` 增加可选 keyword-only `content_columns`；默认 `None` 表示完整既有列。
- 只新增可选参数，不删除/改名既有参数，现有调用继续可运行。
- `UnifiedDataExcelV1` Pydantic Contract 与生成 Schema 不变。
- 列选择仅是最终展示投影，不改变底层数据存在性与字段语义。

# Migration / 部署 / 回滚

- 数据库 Migration：不适用。
- 依赖升级：不适用，继续使用已锁定 openpyxl。
- 部署：随正常代码 Release；不需要数据迁移。
- 回滚：回退本 Change 的 Exporter/入口/文档提交即可；底层 JSONL、Contract、数据库均未改变，不需要数据回滚。

# 风险

- 列投影配置错误：通过非空、合法列、无重复的 fail-closed 校验处理。
- 可选列导致重新打开验证无法固定依赖 `内容ID`：验证改为以实际表头、行数和存在时的稳定 ID 做检查，不为隐藏列制造假值。
- 样式对大文件性能影响：只使用固定字体/填充/列宽/行高/冻结/筛选，不做 autofit、复杂条件格式或全表扫描。
- 共享样式变化会影响 TikHub/正式默认 Excel 外观，但不改变字段和值；这是本次用户明确要求的统一视觉调整。

# 任务

- [x] 读取仓库规则、Blueprint、共享 Exporter/Contract/测试和附件真实格式
- [ ] 建立列投影、默认 imports_test 10 列和附件样式的失败测试并确认 Red
- [ ] 实现共享 Exporter 最小列投影与统一样式
- [ ] 接线 `imports_test` 默认列配置
- [ ] 重写 `imports_test/README.md` 为使用说明
- [ ] 更新 Blueprint 13 长期规则
- [ ] 运行目标/相关测试、Ruff、mypy、Contract/架构/Secret/Docs 与适用 CI
- [ ] 两阶段 Review、正常 PR 合并、Change 归档

# 验证

## 计划

- 目标测试：`tests/unit/platform/test_excel_export.py`、`tests/unit/collection/test_imports_test_export.py`、`tests/unit/collection/test_p1g_imports_run_all.py`
- 相关测试：P1/Analysis/Export 测试集合与完整 `tests/unit`
- 静态/契约：Ruff format/check、mypy、contract generation/check、architecture、secret、docs
- 真实格式：自动测试检查冻结首行、AutoFilter、表头填充/字体、行高、网格线、列宽、页边距/方向、超链接与重新打开可用性。
- CI：PR 最终 head 的适用 workflows 全部成功后才合并。

## 新鲜证据

- 尚未执行 Red/Green。

# 文档影响

- `imports_test/README.md`：整体改写为人工使用指南。
- Blueprint 13：从“固定完整列且调用方不可选”调整为“固定字段语义 + 共享 Exporter 受控展示投影”，并固化统一样式规则。

# 交付

- Commit：待完成。
- PR：待创建。
- 发布：不独立部署，随正常 PR 集成。