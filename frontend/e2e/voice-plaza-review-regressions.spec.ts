import { expect, test, type Page } from './fixture'

import { stubVoicePlazaTaxonomy } from './voicePlazaTaxonomy'

const content = {
  id: '52345678-1234-5678-1234-567812345678',
  platform: 'xiaohongshu',
  external_content_id: 'voice-plaza-review-1',
  content_type: 'note',
  title: '爱玛通勤体验',
  text: '用于 Review 回归测试的稳定内容。',
  author_display_name: '测试用户',
  published_at: '2026-08-29T01:42:00Z',
  last_seen_at: '2026-08-29T02:00:00Z',
  content_url: 'https://example.com/voice-plaza-review-1',
  metrics: {
    like_count: 12,
    comment_count: 3,
    share_count: 1,
    repost_count: null,
    favorite_count: 2,
    play_count: null,
    view_count: 120,
  },
  analysis: {
    status: 'completed',
    relevance: 'relevant',
    voice_type: '真实用户发声',
    sentiment: '中性',
    labels: [{ primary_label: '产品体验', secondary_label: '通勤体验' }],
    analyzed_at: '2026-08-29T02:30:00Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  effective_relevance: 'relevant',
  relevance_source: 'ai',
  source: { provider_name: 'fixture' },
}

/** 固定与当前 Review 风险无关的导出记录和 Analysis 能力响应。 */
async function stubStableAuxiliaryRoutes(page: Page): Promise<void> {
  await stubVoicePlazaTaxonomy(page)
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: true }),
    })
  })
  await page.route('**/api/v1/data-exports**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/data-exports') return route.fallback()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })
}

test('辅助能力失败时保留成功加载的空内容状态', async ({ page }) => {
  await stubStableAuxiliaryRoutes(page)
  await page.unroute('**/api/v1/content-analysis-capabilities')
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        title: 'AI 能力暂不可用',
        status: 503,
        detail: 'AI 能力读取失败，请稍后重试。',
        request_id: 'req_voice_plaza_capability_failure',
        errors: [],
      }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/analysis/content-runs') return route.fallback()
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')

  await expect(page.getByText('声音广场操作失败')).toBeVisible()
  await expect(page.getByText('加载声音广场失败')).toHaveCount(0)
  await expect(page.getByText('暂无符合条件的内容')).toBeVisible()
  await expect(page.getByText('暂时无法加载声音记录')).toHaveCount(0)
  await expect(page.locator('.page-error')).toContainText('req_voice_plaza_capability_failure')
})

test('车型目录响应缺少 items 时显示错误且不中断页面渲染', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await stubStableAuxiliaryRoutes(page)
  await page.route('**/api/v1/vehicle-models**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({}) })
  })
  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/analysis/content-runs') return route.fallback()
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')

  await expect(page.getByText('车型目录响应无效，请稍后重试。')).toBeVisible()
  await expect(page.getByText('暂无符合条件的内容')).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('Failed Analysis Run 在全局任务中心保留后端 error_code', async ({ page }) => {
  await stubStableAuxiliaryRoutes(page)
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [content], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/analysis/content-runs') return route.fallback()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: '62345678-1234-5678-1234-567812345678',
          planner_job_id: '63345678-1234-5678-1234-567812345678',
          sequence_no: 13,
          status: 'failed',
          run_intent: 'manual_reanalysis',
          scope: 'selected',
          target_count: 1,
          shard_count: 1,
          shard_size: 1,
          prompt_version: 'content_labeling_v3',
          prompt_sha256: 'a'.repeat(64),
          taxonomy_sha256: 'b'.repeat(64),
          model_provider: 'openai-compatible',
          model: 'fixture-model',
          generation_config: { temperature: 0 },
          generation_config_hash: 'c'.repeat(64),
          stats: { pending: 0, succeeded: 0, failed: 1, cancelled: 0, stale: 0 },
          shards: [],
          error_code: 'analysis_shard_failed',
          created_at: '2026-08-29T02:00:00Z',
          started_at: '2026-08-29T02:00:01Z',
          finished_at: '2026-08-29T02:00:03Z',
        }],
      }),
    })
  })

  await page.goto('/voice-plaza')

  await expect(page.getByLabel('AI Analysis Run 历史')).toHaveCount(0)
  await page.getByRole('button', { name: /任务中心/ }).click()
  const taskCenter = page.getByRole('complementary', { name: '任务中心' })
  await expect(taskCenter).toBeVisible()
  await expect(taskCenter).toContainText('AI 打标 · Run #13')
  await expect(taskCenter).toContainText('analysis_shard_failed')
})