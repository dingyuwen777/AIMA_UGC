import { expect, test } from '@playwright/test'
import { ensureStage3FilterBrand } from './stage3-brand-support'

test('新 Plan 的逐平台 Search Config 经过真实 API 持久化到 PostgreSQL', async ({ page, request }) => {
  const suffix = `${Date.now()}`
  const packName = `Plan Search Full-stack ${suffix}`
  const packResponse = await request.post('/api/v1/keyword-packs', {
    data: { name: packName },
  })
  expect(packResponse.status()).toBe(201)
  const pack = await packResponse.json() as { id: string }
  const keywordResponse = await request.post(`/api/v1/keyword-packs/${pack.id}/keywords`, {
    data: { text: `爱玛 Plan ${suffix}`, priority: 10 },
  })
  expect(keywordResponse.status()).toBe(201)
  const brand = await ensureStage3FilterBrand(request)

  const capabilitiesResponse = await request.get('/api/v1/collection-capabilities')
  expect(capabilitiesResponse.status()).toBe(200)
  const capabilities = await capabilitiesResponse.json() as {
    provider_configs: { id: string; provider: string }[]
    capabilities: { provider: string; platform: string }[]
  }
  const xiaohongshu = capabilities.capabilities.find((item) => item.platform === 'xiaohongshu')
  expect(xiaohongshu).toBeTruthy()
  const provider = capabilities.provider_configs.find((item) => item.provider === xiaohongshu!.provider)
  expect(provider).toBeTruthy()

  await page.goto('/collection-strategy')
  await expect(page.getByRole('navigation', { name: '采集策略类型' })).not.toContainText('全局相关性')
  await page.getByRole('button', { name: /新建采集计划/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建采集计划' })
  await drawer.getByPlaceholder('例如：爱玛新品口碑追踪').fill(`Plan Search ${suffix}`)
  await drawer.getByRole('checkbox', { name: new RegExp(packName) }).check()
  await drawer.getByLabel('指定品牌', { exact: true }).check()
  await drawer.getByRole('group', { name: '指定品牌（可多选）' }).getByLabel(brand.name, { exact: true }).check()
  await drawer.getByText('小红书').click()
  await expect(drawer.getByRole('button', { name: '保存采集计划' })).toBeDisabled()
  await drawer.getByLabel('小红书排序').selectOption('latest')
  await drawer.getByLabel('小红书发布时间').selectOption('1d')
  await drawer.getByLabel('小红书内容类型').selectOption('all')

  const createdResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/collection-plans',
  )
  await drawer.getByRole('button', { name: '保存采集计划' }).click()
  const createdResponse = await createdResponsePromise
  expect(createdResponse.status()).toBe(201)
  const created = await createdResponse.json() as {
    id: string
    brand_ids: string[]
    vehicle_model_ids?: string[]
    platforms: { platform: string; provider_config_id: string; search_config: Record<string, string | null> }[]
  }
  expect(created.brand_ids).toEqual([brand.id])
  expect(created.vehicle_model_ids ?? []).toEqual([])
  expect(created.platforms).toEqual([{
    platform: 'xiaohongshu',
    provider_config_id: provider!.id,
    search_config: {
      sort_mode: 'latest', published_within: '1d', duration: null, content_type: 'all',
    },
  }])

  const persistedResponse = await request.get(`/api/v1/collection-plans/${created.id}`)
  expect(persistedResponse.status()).toBe(200)
  const persisted = await persistedResponse.json() as typeof created
  expect(persisted.platforms).toEqual(created.platforms)
})
