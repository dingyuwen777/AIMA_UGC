import { expect, test, type Locator, type Page } from '@playwright/test'

const packId = '11111111-1111-4111-8111-111111111111'
const relevancePackId = '22222222-2222-4222-8222-222222222222'
const planId = '33333333-3333-4333-8333-333333333333'
const providerId = '44444444-4444-4444-8444-444444444444'
const historicalVehicleId = '66666666-6666-4666-8666-666666666666'
const activeVehicleId = '77777777-7777-4777-8777-777777777777'

const packs = [
  { id: packId, name: '爱玛品牌词包', description: '新品车型及用户讨论', enabled: true, version: 4, keyword_count: 28 },
  { id: relevancePackId, name: '产品车型词包', description: '车型、型号与产品系列发现', enabled: true, version: 2, keyword_count: 16 },
]

const historicalVehicle = {
  id: historicalVehicleId,
  code: 'A01',
  display_name: '示例车型 A',
  status: 'deprecated',
  version: 3,
  catalog_version: 9,
  merged_into_id: null,
  aliases: [],
  keyword_pack_ids: [],
  referenced: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-28T00:00:00Z',
}

const activeVehicle = {
  ...historicalVehicle,
  id: activeVehicleId,
  code: 'Q7',
  display_name: '爱玛 Q7',
  status: 'active',
  version: 1,
  referenced: false,
}

const plan = {
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
  platforms: [{ platform: 'xiaohongshu', provider_config_id: providerId, search_config: {} }],
  keyword_pack_ids: [packId],
  vehicle_model_ids: [historicalVehicleId],
  created_at: '2026-08-21T00:00:00Z',
  updated_at: '2026-08-21T00:00:00Z',
}

async function mockStrategyApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (url.pathname === '/api/v1/principal') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          principal_id: 'admin-1',
          display_name: '爱玛',
          role: 'administrator',
          source: 'development',
          is_administrator: true,
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/notifications') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [], unread_count: 0 }) })
      return
    }
    if (url.pathname === '/api/v1/keyword-packs' && request.method() === 'GET') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: packs, total: 2, offset: 0, limit: Number(url.searchParams.get('limit') ?? '20') }),
      })
      return
    }
    if (url.pathname === `/api/v1/keyword-packs/${packId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...packs[0],
          keywords: [
            { id: 'kw-1', text: '爱玛 Q7', platform_scope: 'all', enabled: true, priority: 100, note: '' },
            { id: 'kw-2', text: '爱玛电动车', platform_scope: 'all', enabled: true, priority: 100, note: '' },
            { id: 'kw-3', text: '爱玛门店', platform_scope: 'all', enabled: true, priority: 100, note: '' },
          ],
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/vehicle-models' && request.method() === 'GET') {
      const items = url.searchParams.get('status') === 'active' ? [activeVehicle] : [historicalVehicle]
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items, total: items.length, catalog_version: 9, offset: 0, limit: 200 }),
      })
      return
    }
    if (url.pathname === '/api/v1/relevance-config' && request.method() === 'GET') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          keyword_pack_id: packId,
          keyword_pack_version: 4,
          version: 3,
          effective_keywords: ['爱玛 Q7', '爱玛电动车', '爱玛门店'],
          updated_at: '2026-08-27T15:20:00Z',
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/collection-capabilities') {
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
    if (url.pathname === '/api/v1/collection-plans' && request.method() === 'GET') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [plan], total: 24, enabled_count: 18, offset: 0, limit: 20 }),
      })
      return
    }

    await route.fulfill({ status: 404, body: 'not mocked' })
  })
}

async function expectBox(
  locator: Locator,
  expected: { x?: number; y?: number; width?: number; height?: number },
): Promise<void> {
  await expect(locator).toBeVisible()
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  for (const [key, value] of Object.entries(expected)) {
    const actual = box?.[key as keyof typeof expected]
    expect(Math.abs(Number(actual) - Number(value)), `${key}: ${actual} ≈ ${value}`).toBeLessThanOrEqual(1)
  }
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockStrategyApi(page)
})

test('matches the formal 1440×900 Figma geometry for the strategy workspace', async ({ page }) => {
  await page.goto('/collection-strategy')

  await expectBox(page.locator('.aima-page-header'), { x: 204, y: 88, width: 1212, height: 64 })
  await expectBox(page.locator('.strategy-summary'), { x: 204, y: 172, width: 1212, height: 88 })
  await expectBox(page.locator('.tabs'), { x: 204, y: 280, width: 1212, height: 46 })
  await expectBox(page.locator('.filters'), { x: 204, y: 346, width: 1212, height: 72 })
  await expectBox(page.locator('.plan-card > .aima-feedback'), { x: 204, y: 438, width: 1212, height: 44 })
  await expectBox(page.locator('.table-wrap'), { x: 204, y: 544, width: 1212, height: 227 })

  await page.getByRole('button', { name: '关键词包' }).click()
  await expectBox(page.locator('.panel-grid'), { x: 204, y: 346, width: 1212 })
  await expectBox(page.locator('.table-card'), { x: 204, y: 346, width: 823 })
  await expectBox(page.locator('.detail-card'), { x: 1043, y: 346, width: 373 })
  await expectBox(page.locator('.table-head'), { height: 54 })
  await expectBox(page.locator('.pack-row').first(), { height: 74 })
  await expectBox(page.locator('.detail-card form'), { width: 287 })
  await expectBox(page.locator('.detail-card form input'), { width: 217, height: 40 })
  await expectBox(page.locator('.detail-card form button'), { width: 58, height: 40 })
})

test('matches the formal keyword modal and collection plan drawer geometry', async ({ page }) => {
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包' }).click()
  await page.locator('.table-head').getByRole('button', { name: /新建词包/ }).click()

  const packDialog = page.getByRole('dialog', { name: '新建关键词包' })
  await expectBox(packDialog, { x: 405, y: 187, width: 630, height: 526 })
  await expectBox(packDialog.locator('textarea'), { height: 120 })
  await expectBox(packDialog.locator('footer'), { height: 76 })
  await packDialog.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: /新建采集计划/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建采集计划' })
  await expectBox(drawer, { x: 930, y: 0, width: 510, height: 900 })
  await expectBox(drawer.locator('header'), { height: 84 })
  await expectBox(drawer.locator('.body'), { y: 84, height: 742 })
  await expectBox(drawer.locator('footer'), { y: 826, height: 74 })
  await expectBox(drawer.locator('.platform').first(), { height: 68 })

  const vehicleSelect = drawer.locator('.vehicle-select')
  await expect(vehicleSelect).toHaveCSS('border-top-width', '0px')
  await expect(vehicleSelect.locator('.vehicle-select__options label').first()).toHaveCSS('border-top-width', '0px')
  await expectBox(vehicleSelect.locator('.vehicle-select__options label').first(), { height: 32 })
})
