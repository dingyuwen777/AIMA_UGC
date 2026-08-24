import { expect, test } from '@playwright/test'

const contentId = '42345678-1234-5678-1234-567812345678'

const irrelevantItem = {
  id: contentId,
  platform: 'xiaohongshu',
  external_content_id: 'note-manual-review-1',
  content_type: 'note',
  title: '爱玛 Q7 真实体验',
  text: '这条内容被 AI 误判成不相关，需要人工复核。',
  author_display_name: '用户甲',
  published_at: '2026-08-24T01:00:00Z',
  last_seen_at: '2026-08-24T01:10:00Z',
  content_url: 'https://example.com/note-manual-review-1',
  metrics: { like_count: 10, comment_count: 2, share_count: 1, favorite_count: 3 },
  analysis: {
    status: 'completed',
    relevance: 'irrelevant',
    effective_relevance: 'irrelevant',
    relevance_source: 'ai',
    voice_type: 'media_information',
    sentiment: null,
    labels: [],
    analyzed_at: '2026-08-24T01:20:00Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  source: { provider_name: 'file-import', import_batch_id: null },
}

test('filters AI irrelevant content and supports single manual include', async ({ page }) => {
  let reviewed = false
  let reviewRequest: unknown
  const listRequests: string[] = []

  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configured: true }) })
  })
  await page.route('**/api/v1/data-exports**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    const url = new URL(route.request().url())
    listRequests.push(url.toString())
    const asksIrrelevant = url.searchParams.get('relevance') === 'irrelevant'
    const body = asksIrrelevant && !reviewed
      ? { items: [irrelevantItem], next_cursor: null, has_more: false }
      : { items: [], next_cursor: null, has_more: false }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.route('**/api/v1/content-relevance-reviews', async (route) => {
    reviewRequest = route.request().postDataJSON()
    reviewed = true
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ requested_count: 1, reviewed_count: 1, already_reviewed_count: 0 }),
    })
  })

  await page.goto('/voice-plaza')
  await page.getByLabel('AI 相关性').selectOption('irrelevant')
  await page.getByRole('button', { name: '查询' }).click()

  await expect(page.getByText('AI 判定不相关')).toBeVisible()
  await page.getByRole('button', { name: '人工标记为相关' }).click()

  expect(reviewRequest).toEqual({ content_ids: [contentId] })
  await expect(page.getByText(/已人工标记 1 条内容为相关/)).toBeVisible()
  await expect(page.getByText('爱玛 Q7 真实体验')).toHaveCount(0)
  expect(listRequests.some((value) => new URL(value).searchParams.get('relevance') === 'irrelevant')).toBe(true)
})

test('batch reviews selected irrelevant content through the same endpoint', async ({ page }) => {
  let reviewRequest: unknown

  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configured: true }) })
  })
  await page.route('**/api/v1/data-exports**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [irrelevantItem], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/content-relevance-reviews', async (route) => {
    reviewRequest = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ requested_count: 1, reviewed_count: 1, already_reviewed_count: 0 }),
    })
  })

  await page.goto('/voice-plaza')
  await page.getByLabel('AI 相关性').selectOption('irrelevant')
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByLabel('选择 爱玛 Q7 真实体验').check()
  await page.getByRole('button', { name: '批量标记为相关' }).click()

  expect(reviewRequest).toEqual({ content_ids: [contentId] })
  await expect(page.getByText(/已人工标记 1 条内容为相关/)).toBeVisible()
})
