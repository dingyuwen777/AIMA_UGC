---
schema: coding-change/v1
id: CHG-20260908-representative-selection-feishu-sync
title: 代表性正负面内容筛选与飞书多维表同步
level: L2
status: completed
owner: chatgpt
branch: feature/BOLL2
created: 2026-09-08
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - imports
  - external-provider
  - configuration
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/feishu/
  - backend/src/aima_ugc/entrypoints/representative_selection_main.py
  - backend/src/aima_ugc/platform/config/settings.py
  - tests/unit/analysis/
  - tests/unit/platform/
  - env.local.example
  - docs/
contracts: []
data_changes:
  - 本地代表性筛选运行审计文件
  - 飞书多维表记录的 Upsert（仅显式 write-feishu 模式）
---

# 背景、目标与边界

读取一个或多个已经完成打标的 Excel 的 `内容` Sheet，使用用户确认的 `zhengfu_shaixuan.md`，只从抖音和小红书的真实用户发声中筛选正面、负面代表性内容，每组最多 10 条，并按目标飞书表的 `声音内容/连接` 原文链接更新已有记录或创建缺失记录。

## 非目标

- 不修改现有导入、打标和报告主流程。
- 不修改原始 Excel、既有 Prompt、数据库 Schema 或前端页面。
- 不删除飞书记录，不清空未参与本次映射的字段。
- 不把 Dry Run 变成真实外部写入。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 只读取一个或多个文件的 `内容` Sheet，并按平台 + 内容ID 跨文件去重 | 用户确认方案 | satisfied | `labeled_content_reader.py`；单文件、跨文件 Reader 测试 |
| R2 | 只处理抖音和小红书，且只从真实用户发声建立候选池 | 用户确认方案 | satisfied | `build_candidate_pool()`；候选池单元测试；非真实用户不会进入 LLM 筛选 |
| R3 | 使用已有发声类型和情感标签作为硬筛选条件，不重新打标；指定 Prompt 仅用于组内代表性选择，不执行全量导入打标 | 用户确认方案 | satisfied | `build_candidate_pool()` + `RepresentativePrompt` + 独立筛选入口；全量导入打标流程保持独立 |
| R4 | 四组结果每组最多 10 条，数量不足不硬凑 | 用户确认方案 | satisfied | 四组独立选择、主题多样性、本地兜底和不足摘要；服务单元测试覆盖 |
| R5 | 筛选结果保留主题、理由、评分和原始内容字段 | 用户确认方案 | satisfied | `selected_results.jsonl` 与 `_selected_row()` |
| R6 | 每次写入在同一 Base 内新建按生成时间命名的数据表，旧数据表和旧记录不更新、不删除 | 用户后续确认 | satisfied | `create_table_from_current()` + 新表字段复制 + 新表写入/回读；Mock HTTP 创建表测试 |
| R7 | 飞书字段动态读取、类型转换、写入前快照和写入后回读核验 | 用户确认方案 | satisfied | `bitable.py` 字段映射、类型转换、快照和字段值回读验证；Mock HTTP 测试 |
| R8 | Secret 不进入日志或运行结果，默认 Dry Run | 项目 Secret/安全边界 | satisfied | Secret 文件读取复用现有安全边界；入口默认不写飞书；错误输出只保留稳定错误类型 |
| R9 | 不新增第三方依赖、不新增数据库 Migration 或公共 HTTP API | 已确认实施方案 | satisfied | 仅复用既有 `openpyxl`、`httpx`、Pydantic 和 LLM Adapter；无 Migration/API 变更 |
| R10 | 运行入口、配置、README 和测试同步 | 已确认实施方案 | satisfied | 独立入口、Settings/env 模板、Analysis/imports_test README、28 个相关测试 |
| R11 | 已完成 Dry Run 后可只同步已有结果，避免重复调用大模型，并写入新的时间命名数据表 | 用户后续确认 | satisfied | `--write-feishu-from-run`；selected_results JSONL 严格校验；入口测试验证不初始化 LLM |
| R12 | 支持直接使用飞书 `/base/` 链接中的 app_token，不强制依赖 Wiki Token | 用户后续确认 | satisfied | `AIMA_FEISHU_APP_TOKEN`；Base 直连跳过 Wiki 解析测试；Wiki 模式继续兼容 |
| R13 | 已打标的多个 Excel 可直接传入代表性筛选入口，不经过 `test.py` 全量重新打标 | 用户后续确认 | satisfied | `--input-xlsx` 可重复传入；跨文件读取测试和入口参数测试 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit | required | passed；相关测试通过，包含 Excel Sheet/去重、Prompt 校验、四组选择、配置、Base 直连和不足数量 |
| 外部 Adapter Mock | required | passed；Token、Wiki 节点、字段、创建/更新、回读和 429 重试覆盖 |
| Build / Runtime | required | passed；Ruff、Mypy（8 个受影响源文件）和目标 pytest 通过 |
| External Provider Probe | not_applicable | 不作为 CI 门禁；真实 dry-run 已尝试，但当前执行环境网络无法访问 LLM，审计记录为 `network_error`，未发出飞书请求 |
| Docs / Governance | required | passed；README、环境模板和本 Change 已同步 |

# Completion Audit

- [x] upstream_re_read：完成实现前重新核对用户方案、Prompt、Excel 表头和现有 LLM/Secret 边界。
- [x] change_coverage：R1—R11 均有实现、测试或明确不适用证据。
- [x] reverse_audit：核对入口参数、Dry Run/写入开关和 Feishu Upsert 保护边界。
- [x] validation_matrix：完成 required 层的本轮新鲜验证。
- [x] unresolved_cleared：无未解决的代码级关键字段、Secret、幂等或删除风险；真实外部 dry-run 仅受网络访问条件阻塞。
