# Excel 离线导入测试 / 调试

本目录是临时 P1 的**人工入口**，用于在不接数据库、不接 Scheduler 的情况下逐步验证本地 XLSX 处理链。它不是第二套实现：Excel Reader/Profile/Identity/Mapper 来自 `aima_ugc.adapters.providers.imports`，关键词过滤、去重和 AI 分析业务核心来自平台无关的 `aima_ugc.modules.analysis`，Excel 人工审阅视图复用 `aima_ugc.platform.export` 的共享 Exporter。

当前已实现 P1B—P1E 的底层能力：

```text
source.xlsx
→ convert()
→ output/canonical/contents.jsonl        # CanonicalContentV1
→ filter_keywords()
→ output/filtered/contents.jsonl         # UnifiedContentRecordV1
→ deduplicate()
→ output/deduplicated/contents.jsonl     # UnifiedContentRecordV1
     └─ export_raw_excel()               # 可选人工审阅旁路
        → output/raw_data.xlsx
```

P1E 已建立 `PromptTaxonomyLoader`、完整 Prompt、严格本地 Validator、Analysis Contract、Analysis Service/Port 与无网络 Fake；**尚未**把真实模型、checkpoint 和 JSONL 回写接入 `label_sentiment()`。因此当前默认人工主链仍停在去重，不能把 P1E 的底层分析能力误认为 P1F/P1G 已完成。

`export_raw_excel()` 只读取 `deduplicated/contents.jsonl`，不会回读 `source.xlsx`，也不进入未来默认 `run_all()` 主链。

## 1. 配置本地文件

编辑 `test.py` 顶部：

```python
INPUT_XLSX = Path(r"E:\path\to\source.xlsx")
OUTPUT_ROOT = Path(__file__).with_name("output")

KEYWORDS = ("爱玛",)

SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"

ENABLE_REAL_LLM = False
MAX_VALIDATION_RETRIES = 2
ENV_FILE = Path(__file__).with_name(".env")
```

`MAX_VALIDATION_RETRIES` 就在 `test.py` 顶部修改。推荐从 `2` 开始，它的精确定义是：

```text
0 = 首次请求失败后不重试，总请求最多 1 次
1 = 额外重试 1 次，总请求最多 2 次
2 = 额外重试 2 次，总请求最多 3 次
```

P1E 已在正式 `ContentLabelingService` 固定这套语义，但 `test.py` 的 `label_sentiment()`、`ENABLE_REAL_LLM` 与 `.env` 真实 Adapter 接线属于 P1F；当前不要为了“能跑”自行在本文件实现第二套 LLM 调用。

本工具不增加 CLI 参数。当前可以在 IDE/调试器中按顺序单独调用：

```python
from aima_ugc.adapters.providers.imports_test.test import (
    convert,
    deduplicate,
    export_raw_excel,
    filter_keywords,
)

convert()
filter_keywords()
deduplicate()
export_raw_excel()  # 可选，不属于默认主链
```

当前 `__main__` 仍只执行 `convert()`；完整串联由 P1G 的 `run_all()` 建立。

## 2. Excel Profile 与 Canonical 映射

首版 Profile：`aima-monitoring-excel.v1`，默认 Sheet：`文章`。

要求存在以下 13 列，允许额外列：

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

Reader 使用：

```python
load_workbook(path, read_only=True, data_only=True)
iter_rows(values_only=True)
```

因此不会为了约 9 万行数据构造普通可写 Workbook，也没有引入 pandas。

P1 保持 `CanonicalContentV1` 不变，不向 Canonical 增加 AI 标签。主要映射：标题→`title`、内文→`text`、媒体名称→`platform`、出版日期按 `Asia/Shanghai` 解释后转 UTC、作者→`author.display_name`、粉丝数→`author.follower_count`、原文链接→`canonical_url`。源“全文情感”不写成系统 AI Analysis。

稳定身份严格按：

```text
平台 URL 中可验证的原生内容 ID
→ 文章编号
→ 规范化 URL 的 SHA-256
→ 无法构造则拒绝该行
```

## 3. convert() 输出与错误

成功输出：

```text
output/canonical/
├─ contents.jsonl
└─ conversion_errors.jsonl
```

`contents.jsonl` 每行都可由 `CanonicalContentV1` 重新校验。任何一行不合法时转换继续扫描并记录安全的行号诊断，但**不会发布部分业务 `contents.jsonl`**。

## 4. filter_keywords() 规则

过滤只消费 `canonical/contents.jsonl`。关键词配置先执行最小清洗：去掉首尾空白、去除重复项；空关键词直接拒绝，避免产生“匹配所有内容”的错误结果。

匹配范围固定为：

```text
title
+
text
```

首版采用**区分大小写的字面包含匹配**，不做模糊匹配、分词、同义词扩展或正则猜测。命中多个关键词时，`matched_keywords` 按 `KEYWORDS` 的配置顺序保存。

输出：

```text
output/filtered/contents.jsonl
```

每行结构：

```json
{
  "schema_version": "content-record.v1",
  "content": {"schema_version": "content.v1"},
  "matched_keywords": ["爱玛"],
  "analysis": null
}
```

过滤/去重阶段的 `analysis` 为空。P1E 已允许 `UnifiedContentRecordV1.analysis` 在**通过本地 Validator 后**承载 `ContentLabelAnalysisV1`；实际回写在 P1F 才建立。

## 5. deduplicate() 规则

去重只消费 `filtered/contents.jsonl`，稳定身份键为：

```text
(platform, external_content_id)
```

同一稳定身份下，只有**除 `content.source.item_locator` 外完全等价**的记录才视为重复；保留第一条并计入 `duplicates_removed`。忽略 `item_locator` 只是因为同一来源内容重复出现在 Excel 不同行时行定位天然不同，不代表其他业务字段可以被忽略。

如果同一稳定身份的其他字段不同，则视为冲突：

- 不猜哪一条正确；
- 不合并字段；
- 不静默“后写覆盖前写”；
- 继续扫描以收集冲突；
- 不发布部分 `deduplicated/contents.jsonl`。

安全诊断写入：

```text
output/deduplicated/deduplication_conflicts.jsonl
```

诊断只包含平台、内容 ID、首次/重复行号和不同字段路径，不复制标题、正文等业务文本。

没有冲突时输出：

```text
output/deduplicated/contents.jsonl
```

## 6. P1E AI 分析核心与 Validation Retry

唯一 Prompt/Taxonomy 事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

Python 不复制具体标签 Enum/Literal/父子关系。`PromptTaxonomyLoader` 从 Markdown 中唯一机器 JSON 块加载当前闭集，并计算 `prompt_sha256` 与 `taxonomy_sha256`。

每条内容发给模型的业务字段只允许：

```text
title
text
author.display_name
```

缺失填 `""`。临时 `item_no` 只用于批次配对。内容 ID、平台、URL、互动指标、粉丝数、Provider、`matched_keywords`、源 Excel 情感、Raw locator 等都不能发送。

本地 Validator 会严格检查 JSON、固定字段、额外字段、item 数量/顺序/唯一性、sentiment、一级标签和二级父子关系。非法输出不做模糊匹配或自动改标签。

Validation Retry 只重试当前仍未成功的 item。同批已经校验成功的 item 不会因为其他 item 失败而再次调用。每次模型请求是独立 attempt；真实 token/费用只有 Adapter 能提供时才记录。

如果手工用 P1E 的 `FakeContentLabelingLLM` 调试，可查看：

```text
ContentLabelingBatchResult.attempts
ContentLabelingItemResult.analysis_status
ContentLabelingItemResult.validation_error_codes
```

达到 `MAX_VALIDATION_RETRIES` 上限后失败 item 为：

```text
analysis_status = failed
analysis = None
```

不会填猜测标签。

### attempts / checkpoints / failed 在哪里看

- **P1E 当前**：attempts 和 failed 只存在于 `ContentLabelingBatchResult` 内存结果，用于 Fake/Service 单元测试和调试；
- **P1F 建立后**：通过 Validator 的成功结果会先进入 `output/analysis/checkpoints.jsonl`，再原子回写 `deduplicated/contents.jsonl`；真实入口也会把 attempt/失败诊断暴露为可审计输出；
- 现在如果目录里没有 `analysis/checkpoints.jsonl`，这是正常的 P1E 阶段边界，不要自行伪造 checkpoint 文件。

## 7. 共享 Excel Exporter

P1D 建立唯一共享导出链：

```text
UnifiedDataExcelV1
→ aima_ugc.platform.export.excel
→ .xlsx
```

Contract 与实现位置：

```text
backend/src/aima_ugc/contracts/export/
contracts/export/unified-data-excel.v1.schema.json
backend/src/aima_ugc/platform/export/excel.py
```

工作簿固定为 `内容`、`评论` 两个 Sheet；外部 ID 以文本写入，HTTP(S) URL 可点击，文本经过公式注入防护，时间统一按北京时间展示。`raw_data.xlsx` 与未来 `labeled_data.xlsx` 使用同一列 Schema；raw 导出只把分析列留空，不创建另一套业务事实源。

Exporter 使用 write-only Workbook 流式写出，并在发布目标文件前重新打开检查 Sheet、表头、行数和关键 ID。完整业务数据仍以 JSONL 为事实源，Excel 只用于人工查看和交付。

## 8. JSONL 与失败边界

filtered/deduplicated 业务文件都使用 `UnifiedContentRecordV1`，不会创建第二套 Excel 中间事实源。输入 JSONL 每行都重新做 Pydantic 校验；空行、非法 JSON 或 Contract 不合法时 fail closed。

目标 JSONL 文件通过临时文件写完、`flush/fsync` 后再替换；新一轮开始前清理旧目标/诊断，避免后续步骤误读上一次成功或失败的陈旧文件。

P1F 的 AI 成功回写仍只更新同一个 `deduplicated/contents.jsonl`；`analysis/checkpoints.jsonl` 是恢复/费用安全/审计依据，不是第二业务事实源。

## 9. .env 与真实模型边界

P1E 不读取真实 Secret，也不会访问真实模型。`ENABLE_REAL_LLM=False` 保持默认安全状态。

真实 OpenAI-compatible LLM Adapter、`.env.example` 需要的 URL/API key/model 配置、网络/Transport Retry、checkpoint、JSONL 原子回写和 `label_sentiment()` 接线统一在 P1F 实现。真实 `.env` 已由仓库根 `.gitignore` 忽略，不要提交密钥。
