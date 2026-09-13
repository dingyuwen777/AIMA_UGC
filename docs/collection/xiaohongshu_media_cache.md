# 小红书图片缓存与声音广场展示

本文记录小红书图文图片从 Detail 事实到服务器可丢弃缓存、声音广场同源展示的当前实现。Provider Endpoint、分页和 Mapper 仍以 [`docs/collection/01_xiaohongshu.md`](01_xiaohongshu.md) 为事实入口；本文不复制 TikHub 协议。

## 1. 数据与缓存边界

小红书 Detail 的 `images_list` 先由现有 Mapper 写入 Canonical / PostgreSQL：

```text
content_media
├─ external_media_id   # fileid 等稳定媒体身份
├─ url                 # Provider 返回的原始 xhscdn / ci.xiaohongshu.com URL
├─ position            # images_list 数组顺序
├─ width
└─ height
```

这些字段是长期媒体事实。服务器缓存只是派生副本：缓存被删除、过期或容量回收时，不删除 `content_media.url` / `external_media_id`，因此可以按源 URL 重建。

缓存绑定表：

```text
content_media_cache_entries
├─ content_id + position
├─ source_url_hash
├─ artifact_id
└─ cached_at
```

缓存字节继续由统一 ArtifactStore 管理，不在 PostgreSQL 存图片 BLOB，也不创建第二套文件存储系统。

## 2. 辅助补采何时缓存

Batch Supplement 的正式 Collection 主链保持：

```text
Detail
→ Content Ingestion
→ Comments
→ SubComments（按用户选择/能力）
→ Scope 得到 succeeded / partial_success
→ best-effort 图片缓存预热
```

只有小红书 `content + content_enrichment` 且 Scope 为 `succeeded` / `partial_success` 时才预热。图片缓存属于非关键派生能力：单张或整次预热失败只记录安全日志，不改变已经完成的 Detail/评论结果，也不触发额外 TikHub 请求。

**预热只是性能优化，不是声音广场显示图片的前置条件。** 历史 Content 没有预热缓存也不需要回填任务；只要 `content_media` 已有小红书图片 URL，首次打开详情就会走 cache miss → 源 URL 下载 → Artifact 缓存 → 返回浏览器。

## 3. 未做辅助补采的帖子怎么显示

“有没有辅助补采评论”和“详情页能不能正常显示”是两个独立维度。

### 3.1 已有媒体事实，但从未预热

```text
content_media.url 已存在
→ 打开声音广场详情
→ 前端使用 AIMA 同源媒体地址
→ cache miss
→ 后端按已保存的源 URL 安全懒缓存
→ 正常显示图片
```

因此 Excel 历史导入、旧 TikHub 数据或从未执行 Batch Supplement 的帖子，只要已有 `content_media`，也可以直接展示图片。

### 3.2 完全没有媒体事实

如果 `Content Detail.media` 为空，详情抽屉不渲染媒体区，不保留 336 px 空白卡片。标题、正文、AI 信息、互动数据和评论状态直接自然上移。

### 3.3 有媒体事实，但源图片临时不可用

源图请求失败、第三方 URL 失效或当前无法安全读取时，内部媒体资源不会把浏览器的破图图标直接暴露给用户，而是返回 AIMA 固定的同源浅灰占位图：

```text
图片暂不可用
帖子正文与评论信息仍可正常查看
```

响应使用 `X-AIMA-Media-State: unavailable`，只短缓存 60 秒；后续重新打开仍可再次尝试按原始媒体 URL 重建。这个占位 SVG 是服务器固定静态内容，不包含用户输入，也不进入业务 OpenAPI/generated client。

### 3.4 从未采集评论

未采集评论不是错误态。声音广场根据当前事实区分：

```text
平台显示评论数 > 0，已采集 = 0
→ “评论尚未采集”
→ 展示平台评论数
→ 提示需要评论分析时再到采集运行中心发起辅助补采

平台显示评论数 = 0
→ “平台当前暂无评论”
→ 明确这不是采集异常

已采集 > 0
→ 按现有 complete / partial / 完整度待确认语义显示

真实加载失败
→ 才进入红色错误态并提供重试
```

正文、已有图片和 AI 信息始终不依赖评论是否已经补采。

相关实现与回归测试：

- [`backend/src/aima_ugc/bootstrap/content_media_http.py`](../../backend/src/aima_ugc/bootstrap/content_media_http.py)
- [`frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue`](../../frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue)
- [`frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentCommentSection.vue`](../../frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentCommentSection.vue)
- [`tests/unit/content/test_content_media_http.py`](../../tests/unit/content/test_content_media_http.py)
- [`frontend/tests/content-comment-section.spec.ts`](../../frontend/tests/content-comment-section.spec.ts)

## 4. 安全下载边界

媒体缓存不是通用 URL Proxy。后端只接受小红书图片 Origin：

```text
*.xhscdn.com
xhscdn.com
ci.xiaohongshu.com
```

并强制：

- 最终请求使用 HTTPS；
- HTTP/HTTPS 端口必须与 scheme 匹配；
- 禁止 userinfo；
- 不跟随 HTTP redirect；
- `trust_env=False`，不继承宿主代理；
- 请求带 `Referer: https://www.xiaohongshu.com/` 和固定 AIMA User-Agent；
- 只接收 AVIF/GIF/JPEG/PNG/WebP 栅格图片，不接收 SVG/HTML；
- 单张图片最大 **10 MiB**，同时检查 `Content-Length` 与实际流式字节数；
- 原始媒体 URL 不写日志。

相关实现：

- [`backend/src/aima_ugc/bootstrap/content_media_cache.py`](../../backend/src/aima_ugc/bootstrap/content_media_cache.py)
- [`tests/unit/content/test_content_media_cache.py`](../../tests/unit/content/test_content_media_cache.py)

## 5. 保留期与容量

媒体缓存 Artifact：

```text
kind = content-media-cache
TTL = 30 天
单张最大 = 10 MiB
容量高水位 = 30 GiB
容量低水位 = 24 GiB
```

现有 Scheduler 每小时执行统一 `run_artifact_cleanup_once()`：

1. 先按 `expires_at` 删除 30 天到期缓存；
2. 再统计仍占实体存储的 `content-media-cache`；
3. 总量不超过 30 GiB 时不做额外容量回收；
4. 超过 30 GiB 时按 Artifact `created_at` 最旧优先删除，目标回落到不高于 24 GiB；
5. 单次容量清理最多处理 10,000 个 Artifact，极端情况下下一个小时继续，避免 housekeeping 长时间独占进程。

删除的是 Artifact 字节和存储状态，不删除 Content 媒体事实；下次读取可以重新缓存。

相关实现：

- [`backend/src/aima_ugc/platform/storage/retention.py`](../../backend/src/aima_ugc/platform/storage/retention.py)
- [`backend/src/aima_ugc/bootstrap/artifact_cleanup.py`](../../backend/src/aima_ugc/bootstrap/artifact_cleanup.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/content_media_cache.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/content_media_cache.py)

## 6. 声音广场展示

声音广场仍通过正式 Content Detail Contract 读取 `media.position/url`，不把二进制图片端点加入 OpenAPI/generated client。

对小红书 `image`，前端把预览地址投影为同源内部资源：

```text
/api/v1/contents/{content_id}/media/{position}
```

该路由：

```text
cache hit  → ArtifactStore 直接返回
cache miss → 安全请求保存的 xhscdn URL → 缓存 → 返回
源不可用  → AIMA 固定浅灰占位图，不暴露浏览器破图
```

原始 `media.url` 不被覆盖，仍可用于溯源/原始媒体链接。

详情抽屉媒体区使用浏览器原生横向滚动和 `scroll-snap`，不引入额外 Carousel/UI Library：

- 单图占满媒体区；
- 多图保留下一张轻微露出，提示左右滑动；
- 触屏、触控板、鼠标横向滚动都使用原生行为；
- 图片 `object-fit: contain`，避免裁掉车型/产品主体；
- 隐藏厚重滚动条，不增加无必要箭头/分页器；
- 没有媒体事实时整个媒体区不出现；
- 图片源失败不影响标题、正文、AI 信息、人工确认和评论。

正式 Figma：`EAPm8KVarUe7BFTSnzvOpT / 4627:7429`。共享 Detail Drawer body Owner 与代码保持一致：610 px Drawer 内使用 336 px 高、FIT、横向可滚动媒体区；未补采/无媒体/媒体不可用/评论未采集状态由同页状态规格说明。

## 7. Migration 与回滚

Migration：

```text
20260913_0052_content_media_cache
```

部署：应用正常发布并执行 Alembic upgrade。Artifact 根目录继续复用既有持久可写挂载，无新增卷。

回滚：

1. 先回滚应用；
2. Alembic downgrade 0052 删除 `content_media_cache_entries`；
3. 已存在 `content-media-cache` Artifact 属于可丢弃字节，可以由 housekeeping 或人工清理；
4. `contents/content_media`、Provider Raw 和评论数据不受影响。
