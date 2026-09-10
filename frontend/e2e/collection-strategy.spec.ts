import { expect, test } from './fixture'

const packId = '11111111-1111-4111-8111-111111111111'
const secondaryPackId = '22222222-2222-4222-8222-222222222222'
const planId = '33333333-3333-4333-8333-333333333333'
const providerId = '44444444-4444-4444-8444-444444444444'
const activeBrandId = '88888888-8888-4888-8888-888888888888'

const packs = [
  { id: packId, name: '爱玛新品发现', description: 'Discovery', enabled: true, version: 4, keyword_count: 2 },
  { id: secondaryPackId, name: '门店活动发现', description: 'Discovery', enabled: true, version: 8, keyword_count: 3 },
]
const activeBrand = {
  id: activeBrandId,
  code: 'AIMA',
  display_name: '爱玛',
  role: 'owned',
  status: 'active',
  version: 1,
  catalog_version: 18,
  aliases: [],
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-28T00:00:00Z',
}
const plan = {
  id: planId,
  name: '爱玛口碑周期采集',
  enabled: true,
  schedule_expr: '0 9 * * *',
  timezone: 'Asia/Shanghai',
  schedule_version: 1,
  next_run_at: null,
  last_scheduled_at: null,
  detail_policy: 'on_change',
  comment_policy: 'adaptive',
  platforms: [{ platform: 'xiaohongshu', provider_config_id: providerId, search_config: {} }],
  keyword_pack_ids: [packId],
  brand_ids: [activeBrandId],
  created_at: '2026-08-21T00:00:00Z',
  updated_at: '2026-08-21T00:00:00Z',
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/keyword-packs' && request.method() === 'GET') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: packs, total: 2, offset: 0, limit: 100 }) })
      return
    }
    if (url.pathname === `/api/v1/keyword-packs/${packId}`) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...packs[0], keywords: [{ id: '55555555-5555-4555-8555-555555555555', text: '爱玛 Q7', platform_scope: 'all', enabled: true, priority: 10, note: '' }] }) })
      return
    }
    if (url.pathname === '/api/v1/vehicle-brands' && request.method() === 'GET') {
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const items = offset === 0
        ? Array.from({ length: 200 }, (_, index) => ({
          ...activeBrand,
          id: `brand-${index}`,
          code: `BRAND-${index}`,
          display_name: `候选品牌 ${index}`,
        }))
        : offset === 200 ? [activeBrand] : []
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items, total: 201, catalog_version: 18, offset, limit: 200 }),
      })
      return
    }
    if (url.pathname === '/api/v1/collection-capabilities') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ provider_configs: [{ id: providerId, provider: 'tikhub', display_name: 'TikHub 主配置' }], capabilities: [{ provider: 'tikhub', platform: 'xiaohongshu', operations: ['keyword_search'], search: { supported_sort_modes: ['general', 'latest'], supported_time_filters: ['all', '1d', '7d', '180d'], supported_duration_filters: [], supported_content_types: ['all', 'video', 'image'], manual_default: { sort_mode: 'latest', published_within: '1d', content_type: 'all' } } }] }) })
      return
    }
    if (url.pathname === '/api/v1/collection-plans' && request.method() === 'GET') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [plan], total: 1, enabled_count: 1, offset: 0, limit: 20 }) })
      return
    }
    if (url.pathname === '/api/v1/collection-plans' && request.method() === 'POST') {
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(plan) })
      return
    }
    await route.fulfill({ status: 404, body: 'not mocked' })
  })
})

test('matches the approved Figma workspace and resolves the current Brand filter from the API catalog', async ({ page }) => {
  await page.goto('/collection-strategy')

  await expect(page.getByRole('heading', { name: '采集策略' })).toBeVisible()
  await expect(page.getByRole('link', { name: /采集策略/ })).toHaveClass(/router-link-active/)
  await expect(page.getByLabel('采集策略摘要').getByText('关键词包')).toBeVisible()
  await expect(page.locator('.aima-page-actions').getByRole('button', { name: /刷新数据/ })).toBeVisible()
  await expect(page.locator('.aima-page-actions').getByRole('button', { name: /新建采集计划/ })).toBeVisible()
  await expect(page.locator('.aima-page-actions').getByRole('button', { name: /新建词包/ })).toHaveCount(0)

  await expect(page.getByText('爱玛口碑周期采集')).toBeVisible()
  const headers = page.locator('.plan-table thead th')
  await expect(headers).toHaveCount(6)
  await expect(headers.nth(0)).toHaveText('计划')
  await expect(headers.nth(1)).toHaveText('状态')
  await expect(headers.nth(2)).toHaveText('搜索条件 / 品牌过滤')
  await expect(headers.nth(3)).toHaveText('目标平台 / 采集渠道')
  await expect(headers.nth(4)).toHaveText('调度与下次运行')
  await expect(headers.nth(5)).toHaveText('操作')

  const planRow = page.locator('.plan-table tbody tr').filter({ hasText: '爱玛口碑周期采集' })
  await expect(planRow.getByText(planId)).toHaveCount(0)
  await expect(planRow.getByText('爱玛新品发现')).toBeVisible()
  await expect(planRow.getByText('品牌：爱玛')).toBeVisible()
  await expect(page.getByText('智能洞察')).toHaveCount(0)
  await expect(page.getByText('单次运行')).toHaveCount(0)

  await planRow.getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '采集计划详情' })
  await expect(detail.getByText('爱玛新品发现 · v4')).toBeVisible()
  await expect(detail.getByRole('heading', { name: '内容过滤条件 · 品牌' })).toBeVisible()
  await expect(detail.getByText('爱玛 · 自有')).toBeVisible()
  await expect(detail.getByText(planId)).not.toBeVisible()
  await detail.getByText('技术详情', { exact: true }).click()
  await expect(detail.getByText(planId)).toBeVisible()
  await detail.getByRole('button', { name: '关闭详情' }).click()

  await page.getByRole('button', { name: '关键词包' }).click()
  const packHeader = page.locator('.table-head')
  const packDetail = page.locator('.detail-card')
  await expect(packHeader.getByText('共 2 个')).toBeVisible()
  await expect(packHeader.getByRole('button', { name: /新建词包/ })).toBeVisible()
  await expect(page.locator('.aima-page-actions').getByRole('button', { name: /新建词包/ })).toHaveCount(0)
  await expect(packDetail.getByText('爱玛 Q7', { exact: true })).toBeVisible()
  await expect(packDetail.getByText('全部平台', { exact: true })).toHaveCount(0)
  await packHeader.getByRole('button', { name: /新建词包/ }).click()
  await expect(page.getByRole('dialog', { name: '新建关键词包' })).toBeVisible()
})

test('removes the global relevance entry and still protects Keyword Packs used by plans', async ({ page }) => {
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包' }).click()

  const planPackRow = page.locator('.pack-row').filter({ hasText: '爱玛新品发现' })
  await expect(planPackRow.getByRole('button', { name: '停用' })).toBeDisabled()
  await expect(planPackRow.getByRole('button', { name: '停用' })).toHaveAttribute('title', /采集计划/)

  await expect(page.getByRole('button', { name: '全局相关性' })).toHaveCount(0)
})

test('creates a periodic Collection Plan with paginated active Brand filtering and no new vehicle scope', async ({ page }) => {
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: /新建采集计划/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建采集计划' })
  await expect(drawer).toBeVisible()
  const secondBrandPagePromise = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return url.pathname === '/api/v1/vehicle-brands'
      && url.searchParams.get('status') === 'active'
      && url.searchParams.get('offset') === '200'
  })
  await drawer.getByText('指定品牌', { exact: true }).click()
  const secondBrandPage = await secondBrandPagePromise
  const brandUrl = new URL(secondBrandPage.url())
  expect(brandUrl.searchParams.get('limit')).toBe('200')
  expect(brandUrl.searchParams.get('status')).toBe('active')

  await drawer.getByPlaceholder('例如：爱玛新品口碑追踪').fill('爱玛新品自动采集')
  await drawer.getByText('爱玛新品发现 · v4').click()
  await drawer.getByText('爱玛', { exact: true }).click()
  await drawer.getByText('小红书').click()
  await expect(drawer.getByRole('button', { name: '保存采集计划' })).toBeDisabled()
  await drawer.getByLabel('小红书排序').selectOption('latest')
  await drawer.getByLabel('小红书发布时间').selectOption('1d')
  await drawer.getByLabel('小红书内容类型').selectOption('all')

  const requestPromise = page.waitForRequest(
    (request) => new URL(request.url()).pathname === '/api/v1/collection-plans' && request.method() === 'POST',
  )
  await drawer.getByRole('button', { name: '保存采集计划' }).click()
  const payload = (await requestPromise).postDataJSON()

  expect(payload).toEqual({
    name: '爱玛新品自动采集',
    schedule_expr: '0 */6 * * *',
    keyword_pack_ids: [packId],
    brand_ids: [activeBrandId],
    platforms: [{
      platform: 'xiaohongshu',
      provider_config_id: providerId,
      search_config: { sort_mode: 'latest', published_within: '1d', content_type: 'all' },
    }],
    enabled: true,
  })
  expect(payload).not.toHaveProperty('schedule_mode')
  expect(payload).not.toHaveProperty('relevance_keyword_pack_id')
  expect(payload).not.toHaveProperty('vehicle_model_ids')
  await expect(page.getByText('采集计划已保存，将由调度服务执行。')).toBeVisible()
})
