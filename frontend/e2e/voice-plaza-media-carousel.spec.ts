import { expect, test, type Page } from './fixture'

import { stubVoicePlazaTaxonomy } from './voicePlazaTaxonomy'
import type { ContentMediaPlaybackResponse, ContentMediaResponse } from '../src/generated/api/client'

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
async function stubVoicePlazaRoutes(page: Page, media: ContentMediaResponse[] = [0, 1, 2].map((position) => ({
  position,
  media_type: 'image',
  url: `https://sns-i11.rednotecdn.com/image-${position}`,
  preview_url: null,
  alt_text: `图片 ${position + 1}`,
}))): Promise<void> {
  const currentContent = { ...content, content_type: media.some((entry) => entry.media_type === 'video') ? 'video' : 'note' }
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
      const position = Number(path.split('/').at(-1))
      const [width, height] = position === 1 ? [480, 1200] : position === 2 ? [480, 4800] : [1200, 480]
      await route.fulfill({
        contentType: 'image/svg+xml',
        body: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="${width}" height="${height}" fill="#eef2f6"/></svg>`,
      })
      return
    }
    if (path === `/api/v1/contents/${contentId}`) {
      await route.fulfill({
        json: {
          ...currentContent,
          media,
          comments: [],
          source_records: [content.source],
          supplement_status: null,
          vehicles: [],
          brands: [],
        },
      })
      return
    }
    await route.fulfill({ json: { items: [currentContent], next_cursor: null, has_more: false } })
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

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/xiaohongshu-media-carousel-navigation.png', fullPage: true })
  }

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

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 740 }]) {
  test(`横图竖图长图完整显示且切换不跳动 ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await stubVoicePlazaRoutes(page)
    await page.goto('/voice-plaza')
    await page.getByRole('button', { name: '查看详情' }).click()
    const drawer = page.getByRole('dialog', { name: '内容详情' })
    const gallery = drawer.locator('.media-grid')
    const height = (await gallery.boundingBox())!.height
    const geometry: Array<Record<string, unknown>> = []
    for (let index = 0; index < 3; index += 1) {
      const image = gallery.locator('img').nth(index)
      await expect(image).toHaveCSS('object-fit', 'contain')
      await expect.poll(() => image.evaluate((element) => element.naturalWidth)).toBeGreaterThan(0)
      const box = await image.boundingBox()
      geometry.push({ index, box, source: await image.evaluate((element) => ({ width: element.naturalWidth, height: element.naturalHeight })), objectFit: await image.evaluate((element) => getComputedStyle(element).objectFit) })
      expect(box!.height).toBeLessThanOrEqual(viewport.height * .5)
      expect(box!.width).toBeLessThanOrEqual(viewport.width)
      expect((await gallery.boundingBox())!.height).toBeCloseTo(height, 0)
      await expect(gallery.getByRole('link').nth(index)).toHaveAttribute('href', `/api/v1/contents/${contentId}/media/${index}`)
      if (index < 2) await drawer.getByRole('button', { name: '下一张图片' }).click()
    }
    expect(await drawer.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
    await expect(drawer.getByText('3 / 3', { exact: true })).toBeVisible()
    await test.info().attach('media-geometry', { body: JSON.stringify({ viewport, galleryHeight: height, geometry }, null, 2), contentType: 'application/json' })
    if (process.env.AIMA_CAPTURE_VISUAL === '1') {
      await page.screenshot({ path: test.info().outputPath(`media-contained-${viewport.width}.png`) })
    }
  })
}

/** 播放响应严格采用生成 Client 的 Contract，测试只替换网络边界。 */
function playbackResponse(overrides: Partial<ContentMediaPlaybackResponse> = {}): ContentMediaPlaybackResponse {
  return {
    content_id: contentId,
    position: 0,
    status: 'ready',
    generation: 1,
    source_revision: 'a'.repeat(64),
    stream_url: `/api/v1/contents/${contentId}/media/0/playback/stream?session=fixture`,
    ...overrides,
  }
}

test('无URL视频显示标识与时长，点击才准备，原生控件不自动下载，关闭释放src', async ({ page }) => {
  await stubVoicePlazaRoutes(page, [{ position: 0, media_type: 'video', url: null, preview_url: null, duration_ms: 65000 }])
  let prepares = 0
  let streamRequests = 0
  await page.route('**/playback/prepare', async (route) => {
    prepares += 1
    await route.fulfill({ json: playbackResponse() })
  })
  page.on('request', (request) => { if (request.url().includes('/playback/stream')) streamRequests += 1 })
  await page.goto('/voice-plaza')
  await expect(page.getByLabel('视频内容')).toBeVisible()
  await page.getByRole('button', { name: '查看详情' }).click()
  const drawer = page.getByRole('dialog', { name: '内容详情' })
  await expect(drawer.getByText('视频 · 1:05', { exact: true })).toBeVisible()
  expect(prepares).toBe(0)
  await expect(drawer.locator('video')).toHaveCount(0)
  await drawer.getByRole('button', { name: '准备播放视频' }).click()
  const video = drawer.locator('video')
  await expect(video).toHaveAttribute('controls', '')
  await expect(video).toHaveAttribute('preload', 'none')
  await expect(video).not.toHaveAttribute('autoplay')
  expect(prepares).toBe(1)
  expect(streamRequests).toBe(0)
  await video.evaluate((element) => { (window as unknown as { closedMedia: HTMLVideoElement }).closedMedia = element })
  await drawer.getByRole('button', { name: '关闭', exact: true }).click()
  expect(await page.evaluate(() => (window as unknown as { closedMedia: HTMLVideoElement }).closedMedia.getAttribute('src'))).toBeNull()
})

test('准备中可继续阅读和编辑，关闭停止只读观察且不取消共享任务', async ({ page }) => {
  await stubVoicePlazaRoutes(page, [{ position: 0, media_type: 'video', url: null, preview_url: 'https://sns-i11.rednotecdn.com/cover', duration_ms: 65000 }])
  let polls = 0
  let cancels = 0
  let initialPrepares = 0
  let importJobQueries = 0
  const jobId = '10000000-0000-4000-8000-000000000001'
  await page.route('**/playback/prepare', async (route) => {
    const body = route.request().postDataJSON()
    if (body.observed_job_id) {
      expect(body).toEqual({ observed_job_id: jobId })
      polls += 1
    } else {
      expect(body).toEqual({})
      initialPrepares += 1
    }
    await route.fulfill({ json: playbackResponse({ status: 'preparing', stream_url: null, job_id: jobId }) })
  })
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/cancel')) cancels += 1
    if (request.method() === 'GET' && /\/api\/v1\/jobs\//.test(request.url())) importJobQueries += 1
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '查看详情' }).click()
  const drawer = page.getByRole('dialog', { name: '内容详情' })
  await drawer.getByRole('button', { name: '准备播放视频' }).click()
  await expect(drawer.getByRole('button', { name: '正在准备视频' })).toBeDisabled()
  await expect(drawer.getByText(content.text, { exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '修改车型' }).click()
  await expect(drawer.getByText('车型人工确认', { exact: true })).toBeVisible()
  await expect.poll(() => polls).toBeGreaterThan(0)
  await drawer.getByRole('button', { name: '关闭', exact: true }).click()
  const finalPolls = polls
  await page.clock.install()
  await page.clock.fastForward(5000)
  expect(polls).toBe(finalPolls)
  expect(initialPrepares).toBe(1)
  expect(importJobQueries).toBe(0)
  expect(cancels).toBe(0)
})

test('只读观察成功直接显示原生播放器，不经过Import Job查询或再次空prepare', async ({ page }) => {
  await stubVoicePlazaRoutes(page, [{ position: 0, media_type: 'video', url: null, preview_url: 'https://sns-i11.rednotecdn.com/cover', duration_ms: 65000 }])
  const jobId = '10000000-0000-4000-8000-000000000001'
  const bodies: unknown[] = []
  let importJobQueries = 0
  await page.route('**/playback/prepare', async (route) => {
    const body = route.request().postDataJSON()
    bodies.push(body)
    await route.fulfill({ json: bodies.length === 1
      ? playbackResponse({ status: 'preparing', stream_url: null, job_id: jobId })
      : playbackResponse() })
  })
  page.on('request', (request) => {
    if (request.method() === 'GET' && /\/api\/v1\/jobs\//.test(request.url())) importJobQueries += 1
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '查看详情' }).click()
  const drawer = page.getByRole('dialog', { name: '内容详情' })
  await drawer.getByRole('button', { name: '准备播放视频' }).click()
  await expect(drawer.getByRole('button', { name: '正在准备视频' })).toBeDisabled()
  const video = drawer.getByLabel('内容视频播放器')
  await expect(video).toHaveAttribute('src', playbackResponse().stream_url!)
  await expect(video).toHaveAttribute('controls', '')
  await expect(video).toHaveAttribute('preload', 'none')
  await expect(video).not.toHaveAttribute('autoplay')
  expect(bodies).toEqual([{}, { observed_job_id: jobId }])
  expect(importJobQueries).toBe(0)
  await drawer.getByRole('button', { name: '关闭', exact: true }).click()
})
