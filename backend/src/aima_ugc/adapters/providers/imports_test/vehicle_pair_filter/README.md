# 爱玛车型 × 竞品车型增量共现筛选

本目录是 `imports_test` 的第二阶段离线工具。输入仍是第一阶段 `deduplicated/contents.jsonl`，匹配规则不变：一篇帖子必须至少命中 1 个爱玛车型和 1 个非爱玛车型。现在新增的是**本地历史自动接管与增量续跑**。

真实 `output/` 仍只存在本机，不上传 GitHub。

## 1. 数据流

```text
Stage 1 新 run delta
→ vehicle_pair_filter/filter_vehicle_pairs.py
→ 检查该输入 JSONL 的 SHA-256 是否已经处理
→ 未处理：执行车型 alias 匹配
→ 已处理：no-op，不重新车型分析
→ runs/<run_id>/comparison_posts.jsonl/.xlsx   # 本次 delta
→ current/comparison_posts.jsonl/.xlsx         # 历史 + 新增累计视图
```

Stage 2 不重新解析 Excel、不访问 PostgreSQL、不调用 TikHub/LLM。

## 2. 第一次升级自动接管旧 run

如果 `output/state/` 还没有增量状态，代码自动扫描：

```text
output/runs/*/run_summary.json
```

对仍存在的历史输入 JSONL 计算 SHA-256，并把它登记为已处理输入。旧：

```text
comparison_posts.jsonl
comparison_posts.xlsx
run_summary.json
```

全部只读保留。

因此你本地已经跑完的旧 Stage 2 run 不需要上传 GitHub，也不需要手工迁移。

## 3. 重复输入

同一个输入 JSONL 第二次运行：

```text
input_sha256 已存在于 state
→ input_skipped_cached = true
→ rows_seen = 0
→ 不执行车型文本扫描
→ 本次 run 输出空 delta JSONL/Excel 表头
```

累计 `current` 不受影响，仍包含历史有效车型共现记录。

第一阶段现在已经保证不同增量 run 之间 content identity 全局唯一，所以正常链路下 Stage 2 只需对最新 Stage 1 delta 做一次车型分析。

## 4. 车型匹配规则保持不变

只匹配：

```text
content.title
content.text
```

只认 [`backend/src/aima_ugc/adapters/providers/imports_test/vehicle_pair_filter/vehicle_catalog.json`](vehicle_catalog.json) 中的车型标准名和 aliases；不要求品牌名同时出现在帖子中。车型标准名本身自动作为 alias。

同一规范化 alias 不能属于两个不同车型，否则 fail closed。

例如：

```text
爱玛：元宇宙、墩墩
竞品：雅迪/莱茵、九号/Q3
```

一篇帖子会生成四个 `matched_pairs`，但 JSONL 和 Excel `内容` Sheet 仍然一帖一行。

## 5. 车型目录变化为什么会停止增量

Stage 2 的本地增量状态绑定当前 [`backend/src/aima_ugc/adapters/providers/imports_test/vehicle_pair_filter/vehicle_catalog.json`](vehicle_catalog.json) 的 SHA-256。

如果目录发生变化，历史帖子可能产生新的车型命中关系，因此程序不会静默沿用旧 Stage 2 state，而会明确报错：

```text
vehicle_catalog.json 已变化
```

此时需要使用新的 Stage 2 `output_root` 或明确重建 Stage 2 state。

这**不会导致评论重新抓取**：Stage 3 评论缓存按 `(platform, external_content_id)` 独立管理，车型规则重算后只复用旧 comments。

## 6. 输出

```text
output/
├── state/
├── current/
│   ├── comparison_posts.jsonl
│   └── comparison_posts.xlsx
└── runs/
    ├── <历史旧 run>/          # 原封不动
    └── <本次 run>/
        ├── comparison_posts.jsonl
        ├── comparison_posts.xlsx
        └── run_summary.json
```

### runs 是本次 delta

本次没有新输入时可以为空。

### current 是累计视图

代码从所有不可变成功 run 重新物化，并按正式 content identity 去重：

```text
(platform, external_content_id)
```

Excel 继续复用唯一 Provider-neutral：

```text
UnifiedDataExcelV1
project_canonical_content()
export_unified_data_excel()
```

内容 Sheet 包括帖子基础字段以及已有统一列：

```text
品牌
品牌角色
竞品范围
车型
```

## 7. run_summary.json 新增字段

```text
input_sha256
input_skipped_cached
outputs.current_comparison_posts
outputs.current_comparison_posts_excel
```

原有车型计数和 pair 计数保持不变。

## 8. 运行

编辑顶部：

```python
INPUT_JSONL = Path(r"...\monitoring_excel_filter\output\runs\<最新run>\deduplicated\contents.jsonl")
```

然后：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs
```

如果这个 Stage 1 delta 以前已经处理过，终端会显示：

```text
cached_input=True
rows_seen=0
```

## 9. 失败边界

- 输入/车型目录非法时 fail closed；
- 车型目录 SHA 漂移时 fail closed；
- JSONL/Excel 继续使用原子发布；
- `current` 是可由历史 runs 重建的展示视图，不反向修改旧 run；
- `output/` 仍由 `.gitignore` 排除，真实业务数据不提交 GitHub。
