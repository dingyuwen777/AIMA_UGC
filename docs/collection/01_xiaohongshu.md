# 小红书采集实现

本文是小红书当前 TikHub 生产实现的代码导航。精确 JSON 字段见：

[`../appendix/02_TikHub五平台真实响应与字段映射.md`](../appendix/02_TikHub五平台真实响应与字段映射.md)

## 1. 当前代码

```text
Operation / Pagination
→ backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py

Mapper
→ backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py

Capability
→ backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py

真实 Fixture
→ tests/fixtures/providers/tikhub/xiaohongshu/
```

生产 Collection 串联：

- [`backend/src/aima_ugc/bootstrap/collection_scope.py`](../../backend/src/aima_ugc/bootstrap/collection_scope.py)

## 2. 当前正式主 Operation

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

当前正式主链是 App V2。

代码里还存在 App V1 / Web V3 的显式 Search Candidate Builder，用于 A/B 验证；它们没有进入自动 fallback。

## 3. Search 当前支持什么

Capability 当前公开：

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

## 5. Search 分页

当前 `XiaohongshuSearchPagination` 会维护：

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

停止时会防：

- 空页；
- 没有下一页；
- 分页状态不推进；
- 重复页/安全上限等生产保护。

如果要改 xiaohongshu 分页，先改 `operations/xiaohongshu.py` 的状态机和对应 Unit Test，不要在 [`collection_scope.py`](../../backend/src/aima_ugc/bootstrap/collection_scope.py) 增加小红书私有 cursor 逻辑。

## 6. Detail 为什么分图文/视频

xiaohongshu 当前不同内容类型使用不同 Detail Endpoint。

真实路径：

```text
图文
→ data.data[0].note_list[0]

视频
→ data.data[0]
```

Fixture：

- [`xiaohongshu/image_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/image_detail.sanitized.json)
- [`xiaohongshu/video_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/video_detail.sanitized.json)

Search Mapper 能识别内容类型；Decision 需要 Detail 时，生产链选择正确的 Detail Operation。

## 7. 评论能力

当前 Capability：

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

根评论 Canonical：

```text
root_comment_id = external_comment_id
parent_comment_id = null
```

二级回复的 parent 只有 Provider 有明确直接父 ID 时才写，不能根据用户名/数组位置猜。

## 8. 为什么 xiaohongshu 可以做最新评论增量

当前 Capability 明确：

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

## 9. xiaohongshu Raw Replay

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

## 10. 当前备用 family 状态

代码中存在：

```text
App V1 Search Candidate
Web V3 Search Candidate
```

当前不能因为 builder 已存在就写成正式备用或自动 fallback。

验证/切换规则：

[`../appendix/03_TikHub多接口验证与备用策略.md`](../appendix/03_TikHub多接口验证与备用策略.md)

## 11. 要改什么时改哪里

### Search Endpoint/参数变了

```text
operations/xiaohongshu.py
→ Fixture / Real Probe
→ Operation tests
→ capabilities.py（如果业务支持变化）
→ pricing.toml（如果 endpoint identity/price 变化）
→ 本文/TikHub附录
```

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

## 12. 调试顺序

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

数据库 SQL：

[`../appendix/01_PostgreSQL查询与调试实战.md`](../appendix/01_PostgreSQL查询与调试实战.md)
