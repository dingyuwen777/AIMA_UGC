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

历史 Content 没有预热缓存也不需要回填任务。声音广场首次读取图片时可以 cache miss → 源 URL 下载 → Artifact 缓存 → 返回浏览器。

## 3. 安全下载边界

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

## 4. 保留期与容量

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

## 5. 声音广场展示

声音广场仍通过正式 Content Detail Contract 读取 `media.position/url`，不把二进制图片端点加入 OpenAPI/generated client。

对小红书 `image`，前端把预览地址投影为同源内部资源：

```text
/api/v1/contents/{content_id}/media/{position}
```

该路由：

```text
cache hit  → ArtifactStore 直接返回
cache miss → 安全请求保存的 xhscdn URL → 缓存 → 返回
```

原始 `media.url` 不被覆盖，仍可用于溯源/原始媒体链接。

详情抽屉媒体区使用浏览器原生横向滚动和 `scroll-snap`，不引入额外 Carousel/UI Library：

- 单图占满媒体区；
- 多图保留下一张轻微露出，提示左右滑动；
- 触屏、触控板、鼠标横向滚动都使用原生行为；
- 图片 `object-fit: contain`，避免裁掉车型/产品主体；
- 隐藏厚重滚动条，不增加无必要箭头/分页器；
- 图片失败不影响标题、正文、AI 信息、人工确认和评论。

正式 Figma：`EAPm8KVarUe7BFTSnzvOpT / 4627:7429`。共享 Detail Drawer body Owner 与代码保持一致：610 px Drawer 内使用 336 px 高、FIT、横向可滚动媒体区。

## 6. Migration 与回滚

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
