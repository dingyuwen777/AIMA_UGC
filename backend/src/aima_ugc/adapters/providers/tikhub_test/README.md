# TikHub 五平台独立测试 / 调试

这个目录用于**人工验证 TikHub 五个平台的真实采集链**，不是第二套采集器。

它的核心原则是：

```text
人工传参数
→ 复用正式 TikHub Operation / Transport / Mapper / Capability
→ 复用正式 Collection Decision
→ 保存可检查的 Raw / Canonical / Excel / run summary
→ 可选进入正式 PostgreSQL 来源链
```

所以当你想确认“这个 endpoint 还能不能用”“某个平台字段是不是变了”“为什么评论没有继续翻页”“同一帖子为什么没有重复抓”时，可以从这里运行；但真正的 endpoint、分页、字段映射和业务决策仍由生产代码负责。

支持：小红书、抖音、微博、B站、快手。

深入理解当前 TikHub 结构：

- [`docs/appendix/02_TikHub五平台真实响应与字段映射.md`](../../../../../../docs/appendix/02_TikHub五平台真实响应与字段映射.md)
- [`docs/appendix/03_TikHub多接口验证与备用策略.md`](../../../../../../docs/appendix/03_TikHub多接口验证与备用策略.md)
- [`docs/appendix/04_TikHub接口选型与真实验证台账.md`](../../../../../../docs/appendix/04_TikHub接口选型与真实验证台账.md)
- [`docs/collection/README.md`](../../../../../../docs/collection/README.md)

## 1. 先看代码结构

当前目录：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/
├─ .env.example
├─ README.md
├─ __init__.py
├─ test.py
├─ core/
├─ operations/
└─ output/
```

生产 TikHub 实现不在这里，而在：

```text
backend/src/aima_ugc/adapters/providers/tikhub/
├─ transport.py
├─ runtime.py
├─ capabilities.py
├─ pricing.py / pricing.toml
├─ operations/
└─ mappers/
```

如果只是改人工入口的默认参数/输出路径，才优先改 `tikhub_test`；如果要改 endpoint、分页、Mapper 或 Capability，应先改生产 TikHub 代码和测试，再让本目录继续复用。

## 2. 配置 URL 和密钥

复制：

```text
.env.example
```

为同目录：

```text
.env
```

当前示例：

```text
TIKHUB_BASE_URL=https://api.tikhub.dev
TIKHUB_API_KEY=你的真实密钥
TIKHUB_TIMEOUT_SECONDS=300
```

`.env` 已被 Git 忽略。不要把真实 API Key 写进源码、README、Issue、日志或提交历史。

生产 `TikHubHttpTransport` 当前允许的 HTTPS Host 以：

- [`backend/src/aima_ugc/adapters/providers/tikhub/transport.py`](../tikhub/transport.py)

为准。当前默认 Base URL 是 `https://api.tikhub.dev`，同时允许显式使用 `https://api.tikhub.io`；其他 Origin 会在 Secret 发送前被拒绝。

### 数据库模式额外要求

`write_to_database=True` 时，还必须显式提供已经存在于正式 `provider_configs` 的 `provider_config_id`。

程序会核对：

```text
provider = tikhub
config 已启用
base_url 与当前调试 .env 一致
正式 secret_ref 解析出的 Secret 与当前调试 Secret 一致
```

不一致会在发送前失败，避免：

```text
本地调试文件记录账号 A
数据库来源链却记成账号 B
```

## 3. 关键词怎么传

关键词是本次人工调试参数，不放在 `.env`。

单关键词：

```python
from aima_ugc.adapters.providers.tikhub_test import run_xiaohongshu

result = run_xiaohongshu(keyword="爱玛")
```

多关键词：

```python
result = run_xiaohongshu(
    keywords=("爱玛", "爱玛电动车", "周冠宇"),
)
```

规则：

- `keyword` 与 `keywords` 不能同时传；
- 都不传时，当前人工入口默认使用“爱玛”；
- 空关键词失败；
- 重复关键词保留第一次；
- 每个关键词独立执行 Search/分页；
- 同一稳定内容被多个关键词命中时，后续 Detail/Comments/Replies 只处理一次；
- `run_summary.json` 与 Excel 仍保存全部命中关键词。

这里的关键词是**调试发现词**，不是正式数据库 Keyword Pack 的替代品。

## 4. 五个平台怎么调用

```python
from aima_ugc.adapters.providers.tikhub_test import (
    run_bilibili,
    run_douyin,
    run_kuaishou,
    run_weibo,
    run_xiaohongshu,
)
```

### 4.1 小红书

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

当前公开 Capability 的常用业务值：

```text
sort_mode:
  general
  latest
  most_liked
  most_commented
  most_collected
  english_preferred

published_within:
  all / 1d / 7d / 180d

content_type:
  all / video / image
```

注意：生产 Operation 的底层 Provider 参数可能还认识其他值，但**公开 Capability 当前没有把 live 作为可配置内容类型暴露**。人工调试不要用旧文档中的 `live` 推导生产正式支持。

当前主链：App V2 Search / Image Detail / Video Detail / Comments / Sub-comments。

### 4.2 抖音

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

当前 Search V2 Capability 支持业务排序、发布时间、时长和 `all/video/image` 内容类型；精确可选值看：

- [`backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py`](../tikhub/capabilities.py)
- [`backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py`](../tikhub/operations/douyin.py)

### 4.3 微博

```python
result = run_weibo(
    keywords=("爱玛", "爱玛电动车"),
    sort_mode="latest",
    published_within="week",
)
```

当前主链是：

```text
Web Search
→ App Detail
→ App Comments
→ Web V2 Sub-comments
```

不要因为同平台混用 App/Web 就自行统一 endpoint family；这是当前真实接口能力选择。

### 4.4 B站

```python
result = run_bilibili(
    keywords=("爱玛", "爱玛电动车"),
    sort_mode="latest",
    content_type="video",
)
```

当前 Search Capability 只公开视频内容，且 `native_time_filter=False`。

### 4.5 快手

```python
result = run_kuaishou(
    keywords=("爱玛", "爱玛电动车"),
)
```

快手当前正式主链使用 App：

```text
search_video_v2
fetch_one_video
fetch_video_comment
fetch_video_sub_comments
```

Web 评论链只保留 `verified_backup` 证据，不自动 fallback。

## 5. 通用请求边界

五个平台入口按当前函数 Contract 提供类似的调试保护参数，例如：

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
write_to_database = False
provider_config_id = None
```

白话理解：

- `max_search_pages`：每个关键词最多翻多少 Search 页；
- `max_contents`：跨全部关键词最多处理多少个唯一内容；
- `max_comments_per_content`：每个内容希望取得的一级评论软目标；
- `max_comment_pages_per_content`：一级评论技术页数上限；
- `max_replies_per_root`：每个根评论希望取得的回复软目标；
- `max_reply_pages_per_root`：回复技术页数上限；
- `include_comments=False`：只验证发现/详情；
- `include_replies=False`：只到一级评论；
- `force_refresh=True`：忽略部分跨运行“无需刷新”决策，做受控人工重验；
- `write_to_database=False`：纯文件调试；
- `write_to_database=True`：同一网络响应同时接入正式数据库来源链。

当前系统**没有生产预算/金额硬上限模块**。这些参数是人工调试/技术保护边界，不是预算账户。

真实 Provider 会产生费用时，运行前应根据当前主 endpoint 和：

- [`backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml`](../tikhub/pricing.toml)

估算请求规模。

## 6. 为什么同一个帖子不会被多个关键词重复抓详情

稳定内容身份：

```text
(platform, external_content_id)
```

同一运行内：

```text
多个 Search Raw 都保留
→ 汇总内容身份
→ 同一稳定内容只进入一次后续处理
→ matched_keywords 合并
```

评论用稳定 `external_comment_id` 去重。

不要用标题、作者名、URL 做主身份。

跨运行时：

```text
output/<platform>/state.json
```

保存人工调试需要的轻量状态，用于 Decision 判断是否值得再次抓 Detail/Comments。

它只是**省请求状态**，不是业务数据库；数据库模式最终仍由 Content Owner 的 UNIQUE、Version、Metric、来源历史保证幂等和可追溯。

## 7. 输出目录

默认：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/output/
```

典型结构：

```text
output/
└─ xiaohongshu/
   ├─ state.json
   └─ runs/
      └─ <run-id>/
         ├─ raw/
         ├─ canonical/
         │  ├─ contents.jsonl
         │  └─ comments.jsonl
         ├─ raw_data/
         │  └─ xiaohongshu_raw_data.xlsx
         └─ run_summary.json
```

含义：

- `raw/`：人工调试版脱敏真实响应；
- `canonical/`：生产 Mapper 的 `CanonicalContentV1 / CanonicalCommentV1`；
- `run_summary.json`：请求数、关键词、停止原因、内容/评论计数等；
- `raw_data/*.xlsx`：人工可读统一 Excel，不是舆情报告；
- `state.json`：下一次调试判断是否需要刷新所用的轻量状态。

数据库模式不会删除这些本地文件。

### 本地 Raw 与正式 Raw Artifact 的区别

`write_to_database=True` 时，同一个 Provider 响应会：

```text
先通过唯一一次 Transport 发送得到响应
├─ 镜像到 tikhub_test/raw/，便于人工检查
└─ 交给正式 RawArtifactService，进入 Artifact/Attempt 来源链
```

不会为了数据库再调用一次 TikHub。

## 8. Excel 为什么现在是三个 Sheet

`tikhub_test` 已收口到系统唯一共享 Excel Exporter：

```text
Canonical Content / Comment
→ UnifiedDataExcelV1
→ aima_ugc.platform.export.excel
→ <platform>_raw_data.xlsx
```

共享 Exporter 当前固定创建：

```text
内容
标签明细
评论
```

`tikhub_test` 本身没有 AI Analysis 时，`标签明细` 通常没有业务标签行，但 Sheet 结构仍由共享 Exporter 统一维护。

不要再按旧文档实现一套“两 Sheet TikHub Excel”。

共享 Exporter 负责：

- 长 ID 按文本写入；
- URL 超链接；
- 长文本换行；
- 公式注入防护；
- 北京时间显示；
- write-only 流式输出；
- 写完重新打开校验 Sheet、表头、行数和关键 ID；
- 临时文件验证后原子发布。

完整设计与当前代码：

- [`docs/appendix/06_Excel统一数据导出与离线调试.md`](../../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md)
- [`backend/src/aima_ugc/contracts/export/models.py`](../../../contracts/export/models.py)
- [`backend/src/aima_ugc/platform/export/excel.py`](../../../platform/export/excel.py)

Excel 不是 Raw，不作为数据库回灌事实源。

## 9. 显式 PostgreSQL 模式

默认：

```text
write_to_database=False
```

只进行文件调试，不装配 PostgreSQL Runtime。

显式：

```text
write_to_database=True
+ provider_config_id=<正式 UUID>
```

当前真实链路：

```text
校验 PostgreSQL / 当前 Schema
→ 校验 Provider Config / Secret / Base URL
→ 创建 manual Collection Run / Scope / Job Fencing
→ 每次实际 TikHub Operation 创建 Provider Request / billable Attempt
→ Transport 只发送一次
→ 本地 Raw 镜像 + 正式 Raw Artifact
→ Candidate-before-Mapper
→ 正式 Mapper / Canonical
→ 正式 fenced Content Ingestion
→ Content Current / Version / Metric / 来源历史
→ Run / Scope / Job 收敛终态
```

正式组合代码主要看：

- [`backend/src/aima_ugc/bootstrap/tikhub_test_database.py`](../../../bootstrap/tikhub_test_database.py)
- [`backend/src/aima_ugc/modules/collection/provider_dispatch.py`](../../../modules/collection/provider_dispatch.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py`](../../persistence/postgres/collection_content.py)

数据库模式固定：

- 不自动启动/关闭 Docker；
- 不自动执行 Alembic Migration；
- Schema 不满足当前代码就失败；
- 不创建 `TikHubDatabaseWriter` 或私有 Content Repository；
- 不从 Excel/JSONL 做第二次回灌；
- 不绕过 Job Fencing；
- 不因调试而绕过 Secret/Origin 校验。

## 10. 如何根据输出排障

### Search 有数据，但 Canonical 是空的

```text
raw/ Search
→ 当前平台 Operation extractor
→ 当前 Mapper
→ stable ID / required field
→ Canonical validation
```

字段结构参考：

- [`docs/appendix/02_TikHub五平台真实响应与字段映射.md`](../../../../../../docs/appendix/02_TikHub五平台真实响应与字段映射.md)

### Comment 数明明增长了，但没有继续抓评论

```text
Search/Detail 是否真实观察 comment_count
→ state.json previous observation
→ CollectionDecisionService
→ 该平台 Capability 是否支持 incremental comment sort
→ stop_reason
```

不要先在 `tikhub_test` 里写一个新的 if/else 绕过生产 Decision。

### 数据库模式有 Raw，但没有 Content

```text
Run / Scope
→ Provider Request / Attempt
→ Raw Artifact
→ Candidate
→ Mapper
→ 全局 Relevance
→ Content Ingestion
```

可以结合：

- [`docs/appendix/01_PostgreSQL查询与调试实战.md`](../../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md)

### 想完全重跑人工调试

`state.json` 只影响人工跨运行省请求。确认不需要历史调试状态后，可以删除对应平台 `state.json` 再运行；历史 `runs/` 不会因此删除。

不要为了“重跑”去删除数据库 Current 或 Raw Artifact。

## 11. 改不同问题应该改哪里

| 需求 | 正确修改入口 |
| --- | --- |
| 改人工默认关键词/页数/输出目录 | [`tikhub_test/test.py`](test.py) 或本目录调用参数 |
| 改某平台 endpoint/参数翻译 | `adapters/providers/tikhub/operations/<platform>.py` |
| 改分页推进/停止 | 对应生产 Operation / Runtime |
| 改 Provider Raw 字段映射 | `adapters/providers/tikhub/mappers/<platform>.py` |
| 改前端可配置能力 | [`adapters/providers/tikhub/capabilities.py`](../tikhub/capabilities.py) + Contract/API |
| 改 TikHub 单价 | [`adapters/providers/tikhub/pricing.toml`](../tikhub/pricing.toml) |
| 改内容去重/Current/Version | Content Owner，不在 `tikhub_test` |
| 改详情/评论是否继续抓 | Collection Decision，不在人工入口复制规则 |
| 改 Excel 列/安全/样式 | [`platform/export/excel.py`](../../../platform/export/excel.py) + Export Contract |
| 改数据库调试装配 | [`bootstrap/tikhub_test_database.py`](../../../bootstrap/tikhub_test_database.py)，同时保持正式来源链 |

## 12. 测试与真实 Probe

普通 CI 不发送真实付费 TikHub 请求。

自动验证主要依赖：

```text
生产 Operation unit tests
Mapper + Sanitized Fixture tests
Capability tests
Collection Decision tests
Fake Transport PostgreSQL integration
共享 Excel tests
```

真实接口只在明确需要验证 Provider 当前行为时做受限 Probe：

```text
请求数/页数先限制
→ 使用生产 Operation/Transport
→ 保存合法脱敏证据
→ 必要时更新 Fixture/台账
→ 再修改 Mapper/Capability
```

不要用一次 HTTP 200 代替可重复 Fixture/自动测试。

## 13. 不要在这个目录做什么

- 不复制正式 endpoint；
- 不复制 Mapper；
- 不建立第二套分页；
- 不直接写 `contents` / `comments`；
- 不把 Excel 当 Raw 或回灌格式；
- 不实现自动 App/Web fallback；
- 不把 `state.json` 当业务数据库；
- 不提交真实 `.env`；
- 不把人工页数限制说成生产预算功能。
