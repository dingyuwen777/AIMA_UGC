import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'

import type { ContentDetailResponse } from '../src/generated/api/client'
import ContentDetailDrawer from '../src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue'

const baseItem = {
  id: '01991f80-6d5d-7dc8-95cb-c67c12345678',
  platform: 'xiaohongshu',
  external_content_id: 'note-1',
  content_type: 'note',
  title: '爱玛测试内容',
  text: '这是 Excel 已导入并保留的原始内容。',
  published_at: '2026-08-21T01:00:00Z',
  last_seen_at: '2026-08-21T02:00:00Z',
  content_url: 'https://www.xiaohongshu.com/explore/note-1',
  metrics: {},
  analysis: { status: 'pending', labels: [] },
  source: { provider_name: 'file_import' },
  media: [],
  comments: [],
  source_records: [],
} as unknown as ContentDetailResponse

async function render(item: ContentDetailResponse): Promise<string> {
  return renderToString(
    createSSRApp({
      render: () => h(ContentDetailDrawer, { modelValue: true, item, loading: false }),
    }),
  )
}

describe('content supplement status', () => {
  it('describes a failed supplement without claiming the imported content is unviewable', async () => {
    const item = {
      ...baseItem,
      supplement_status: {
        run_id: '01991f80-6d5d-7dc8-95cb-c67c12345679',
        status: 'failed',
        stop_reason: 'provider_http_500',
        updated_at: '2026-08-22T12:00:00Z',
      },
    } as unknown as ContentDetailResponse

    const html = await render(item)

    expect(html).toContain('内容补充失败')
    expect(html).toContain('暂时无法获取完整详情与评论')
    expect(html).toContain('已保留原始导入内容')
    expect(html).toContain('采集中心')
    expect(html).not.toContain('TikHub补采失败')
    expect(html).not.toContain('内容无法浏览')
  })

  it('does not show a failure warning after the latest supplement succeeded', async () => {
    const item = {
      ...baseItem,
      supplement_status: {
        run_id: '01991f80-6d5d-7dc8-95cb-c67c12345679',
        status: 'succeeded',
        stop_reason: null,
        updated_at: '2026-08-22T12:00:00Z',
      },
    } as unknown as ContentDetailResponse

    const html = await render(item)

    expect(html).not.toContain('内容补充失败')
    expect(html).not.toContain('内容补充不完整')
  })
})
