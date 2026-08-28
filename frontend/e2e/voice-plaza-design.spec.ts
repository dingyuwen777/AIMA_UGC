import { expect, test, type Page } from '@playwright/test'

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

  const sidebar = await page.locator('.sidebar').boundingBox()
  const topbar = await page.locator('.topbar').boundingBox()
  const filters = await page.locator('.filters').boundingBox()
  expect(sidebar?.width).toBe(180)
  expect(topbar?.height).toBe(60)
  expect(filters?.width).toBeGreaterThanOrEqual(1210)
  expect(filters?.width).toBeLessThanOrEqual(1214)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-empty.png', fullPage: true })
  }
})

test('renders the formal loading state while the content request is in flight', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800))
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('正在加载声音记录…')).toBeVisible()
  await expect(page.getByText('正在获取内容列表、AI 状态与运行记录')).toBeVisible()
  await expect(page.locator('.skeleton i')).toHaveCount(3)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-loading.png', fullPage: true })
  }
})

test('renders the formal error banner and recoverable list error state', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'fixture content failure' }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('加载声音广场失败')).toBeVisible()
  await expect(page.getByText('暂时无法加载声音记录')).toBeVisible()
  await expect(page.getByText('检查网络或服务状态后点击“刷新数据”重试。')).toBeVisible()

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-error.png', fullPage: true })
  }
})
