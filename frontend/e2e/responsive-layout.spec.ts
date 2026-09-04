import { expect, test, type Page } from './fixture'

import { stubVoicePlazaTaxonomy } from './voicePlazaTaxonomy'

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

/** 为声音广场窄桌面验收提供最小只读响应，业务状态仍使用正式页面入口。 */
async function mockVoicePlazaApi(page: Page): Promise<void> {
  await stubVoicePlazaTaxonomy(page)
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: true }),
    })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })
}

/** 为采集运行中心响应式验收补充当前首页所需的 KPI 摘要。 */
async function mockRuntimeApi(page: Page): Promise<void> {
  await page.route('**/api/v1/collection-runtime/summary', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        processing_count: 0,
        completed_today_count: 0,
        contents_ingested_today: 0,
        as_of: '2026-09-04T00:00:00Z',
      }),
    })
  })
}

/** 为管理员页面初始 Tab 提供最小目录响应，避免把响应式测试变成业务 Fixture 镜像。 */
async function mockAdminApi(page: Page): Promise<void> {
  await page.route('**/api/v1/keyword-packs**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, offset: 0, limit: 100 }),
    })
  })
  await page.route('**/api/v1/analysis-schemes', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/audit-events**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, offset: 0, limit: 100 }),
    })
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

/** 验证 AppShell 与真实内容区都被约束在当前 viewport 内。 */
async function expectWorkspaceInsideViewport(page: Page, viewportWidth: number): Promise<void> {
  const shell = await page.locator('.app-shell').boundingBox()
  const workspace = await page.locator('.workspace-main').boundingBox()
  expect(shell).not.toBeNull()
  expect(workspace).not.toBeNull()
  expect((shell?.x ?? 0) + (shell?.width ?? 0)).toBeLessThanOrEqual(viewportWidth + 1)
  expect((workspace?.x ?? 0) + (workspace?.width ?? 0)).toBeLessThanOrEqual(viewportWidth + 1)
  await expectNoPageHorizontalOverflow(page)
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
    await expectWorkspaceInsideViewport(page, viewport.width)

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

test('keeps voice plaza readable and bounded on compact desktop', async ({ page }) => {
  const viewport = { width: 1180, height: 800 }
  await page.setViewportSize(viewport)
  await mockVoicePlazaApi(page)
  await page.goto('/voice-plaza')

  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()
  await expect(page.getByText('暂无符合条件的内容')).toBeVisible()
  await expectWorkspaceInsideViewport(page, viewport.width)
  const filters = await page.locator('.filters').evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }))
  expect(filters.scrollWidth).toBeLessThanOrEqual(filters.clientWidth + 1)
  expect(await fontSize(page, '.filters .field')).toBeGreaterThanOrEqual(12)
})

test('keeps collection runtime bounded on compact desktop', async ({ page }) => {
  const viewport = { width: 1180, height: 800 }
  await page.setViewportSize(viewport)
  await mockRuntimeApi(page)
  await page.goto('/collection-runtime')

  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await expectWorkspaceInsideViewport(page, viewport.width)
  await expect(page.locator('.runtime-tabs')).toBeVisible()
})

test('keeps administrator configuration bounded on compact desktop', async ({ page }) => {
  const viewport = { width: 1180, height: 800 }
  await page.setViewportSize(viewport)
  await mockAdminApi(page)
  await page.goto('/admin/configuration')

  await expect(page.getByRole('heading', { name: '管理员配置' })).toBeVisible()
  await expectWorkspaceInsideViewport(page, viewport.width)
  await expect(page.getByRole('navigation', { name: '管理员配置分类' })).toBeVisible()
})

test('constrains a real dialog to the viewport safe margin in a narrow window', async ({ page }) => {
  const viewport = { width: 560, height: 800 }
  await page.setViewportSize(viewport)
  await mockStrategyApi(page)
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包' }).click()
  await page.locator('.table-head').getByRole('button', { name: /新建词包/ }).click()

  const dialog = page.getByRole('dialog', { name: '新建关键词包' })
  await expect(dialog).toBeVisible()
  const box = await dialog.boundingBox()
  expect(box).not.toBeNull()
  expect(box?.x).toBeGreaterThanOrEqual(15)
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(viewport.width - 15)
})

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