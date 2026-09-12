# 车型共现帖子五平台评论补采

本目录是 `imports_test` 下新的**第三阶段独立离线工具**。它直接读取第二阶段 `vehicle_pair_filter` 产生的 `comparison_posts.jsonl`，不再先把帖子物理拆成五个平台文件，而是逐帖读取正式 `platform + content identity`，复用生产 TikHub Runtime 抓取该帖全部一级评论和全部二级回复。

## 1. 当前三阶段数据流

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
→ comparison_comment_enrichment/enrich_comments.py
→ 逐帖读取 platform + external_content_id + alternate_ids
→ TikHub Comments / SubComments 正式 Runtime
→ comparison_posts_with_comments.jsonl
→ comparison_posts_with_comments.xlsx
```

旧的 `cross_brand_platform_split` 已退出主链，因为 TikHub Runtime 本身已经能根据正式平台身份 dispatch 到五个平台的评论接口；先拆成五个文件再统一处理只会增加一次无业务价值的 I/O。

## 2. 输入

编辑本目录 [enrich_comments.py](enrich_comments.py) 顶部：

```python
INPUT_JSONL = Path(
    r"E:\AIMA_UGC_data\vehicle_pair_filter\output\runs\<run_id>\comparison_posts.jsonl"
)
```

每个非空行必须是第二阶段正式输出 `VehiclePairRecordV1`。工具在发出任何 Provider 请求前会先完整扫描并校验输入 JSONL；输入格式错误时不会先消耗 TikHub 请求。

## 3. TikHub 配置

沿用现有 `tikhub_test` 配置：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/.env
```

可从同目录 `.env.example` 复制后填写：

```text
TIKHUB_BASE_URL=https://api.tikhub.dev
TIKHUB_API_KEY=...
TIKHUB_TIMEOUT_SECONDS=300
```

真实 API Key 不写入本工具、不写入 JSONL/Excel/summary/Raw；确定响应 Raw 继续通过现有 `RunOutputStore` 脱敏后落盘。

## 4. 五个平台统一 ID dispatch

本工具不自己维护 Provider endpoint 或平台私有 ID 规则，全部复用：

```text
aima_ugc.adapters.providers.tikhub.runtime
```

当前 Runtime 会从 Canonical 内容身份自动选择：

```text
xiaohongshu → note_id
douyin      → aweme_id
weibo       → status_id
bilibili    → bv_id / av_id
kuaishou    → photo_id
```

`alternate_ids` 中存在 Provider typed identity 时优先使用，否则按现有 Runtime 的稳定 `external_content_id` fallback 规则处理。

一级评论固定复用：

```text
build_comments_call
extract_comment_items
map_comment
advance_comments
```

二级回复固定复用：

```text
build_sub_comments_call
extract_sub_comment_items
map_comment
advance_sub_comments
```

因此新增平台 API 差异仍由 TikHub Adapter/Runtime Owner 维护，本工具只负责“已知帖子 ID → 全量评论补采”的批处理编排。

## 5. “全部评论”的精确定义

现有 `tikhub_test/run_xxx()` 搜索调试入口默认有：

```text
max_comments_per_content=100
max_comment_pages_per_content=20
max_replies_per_root=20
max_reply_pages_per_root=10
```

这些适合搜索调试，不等于本任务需要的“全部评论”。

本工具**不使用上述采样数量/页数上限**：

```text
一级评论
→ 从第一页开始
→ Runtime advance_comments() 给出下一页就继续
→ 直到 Runtime 明确停止

二级回复
→ reply_count == 0：不发无意义请求
→ reply_count > 0 或未知：开始补采
→ Runtime advance_sub_comments() 给出下一页就继续
→ 直到 Runtime 明确停止
```

分页终止、游标不推进等规则继续由五平台正式 Runtime 负责，不在本工具复制 Provider-private 分页算法。

## 6. 输出 JSONL

成功 run：

```text
output/runs/<run_id>/
├── comparison_posts_with_comments.jsonl
├── comparison_posts_with_comments.xlsx
├── run_summary.json
└── provider/
    └── <platform>/runs/comments/
        ├── raw/
        ├── canonical/comments.jsonl
        └── raw_data/
```

`comparison_posts_with_comments.jsonl` 仍保持**一帖一行**。每行：

```text
VehiclePairCommentRecordV1
├── record
│   └── 原完整 VehiclePairRecordV1
│       ├── 原帖子
│       ├── matched_target_models
│       ├── matched_competitor_models
│       ├── matched_pairs
│       └── model_mentions
├── comments[]
│   └── CanonicalCommentV1
└── comment_fetch
    ├── coverage
    ├── reported_total
    ├── root_comment_count
    ├── reply_count
    ├── request_count
    ├── root_stop_reason
    └── failures[]
```

同一帖子内按稳定 `external_comment_id` 去重。Canonical 根评论保持 `root_comment_id == external_comment_id`；回复保留正式 `root_comment_id / parent_comment_id`，不会为了 Excel 展示改写 Canonical。

## 7. Coverage 与失败语义

### complete

一级评论分页正常耗尽，所有需要补采的根评论也完成回复分页，没有 Provider 永久失败；如果帖子已知一级评论总数，实际一级评论数不能少于该值；如果某个一级评论已知 `reply_count`，实际拿到的该根评论回复数也不能少于该值。`complete` 因此不仅表示“分页 API 停止”，还必须通过已知数量对账。

### partial

以下情况保留已取得的数据，但不会声明完整：

- 某个一级评论页或回复页发生可归因到单内容的永久 4xx，记录 `failures[]` 和对应脱敏 Raw 定位；
- Provider 一级评论分页已停止，但帖子存在已知 `comment_count`，且本次实际一级评论数更少，此时 `root_stop_reason` 会包含 `observed_lt_reported_total`。

### unavailable

该帖在获得任何评论前即发生可归因到单内容的永久 4xx。

### 整次 run 直接失败

以下情况不继续批量请求，也不会发布正式 `runs/<run_id>`：

```text
HTTP 401 / 403
HTTP 408 / 425 / 429
HTTP 5xx
Transport 连接失败或发送状态未知
成功响应不是 JSON Object
Mapper / Contract / 分页不变量异常
complete 记录与一级评论已知 reply_count 对账失败
输入 JSONL Contract 错误
```

其中已知回复数短缺不会被伪装成 `complete`；输出 Contract 会直接拒绝该记录并让本次 run fail closed。401/403 属于配置级认证失败；429/5xx/Transport 异常属于需要停止并稍后重试的运行级边界，避免继续打 Provider。

## 8. Excel

同一次 run 自动调用现有：

```text
export_unified_data_excel()
```

生成：

```text
comparison_posts_with_comments.xlsx
```

继续使用正式 Provider-neutral `UnifiedDataExcelV1`：

- `内容` Sheet：一帖一行；
- `评论` Sheet：一级评论和二级回复逐行展示，并通过内容 ID 关联帖子；
- 评论层级由 Canonical root/parent identity 投影为“一级 / 二级”；
- 内容行继续携带命中关键词，并从第二阶段 `model_mentions` 投影品牌、品牌角色、竞品范围和车型；
- `评论覆盖` 显示 complete/partial/unavailable 与本次一级/二级采集数。

JSONL 是完整机器事实；Excel 是现有受控展示格式，不反向修改 JSONL。

## 9. 运行

从仓库根目录：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.comparison_comment_enrichment.enrich_comments
```

完成后终端打印帖子数、complete/partial/unavailable、一级评论数、回复数、请求数、五平台帖子数和输出目录。

## 10. 成本与重跑

“全部评论”意味着请求数由真实评论页数和回复页数决定，可能显著高于搜索调试的采样模式。工具不隐藏自动重试，也不把 Provider partial 冒充 complete。

当前版本是离线一次性批处理：失败 run 不发布正式结果；成功 run 使用独立 `run_id`，不会覆盖旧结果。后续如果数据规模证明需要断点续跑/并发窗口，再基于真实耗时和 Provider 限额单独设计，不在当前简单链路中预先引入复杂调度。
