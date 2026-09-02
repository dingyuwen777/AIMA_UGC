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
├─ xiaohongshu_accounts_test.py
├─ core/
├─ operations/
└─ output/
```

生产 TikHub 实现不在这里，而在：

```text
backend/src/aima_ugc/adapters/providers/tikhub/
├─ transport.py
├─ runtime.py
├─ account_runtime.py
├─ capabilities.py
├─ pricing.py / pricing.toml
├─ operations/
└─ mappers/
```

如果只是改人工入口的默认参数/输出路径，才优先改 `tikhub_test`；如果要改 endpoint、分页、Mapper 或 Capability，应先改生产 TikHub 代码和测试，再让本目录继续复用。

小红书指定账号 Discovery 的 Provider endpoint、Extractor 和分页也不写在 [`xiaohongshu_accounts_test.py`](xiaohongshu_accounts_test.py) 里，而由以下生产适配层统一维护：

- [`backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu_accounts.py`](../tikhub/operations/xiaohongshu_accounts.py)
- [`backend/src/aima_ugc/adapters/providers/tikhub/account_runtime.py`](../tikhub/account_runtime.py)

## 2. 配置 URL 和密钥

复制：

- [`backend/src/aima_ugc/adapters/providers/tikhub_test/.env.example`](.env.example)

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

通用关键词入口在 `write_to_database=True` 时，还必须显式提供已经存在于正式 `provider_configs` 的 `provider_config_id`。

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

**小红书指定账号入口当前固定为纯文件模式，不开放 `write_to_database=True`。** 它不是正式 Collection Plan / Scheduler / 数据库账号采集能力。

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

### 4.1 小红书关键词发现

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

当前关键词主链：App V2 Search / Image Detail / Video Detail / Comments / Sub-comments。

### 4.1.1 小红书指定账号按日期采集

公共入口：

```python
from aima_ugc.adapters.providers.tikhub_test import (
    XiaohongshuAccountTarget,
    run_xiaohongshu_accounts,
)

result = run_xiaohongshu_accounts(
    accounts=(
        XiaohongshuAccountTarget(nickname="爱玛电动车", red_id="49328786266"),
        XiaohongshuAccountTarget(nickname="爱玛三轮电动车", red_id="27247301529"),
    ),
    start_date="2026-08-01",
    end_date="2026-09-02",
    include_comments=True,
    include_replies=True,
    comment_mode="all",
)
```

仓库已经提供一个只放人工参数的薄入口：

- [`backend/src/aima_ugc/adapters/providers/tikhub_test/xiaohongshu_accounts_test.py`](xiaohongshu_accounts_test.py)

当前文件预置的五个目标账号是：

| 官号名称 | 小红书号 |
| --- | --- |
| 爱玛电动车 | `49328786266` |
| 爱玛三轮电动车 | `27247301529` |
| 爱玛东2楼 | `11132750536` |
| 我是玛小爱 | `1092546221` |
| 元宇宙女孩的实验室 | `6758835472` |

默认：

```text
START_DATE = 2026-08-01
END_DATE = 运行当天的北京时间日期
INCLUDE_COMMENTS = true
INCLUDE_REPLIES = true
COMMENT_MODE = all
```

账号身份规则：

```text
已知 user_id
→ 直接使用稳定身份

否则
→ search_users
→ red_id 精确匹配
→ nickname 只作辅助核验
→ 得到稳定 user_id
→ get_user_posted_notes
```

只有昵称且存在多个同名候选时会失败，不会默认选择第一条。已解析的稳定公开账号身份会缓存到：

```text
output/xiaohongshu/resolved_accounts.json
```

缓存不保存 API Key。

日期规则：

- `start_date` / `end_date` 都是**包含式**自然日；
- 内部按 `Asia/Shanghai` 转换为左闭右开的时间窗口；
- `get_user_posted_notes` 当前没有被假设成“看到旧笔记就可安全停止”，所以会继续按 Provider cursor 翻页，再做日期过滤；
- 翻页优先使用响应级下一页 `cursor`，只有响应未观察到该字段时才兼容回退到最后一条笔记的 cursor/note_id。

`comment_mode="all"` 的“全部”含义是：

```text
正数或未知 comment_count / reply_count
→ 不作为“已经抓完”的停止条件

显式 comment_count=0 / reply_count=0
→ 沿用正式 Collection Decision，跳过对应评论/回复接口

一旦进入评论/回复抓取
→ 继续翻页直到 Provider 明确 has_more=false / 分页耗尽
或
→ 技术硬页数上限触发
```

这是为了避免详情里的正数计数滞后导致漏掉 Provider 实际还能返回的下一页。一级评论和二级回复都有回归测试覆盖“数量已达到但 `has_more=true`”的情况。

仍保留：

```text
max_comment_pages_per_content
max_reply_pages_per_root
```

作为异常响应或极端数据量下的技术硬保护。如果硬上限先于 Provider 耗尽触发，运行摘要不能把该结果视为完整。二级回复由于共享 Runner 不暴露最终 Provider 停止原因，账号 `all` 在**触达回复硬页数边界**时采取保守策略，标记账号为 `partial`，避免假完整。

账号 Discovery 使用：

```text
search_users
get_user_info（只有 validate_user_info=True 时）
get_user_posted_notes
```

它们当前只批准给这个人工文件模式使用，不代表已经进入正式 `BusinessOperation` / Collection Capability / Pricing Dispatch。账号笔记拿到后，后续 Detail、Comments、SubComments、Mapper、Canonical 和 Excel 全部继续复用已有正式链路。

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

五个平台关键词入口按当前函数 Contract 提供类似的调试保护参数，例如：

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

指定账号入口的 `comment_mode="all"` 会忽略 `max_comments_per_content` / `max_replies_per_root` 这两个**软数量目标**，但不会忽略对应的硬页数上限；显式观察到评论/回复计数为 0 时仍沿用正式 Decision 的零值跳过语义。

当前系统**没有生产预算/金额硬上限模块**。这些参数是人工调试/技术保护边界，不是预算账户。

真实 Provider 会产生费用时，生产已登记 endpoint 可根据当前主链和：

- [`backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml`](../tikhub/pricing.toml)

估算请求规模。

小红书账号 Discovery 三个 endpoint 当前未进入生产 Pricing Dispatch；不要为人工文件模式编造价格。若未来升级为正式 Collection Source，必须先重新核验官方单价并登记 Pricing。

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

指定账号入口仍使用同一个 `(platform, external_content_id)` 内容身份，不建立“官号笔记”专用主键或 Schema。

不要用标题、作者名、URL 做主身份。

跨运行时：

```text
output/<platform>/state.json
```

保存通用人工调试需要的轻量状态，用于 Decision 判断是否值得再次抓 Detail/Comments。

它只是**省请求状态**，不是业务数据库；数据库模式最终仍由 Content Owner 的 UNIQUE、Version、Metric、来源历史保证幂等和可追溯。

## 7. 输出目录

默认：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/output/
```

指定账号典型结构：

```text
output/
└─ xiaohongshu/
   ├─ state.json
   ├─ resolved_accounts.json
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
- `run_summary.json`：请求数、停止原因、内容/评论计数；账号模式还包含逐账号解析/页数/失败信息；
- `raw_data/*.xlsx`：人工可读统一 Excel，不是舆情报告；
- `state.json`：通用调试 Decision 使用的轻量状态；
- `resolved_accounts.json`：账号模式的稳定公开身份解析缓存，不含 Secret。

数据库模式不会删除这些本地文件。

### 本地 Raw 与正式 Raw Artifact 的区别

通用入口 `write_to_database=True` 时，同一个 Provider 响应会：

```text
先通过唯一一次 Transport 发送得到响应
├─ 镜像到 tikhub_test/raw/，便于人工检查
└─ 交给正式 RawArtifactService，进入 Artifact/Attempt 来源链
```

不会为了数据库再调用一次 TikHub。

指定账号入口当前固定纯文件模式，因此只生成本地脱敏 Raw/Canonical/Excel/run summary，不创建数据库 Provider Request/Attempt。

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

通用关键词入口默认：

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

指定账号入口当前不提供数据库模式；若以后需要长期官号监控，应把账号 Discovery 正式提升为 Collection Source，而不是给当前薄脚本直接加数据库写入。

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

### 指定账号找错或找不到

按顺序检查：

```text
配置 red_id 是否正确
→ raw/search_users 对应请求
→ run_summary 的 resolved_red_id / resolved_user_id
→ 是否因为同名或搜索页上限 fail closed
→ resolved_accounts.json 是否仍与当前 red_id 一致
```

不要把昵称搜索第一条直接当稳定身份。

### Comment 数明明增长了，但没有继续抓评论

通用关键词调试：

```text
Search/Detail 是否真实观察 comment_count
→ state.json previous observation
→ CollectionDecisionService
→ 该平台 Capability 是否支持 incremental comment sort
→ stop_reason
```

指定账号 `comment_mode="all"`：

```text
Provider has_more / cursor
→ max_comment_pages_per_content
→ max_reply_pages_per_root
→ run_summary 是否标记 partial
```

不要在薄配置入口复制一套 Provider 分页。

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

`state.json` 只影响通用人工跨运行省请求。确认不需要历史调试状态后，可以删除对应平台 `state.json` 再运行；历史 `runs/` 不会因此删除。

账号解析缓存 `resolved_accounts.json` 只保存稳定公开身份；当账号配置的 `red_id/user_id` 发生变化或需要强制重新解析时，可以删除对应缓存后再运行。

不要为了“重跑”去删除数据库 Current 或 Raw Artifact。

## 11. 改不同问题应该改哪里

| 需求 | 正确修改入口 |
| --- | --- |
| 改人工默认关键词/页数/输出目录 | [`backend/src/aima_ugc/adapters/providers/tikhub_test/test.py`](test.py) 或本目录调用参数 |
| 改小红书指定账号/日期/人工页数 | [`backend/src/aima_ugc/adapters/providers/tikhub_test/xiaohongshu_accounts_test.py`](xiaohongshu_accounts_test.py) |
| 改小红书账号 Discovery endpoint/分页 | [`backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu_accounts.py`](../tikhub/operations/xiaohongshu_accounts.py) + [`backend/src/aima_ugc/adapters/providers/tikhub/account_runtime.py`](../tikhub/account_runtime.py) |
| 改某平台关键词 endpoint/参数翻译 | 对应 `adapters/providers/tikhub/operations/<platform>.py` |
| 改分页推进/停止 | 对应生产 Operation / Runtime |
| 改 Provider Raw 字段映射 | 对应 `adapters/providers/tikhub/mappers/<platform>.py` |
| 改前端可配置能力 | [`backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py`](../tikhub/capabilities.py) + Contract/API |
| 改 TikHub 单价 | [`backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml`](../tikhub/pricing.toml) |
| 改内容去重/Current/Version | Content Owner，不在 `tikhub_test` |
| 改正式详情/评论是否继续抓 | Collection Decision，不在人工入口复制规则 |
| 改账号人工 `limited/all` 策略 | [`backend/src/aima_ugc/adapters/providers/tikhub_test/operations/xiaohongshu_accounts.py`](operations/xiaohongshu_accounts.py)，不得修改正式 Decision Contract |
| 改 Excel 列/安全/样式 | [`backend/src/aima_ugc/platform/export/excel.py`](../../../platform/export/excel.py) + Export Contract |
| 改数据库调试装配 | [`backend/src/aima_ugc/bootstrap/tikhub_test_database.py`](../../../bootstrap/tikhub_test_database.py)，同时保持正式来源链 |

## 12. 测试与真实 Probe

普通 CI 不发送真实付费 TikHub 请求。

自动验证主要依赖：

```text
生产 Operation unit tests
Mapper + Sanitized Fixture tests
Capability tests
Collection Decision tests
Fake Transport 纵切 / PostgreSQL integration
共享 Excel tests
```

指定账号能力另外用 Fake Transport 覆盖：

- `red_id` 精确匹配和昵称歧义 fail closed；
- 用户 Search/Notes 分页推进与异常停止；
- 响应级用户笔记 cursor 优先于列表项兼容回退值；
- 北京时间日期过滤；
- 账号 Discovery → Detail → Comments → Canonical JSONL → Excel；
- `all` 在正数 `comment_count` 已达到但 Provider 仍 `has_more=true` 时继续翻一级评论；
- `all` 在正数 `reply_count` 已达到但 Provider 仍 `has_more=true` 时继续翻二级回复；
- 回复触达 `max_reply_pages_per_root` 边界时保守标记 `partial`，避免假完整。

真实接口只在明确需要验证 Provider 当前行为时做受限 Probe：

```text
请求数/页数先限制
→ 使用生产 Operation/Transport
→ 保存合法脱敏证据
→ 必要时更新 Fixture/台账
→ 再修改 Mapper/Capability
```

当前指定账号开发不能因为聊天里出现过 API Key 就把它写进 Workflow、命令、Issue、PR 或日志。只有 GitHub Runner 能**安全引用已经存在的 Actions Secret**时，才能执行新的付费真实 Probe；否则必须把“未做真实 Probe”作为明确限制保留。

不要用一次 HTTP 200 代替可重复 Fixture/自动测试。

## 13. 不要在这个目录做什么

- 不复制正式 endpoint；
- 不复制 Mapper；
- 不建立第二套分页；
- 不直接写 `contents` / `comments`；
- 不把 Excel 当 Raw 或回灌格式；
- 不实现自动 App/Web fallback；
- 不把 `state.json` / `resolved_accounts.json` 当业务数据库；
- 不提交真实 `.env`；
- 不把人工页数限制说成生产预算功能；
- 不把指定账号人工文件入口直接描述成正式官号监控/调度能力。
