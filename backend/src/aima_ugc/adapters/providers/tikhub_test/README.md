# TikHub 五平台独立测试 / 调试

本目录用于人工验证 TikHub 五个平台采集链。它不是第二套采集器：Search、Detail、一级评论、二级回复、分页、Mapper、Capability 和 Collection Decision 都复用 `aima_ugc.adapters.providers.tikhub` 的正式生产实现。

默认 `write_to_database=False`，因此仍可**脱离数据库**只保存调试文件；显式开启数据库模式后，同一次 TikHub 请求同时保留本地调试 Raw，并进入正式 Collection / Provider / Raw / Candidate / Ingestion 来源链写入 PostgreSQL，不会为了写库再发送第二次 Provider 请求。

支持平台：小红书、抖音、微博、B站、快手。

## 1. 配置 TikHub URL 和密钥

复制本目录的 `.env.example` 为 `.env`：

```text
TIKHUB_BASE_URL=https://api.tikhub.dev
TIKHUB_API_KEY=你的真实密钥
TIKHUB_TIMEOUT_SECONDS=300
```

`.env` 已被 Git 忽略，**不要提交真实密钥**。代码默认读取 `tikhub_test/.env`，也可通过函数显式指定 `env_file`。当前默认 TikHub Origin 为 `https://api.tikhub.dev`；为兼容既有配置，`https://api.tikhub.io` 仍可显式使用，但任意未允许的第三方 Origin 都会在发送 Secret 之前被拒绝。

数据库模式还要求正式 `provider_configs` 中存在一个已启用的 `provider=tikhub` 配置，并显式传入它的 `provider_config_id`。该配置的 `base_url` 与 Secret 必须和当前 `tikhub_test/.env` 实际使用的 URL/API Key 一致；不一致时在发送请求前关闭失败，避免“调试文件用一套凭据、正式来源链记录另一套配置”。

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

默认 file-only：

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

显式数据库模式：

```python
from uuid import UUID

result = run_xiaohongshu(
    keywords=("爱玛", "爱玛电动车"),
    sort_mode="latest",
    published_within="7d",
    content_type="all",
    write_to_database=True,
    provider_config_id=UUID("正式 provider_configs.id"),
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

五个平台的 `run_*()` 都支持相同的数据库开关：

```python
write_to_database = False
provider_config_id = None
```

只有 `write_to_database=True` 时 `provider_config_id` 才是必填；默认 file-only 不需要它，也不会装配数据库 Runtime。

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
write_to_database = False
provider_config_id = None
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
- `force_refresh=True`：即使跨运行状态显示评论数未变化，也允许受控重新抓评论；
- `write_to_database=False`：只保留调试文件，不要求 PostgreSQL；
- `write_to_database=True`：复用正式数据库来源链，同时必须传正式 `provider_config_id`。

这里**没有生产预算/费用硬上限系统**。节省费用依靠：关键词去重、帖子 ID 去重、评论 ID 去重、跨运行状态、Provider 末页、目标评论数和显式页数边界。数据库模式也不会因为“还要入库”额外重复请求同一个 TikHub Operation。

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

数据库模式不会删除这些调试产物。正式 PostgreSQL Raw Artifact 是同一次 Provider 响应在生产来源链中的不可变证据，本地 `raw/*.json` 继续是人工调试副本；两者职责不同。

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

数据库模式的最终业务身份仍由 PostgreSQL Content Owner 的 `(platform, external_content_id)` 以及评论稳定身份约束收敛；`state.json` 只用于人工调试省请求，不能替代数据库唯一约束、Version/Metric 或来源历史。

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

完整 TikHub 原始响应仍以 `raw/*.json` 为人工调试 Provider 证据，Canonical JSONL 仍是统一业务数据，不把 Excel 当 Provider Raw、数据库回灌格式或第二事实源。数据库模式直接把同一次响应送入正式 Raw/Candidate/Ingestion，不从导出 Excel 或 Canonical JSONL 再做第二次回灌。

统一导出设计门禁见 [`docs/blueprint/13-统一数据Excel导出与调试复用.md`](../../../../../../docs/blueprint/13-统一数据Excel导出与调试复用.md)。

## 8. 不使用命令行参数

本工具没有 CLI。直接在 Python 代码、IDE、调试器或临时 Python 文件中调用 `run_*()` 函数即可。

返回值 `TikHubTestRunResult` 会告诉你本次运行目录、Excel、manifest、内容数、一级评论数、二级回复数和真实请求数。

## 9. Stage 8A 可选数据库写入（已实现）

Stage 8A 已实现显式 opt-in 的 PostgreSQL 模式，同时保持原有 file-only 默认行为：

```text
默认：write_to_database=False
→ 只使用 tikhub_test/.env 的调试配置
→ 保持 Raw / Canonical / Excel / state / run summary
→ 不装配 PostgreSQL Runtime

显式：write_to_database=True + provider_config_id=<正式 UUID>
→ 先校验 PostgreSQL 18 / Stage 8A Schema
→ 校验正式 provider_config_id 存在、已启用、provider=tikhub
→ 校验正式 Provider Config 的 base_url 和 Secret 与本次 .env 实际配置一致
→ 建立 manual Collection Run / keyword Scope / Job + Fencing
→ 为每一次实际 TikHub 调用建立正式 Provider Request / billable Attempt
→ Transport 只发送一次网络请求
→ 同一个响应先镜像到 tikhub_test 本地 Raw
→ 同一个响应再由正式 RawArtifactService 保存正式 Raw Artifact
→ Candidate-before-Mapper
→ 正式 TikHub Mapper / Canonical
→ 本地 Canonical / Excel 继续保留
→ 正式 fenced Content Ingestion
→ PostgreSQL Current / Version / Metric / 来源历史
```

数据库模式固定遵守：

- 假定开发者机器上已经有一个可访问的 PostgreSQL 18 开发实例，通常是已经启动的本地数据库容器；
- 只读取仓库正式 `AIMA_DB_*` / Secret 配置，不自动 `docker compose up/down`；
- 不自动创建/删除数据库容器；
- 不自动执行 Alembic Migration；Schema 不满足当前代码要求时直接失败；
- `provider_config_id` 必须显式提供，不能根据名称或 `.env` 静默猜正式配置；
- `.env` Base URL/API Key 必须和该正式 Provider Config/Secret 一致，避免来源审计错配；
- 不建立 `TikHubDatabaseWriter` 或 `tikhub_test` 私有 Repository，不直接写 Content SQL；
- 不从已导出的 JSONL/Excel 再走平行回灌路径；
- Canonical 之后复用现有正式 Collection Content Ingestion / Content Owner；
- 同一 Provider 网络调用只发送一次，数据库模式本身不会把付费请求翻倍；
- 如果本地 Raw 镜像失败，正式 Attempt/Raw 会先按生产链收敛，随后错误仍向人工调用方暴露，不把调试文件失败静默吞掉；
- 执行结束后 Run/Scope/Job 会按真实 Attempt 成败收敛为终态。

因此同一组人工 TikHub 参数可以按需要选择：

```text
仅文件调试
```

或：

```text
文件保留 + 正式 PostgreSQL 入库
```

两种模式都复用同一套正式 TikHub Client、Operation、分页、Mapper、Decision 和 Ingestion；本目录仍然只是人工调试/验证入口，不成为第二套生产采集器。
