import { expect, test, type Page } from './fixture'

import { stubVoicePlazaTaxonomy } from './voicePlazaTaxonomy'

const contentId = '78345678-1234-5678-1234-567812345678'
const content = {
  id: contentId,
  platform: 'xiaohongshu',
  external_content_id: 'voice-plaza-media-carousel-1',
  content_type: 'note',
  title: '爱玛多图内容',
  text: '用于验证普通鼠标也能逐张查看缓存图片。',
  author_display_name: '测试用户',
  published_at: '2026-09-14T01:00:00Z',
  last_seen_at: '2026-09-14T02:00:00Z',
  content_url: 'https://www.xiaohongshu.com/explore/voice-plaza-media-carousel-1',
  metrics: {
    like_count: 18,
    comment_count: 0,
    share_count: 2,
    repost_count: null,
    favorite_count: 6,
    play_count: null,
    view_count: null,
  },
  analysis: {
    status: 'pending',
    relevance: null,
    voice_type: null,
    sentiment: null,
    labels: [],
    analyzed_at: null,
    model_provider: null,
    model: null,
  },
  effective_relevance: null,
  relevance_source: 'unreviewed',
  source: { provider_name: 'fixture' },
}

/** 固定声音广场和详情公开入口所需的最小 Contract 响应。 */
async function stubVoicePlazaRoutes(page: Page): Promise<void> {
  await stubVoicePlazaTaxonomy(page)
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ json: { configured: true } })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === `/api/v1/contents/${contentId}/comments`) {
      await route.fulfill({
        json: { items: [], next_cursor: null, has_more: false, total_count: 0, ingested_total_count: 0 },
      })
      return
    }
    if (path.startsWith(`/api/v1/contents/${contentId}/media/`)) {
      await route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect width="640" height="480" fill="#eef2f6"/></svg>',
      })
      return
    }
    if (path === `/api/v1/contents/${contentId}`) {
      await route.fulfill({
        json: {
          ...content,
          media: [0, 1, 2].map((position) => ({
            position,
            media_type: 'image',
            url: `https://sns-i11.rednotecdn.com/image-${position}`,
            preview_url: null,
            alt_text: `图片 ${position + 1}`,
          })),
          comments: [],
          source_records: [content.source],
          supplement_status: null,
          vehicles: [],
          brands: [],
        },
      })
      return
    }
    await route.fulfill({ json: { items: [content], next_cursor: null, has_more: false } })
  })
}

test.use({ viewport: { width: 1440, height: 900 } })

test('普通鼠标可通过左右按钮逐张查看全部缓存图片', async ({ page }) => {
  await stubVoicePlazaRoutes(page)

  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '查看详情' }).click()

  const drawer = page.getByRole('dialog', { name: '内容详情' })
  const gallery = drawer.locator('.media-grid')
  const previous = drawer.getByRole('button', { name: '上一张图片' })
  const next = drawer.getByRole('button', { name: '下一张图片' })
  const position = drawer.getByText(/\d \/ 3/)

  await expect(drawer).toBeVisible()
  await expect(position).toHaveText('1 / 3')
  await expect(previous).toBeDisabled()
  await expect(next).toBeEnabled()

  await next.click()
  await expect(position).toHaveText('2 / 3')
  await expect.poll(() => gallery.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0)

  await next.click()
  await expect(position).toHaveText('3 / 3')
  await expect(next).toBeDisabled()

  await previous.click()
  await expect(position).toHaveText('2 / 3')

  await gallery.evaluate((node) => { node.scrollLeft = 0; node.dispatchEvent(new Event('scroll')) })
  await expect(position).toHaveText('1 / 3')
  await expect(previous).toBeDisabled()
})
