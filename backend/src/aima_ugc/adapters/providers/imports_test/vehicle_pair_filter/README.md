# 爱玛车型 × 竞品车型共现二次筛选

本目录是 `imports_test` 下的**第二阶段独立离线工具**。它不再处理 Excel，也不修改第一阶段 `monitoring_excel_filter`：输入直接使用第一阶段已经完成五平台宽筛和跨文件去重后的 `deduplicated/contents.jsonl`。

## 1. 两阶段职责

第一阶段：

```text
Excel 目录
→ monitoring_excel_filter/process_directory.py
→ 五个平台
→ 品牌词 OR 车型词宽筛
→ 跨 Excel 去重
→ deduplicated/contents.jsonl
```

第二阶段：

```text
deduplicated/contents.jsonl
→ vehicle_pair_filter/filter_vehicle_pairs.py
→ 逐帖识别车型 alias
→ 至少 1 个爱玛车型
AND 至少 1 个非爱玛车型
→ 对该帖实际命中的两个车型集合做局部笛卡尔积
→ comparison_posts.jsonl
→ comparison_posts.xlsx
```

第二阶段**不会**重新解析 Excel、重新做 content 去重、访问 PostgreSQL、调用 TikHub/LLM，也不会修改正式 Brand/Vehicle、Platform、Canonical 或 HTTP Contract。

`comparison_posts.xlsx` 不是第二套业务数据：它从本次最终 `comparison_posts.jsonl` 流式派生，并复用仓库唯一的 Provider-neutral `UnifiedDataExcelV1` + `export_unified_data_excel()`。因此 JSONL 仍是后续机器处理的正式输入，Excel 只是方便人工查看的统一展示视图。

## 2. 匹配规则

第二阶段只认**车型标准名/alias**，不要求帖子同时出现品牌名，也没有 `require_brand`。

例如配置中：

```json
{
  "name": "九号",
  "models": [
    {
      "name": "Q3",
      "aliases": ["九号Q3"]
    }
  ]
}
```

则下列内容都会把 `Q3` 识别为 `九号/Q3`：

```text
Q3骑起来怎么样
九号Q3和元宇宙怎么选
```

品牌名称只负责说明车型归属，不参与命中条件。反过来，帖子只出现“九号”“雅迪”“爱玛”等品牌词而没有任何配置车型时，不形成车型命中。

匹配字段仅为：

```text
content.title
content.text
```

并继续复用当前 `normalize_keyword_match_text()`：Unicode NFKC、casefold，并在匹配时忽略空白以及 `-`、`_`、`·`。

## 3. 配置 vehicle_catalog.json

默认配置：

[`backend/src/aima_ugc/adapters/providers/imports_test/vehicle_pair_filter/vehicle_catalog.json`](vehicle_catalog.json)

结构：

```json
{
  "schema_version": "vehicle-pair-catalog.v1",
  "target_brand": "爱玛",
  "brands": [
    {
      "name": "爱玛",
      "models": [
        {
          "name": "元宇宙",
          "aliases": ["爱玛元宇宙"]
        }
      ]
    },
    {
      "name": "雅迪",
      "models": [
        {
          "name": "莱茵",
          "aliases": ["雅迪莱茵"]
        }
      ]
    }
  ]
}
```

规则：

- `target_brand` 当前设为 `爱玛`；
- `brands` 可以继续增加其他品牌；
- 每个车型的 `name` **自动作为一个匹配 alias**，不需要在 `aliases` 重复填写；
- `aliases` 只补充标准名之外的写法；
- 目标品牌必须存在且有车型；
- 至少存在一个非目标品牌车型；
- 同一规范化 alias 不能同时归属于两个不同车型，否则启动时 fail closed，避免一条文本被歧义归到多个品牌/车型。

实际跑全量数据前，应把需要参与比较的全部爱玛车型和竞品车型维护在该文件中，并保证一个规范化 alias 只归属于一个标准车型。

## 4. 输入

编辑 [`backend/src/aima_ugc/adapters/providers/imports_test/vehicle_pair_filter/filter_vehicle_pairs.py`](filter_vehicle_pairs.py) 顶部：

```python
INPUT_JSONL = Path(
    r"E:\...\monitoring_excel_filter\output\runs\<run_id>\deduplicated\contents.jsonl"
)
```

输入每行必须是现有正式：

```text
UnifiedContentRecordV1
```

因此推荐只消费第一阶段最终的 `deduplicated/contents.jsonl`。本工具不会再次去重；它遵守“一条输入帖子最多写一条输出帖子”。

## 5. 多车型组合

程序不会先全局生成所有爱玛车型 × 所有竞品车型，再反复扫描 JSONL。

每篇帖子只扫描一次。例如一篇帖子实际命中：

```text
爱玛：元宇宙、墩墩
竞品：雅迪/莱茵、九号/Q3
```

该帖生成四个 `matched_pairs`：

```text
元宇宙 × 雅迪/莱茵
元宇宙 × 九号/Q3
墩墩 × 雅迪/莱茵
墩墩 × 九号/Q3
```

但 `comparison_posts.jsonl` 中这篇帖子仍然只占一行；对应 `comparison_posts.xlsx` 的“内容”Sheet 也只占一行，避免后续抓评论、统计、人工检查或 LLM 分析时重复处理同一个 content identity。

## 6. 输出

每次运行创建独立目录：

```text
output/
└── runs/
    └── <run_id>/
        ├── comparison_posts.jsonl
        ├── comparison_posts.xlsx
        └── run_summary.json
```

### 6.1 comparison_posts.jsonl

每行结构：

```json
{
  "schema_version": "vehicle-pair-record.v1",
  "record": {"...": "原始 UnifiedContentRecordV1"},
  "matched_target_models": ["元宇宙"],
  "matched_competitor_models": [
    {"brand": "雅迪", "model": "莱茵"}
  ],
  "matched_pairs": [
    {
      "target_model": "元宇宙",
      "competitor_brand": "雅迪",
      "competitor_model": "莱茵"
    }
  ],
  "model_mentions": [
    {
      "brand": "爱玛",
      "model": "元宇宙",
      "fields": ["title"],
      "matched_aliases": ["元宇宙"]
    }
  ]
}
```

`model_mentions` 用来解释车型为什么被识别：命中了标题还是正文，以及具体命中的标准名/alias。

### 6.2 comparison_posts.xlsx

Excel 从上面的 JSONL 重新读取 `VehiclePairRecordV1` 后，通过共享 Provider-neutral Excel Exporter 生成，不自己维护 Workbook Schema、样式或 Formula/ID 规则。

Workbook 仍遵守统一三 Sheet：

```text
内容
标签明细
评论
```

本阶段没有 AI 标签和评论，因此“标签明细”“评论”只保留统一表头，不伪造数据行；人工查看主要使用“内容”Sheet。

“内容”Sheet 选择现有统一合法列，包含帖子基础信息、互动指标和：

```text
品牌
品牌角色
竞品范围
车型
```

例如一帖同时命中：

```text
爱玛：元宇宙、墩墩
雅迪：莱茵
九号：Q3
```

Excel 仍只写一条 Content 行，其中展示：

```text
品牌      爱玛；雅迪；九号
品牌角色  自有品牌；竞品品牌；竞品品牌
竞品范围  混合品牌
车型      元宇宙；墩墩；莱茵；Q3
```

精确 `matched_pairs` 与 alias 命中证据仍保留在 JSONL，不为了人工展示新增第二套 Excel 私有字段。

## 7. run_summary.json

摘要包含：

```text
rows_seen
rows_with_target_model
rows_with_competitor_model
rows_with_cross_brand_pair
rows_filtered_out

target_model_counts
competitor_model_counts
pair_counts
```

`outputs` 同时记录：

```text
comparison_posts
comparison_posts_excel
```

其中车型/pair 计数只统计最终进入 `comparison_posts.jsonl` 的帖子；每个帖子对同一个车型或 pair 最多贡献 1 次。

成功运行满足：

```text
rows_seen
= rows_with_cross_brand_pair
+ rows_filtered_out

Excel 内容数据行数
= rows_with_cross_brand_pair
= comparison_posts.jsonl 有效行数
```

注意 `rows_with_target_model` 与 `rows_with_competitor_model` 可以重叠，也可能包含最终因缺少另一侧车型而被过滤的帖子，因此两者不能相加做总量对账。

## 8. 运行

从仓库根目录执行：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs
```

成功后终端打印：

```text
run_id
rows_seen
matched
output
excel
```

其中：

```text
output → comparison_posts.jsonl
excel  → comparison_posts.xlsx
```

## 9. 失败与数据安全

- 输入 JSONL 只读；
- catalog 或输入 Contract 非法时 fail closed；
- `comparison_posts.jsonl` 使用临时文件 + `fsync` + 原子替换；
- `comparison_posts.xlsx` 复用共享 Exporter 的临时文件 + Workbook readback 校验 + 原子替换；
- Excel 从最终 JSONL 派生，并校验 Excel Content 行数必须等于共现 JSONL 帖子数；
- JSONL、Excel、摘要任一步失败时都会删除本次新建 run 目录，不留下看似成功的半截正式结果；
- 全流程逐行处理，不把完整 JSONL 一次性加载到内存；
- `output/` 已被当前目录 `.gitignore` 排除，不提交真实数据产物。
