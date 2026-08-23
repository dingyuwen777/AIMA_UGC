# TikHub 多接口验证与备用策略

同一个平台在 TikHub 里可能同时存在 App、Web、V1、V2、V3。**接口名相似，不代表业务语义、内容集合、排序、分页、字段结构或价格相同。**

本文说明：

- 当前生产主链和候选接口如何区分；
- 怎样做可复现 A/B；
- `verified_backup` 到底代表什么；
- 为什么当前不做自动 fallback；
- 要把备用切成主链时需要改哪些代码、Fixture、Pricing 和测试。

真实响应字段见：

[`03_TikHub五平台真实响应与字段映射.md`](03_TikHub五平台真实响应与字段映射.md)

真实验证台账见：

[`05_TikHub接口选型与真实验证台账.md`](05_TikHub接口选型与真实验证台账.md)

---

## 1. 当前代码把“主链”和“候选”怎样分开

主 Operation / Candidate Builder 都位于：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/
```

当前代码使用清晰命名防止候选被 Runtime 误用，例如：

```text
build_video_search_request(...)
→ 正式主 Operation

build_video_search_v1_candidate_request(...)
→ 只用于显式 A/B Candidate
```

当前生产能力登记：

```text
backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
```

当前运行装配：

```text
backend/src/aima_ugc/adapters/providers/tikhub/runtime.py
```

集合比较工具：

```text
backend/src/aima_ugc/adapters/providers/tikhub/api_family_compare.py
```

备用 builder：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/backup.py
以及各平台 operations/*.py 中显式 candidate/web builder
```

关键原则：

> Candidate Builder 存在 ≠ Capability 已启用 ≠ Runtime 会自动 fallback。

---

## 2. 为什么当前不做自动 fallback

表面上看：

```text
App 失败
→ 自动请求 Web
```

似乎更“稳定”，但这里有几个实际风险。

### 2.1 可能不是同一个业务语义

例如快手：

```text
search_video_v2
vs
search_comprehensive
```

后者语义更宽，可能混入非视频对象。自动切换后即使 HTTP 200，也可能悄悄改变采集口径。

### 2.2 Pagination 不一定能直接续

App 的：

```text
cursor / pcursor / search_id
```

不能假设可以直接交给 Web family 继续下一页。

### 2.3 字段密度可能不同

备用接口可能不返回：

- comment_count；
- reply_count；
- 某类作者信息；
- 当前主链依赖的分页元数据。

如果不显式验证，会出现“HTTP 成功但业务事实悄悄变少”。

### 2.4 费用可能差很多

同一业务动作在不同 endpoint 上价格可能不同。快手历史 Probe 就出现 Web 二级评论明显高于 App 的情况。

因此当前原则是：

```text
主接口失败
→ 按主接口自己的失败/Retry 语义处理
→ 不自动跨 family
```

要切换 family，必须形成可审计变更。

---

## 3. 候选接口的三个状态

| 状态 | 含义 | 当前能否被 Runtime 自动调用 |
| --- | --- | --- |
| `verified_backup` | 使用同业务输入做过受限真实 A/B，稳定 ID/结构可以归一化，价格已核验 | **不能** |
| `candidate_pending_probe` | 当前代码能构造候选，但还没有足够真实 A/B 证据 | 不能 |
| `not_equivalent` | 当前没有同语义候选，或者候选明显是不同业务口径 | 不能 |

`verified_backup` 的意思只是：

> 如果以后要人工切换/正式变更，我们已经有一组真实兼容证据。

它不是：

> 生产代码可以在异常时偷偷切过去。

---

## 4. A/B 验证必须比较什么

搜索类使用：

```text
同一个 keyword
尽可能相同的排序
尽可能相同的发布时间过滤
尽可能相同的内容类型
尽可能接近的执行时间
```

内容/评论类使用：

```text
同一个 content_id
同一个 root_comment_id（回复场景）
```

至少记录：

```text
platform
business_operation
input identity
executed_at
primary_endpoint
candidate_endpoint
primary_filters
candidate_filters
primary_endpoint_price
candidate_endpoint_price
primary_count
candidate_count
primary_unique_count
candidate_unique_count
primary_duplicate_count
candidate_duplicate_count
shared_count
primary_only_count
candidate_only_count
union_count
jaccard
same_unique_content
pagination_semantics
ordering_semantics
shape_compatibility
verification_status
```

### 为什么按稳定 ID，不按标题比较

内容集合比较的主键必须是稳定外部 ID：

```text
Content → external_content_id
Comment → external_comment_id
```

标题、作者名、URL 都可能变化或格式化不同，不适合作为 A/B 集合身份。

### Jaccard

```text
shared / union
```

两边都是空集合时：

```text
union = 0
→ jaccard = null / inconclusive
```

不能写成 1.0，因为“两个接口都没返回任何东西”不等于“证明两者完全等价”。

---

## 5. 单页一样，为什么仍不能宣布接口完全等价

一次 A/B 通常只验证一页。

例如：

```text
Primary page 1 IDs = A,B,C
Candidate page 1 IDs = A,B,C
```

只能说明：

> 在这个关键词、这个时间、这个第一页窗口下，两者集合一致。

不能证明：

- 第二页以后也一致；
- 排序永久一致；
- 全量结果一致；
- 过滤语义完全一致；
- 未来 Provider 实现不会漂移。

如果要验证“全量等价”，需要两边分别分页到终止，并记录：

- 请求数；
- 总费用；
- 最终稳定 ID 集合；
- 分页终止语义；
- 排序差异。

---

# 6. 当前平台矩阵

## 6.1 快手

### 正式主链

当前 `operations/kuaishou.py`：

```text
Search
GET /api/v1/kuaishou/app/search_video_v2

Detail
GET /api/v1/kuaishou/app/fetch_one_video

Comments
GET /api/v1/kuaishou/app/fetch_video_comment

SubComments
GET /api/v1/kuaishou/app/fetch_video_sub_comments
```

### 已验证 Web 备用

```text
GET /api/v1/kuaishou/web/fetch_one_video_comment
GET /api/v1/kuaishou/web/fetch_one_video_sub_comment

status = verified_backup
```

同一真实作品、同一确实有回复的根评论 A/B：

```text
App 一级 → 200 / 非空
Web 一级 → 200 / 非空
App 二级 → 200 / 非空
Web 二级 → 200 / 非空
```

历史 2026-08-16 endpoint-info 快照：

```text
App 一级 0.001 USD
App 二级 0.001 USD
Web 一级 0.002 USD
Web 二级 0.010 USD
```

这些数字只属于当时 Probe 证据。当前生产价格必须看：

```text
backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml
```

当前正式 builder：

```python
build_video_comments_request(...)
→ 委托 App builder

build_video_sub_comments_request(...)
→ 委托 App builder
```

所以 Web 备用不会被异常路径自动调用。

### 搜索为什么没有 App/Web A/B

当前快手 Web family 没有和关键词视频 Search V2 同语义的 Web Search。

因此状态：

```text
not_equivalent / no_same_semantic_web_search
```

不能说“一致”，也不能说“不一致”，因为根本没有合法对照对象。

### `search_comprehensive`

代码有候选：

```text
/api/v1/kuaishou/app/search_comprehensive
```

但它是综合搜索，业务口径比纯视频更宽：

```text
status = candidate_pending_probe
```

未来只能比较可识别视频子集，不能拿综合总数和视频 Search V2 总数直接比。

---

## 6.2 抖音

正式：

```text
POST /api/v1/douyin/search/fetch_video_search_v2
```

候选：

```text
POST /api/v1/douyin/search/fetch_video_search_v1
status = candidate_pending_probe
```

代码：

```text
operations/douyin.py
build_video_search_request(...)
build_video_search_v1_candidate_request(...)
```

V1/V2 都能接受同一组核心条件：

```text
keyword
cursor
sort
publish_time
duration
content_type
```

因此这是目前比较适合做真实搜索 A/B 的候选。

---

## 6.3 微博

正式搜索：

```text
GET /api/v1/weibo/web/fetch_search
```

候选：

```text
GET /api/v1/weibo/app/fetch_search_all
status = candidate_pending_probe
```

代码显式保留一个差异：

```text
Web 可以 time_scope
App candidate 不伪造 Web 私有 time_scope
```

因此只能在双方真正可对齐的条件下比较。

一级评论：

```text
正式 App
/api/v1/weibo/app/fetch_status_comments

候选 Web V2
/api/v1/weibo/web_v2/fetch_post_comments
status = candidate_pending_probe
```

二级评论当前正式本身就是：

```text
/api/v1/weibo/web_v2/fetch_post_sub_comments
```

所以“微博 App/Web 哪个是主链”不能按整个平台笼统下结论，必须按业务 Operation 分开。

---

## 6.4 B站

正式主链当前使用 App：

```text
Search
/api/v1/bilibili/app/fetch_search_by_type

Detail
/api/v1/bilibili/app/fetch_one_video

Comments
/api/v1/bilibili/app/fetch_video_comments

Reply
/api/v1/bilibili/app/fetch_reply_detail
```

当前 Web Candidate：

```text
Search   /api/v1/bilibili/web/fetch_general_search
Detail   /api/v1/bilibili/web/fetch_one_video
Comments /api/v1/bilibili/web/fetch_video_comments
Reply    /api/v1/bilibili/web/fetch_comment_reply
```

状态仍按 endpoint/operation 真实验证结果决定；当前不能因为 builder 已存在就自动升级为生产 fallback。

搜索排序只对齐明确映射：

```text
latest  ↔ pubdate
general ↔ totalrank
```

评论/回复要用同一 BV ID、同一根评论对照。

---

## 6.5 小红书

当前正式主链：

```text
App V2
```

代码同时有：

```text
App V1 Search Candidate
Web V3 Search Candidate
```

位置：

```text
operations/xiaohongshu.py
```

但是小红书多代接口的参数/字段/能力持续演进，因此不能拿旧 endpoint 名称或历史文档直接宣布它们是备用。

当前原则：

```text
primary = App V2
alternate family = endpoint-specific verification required
```

要升级为 `verified_backup`，必须对目标 Endpoint 单独重新确认。

---

# 7. 当前候选状态表

这张表记录当前仓库文档已经有的结论；如果后续新 Real Probe 改变状态，要同时更新台账和测试证据。

| 平台 | 对照 | 状态 | 当前结论 |
| --- | --- | --- | --- |
| 快手 | App Comments/SubComments vs Web | `verified_backup` | 同作品/根评论均 200 非空；App 历史 Probe 成本更低；生产主链是 App |
| 快手 | App Search V2 vs Web Search | `not_equivalent` | 无同语义 Web Search |
| 快手 | App Search V2 vs App Comprehensive | `candidate_pending_probe` | 综合搜索更宽，只可比视频子集 |
| 抖音 | Video Search V2 vs V1 | `candidate_pending_probe` | 同业务候选 builder 已存在 |
| 微博 | Web Search vs App Search All | `candidate_pending_probe` | 只能在可对齐过滤条件下比较 |
| 微博 | App Comments vs Web V2 Comments | `candidate_pending_probe` | 同内容候选已存在 |
| B站 | App vs Web Search/Detail/Comments/Reply | `candidate_pending_probe` | 候选 builder 已存在，需按 operation 真实验证 |
| 小红书 | App V2 vs App V1/Web V3 等 | `candidate_pending_probe` | 需 endpoint-specific 当前验证 |

注意：本表不是 Runtime 配置。Runtime 当前主链仍看 `capabilities.py` 和各主 builder。

---

# 8. 一个 Candidate 怎样升级为 `verified_backup`

必须同时满足：

1. 当前 Endpoint/参数由代码和 Provider 当前资料确认；
2. 真实查到 endpoint-level Pricing；
3. 使用同关键词/同内容 ID/同根评论做受限 A/B；
4. 两边都成功；
5. 两边都能提取稳定内容/评论 ID；
6. 记录数量、交集、only 集合、Jaccard；
7. 记录排序/分页差异；
8. 响应结构能进入现有或候选 Extractor/Mapper；
9. 不需要把 Provider 私有字段污染到 Canonical；
10. Fixture/测试/Secret Scan 通过；
11. 更新真实验证台账和本策略文档。

即使全部满足：

```text
verified_backup
≠ 自动 fallback
```

正式切主仍是独立变更。

---

# 9. 实际做一次 A/B 应该怎么走

## 9.1 先确认主链代码

例如抖音：

```text
operations/douyin.py
→ build_video_search_request()
```

## 9.2 找 Candidate Builder

```text
build_video_search_v1_candidate_request()
```

不要自己在临时脚本里手写 endpoint/参数，否则测的不是生产代码候选。

## 9.3 控制真实请求边界

Real Probe 必须：

- 显式运行；
- 有请求上限；
- 有费用意识；
- 不进普通 CI；
- 不打印 Secret；
- 不默认写生产业务库。

## 9.4 保存脱敏证据

```text
tests/fixtures/providers/tikhub/endpoint_ledger/<date>/
```

或当前对应平台 Fixture 目录。

## 9.5 比较稳定 ID

使用：

```text
api_family_compare.py
```

它只做稳定 ID 集合比较，不访问网络、不访问数据库、不读 Secret。

## 9.6 再决定状态

```text
真实对照不足
→ candidate_pending_probe

没有同语义对象
→ not_equivalent

真实同输入可归一化且价格/结构已确认
→ verified_backup
```

---

# 10. 正式切换主接口时应该改什么

不要只改一个 URL。

至少检查：

```text
operations/<platform>.py
→ 正式 builder / pagination / extractor

capabilities.py
→ 主 Operation 能力声明

runtime.py
→ Operation / Mapper 装配

pricing.toml
→ 当前正式 endpoint 价格

mappers/<platform>.py
→ 如果 shape 有差异

tests/fixtures/providers/tikhub/
→ 新真实 Sanitized Fixture

unit / contract / integration
→ 结构、Canonical、Ingestion

docs/collection/<platform>.md
本策略文档
03_TikHub五平台真实响应与字段映射.md
05_TikHub接口选型与真实验证台账.md
```

如果响应业务事实无法由当前 Canonical 表达，再单独评估 Contract 变化；不要为了切接口顺手扩大公共 Schema。

---

# 11. 当前明确禁止的做法

- `transport.py` 捕获 App 错误后自动改发 Web；
- 同一个 Attempt 内隐藏第二次真实 HTTP；
- 仅凭 Endpoint 名称相似宣布等价；
- 两边空结果就记 Jaccard 1.0；
- 用标题/作者名替代稳定 ID 比较；
- 未查价格就升级 `verified_backup`；
- Candidate 尚未验证就登记到默认 Capability；
- 把历史 Probe 价格当当前 Pricing 配置；
- 把 TikHub 官方示例响应伪造成仓库“真实 Fixture”。
