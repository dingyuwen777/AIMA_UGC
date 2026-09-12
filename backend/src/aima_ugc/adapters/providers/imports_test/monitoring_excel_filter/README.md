# 监测 Excel 目录批量过滤

这个目录提供一个**一次性离线人工工具**：给定一个监测 Excel 根目录，递归读取其中全部 `.xlsx`，只保留 AIMA 当前支持的五个平台内容，再按本地关键词包过滤标题/正文并统一去重，最终得到 JSONL。

它解决的是“把一批混合媒体监测 Excel 快速整理成五平台、关键词相关、已去重的数据文件”，不是正式历史迁移或产品导入入口。

## 1. 处理链

```text
INPUT_DIR
→ 递归发现 .xlsx
→ Excel Reader
→ Excel Mapper
├─ 当前五个平台 → CanonicalContentV1
└─ platform_unmapped → 明确跳过并计数
→ keyword_pack.txt 任意词 OR 过滤
→ UnifiedContentRecordV1
→ 稳定身份去重
→ JSONL + run_summary.json
```

工具复用现有生产实现：

- Excel 读取与异常 worksheet dimension 兼容：[`backend/src/aima_ugc/adapters/providers/imports/excel_reader.py`](../../imports/excel_reader.py)
- Excel 行到 Canonical 的映射：[`backend/src/aima_ugc/adapters/providers/imports/mapper.py`](../../imports/mapper.py)
- 稳定内容身份：[`backend/src/aima_ugc/adapters/providers/imports/identity.py`](../../imports/identity.py)
- 本地词包加载：[`backend/src/aima_ugc/adapters/providers/imports_test/keyword_pack.py`](../keyword_pack.py)
- 关键词过滤与去重：[`backend/src/aima_ugc/modules/analysis/offline_content.py`](../../../../modules/analysis/offline_content.py)

本目录只负责“目录发现 + 非目标平台跳过 + 人工运行编排”，不复制上述业务语义。

## 2. 平台范围

只处理 AIMA 当前正式支持的五个平台：

```text
xiaohongshu
douyin
weibo
bilibili
kuaishou
```

Excel 中的微信、今日头条、微信视频号、百度等其他来源会由现有 Mapper 判为 `platform_unmapped`。本工具把这个错误视为**明确的非目标来源**：

```text
platform_unmapped
→ 不写入 Canonical
→ 继续处理
→ 在 run_summary.json 中计数
```

其他错误不会被吞掉。例如：

```text
platform_missing
content_identity_missing
canonical_url_invalid
published_at_invalid
follower_count_invalid
Canonical ValidationError
```

这些都表示目标数据或输入格式存在问题，运行会失败且不会发布半成品 Canonical 文件。

## 3. 配置输入目录

修改 [`backend/src/aima_ugc/adapters/providers/imports_test/monitoring_excel_filter/process_directory.py`](process_directory.py) 顶部：

```python
INPUT_DIR = Path(r"E:\AIMA_UGC_data\monitoring")
```

只需要配置这一个根目录。脚本会递归发现根目录及所有子目录中的 `.xlsx`，同时：

- 忽略 `~$*.xlsx` Excel 临时文件；
- 忽略 `.csv`、`.xls`、`.txt` 等其他扩展名；
- 按相对路径做确定性排序；
- 支持不同子目录中存在同名 Excel；
- Canonical `source_value` 保存相对 `INPUT_DIR` 的路径，用于唯一追溯来源。

如果目录不存在、不是目录或没有任何 `.xlsx`，脚本会明确失败。

`SHEET_NAME` 默认是 `None`，继续使用现有 Excel Profile 自动发现符合表头的 Sheet。如果这批文件必须固定到某个 Sheet，也可以改成：

```python
SHEET_NAME = "文章"
```

## 4. 配置关键词

编辑当前目录的 `keyword_pack.txt`。

规则沿用现有 `imports_test` 词包：

```text
一行一个词
空行忽略
# 开头是注释
```

品牌词和车型词放在**同一个文件**中，例如：

```text
# 品牌
爱玛
雅迪

# 车型
元宇宙
Q3
```

本工具只向现有过滤函数传 `keywords=`，因此所有词属于同一个匹配维度：

```text
爱玛 OR 雅迪 OR 元宇宙 OR Q3 ...
```

搜索字段仍是：

```text
标题 OR 正文
```

命中任意一个词即保留。精确文本规范化规则继续由现有 Relevance 实现负责，不在本工具复制第二套规则。

`keyword_pack.txt` 默认只提供注释示例；正式运行前必须至少配置一个有效关键词，否则词包加载会 fail closed。

## 5. 执行

在仓库根目录运行：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory
```

这个入口不会：

- 连接 PostgreSQL；
- 调用 TikHub；
- 调用 LLM；
- 执行 AI 打标；
- 启动 Worker / Scheduler；
- 修改源 Excel；
- 生成正式 Excel Export、Markdown 或 Word 报告。

完整 `imports_test` 的其他人工能力仍由 [`backend/src/aima_ugc/adapters/providers/imports_test/test.py`](../test.py) 负责；本工具不改变它的行为。

## 6. 输出

每次运行创建独立目录：

```text
backend/src/aima_ugc/adapters/providers/imports_test/output/
└── monitoring_excel_filter/
    └── runs/
        └── <run_id>/
            ├── canonical/
            │   └── contents.jsonl
            ├── filtered/
            │   └── contents.jsonl
            ├── deduplicated/
            │   ├── contents.jsonl
            │   └── deduplication_conflicts.jsonl
            └── run_summary.json
```

通常后续真正使用：

```text
deduplicated/contents.jsonl
```

各文件含义：

- `canonical/contents.jsonl`：目录内所有成功映射的五平台内容；
- `filtered/contents.jsonl`：标题/正文命中任意关键词的内容；
- `deduplicated/contents.jsonl`：按现有 `(platform, external_content_id)` 规则统一去重后的最终内容；
- `deduplication_conflicts.jsonl`：同一稳定身份但业务字段不等价的重复记录审计；
- `run_summary.json`：输入、平台跳过、过滤、去重和逐文件统计。

输出位于现有 `imports_test/output/` 忽略目录下，不应提交真实 Excel 或生成 JSONL。

## 7. 运行摘要与对账

成功运行时，`run_summary.json` 至少记录：

```text
input_file_count
keyword_count
rows_seen
rows_supported_platform
rows_skipped_platform_unmapped
rows_keyword_matched
rows_keyword_filtered_out
rows_after_deduplication
duplicates_removed
deduplication_conflicts
skipped_media_names
files
outputs
```

关键对账关系：

```text
rows_seen
=
rows_supported_platform
+
rows_skipped_platform_unmapped
```

以及：

```text
rows_keyword_matched
=
rows_after_deduplication
+
duplicates_removed
```

`files` 会保存每个相对输入文件的读取、五平台写入和非目标来源跳过统计；`skipped_media_names` 用于解释“哪些媒体被有意识排除”。

## 8. 验证

目标回归测试：

```bash
uv run pytest tests/unit/ingestion/test_monitoring_excel_filter.py -q
```

静态检查按仓库当前质量入口执行。相关测试会覆盖：

- 根目录和子目录递归发现；
- Excel 临时文件/其他扩展名排除；
- 五平台 Mapper 复用；
- `platform_unmapped` 跳过；
- 其他 Mapper 错误 fail closed；
- 同名文件的相对来源追溯；
- 品牌词/车型词同维度 OR；
- 跨 Excel 稳定身份去重；
- `run_summary.json` 对账。
