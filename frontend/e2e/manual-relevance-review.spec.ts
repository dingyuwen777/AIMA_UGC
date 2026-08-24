import { expect, test } from '@playwright/test'

const irrelevantContentId = '42345678-1234-5678-1234-567812345678'
const relevantContentId = '52345678-1234-5678-1234-567812345678'

const irrelevantItem = {
  id: irrelevantContentId,
  platform: 'xiaohongshu',
  external_content_id: 'note-manual-review-irrelevant',
  content_type: 'note',
  title: '爱玛 Q7 误判不相关',
  text: '这条内容被 AI 误判成不相关，需要人工复核。',
  author_display_name: '用户甲',
  published_at: '2026-08-24T01:00:00Z',
  last_seen_at: '2026-08-24T01:10:00Z',
  content_url: 'https://example.com/note-manual-review-irrelevant',
  metrics: { like_count: 10, comment_count: 2, share_count: 1, favorite_count: 3 },
  analysis: {
    status: 'completed',
    relevance: 'irrelevant',
    voice_type: 'media_information',
    sentiment: null,
    labels: [],
    analyzed_at: '2026-08-24T01:20:00Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  source: { provider_name: 'file-import', import_batch_id: null },
}

const relevantItem = {
  ...irrelevantItem,
  id: relevantContentId,
  external_content_id: 'note-manual-review-relevant',
  title: '爱玛 Q7 误判相关',
  text: '这条内容虽然提到了品牌，但人工判断与业务无关。',
  content_url: 'https://example.com/note-manual-review-relevant',
  analysis: {
    ...irrelevantItem.analysis,
    relevance: 'relevant',
    voice_type: 'user_voice',
    sentiment: '中性',
    labels: [{ primary_label: '产品体验', secondary_label: '续航表现' }],
  },
}

async function routeShared(page: import('@playwright/test').Page): Promise<void> {
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configured: true }) })
  })
  await page.route('**/api/v1/data-exports**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
}

test('marks AI irrelevant content as relevant through the explicit decision contract', async ({ page }) => {
  let reviewRequest: unknown
  await routeShared(page)
  await page.route('**/api/v1/contents**', async (route) => {
    const relevance = new URL(route.request().url()).searchParams.get('relevance')
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: relevance === 'irrelevant' ? [irrelevantItem] : [],
        next_cursor: null,
        has_more: false,
      }),
    })
  })
  await page.route('**/api/v1/content-relevance-reviews', async (route) => {
    reviewRequest = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ requested_count: 1, changed_count: 1, unchanged_count: 0 }),
    })
  })

  await page.goto('/voice-plaza')
  await page.getByLabel('AI 相关性').selectOption('irrelevant')
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByRole('button', { name: '人工标记为相关' }).click()

  expect(reviewRequest).toEqual({ content_ids: [irrelevantContentId], decision: 'relevant' })
  await expect(page.getByText(/已人工标记 1 条内容为相关/)).toBeVisible()
})

test('marks AI relevant content as irrelevant from the business-relevant list', async ({ page }) => {
  let reviewRequest: unknown
  await routeShared(page)
  await page.route('**/api/v1/contents**', async (route) => {
    const relevance = new URL(route.request().url()).searchParams.get('relevance')
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: relevance === 'relevant' ? [relevantItem] : [],
        next_cursor: null,
        has_more: false,
      }),
    })
  })
  await page.route('**/api/v1/content-relevance-reviews', async (route) => {
    reviewRequest = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ requested_count: 1, changed_count: 1, unchanged_count: 0 }),
    })
  })

  await page.goto('/voice-plaza')
  await page.getByLabel('AI 相关性').selectOption('relevant')
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByRole('button', { name: '人工标记为不相关' }).click()

  expect(reviewRequest).toEqual({ content_ids: [relevantContentId], decision: 'irrelevant' })
  await expect(page.getByText(/已人工标记 1 条内容为不相关/)).toBeVisible()
})

test('undoes a manual relevant override without deleting the AI irrelevant fact', async ({ page }) => {
  let reviewRequest: unknown
  await routeShared(page)
  await page.route('**/api/v1/contents**', async (route) => {
    const relevance = new URL(route.request().url()).searchParams.get('relevance')
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: relevance === 'relevant' ? [irrelevantItem] : [],
        next_cursor: null,
        has_more: false,
      }),
    })
  })
  await page.route('**/api/v1/content-relevance-reviews', async (route) => {
    reviewRequest = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ requested_count: 1, changed_count: 1, unchanged_count: 0 }),
    })
  })

  await page.goto('/voice-plaza')
  await page.getByLabel('AI 相关性').selectOption('relevant')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText('人工复核相关', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '撤销人工判断' }).click()

  expect(reviewRequest).toEqual({ content_ids: [irrelevantContentId], decision: 'inherit_ai' })
  await expect(page.getByText(/已撤销 1 条人工相关性判断/)).toBeVisible()
})

test('batch marks selected AI relevant content as irrelevant through the same endpoint', async ({ page }) => {
  let reviewRequest: unknown
  await routeShared(page)
  await page.route('**/api/v1/contents**', async (route) => {
    const relevance = new URL(route.request().url()).searchParams.get('relevance')
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: relevance === 'relevant' ? [relevantItem] : [],
        next_cursor: null,
        has_more: false,
      }),
    })
  })
  await page.route('**/api/v1/content-relevance-reviews', async (route) => {
    reviewRequest = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ requested_count: 1, changed_count: 1, unchanged_count: 0 }),
    })
  })

  await page.goto('/voice-plaza')
  await page.getByLabel('AI 相关性').selectOption('relevant')
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByLabel('选择 爱玛 Q7 误判相关').check()
  await page.getByRole('button', { name: '批量标记为不相关' }).click()

  expect(reviewRequest).toEqual({ content_ids: [relevantContentId], decision: 'irrelevant' })
  await expect(page.getByText(/已人工标记 1 条内容为不相关/)).toBeVisible()
})
