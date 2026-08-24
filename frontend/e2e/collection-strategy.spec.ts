import { expect, test } from '@playwright/test'

const packId = '11111111-1111-4111-8111-111111111111'
const relevancePackId = '22222222-2222-4222-8222-222222222222'
const planId = '33333333-3333-4333-8333-333333333333'
const providerId = '44444444-4444-4444-8444-444444444444'

const packs = [
  { id: packId, name: '爱玛新品发现', description: 'Discovery', enabled: true, version: 4, keyword_count: 2 },
  { id: relevancePackId, name: '爱玛核心相关词', description: 'Relevance', enabled: true, version: 8, keyword_count: 3 },
]
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
    if (url.pathname === '/api/v1/relevance-config' && request.method() === 'GET') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ keyword_pack_id: relevancePackId, keyword_pack_version: 8, version: 3, effective_keywords: ['爱玛', '爱玛电动车'], updated_at: '2026-08-21T00:00:00Z' }) })
      return
    }
    if (url.pathname === '/api/v1/relevance-config' && request.method() === 'PUT') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ keyword_pack_id: packId, keyword_pack_version: 4, version: 4, effective_keywords: ['爱玛 Q7'], updated_at: '2026-08-21T01:00:00Z' }) })
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

test('shows the approved collection strategy workspace and global relevance', async ({ page }) => {
  await page.goto('/collection-strategy')

  await expect(page.getByRole('heading', { name: '采集策略' })).toBeVisible()
  await expect(page.getByRole('link', { name: /采集策略/ })).toHaveClass(/router-link-active/)
  await expect(page.getByLabel('采集策略摘要').getByText('Discovery 词包')).toBeVisible()
  await expect(page.getByText('爱玛口碑周期采集')).toBeVisible()
  await expect(page.getByText('单次运行')).toHaveCount(0)

  await page.getByRole('button', { name: '查看详情' }).click()
  await expect(page.getByText('历史计划：沿用兼容默认（不限时间）')).toBeVisible()
  await page.getByRole('button', { name: '关闭详情' }).click()

  await page.getByRole('button', { name: '全局相关性' }).click()
  await expect(page.getByText('所有 Excel、TikHub 与未来采集来源共用一份 Relevance 准入配置。')).toBeVisible()
  await expect(page.getByText('爱玛电动车')).toBeVisible()
})

test('disables Keyword Pack stop actions when current backend facts forbid them', async ({ page }) => {
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包' }).click()

  const planPackRow = page.locator('.pack-row').filter({ hasText: '爱玛新品发现' })
  await expect(planPackRow.getByRole('button', { name: '停用' })).toBeDisabled()
  await expect(planPackRow.getByRole('button', { name: '停用' })).toHaveAttribute('title', /Collection Plan/)

  const relevancePackRow = page.locator('.pack-row').filter({ hasText: '爱玛核心相关词' })
  await expect(relevancePackRow.getByRole('button', { name: '停用' })).toBeDisabled()
  await expect(relevancePackRow.getByRole('button', { name: '停用' })).toHaveAttribute('title', /Relevance/)
})

test('creates only a periodic Collection Plan from the approved drawer', async ({ page }) => {
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: /新建采集计划/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建采集计划' })
  await expect(drawer).toBeVisible()
  await drawer.getByPlaceholder('例如：爱玛新品口碑追踪').fill('爱玛新品自动采集')
  await drawer.getByText('爱玛新品发现 · v4').click()
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
    schedule_expr: '0 9 * * *',
    keyword_pack_ids: [packId],
    platforms: [{
      platform: 'xiaohongshu',
      provider_config_id: providerId,
      search_config: { sort_mode: 'latest', published_within: '1d', content_type: 'all' },
    }],
    enabled: true,
  })
  expect(payload).not.toHaveProperty('schedule_mode')
  expect(payload).not.toHaveProperty('relevance_keyword_pack_id')
  await expect(page.getByText('周期采集计划已保存，将由 Scheduler 执行。')).toBeVisible()
})
