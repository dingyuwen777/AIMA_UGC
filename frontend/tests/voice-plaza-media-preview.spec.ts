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
  it('小红书只投影有源 URL 的图片，并过滤完全不可展示的媒体', () => {
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
    expect(projected.media?.[1]?.preview_url).toBe('https://example.invalid/cover')
    expect(projected.media?.[2]?.preview_url).toBe('https://example.invalid/existing-preview')
    expect(projected.media?.[2]?.url).toBeNull()
  })

  it('其它平台保持原媒体地址不变', () => {
    const original = detail('douyin', [
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
