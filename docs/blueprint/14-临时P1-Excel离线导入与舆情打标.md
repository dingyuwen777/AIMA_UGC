# 临时 P1：Excel 离线导入、清洗、去重与舆情打标

> 状态：已批准的临时优先阶段设计；P1A—P1F 已闭环，当前下一最小单元为 P1G。  
> 执行位置：Stage 7 已闭环之后、Stage 8 正式开发之前。  
> 生命周期：P1 完成并归档后删除本文和 Blueprint 导航中的 P1 临时入口；长期 AI 打标规则由 [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md) 维护，统一 Excel 契约由 [`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md) 维护。

## 1. P1 目标

当前 Stage 1—7 已闭环，Stage 8 原本是下一正式阶段。业务优先级调整后，需要先处理每批约 9 万条本地 Excel：转换为统一内容、筛选包含“爱玛”等关键词的帖子、去重、调用全平台通用 AI 打标，并生成统一 Excel。

P1 不重编号正式 Stage。P1 完成后删除本文，Stage 8 仍按原编号继续。

第一版不启动 PostgreSQL、API、Scheduler 和正式 Job Runtime：

```text
本地 XLSX
→ Excel File Provider Reader / Mapper
→ canonical/contents.jsonl
→ 关键词筛选
→ filtered/contents.jsonl
→ 去重并形成 UnifiedContentRecordV1
→ deduplicated/contents.jsonl（analysis 初始为空）
→ 全平台 ContentLabelingService
→ LLM 响应
→ 本地结构 + Prompt Taxonomy 校验
→ 不合法时按配置上限重新请求
→ 合法结果 checkpoint
→ 原子回写同一个 deduplicated/contents.jsonl（analysis 已填）
→ 唯一共享 Excel Exporter
→ <source>_<run-id>_labeled_data.xlsx
```

业务数据中间产物使用 JSONL。`run_summary.json` 等运行元数据可以使用 JSON。

`analysis/checkpoints.jsonl` 只负责崩溃恢复、费用安全和审计，不成为 Excel/数据库的第二业务事实源。

`*_raw_data.xlsx` 只是可选人工审阅旁路，不是 AI 或默认 `run_all()` 的前置步骤。

## 2. 跨平台统一记录

P1 不修改 `CanonicalContentV1` 的事实语义。

筛选/去重后使用：

```text
UnifiedContentRecordV1
= CanonicalContentV1
+ matched_keywords
+ analysis: ContentLabelAnalysisV1 | null
```

AI 标签属于 Analysis，不进入 Canonical `observed_fields`。

未来正式入库：

```text
record.content → Content Owner
record.analysis → Analysis Owner
```

不能把整条处理记录直接作为 `contents` JSONB。

## 3. AI 标签体系只维护在一个 Markdown Prompt

P1E 必须建立：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

这个 Markdown 同时维护：

```text
机器可读 Taxonomy JSON
情感闭集
一级标签闭集
二级标签闭集
一级/二级父子关系
覆盖内容
典型表达
边界规则
冲突优先级
示例
```

Python 不维护第二份具体业务 `Enum/Literal` 或一级→二级映射。

当前业务截图首版基线是：

```text
9 个一级标签
39 个二级标签
```

完整名称、父子关系与判断标准由 Blueprint 15 和未来实际 Prompt 维护，本文不复制第二份 taxonomy。

以后只要是标签增删/改名、父子关系或判断标准变化，业务 Owner 只改 `content_labeling_v1.md`；代码运行时重新解析 Taxonomy 并计算 Hash，不要求同步修改 Python 标签枚举。

## 4. 本地校验与可配置有界重试

大模型不能被当成格式/业务约束的唯一保证。

固定链路：

```text
PromptTaxonomyLoader
→ Taxonomy 自身校验
→ LLM
→ JSON/固定字段校验
→ item 映射校验
→ 标签闭集校验
→ 一级/二级父子校验
```

不合法时，Analysis Service 在配置上限内重新请求；直到成功或达到上限。

生产 Service 使用：

```text
max_validation_retries: int >= 0
```

含义是首次失败后允许的**额外**重试次数：

```text
0 → 总请求最多 1 次
1 → 总请求最多 2 次
2 → 总请求最多 3 次
```

P1 `imports_test/test.py` 暴露：

```python
MAX_VALIDATION_RETRIES = 2
```

`2` 是人工调试推荐起始示例，可由用户修改，不是不可变长期业务常量。重试会增加真实模型调用与费用。

达到上限仍不合法：

```text
analysis_status = failed
```

不得猜一个标签写入。

完整可重试错误、attempt 记录和 README 要求见 Blueprint 15。

## 5. 代码边界

目标结构：

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
│     └─ openai_compatible.py
├─ contracts/
│  ├─ analysis/
│  └─ export/
├─ modules/
│  └─ analysis/
│     ├─ README.md
│     ├─ prompts/
│     │  └─ content_labeling_v1.md
│     └─ ...
└─ platform/
   └─ export/
      └─ excel.py
```

真正编码时若最新 Architecture Check 证明目标路径依赖不合法，可以最小调整目录，但以下边界不可改变：

- File Provider/Mapper 不做关键词、AI、Excel、数据库；
- Analysis 是全平台通用能力；
- 一个 Prompt Taxonomy；
- 一个 `UnifiedDataExcelV1`；
- 一个共享 Excel Exporter。

## 6. `imports_test/test.py`

用户在文件顶部直接配置：

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
MAX_VALIDATION_RETRIES = 2
ENV_FILE = Path(__file__).with_name(".env")
```

真实 Secret 不写源码。

必须提供：

```python
convert()
filter_keywords()
deduplicate()
export_raw_excel()       # 可选旁路
label_sentiment()        # 名称可保留，实际完成情感+一级+二级
export_labeled_excel()
run_all()
```

人工入口只组装配置和调用生产函数，不复制算法。

默认：

```text
run_all
= convert
→ filter_keywords
→ deduplicate
→ label_sentiment
→ export_labeled_excel
```

## 7. Excel 输入 Profile

首个 Profile：

```text
aima-monitoring-excel.v1
```

Sheet：`文章`。

已知列：

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

映射：

- 标题 → Canonical title；
- 内文 → Canonical text；
- 媒体名称 → 显式 platform；
- 出版日期 → 按 `Asia/Shanghai` 解释；
- 作者 → `author.display_name`；
- 粉丝数 → `author.follower_count`；
- URL → canonical URL，并优先解析平台原生内容 ID；
- 文章编号 → 来源 alternate ID，必要时才 fallback；
- 版面不进入 Canonical；
- 媒体类型不未经验证直接等价 `content_type`；
- 源“全文情感”只保留来源事实，不覆盖 AI 标签。

ID 优先：

```text
平台 URL 可验证原生 ID
→ 来源文章编号 fallback
→ 规范化 URL SHA-256 fallback
→ 都不存在则拒绝
```

## 8. 模型输入最小化

每条业务内容只发送：

```text
title
text
author.display_name
```

缺失填 `""`。

禁止发送 ID、URL、互动指标、粉丝数、Provider、matched_keywords、源全文情感、Raw 定位等。

批量可以增加临时 `item_no` 做返回配对。

## 9. Prompt / Taxonomy Hash

运行时：

```text
prompt_sha256 = 完整 Markdown SHA-256
taxonomy_sha256 = 机器 Taxonomy JSON 规范化后的 SHA-256
```

标签或判断规则变化后旧结果不得误复用，即使忘记手工改版本号也由 Hash 识别。

## 10. 唯一 Excel 输出

长期规则见 Blueprint 13。

最终默认：

```text
deduplicated/contents.jsonl（analysis 已填）
→ Shared Excel Exporter
→ labeled_data.xlsx
```

可选 raw：

```text
同一 deduplicated/contents.jsonl
→ include_analysis=False
→ raw_data.xlsx
```

不维护第二份业务 JSONL，也不从 Excel 回读进入 AI。

## 11. README 门禁

P1B 的 `imports_test/README.md` 必须先介绍 File Import 调试入口、JSONL 主链和单步函数；P1E/P1F 完成后同步补充：

```text
Prompt Markdown 在哪里修改
标签/父子关系只改 Prompt
MAX_VALIDATION_RETRIES 怎么配置
0/1/2 的精确含义
哪些模型输出错误会重试
达到上限后的 failed 行为
重试带来的费用影响
如何查看 checkpoint / failed 项
```

长期平台通用行为还必须记录在：

```text
backend/src/aima_ugc/modules/analysis/README.md
```

## 12. P1 子阶段

### P1A：设计与阶段导航

- Active Change；
- P1 Blueprint 导航；
- 本文；
- Blueprint 13 唯一 Excel；
- Blueprint 15 全平台 AI、动态 Prompt Taxonomy、本地校验和有界重试。

### P1B：Excel imports + imports_test

- `imports/` 与 `imports_test/`；
- README、`.env.example`、`test.py`；
- Excel Profile/Reader/Identity/Mapper；
- `convert()` 与自动测试。

### P1C：关键词过滤 + 去重

- `filter_keywords()`；
- `deduplicate()`；
- `UnifiedContentRecordV1` JSONL；
- 冲突记录和测试。

### P1D：统一 Excel + 共享 Exporter

- `UnifiedDataExcelV1`；
- 唯一共享 Exporter；
- `tikhub_test` 迁移并删除重复 Excel 实现；
- 可选 `export_raw_excel()`。

### P1E：平台通用 Analysis + Prompt + Fake

- `content_labeling_v1.md`，完整包含当前 9 一级/39 二级；
- `PromptTaxonomyLoader`；
- `ContentLabelAnalysisV1` 固定结构但不硬编码具体标签；
- Runtime Validator；
- `ContentLabelingService` / LLM Port；
- `modules/analysis/README.md`；
- Fake 覆盖非法格式、未知标签、父子错配和 Validation Retry。

### P1F：真实 LLM + JSONL 回写

- OpenAI-compatible Adapter；
- Secret；
- 最小 AI 输入；
- `max_validation_retries`；
- 每次重试 attempt 可观察；
- checkpoint + 原子回写；
- 真实 Probe 默认关闭。

### P1G：`run_all()` + 恢复

- 完整 JSONL 主链；
- 重启不重复成功模型调用；
- `run_summary.json`；
- 最终 Excel 只读取回写后的 JSONL。

### P1H：90k / 真实样本 / 收口

- 90k 性能证据；
- 真实模型小样；
- 统计首次合法率、重试后成功率、平均尝试次数、最终失败率、token/费用；
- 全链路、Review、CI；
- 删除本文和 README P1 临时导航；
- Blueprint 13/15 长期保留；
- Stage 8 恢复为下一正式阶段。

## 13. 跨网页对话续接

每个新对话重新读取：

```text
AGENTS.md
→ RVC Skill
→ docs/blueprint/README.md
→ 本文
→ Blueprint 15
→ Blueprint 13
→ P1 Active Change
→ 当前 branch / PR / 代码 / 测试 / CI
```

只处理最前面的未完成 P1 子阶段；上一阶段没有真正闭环时先补它。每轮结束更新同一个 Change 的 checklist、checkpoint、新鲜验证和 Git/PR/CI 状态。

## 14. 收口

P1 完成后删除：

- 本文；
- Blueprint README 中 P1 临时入口。

长期保留：

- `imports/`；
- `imports_test/`；
- `UnifiedContentRecordV1`；
- Analysis/LLM 通用能力；
- 一个可编辑 Markdown Prompt/Taxonomy；
- 本地 Validator 与可配置 Validation Retry；
- JSONL 回写/恢复；
- `UnifiedDataExcelV1`；
- 唯一共享 Excel Exporter；
- Blueprint 13 与 15。