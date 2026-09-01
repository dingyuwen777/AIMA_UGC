# Content 模块

Content 是 AIMA_UGC 的**核心业务事实 Owner**。它负责把来自 TikHub、Excel 等不同来源的 Canonical Observation 收敛为同一套账号、内容、评论 Current，并保存正文历史、指标历史、评论覆盖和查询 Read Model。

如果你要理解“同一个帖子为什么不会重复插入”“旧 Search 为什么不会把 Detail 的正文清空”“点赞下降为什么也要记录”“声音广场的数据从哪里来”，就从这个模块开始。

系统数据链：

```text
Provider / Excel
→ Mapper
→ Canonical
→ ContentIngestionService
→ Content PostgreSQL Owner
→ Current / Version / Metric / Coverage
→ Query Repository
→ API / Analysis / Export
```

相关：

- [`../../../../../docs/blueprint/03_数据库与文件存储.md`](../../../../../docs/blueprint/03_数据库与文件存储.md)
- [`../../../../../docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`../../../../../docs/01_代码结构与修改导航.md`](../../../../../docs/01_代码结构与修改导航.md)

---

## 1. 当前代码地图

```text
backend/src/aima_ugc/modules/content/
├─ ingestion.py
├─ query.py
├─ content_cursor.py
├─ http.py
├─ tables.py
├─ extended_tables.py
├─ account_tables.py
└─ source_constraints.py
```

### [`ingestion.py`](ingestion.py)

领域摄取入口：

```text
ContentIngestionService
ContentIngestionRepository Protocol
```

同时提供轻量 `InMemoryContentRepository`，用于无数据库情况下验证一部分 freshness/Version/Metric 领域语义。

### `tables.py`

核心 Current/History：

```text
accounts
contents
content_versions
content_metric_observations
comments
comment_versions
comment_metric_observations
comment_coverage_observations
```

### [`extended_tables.py`](extended_tables.py)

内容/评论扩展实体和关系，例如：

```text
external ids
media
topics
mentions
locations
thread coverage
```

精确结构直接看当前文件和 Migration。

### `query.py`

定义 Provider-neutral Content Read Model，不写 SQL。

### [`content_cursor.py`](content_cursor.py)

声音广场 Content 列表 Cursor 编解码和 query-hash 绑定。

### `http.py`

Content HTTP Port / 应用异常，不直接 SQL。

---

## 2. 真正 PostgreSQL 写入在哪里

Domain Service 不自己写 SQL。

PostgreSQL 实现位于：

```text
backend/src/aima_ugc/adapters/persistence/postgres/
```

Collection 调 Content Owner 的边界：

- [`collection_content.py`](../../adapters/persistence/postgres/collection_content.py)

Content 查询：

- [`content_queries.py`](../../adapters/persistence/postgres/content_queries.py)

生产装配：

- [`backend/src/aima_ugc/bootstrap/collection_scope.py`](../../bootstrap/collection_scope.py)
- [`backend/src/aima_ugc/bootstrap/manual_ingestion.py`](../../bootstrap/manual_ingestion.py)
- [`backend/src/aima_ugc/bootstrap/content_http.py`](../../bootstrap/content_http.py)

如果看到 Provider/Router 直接 `INSERT INTO contents`，就违反了当前 Owner 边界。

---

## 3. Content 身份怎样定义

```text
(platform, external_content_id)
```

数据库有对应 UNIQUE 约束。

例如：

```text
Excel 导入
platform=xiaohongshu
external_content_id=note_123

TikHub 后续又采到
platform=xiaohongshu
external_content_id=note_123
```

最终是**同一条 Content Current**，不会因为来源不同创建两条业务内容。

不要用：

- 标题；
- URL；
- 作者名；

作为最终 Content 身份。

---

## 4. Comment 身份怎样定义

评论是在具体 Content 内收敛：

```text
(content_id, external_comment_id)
```

根评论/父评论是关系事实：

```text
root_comment_id
parent_comment_id
```

没有 Provider 明确父关系时保留 `parent_comment_id = null`，不靠文本/用户名/数组位置猜。

---

## 5. 为什么同时有 Current、Version、Metric

### Current

用于页面和普通查询：

```text
contents
comments
```

例如：

```text
当前标题
当前正文
当前点赞
当前评论数
最后一次观察时间
```

### Version

记录稳定业务字段变化：

```text
content_versions
comment_versions
```

例如正文：

```text
A
→ B
→ A
```

当前规则允许形成三个业务版本；Version 和“以前是否出现过相同正文”不是一回事。

### Metric Observation

互动指标频繁变化，不应每次点赞 +1 就创建正文 Version：

```text
content_metric_observations
comment_metric_observations
```

当前原因包括：

```text
initial
changed
daily_checkpoint
```

因此：

```text
正文改变
→ Version

点赞/评论/播放改变
→ Metric Observation
```

---

## 6. 指标为什么允许下降

真实平台可能出现：

- 用户取消点赞；
- 评论被删除；
- 平台修正播放量；
- Provider 返回更正值。

所以当前不能：

```python
current_like_count = max(old, new)
```

只要 Provider 本次**明确观察**到新的合法值，即使从 100 降到 98，也应该记录真实变化。

---

## 7. `observed_fields` 是什么

不同 Observation 字段密度不同。

例如：

```text
10:00 Detail
→ text="完整正文"
→ observed_fields 包含 text

12:00 Search 卡片
→ Provider 没返回正文
→ observed_fields 不包含 text
```

12:00 这条 Observation 不能把数据库正文清空。

Canonical 会显式携带：

```text
observed_fields
```

含义：

```text
字段在 observed_fields
→ 本次明确观察到，可参与更新

字段不在 observed_fields
→ 本次未知，不覆盖旧值
```

---

## 8. `field_observed_at` 为什么存在

Current 表保存：

```text
field_observed_at JSONB
```

用于字段级 freshness。

例子：

```text
10:00 Search 观察 title
11:00 Detail 观察 title + text
10:30 一个延迟 Observation 才到达
```

10:30 的旧值不能回滚 11:00 已经明确观察过的字段。

但如果 10:30 观察了一个数据库以前从没见过的字段，这个字段仍可以被补入。

所以当前不是简单：

```text
整条记录 last-write-wins
```

而是：

```text
字段级 observation freshness
```

核心规则落在 Content Owner Repository；领域 Fake 也覆盖基本行为。

---

## 9. Source Lineage 怎样进入 Content Version

`content_versions` / `comment_versions` 会保存：

```text
provider_attempt_id
raw_artifact_id
observed_at
```

因此一条业务 Version 可以反查：

```text
Content Version
→ Provider Attempt
→ Provider Request
→ Collection Scope/Run
或
→ Import Batch

同时
→ Raw/Input Artifact
```

这也是为什么 Content 去重后不能删除来源证据。

SQL：

[`../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md`](../../../../../docs/appendix/01_PostgreSQL查询与调试实战.md)

---

## 10. Comment Coverage 为什么归 Content Owner

评论是否完整是内容当前业务事实的一部分，不是 Provider 临时 cursor。

当前保存：

```text
coverage
reported_total
collected_count
sample_mode
sort_mode
target_count
stop_reason
observed_at
```

用途：

- 告诉页面/报告评论是否只是 partial；
- 给 Collection Decision 判断后续是否值得继续抓；
- 不把“程序停止了”误写成“所有评论抓完了”。

精确表：

```text
comment_coverage_observations
comment_thread_coverage_observations
```

---

## 11. 声音广场的 Query 并不是只查 `contents`

生产查询：

- [`backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`](../../adapters/persistence/postgres/content_queries.py)

它会组合：

```text
Content Current
+ Current Version author snapshot/source
+ Current Analysis Identity 对应 Analysis
+ Label Pairs
+ Provider/Raw/Run/Batch Source
```

列表 Application Service：

- [`backend/src/aima_ugc/bootstrap/content_http.py`](../../bootstrap/content_http.py)

### 当前 Analysis 状态

```text
completed
→ 当前 Content Version 有当前 Prompt/Taxonomy/Model Identity 的 Analysis

stale
→ 当前版本没有当前 Analysis，但历史有 Analysis

pending
→ 从未分析
```

### 默认 irrelevant 过滤

列表未显式指定 `relevance` 时：

```text
current Analysis = irrelevant
→ 默认排除

没有当前 Analysis
→ 仍显示
```

单条详情可以审计 irrelevant Content。

AI relevance 不存 `contents.is_relevant`。

---

## 12. 当前 Content HTTP

```text
GET /api/v1/contents
GET /api/v1/contents/{content_id}
POST /api/v1/content-analysis-requests
GET /api/v1/content-analysis-jobs/{job_id}
```

Content 列表/详情是这个模块的 Read Model；Analysis 写入仍归 Analysis Owner。

精确 HTTP Contract：

- [`backend/src/aima_ugc/contracts/http.py`](../../contracts/http.py)

---

## 13. Content Cursor 为什么绑定查询条件

当前列表 Cursor 不是裸数据库 ID。

代码：

- [`content_cursor.py`](content_cursor.py)
- [`bootstrap/content_http.py`](../../bootstrap/content_http.py)

Application Service 会对：

```text
ContentFilterSnapshot
```

计算 query hash，并在 Cursor 中绑定。

因此：

```text
平台=xiaohongshu 的 cursor
```

不能拿去继续：

```text
平台=weibo
```

的查询。

前端只原样保存/回传 `next_cursor`。

---

## 14. 修改不同问题应该改哪里

### 改 Content 身份

高风险：

```text
Canonical stable identity
→ tables.py UNIQUE
→ PostgreSQL Owner Repository
→ Migration / 数据迁移
→ 所有入口/查询/测试
```

不能只改一个 Dedup 函数。

### 改 Current/Version 规则

```text
modules/content/ingestion.py
→ PostgreSQL Content Repository
→ tables.py / Migration（如果结构变化）
→ unit + integration
```

### 新增一个稳定 Content 字段

```text
Canonical Contract
→ Provider/File Mapper
→ contents/current + content_versions（按语义）
→ Migration
→ Owner Repository
→ Query/API/Export/Frontend（按需要）
```

### 只新增 Provider 私有字段

先判断是否真是跨来源长期业务事实。不是的话，不应为了保存“所有 Raw 字段”扩大 Content Schema；Raw Artifact 已保留原始证据。

### 改声音广场筛选

```text
ContentFilterSnapshot / ContentListQuery
→ modules/content/query.py
→ content_queries.py
→ Cursor query hash
→ API Test
→ OpenAPI / generated Client
→ voice-plaza Feature
```

---

## 15. 常见故障

### 同一帖子重复两条

检查：

```text
platform
external_content_id
Mapper stable ID
contents UNIQUE
Repository upsert
```

不要先增加标题/URL fuzzy dedup。

### 新正文被旧 Search 清空

检查：

```text
Canonical observed_fields
field_observed_at
Mapper 是否错误声明 text 已观察
```

### 点赞没产生历史

检查：

```text
metrics.like_count 是否在 observed_fields
当前值/新值
Metric Observation reason
```

### 声音广场看不到已入库内容

按顺序：

```text
contents
→ 查询 filter
→ 当前 Analysis Identity
→ current irrelevant 默认过滤
→ Cursor
→ API
→ Frontend
```

---

## 16. 测试重点

- Content/Comment stable identity；
- Current First/Last Seen；
- `observed_fields`；
- field freshness；
- A→B→A Version；
- 指标变化/下降；
- daily checkpoint；
- Source Attempt/Raw；
- Coverage；
- Query current Analysis；
- stale/pending/completed；
- default irrelevant filtering；
- Cursor query binding；
- PostgreSQL UNIQUE/并发。

最终 PostgreSQL 行为必须由 Integration Test 验证，不能只依赖 InMemory Fake。

---

## 17. Historical Fill-Only 不是普通新鲜度写入

统一数据导入仍由 Content Owner 写 `contents/accounts/content_versions`。每个 Campaign 独立冻结写入策略：`standard_observation` 复用既有观测语义；`historical_fill_only` 只补 Current 空字段，非空同值不写，非空异值不覆盖并输出冲突，空历史值不清空 Current。后者的 `unchanged/conflict` 不推进字段新鲜度或 `last_seen_at`；没有可信历史观测时间的 Metric 不更新 Current，也不创建伪造 Observation。来源是本地还是服务器不会静默改变该策略。

生产入口：

- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py`](../../adapters/persistence/postgres/historical_content.py)：PostgresHistoricalContentRepository.ingest_rows()


该入口每次最多处理一个有界 Chunk，并在同一事务提交业务变化、逐行 outcome 和冲突。普通 Excel/TikHub 继续使用既有字段新鲜度规则，不受历史策略影响。
