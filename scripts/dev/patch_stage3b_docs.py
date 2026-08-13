"""一次性同步 Stage 3B 已确认架构到长期文档。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: 预期唯一旧文本，实际 {count} 处")
    target.write_text(text.replace(old, new), encoding="utf-8")


def replace_section(path: str, start: str, end: str, new_body: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"{path}: section marker 不唯一")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    target.write_text(before + new_body.rstrip() + "\n\n" + end + after, encoding="utf-8")


def main() -> int:
    replace_once(
        "AGENTS.md",
        "- TikHub → 不可变 Raw → 平台 Mapper → Canonical → Ingestion → PostgreSQL；",
        "- Provider Adapter（TikHub、官方 API、Apify、自建采集器、文件/历史导入等）→ 不可变 Raw → Mapper → Canonical → Ingestion Service → Owner Repository → PostgreSQL；",
    )
    replace_once(
        "AGENTS.md",
        "Provider\n→ Raw Artifact\n→ Mapper\n→ Canonical\n→ Ingestion\n→ Owner Repository",
        "Provider Adapter\n→ Raw Artifact\n→ Mapper\n→ Canonical\n→ Ingestion Service\n→ Owner Repository\n→ PostgreSQL\n\n数据库读取：\n\nPostgreSQL\n→ Query Repository / Read Model\n→ Query/Application Service\n→ Router / API",
    )
    replace_once(
        "AGENTS.md",
        "- TikHub Probe 调生产 Client/Operation；",
        "- Provider Probe 调对应生产 Adapter/Operation；TikHub 只是一个 Provider 实现；",
    )
    replace_once(
        "AGENTS.md",
        "真实 TikHub/模型 Probe 默认关闭，明确费用，不进普通 CI，不写生产库，不打印 Secret。",
        "真实付费 Provider/模型 Probe 默认关闭，明确费用，不进普通 CI，不写生产库，不打印 Secret。",
    )

    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "TikHub 改了分页字段\n→ 应主要影响 TikHub Operation 和 Fixture",
        "某个 Provider 改了分页字段\n→ 应主要影响对应 Provider Adapter / Operation 和 Fixture",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "TikHub、小红书、抖音等字段都不是系统的公共语言。系统自己的公共语言是版本化 Canonical Contract。\n\n```text\n第三方 JSON\n→ Provider/Mapper\n→ Canonical\n→ 业务服务\n→ PostgreSQL\n```",
        "TikHub、官方 API、Apify 等 Provider 以及小红书、抖音、微博、B站、快手的平台私有字段都不是系统公共语言。系统先定义版本化的理想 Canonical Contract，再让各 Provider/平台 Mapper 适配。\n\n```text\nProvider Adapter\n→ 不可变 Raw Evidence\n→ Mapper\n→ Canonical Content / Comment\n→ Ingestion Service\n→ Owner Repository\n→ PostgreSQL\n\nPostgreSQL\n→ Query Repository / Read Model\n→ Query/Application Service\n→ API / AI / Reporting\n```\n\nCanonical 之后不再关心数据来自 TikHub、官方 API、Apify、自建采集器还是文件导入；数据库读写也不反向污染 Mapper。",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "- TikHub 或其他数据 Provider；",
        "- TikHub、官方 API、Apify、自建采集器、文件/历史导入等数据 Provider Adapter；",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "    TikHub[TikHub]\n",
        "    Providers[Provider Adapters]\n",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "    Worker --> TikHub\n",
        "    Worker --> Providers\n",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "- 直接操作 TikHub 原始 JSON；",
        "- 直接操作任一 Provider 原始响应；",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "Scheduler 不直接调用 TikHub，不直接运行 AI，不直接写内容表。",
        "Scheduler 不直接调用任何数据 Provider，不直接运行 AI，不直接写内容表。",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "| `collection` | 采集计划、Run、Scope、Provider 调用、Raw、重试 | Canonical 内容和评论 |\n| `content` | 内容、评论、版本、指标历史、查询、人工复核 | 稳定业务数据 |",
        "| `collection` | 采集计划、Run、Scope、Provider Adapter 调用、Raw、Candidate、Mapper、重试 | Canonical 内容和评论 |\n| `content` | Ingestion、内容、评论、版本、指标历史、Owner Repository、Query Repository/Read Model、人工复核 | 稳定业务数据与内容聚合视图 |",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "│  │     ├─ providers/\n│  │     │  ├─ tikhub/\n│  │     │  └─ llm/",
        "│  │     ├─ providers/\n│  │     │  ├─ tikhub/\n│  │     │  ├─ official/\n│  │     │  ├─ apify/\n│  │     │  └─ imports/\n│  │     ├─ llm/",
    )

    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "TikHub 原始返回是什么？",
        "实际 Provider 原始返回/输入是什么？",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "### 3.5 Provider Request Attempt：一次真实 HTTP 调用\n\n每一次真实 TikHub HTTP 调用都生成独立 Attempt：",
        "### 3.5 Provider Request Attempt：一次真实 Provider 执行\n\n每一次真实 Provider 执行都生成独立 Attempt。HTTP/SDK Provider 的一次外部发送是一条 Attempt；文件/历史导入的一次受控读取同样以 Attempt 留下可追溯执行事实。HTTP 状态、外部 request ID 和计费字段只在该传输/Provider 明确提供时填写：",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "## 5. TikHub Adapter\n\n目标目录：",
        "## 5. Provider Adapter 与 TikHub 参考实现\n\n系统允许 TikHub、平台官方 API、Apify、自建采集器、文件/历史导入等同级 Provider Adapter。Provider 可以使用 HTTP、SDK 或文件读取，但都必须先形成可追溯 Raw Evidence/Candidate，再由 Mapper 产出同一 Canonical；任何 Provider 都不能直接写内容表。TikHub 只是当前规划中的第一个具体参考实现。\n\nTikHub 目标目录：",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "/data/AIMA_UGC/runtime/data/raw/\n  tikhub/\n    xhs/",
        "/data/AIMA_UGC/runtime/data/raw/\n  <provider>/\n    <platform>/",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "### 6.2 Raw Envelope\n\n```json",
        "### 6.2 Raw Envelope\n\nRaw Envelope 顶层语义 Provider 无关；下面只用 TikHub + 小红书展示一个具体实例，其他 Provider 不需要伪装成 TikHub 字段。\n\n```json",
    )

    canonical_section = """## 8. Canonical 数据契约

Canonical 是 AIMA 自己定义的理想业务语言，不由 TikHub 或任一平台当前响应反向决定。机器事实源固定在：

```text
backend/src/aima_ugc/contracts/canonical/
→ Pydantic 唯一手写事实源

contracts/canonical/*.schema.json
→ 由 Pydantic 确定性生成的 JSON Schema

contracts/canonical/examples/
→ 固定合法脱敏示例
```

写入使用原子 Observation：`CanonicalContentV1` 与 `CanonicalCommentV1`；读取、导出、AI 和页面使用以一条内容为根的 `CanonicalContentAggregateV1`。Mapper 只生成原子 Contract，不为凑出整帖树查询数据库。

### 8.1 内容与账号

内容身份固定为 `(platform, external_content_id)`，备用稳定 ID 放入 `alternate_ids`。内容可表达内容类型、标题、正文、稳定原文 URL、分享 URL、发布时间/来源更新时间、公开作者资料、媒体、话题、@提及、公开地点/IP 属地、状态和来源追溯。

帖子作者和评论者复用 `CanonicalAuthorV1`。已批准方案 B：在 Provider 明确公开提供时尽量保存主账号 ID、备用 ID、handle/账号名、显示昵称、主页 URL、头像 URL、简介、认证、公开地区及粉丝/关注/作品/累计获赞等统计；缺失或不可靠时为 `null`，禁止猜测。手机号、Cookie、Token、API Key、签名和其他认证 Secret 不进入 Canonical；生日、性别、学校、职业不属于 V1 核心字段。

### 8.2 互动指标

`CanonicalMetricsV1` 可表达：

```text
like_count
comment_count
share_count
repost_count
favorite_count
view_count
play_count
danmaku_count
coin_count
download_count
reply_count
```

平台没有该概念或本次响应未提供时为 `null`；明确观察到零才写 `0`。多次采集允许指标上升或下降，不能使用 `max()` 覆盖真实平台校正、取消点赞或评论删除。

### 8.3 评论关系

评论身份固定为 `(platform, external_content_id, external_comment_id)`：

- `external_comment_id`：评论自身 ID；
- `root_comment_id`：所属一级评论线程根；
- `parent_comment_id`：直接回复对象；
- 无法确认关系时保留 `null` 或进入聚合视图的 `unthreaded_comments`，禁止按数组位置猜父子关系。

评论还可表达评论者公开资料、正文、发布时间/来源更新时间、点赞/回复数、媒体、@提及、地点/IP 属地、是否内容作者本人、状态和来源。

### 8.4 稀疏 Observation

每个 `CanonicalContentV1` / `CanonicalCommentV1` 都必须带 `observed_fields`，只声明本次 Provider/Operation 真正观察到的可更新字段：

```text
字段出现在 observed_fields
→ Ingestion 可以按本次值更新

字段未出现
→ 保留数据库已有更完整值

字段明确观察为 null
→ 只有该字段/Operation 语义允许清空时才清空
```

因此搜索卡片、详情、评论接口和不同 Provider 可以共同刷新同一内容，而不会因为稀疏响应把历史详情、媒体或作者资料误删。

### 8.5 内容聚合与评论覆盖

`CanonicalContentAggregateV1` 是 Read Model/交换结构，不是数据库单行大 JSON。它以一条帖子/笔记/视频/微博为根，包含：

```text
content
comment_coverage
comment_threads[]
  ├─ root_comment
  ├─ replies[]
  └─ coverage
unthreaded_comments[]
system(first_seen_at / last_seen_at / latest_observed_at)
lineage[]
```

评论覆盖状态固定区分 `complete`、`partial`、`not_requested`、`unavailable`，并可记录平台报告总数、已采集数和观察时间。空评论数组不能被静默解释成“平台确实没有评论”。`lineage` 从 Candidate/Attempt/Raw 等来源事实组装，不创建第二套来源真相。

### 8.6 时间规则

- API/Canonical 使用 ISO-8601 且需要时刻的字段必须带时区；
- 数据库存 `timestamptz`；
- 无时区时间只有在 Provider 语义明确且已绑定平台时区时才能转换；
- 无法可靠解析时保存 `null` 和原始值到 Raw；
- 禁止把采集时间冒充发布时间；
- 从平台 ID 推算时间只能作为明确标记的低置信度候选，不覆盖来源明确的发布时间。
"""
    replace_section(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "## 8. Canonical 数据契约",
        "## 9. 摄取算法",
        canonical_section,
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "1. Raw 已成功落盘\n2. Mapper 输出 Canonical\n3. Pydantic + JSON Schema 校验\n4. 开启数据库事务",
        "1. Raw 已成功落盘并形成 Candidate\n2. 对应 Provider/平台 Mapper 输出原子 Canonical\n3. Pydantic + JSON Schema 校验，并保留 `observed_fields`/Source\n4. ContentIngestionService 开启数据库短事务",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "5. 按平台身份锁定或 Upsert 当前内容\n6. 业务字段变化时新增 content_version\n7. 指标变化或到达每日检查点时新增 metric_observation",
        "5. 按平台身份锁定或 Upsert 当前内容；只更新 `observed_fields` 明确观察到的字段，未观察字段保持原值\n6. 业务字段变化时新增 content_version\n7. 指标变化或到达每日检查点时新增 metric_observation；指标允许真实下降，禁止只取历史最大值",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "content_metric_observations\n→ 点赞、评论、分享、收藏、播放等时间序列",
        "content_metric_observations\n→ 点赞、评论、分享、转发、收藏、浏览/播放、弹幕、投币、下载等时间序列",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "comment_metric_observations\n→ 评论点赞等变化",
        "comment_metric_observations\n→ 评论点赞、回复数等变化\n\ncomment_coverage_observations\n→ 评论完整/部分/未请求/不可用及抓取数量历史",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "TikHubConfig + platform + operation + explicit parameters",
        "ProviderConfig + platform + operation + explicit parameters",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "Probe 必须调用生产 `client.py` 和 `operations/*.py`，不能复制 endpoint、参数和分页。",
        "Probe 必须调用对应 Provider Adapter 的生产 Client/Operation，不能复制 endpoint、参数、分页或文件解析逻辑。",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "- 只使用专用测试关键词和小预算；",
        "- 付费/外部 Provider 只使用专用测试关键词和小预算；",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "## 14. 平台能力门禁与 TikHub 入口参考",
        "## 14. 平台能力门禁与 TikHub Provider 入口参考",
    )
    replace_once(
        "docs/blueprint/02-采集系统与数据标准化.md",
        "截至 2026-08-13，设计时核验过且保留为候选的入口包括：",
        "TikHub 只是一个 Provider Adapter。官方 API、Apify、自建采集器和文件/历史导入可以并列增加，只要遵守相同 Raw → Mapper → Canonical 边界。以下仅是截至 2026-08-13 对 TikHub 设计时核验过且保留为候选的入口：",
    )

    replace_once(
        "docs/blueprint/03-数据库与文件存储.md",
        "contents\ncontent_versions\ncontent_metric_observations\ncontent_discoveries\ncomments\ncomment_versions\ncomment_metric_observations",
        "accounts\naccount_external_ids\ncontents\ncontent_versions\ncontent_metric_observations\ncontent_media\ncontent_topics\ncontent_mentions\ncontent_locations\ncontent_discoveries\ncomments\ncomment_versions\ncomment_metric_observations\ncomment_media\ncomment_mentions\ncomment_locations\ncomment_coverage_observations",
    )

    persistence_section = """### 5.11 `accounts` 与公开作者资料

`accounts` 保存外部内容平台上的公开账号当前值，**不是系统登录用户、Principal 或认证账号表**。只有稳定 `external_account_id` 明确可得时才建立账号身份；只有昵称而没有稳定 ID 时，不按昵称制造账号身份，实际观察到的作者快照仍由 Content/Comment Version 保存。

```text
id                    uuid primary key
platform              text not null
external_account_id   text not null
handle                text
display_name          text
profile_url           text
avatar_url            text
bio                    text
verified               boolean
verification_label    text
region                 text
current_follower_count bigint
current_following_count bigint
current_content_count bigint
current_total_like_count bigint
first_seen_at          timestamptz not null
last_seen_at           timestamptz not null
updated_at             timestamptz not null

unique(platform, external_account_id)
```

`account_external_ids` 关系化保存 `red_id`、`sec_uid`、`bvid/aid` 类备用稳定账号标识；Provider 私有临时 Token、签名和认证字段不得进入该表。账号字段同样遵守 Canonical `observed_fields` 稀疏合并：本次没观察到的简介/头像/统计不能清空旧值。是否对粉丝数等账号统计建立独立长期 Observation，在实际账号趋势需求进入范围时另行冻结，不在 Stage 3B 偷加历史策略。

### 5.12 `contents` 与 `content_versions`

`contents` 一帖/笔记/视频/微博一行，保存当前可查询值：

```text
id                      uuid primary key
platform                text not null
external_content_id     text not null
content_type            text not null
title                   text not null default ''
text                    text not null default ''
canonical_url           text
share_url               text
author_account_id       uuid references accounts
published_at            timestamptz
source_updated_at       timestamptz
status                  text not null default 'active'
first_seen_at           timestamptz not null
last_seen_at            timestamptz not null
current_version         integer not null
current_like_count      bigint
current_comment_count   bigint
current_share_count     bigint
current_repost_count    bigint
current_favorite_count  bigint
current_view_count      bigint
current_play_count      bigint
current_danmaku_count   bigint
current_coin_count      bigint
current_download_count  bigint
updated_at              timestamptz not null

unique(platform, external_content_id)
```

`content_versions` 只记录业务状态变化，保留标题、正文、内容类型、URL、作者公开快照、发布时间/来源更新时间、状态和本次来源；作者快照使用版本化 `jsonb` 保存当时 `CanonicalAuthorV1` 的完整公开观察，避免账号后来改名后丢失历史上下文。Business Hash 仍只和当前版本比较，允许 `A → B → A` 产生新版本。

### 5.13 内容指标 Observation

`content_metric_observations` 与 `contents.current_*` 使用同一稳定指标语义：

```text
like_count
comment_count
share_count
repost_count
favorite_count
view_count
play_count
danmaku_count
coin_count
download_count
```

各值可空：`null` 表示未知/本次未提供，`0` 表示明确观察到零。新 Observation 可以比旧值小，禁止把指标写成单调递增或只保留最大值。继续使用 `initial`、`changed`、`daily_checkpoint`、来源 Attempt/Raw、`observation_key` 和 `Asia/Shanghai` 每日部分唯一约束保证历史与幂等。

### 5.14 内容子实体与来源

图片/视频/Live Photo/音频、话题、@提及和公开位置/IP 属地不能塞进一个不可查询的大帖子 JSON。目标关系按内容 Owner 管理：

```text
content_media
content_topics
content_mentions
content_locations
```

列表顺序需要展示语义时保存稳定 `position`。Provider 编码流、CDN 实验字段、临时签名等只留 Raw，不为了“字段多”污染业务表。

`content_discoveries` 继续保存来源聚合；逐次权威来源仍是 `collection_candidates → collection_candidate_ingestions → provider_request_attempts → Raw Artifact`，`CanonicalContentAggregateV1.lineage` 从这些事实组装，不另建第二套 lineage 真相表。

### 5.15 `comments`、评论历史与覆盖

`comments` 一评论/回复一行：

```text
id                    uuid primary key
content_id            uuid not null references contents
external_comment_id   text not null
root_comment_id       text
parent_comment_id     text
author_account_id     uuid references accounts
text                  text not null
published_at          timestamptz
source_updated_at     timestamptz
status                text not null default 'active'
is_by_content_author  boolean
first_seen_at         timestamptz not null
last_seen_at          timestamptz not null
current_like_count    bigint
current_reply_count   bigint
current_version       integer not null
updated_at            timestamptz not null

unique(content_id, external_comment_id)
```

评论平台由 Content 推导；`external_comment_id` 是自身身份，`root_comment_id` 表示一级线程根，`parent_comment_id` 表示直接回复对象。父/根评论可能被删除或尚未抓到，因此不凭数组层级猜关系，也不要求所有外部关系立刻能建数据库外键。

`comment_versions` 保存评论文本、root/parent 关系、作者公开快照、状态等业务变化；`comment_metric_observations` 保存 `like_count/reply_count` 的初始、变化和每日检查点。`comment_media/comment_mentions/comment_locations` 保存可查询子实体。

`comment_coverage_observations` 保存一次评论采集对某个内容或线程的覆盖事实：`complete/partial/not_requested/unavailable`、平台报告总数、已采集数、观察时间和来源。这样 Read Model 能区分“没有评论”和“没有抓评论”。

### 5.15A Ingestion、稀疏更新和读取中间层

Mapper 不能写数据库。写入固定经过：

```text
CanonicalContentV1 / CanonicalCommentV1
→ ContentIngestionService
→ Content Owner Repository
→ PostgreSQL
```

Ingestion 依据 `observed_fields` 合并：只更新本次明确观察字段；未观察字段保留数据库已有值；明确 `null` 只有在字段/Operation 语义允许时才清空。Candidate Ingestion 账本应保留 Canonical 版本、身份和本次 `observed_fields`，便于审计稀疏合并。

数据库读取固定经过：

```text
PostgreSQL
→ Query Repository / Read Model
→ Query/Application Service
→ API / AI / Reporting
```

`CanonicalContentAggregateV1` 在读取时按 `contents/accounts/media/topics/mentions/locations/comments/coverage` 和来源账本组装，包含一级评论线程、回复、无法可靠归线程的评论、`system` 和 `lineage`；**数据库不把整棵帖子+评论树作为单行巨大 JSON 保存**。

Stage 3B 只冻结上述持久化语义和边界，不创建这些业务表的 Alembic Revision。实际 DDL、索引、Deferred Trigger 和 Repository 在进入对应 Ingestion/单平台纵切的 L3 Change 时再次对照已冻结 Canonical 后实施和验证。

### 5.15B `content_discoveries`

同一内容可能被多个关键词、话题或账号发现，不能只保存一个 `source_keyword`。它是查询便利聚合，不能替代逐项 Candidate/Ingestion 来源账本。
"""
    replace_section(
        "docs/blueprint/03-数据库与文件存储.md",
        "### 5.11 `contents`",
        "### 5.16 `jobs`",
        persistence_section,
    )

    replace_once(
        "docs/blueprint/04-后端任务API与前端.md",
        "每层只做自己负责的事情。Router 不承载复杂业务；页面不理解数据库表；Repository 不解释 TikHub 字段。",
        "每层只做自己负责的事情。Router 不承载复杂业务；页面不理解数据库表；Repository 不解释任何 Provider 私有字段。内容读取走 Query Repository/Read Model，内容写入走 Ingestion + Owner Repository，二者不让 API 或 Mapper 直接碰 SQL。",
    )
    replace_once(
        "docs/blueprint/04-后端任务API与前端.md",
        "- TikHub 请求；",
        "- 直接 Provider 请求；",
    )
    replace_once(
        "docs/blueprint/04-后端任务API与前端.md",
        "### 2.3 Repository\n\nRepository 只负责本模块表的读写：",
        "### 2.3 Repository\n\nOwner Repository 负责本模块业务写入，Query Repository 负责只读查询和 Read Model 组装。二者共享数据库运行时但不合并成万能 Repository：",
    )
    replace_once(
        "docs/blueprint/04-后端任务API与前端.md",
        "- 不做 TikHub 字段翻译；",
        "- 不做 TikHub、官方 API、Apify 等 Provider 字段翻译；",
    )
    replace_once(
        "docs/blueprint/04-后端任务API与前端.md",
        "### 3.2 Canonical\n\n```text\nPydantic Canonical Model\n→ 生成 JSON Schema\n→ 固定 examples\n→ Mapper / Ingestion / Contract Test\n```\n\nCanonical 不再同时手写两份可能漂移的 Python 类和 JSON Schema。Pydantic 模型是唯一手写事实源，JSON Schema 和示例验证由脚本生成/校验。",
        "### 3.2 Canonical\n\n```text\nPydantic Canonical Model\n→ 生成 JSON Schema\n→ 固定 examples\n→ Mapper / Ingestion / Query / Contract Test\n```\n\nPydantic 模型是唯一手写事实源，JSON Schema 由 `scripts/contracts/generate.py` 确定性生成到 `contracts/canonical/`。写入原子 Contract 是 `CanonicalContentV1` / `CanonicalCommentV1`；查询、导出、AI 和页面的完整帖子视图使用 `CanonicalContentAggregateV1`。Aggregate 是 Read Model，不要求 Mapper 一次生成，也不作为数据库大 JSON 持久化。`observed_fields` 控制稀疏更新，`comment_coverage` 明确评论采集完整度。",
    )

    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "生产 TikHub 分页实现一份\n调试脚本再复制一份",
        "生产 Provider 分页/解析实现一份\n调试脚本再复制一份",
    )
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "E2E 使用固定 Fake Provider，不调用付费 TikHub。",
        "E2E 使用固定 Fake Provider，不调用任何真实付费 Provider。",
    )
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "### 阶段 5：TikHub Client 和 Raw\n\n→ 修改范围：Client、错误、费用、Artifact Envelope、Fake HTTP  \n→ 预期结果：外部请求可脱敏落盘并回放  \n→ 验证：超时、429、5xx、Raw 原子写、SHA-256",
        "### 阶段 5：Provider Adapter 和 Raw\n\n→ 修改范围：Provider Client/Adapter、错误、费用、Artifact Envelope、Fake Transport；TikHub 可以作为首个具体实现，但不得成为公共接口  \n→ 预期结果：HTTP/SDK/文件等 Provider 输入均可按同一 Raw/Attempt 边界脱敏留证并回放  \n→ 验证：首个外部 Provider 的超时/限流/5xx（适用时）、Raw 原子写、SHA-256、Provider 私有字段不泄漏 Canonical；文件 Provider 验证幂等读取与来源追溯",
    )
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "- TikHub Provider → Raw Artifact → Mapper → Canonical → Ingestion → PostgreSQL；",
        "- Provider Adapter（TikHub/官方 API/Apify/自建采集器/文件导入等）→ Raw Artifact → Mapper → Canonical → Ingestion Service → Owner Repository → PostgreSQL；",
    )

    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "> 蓝图版本：1.8  ",
        "> 蓝图版本：1.9  ",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "| 常规/发布备份 | 维护 epoch + 统一共享/独占 PostgreSQL advisory 写屏障排空在途写入，再创建统一截止点的数据库+Artifact Backup Set；独立文件增量不算恢复点 |",
        "| 常规/发布备份 | 维护 epoch + 统一共享/独占 PostgreSQL advisory 写屏障排空在途写入，再创建统一截止点的数据库+Artifact Backup Set；独立文件增量不算恢复点 |\n| Provider / Canonical | AIMA 先定义理想 Provider/平台无关 Canonical；TikHub、官方 API、Apify、自建采集器和文件导入均在 Canonical 之前各自适配，Raw 保留原始证据 |\n| Canonical 作者/评论者 | 采用已批准方案 B：尽量保存平台明确公开的账号 ID/备用 ID、handle/昵称、主页/头像、简介、认证、地区和公开统计；敏感认证信息及生日/性别/学校/职业不进入 V1 核心 |\n| 数据库中间层 | 写入固定 Canonical → Ingestion Service → Owner Repository；读取固定 PostgreSQL → Query Repository/Read Model → Query Service；Aggregate 不作为数据库大 JSON 持久化 |",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "4. 个人信息、Raw、导出和审计的访问、保留、删除与合规规则；",
        "4. Canonical V1 的公开作者/评论者字段范围已批准；个人信息、Raw、导出和审计的访问控制、保留、删除与合规规则仍待批准；",
    )

    replace_once(
        "README.md",
        "TikHub / 其他 Provider\n→ 不可变 Raw Artifact\n→ 平台 Mapper\n→ Canonical Contract\n→ Ingestion\n→ PostgreSQL\n→ API / Analysis / Monitoring / Reporting",
        "TikHub / 官方 API / Apify / 自建采集器 / 文件导入 / 其他 Provider\n→ 不可变 Raw Artifact\n→ 对应 Mapper\n→ Canonical Contract\n→ Ingestion Service\n→ Owner Repository\n→ PostgreSQL\n→ Query Repository / Read Model\n→ API / Analysis / Monitoring / Reporting",
    )

    replace_once(
        "docs/blueprint/README.md",
        "| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | Plan/Run/Scope/Request/Attempt/Candidate、TikHub Adapter、Raw、Mapper、Canonical、分页、刷新策略 | Provider、TikHub、采集、Raw、Mapper、Canonical、平台数据映射 |",
        "| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | Plan/Run/Scope/Request/Attempt/Candidate、Provider Adapter、Raw、Mapper、Canonical、分页、刷新策略 | Provider、TikHub/官方 API/Apify/导入、采集、Raw、Mapper、Canonical、平台数据映射 |",
    )

    print("Stage 3B 架构文档迁移完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
