# 车型共现帖子五平台增量评论补采

本目录是 `imports_test` 的第三阶段离线工具。它直接读取第二阶段 `comparison_posts.jsonl`，按正式 `platform + content identity` 调用现有 TikHub Runtime 抓一级评论和二级回复。现在默认具备**本机历史评论自动接管与缓存复用**：已经成功产出的评论 run 不需要上传 GitHub，也不会因为重新运行脚本而重复请求 TikHub。

## 1. 三阶段增量链路

```text
Stage 1
新增 Excel
→ 只输出全局新增帖子 delta

Stage 2
新帖子 delta
→ 只做一次车型共现分析
→ comparison_posts.jsonl delta

Stage 3
comparison_posts.jsonl
→ 查本地 comment cache
├─ cache hit  → 直接读取旧 run comments/coverage，Provider 请求 = 0
└─ cache miss → TikHub Runtime 全量抓评论
→ runs/<run_id>/comparison_posts_with_comments.jsonl/.xlsx
→ current/comparison_posts_with_comments.jsonl/.xlsx  # 历史 + 新增累计全量
```

## 2. 第一次升级会自动识别你本机已有数据

如果 `output/state/` 还没有评论缓存状态，代码自动扫描本机：

```text
output/runs/*/run_summary.json
output/runs/*/comparison_posts_with_comments.jsonl
```

每个旧 `VehiclePairCommentRecordV1` 会建立：

```text
(platform, external_content_id)
→ 历史 JSONL path + byte offset
```

索引保存在 `output/state/cache_index/` 的 256 个 JSONL 分片中。

state **不复制评论正文**；comments 仍只存在原来的不可变历史 run JSONL 中。旧 run 不修改、不删除、不覆盖。

因此你已经在本地完整跑过的评论数据会自动成为缓存基线，不要求重新抓取。

## 3. 默认缓存策略

当前固定：

```text
reuse-any-committed-result.v1
```

也就是只要某帖子已经存在 committed 历史结果，就默认复用：

```text
complete
partial
unavailable
```

都不会自动重试。

最重要的行为：

```text
历史帖子再次输入
→ rows_cached += 1
→ rows_fetched 不增加
→ request_count 不增加
→ TikHub Transport.send() 不执行
```

这样不会因为误把旧 `comparison_posts.jsonl` 再跑一次而重复付费。

以后如果确实需要刷新旧帖新增评论，应单独增加显式 `force/ttl/retry_incomplete` 策略；当前任务不做后台自动刷新。

## 4. 车型规则变化不会导致评论重抓

评论缓存只按：

```text
(platform, external_content_id)
```

识别。

如果第二阶段以后因为 [`backend/src/aima_ugc/adapters/providers/imports_test/vehicle_pair_filter/vehicle_catalog.json`](../vehicle_pair_filter/vehicle_catalog.json) 改动重算了某篇旧帖子，Stage 3 会：

```text
使用本次最新 VehiclePairRecordV1
+
历史缓存 comments[]
+
历史 comment_fetch
```

重新组装输出。

因此 pair metadata 可以更新，但评论不会因为车型规则变化再次请求 TikHub。

## 5. TikHub Runtime 仍是唯一 Provider 事实源

cache miss 时继续复用正式：

```text
build_comments_call
extract_comment_items
map_comment
advance_comments

build_sub_comments_call
extract_sub_comment_items
map_comment
advance_sub_comments
```

Typed identity 继续由 Runtime 处理：

```text
xiaohongshu → note_id
douyin      → aweme_id
weibo       → status_id
bilibili    → bv_id / av_id
kuaishou    → photo_id
```

本工具不复制 endpoint、分页或 Mapper 规则。

## 6. “全部评论”语义

对 cache miss：

```text
一级评论
→ 一直 advance_comments() 到 Provider/Runtime 明确停止

二级回复
→ 已知 reply_count == 0 时跳过
→ 其他情况一直 advance_sub_comments() 到明确停止
```

不使用 `tikhub_test` 搜索调试入口原来的 100 条、20 页、10 页等采样上限。

`complete` 仍要求已知 `comment_count/reply_count` 数量对账；不足时不能伪装成 complete。

## 7. 输出

```text
output/
├── state/
│   └── cache_index/*.jsonl
├── current/
│   ├── comparison_posts_with_comments.jsonl
│   └── comparison_posts_with_comments.xlsx
└── runs/
    ├── <历史旧 run>/                 # 原封不动
    └── <本次 run>/
        ├── comparison_posts_with_comments.jsonl
        ├── comparison_posts_with_comments.xlsx
        ├── run_summary.json
        └── provider/                  # 仅 cache miss 才产生新的 Raw/Canonical
```

### run 输出

表示本次输入帖子处理结果；其中既可能包含：

```text
cached records
fetched records
```

但 cached 记录没有新 Provider 请求。

### current 输出

`current` 从 cache index 的最新 locator 重建，所以始终表示当前本地累计：

> 所有历史缓存帖子 + 本次新增帖子及评论。

Excel 继续复用唯一 Provider-neutral `export_unified_data_excel()`：

- `内容`：一帖一行；
- `评论`：一级/二级逐行；
- 内容和评论通过稳定 content ID 关联。

## 8. run_summary.json 重点看这些字段

```text
rows_seen
rows_cached
rows_fetched
rows_complete
rows_partial
rows_unavailable
root_comment_count
reply_count
request_count
failure_count
```

如果你重新运行一批已经缓存的旧帖子，预期看到：

```text
rows_seen=10000
rows_cached=10000
rows_fetched=0
request_count=0
```

这就是“没有重复抓评论”的直接证据。

## 9. Provider 配置

cache miss 时沿用：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/.env
```

真实 API Key 不写入 JSONL/Excel/summary/Raw。确定响应仍先通过现有 `RunOutputStore` 脱敏落盘。

## 10. 运行

编辑：

```python
INPUT_JSONL = Path(
    r"...\vehicle_pair_filter\output\runs\<run_id>\comparison_posts.jsonl"
)
```

然后：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.comparison_comment_enrichment.enrich_comments
```

终端会打印：

```text
rows
cached
fetched
complete / partial / unavailable
requests
current
```

## 11. 失败与恢复

- 输入 JSONL 在任何网络请求前完整校验；
- 429/408/425/5xx/Transport 等运行级失败继续 fail closed；
- 永久单帖 4xx 仍按 partial/unavailable 保存；
- 新 run 通过 staging 目录原子发布；
- 只有已经存在 `run_summary.json` 的完成 run 才会被后续自动纳入 cache；
- 如果 run 已成功发布，但 state/current 更新中断，下次启动会从该不可变 run 自动补 cache，因此不会因为 state 落后而重复请求 Provider；
- `output/` 由 `.gitignore` 排除，真实本地评论数据不提交 GitHub。
