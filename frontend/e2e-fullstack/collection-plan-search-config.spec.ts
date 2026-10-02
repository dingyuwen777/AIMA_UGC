import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
import { expect, test } from '@playwright/test'
import { ensureStage3FilterBrand } from './stage3-brand-support'

for (const mode of ['adaptive', 'full'] as const) {
test(`TikHub ${mode} Plan 从浏览器经 API/PG 到 Scheduler 冻结`, async ({ page, request }) => {
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
  await page.getByRole('button', { name: /新建 TikHub 采集计划/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建 TikHub 采集计划' })
  await drawer.getByPlaceholder('例如：爱玛新品口碑追踪').fill(`Plan Search ${suffix}`)
  await drawer.getByRole('checkbox', { name: new RegExp(packName) }).check()
  await drawer.getByLabel('指定品牌', { exact: true }).check()
  await drawer.getByRole('group', { name: '指定品牌（可多选）' })
    .getByRole('checkbox', { name: new RegExp(brand.name) })
    .check()
  await drawer.getByText('小红书', { exact: true }).click()
  const serviceChoice = drawer.getByLabel('小红书采集服务')
  if (await serviceChoice.count()) await serviceChoice.selectOption(provider!.id)
  await expect(drawer.getByRole('button', { name: '保存计划' })).toBeDisabled()
  await drawer.getByLabel('小红书排序').selectOption('latest')
  await drawer.getByLabel('小红书发布时间').selectOption('1d')
  await drawer.getByLabel('小红书内容类型').selectOption('all')

  await drawer.getByRole('radio', { name: mode === 'full' ? /^全量采集/ : /^自适应采集/ }).check()

  const createdResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/collection-plans',
  )
  await drawer.getByRole('button', { name: '保存计划' }).click()
  const createdResponse = await createdResponsePromise
  expect(createdResponse.status()).toBe(201)
  const created = await createdResponse.json() as {
    id: string
    plan_type: string
    comment_policy: string
    schedule_version: number
    brand_ids: string[]
    vehicle_model_ids?: string[]
    platforms: { platform: string; provider_config_id: string; search_config: Record<string, string | null> }[]
  }
  expect(created.plan_type).toBe('tikhub')
  expect(created.comment_policy).toBe(mode)
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
  expect(persisted.comment_policy).toBe(mode)
  const repo = resolve(process.cwd(), '..')
  const python = resolve(repo, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
  const output = execFileSync(python, ['-X', 'utf8', 'tests/fullstack/assert_tikhub_plan_snapshot.py', created.id, mode, String(created.schedule_version)], { cwd: repo, encoding: 'utf8' })
  const snapshot = JSON.parse(output.trim().split('\n').at(-1)!)
  expect(snapshot).toMatchObject({ plan_type: 'tikhub', comment_policy: mode, schedule_version: created.schedule_version, decision_policy: { comment_mode: mode } })

  const nextMode = mode === 'full' ? 'adaptive' : 'full'
  const updatedResponse = await request.put(`/api/v1/collection-plans/${created.id}`, { data: {
    expected_version: created.schedule_version, plan_type: 'tikhub', comment_policy: nextMode,
    name: `Plan Edited ${suffix}`, enabled: true, schedule_expr: '0 */6 * * *',
    keyword_pack_ids: [pack.id], brand_ids: [brand.id], platforms: created.platforms,
  } })
  expect(updatedResponse.status()).toBe(200)
  const updated = await updatedResponse.json() as typeof created
  expect(updated.comment_policy).toBe(nextMode)
  expect(updated.schedule_version).toBe(created.schedule_version + 1)
  const copiedResponse = await request.post(`/api/v1/collection-plans/${created.id}/copy`, { data: { name: `Plan Copy ${suffix}` } })
  expect(copiedResponse.status()).toBe(201)
  expect(await copiedResponse.json()).toMatchObject({ plan_type: 'tikhub', comment_policy: nextMode, enabled: false })
  const nextOutput = execFileSync(python, ['-X', 'utf8', 'tests/fullstack/assert_tikhub_plan_snapshot.py', created.id, nextMode, String(updated.schedule_version), mode], { cwd: repo, encoding: 'utf8' })
  expect(JSON.parse(nextOutput.trim().split('\n').at(-1)!)).toMatchObject({ plan_type: 'tikhub', comment_policy: nextMode, decision_policy: { comment_mode: nextMode } })
})
}
