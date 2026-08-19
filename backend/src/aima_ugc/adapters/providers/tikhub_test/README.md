# TikHub 五平台独立测试 / 调试

本目录用于**脱离数据库**直接验证 TikHub 五个平台采集链。它不是第二套采集器：Search、Detail、一级评论、二级回复、分页、Mapper、Capability 和 Collection Decision 都复用 `aima_ugc.adapters.providers.tikhub` 的正式生产实现。

支持平台：小红书、抖音、微博、B站、快手。

## 1. 配置 TikHub URL 和密钥

复制本目录的 `.env.example` 为 `.env`：

```text
TIKHUB_BASE_URL=https://api.tikhub.io
TIKHUB_API_KEY=你的真实密钥
TIKHUB_TIMEOUT_SECONDS=300
```

`.env` 已被 Git 忽略，**不要提交真实密钥**。代码默认读取 `tikhub_test/.env`，也可通过函数显式指定 `env_file`。本地真实调试使用 `https://api.tikhub.io`；生产 Transport 负责 Origin 白名单校验，任意未允许的第三方 Origin 都会在发送 Secret 之前被拒绝。

## 2. 关键词在哪里配置

关键词属于每次调试的业务参数，直接在平台函数中设置，不写进 `.env`。

单关键词：

```python
from aima_ugc.adapters.providers.tikhub_test import run_xiaohongshu

result = run_xiaohongshu(
    keyword="爱玛",
)
```

多关键词推荐使用 `keywords`：

```python
result = run_xiaohongshu(
    keywords=("爱玛", "爱玛电动车", "周冠宇"),
)
```

也可以传列表：

```python
result = run_xiaohongshu(
    keywords=["爱玛", "爱玛电动车", "周冠宇"],
)
```

规则：

- `keyword` 和 `keywords` 不能同时传；
- 二者都不传时默认使用 `爱玛`；
- 空关键词关闭失败；
- 同一组关键词中完全相同的词会去重并保持首次出现顺序；
- 每个关键词分别执行自己的 Search/分页；
- **同一帖子被多个关键词命中时，只执行一次后续 Detail/评论/回复，避免重复付费**；
- `run_summary.json` 和 Excel 的“命中关键词”列保留该帖子命中的全部关键词。

## 3. 平台入口

```python
from aima_ugc.adapters.providers.tikhub_test import (
    run_bilibili,
    run_douyin,
    run_kuaishou,
    run_weibo,
    run_xiaohongshu,
)
```

### 小红书

```python
result = run_xiaohongshu(
    keywords=("爱玛", "爱玛电动车"),
    sort_mode="latest",
    published_within="7d",
    content_type="all",
    max_search_pages=10,
    max_comments_per_content=100,
    max_replies_per_root=20,
)
```

当前正式 Operation 支持的搜索值以生产代码为准；常用值包括：

- `sort_mode`: `general` / `latest` / `most_liked` / `most_commented` / `most_collected`；
- `published_within`: `all` / `1d` / `7d` / `180d`；
- `content_type`: `all` / `video` / `image` / `live`。

### 抖音

```python
result = run_douyin(
    keywords=("爱玛", "周冠宇"),
    sort_mode="latest",
    published_within="7d",
    duration="all",
    content_type="all",
    max_comments_per_content=100,
)
```

支持生产 Search 已实现的 `sort_mode`、`published_within`、`duration`、`content_type`。

### 微博

```python
result = run_weibo(
    keywords=("爱玛", "爱玛电动车"),
    sort_mode="latest",
    published_within="week",
)
```

### B站

```python
result = run_bilibili(
    keywords=("爱玛", "爱玛电动车"),
    sort_mode="latest",
    content_type="video",
)
```

### 快手

```python
result = run_kuaishou(
    keywords=("爱玛", "爱玛电动车"),
)
```

快手当前主 Search Operation 没有额外统一排序/时间筛选参数，因此调试入口不虚构这些选项。

## 4. 评论、回复和请求范围

五个平台共用以下调试边界：

```python
max_search_pages = 20
max_contents = None
max_comments_per_content = 100
max_comment_pages_per_content = 20
max_replies_per_root = 20
max_reply_pages_per_root = 10
include_comments = True
include_replies = True
force_refresh = False
```

含义：

- `max_search_pages`：**每个关键词**最多搜索页数；
- `max_contents`：本次运行跨全部关键词最多处理的**唯一帖子总数**，`None` 表示不额外限制，由 Provider 末页/搜索页数停止；
- `max_comments_per_content`：每个帖子希望取得的一级评论目标；
- `max_comment_pages_per_content`：每帖一级评论最多翻页数；
- `max_replies_per_root`：每个一级评论希望取得的二级回复目标；
- `max_reply_pages_per_root`：每个一级评论的回复最多翻页数；
- `include_comments=False`：只验证 Search/Detail，不抓评论；
- `include_replies=False`：抓一级评论但不抓二级回复；
- `force_refresh=True`：即使跨运行状态显示评论数未变化，也允许受控重新抓评论。

这里**没有生产预算/费用硬上限系统**。节省费用依靠：关键词去重、帖子 ID 去重、评论 ID 去重、跨运行状态、Provider 末页、目标评论数和显式页数边界。

## 5. 输出目录

默认输出根目录：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/output/
```

结构：

```text
output/
└─ xhs/                         # douyin / weibo / bilibili / kuaishou 同理
   ├─ state.json                # 跨运行轻量去重状态
   └─ runs/
      └─ <run-id>/
         ├─ raw/
         │  ├─ 0001_search_notes.json
         │  ├─ 0002_detail....json
         │  └─ ...
         ├─ canonical/
         │  ├─ contents.jsonl
         │  └─ comments.jsonl
         ├─ raw_data/
         │  └─ xhs_raw_data.xlsx
         └─ run_summary.json
```

未显式传入 `run_id` 时，目录名使用 `Asia/Shanghai` 北京时间，并显式携带 `+0800` 偏移，例如 `20260818T141008.637851+0800`；Raw/Canonical 内部时间语义仍按各自正式 Contract 保持不变。

- `raw/`：每个真实请求的完整脱敏 Provider 响应；
- `canonical/`：正式 Mapper 产生的统一 `CanonicalContentV1 / CanonicalCommentV1`；
- `run_summary.json`：关键词、请求、停止原因、内容/评论数量、每条内容命中哪些关键词等运行事实；
- `raw_data/*.xlsx`：帖子 + 评论基础采集数据的人工可读视图，**不是舆情分析报告**；
- `state.json`：仅保存避免重复请求所需的帖子 ID、评论 ID、最近评论计数等轻量信息。

## 6. 去重逻辑

### 同一次运行

内容唯一身份：

```text
(platform, external_content_id)
```

多个关键词、不同搜索页命中同一个帖子时：

1. Raw Search 响应仍完整保存；
2. 记录新增的“命中关键词”；
3. 同一帖子只执行一次后续 Detail/评论/回复；
4. 评论按稳定 `external_comment_id` 去重。

不会使用标题、作者、链接等不稳定字段代替平台内容 ID。

### 跨运行

`output/<platform>/state.json` 会累积轻量去重状态。下次运行发现同一帖子且评论数没有变化时，生产 `CollectionDecisionService` 可跳过没有价值的 Detail/评论刷新。

需要完全重新验证时，可在确认不再需要历史调试状态后删除对应平台的 `state.json`。删除 `state.json` 不会删除历史 `runs/` Raw/Canonical/Excel。

## 7. Excel 说明

当前 TikHub 调试导出已经收口到统一 `UnifiedDataExcelV1` + 唯一共享 Exporter：

```text
CanonicalContentV1 / CanonicalCommentV1
→ tikhub_test 只做统一导出投影
→ aima_ugc.platform.export.excel
→ <platform>_raw_data.xlsx
```

工作簿固定为两个 Sheet：

- `内容`：每条内容一行，包含稳定内容 ID、内容/作者/指标、命中关键词、Provider、Raw 定位和评论覆盖状态；
- `评论`：每条一级/二级评论一行，保留 content/comment/root/parent ID 和 Raw 定位。

共享 Exporter 统一负责：

- 外部 ID 按文本保存，避免 Excel 科学计数法破坏 ID；
- HTTP(S) URL 生成可点击超链接；
- 长文本换行；
- Excel 公式注入防护；
- 时间转换为北京时间可读格式；
- write-only 流式写出；
- 写出后重新打开检查 Sheet、表头、行数和关键 ID。

`tikhub_test` 不再维护自己的 Workbook 布局实现，原 `tikhub_test/core/excel.py` 已删除；通用 Excel 行为测试也归属共享导出模块。以后 `imports_test`、正式数据导出和 TikHub 调试都必须复用同一 Exporter，不允许再建立平行的内容+评论 Excel 生成逻辑。

完整 TikHub 原始响应仍以 `raw/*.json` 为 Provider 事实，Canonical JSONL 仍是统一业务数据，不把 Excel 当 Provider Raw、数据库回灌格式或第二事实源。

统一导出设计门禁见 [`docs/blueprint/13-统一数据Excel导出与调试复用.md`](../../../../../../docs/blueprint/13-统一数据Excel导出与调试复用.md)。

## 8. 不使用命令行参数

本工具没有 CLI。直接在 Python 代码、IDE、调试器或临时 Python 文件中调用 `run_*()` 函数即可。

返回值 `TikHubTestRunResult` 会告诉你本次运行目录、Excel、manifest、内容数、一级评论数、二级回复数和真实请求数。
