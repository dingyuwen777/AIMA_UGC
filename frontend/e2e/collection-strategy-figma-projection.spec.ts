import { expect, test, type Page } from './fixture'

const packId = '11111111-1111-4111-8111-111111111111'
const planId = '33333333-3333-4333-8333-333333333333'
const providerId = '44444444-4444-4444-8444-444444444444'
const brandId = '88888888-8888-4888-8888-888888888888'

/** 为采集策略 Figma 投影测试提供最小真实 Contract 形状。 */
async function mockStrategyApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/principal') {
      await route.fulfill({ json: { principal_id: 'admin-1', display_name: '爱玛', role: 'administrator', source: 'development', is_administrator: true } })
      return
    }
    if (url.pathname === '/api/v1/notifications') {
      await route.fulfill({ json: { items: [], unread_count: 0 } })
      return
    }
    if (url.pathname === '/api/v1/keyword-packs' && request.method() === 'GET') {
      await route.fulfill({ json: { items: [{ id: packId, name: '爱玛品牌词包', description: '新品车型及用户讨论', enabled: true, version: 4, keyword_count: 28 }], total: 1, offset: 0, limit: Number(url.searchParams.get('limit') ?? '20') } })
      return
    }
    if (url.pathname === `/api/v1/keyword-packs/${packId}`) {
      await route.fulfill({ json: { id: packId, name: '爱玛品牌词包', description: '新品车型及用户讨论', enabled: true, version: 4, keyword_count: 28, keywords: [{ id: 'kw-1', text: '爱玛 Q7', platform_scope: 'all', enabled: true, priority: 100, note: '' }] } })
      return
    }
    if (url.pathname === '/api/v1/vehicle-brands') {
      await route.fulfill({ json: { items: [{ id: brandId, code: 'AIMA', display_name: '爱玛', role: 'owned', status: 'active', version: 1, catalog_version: 18, aliases: [], created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-28T00:00:00Z' }], total: 1, catalog_version: 18, offset: 0, limit: 200 } })
      return
    }
    if (url.pathname === '/api/v1/collection-capabilities') {
      await route.fulfill({ json: {
        provider_configs: [{ id: providerId, provider: 'tikhub', display_name: '主采集渠道' }],
        capabilities: [{ provider: 'tikhub', platform: 'xiaohongshu', operations: ['keyword_search'], search: { supported_sort_modes: ['latest'], supported_time_filters: ['1d'], supported_duration_filters: [], supported_content_types: ['all'], manual_default: { sort_mode: 'latest', published_within: '1d', content_type: 'all' } } }],
      } })
      return
    }
    if (url.pathname === '/api/v1/collection-plans' && request.method() === 'GET') {
      await route.fulfill({ json: { items: [{
        id: planId,
        name: '爱玛新品口碑追踪',
        enabled: true,
        schedule_expr: '0 */6 * * *',
        timezone: 'Asia/Shanghai',
        schedule_version: 3,
        next_run_at: '2026-08-28T01:00:00Z',
        last_scheduled_at: null,
        detail_policy: 'on_change',
        comment_policy: 'adaptive',
        platforms: [{ platform: 'xiaohongshu', provider_config_id: providerId, search_config: { sort_mode: 'latest', published_within: '1d', content_type: 'all' } }],
        keyword_pack_ids: [packId],
        brand_ids: [brandId],
        created_at: '2026-08-21T00:00:00Z',
        updated_at: '2026-08-21T00:00:00Z',
      }], total: 1, enabled_count: 1, offset: 0, limit: 20 } })
      return
    }
    await route.fulfill({ status: 404, body: 'not mocked' })
  })
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockStrategyApi(page)
})

test('uses the current Figma business projection without leaking Provider details', async ({ page }) => {
  await page.goto('/collection-strategy')

  await expect(page.locator('.summary-item')).toHaveCount(3)
  await expect(page.getByText('1 个品牌', { exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '目标平台', exact: true })).toBeVisible()
  await expect(page.locator('.plan-table tbody tr').first()).toContainText('1 个关键词包 · 1 个平台')
  await expect(page.locator('.plan-table tbody tr').first()).toContainText('小红书')
  await expect(page.locator('.plan-table tbody tr').first()).not.toContainText('主采集渠道')

  await page.locator('.plan-table tbody tr').first().getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '采集计划详情' })
  await expect(detail.getByText('计划规则与执行范围', { exact: true })).toBeVisible()
  await expect(detail.getByText('主采集渠道', { exact: false })).toBeHidden()
  await expect(detail.getByText('小红书', { exact: true })).toBeVisible()
})

test('wraps the keyword detail card below the list at the compact 1180 viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 1080 })
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包', exact: true }).click()

  const listBox = await page.locator('.table-card').boundingBox()
  const detailBox = await page.locator('.detail-card').boundingBox()
  expect(listBox).not.toBeNull()
  expect(detailBox).not.toBeNull()
  expect(detailBox!.y).toBeGreaterThan(listBox!.y + listBox!.height)
  expect(detailBox!.x + detailBox!.width).toBeLessThanOrEqual(1157)
})
