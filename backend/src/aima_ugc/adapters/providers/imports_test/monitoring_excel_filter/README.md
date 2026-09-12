# 监测 Excel 目录批量过滤

本目录是 `imports_test` 下的一次性离线工具，用来处理一整个目录树中的监测 Excel：自动发现所有 `.xlsx`，只保留 AIMA_UGC 当前正式支持的五个平台数据，再按词包过滤标题/正文，最后跨文件统一去重并输出 JSONL。

它只改变**人工触发方式和离线输出**，数据解析继续复用正式 Excel Reader、Mapper、Canonical、关键词过滤和去重实现。

## 1. 处理链

```text
INPUT_DIR
→ 递归发现所有 .xlsx
→ iter_excel_rows()
→ map_excel_row()
   ├─ xiaohongshu / douyin / weibo / bilibili / kuaishou → CanonicalContentV1
   └─ platform_unmapped → 明确跳过并计数
→ canonical/contents.jsonl
→ filter_canonical_content_jsonl(keywords=...)
→ filtered/contents.jsonl
→ deduplicate_content_jsonl()
→ deduplicated/contents.jsonl
→ run_summary.json
```

本工具**不会**写 PostgreSQL、调用 TikHub、调用 LLM、执行 AI 打标、启动 Worker/Scheduler、生成正式报告，也不会修改正式 Platform/Canonical Contract。

## 2. 输入目录

编辑 [`backend/src/aima_ugc/adapters/providers/imports_test/monitoring_excel_filter/process_directory.py`](process_directory.py) 顶部：

```python
INPUT_DIR = Path(r"E:\AIMA_UGC_data\monitoring")
```

脚本递归遍历该目录及全部子目录：

```text
monitoring/
├── 2026-03/
│   ├── 2026-03-01_xxx.xlsx
│   └── 2026-03-02_xxx.xlsx
├── 2026-04/
│   └── ...
└── 2026-09/
    └── ...
```

规则：

- 处理后缀为 `.xlsx` 的文件（大小写不敏感）；
- 自动忽略 Excel 临时文件 `~$*.xlsx`；
- 其他格式忽略；
- 没有发现 XLSX 时直接报错；
- 文件按文件名、再按相对路径确定性排序；来源文件名以 `YYYY-MM-DD` 开头时自然按日期升序处理；
- Canonical `source_value` 保存相对于 `INPUT_DIR` 的路径，因此不同子目录下同名 Excel 仍可唯一追溯。

## 3. Excel 格式与平台范围

继续使用现有 Profile：

```text
aima-monitoring-excel.v1
```

`SHEET_NAME = None` 时沿用正式 Reader 自动发现符合 Profile 表头的工作表；如果全部文件都确定使用“文章”，也可改成：

```python
SHEET_NAME = "文章"
```

只处理 AIMA 当前五个平台：

```text
xiaohongshu
douyin
weibo
bilibili
kuaishou
```

微信、今日头条、微信视频号、百度等无法映射为这五个平台的行会产生 `platform_unmapped`，本工具把它们视为明确的非目标数据：跳过并在 `run_summary.json` 统计。

只有 `platform_unmapped` 可以跳过。`platform_missing`、内容身份缺失、日期/粉丝数字段非法、Canonical 校验失败、工作表/表头异常、损坏 XLSX 等都直接失败，避免静默丢失目标平台数据。

## 4. 配置品牌词和车型词

编辑当前目录的 [`backend/src/aima_ugc/adapters/providers/imports_test/monitoring_excel_filter/keyword_pack.txt`](keyword_pack.txt)。品牌和车型放在**同一个词包**，因为本次规则就是“命中任意品牌词 **OR** 任意车型词即保留”。

```text
# 品牌
爱玛
雅迪

# 车型
元宇宙
墩墩
莱茵
```

沿用 `imports_test.keyword_pack.load_keyword_pack()`：

- UTF-8 / UTF-8 BOM；
- 一行一个词；
- 空行忽略；
- `#` 开头为注释；
- 规范化重复词只保留第一个标准词。

匹配继续复用现有相关性实现，只检查：

```text
title OR text
```

匹配前继续执行当前规则：Unicode NFKC、casefold、忽略空白以及 `-`、`_`、`·` 连接符。最终 `matched_keywords` 保存词包中的标准名称。

## 5. 输出

默认输出在本目录：

```text
output/
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

- `canonical/contents.jsonl`：目录中所有成功映射到五个平台的 Canonical 内容；
- `filtered/contents.jsonl`：标题/正文命中词包任意词的数据；
- `deduplicated/contents.jsonl`：按 `(platform, external_content_id)` 去重后的最终结果；
- `deduplication_conflicts.jsonl`：同稳定身份但业务字段存在差异的重复记录审计；
- `run_summary.json`：总行数、五平台行数、非目标平台跳过数、过滤/去重统计，以及逐文件统计。

每次执行创建独立 run；已存在的显式 `run_id` 不会被覆盖。`output/` 已由当前目录 `.gitignore` 排除，不应提交真实数据产物。

## 6. 运行

从仓库根目录执行：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory
```

成功后终端会打印本次 run ID、输入文件数、总行数、五平台行数、关键词命中数、最终去重行数和最终 JSONL 路径。

## 7. 去重语义

直接复用现有 `deduplicate_content_jsonl()`：

```text
identity = (platform, external_content_id)
```

- 第一次出现：保留；
- 相同身份再次出现：删除后续记录；
- 字段完全等价：普通重复；
- 字段有差异：仍保留首次记录，同时写 `deduplication_conflicts.jsonl`。

脚本按确定性文件顺序处理，因此“首次记录”由该顺序决定。本工具不改变正式去重策略，也不实现“自动保留最新记录”。

## 8. 运行摘要与对账

成功 run 至少满足：

```text
rows_seen
= rows_supported_platform
+ rows_skipped_platform_unmapped
```

以及：

```text
rows_keyword_matched
= rows_after_deduplication
+ duplicates_removed
```

`run_summary.json` 同时保存 `skipped_media_names`，用于说明哪些媒体来源被明确作为非五平台跳过，而不是读取过程静默丢行。

## 9. 失败与数据安全

- 输入 Excel 只读，不删除、不修改；
- Canonical 阶段使用临时文件 + `fsync` + 原子替换；异常时不发布半截 JSONL；
- 过滤和去重继续使用现有原子写入实现；
- 全流程流式处理，不把整批 Excel 或 JSONL 一次性加载到内存；
- 只有所有阶段成功后才写 `run_summary.json`。
