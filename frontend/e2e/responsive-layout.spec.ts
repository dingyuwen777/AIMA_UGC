import { expect, test, type Page } from './fixture'

const providerId = '44444444-4444-4444-8444-444444444444'

/** 为响应式 Browser Mock 提供采集策略页面最小稳定数据，不复制后端业务规则。 */
async function mockStrategyApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (request.method() === 'GET' && url.pathname === '/api/v1/keyword-packs') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: '11111111-1111-4111-8111-111111111111',
              name: '爱玛品牌词包',
              description: '响应式布局测试',
              enabled: true,
              version: 4,
              keyword_count: 28,
            },
          ],
          total: 1,
          offset: Number(url.searchParams.get('offset') ?? '0'),
          limit: Number(url.searchParams.get('limit') ?? '20'),
        }),
      })
      return
    }

    if (request.method() === 'GET' && url.pathname === '/api/v1/relevance-config') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          keyword_pack_id: '11111111-1111-4111-8111-111111111111',
          keyword_pack_version: 4,
          version: 3,
          effective_keywords: ['爱玛 Q7'],
          updated_at: '2026-09-04T00:00:00Z',
        }),
      })
      return
    }

    if (request.method() === 'GET' && url.pathname === '/api/v1/collection-capabilities') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          provider_configs: [{ id: providerId, provider: 'tikhub', display_name: '主采集渠道' }],
          capabilities: [{
            provider: 'tikhub',
            platform: 'xiaohongshu',
            operations: ['keyword_search'],
            search: {
              supported_sort_modes: ['latest'],
              supported_time_filters: ['1d'],
              supported_duration_filters: [],
              supported_content_types: ['all'],
              manual_default: { sort_mode: 'latest', published_within: '1d', content_type: 'all' },
            },
          }],
        }),
      })
      return
    }

    if (request.method() === 'GET' && url.pathname === '/api/v1/collection-plans') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, enabled_count: 0, offset: 0, limit: 20 }),
      })
      return
    }

    return route.fallback()
  })
}

/** 读取 CSS px 数值，用于验证 fluid typography 的锚点与上限。 */
async function fontSize(page: Page, selector: string): Promise<number> {
  return page.locator(selector).evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))
}

/** 验证当前页面没有被普通布局撑出 viewport。 */
async function expectNoPageHorizontalOverflow(page: Page): Promise<void> {
  const metrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
}

const viewports = [
  { name: 'compact-1180', width: 1180, height: 800 },
  { name: 'compact-1280', width: 1280, height: 800 },
  { name: 'baseline-1440', width: 1440, height: 900 },
  { name: 'large-1600', width: 1600, height: 900 },
  { name: 'wide-1920', width: 1920, height: 1080 },
  { name: 'wide-2560', width: 2560, height: 1440 },
] as const

for (const viewport of viewports) {
  test(`keeps collection strategy usable without page overflow at ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await mockStrategyApi(page)
    await page.goto('/collection-strategy')

    await expect(page.getByRole('heading', { name: '采集策略' })).toBeVisible()
    await page.getByRole('button', { name: '采集计划' }).click()
    await expect(page.locator('.filters')).toBeVisible()
    await expectNoPageHorizontalOverflow(page)

    const shell = await page.locator('.app-shell').boundingBox()
    const workspace = await page.locator('.workspace-main').boundingBox()
    expect(shell?.width).toBeLessThanOrEqual(viewport.width + 1)
    expect(workspace?.width).toBeLessThanOrEqual(viewport.width + 1)

    if (viewport.width <= 1279) {
      const filters = await page.locator('.filters').evaluate((element) => ({
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        height: element.getBoundingClientRect().height,
      }))
      expect(filters.scrollWidth).toBeLessThanOrEqual(filters.clientWidth + 1)
      expect(filters.height).toBeGreaterThan(72)
    }
  })
}

test('anchors typography at 1440 and grows it only within the approved desktop bounds', async ({ page }) => {
  await mockStrategyApi(page)

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/collection-strategy')
  const baselineTitle = await fontSize(page, '.aima-page-header h1')
  expect(baselineTitle).toBeCloseTo(24, 1)

  await page.setViewportSize({ width: 1920, height: 1080 })
  const largeTitle = await fontSize(page, '.aima-page-header h1')
  expect(largeTitle).toBeGreaterThan(baselineTitle)
  expect(largeTitle).toBeLessThanOrEqual(28)

  await page.setViewportSize({ width: 2560, height: 1440 })
  const wideTitle = await fontSize(page, '.aima-page-header h1')
  const workspace = await page.locator('.workspace-main').boundingBox()
  expect(wideTitle).toBeGreaterThanOrEqual(largeTitle)
  expect(wideTitle).toBeLessThanOrEqual(28)
  expect(workspace?.width).toBeLessThan(1900)
  await expectNoPageHorizontalOverflow(page)
})
