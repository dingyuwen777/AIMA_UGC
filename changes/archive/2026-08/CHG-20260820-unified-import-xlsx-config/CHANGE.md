---
schema: rvc-change/v1
id: "CHG-20260820-unified-import-xlsx-config"
title: "统一 imports_test Excel 输入配置"
level: L2
status: done
owner: "codex"
branch: "main"
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - "excel-import"
affected_paths:
  - ".reliable-vibe-coding/project-context.json"
  - "backend/src/aima_ugc/adapters/providers/imports_test/test.py"
  - "backend/src/aima_ugc/adapters/providers/imports_test/README.md"
  - "tests/unit/collection/test_p1g_imports_run_all.py"
  - "tests/unit/collection/test_imports_test_export.py"
contracts: []
data_changes: []
---

# 目标

把 `imports_test` 的 Excel 文件配置收敛为唯一 `INPUT_XLSX_FILES` 入口：配置一个 `Path`
时自动使用现有单文件转换；配置多个路径的元组时自动使用现有多文件合并转换。

# 成功标准

- [x] `test.py` 不再定义或读取 `INPUT_XLSX`。
- [x] `INPUT_XLSX_FILES = Path(...)` 规范化为一个输入文件，并调用
  `convert_excel_to_canonical_jsonl()`。
- [x] `INPUT_XLSX_FILES = (Path(...), Path(...))` 保持按顺序合并到同一 run，并调用
  `convert_excel_files_to_canonical_jsonl()`。
- [x] 空元组在转换、付费调用和数据库写入前明确失败。
- [x] 单文件 run summary 继续兼容保留 `source_xlsx`，多文件来源、全局去重和独立
  Artifact/Import Batch 语义不变。
- [x] 相关测试、格式、静态、类型、质量与构建门禁获得本轮新鲜通过证据。

# 范围

- 修改人工入口的唯一 Excel 配置类型与规范化函数。
- 更新依赖该配置的单元测试与 `imports_test/README.md` 示例。
- 记录、验证并交付本次配置行为变化。

# 非目标

- 不改变生产单文件/多文件转换 API、Canonical、过滤、去重、AI、Excel 导出或数据库 Schema。
- 不保留第二个弃用配置、兼容别名或环境变量映射。
- 不升级依赖，不改变关键词、Prompt、价格或重试策略。

# 必须保持不变

- `convert_excel_to_canonical_jsonl()` 与 `convert_excel_files_to_canonical_jsonl()` 公共行为不变。
- 一个文件仍走单文件 Converter；两个及以上文件仍按配置顺序合并为一个 run。
- `run_summary.json`、`canonical/conversion_summary.json` 和数据库来源追溯格式不变。
- 空配置继续 fail closed，不进入付费或数据库阶段。

# 关键决策

- 用户明确要求移除 `INPUT_XLSX`/`INPUT_XLSX_FILES` 双入口，改为一个配置自动判断数量。
- 采用 `INPUT_XLSX_FILES: Path | tuple[Path, ...]`：单个 `Path` 最简，多个文件继续使用
  现有有序元组；不引入 list/string 等额外配置形态。
- 删除旧 `INPUT_XLSX`，不保留静默兼容别名，避免继续存在两个事实源；迁移只需把旧值赋给
  `INPUT_XLSX_FILES`。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/collection/test_p1g_imports_run_all.py tests/unit/collection/test_imports_test_export.py -q`
- 相关测试：`uv run pytest tests/unit/collection -q`、`uv run pytest tests/unit -q`
- 静态检查/构建：`uv run ruff format --check backend tests scripts`、`uv run ruff check backend tests scripts`、`uv run mypy backend/src`、四项质量脚本与 `uv build`。

## 新鲜证据

- Red：单独运行新增单文件配置测试，修复前因把 `Path` 当作可迭代对象而失败，
  `1 failed`。
- Green：目标测试文件修复后运行，`11 passed`。
- `uv run pytest tests/unit/collection -q`：`270 passed`。
- `uv run pytest tests/unit -q`：最终代码复跑为 `402 passed, 1 skipped`。
- `uv run ruff format --check backend tests scripts`：`338 files already formatted`。
- `uv run ruff check backend tests scripts`：`All checks passed!`。
- `uv run mypy backend/src`：`Success: no issues found in 178 source files`。
- `uv run python scripts/quality/check_architecture.py`、`check_table_ownership.py`、
  `scan_secrets.py`、`check_docs.py`：退出码均为 0。
- `uv build`：成功生成 sdist 与 Wheel。
- `git diff --check`：退出码 0，仅输出 Git 的 CRLF 转换提示。

# 文档影响

- 更新 `backend/src/aima_ugc/adapters/providers/imports_test/README.md`，只展示一个配置入口的
  单文件和多文件写法；其他 Blueprint、Contract 与部署文档不受影响。

# 交付

- Commit：用户已授权完成后提交并推送远程 `main`；由包含本记录的提交交付。
- PR：用户要求直接推送 `main`，不创建 PR。
- 发布：不在本次范围。
