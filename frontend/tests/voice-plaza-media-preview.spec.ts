import { describe, expect, it } from 'vitest'

import type { ContentDetailResponse } from '../src/generated/api/client'
import { withLocalMediaPreview } from '../src/features/voice-plaza/api'

function detail(
  platform: string,
  media: ContentDetailResponse['media'],
): ContentDetailResponse {
  return {
    id: '01991f80-6d5d-7dc8-95cb-c67c12345670',
    platform,
    media,
  } as ContentDetailResponse
}

describe('voice plaza media preview projection', () => {
  it('小红书图片与视频封面使用同源缓存，保留可准备的视频身份', () => {
    const original = detail('xiaohongshu', [
      {
        position: 0,
        media_type: 'image',
        url: 'https://sns-img-bd.xhscdn.com/image-0',
        preview_url: 'https://sns-img-bd.xhscdn.com/preview-0',
      },
      {
        position: 1,
        media_type: 'image',
        url: null,
        preview_url: null,
      },
      {
        position: 2,
        media_type: 'video',
        url: 'https://example.invalid/video',
        preview_url: 'https://example.invalid/cover',
      },
      {
        position: 3,
        media_type: 'image',
        url: null,
        preview_url: 'https://example.invalid/existing-preview',
      },
    ])

    const projected = withLocalMediaPreview(original)

    expect(projected.media).toHaveLength(3)
    expect(projected.media?.[0]?.preview_url).toBe(
      `/api/v1/contents/${original.id}/media/0`,
    )
    expect(projected.media?.[0]?.url).toBe('https://sns-img-bd.xhscdn.com/image-0')
    expect(projected.media?.some((media) => media.position === 1)).toBe(false)
    expect(projected.media?.[1]?.preview_url).toBe(`/api/v1/contents/${original.id}/media/2`)
    expect(projected.media?.[2]?.preview_url).toBe('https://example.invalid/existing-preview')
    expect(projected.media?.[2]?.url).toBeNull()
  })

  it('没有播放地址或封面的视频也保留，避免将视频笔记伪装成无媒体', () => {
    const original = detail('xiaohongshu', [
      { position: 0, media_type: 'video', url: null, preview_url: null, duration_ms: 65000 },
    ])
    expect(withLocalMediaPreview(original).media).toEqual(original.media)
  })

  it.each(['douyin', 'weibo', 'bilibili', 'kuaishou'])('%s 保持原媒体地址不变', (platform) => {
    const original = detail(platform, [
      {
        position: 0,
        media_type: 'image',
        url: 'https://example.invalid/image',
        preview_url: 'https://example.invalid/preview',
      },
    ])

    expect(withLocalMediaPreview(original)).toBe(original)
  })
})
