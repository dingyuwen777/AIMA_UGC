# 五平台采集实现导航

本文是 `docs/collection/` 的入口。目标不是重复 Blueprint，而是让开发者快速回答：

```text
这个平台当前生产用哪个 TikHub Operation？
Search/Detail/Comments/Replies 各在哪里？
Mapper 文件在哪？
真实 Fixture 在哪？
当前 Capability 支持哪些排序/时间/增量能力？
想换 endpoint 或修字段时应该改哪些文件？
```

系统采集架构先看：

- [`../blueprint/02-采集系统与数据标准化.md`](../blueprint/02-采集系统与数据标准化.md)
- [`../blueprint/08-采集策略与平台能力.md`](../blueprint/08-采集策略与平台能力.md)

真实 JSON 路径：

- [`../appendix/TikHub五平台真实响应与字段映射.md`](../appendix/TikHub五平台真实响应与字段映射.md)

接口家族/备用：

- [`../appendix/TikHub多接口验证与备用策略.md`](../appendix/TikHub多接口验证与备用策略.md)
- [`../appendix/TikHub接口选型与真实验证台账.md`](../appendix/TikHub接口选型与真实验证台账.md)

---

## 1. 五平台当前代码入口

```text
backend/src/aima_ugc/adapters/providers/tikhub/
├─ capabilities.py
├─ runtime.py
├─ transport.py
├─ pricing.py
├─ pricing.toml
├─ operations/
│  ├─ xiaohongshu.py
│  ├─ douyin.py
│  ├─ weibo.py
│  ├─ bilibili.py
│  └─ kuaishou.py
└─ mappers/
   ├─ common.py
   ├─ xiaohongshu.py
   ├─ douyin.py
   ├─ weibo.py
   ├─ bilibili.py
   └─ kuaishou.py
```

生产 Collection 串联：

```text
backend/src/aima_ugc/bootstrap/collection_scope.py
```

Collection Domain：

```text
backend/src/aima_ugc/modules/collection/
```

真实 Fixture：

```text
tests/fixtures/providers/tikhub/
```

---

## 2. 当前生产主链

| 平台 | Search | Detail | Comments | Replies/Sub-comments |
| --- | --- | --- | --- | --- |
| 小红书 | App V2 `search_notes` | App V2 image/video detail | App V2 `get_note_comments` | App V2 `get_note_sub_comments` |
| 抖音 | Search V2 | App V3 one video | App V3 comments | App V3 replies |
| 微博 | Web Search | App detail | App comments | Web V2 sub comments |
| B站 | App search by type | App one video | App comments | App reply detail |
| 快手 | App video search V2 | App one video | App comments | App sub comments |

Endpoint 精确路径不要从这个摘要猜，打开目标平台 `operations/*.py` 或真实响应附录。

---

## 3. 当前评论增量资格

机器事实：

```text
backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
```

当前：

| 平台 | `supports_incremental_comment_sort` | 含义 |
| --- | --- | --- |
| 小红书 | `true` | 当前正式 latest 评论链有可靠增量边界 |
| 抖音 | `false` | 当前正式 Comments 未承诺可靠 newest-first 增量 |
| 微博 | `false` | 当前正式排序证据不足以声明安全增量 |
| B站 | `true` | 当前 latest 模式和分页证据支持已知评论边界停止 |
| 快手 | `false` | 当前评论时间/排序不满足统一安全增量条件 |

这不是“接口有没有 cursor”的判断。

增量语义：

```text
请求当前页
→ 当前页完整保存 Raw
→ 当前页所有新 Observation 先 Mapper/Ingest
→ 遇到稳定已知 Comment ID 边界
→ 才停止后续页
```

Capability=false 的平台走受控刷新，不套用同一逻辑。

---

## 4. 当前 Capability 关键差异

| 平台 | Native time filter | Search observes comment_count | Reply count | Sub-comments |
| --- | --- | --- | --- | --- |
| XHS | 是 | 是 | 是 | 是 |
| Douyin | 是 | 是 | 是 | 是 |
| Weibo | 是 | 是 | 是 | 是 |
| Bilibili | 否 | 否 | 是 | 是 |
| Kuaishou | 否 | 是 | 是 | 是 |

为什么需要这个表：

- B站当前不能在 UI 写“原生 7 天过滤”；
- B站 Search 没有真实证据就不能把 `comment_count` 当 0；
- 快手虽然支持回复数/二级评论，但不代表它支持安全最新评论增量。

精确排序/时间/内容类型枚举看 `capabilities.py` 和 Blueprint 08。

---

## 5. Provider Request/Attempt 和 Raw

五个平台统一执行规则：

```text
Provider Request
→ 逻辑请求

Provider Attempt
→ 一次真实发送

Raw Artifact
→ 该 Attempt 返回的不可变响应
```

一个 Attempt 最多一次 HTTP。

如果已有完整 Raw：

```text
replay
→ 不重复请求 Provider
```

网络结果未知时：

```text
dispatch_status=unknown
→ 不假设没有发出
→ 保留 potential_duplicate_charge 审计
```

生产代码：

```text
modules/collection/provider_dispatch.py
modules/collection/provider_recovery.py
```

---

## 6. Search 后为什么不一定全部抓 Detail/Comments

当前有统一 Decision Pipeline：

```text
Search Candidate
→ Rule Relevance
→ 已有 Content/Metric/Coverage
→ Decision
   ├─ fetch_detail?
   ├─ fetch_comments?
   └─ fetch_sub_comments?
→ durable content action/checkpoint
```

代码：

```text
backend/src/aima_ugc/modules/collection/decision.py
backend/src/aima_ugc/bootstrap/collection_scope.py
```

目的：

- 避免同一个帖子跨关键词重复 Detail；
- 评论数没变化且上次 Coverage 已完整时避免重复抓；
- 已为 Relevance 获取的 Detail 后续直接复用；
- Worker takeover 后从持久 Action/Raw 恢复，而不是重新付费。

---

## 7. 五个平台分别去哪看

- [`xiaohongshu.md`](xiaohongshu.md)
- [`douyin.md`](douyin.md)
- [`weibo.md`](weibo.md)
- [`bilibili.md`](bilibili.md)
- [`kuaishou.md`](kuaishou.md)

每篇应该包含：

```text
当前主 Operation
真实 Endpoint
Mapper
Fixture
Capability
分页/评论关键边界
备用 family 状态
常见修改路径
```

---

## 8. 改平台代码的固定顺序

### Endpoint 变化

```text
Operation Builder
→ Fixture/Real Probe
→ Operation Test
→ Pricing/Capability（按影响）
→ 平台文档
```

### JSON shape 变化

```text
真实 Sanitized Fixture
→ Extractor / Mapper Test
→ Mapper
→ Canonical Contract Test
→ 必要 PostgreSQL Vertical Slice
```

### 打开新 Capability

```text
真实接口证据
→ Operation 能表达
→ Fixture
→ Mapper/分页
→ Capability
→ Contract/API/Frontend（如果公开）
→ Tests
```

不能只改一个 Capability bool。

### 切换 App/Web/V1/V2/V3

先做：

```text
同输入 A/B
→ stable ID 集合
→ Pricing
→ pagination
→ shape
→ candidate status
```

再决定是否切生产主链。

---

## 9. 真实验证怎么做

普通 CI 不发 TikHub 真实付费请求。

真实 Probe 必须：

- 显式；
- 限定请求数/页数；
- 先确认 Pricing；
- 使用生产 Operation；
- 保存 Sanitized Fixture；
- Secret 不进日志/Fixture；
- 不默认写生产业务库。

Fixture 是回归证据，TikHub 文档示例不是“真实 Fixture”。

---

## 10. 调试一条平台采集

推荐：

```text
Collection Run
→ Scope
→ Provider Request
→ Attempt
→ Raw Artifact
→ Candidate
→ Mapper
→ Candidate Ingestion
→ Content / Comment
```

数据库 SQL：

[`../appendix/PostgreSQL查询与调试实战.md`](../appendix/PostgreSQL查询与调试实战.md)

如果 Response 字段问题：

```text
Raw Fixture
→ Operation extractor
→ Mapper
→ Canonical
```

如果 HTTP 200 但数据库没 Content：

```text
Candidate
→ Rule Relevance
→ Mapper Contract
→ Decision
→ Content Ingestion
```

---

## 11. 当前没有的统一采集能力

- 自动 API family fallback；
- 所有平台统一时间过滤；
- 所有平台统一 newest comment 增量；
- Provider 请求/金额 Budget Guard；
- 快手 Comprehensive Search 作为 Video Search 备用；
- B站 Search comment_count 观察；
- Provider 私有字段直接进入公共 API/数据库。
