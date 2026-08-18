# 临时 P1：Excel 离线导入、清洗、去重与舆情打标

> 状态：已批准的临时优先阶段设计，功能代码尚未实现。  
> 执行位置：Stage 7 已闭环之后、Stage 8 正式开发之前。  
> 生命周期：P1 完成并归档后删除本文及 Blueprint 导航中的 P1 临时入口；长期有效的 AI 打标契约由 [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md) 维护，统一 Excel 契约与共享 Exporter 由 [`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md) 维护。

## 1. 为什么插入 P1

当前 Stage 1—7 已闭环，Stage 8 原本是下一正式阶段。业务优先级调整后，需要先处理每批约 9 万条的本地 Excel 数据：转换为系统统一内容、筛出包含“爱玛”等关键词的帖子、去重、调用平台通用 AI 打标签，并生成统一 Excel。

P1 是临时优先插入，不重新编号 Stage 8，也不把无数据库调试实现冒充正式生产摄取链。P1 完成后，Stage 8 仍按原编号继续。

## 2. 当前批准的完整主链

第一版在不启动 PostgreSQL、API、Scheduler 和正式 Job Runtime 的情况下完成：

```text
本地 XLSX
→ Excel File Provider Reader / Mapper
→ canonical/contents.jsonl
→ 关键词筛选
→ filtered/contents.jsonl
→ 去重并形成 UnifiedContentRecordV1
→ deduplicated/contents.jsonl（analysis 初始为空）
→ 平台通用 ContentLabelingService
→ 分批 checkpoint
→ 原子回写同一个 deduplicated/contents.jsonl（analysis 已填充）
→ 唯一共享 Excel Exporter
→ <source>_<run-id>_labeled_data.xlsx
```

**业务数据中间产物全部使用 JSONL。** `run_summary.json` 等运行元数据可以使用 JSON。

不再把 `analysis/results.jsonl` 作为下游业务事实源；分析成功后必须回写 `deduplicated/contents.jsonl` 的 `analysis` 区块。`analysis/checkpoints.jsonl` 只用于费用安全、崩溃恢复与审计。

`*_raw_data.xlsx` 仍只是可选人工审阅旁路，不是 `label_sentiment()` 或默认 `run_all()` 的前置步骤。

## 3. 跨平台统一记录

P1 不修改 `CanonicalContentV1` 的语义。Canonical 继续只保存 Provider/平台可观察事实。

P1 在筛选/去重之后使用 Provider-neutral：

```text
UnifiedContentRecordV1
```

概念结构：

```json
{
  "schema_version": "content-record.v1",
  "content": {
    "schema_version": "content.v1"
  },
  "matched_keywords": ["爱玛"],
  "analysis": null
}
```

AI 成功后在同一条记录中填：

```text
analysis: ContentLabelAnalysisV1
```

完整 Analysis Contract、4 个情感标签、7 个一级标签、17 个二级标签、严格父子映射、Prompt 和未来数据库落点统一由 Blueprint 15 管理。本文件不复制第二份 taxonomy。

## 4. 非目标

P1 第一版明确不做：

- 不写 PostgreSQL；
- 不增加 Alembic Migration；
- 不新增正式 HTTP API 或前端页面；
- 不接 Scheduler；
- 不把离线 JSONL 状态伪装成正式 PostgreSQL Job Runtime；
- 不把 File Provider、Mapper 与 LLM 混在一起；
- 不对评论做 AI 打标；
- 不默认增加 pandas；
- 不增加 Redis、Kafka、Celery、SQLite 或其他基础设施；
- 不把源 Excel 的“全文情感”直接当成系统 AI 结果；
- 不创建第二套或第三套 Excel Exporter；
- 不把 AI 标签塞进 Canonical `observed_fields`。

未来正式接入生产系统时，大文件导入、批量 AI 和大批量导出仍必须按长期 Blueprint 进入持久化 Job；P1 的无数据库编排只用于当前离线优先任务和独立调试。

## 5. 代码边界

目标结构允许在真正编码时根据最新 Architecture Check 做最小路径调整，但职责必须保持：

```text
backend/src/aima_ugc/
├─ adapters/
│  ├─ providers/
│  │  ├─ imports/
│  │  │  ├─ __init__.py
│  │  │  ├─ models.py
│  │  │  ├─ excel_profile.py
│  │  │  ├─ excel_reader.py
│  │  │  ├─ identity.py
│  │  │  └─ mapper.py
│  │  └─ imports_test/
│  │     ├─ __init__.py
│  │     ├─ README.md
│  │     ├─ .env.example
│  │     ├─ test.py
│  │     └─ output/
│  └─ llm/
│     ├─ __init__.py
│     └─ openai_compatible.py
├─ contracts/
│  ├─ analysis/
│  └─ export/
├─ modules/
│  └─ analysis/
│     └─ prompts/
│        └─ content_labeling_v1.md
└─ platform/
   └─ export/
      ├─ __init__.py
      └─ excel.py
```

### 5.1 `imports/`

正式文件 Provider/Mapper 边界，只负责：

```text
XLSX
→ 行读取/格式校验
→ 来源身份解析
→ CanonicalContentV1
```

禁止负责关键词业务筛选、去重策略、AI 分类、Excel 输出或数据库写入。

### 5.2 `imports_test/`

无数据库人工调试入口。它不是第二套业务实现；所有步骤必须调用生产函数。

`test.py` 是人工执行文件，不是根 `tests/` 下的 pytest 自动测试。用户只需要在文件顶部配置本地输入/输出路径、关键词、Profile、是否启用真实 LLM 和 `.env` 位置。

### 5.3 `modules/analysis/` 与 `adapters/llm/`

这是**全平台长期通用能力**，不是 P1 私有目录。完整规则见 Blueprint 15。

长期调用方向：

```text
Canonical / UnifiedContentRecord / DB Read Model
→ build_content_label_input()
→ ContentLabelingService
→ SentimentClassifier Port
→ LLM Adapter
→ ContentLabelAnalysisV1
```

Provider/Mapper 不得直接调用模型。

### 5.4 `platform/export/excel.py`

P1 要建立全平台唯一共享 Excel Exporter。当前 `main` 尚未存在该文件，因此本文描述的是批准的目标实现，不是当前机器事实。

建成后：

```text
tikhub_test ─────┐
imports_test ────┼→ platform/export/excel.py
未来正式导出 ────┘
```

核心只维护一个 Provider-neutral Excel 写出函数，例如：

```python
export_unified_data_excel(...)
```

## 6. `imports_test/test.py` 使用方式

文件顶部目标配置形态：

```python
INPUT_XLSX = Path(r"E:\data\source.xlsx")
OUTPUT_ROOT = Path(r"E:\data\aima_output")

KEYWORDS = (
    "爱玛",
    "爱玛电动车",
)

SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"

ENABLE_REAL_LLM = False
ENV_FILE = Path(__file__).with_name(".env")
```

真实 API Key 不得写入 `test.py`，只通过本地未提交 `.env` 或环境变量读取。

必须提供以下人工函数：

```python
def convert(): ...
def filter_keywords(): ...
def deduplicate(): ...
def export_raw_excel(): ...      # 可选人工检查，不属于 run_all 主链
def label_sentiment(): ...       # 名称可保留兼容，但实际完成情感 + 一级 + 二级标签
def export_labeled_excel(): ...  # 主链最终 Excel
def run_all(): ...
```

每个函数只负责解析配置、调用生产函数、打印可读摘要并返回结果，不复制核心算法。

## 7. 单步生产函数与文件依赖

### 7.1 转换

目标生产函数：

```python
convert_excel_to_canonical(...)
```

输入：原始 XLSX。  
输出：`canonical/contents.jsonl`，非法行写 `errors/rejected_rows.jsonl`。

读取使用 `openpyxl` 的 `read_only=True`、`data_only=True` 和 `iter_rows(values_only=True)`；不得把约 9 万行完整 Cell 对象常驻内存。

### 7.2 关键词筛选

目标生产函数：

```python
filter_contents_by_keywords(...)
```

输入：`canonical/contents.jsonl`。  
输出：`filtered/contents.jsonl`。

标题与正文只在匹配副本上做必要 Unicode/大小写/空白规范化，Canonical 原始标题和正文保持原样；任一关键词命中即保留并记录 `matched_keywords`。

### 7.3 去重

目标生产函数：

```python
deduplicate_contents(...)
```

输入：`filtered/contents.jsonl`。  
输出：`deduplicated/contents.jsonl`；同身份但业务内容冲突写 `errors/duplicate_conflicts.jsonl`。

去重后的每一行固定使用 `UnifiedContentRecordV1`，`analysis` 初始为 `null`。

内容身份固定优先使用：

```text
(platform, external_content_id)
```

不能用标题、作者、正文等不稳定文本代替平台内容身份。

### 7.4 可选 raw Excel

`export_raw_excel()` 直接消费 `deduplicated/contents.jsonl` 并调用唯一共享 Exporter，生成：

```text
<source>_<run-id>_raw_data.xlsx
```

即使 JSONL 已经有 `analysis`，raw 模式也忽略/留空分析列。它只用于人工检查，不改变 JSONL 主链，不是 `label_sentiment()` 前置依赖，也不是 `run_all()` 默认步骤。

### 7.5 AI 打标

目标生产函数推荐使用平台中立名称：

```python
label_content(...)
```

人工入口可以保留：

```python
label_sentiment()
```

但实际一次完成：

```text
情感标签
一级标签
二级标签
```

**输入固定为 `deduplicated/contents.jsonl`。**

发给模型的每条业务内容固定只有：

```text
title
author.display_name
text
```

缺失字段填空字符串。平台 ID、URL、指标、命中关键词、Provider、源“全文情感”等都不得发给模型。完整模型 I/O Contract 见 Blueprint 15。

成功结果先追加到：

```text
analysis/checkpoints.jsonl
```

然后按受控批次通过 `.tmp + fsync + atomic replace` 回写到**同一个**：

```text
deduplicated/contents.jsonl
```

打标成功后这份 JSONL 的 `analysis` 不再为空。checkpoint 只用于崩溃恢复，不是最终业务事实源。

### 7.6 最终 labeled Excel

`export_labeled_excel()` 只读取：

```text
deduplicated/contents.jsonl
```

其中已经包含 `analysis`，然后调用同一个 `export_unified_data_excel(...)` 生成：

```text
<source>_<run-id>_labeled_data.xlsx
```

不再额外 join `analysis/results.jsonl`。

### 7.7 `run_all()`

默认完整顺序固定为：

```text
convert
→ filter_keywords
→ deduplicate
→ label_sentiment
→ export_labeled_excel
```

`export_raw_excel()` 不在默认顺序中。

## 8. Excel 输入 Profile

首个已批准 Profile：

```text
aima-monitoring-excel.v1
```

当前样例 Sheet：`文章`，字段：

```text
序号
监测项名称
文章编号
标题
内文
媒体名称（中文）
版面
出版日期
媒体类型
作者
全文情感
原文链接
粉丝数
```

映射原则：

- `标题` → Canonical title；
- `内文` → Canonical text；
- `媒体名称（中文）` → 显式平台映射；
- `出版日期` → 按 `Asia/Shanghai` 解释为带时区时间；
- `作者` → `author.display_name`；
- `粉丝数` → `author.follower_count`；
- `原文链接` → canonical URL，并优先解析平台原生内容 ID；
- `文章编号` → 保留为来源系统 ID/alternate ID，必要时才作为 fallback identity；
- `版面` 当前样例语义不稳定，不进入 Canonical；
- `媒体类型` 不未经验证直接等价于 Canonical `content_type`；
- 源 `全文情感` 只作为来源事实，不覆盖系统 AI 标签。

外部内容 ID 优先级：

```text
平台 URL 可验证的原生 ID
→ 来源文章编号 fallback
→ 规范化 URL 的确定性 SHA-256 fallback
→ 均不存在则拒绝该行
```

## 9. 无数据库运行目录

默认目标目录：

```text
imports_test/output/
└─ runs/
   └─ <run-id>/
      ├─ input/
      │  └─ source.xlsx
      ├─ canonical/
      │  └─ contents.jsonl
      ├─ filtered/
      │  └─ contents.jsonl
      ├─ deduplicated/
      │  └─ contents.jsonl            # AI 完成后 analysis 写回这里
      ├─ analysis/
      │  └─ checkpoints.jsonl         # 恢复/费用安全辅助
      ├─ errors/
      │  ├─ rejected_rows.jsonl
      │  └─ duplicate_conflicts.jsonl
      ├─ export/
      │  ├─ <source>_<run-id>_raw_data.xlsx      # 只有显式调用时存在
      │  └─ <source>_<run-id>_labeled_data.xlsx  # 默认最终产物
      └─ run_summary.json
```

用户可以通过 `OUTPUT_ROOT` 指定其他本地目录。历史 Run 不自动删除。

## 10. Prompt Markdown

P1E 必须建立正式平台通用 Prompt 文件：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

用户可以直接编辑该 Markdown 调优，不把完整提示词硬编码在 Python 中。

运行时必须记录/计算：

```text
prompt_version
prompt_sha256
```

Prompt 内容变化必须改变分析 identity，避免继续复用旧打标结果。标签闭集与判断标准仍由机器 Contract + Blueprint 15 约束；用户调 Prompt 可以扩充说明和示例，但不能不经 Contract 变更自行创造新标签。

## 11. 唯一 Excel Contract

长期只维护一个 Provider-neutral `UnifiedDataExcelV1`，完整长期规则见 Blueprint 13。

`raw_data.xlsx` 与 `labeled_data.xlsx` 使用完全相同的 Sheet、列和顺序；区别仅是 raw 模式留空分析列，labeled 模式读取 `UnifiedContentRecordV1.analysis`。

推荐 Workbook：

```text
内容
评论
```

P1 输入没有评论时，“评论” Sheet 可以只有表头。

分析列至少包括：

```text
情感标签
一级标签
二级标签
分析模型
Prompt版本
Taxonomy版本
```

## 12. openpyxl 与性能门禁

P1 继续使用仓库已经锁定的 `openpyxl`，不默认增加 pandas。

P1H 必须使用与真实文本长度相似的 `90,000 × 13` Fixture 和真实目标 Windows 环境记录：

- 读取与转换 wall time；
- 关键词筛选 wall time；
- 去重 wall time；
- JSONL AI 回写开销；
- 最终 Excel 写出 wall time；
- rows/s；
- 峰值 RSS；
- 输入/输出大小。

只有 `openpyxl read_only + write_only` 的真实证据不能满足当前离线任务后，才通过独立决策比较 pandas/calamine 等替代方案；不得凭猜测增加依赖。

## 13. `imports_test/README.md` 门禁

P1B 必须增加 README，至少讲清：

- `imports` 与 `imports_test` 的关系；
- Excel Profile 与字段要求；
- `.env.example` 如何使用；
- `test.py` 哪些路径/关键词/模型配置需要修改；
- `convert()`、`filter_keywords()`、`deduplicate()`、`export_raw_excel()`、`label_sentiment()`、`export_labeled_excel()`、`run_all()` 的输入输出；
- raw Excel 是可选人工检查，不是主链；
- JSONL 中间文件、AI 回写和断点恢复；
- 真实 LLM 默认关闭、费用和 Secret 安全；
- 运行时 Prompt Markdown 在哪里修改；
- 9 万行性能边界和常见输入错误。

## 14. P1 子阶段

P1 使用同一个 L3 Change、同一个 feature branch 和同一个 Draft PR 顺序推进：

### P1A：设计与阶段导航

- 建立 P1 Active Change；
- 将 P1 写入 Blueprint 导航；
- 建立本文；
- 更新 13 的唯一 Excel Contract/Exporter 长期规则；
- 建立 15 的平台通用 AI 打标长期契约。

### P1B：Excel imports + imports_test

- 建立 `imports/` 与 `imports_test/`；
- README、`.env.example`、`test.py`；
- Excel Profile、Reader、Identity、Mapper；
- `convert()` 与相关自动测试。

### P1C：关键词过滤 + 去重

- `filter_keywords()`；
- `deduplicate()`；
- `UnifiedContentRecordV1` JSONL；
- 重复冲突记录和测试。

### P1D：统一 Excel Contract + 共享 Exporter

- 建立 `UnifiedDataExcelV1`；
- 建立 `platform/export/excel.py` 唯一共享 Exporter；
- 将 `tikhub_test` 迁移到共享实现并删除重复 Excel 代码；
- `export_raw_excel()` 作为可选人工入口；
- 通用 Excel 测试迁移到共享能力。

### P1E：平台通用 Analysis Contract + Prompt + Fake

- 建立 `ContentLabelAnalysisV1`、情感/一级/二级标签机器闭集；
- 建立 `ContentLabelingService` / Port；
- 建立 `prompts/content_labeling_v1.md`；
- Prompt Hash、最小 AI 输入构造；
- Fake Classifier；
- 不联网完成 Red-Green-Refactor。

### P1F：真实 LLM Adapter + JSONL 回写

- OpenAI-compatible HTTP Adapter；
- Secret、严格 JSON、错误分类；
- 有界 batch/concurrency；
- `label_sentiment()` 只发 title/text/author.display_name；
- checkpoint + 原子写回 deduplicated JSONL；
- 真实 Probe 默认关闭。

### P1G：`run_all()` + 恢复

- 完整 JSONL 主链；
- 分析结果断点恢复；
- `run_summary.json`；
- 证明重启不会重复已成功模型调用；
- 最终 Excel 只读取回写后的 deduplicated JSONL。

### P1H：90k / 真实样本 / 收口

- 90k 性能证据；
- 100—200 条人工确认样本真实模型 Probe，覆盖 4 个情感、7 个一级标签和易混淆二级边界；
- 全链路与最终 XLSX reopen 验证；
- 完整需求符合性和代码质量 Review；
- P1 Change/PR 闭环后删除本文和 Blueprint P1 临时导航；
- Stage 8 恢复为当前下一正式阶段。

## 15. 跨网页对话续接规则

每个网页端新对话都必须重新读取当前 GitHub 事实，不依赖历史聊天：

```text
AGENTS.md
→ RVC Skill
→ docs/blueprint/README.md
→ 本文
→ docs/blueprint/15-舆情AI打标与统一分析契约.md
→ docs/blueprint/13-统一数据Excel导出与调试复用.md
→ P1 Active Change
→ 当前 branch / PR / 实现 / 测试
```

只处理最前面的未完成 P1 子阶段；如果上一子阶段没有真正闭环，先完成它。每轮结束前把 checklist、checkpoint 和新鲜验证证据更新回同一个 P1 Change。

## 16. 收口规则

P1 完成后删除的是临时阶段管理信息，不是已经形成的长期能力。

删除：

- 本文；
- `docs/blueprint/README.md` 中 P1 临时导航和当前优先级说明。

保留：

- `imports/` File Provider/Mapper；
- `imports_test/` 无数据库调试入口；
- `UnifiedContentRecordV1` 处理/交换边界；
- Analysis/LLM 全平台通用能力；
- 可编辑 Markdown Prompt；
- JSONL 回写和离线恢复能力；
- `UnifiedDataExcelV1`；
- 唯一共享 `platform/export/excel.py`；
- Blueprint 13 与 15 的长期设计；
- 自动测试和必要的调试文档。

P1 删除后，任何新对话再次按正常 Blueprint 判断 Stage 8 为下一正式阶段。