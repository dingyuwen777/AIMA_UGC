import { expect, test, type Page } from '@playwright/test'

const contentId = '42345678-1234-5678-1234-567812345678'
const content = {
  id: contentId,
  platform: 'xiaohongshu',
  external_content_id: 'voice-plaza-figma-1',
  content_type: 'note',
  title: '爱玛 Q7 的坐垫舒适，但续航仍有提升空间',
  text: '日常通勤约 12 公里，坐垫很舒服，希望后续优化低温续航。',
  author_display_name: '测试用户',
  published_at: '2026-08-29T01:42:00Z',
  last_seen_at: '2026-08-29T02:00:00Z',
  content_url: 'https://example.com/voice-plaza-figma-1',
  metrics: {
    like_count: 128,
    comment_count: 18,
    share_count: 6,
    repost_count: null,
    favorite_count: 32,
    play_count: null,
    view_count: 1284,
  },
  analysis: {
    status: 'completed',
    relevance: 'relevant',
    voice_type: '真实用户发声',
    sentiment: '负面',
    labels: [{ primary_label: '产品体验', secondary_label: '续航表现' }],
    analyzed_at: '2026-08-29T02:30:00Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  effective_relevance: 'relevant',
  relevance_source: 'ai',
  source: { provider_name: 'fixture' },
}

test.use({ viewport: { width: 1440, height: 900 } })

/** 为 Design-to-Code 状态测试固定与目标状态无关的能力、Run 和 Export 只读响应。 */
async function stubCommonRoutes(page: Page): Promise<void> {
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: true }),
    })
  })

  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/analysis/content-runs') return route.fallback()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
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

/** 允许 1px 浏览器布局取整误差地核对 Figma 的正式关键尺寸。 */
function expectNear(actual: number | undefined, expected: number): void {
  expect(actual).toBeDefined()
  expect(Math.abs((actual ?? 0) - expected)).toBeLessThanOrEqual(1)
}

test.beforeEach(async ({ page }) => {
  await stubCommonRoutes(page)
})

test('matches the formal 1440 desktop shell and empty-state composition', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('暂无符合条件的内容')).toBeVisible()
  await expect(page.getByText('当前没有可加载的下一页，不显示虚构页码。')).toBeVisible()
  await expect(page.getByText('游标分页不会虚构总页数')).toHaveCount(0)
  await expect(page.getByText('标题内容', { exact: true })).toHaveCount(0)

  const sidebar = await page.locator('.sidebar').boundingBox()
  const topbar = await page.locator('.topbar').boundingBox()
  const filters = await page.locator('.filters').boundingBox()
  expectNear(sidebar?.width, 180)
  expectNear(topbar?.height, 60)
  expectNear(filters?.width, 1212)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-empty.png', fullPage: true })
  }
})

test('renders the formal loading state while the content request is in flight', async ({ page }) => {
  let releaseContents!: () => void
  const contentRelease = new Promise<void>((resolve) => {
    releaseContents = resolve
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await contentRelease
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('正在加载声音记录…')).toBeVisible()
  await expect(page.getByText('正在获取内容列表、AI 状态与运行记录')).toBeVisible()
  await expect(page.locator('.skeleton')).toHaveCount(3)
  await expect(page.getByText('标题内容', { exact: true })).toHaveCount(0)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-loading.png', fullPage: true })
  }

  releaseContents()
  await expect(page.getByText('暂无符合条件的内容')).toBeVisible()
})

test('renders the formal error banner and recoverable list error state', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        title: '声音广场暂不可用',
        status: 503,
        detail: '内容列表服务暂不可用，请使用 request_id 联系管理员。',
        request_id: 'req_voice_plaza_figma_error',
        errors: [],
      }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('加载声音广场失败')).toBeVisible()
  await expect(page.getByText('暂时无法加载声音记录')).toBeVisible()
  await expect(page.getByText('检查网络或服务状态后点击“刷新数据”重试。')).toBeVisible()
  await expect(page.locator('.page-error')).toContainText('req_voice_plaza_figma_error')
  await expect(page.getByText('标题内容', { exact: true })).toHaveCount(0)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-error.png', fullPage: true })
  }
})

test('matches the formal detail, analysis and export overlay geometry', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === `/api/v1/contents/${contentId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...content,
          media: [],
          comments: [],
          comment_coverage: null,
          source_records: [content.source],
          supplement_status: null,
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [content], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
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
        configuration_hash: 'd'.repeat(64),
        cost_estimate_available: false,
        cost_estimate_note: '仅在确认创建后产生实际模型调用。',
      }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByRole('button', { name: '查看详情' })).toBeVisible()

  await page.getByRole('button', { name: '查看详情' }).click()
  const drawer = page.getByRole('complementary', { name: '内容详情' })
  await expect(drawer).toBeVisible()
  const drawerBox = await drawer.boundingBox()
  expectNear(drawerBox?.width, 610)
  expectNear(drawerBox?.height, 900)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-detail.png', fullPage: true })
  }
  await drawer.getByRole('button', { name: '关闭' }).click()

  await page.getByLabel('选择当前已加载内容').check()
  const analysisButton = page.getByRole('button', { name: 'AI 打标' })
  await expect(analysisButton).toBeEnabled()
  await analysisButton.click()
  const analysisDialog = page.getByRole('dialog', { name: '创建 AI Analysis Run' })
  await expect(analysisDialog).toBeVisible()
  await expect(analysisDialog.getByText('预检目标 1 条，拆分 1 个 Shard')).toBeVisible()
  const analysisBox = await analysisDialog.boundingBox()
  expectNear(analysisBox?.width, 540)
  expectNear(analysisBox?.height, 446)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-analysis.png', fullPage: true })
  }
  await analysisDialog.locator('.close-button').click()

  await page.getByRole('button', { name: '导出记录' }).click()
  const exportDialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect(exportDialog).toBeVisible()
  const exportBox = await exportDialog.boundingBox()
  expectNear(exportBox?.width, 650)
  expectNear(exportBox?.height, 690)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-export.png', fullPage: true })
  }
})
