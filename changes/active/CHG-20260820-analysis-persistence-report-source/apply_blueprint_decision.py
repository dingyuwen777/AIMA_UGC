from pathlib import Path


def replace_between(path: str, start: str, end: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    file_path.write_text(
        text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:],
        encoding="utf-8",
    )


def insert_before(path: str, marker: str, insertion: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if insertion.strip() in text:
        return
    index = text.index(marker)
    file_path.write_text(
        text[:index] + insertion.rstrip() + "\n\n" + text[index:],
        encoding="utf-8",
    )


def replace_required(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"{path}: required text not found: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Blueprint 03：把 Analysis 表描述改成目标逻辑模型，明确当前尚未形成机器 Schema。
replace_between(
    "docs/blueprint/03-数据库与文件存储.md",
    "### 4.5 Analysis、Monitoring、Reporting",
    "## 5. 关键表",
    '''### 4.5 Analysis、Monitoring、Reporting

本组同时包含当前目标域和未来持久化规划；**没有对应 Alembic Migration 的对象不属于当前机器 Schema**。尤其 Analysis/Reporting 仍需后续独立 L3 Change 冻结 DDL、表名和约束，本文只冻结 Owner 与数据形态。

Analysis Owner 的长期逻辑模型固定为：

```text
Analysis Run / Job execution
→ Content Analysis Result（父事实，一次已校验分析结果）
   → Content Analysis Label Pair（子事实，按 ordinal 保存一级/二级标签对）

未来评论打标真正进入范围后：
→ Comment Analysis Result
   → Comment Analysis Label Pair
```

硬边界：

- `contents/comments` 只保存 Content Owner 的外部可观察业务事实，不塞 AI 标签；
- 正式 Analysis 持久化落地后，通过 Validator 的成功 Analysis 必须由 Analysis Owner 写 PostgreSQL，不能长期只存在 JSONL/Excel；
- 多标签必须是子记录，不用逗号/换行字符串塞单列，也不使用 PostgreSQL ENUM 固化业务标签；
- 具体建议字段、幂等身份、历史与 current 选择规则以 Blueprint 15 为设计事实源；正式 DDL/表名仍由后续 Analysis Persistence Change + Migration 冻结。

Monitoring / Reporting 的长期域仍包括规则、告警、VOC/工单、报告与版本等业务对象；在对应阶段未落 Migration 前同样不得写成“当前已存在表”。
''',
)

# Blueprint 15：把“未来数据库设计”升级为已批准的正式持久化目标和硬规则。
replace_between(
    "docs/blueprint/15-舆情AI打标与统一分析契约.md",
    "## 15. 未来数据库设计",
    "## 16. P1E 必须落地的生产能力",
    '''## 15. 正式 Analysis PostgreSQL 持久化目标（已批准，当前未实现）

当前机器状态必须与目标状态分开：截至本 Blueprint 更新时，`imports_test` 的 AI 成功结果会回写统一 JSONL 并导出 `labeled_data.xlsx`，但 Stage 8A 的显式数据库阶段只持久化 Content；正式 Analysis PostgreSQL DDL/Migration/Repository/Job/HTTP Contract 尚未落地。

长期目标已经确认：**只要运行进入正式数据库模式，AI 结果通过本地 Validator 后，也必须作为独立 Analysis 业务事实写入 PostgreSQL。** 不能形成“Excel 有情感/一级/二级标签，而数据库只有 Content”的长期分叉。

### 15.1 固定写入链路

```text
Canonical / UnifiedContentRecordV1.content
→ ContentIngestionService
→ Content Owner Repository
→ PostgreSQL Content
→ 得到稳定 content_id

同一内容
→ Analysis Service
→ LLM
→ Runtime Taxonomy Validator
→ ContentLabelAnalysisV2（成功）
   ├→ 回写 deduplicated/contents.jsonl
   ├→ Shared Excel Exporter → labeled_data.xlsx
   └→ Analysis Owner Repository → PostgreSQL Analysis
```

固定规则：

1. Content 与 Analysis 分 Owner；不得把 AI 标签加进 `contents` 表方便查询。
2. JSONL、Excel 与 PostgreSQL Analysis 必须消费**同一份已经 Validator 接受的结构化 Analysis**；禁止从 Excel 反向解析标签再入库，也禁止数据库路径重新调用一次模型。
3. AI 失败不得写猜测标签；失败执行事实/错误由 Job/Run/Audit 记录，Analysis Result 只保存合法成功结果。
4. Content 已成功、Analysis 持久化失败时必须显式暴露 Analysis/DB 阶段失败或 partial 状态，并允许幂等重试；不能把“Content 已入库”冒充“AI 数据已完整入库”。
5. file-only 调试模式仍可以只保留 JSONL/Excel；“正式数据库模式必须写 Analysis”只在后续 Analysis Persistence 机器能力落地后成为运行时行为，不能靠 Blueprint 假装当前已经实现。

### 15.2 逻辑数据模型

推荐逻辑结构保持“结果父事实 + 标签对子事实”，避免把多标签压成字符串：

```text
Content Analysis Result
- id
- content_id                      FK → Content
- content_input_hash
- sentiment
- prompt_version
- prompt_sha256
- taxonomy_sha256
- model_provider
- model
- analyzed_at
- analysis_run/job identity

Content Analysis Label Pair
- analysis_result_id              FK → Content Analysis Result
- ordinal                         标签重要性/模型合法顺序
- primary_label
- secondary_label
```

同一结果内 `(analysis_result_id, primary_label, secondary_label)` 必须唯一，`ordinal` 保留 Validator 接受后的标签对顺序。

`analysis_runs`、`content_analysis_results`、`content_analysis_label_pairs` 等名称目前只可作为**建议命名**理解；正式表名、字段、外键、索引、状态、Job 绑定和 Migration 必须在后续 Analysis Persistence L3 Change 中以当时最新代码/Schema 为基线冻结，Blueprint 不冒充 Migration。

未来评论打标进入正式范围时，优先使用独立 Comment Analysis Result/Label Pair 与真实 `comment_id` 外键，不使用 `subject_type + subject_id` 这类无法由 PostgreSQL 正常外键约束的万能多态表，除非后续有新的明确证据改变该决策。

### 15.3 幂等、历史与 Current Analysis

Analysis identity 至少绑定：

```text
content_id
content_input_hash
prompt_sha256
taxonomy_sha256
model_provider
model
```

因此：

- 完全相同 identity 的成功结果重复提交必须幂等收敛，不产生重复标签对；
- Content 输入变化、Prompt/Taxonomy 变化或模型身份变化时，形成新的 Analysis 历史结果，不覆盖旧事实；
- 历史结果用于审计、复算、对比和问题追踪；
- Query 层必须提供确定性的 `current_analysis` 视图：默认选择**匹配当前 Content 输入版本/Hash、且符合当前选定 Analysis 配置的最新成功结果**；具体 current 选择索引/约束在正式 Persistence Change 中冻结并测试。

Prompt/Taxonomy 只是标签合法性事实源；数据库不使用 PostgreSQL ENUM 固化具体标签集合，因此后续只改 Prompt 标签体系不需要数据库 ENUM Migration。

### 15.4 事务与恢复原则

- Content 需要先合法入库/收敛出稳定 `content_id`，Analysis Result 才能建立真实外键；
- 不要求把外部 LLM HTTP 调用放进数据库事务；LLM 调用完成并通过 Validator 后，再用短事务写 Analysis Result + Label Pairs；
- Analysis Result 与其 Label Pairs 必须在同一数据库事务提交；
- 重试必须依赖数据库唯一约束/幂等身份，而不是“先查有没有再插入”的进程内约定；
- 后续正式 Analysis Job 必须继续复用现有 LLM Request Audit/费用快照，不按 Excel/TikHub 来源复制第二套计费实现。

### 15.5 与报告的关系

Analysis 持久化落地后：

```text
离线单批报告
→ 本次 labeled_data.xlsx
→ Excel Report Source

正式系统报告 / Dashboard / 跨批次趋势
→ PostgreSQL Content + current Analysis + Comment Read Model
→ Report Read Model
```

两条路径都必须转换成同一个 Provider-neutral Report Dataset/Context，复用同一统计、Renderer 和 `platform/reporting/report_template.md`。不能因为 PostgreSQL 恰好可访问就让同一个离线 `run_all()` 自动改读数据库；报告数据源必须由业务场景显式决定。完整规则见 Blueprint 13/17。
''',
)

# Blueprint 13：插入报告数据源长期边界并顺延小节编号。
path13 = "docs/blueprint/13-统一数据Excel导出与调试复用.md"
insert_before(
    path13,
    "### 13.2 统计口径",
    '''### 13.2 报告数据源与统一 Report Dataset

**当前机器实现只有 Excel Report Source。** `imports_test.run_all()` 的离线报告无论是否同时开启 Content 数据库写入，仍读取本次 run 的 `labeled_data.xlsx`，因为它代表本次处理完成后的明确批次快照。

长期固定为两个显式 Source Adapter，共同进入一个 Provider-neutral Report Dataset/Context：

```text
离线单批 / 人工交付
labeled_data.xlsx
→ Excel Report Source
→ Report Dataset

正式系统 / 跨批次 / 时间窗口 / Dashboard
PostgreSQL
→ Query Repository / Report Read Model
→ Report Dataset

Report Dataset
→ Statistics
→ Markdown Template / Renderer
→ report.md / report.docx / Web
```

硬规则：

1. **禁止** `if database_available: read_database else: read_excel` 这类环境驱动自动切换；同一命令不能因为某台机器启动了 PostgreSQL 就改变报告范围。
2. `imports_test` 的“本次 run 报告”默认永远是 Excel 快照，即使 `write_to_database=True`；数据库里可能同时存在历史 Excel、TikHub、其他 Batch 和其他时间数据，不能天然代表本次 run。
3. 正式系统报告、跨 Batch 趋势、7/30/90 天窗口和 Dashboard 默认使用 PostgreSQL Report Read Model；它们不能依赖本地 `output/runs/`。
4. PostgreSQL Report Source 必须通过 Query Repository/Read Model 读取 Content、current Analysis、Comments/必要维度；Report Renderer 不直接 SQL，也不成为表 Owner。
5. 两种 Source 只负责把数据适配为同一 Report Dataset；平台、情感、标签、关键词、趋势等统计规则与 Markdown/Word Renderer 只有一套。
6. 数据库版报告在正式启用前必须先满足 Blueprint 15 的 Analysis 持久化/current Analysis 和对应 Query Read Model；数据库缺少 AI Analysis 时不得静默回退 Excel 或伪造标签。
7. 调用方需要特定来源时必须显式选择 Source/Scope；Excel 路径、Import Batch、日期窗口、平台等 Scope 必须可观察、可复现。
''',
)
replace_required(path13, "### 13.2 统计口径", "### 13.3 统计口径")
replace_required(path13, "### 13.3 Markdown 是报告正文唯一模板", "### 13.4 Markdown 是报告正文唯一模板")
replace_required(path13, "### 13.4 Mermaid 与 Word", "### 13.5 Mermaid 与 Word")
replace_required(path13, "### 13.5 失败和数据安全边界", "### 13.6 失败和数据安全边界")
replace_required(path13, "### 13.6 与未来正式报告中心的关系", "### 13.7 与未来正式报告中心的关系")
replace_required(
    path13,
    "当前能力解决“已处理统一 Excel → 人工可交付报告”的独立离线路径，不提前实现正式 Stage 8B+ 网页报告中心。",
    "当前能力解决“已处理统一 Excel → 人工可交付报告”的独立离线路径，不提前实现正式网页报告中心。正式报告中心必须优先读取 PostgreSQL Report Read Model，而不是回扫人工 Excel 目录；数据库数据源的前置条件是 Content + current Analysis 等正式 Query 能力已经落地。",
)

# Blueprint 17：明确 Stage 8A 当前限制、已批准目标和数据库报告门禁。
path17 = "docs/blueprint/17-Stage8数据入口统一入库与业务前端实施.md"
replace_required(
    path17,
    "- `imports_test` 显式 `write_to_database=True` 或单独调用 `ingest_database(run_dir=...)` 时，复用正式 File Import bootstrap 写入 PostgreSQL；",
    "- `imports_test` 显式 `write_to_database=True` 或单独调用 `ingest_database(run_dir=...)` 时，当前 Stage 8A 只复用正式 File Import bootstrap 写入 PostgreSQL Content；该数据库阶段发生在 AI 打标之前，成功 AI Analysis 目前仍只回写 JSONL/Excel，这是**当前机器限制而不是长期目标**；",
)
insert_before(
    path17,
    "## 10. 手工写库模式的本地数据库前置条件",
    '''### 9.3 已批准的后续数据库完整写入目标

一旦 Blueprint 15 的正式 Analysis Persistence 通过独立 L3 Change 落地，`imports_test`/正式 Import Job 的数据库模式不能停留在“只写 Content”。目标链路固定为：

```text
File/TikHub/其他来源
→ Canonical
→ ContentIngestionService
→ Content Owner PostgreSQL
→ stable content_id
→ Analysis Service / Validator
→ Analysis Owner PostgreSQL
→ JSONL / Excel（需要时）
```

规则：

- 同一份 Validator 成功 Analysis 同时服务文件输出和数据库持久化，不能二次调用模型；
- Content 成功但 Analysis DB 写入失败时，必须让 Batch/Job/人工调用方看到 partial/failed Analysis 阶段，并允许幂等补写；
- file-only 模式仍不要求 PostgreSQL，也不因为未来 Analysis DB 存在而改变；
- 当前 Stage 8A 不补做这部分 Schema/Migration，本节只把后续开发目标固化，防止未来实现遗漏。
''',
)
replace_between(
    path17,
    "## 12. AI 的 Stage 8 边界",
    "## 13. 第一张正式页面：采集运行中心",
    '''## 12. AI 的 Stage 8 边界

P1 已经存在可复用的 Analysis Service、Prompt/Taxonomy、Validator、LLM Adapter、checkpoint、费用审计和离线 JSONL 回写；Stage 8A 也已经能把 Content 写入 PostgreSQL。

当前机器事实仍是：正式 Analysis PostgreSQL DDL/Migration/Repository/Job/HTTP Contract 尚未落地，`imports_test(write_to_database=True)` 当前只持久化 Content，AI 成功结果随后进入 JSONL/Excel。

已经批准的目标状态为：

```text
PostgreSQL Content
→ stable content_id

Analysis Service
→ Validator success
→ Analysis Owner Repository
→ PostgreSQL Analysis Result + Label Pairs
```

因此后续硬门禁：

- Stage 8 不把 AI 标签塞进 `contents` 表；
- 正式数据库模式最终必须同时拥有 Content 与成功 Analysis，不能让 Excel 成为唯一带标签的数据事实；
- Analysis Persistence 必须作为独立 L3 Change 落 DDL/Migration/Repository/Job/事务/幂等/current Analysis，并同步 Blueprint 03/15；
- 在 Analysis Persistence 落地前，页面不能把 AI 数据库状态冒充已实现，也不能通过前端 Mock 替代；
- **任何依赖数据库 AI 标签的正式报告、Dashboard、跨批次趋势或 AI 页面，在 Analysis Persistence + current Analysis Query Read Model 完成前不得进入实现闭环。**

报告数据源固定按场景选择：

```text
imports_test 本次离线 run 报告
→ labeled_data.xlsx

正式系统报告 / 跨批次趋势 / Dashboard
→ PostgreSQL Report Read Model
```

即使 `imports_test` 开启 `write_to_database=True`，本次 run 的离线报告也继续读取本次 Excel 快照；禁止根据数据库是否启动自动切换报告源。数据库正式报告通过 Query Repository/Read Model 读取 Content + current Analysis 等事实，再适配为统一 Report Dataset，复用 Blueprint 13 的同一 Renderer/Markdown 模板。

本次只固化目标，不在 Stage 8A 现有代码中偷偷补 Analysis 表或迁移，也不重排 8B—8F 编号。后续如果将 Analysis Persistence 产品化纳入某个 Stage 8 正式单元，必须先建立独立 L3 Change 并以当时最新 main 重新确认范围。
''',
)
replace_required(
    path17,
    "| AI 打标核心 | REUSE_BUT_PRODUCTIZE | 正式持久化前不冒充已接入 |\n| AI 数据库/页面状态 | PLANNED | 按 Blueprint 15/后续明确 Change |",
    "| AI 打标核心 | REUSE_BUT_PRODUCTIZE | 复用现有 Service/Prompt/Validator；正式 DB 模式最终必须持久化成功 Analysis |\n| Analysis PostgreSQL Persistence | PLANNED | 独立 L3 Change；Result + Label Pairs + 幂等/历史/current Analysis |\n| AI 数据库/页面状态 | PLANNED | Analysis Persistence + Query Read Model 完成前不得冒充已接入 |\n| 正式数据库报告/跨批次趋势 | PLANNED | 先完成 Analysis Persistence，再建立 PostgreSQL Report Read Model；Renderer 继续复用 Blueprint 13 |",
)
replace_required(
    path17,
    "PostgreSQL 是唯一业务事实库\n文件证据和调试产物继续保留",
    "PostgreSQL 是唯一业务事实库\n正式数据库模式最终同时持久化 Content 与成功 Analysis\n文件证据和调试产物继续保留",
)
replace_required(
    path17,
    "不要用目标 UI 冒充后端已经存在",
    "离线单批报告读 Excel；正式系统报告读 PostgreSQL Read Model\n报告源显式选择，不按数据库可用性自动切换\n不要用目标 UI 冒充后端已经存在",
)
