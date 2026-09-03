# 小红书采集实现

本文是小红书当前 TikHub 生产实现和人工真实调试入口的代码导航。精确 JSON 字段见：

[`docs/appendix/02_TikHub五平台真实响应与字段映射.md`](../appendix/02_TikHub五平台真实响应与字段映射.md)

## 1. 当前代码

```text
关键词 Search / Detail / Comments / SubComments Operation / Pagination
→ backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py

账号 Search / User Info / User Notes Operation / Pagination
→ backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu_accounts.py

账号人工调试 Runtime
→ backend/src/aima_ugc/adapters/providers/tikhub/account_runtime.py

Mapper
→ backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py

Capability
→ backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py

真实 Fixture
→ tests/fixtures/providers/tikhub/xiaohongshu/
```

生产 Collection 串联：

- [`backend/src/aima_ugc/bootstrap/collection_scope.py`](../../backend/src/aima_ugc/bootstrap/collection_scope.py)

人工账号采集入口：

- [`backend/src/aima_ugc/adapters/providers/tikhub_test/xiaohongshu_accounts_test.py`](../../backend/src/aima_ugc/adapters/providers/tikhub_test/xiaohongshu_accounts_test.py)

账号入口复用正式 TikHub Transport、已有小红书 Mapper、Detail/Comments/SubComments Runtime、Canonical JSONL 和共享 Excel Exporter；它不是第二套采集器。

## 2. 当前生产主链与账号人工 Discovery

### 2.1 生产 Collection 主链

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

当前正式 Collection 主链是 App V2 关键词发现。

代码里还存在 App V1 / Web V3 的显式 Search Candidate Builder，用于 A/B 验证；它们没有进入自动 fallback。

### 2.2 指定账号人工 Discovery

人工文件采集另外复用以下 App V2 Operation：

```text
Search Users
GET /api/v1/xiaohongshu/app_v2/search_users

User Info（可选身份复核）
GET /api/v1/xiaohongshu/app_v2/get_user_info

User Posted Notes
GET /api/v1/xiaohongshu/app_v2/get_user_posted_notes
```

这三条 Operation 当前用于 `tikhub_test` 指定账号人工采集，不等于已经开放为生产 Collection Capability、Scheduler Source 或数据库 Dispatch 能力。

当前边界：

```text
账号 Discovery
→ 解析稳定 user_id
→ get_user_posted_notes 全页遍历
→ 北京时间日期过滤
→ 复用既有 Detail / Comments / SubComments
→ 复用 Mapper / Canonical / Excel
→ 文件输出
```

人工账号 Runner 固定 `write_to_database=False`。因此新账号 Discovery Operation 当前不需要伪造 Pricing Registry 条目；若未来要进入正式数据库 Dispatch/Collection Capability，必须先独立完成价格核验、真实 Probe、Fixture/Contract 和调度设计门禁。

## 3. Search 当前支持什么

生产关键词 Capability 当前公开：

```text
sort
→ general
→ latest
→ most_liked
→ most_commented
→ most_collected
→ english_preferred

time_filter
→ all
→ 1d
→ 7d
→ 180d

content_type
→ all
→ video
→ image
```

当前：

```text
native_time_filter = true
observes_comment_count = true
```

不要在前端自己维护一份小红书参数表；以后 Operation/Capability 变化后应通过后端 Contract/OpenAPI 同步。

指定账号人工 Discovery 不复用关键词 `time_filter`。它通过 `get_user_posted_notes` 遍历账号笔记，再按配置的包含式日期区间在 AIMA 内以 `Asia/Shanghai` 过滤。

## 4. Search 真实响应位置

主要业务 item：

```text
data.data.items[]
```

其中常见笔记对象位于：

```text
item.note
```

Fixture：

- [`tests/fixtures/providers/tikhub/xiaohongshu/search_notes_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/search_notes_page1.sanitized.json)

Operation 中的 Extractor 是生产字段事实；不要从本文复制一段 JSONPath 后在其他脚本再实现一套。

账号 Discovery 同样由 `operations/xiaohongshu_accounts.py` 的 Extractor/Pagination 负责 Provider shape，人工入口不得手写 Provider JSON 路径或 cursor。

当前 `get_user_posted_notes` 真实响应中的笔记发布时间字段为 `create_time`。共享小红书 Mapper 会把它归一化为 Canonical `published_at`，账号人工采集再用该时间执行日期过滤；不能因为账号列表字段名与关键词搜索不同就把发布时间当成缺失。

## 5. Search 与账号分页

当前关键词 `XiaohongshuSearchPagination` 会维护：

```text
page
search_id
search_session_id
```

并观察 Provider 的：

```text
has_more
next_page
search_id
search_session_id
```

账号 Discovery 分别维护：

```text
search_users
→ page / search_id

get_user_posted_notes
→ cursor / 已见 note_id
```

两类分页都会防止空页、重复页、分页状态不推进，并以 Provider 耗尽或显式技术页数上限收口。

`get_user_posted_notes` 翻页优先使用响应级下一页 `cursor`；只有响应未观察到该字段时，才兼容回退到列表最后一条笔记的 cursor/note_id。

账号日期过滤不会基于“第一页出现旧笔记”推断后续一定更旧；在真实响应顺序得到充分证据前，仍遍历 Provider 分页后再按发布时间过滤，避免漏数。

如果要改 xiaohongshu 分页，先改对应生产 Operation/Runtime 状态机和 Unit Test，不要在 [`backend/src/aima_ugc/bootstrap/collection_scope.py`](../../backend/src/aima_ugc/bootstrap/collection_scope.py) 或人工入口增加私有 cursor 逻辑。

## 6. 指定账号如何消歧

人工配置使用：

```text
user_id > red_id（小红书号） > nickname
```

其中：

- 已知稳定 `user_id` 时可直接使用；
- 配置 `red_id` 时，搜索结果必须精确命中同一 `red_id`；
- 昵称只做辅助核验；昵称变化不会覆盖稳定 `red_id`；
- 只有昵称且存在多个同名候选时 fail closed，不选择第一条；
- 解析出的稳定身份可缓存到 `output/xiaohongshu/resolved_accounts.json`，缓存不保存 API Key。

`get_user_info` 是可选额外复核，默认关闭，避免无必要的付费请求。

## 7. Detail 为什么分图文/视频

xiaohongshu 当前不同内容类型使用不同 Detail Endpoint。

真实路径：

```text
图文
→ data.data[0].note_list[0]

视频
→ data.data[0]
```

Fixture：

- [`tests/fixtures/providers/tikhub/xiaohongshu/image_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/image_detail.sanitized.json)
- [`tests/fixtures/providers/tikhub/xiaohongshu/video_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/video_detail.sanitized.json)

Search Mapper 和账号笔记 Mapper 都复用同一 Canonical Content Mapper；进入后续处理后由内容类型选择正确 Detail Operation。

## 8. 评论能力

当前生产 Capability：

```text
comment_sort_modes = latest
supports_reply_count = true
supports_sub_comments = true
supports_incremental_comment_sort = true
```

一级评论：

```text
data.data.comments[]
```

二级评论：

```text
data.data.comments[]
```

一级评论和二级回复的下一页状态不能只取 `cursor` 字面值。真实 App V2 响应既可能分别返回 `cursor`、`index`、`pageArea`，也可能把这几个字段编码进一个 JSON 字符串形式的 `cursor`。生产 Operation 会先解码这一状态，再由 Runtime 把 `cursor`、`index`、`pageArea` 分别传给下一页请求；把整段 JSON 字符串直接当作 cursor 会造成第二页返回空列表。

根评论 Canonical：

```text
root_comment_id = external_comment_id
parent_comment_id = null
```

二级回复的 parent 只有 Provider 有明确直接父 ID 时才写，不能根据用户名/数组位置猜。

### 人工账号评论模式

指定账号人工配置入口当前默认使用 `all`，评论和回复数量目标会被忽略，只由 Provider 耗尽或分页硬保护停止。需要限制单篇笔记的请求范围时可以显式改为 `limited`，再由 `MAX_COMMENTS_PER_CONTENT` 和 `MAX_REPLIES_PER_ROOT` 控制数量目标；它与生产日常增量策略不同：

```text
正数或未知 comment_count / reply_count
→ 一旦进入抓取，不把数量软目标当作“已经抓完”的停止证据

显式 comment_count=0 / reply_count=0
→ 沿用正式 Collection Decision，跳过对应评论/回复接口

继续分页
→ Provider 明确耗尽
或
→ 技术硬页数上限触发
```

原因是内容详情中的正数数量可能滞后于评论分页实际可返回的数据。测试明确覆盖“计数已经达到，但 Provider `has_more=true`”的一级评论和二级回复场景。

仍保留两类安全边界：

- Provider 分页状态不推进时停止；
- `max_comment_pages_per_content` / `max_reply_pages_per_root` 是技术硬上限，触发时结果不能宣称完整。

一级评论公共链能直接返回 coverage；二级回复公共链当前不暴露最终 Provider 停止原因，因此账号 `all` 在**触达回复硬页数边界**时保守标记账号为 `partial`，避免把可能仍有下一页的数据误报为完整。

## 9. 为什么 xiaohongshu 可以做最新评论增量

当前生产 Capability 明确：

```text
supports_incremental_comment_sort = true
```

这表示生产 latest 评论链和真实样本已经满足稳定已知 Comment ID 边界的增量停止条件。

正确流程：

```text
latest comments page
→ 整页 Raw 保存
→ 整页 Mapper/Ingest
→ 遇到已知稳定评论边界
→ 停止后续页
```

不能遇到当前页第一条旧评论就立刻丢掉同页后续新评论。

人工账号 `comment_mode="all"` 会在正数或未知计数进入抓取后禁用跨运行已知边界与数量软目标的提前停止，优先追到 Provider 耗尽；若技术硬页数上限先触发，则保守标记为部分完成。这不会改变共享关键词 Runner 或正式 Collection Decision 的默认语义。

## 10. 账号人工采集输出

默认输出仍使用 `tikhub_test` 统一目录：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/output/xiaohongshu/
├─ resolved_accounts.json
└─ runs/<run-id>/
   ├─ raw/
   ├─ canonical/
   │  ├─ contents.jsonl
   │  └─ comments.jsonl
   ├─ raw_data/
   │  └─ xiaohongshu_raw_data.xlsx
   └─ run_summary.json
```

Canonical 稳定内容身份仍是：

```text
(platform, external_content_id)
```

账号 Discovery 只改变来源语义：

```text
source_type = account
source_value = resolved user_id
```

不会创建“官号笔记”专用数据模型。

Excel 继续调用系统共享 Exporter，当前固定 Sheet 为：

```text
内容
标签明细
评论
```

## 11. xiaohongshu Raw Replay

当前 Collection 模块包含 xiaohongshu 已存 Raw Replay 能力，用于：

```text
已有 Raw
→ 修 Mapper
→ replay
→ 不重新调用 TikHub
```

相关实现：

- [`backend/src/aima_ugc/modules/collection/xiaohongshu_replay.py`](../../backend/src/aima_ugc/modules/collection/xiaohongshu_replay.py)

这体现通用规则：完整 Raw 已存在时优先重放，不重复付费请求 Provider。

## 12. 当前备用 family 状态

代码中存在：

```text
App V1 Search Candidate
Web V3 Search Candidate
```

当前不能因为 builder 已存在就写成正式备用或自动 fallback。

账号 Discovery 的三个 App V2 Operation 也不能因为已经有 Builder/Runtime 就自动升级为生产 Collection Source；它们当前的批准范围只是人工文件调试。

验证/切换规则：

[`docs/appendix/03_TikHub多接口验证与备用策略.md`](../appendix/03_TikHub多接口验证与备用策略.md)

## 13. 要改什么时改哪里

### 关键词 Search Endpoint/参数变了

```text
operations/xiaohongshu.py
→ Fixture / Real Probe
→ Operation tests
→ capabilities.py（如果业务支持变化）
→ pricing.toml（如果 endpoint identity/price 变化）
→ 本文/TikHub附录
```

### 账号 Discovery Endpoint/参数变了

```text
operations/xiaohongshu_accounts.py
→ account_runtime.py
→ Sanitized Fixture / Real Probe
→ Operation/纵切 tests
→ tikhub_test 入口继续只传业务参数
```

若要升级为正式 Collection Source，再额外设计 Capability、Pricing、数据库 Dispatch、调度和前端契约；不能由人工 Runner 反向成为生产实现。

### JSON 字段路径变了

```text
新 Sanitized Fixture
→ Mapper/Extractor Test
→ mappers/xiaohongshu.py
→ Canonical Contract Test
```

### 新增 xiaohongshu 内容类型

先证明：

```text
Search 能发现
Detail 有稳定 Operation
Mapper 能归一化
Fixture/Test 完整
```

再开放 Capability；不能只在前端加下拉项。

## 14. 调试顺序

生产 Collection：

```text
Collection Run/Scope
→ Provider Request/Attempt
→ xiaohongshu Raw Artifact
→ Candidate
→ xiaohongshu Operation Extractor
→ xiaohongshu Mapper
→ Canonical
→ Rule Relevance / Decision
→ Content Ingestion
```

指定账号人工文件采集：

```text
账号配置
→ search_users / 稳定身份消歧
→ get_user_posted_notes
→ 日期过滤
→ Detail
→ Comments / SubComments
→ Raw + Canonical JSONL + Excel + run_summary
```

数据库 SQL：

[`docs/appendix/01_PostgreSQL查询与调试实战.md`](../appendix/01_PostgreSQL查询与调试实战.md)
