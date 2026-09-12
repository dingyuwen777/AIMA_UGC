# 跨品牌车型共现帖子五平台拆分

本目录是 `imports_test` 下的**第三阶段独立离线工具**。它只读取第二阶段已经筛好的跨品牌车型共现帖子，并按正式平台字段无损拆成五个 JSONL。

## 1. 三阶段职责

```text
第一阶段
Excel 目录
→ monitoring_excel_filter/process_directory.py
→ 五平台 + 品牌/车型 OR 宽筛 + 跨 Excel 去重
→ deduplicated/contents.jsonl

第二阶段
→ vehicle_pair_filter/filter_vehicle_pairs.py
→ 至少 1 个爱玛车型 AND 至少 1 个非爱玛车型
→ comparison_posts.jsonl

第三阶段
→ cross_brand_platform_split/split_by_platform.py
→ record.content.platform
→ 五个平台 JSONL
```

第三阶段不再解析 Excel、不做品牌/车型匹配、不重新去重、不修改帖子内容，也不访问 PostgreSQL、TikHub 或 LLM。

## 2. 输入

编辑：

[backend/src/aima_ugc/adapters/providers/imports_test/cross_brand_platform_split/split_by_platform.py](split_by_platform.py)

顶部配置：

```python
INPUT_JSONL = Path(r"E:\...\vehicle_pair_filter\output\runs\<run_id>\comparison_posts.jsonl")
```

输入每个非空行必须是第二阶段的 `VehiclePairRecordV1`。工具读取：

```text
record.content.platform
```

作为唯一分流依据。

## 3. 固定五个平台

平台值直接复用正式 `PLATFORM_NAMES`：

```text
xiaohongshu
douyin
weibo
bilibili
kuaishou
```

输出文件固定为：

```text
xiaohongshu.jsonl
douyin.jsonl
weibo.jsonl
bilibili.jsonl
kuaishou.jsonl
```

即使某个平台本次 0 条，也会生成对应空 JSONL。不会生成 `other.jsonl`，也不会把非法平台静默归类。

## 4. 无损拆分语义

第三阶段会先用 `VehiclePairRecordV1` 校验输入行，再把**原始输入 bytes**直接写到对应平台文件，不调用 `model_dump_json()` 重新序列化业务记录。

因此，对任意有效输入记录：

```text
comparison_posts.jsonl 中的原始行
=
对应平台 JSONL 中的原始行
```

每条输入最多进入一个平台文件，且成功运行必须满足：

```text
rows_seen
== xiaohongshu
 + douyin
 + weibo
 + bilibili
 + kuaishou
```

空白行不视为业务记录，也不计入 `rows_seen`。

## 5. 输出

每次运行发布：

```text
output/
└── runs/
    └── <run_id>/
        ├── xiaohongshu.jsonl
        ├── douyin.jsonl
        ├── weibo.jsonl
        ├── bilibili.jsonl
        ├── kuaishou.jsonl
        └── run_summary.json
```

真实数据输出被当前目录 `.gitignore` 排除。

`run_summary.json` 包含：

```text
schema_version
run_id
input
rows_seen
platform_counts
outputs
```

其中 `platform_counts` 始终包含五个平台，包括计数为 0 的平台。

## 6. 整体原子发布

运行时先创建：

```text
output/.staging-<run_id>/
```

五个平台文件和 `run_summary.json` 都成功写完并 `fsync` 后，才把整个 staging 目录原子 rename 为：

```text
output/runs/<run_id>/
```

如果输入中途出现坏 JSONL、Contract 校验失败、非法平台或其他异常，本次 staging 会被清理，不发布半截正式 run。

如果同名正式 run 或 staging 已存在，工具会明确拒绝，避免覆盖既有数据或自动删除待人工确认的残留 staging。

## 7. 运行

从仓库根目录执行：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.cross_brand_platform_split.split_by_platform
```

成功后终端打印 `run_id`、总行数、五个平台计数和输出目录。

## 8. 下游使用

五个平台文件仍然保留第二阶段完整结构，包括：

```text
原始 UnifiedContentRecordV1
matched_target_models
matched_competitor_models
matched_pairs
model_mentions
```

因此后续可以分别按平台抓详情/评论，或者继续按车型 pair 做统计和大模型分析，而不需要重新识别品牌车型。
