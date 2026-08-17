# TikHub 多接口验证与备用策略

> 状态：已批准长期设计  
> 生效日期：2026-08-16  
> 适用范围：小红书、抖音、微博、B站、快手 TikHub API family 选型、A/B Probe、备用接口证据

## 1. 目的

同一个平台在 TikHub 中可能同时存在 App、Web、V1、V2、V3 等不同 API family。它们可能使用相似关键词或内容 ID，但**不能因为接口名字相似就假定返回数量、内容集合、排序、分页、字段结构或成本一致**。

本项目把“正式主 Operation”和“备用兼容证据”分开：

```text
正式主 Operation
→ 默认 Capability / Runtime 唯一使用

候选 Operation
→ 只用于显式 A/B Probe
→ 不进入自动 fallback
→ 真实验证通过后可升级为“已验证备用”
```

“已验证备用”只表示当前有真实兼容证据，**不表示生产运行时会自动切换**。如需把备用接口切成主接口，必须形成显式变更并重新验证 Pricing、Fixture、Mapper/Extractor、Capability 和回归测试。

## 2. 证据状态

每个候选接口只允许三种状态：

| 状态 | 含义 | 能否作为自动 fallback |
| --- | --- | --- |
| `verified_backup` | 同业务输入的受限真实 A/B 成功，稳定 ID/结构可归一化，endpoint 价格已核验 | **不能** |
| `candidate_pending_probe` | 当前官方 endpoint/参数已确认，代码可构造显式候选请求，但尚无本轮真实 A/B | 不能 |
| `not_equivalent` | 当前没有同语义 endpoint，或候选业务语义明显不同 | 不能 |

禁止用旧聊天、文档示例、历史响应或接口名称相似度把 `candidate_pending_probe` 提升成 `verified_backup`。

## 3. A/B 必须记录的字段

搜索类接口使用同一关键词、尽可能相同的排序/发布时间/内容类型条件，在短时间窗口内各请求一页。每次比较至少记录：

```text
platform
business_operation
keyword / content_id / root_comment_id
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

稳定内容 ID 是判断“内容是否一致”的主键，不按标题、作者名或链接去重。评论对照使用稳定 comment ID。

Jaccard 定义：

```text
shared / union
```

两边都返回 0 条时 `union=0`，Jaccard 必须记为 `null/inconclusive`，不得写成 `1.0` 或“完全一致”。

单页完全一致也只证明本次输入、时间和页窗口下的集合一致，**不证明全量分页结果永远一致**。若要判断全量等价，必须进一步验证两套分页直到各自终止，并记录请求数和费用。

## 4. 当前平台矩阵

### 4.1 快手

#### 正式主链

```text
Search      App /api/v1/kuaishou/app/search_video_v2
Detail      App /api/v1/kuaishou/app/fetch_one_video
Comments    App /api/v1/kuaishou/app/fetch_video_comment
SubComments App /api/v1/kuaishou/app/fetch_video_sub_comments
```

2026-08-16 用户已批准把一级、二级评论从 Web 正式切换到 App。

#### 已验证备用

```text
Comments    Web /api/v1/kuaishou/web/fetch_one_video_comment
SubComments Web /api/v1/kuaishou/web/fetch_one_video_sub_comment
status      verified_backup
```

同一真实作品、同一有回复根评论的 Web/App A/B 中：Web/App 一级均 HTTP 200 非空，Web/App 二级均 HTTP 200 非空。App 一级还返回部分 `subCommentsMap`。当次 endpoint-info 价格快照为：App 一级 0.001 USD、App 二级 0.001 USD、Web 一级 0.002 USD、Web 二级 0.010 USD。

生产 Runtime **只调用 App 主链**。Web builder 只允许显式 Probe/人工切换使用，不做异常自动 fallback。

#### 搜索 App/Web 是否一致

当前快手 Web API family 没有与关键词视频搜索同语义的 Web Search endpoint，因此不存在合法的：

```text
App Search V2 vs Web Search
```

A/B 对象。结论必须记录为：

```text
not_equivalent / no_same_semantic_web_search
```

因此现在既不能说“App/Web 数量一致”，也不能说“不一致”。

快手 App 另有：

```text
/api/v1/kuaishou/app/search_comprehensive
```

它包含综合搜索语义，不是 Web Search，也不是纯视频 Search V2 的严格等价接口。当前只作为 `candidate_pending_probe`，未来实验只能比较其中可识别的视频子集，不能直接拿综合结果总数和 Search V2 视频总数宣称一致或不一致。

### 4.2 抖音

正式搜索：

```text
/api/v1/douyin/search/fetch_video_search_v2
```

当前同业务候选：

```text
/api/v1/douyin/search/fetch_video_search_v1
status = candidate_pending_probe
```

V1/V2 都是视频关键词搜索，并能使用同一组核心 keyword/cursor/sort/publish-time/duration/content-type 条件，因此是优先级最高的搜索 A/B 对象。

“综合搜索 V1/V2”等其他搜索页语义不直接当作当前视频搜索备用；需要单独证明业务对象和稳定内容 ID 语义一致后才能升级。

### 4.3 微博

正式搜索：

```text
Web /api/v1/weibo/web/fetch_search
```

候选搜索：

```text
App /api/v1/weibo/app/fetch_search_all
status = candidate_pending_probe
```

两者都支持关键词与搜索类型，但当前排序/时间过滤语义并非完全相同：Web 可以显式携带 `time_scope`，App 候选不伪造该参数。因此只能在可对齐条件下做真实集合比较，不能先验认定等价。

正式一级评论：

```text
App /api/v1/weibo/app/fetch_status_comments
```

候选一级评论：

```text
Web V2 /api/v1/weibo/web_v2/fetch_post_comments
status = candidate_pending_probe
```

正式二级评论当前本身使用 Web V2 `/fetch_post_sub_comments`，所以“App/Web 备用”需要按具体业务 Operation 分开判断，不能给整个平台一个笼统结论。

### 4.4 B站

当前正式主链使用 App Search/Detail/Comments/Reply。

当前 Web 候选：

```text
Search   /api/v1/bilibili/web/fetch_general_search
Comments /api/v1/bilibili/web/fetch_video_comments
Reply    /api/v1/bilibili/web/fetch_comment_reply
status   candidate_pending_probe
```

搜索 A/B 只对齐明确可映射的排序，例如 `latest ↔ pubdate`、`general ↔ totalrank`。评论/回复优先使用同一个 BV ID、同一个根评论做单页对照。真实验证前不修改 App 默认 Capability。

### 4.5 小红书

当前正式主链保持 App V2。

TikHub 存在多代 App/Web API family，官方也给出详情 API 的版本优先级，但当前文档目录中的不同 family 能力在持续演进。对小红书不得根据旧 endpoint 名称或历史文档直接声明“Web 搜索/评论备用”。

当前状态：

```text
primary = App V2
alternate family = candidate_pending_probe / endpoint-specific verification required
```

只有重新确认目标 endpoint 当前存在、查得 endpoint-level Pricing，并完成同内容/同关键词真实 A/B 后，才能新增 `verified_backup`。

## 5. 当前实验状态

截至 2026-08-16：

| 平台 | 对照 | 状态 | 已知结论 |
| --- | --- | --- | --- |
| 快手 | App Comments/SubComments vs Web | `verified_backup` | 同作品/根评论两边均 200 非空；App 成本更低；正式主链已切 App |
| 快手 | App Search V2 vs Web Search | `not_equivalent` | 当前无同语义 Web Search，不能做数量/内容等价实验 |
| 快手 | App Search V2 vs App Comprehensive | `candidate_pending_probe` | 综合搜索语义更宽，只能比较视频子集 |
| 抖音 | Video Search V2 vs V1 | `candidate_pending_probe` | 同业务候选已确认，等待真实 A/B |
| 微博 | Web Search vs App Search All | `candidate_pending_probe` | 可对齐部分条件，排序/时间语义需实测 |
| 微博 | App Comments vs Web V2 Comments | `candidate_pending_probe` | 同内容评论候选已确认，等待真实 A/B |
| B站 | App Search vs Web Search | `candidate_pending_probe` | 同关键词候选已确认，等待真实 A/B |
| B站 | App Comments/Reply vs Web | `candidate_pending_probe` | 同内容候选已确认，等待真实 A/B |
| 小红书 | App V2 vs 其他 family | `candidate_pending_probe` | 必须先做当前 endpoint 级重新确认，禁止复用旧文档结论 |

当前执行沙箱无法连接 `api.tikhub.io`；仓库已有 GitHub-hosted Runner 的一次性 RSA 凭据交接方案，但当前工具无法读取其公钥 artifact 的二进制内容，也没有安全写入 Actions Secret 的能力。因此除已有快手评论 A/B 外，其余候选暂不升级为 `verified_backup`。

## 6. 代码边界

- 正式主 Operation builder 使用业务稳定名称，例如 `build_video_comments_request`；
- 候选接口使用带 `candidate` 的显式 builder 名称，避免被 Runtime 无意选中；
- 已验证备用可以保留显式 `build_web_*` 等 builder，但默认 Capability 仍只登记主接口；
- 候选 endpoint 未进入正式 Dispatch 前，不因官方文档存在而写入 verified Pricing；真实 Probe 先查 endpoint-info，再受请求数/费用上限保护；
- `api_family_compare.py` 只比较稳定 ID 集合，不访问网络、数据库或 Provider Secret；
- Probe 输出可以记录 endpoint path、价格、计数和脱敏稳定 ID，但不得保存 API Key、Authorization、Cookie、Token 或未脱敏业务正文。

## 7. 升级为已验证备用的门禁

一个候选只有同时满足以下条件才能从 `candidate_pending_probe` 变成 `verified_backup`：

1. 当前官方 endpoint 和参数再次确认；
2. `get_endpoint_info` 返回 endpoint-level 精确单价；
3. 使用同关键词或同内容 ID 做受限真实请求，两边均成功；
4. 能提取稳定内容/评论 ID；
5. 记录数量、交集、仅主、仅候选、Jaccard 和排序/分页差异；
6. 响应结构可经现有或候选 Extractor/Mapper 归一化，不需要污染 Canonical 公共字段；
7. Secret Scan、目标 Unit/Contract/质量门禁通过；
8. 长期文档更新真实实验日期和结论。

通过这些门禁后仍**不建立自动 fallback**。正式主接口切换必须另行显式批准。
