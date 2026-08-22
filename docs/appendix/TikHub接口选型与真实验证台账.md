# TikHub 接口选型与真实验证台账

> 首批真实验证：2026-08-15 至 2026-08-16  
> Provider：TikHub  
> Probe Base URL：`https://api.tikhub.io`  
> 历史验证关键词：`爱玛`

这是一份**实证台账**。它记录“为什么当前生产代码选择这组 TikHub Endpoint，以及哪些备用/候选曾经得到什么真实证据”。

它和另外两篇 TikHub 文档的职责不同：

- [`TikHub五平台真实响应与字段映射.md`](TikHub五平台真实响应与字段映射.md)：开发时查 JSON 路径、Mapper 和 Fixture；
- [`TikHub多接口验证与备用策略.md`](TikHub多接口验证与备用策略.md)：说明 A/B 方法、状态和切换门禁；
- **本文**：保存已经得到的真实 Endpoint、价格快照和 A/B 结论。

当前生产 Endpoint 的最终机器事实仍看：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/
backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml
```

真实响应结构看：

```text
tests/fixtures/providers/tikhub/
```

---

## 1. 当前生产主链一览

| 平台 | Search | Detail | Comments | Replies/Sub-comments |
| --- | --- | --- | --- | --- |
| 小红书 | App V2 `search_notes` | App V2 image/video detail | App V2 `get_note_comments` | App V2 `get_note_sub_comments` |
| 抖音 | Search V2 | App V3 one video | App V3 video comments | App V3 comment replies |
| 微博 | Web Search | App status detail | App status comments | Web V2 sub comments |
| B站 | App search by type | App one video | App video comments | App reply detail |
| 快手 | App video search V2 | App one video | App video comment | App video sub comments |

这些接口不是因为“版本号最新”自动胜出，而是因为当前代码和证据链对：

```text
Endpoint 可调用
→ 稳定 ID 可串联
→ Pagination 可解释
→ Mapper 能归一化
→ Pricing 已核验
→ Fixture/Test 已覆盖
```

闭环更完整。

---

## 2. 当前 Pricing 机器事实

运行时价格来源：

```text
backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml
```

当前 Pricing Snapshot：

```text
schema_version = tikhub-pricing.v1
pricing_version = 2026-08-16.1
verified_at = 2026-08-16
```

当前正式主链价格：

| 平台/业务 | Endpoint | 当前配置 base_price USD/request |
| --- | --- | ---: |
| xiaohongshu Search | `/api/v1/xiaohongshu/app_v2/search_notes` | 0.010 |
| xiaohongshu Image Detail | `/api/v1/xiaohongshu/app_v2/get_image_note_detail` | 0.010 |
| xiaohongshu Video Detail | `/api/v1/xiaohongshu/app_v2/get_video_note_detail` | 0.010 |
| xiaohongshu Comments | `/api/v1/xiaohongshu/app_v2/get_note_comments` | 0.010 |
| xiaohongshu SubComments | `/api/v1/xiaohongshu/app_v2/get_note_sub_comments` | 0.010 |
| Douyin Search V2 | `/api/v1/douyin/search/fetch_video_search_v2` | 0.010 |
| Douyin Detail | `/api/v1/douyin/app/v3/fetch_one_video_v3` | 0.001 |
| Douyin Comments | `/api/v1/douyin/app/v3/fetch_video_comments` | 0.001 |
| Douyin Replies | `/api/v1/douyin/app/v3/fetch_video_comment_replies` | 0.001 |
| Weibo Search | `/api/v1/weibo/web/fetch_search` | 0.001 |
| Weibo Detail | `/api/v1/weibo/app/fetch_status_detail` | 0.001 |
| Weibo Comments | `/api/v1/weibo/app/fetch_status_comments` | 0.001 |
| Weibo SubComments | `/api/v1/weibo/web_v2/fetch_post_sub_comments` | 0.001 |
| Bilibili Search | `/api/v1/bilibili/app/fetch_search_by_type` | 0.001 |
| Bilibili Detail | `/api/v1/bilibili/app/fetch_one_video` | 0.001 |
| Bilibili Comments | `/api/v1/bilibili/app/fetch_video_comments` | 0.001 |
| Bilibili Replies | `/api/v1/bilibili/app/fetch_reply_detail` | 0.001 |
| Kuaishou Search V2 | `/api/v1/kuaishou/app/search_video_v2` | 0.010 |
| Kuaishou Detail | `/api/v1/kuaishou/app/fetch_one_video` | 0.001 |
| Kuaishou App Comments | `/api/v1/kuaishou/app/fetch_video_comment` | 0.001 |
| Kuaishou App SubComments | `/api/v1/kuaishou/app/fetch_video_sub_comments` | 0.001 |

已验证但当前不是快手生产主评论链的 Web 价格：

```text
Web Comments     = 0.002 USD/request
Web SubComments  = 0.010 USD/request
```

注意：上表是**当前仓库 Pricing 配置事实**，不是对 TikHub 永久价格的承诺。以后重新核价后应更新 `pricing.toml`，本文同步摘要即可。

未知 Endpoint 不允许退回 `default_base_price` 自动发送；当前：

```text
default_price_dispatch_fallback = false
```

---

# 3. 小红书真实验证

## 3.1 当前主链

```text
Search
GET /api/v1/xiaohongshu/app_v2/search_notes

Image Detail
GET /api/v1/xiaohongshu/app_v2/get_image_note_detail

Video Detail
GET /api/v1/xiaohongshu/app_v2/get_video_note_detail

Comments
GET /api/v1/xiaohongshu/app_v2/get_note_comments

SubComments
GET /api/v1/xiaohongshu/app_v2/get_note_sub_comments
```

真实 Fixture：

```text
tests/fixtures/providers/tikhub/xiaohongshu/
```

已验证的业务链：

```text
Search note_id
→ image/video Detail
→ Comments
→ root comment
→ SubComments
```

生产继续使用 App V2，因为这一整条链拥有真实非空 Fixture、成熟 Mapper 和 Raw Replay/纵切证据。

## 3.2 历史 Probe 的 Search 参数例子

为了验证评论链，曾使用高评论优先图文搜索：

```json
{
  "keyword": "爱玛",
  "page": 1,
  "sort_type": "comment_descending",
  "note_type": "普通笔记",
  "time_filter": "不限",
  "source": "explore_feed"
}
```

视频详情另用视频类型搜索。

这只是 Probe 输入例子，不是所有生产 Plan 的固定参数。生产业务枚举和参数映射以：

```text
operations/xiaohongshu.py
```

为准。

## 3.3 Alternate family 状态

当前代码存在 App V1 / Web V3 Search Candidate Builder，但没有足够证据将它们作为自动备用：

```text
status = candidate_pending_probe
```

---

# 4. 抖音真实验证

## 4.1 当前主链

```text
Search
POST /api/v1/douyin/search/fetch_video_search_v2

Detail
GET /api/v1/douyin/app/v3/fetch_one_video_v3

Comments
GET /api/v1/douyin/app/v3/fetch_video_comments

Replies
GET /api/v1/douyin/app/v3/fetch_video_comment_replies
```

Fixture：

```text
tests/fixtures/providers/tikhub/douyin/
```

## 4.2 Search V2 vs V1 历史 A/B

同关键词、最新、7 天、视频条件下，曾得到：

| 指标 | V2 主接口 | V1 候选 |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| 历史 Probe 单价 | 0.010 | 0.010 |
| 首屏稳定内容 ID 数 | 7 | 7 |
| 共享 ID | 7 | 7 |
| 仅一侧 | 0 | 0 |
| Jaccard | 1.0 | 1.0 |

但两套 Raw shape 差异很大，字段路径 Jaccard 曾约为：

```text
0.0156
```

因此这个 A/B 只能证明：

> 当次首屏内容集合一致，两边 HTTP 可用。

不能证明：

- V1 可以直接套用 V2 extractor；
- 全量分页永远一致；
- V1 已经是生产级备用。

当前状态仍应看候选实现/测试是否完成，不能只根据 7/7 历史结果自动启用。

---

# 5. 微博真实验证

## 5.1 当前主链

```text
Search
GET /api/v1/weibo/web/fetch_search

Detail
GET /api/v1/weibo/app/fetch_status_detail

Comments
GET /api/v1/weibo/app/fetch_status_comments

SubComments
GET /api/v1/weibo/web_v2/fetch_post_sub_comments
```

这是一条混合 Web/App/Web V2 的主链。

为什么没有为了“整齐”强制全部 App：因为每个业务 Operation 分别选择当前真实证据和 Mapper 更完整的接口。

## 5.2 Web Search vs App Search All 历史 A/B

同关键词、可对齐搜索类型下：

| 指标 | Web 主接口 | App Candidate |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| 历史 Probe 单价 | 0.001 | 0.001 |
| 唯一 ID | 10 | 11 |
| 共享 | 9 | 9 |
| Web only | 1 | - |
| App only | - | 2 |
| Union | 12 | 12 |
| Jaccard | 0.75 | 0.75 |

结论：高度重合，但不是同一个结果集合。

而且当前 Web Search 可以表达 `time_scope`，App Candidate 不伪造这个 Web 私有参数，因此不能宣称两套语义完全等价。

## 5.3 App Comments vs Web V2 Comments 历史 A/B

同一个真实微博内容曾得到：

```text
App → 200 / 1 个稳定评论 ID
Web → 200 / 1 个稳定评论 ID
shared = 1
Jaccard = 1.0
```

Raw shape 仍不同，所以 Web Comments 只是候选证据；当前一级评论生产链继续使用 App。

---

# 6. B站真实验证

## 6.1 当前主链

```text
Search
GET /api/v1/bilibili/app/fetch_search_by_type

Detail
GET /api/v1/bilibili/app/fetch_one_video

Comments
GET /api/v1/bilibili/app/fetch_video_comments

Replies
GET /api/v1/bilibili/app/fetch_reply_detail
```

Fixture：

```text
tests/fixtures/providers/tikhub/bilibili/
```

## 6.2 App Search vs Web Search 旧 A/B 的重要勘误

旧 A/B 汇总曾写：

```text
App = 0
Web = 20
```

后续确认：这个“0”来自比较器没有正确从 App wrapper 的 `param/av` 结构提取稳定视频 ID。

因此：

```text
旧数量/Jaccard 结论作废
reason = comparison_extractor_invalid
```

这不能解释成 TikHub App Search 返回 0 条。

在重新用正确 extractor 做最小真实 A/B 前，Web Search 不能升级为 verified backup。

这也是为什么“Probe 脚本本身”也必须复用/验证真实 extractor，而不能只看 HTTP 200。

---

# 7. 快手真实验证

## 7.1 当前主链

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

当前 `operations/kuaishou.py` 的正式评论 builder 明确走 App。

## 7.2 App vs Web 评论 A/B

同一个真实作品、同一个确实有回复的根评论：

| 项目 | Web | App |
| --- | ---: | ---: |
| 一级评论 HTTP | 200 | 200 |
| 二级评论 HTTP | 200 | 200 |
| 二级 `data.subComments[]` | 非空 | 非空 |
| 历史 Probe 一级价格 | 0.002 | 0.001 |
| 历史 Probe 二级价格 | 0.010 | 0.001 |

结论：

```text
App
→ 正式主链

Web
→ verified_backup
→ 不自动 fallback
```

App 一级还能够返回部分：

```text
data.subCommentsMap.<root>.subComments[]
```

当前 App 主链结构证据不要误指向历史 Web Fixture。直接看：

[`../../tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json`](../../tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json)

历史 Web Fixture 仍保留用于 Web 备用回归：

```text
tests/fixtures/providers/tikhub/kuaishou/comments_page1.sanitized.json
tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json
```

## 7.3 Search V2 vs Web

当前没有同语义 Web 关键词视频 Search：

```text
not_equivalent / no_same_semantic_web_search
```

因此没有合法的 App-vs-Web 搜索数量结论。

## 7.4 Search V2 vs App Comprehensive

历史单页 A/B：

| 指标 | Video Search V2 | Comprehensive |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| 历史 Probe 单价 | 0.010 | 0.010 |
| 唯一内容 ID | 17 | 8 |
| 共享 | 0 | 0 |
| Union | 25 | 25 |
| Jaccard | 0.0 | 0.0 |

这说明在当次输入下，两者结果集合完全不同；结合 `search_comprehensive` 本身更宽的业务语义，它不能当成 Video Search V2 的自动备用，只能作为未来补充发现候选。

---

# 8. 当前验证矩阵

| 平台 | 对照 | 当前证据结论 |
| --- | --- | --- |
| xiaohongshu | App V2 vs 其他 family | 生产 App V2；其他 family 需 endpoint-specific 重新验证 |
| 抖音 | Search V2 vs V1 | 历史首屏集合 7/7 相同，但 Raw shape 明显不同；Candidate 不能直接切主 |
| 微博 | Web Search vs App Search All | 历史 Jaccard 0.75；不等价 |
| 微博 | App Comments vs Web V2 | 历史同样本 1/1，但 Raw shape 不同 |
| B站 | App Search vs Web Search | 旧比较器提取错误，数量结论作废，需重验 |
| 快手 | App Comments/Sub vs Web | Web 已验证备用；App 正式主链 |
| 快手 | Video Search V2 vs Web | 无同语义 Web Search |
| 快手 | Video Search V2 vs Comprehensive | 历史集合完全不同，且业务语义更宽 |

状态含义和升级门禁见：

[`TikHub多接口验证与备用策略.md`](TikHub多接口验证与备用策略.md)

---

# 9. 如何从台账追到代码

例如你想确认“快手为什么现在走 App 评论”。

按顺序：

```text
1. 本文
→ 看到 App/Web A/B 和价格证据

2. operations/kuaishou.py
→ build_video_comments_request()
→ 当前明确调用 App builder

3. capabilities.py
→ 当前 Capability 能力声明

4. mappers/kuaishou.py
→ reply_count / comment tree 如何映射

5. endpoint_ledger Fixture
→ App 真实字段证据

6. pricing.toml
→ 当前 App/Web endpoint 价格配置

7. tests
→ Operation / Mapper / Capability 回归
```

这样台账不是孤立的“历史实验记录”，而是能反查当前实现为什么这样写。

---

# 10. 新增一次真实验证怎样入账

不要直接编辑一行“已验证”。

正确流程：

```text
确认当前主/候选 builder
→ 查 endpoint info / Pricing
→ 受限真实 Probe
→ 保存脱敏证据
→ 提取稳定 ID
→ api_family_compare.py 比较
→ 验证 shape / Mapper / Canonical
→ 必要时 PostgreSQL 纵切
→ 更新状态
→ 更新本文和对应平台文档
```

需要保存的长期信息：

- 验证日期；
- 业务 Operation；
- 主/候选 Endpoint；
- 可对齐输入条件；
- endpoint price 快照；
- HTTP 结果；
- stable ID 数量/交集；
- Raw shape/Mapper 兼容结论；
- 分页/排序差异；
- 最终状态；
- Fixture/证据位置。

不要把临时 Runner 文件、真实正文、真实用户 ID 或 Secret 直接提交仓库。

---

# 11. 当前接口切换原则

即使候选真实 A/B 成功，也只会先得到：

```text
verified_backup
```

生产主链切换需要显式修改：

```text
Operation builder
Capability
Runtime
Pricing
Mapper/Extractor（需要时）
Fixture
Tests
平台文档
本文
```

当前不实现自动 API family fallback；否则会改变 Attempt、Raw lineage、失败语义和费用审计。
