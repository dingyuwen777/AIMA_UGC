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

在不改变 Canonical、Analysis、UnifiedDataExcelV1、数据库或 Excel 数据语义的前提下，为**实际处理完成的统一 Excel**增加可独立调用的报告生成能力：

```text
处理完成的统一 Excel
→ 只读统计
→ Markdown 报告
→ Mermaid 图表
→ Word 文档
```

人工既可以直接指定 `.xlsx` 调用 `generate_report()`，也可以把已处理 Excel 通过 `run_all(report_excel_path=...)` 接入当前人工 run。

# 成功标准

- [x] 报告覆盖内容总量、评论总量、标签对总量、各平台数据量/占比、情感、一级标签、二级标签、一级→二级标签对、关键词、日期范围、每日趋势和数据完整性。
- [x] Markdown 使用 Mermaid `pie` / `xychart` 生成平台、情感、标签、关键词和每日趋势图；完整数据仍保留在表格，不因 Top N 图表裁剪丢失。
- [x] `generate_report(...)` 支持绕过 `run_all()`，直接指定处理后的 Excel 和输出目录。
- [x] Markdown 正文只有一份模板；Word 转换读取已经生成的 Markdown，不维护第二套 Word 正文模板。
- [x] Word 转换支持本模板需要的标题、段落、列表、表格、Mermaid `pie` / `xychart`，未支持 Mermaid 类型明确失败。
- [x] 报告实现只读输入 Excel，不写数据库、不调用 LLM、不改变上游数据语义。
- [x] `run_all(report_excel_path=...)` 可把显式处理后 Excel 接入报告阶段；当前人工 `run_all()` 没有实际最终 Excel 时，报告阶段明确记录 `skipped`，不伪造文件。
- [x] 没有为了报告重新启用最新 `main` 已注释的 `label_sentiment()` / `export_labeled_excel()` 自动阶段。
- [x] 未新增 Migration、公共 HTTP Contract、第三方运行时服务或 Python 依赖升级。
- [ ] 在最终融合后的功能分支上取得目标测试、Ruff、Mypy、文档检查等新鲜执行证据。

# 范围

- Provider-neutral 的统一 Excel 报告统计和 Markdown 模板渲染；
- Markdown → DOCX 转换，以及本报告 Mermaid 图表到 Word 内嵌 PNG 的转换；
- `imports_test` 默认报告模板、独立 `generate_report()` 与 `run_all(report_excel_path=...)` 接线；
- 报告/接线自动化测试；
- `imports_test` README、Report 模块 README 和 Blueprint 13 同步；
- DOCX ZIP/OOXML 结构校验。

# 非目标

- 不实现 Stage 8B+ 正式网页报告中心、持久化 Report Job、Artifact 权限/API 或数据库 Report Schema；
- 不改变统一 Excel 三 Sheet Contract、Canonical/Analysis Contract 或标签 Taxonomy；
- 不从模型生成管理层结论，不增加新的 LLM 请求；
- 不实现通用 Markdown 或 Mermaid 全语法渲染器；
- 不恢复当前人工 `run_all()` 中已被注释的 AI 打标/最终 Excel 阶段；
- 不合并到 `main`。

# 必须保持不变

- 最新 `main` 的 `INPUT_XLSX_FILES` 单/多 Excel 配置、全局过滤/去重和多文件数据库来源语义；
- 最新 `main` 的 LLM 请求费用审计、价格目录、复算能力和 `p1-run-summary.v2`；
- **`main@00c3f675023b2aad8f2e26a595d45e931c92a3ad` 中人工 `run_all()` 已注释 `label_sentiment()` 和 `export_labeled_excel()` 的当前调试行为；**
- `UnifiedDataExcelV1` 和共享 `platform/export/excel.py` 的字段、Sheet、样式、安全及导出行为；
- `WRITE_TO_DATABASE=False` 默认 file-only 行为；
- 当前 Python/uv 锁定版本和依赖；
- Prompt Markdown 仍是具体标签体系唯一事实源。

# 关键决策

1. **报告以实际存在的统一 Excel 为唯一输入。** 报告是只读派生层，支持直接指定已经处理完成的 Excel，也避免重新解释 Provider Raw、Canonical 或数据库。
2. **完整统计与图表分层。** Markdown 表格保存完整平台/标签/标签对/关键词/每日非零明细；折线或柱状图可以限制 Top N 以保证可读性。
3. **Markdown 是唯一正文模板。** Python 只负责统计和占位符替换；Word 转换读取最终 `report.md`，模板文字变化会同步进入 Word。
4. **不新增文档转换依赖。** 当前实现使用标准库 OOXML/ZIP/PNG 与现有 `openpyxl`，不引入 Pandoc、python-docx、Matplotlib、pandas 或在线 Mermaid 服务。
5. **Mermaid fail closed。** Markdown 使用 `pie` / `xychart`；Word 转换只支持本模板实际使用的 Mermaid 子集，遇到其他类型明确失败。
6. **并行变更优先保留最新仓库行为。** Change 创建后 `main` 先新增多 Excel/LLM 费用审计，随后又在 `00c3f675...` 修改人工入口并注释 AI/最终 Excel 阶段。本 Change 不把旧 `run_all()` 覆盖回来，而是增加显式 `report_excel_path`；默认没有最终 Excel 时记录 `generate_report: skipped`。
7. **DOCX 结构不依赖办公软件容错。** `w:br` 固定位于 `w:r`，生成后校验 ZIP CRC、必需 OOXML、关键 XML 和图表媒体数量。

# 任务

- [x] 调查 Excel Exporter、`imports_test.run_all()`、Analysis 标签与文档边界。
- [x] 建立报告生成、模板同步、输入 Excel 不变、未知 Mermaid 失败测试。
- [x] 实现 Provider-neutral 报告统计、Markdown 渲染、Word 生成和 DOCX 校验。
- [x] 接入 `imports_test.generate_report()` 与 `run_all(report_excel_path=...)`。
- [x] 融合多 Excel、费用审计以及最新人工 `run_all()` 禁用阶段，不静默恢复旧行为。
- [x] 同步模块 README、`imports_test/README.md` 与 Blueprint 13。
- [x] 修正 OOXML 换行节点层级，增加 ZIP CRC、XML 和换行层级回归测试。
- [ ] 再次融合最新 `main`，确认 `behind=0`。
- [ ] 在最终分支上执行验证门禁。

# 验证

## 计划

目标测试：

```bash
uv run pytest \
  tests/unit/platform/test_offline_reporting.py \
  tests/unit/platform/test_imports_test_reporting.py \
  tests/unit/platform/test_docx_package_structure.py \
  tests/unit/collection/test_p1g_imports_run_all.py -q
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

- 开发早期曾执行 Red → Green，报告核心最小测试实现后为 3/3 通过；随后仓库基线和 OOXML 实现均发生变化，因此不把该结果作为最终分支通过证据。
- 开发早期曾生成样例 DOCX 并经 LibreOffice 渲染为 9 页，未观察到空白页、图表丢失或明显裁切；随后修正了 OOXML 换行结构，因此同样只作为探索证据。
- 当前执行环境尝试克隆分支时 DNS 无法解析 `github.com`，不能在本地取得最终分支执行命令。
- 曾建立临时 feature-branch push workflow 尝试验证，但当前 GitHub 连接器只能可靠读取 PR 触发的 workflow run，commit status 也没有返回该 push run 的可用结果；临时 workflow 已删除，未把不可读结果当作证据。
- 因最终融合后的新鲜完整执行证据仍缺失，Change 保持 `in_progress`，不标记 `ready_for_review`/`done`。

# 文档影响

已同步：

- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`：报告目录、独立生成、统计口径、模板、Mermaid/Word 和失败边界；最终融合后还需复核其对最新人工 `run_all()` 的描述。
- `backend/src/aima_ugc/platform/reporting/README.md`：生产入口、输入输出、统计口径、Word、测试和当前 `run_all()` 兼容行为。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：在“数据明细 Excel 与 Report Renderer 独立”原则下固化离线 Report Renderer 边界。

未修改其他 Contract/Migration：本次没有改变对应机器语义。

# 交付

- 最新已观察主分支：`main@00c3f675023b2aad8f2e26a595d45e931c92a3ad`；交付前必须再次确认并融合。
- 分支：`feature/offline-reporting`。
- Commit：已在功能分支持续提交，提交信息使用中文。
- PR：未创建。
- 合并：未执行，且用户明确要求本轮不要合并 `main`。
- 发布/部署：未执行。
