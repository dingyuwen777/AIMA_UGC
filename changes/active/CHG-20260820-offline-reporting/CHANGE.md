---
schema: rvc-change/v1
id: CHG-20260820-offline-reporting
title: 离线数据报告与 Markdown Word 导出
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/offline-reporting
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - platform-reporting
  - imports-test
affected_paths:
  - backend/src/aima_ugc/platform/reporting/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - tests/unit/platform/
  - tests/unit/collection/test_p1g_imports_run_all.py
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
contracts: []
data_changes: []
---

# 目标

在不改变既有 Canonical、Analysis、UnifiedDataExcelV1、数据库或 Excel 数据处理结果的前提下，为处理完成的统一 Excel 增加可独立调用的报告生成能力：

```text
处理完成的 labeled_data.xlsx
→ 只读统计
→ Markdown 报告
→ Mermaid 图表
→ Word 文档
```

`imports_test.run_all()` 在最终 Excel 成功导出后调用同一报告实现；人工也可以直接指定任意符合当前统一 Excel 结构的 `.xlsx` 生成报告。

# 成功标准

- [x] `imports_test.run_all()` 在最终 Excel 后接入 `generate_report()`，报告路径进入 `run_summary.json` 和 `P1RunSummary`。
- [x] 报告覆盖内容总量、评论总量、标签对总量、各平台数据量/占比、情感、一级标签、二级标签、一级→二级标签对、关键词、日期范围、每日趋势和数据完整性。
- [x] Markdown 使用 Mermaid `pie` / `xychart` 生成平台、情感、标签、关键词和每日趋势图；完整数据仍保留在表格，不因 Top N 图表裁剪丢失。
- [x] `generate_report(...)` 支持绕过 `run_all()`，直接指定处理后的 Excel 和输出目录。
- [x] Markdown 正文只有一份模板；Word 转换读取已经生成的 Markdown，不维护第二套 Word 正文模板。
- [x] Word 转换支持本模板需要的标题、段落、列表、表格、Mermaid `pie` / `xychart`，未支持 Mermaid 类型明确失败。
- [x] 报告实现只读输入 Excel，不写数据库、不调用 LLM、不改变上游数据语义。
- [x] 未新增 Migration、公共 HTTP Contract、第三方运行时服务或 Python 依赖升级。
- [ ] 在最新融合后的功能分支上取得完整目标测试、Ruff、Mypy、文档检查等新鲜执行证据。

# 范围

- Provider-neutral 的统一 Excel 报告统计和 Markdown 模板渲染；
- Markdown → DOCX 转换，以及本报告 Mermaid 图表到 Word 内嵌 PNG 的转换；
- `imports_test` 默认报告模板、独立函数和 `run_all()` 接线；
- 报告/接线自动化测试；
- `imports_test` README 和 Blueprint 13 同步；
- DOCX ZIP/OOXML 结构校验。

# 非目标

- 不实现 Stage 8B+ 正式网页报告中心、持久化 Report Job、Artifact 权限/API 或数据库 Report Schema；
- 不改变统一 Excel 三 Sheet Contract、Canonical/Analysis Contract 或标签 Taxonomy；
- 不从模型生成管理层结论，不增加新的 LLM 请求；
- 不实现通用 Markdown 或 Mermaid 全语法渲染器；
- 不合并到 `main`。

# 必须保持不变

- 最新 `main` 已存在的 `INPUT_XLSX_FILES` 单/多 Excel 统一配置、全局过滤/去重和多文件数据库来源语义；
- 最新 `main` 已存在的 LLM 请求费用审计、价格目录、复算能力和 `p1-run-summary.v2`；
- `imports_test` convert → filter → deduplicate → 可选数据库 → label → Excel 的处理语义；
- `UnifiedDataExcelV1` 和共享 `platform/export/excel.py` 的字段、Sheet、样式、安全及导出行为；
- `WRITE_TO_DATABASE=False` 默认 file-only 行为；
- 当前 Python/uv 锁定版本和依赖；
- Prompt Markdown 仍是具体标签体系唯一事实源。

# 关键决策

1. **报告以最终统一 Excel 为唯一输入。** 报告是只读派生层，天然支持直接指定已经处理完成的 Excel，也避免重新解释 Provider Raw、Canonical 或数据库。
2. **完整统计与图表分层。** Markdown 表格保存完整平台/标签/标签对/关键词/每日非零明细；折线或柱状图可以限制 Top N 以保证可读性。
3. **Markdown 是唯一正文模板。** Python 只负责统计和占位符替换；Word 转换读取最终 `report.md`，模板文字变化会同步进入 Word。
4. **不新增文档转换依赖。** 当前实现使用标准库 OOXML/ZIP/PNG 与现有 `openpyxl`，不引入 Pandoc、python-docx、Matplotlib、pandas 或在线 Mermaid 服务。
5. **Mermaid fail closed。** Markdown 使用当前 Mermaid 官方支持的 `pie` / `xychart` 语法；Word 转换只支持本模板实际使用的 Mermaid 子集，遇到其他类型明确失败。
6. **并行变更融合。** 本 Change 创建后 `main` 又新增多 Excel 合并和 LLM 费用审计；功能分支已重新融合到当时最新 `main` `e9acf5382186c3b1e3bd4b9e631655bfea2b6267`，保留这些行为后再接报告，不以旧实现覆盖新事实。

# 任务

- [x] 调查 Excel Exporter、`imports_test.run_all()`、Analysis 标签与文档边界。
- [x] 建立报告生成、模板同步、输入 Excel 不变、未知 Mermaid 失败测试。
- [x] 实现 Provider-neutral 报告统计、Markdown 渲染、Word 生成和 DOCX 校验。
- [x] 接入 `imports_test.generate_report()` 和 `run_all()`。
- [x] 融合最新 `main` 的多 Excel 与费用审计能力，并同步既有 `run_all()` 测试预期。
- [x] 同步 `imports_test/README.md` 与 Blueprint 13。
- [x] 复核并修正 OOXML 换行节点层级，增加 DOCX ZIP CRC 与关键 XML 解析校验。
- [ ] 在最新分支上执行最终完整验证门禁。

# 验证

## 计划

目标测试：

```bash
uv run pytest tests/unit/platform/test_offline_reporting.py tests/unit/platform/test_imports_test_reporting.py tests/unit/collection/test_p1g_imports_run_all.py -q
```

相关静态/文档检查：

```bash
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_docs.py
uv run python scripts/quality/scan_secrets.py
```

必要时再运行完整 Unit：

```bash
uv run pytest tests/unit -q
```

## 新鲜证据

- 开发过程中曾对报告核心行为执行 Red → Green：最小目标测试在实现前因报告 API 不存在而失败，实现后 3/3 通过；这批证据发生在后续融合最新 `main` 和 OOXML 结构修正之前，因此**不作为最终分支通过证据**。
- 开发过程中曾生成完整样例 DOCX，并用 LibreOffice 渲染为 9 页，未观察到空白页、图表丢失或明显裁切；该证据同样早于后续 OOXML 修正，因此只作为实现探索证据，不作为最终交付门禁。
- 当前执行环境尝试克隆 `feature/offline-reporting` 时 DNS 无法解析 `github.com`，无法在本地取得最新分支并运行上述命令。
- 当前仓库工作流没有可见 `workflow_dispatch` 入口，普通 CI 只在 `main` push 或面向 `main` 的 PR 时触发；当前未创建 PR，因此最新功能分支没有 GitHub Actions 运行结果。
- 因缺少最新分支上的新鲜完整执行证据，Change 保持 `in_progress`，不标记 `ready_for_review`/`done`。

# 文档影响

已同步：

- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`：多 Excel、费用审计既有说明继续保留，并增加报告目录、独立生成、统计口径、模板、Mermaid/Word 和失败边界。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：在既有“数据明细 Excel 与 Report Renderer 独立”原则下固化当前离线 Report Renderer 的输入、输出、模板和长期边界。

未修改其他 Blueprint/Contract/Migration：本次没有改变对应机器语义。

# 交付

- 基线：最新融合基线为 `main@e9acf5382186c3b1e3bd4b9e631655bfea2b6267`；交付前还需再次确认 `main` 是否前进。
- 分支：`feature/offline-reporting`。
- Commit：已在功能分支持续提交，提交信息使用中文。
- PR：未创建；用户要求本次先不要合并到 `main`。
- 合并：未执行。
- 发布/部署：未执行。
