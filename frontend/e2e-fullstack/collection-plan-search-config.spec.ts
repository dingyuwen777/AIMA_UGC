import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
import { expect, test } from '@playwright/test'
import type {
  CollectionPlanResponse,
  HistoricalCampaignResponse,
  WisersOneDownloadResponse,
} from '../src/generated/api/client'
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
  await page.getByRole('button', { name: '新建采集计划', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '新建采集计划', exact: true })
  await drawer.getByRole('radio', { name: 'TikHub 采集', exact: true }).check()
  await drawer.getByLabel('执行频率', { exact: true }).selectOption('0 */6 * * *')
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

interface WisersOneWorkflowEvidence {
  plan_type: string
  name: string
  schedule_expr: string
  schedule_version: number
  brand_ids: string[]
  occurrence_count: number
  occurrence_id: string
  download_id: string
  initial_job_id: string
  campaign_id?: string
  content_id?: string
  canonical_rows?: number
  outcomes?: string[]
  submissions?: number
  downloads?: number
}

function assertWisersOneWorkflow(
  phase: 'schedule' | 'result',
  plan: CollectionPlanResponse,
  brandId: string,
): WisersOneWorkflowEvidence {
  const repo = resolve(process.cwd(), '..')
  const python = resolve(repo, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
  const env = { ...process.env }
  delete env.SSLKEYLOGFILE
  const output = execFileSync(python, [
    '-X', 'utf8', 'tests/fullstack/assert_wisersone_plan_workflow.py',
    phase, plan.id, String(plan.schedule_version), brandId, plan.name, plan.schedule_expr!,
  ], { cwd: repo, env, encoding: 'utf8' })
  return JSON.parse(output.trim().split('\n').at(-1)!) as WisersOneWorkflowEvidence
}

test('WisersOne 默认计划从浏览器经真实调度与 Worker 自动导入并打开结果', async ({ page, request }) => {
  // 正式续跑保留三次 30 秒阶段间隔，外部 Fake 不加速 Job 领取时间。
  test.setTimeout(180_000)
  const name = `WisersOne Full-stack ${Date.now()}`
  const brand = await ensureStage3FilterBrand(request)
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '新建采集计划', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新建采集计划', exact: true })
  await expect(dialog.getByRole('radio', { name: 'WisersOne 网站下载', exact: true })).toBeChecked()
  await expect(dialog.getByText('搜索条件 · 关键词包', { exact: true })).toHaveCount(0)
  await expect(dialog.getByText('目标平台', { exact: true })).toHaveCount(0)
  await expect(dialog.getByText('评论采集策略', { exact: true })).toHaveCount(0)
  await dialog.getByPlaceholder('例如：爱玛新品口碑追踪').fill(name)
  await dialog.getByLabel('执行频率', { exact: true }).selectOption('0 */3 * * *')
  await dialog.getByRole('radio', { name: '指定品牌', exact: true }).check()
  await dialog.getByRole('group', { name: '指定品牌（可多选）' })
    .getByRole('checkbox', { name: new RegExp(brand.name) }).check()
  await expect(dialog.getByRole('checkbox', { name: '创建后启用计划', exact: true })).toBeChecked()
  const createdPromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/collection-plans',
  )
  await dialog.getByRole('button', { name: '保存计划', exact: true }).click()
  const createdResponse = await createdPromise
  expect(createdResponse.status()).toBe(201)
  expect(createdResponse.request().postDataJSON()).toEqual({
    plan_type: 'wisersone', name, schedule_expr: '0 */3 * * *', enabled: true,
    brand_ids: [brand.id], keyword_pack_ids: [], platforms: [], comment_policy: null,
  })
  const plan = await createdResponse.json() as CollectionPlanResponse
  expect(plan).toMatchObject({
    plan_type: 'wisersone', name, schedule_expr: '0 */3 * * *', enabled: true,
    brand_ids: [brand.id], keyword_pack_ids: [], platforms: [],
    detail_policy: null, comment_policy: null, schedule_version: 1,
  })
  const persisted = await request.get(`/api/v1/collection-plans/${plan.id}`)
  expect(persisted.status()).toBe(200)
  expect(await persisted.json()).toEqual(plan)
  await expect(page.locator('.plan-table tbody tr').filter({ hasText: name })).toContainText('WisersOne')
  const scheduled = assertWisersOneWorkflow('schedule', plan, brand.id)
  expect(scheduled).toMatchObject({
    plan_type: 'wisersone', name, schedule_expr: plan.schedule_expr,
    schedule_version: plan.schedule_version, brand_ids: [brand.id], occurrence_count: 1,
  })

  await page.goto('/collection-runtime')
  const listedPromise = page.waitForResponse((response) =>
    response.request().method() === 'GET'
    && new URL(response.url()).pathname === '/api/v1/wisersone-downloads',
  )
  await page.getByRole('button', { name: 'WisersOne 任务', exact: true }).click()
  expect((await listedPromise).status()).toBe(200)
  const tasks = page.getByRole('dialog', { name: 'WisersOne 下载与导入任务', exact: true })
  const selector = tasks.getByRole('combobox', { name: '查看已有任务', exact: true })
  await expect(selector.getByRole('option', { name: new RegExp(name) })).toHaveAttribute('value', scheduled.download_id)
  await selector.selectOption(scheduled.download_id)
  await expect(tasks.locator('.task-state')).toContainText(scheduled.download_id)

  let completed: WisersOneDownloadResponse | undefined
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/wisersone-downloads/${scheduled.download_id}`)
    expect(response.status()).toBe(200)
    completed = await response.json() as WisersOneDownloadResponse
    return completed.status
  }, { timeout: 140_000, intervals: [500, 1000, 2000] }).toBe('succeeded')
  expect(completed).toMatchObject({
    id: scheduled.download_id, occurrence_id: scheduled.occurrence_id,
    plan_id: plan.id, plan_name: name, send_state: 'confirmed', percent: 100, error_code: null,
  })
  expect(completed!.campaign_id).toBeTruthy()
  await expect(tasks.locator('.task-state strong')).toHaveText('导入完成')
  const resultPromise = page.waitForResponse((response) =>
    response.request().method() === 'GET'
    && new URL(response.url()).pathname === `/api/v1/data-import-campaigns/${completed!.campaign_id}`,
  )
  await tasks.getByRole('button', { name: '查看导入结果', exact: true }).click()
  const resultResponse = await resultPromise
  expect(resultResponse.status()).toBe(200)
  const result = await resultResponse.json() as HistoricalCampaignResponse
  expect(result).toMatchObject({
    id: completed!.campaign_id, status: 'succeeded', ingestion_policy: 'standard_observation',
    total_rows: 2, stats: { created: 1, filtered: 1, failed: 0, invalid: 0 },
  })
  await expect(tasks).toHaveCount(0)
  const importResult = page.getByRole('dialog', { name: '导入数据', exact: true })
  await expect(importResult.locator('.campaign-status')).toHaveText('导入完成')
  await expect(importResult).toContainText('标准观测')
  await expect(importResult).toContainText('2 / 2 行已处理')
  await expect(importResult.getByText('新建 1', { exact: true })).toBeVisible()
  await expect(importResult.getByText('过滤 1', { exact: true })).toBeVisible()
  const final = assertWisersOneWorkflow('result', plan, brand.id)
  expect(final).toMatchObject({
    ...scheduled, campaign_id: completed!.campaign_id, canonical_rows: 2,
    outcomes: ['created', 'filtered'], submissions: 1, downloads: 1,
  })
  await importResult.getByRole('button', { name: '查看导入内容', exact: true }).click()
  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('source_identifier') === completed!.campaign_id,
  )
  await expect(page.getByText(`爱玛 WisersOne 全栈 ${scheduled.download_id}`, { exact: true })).toBeVisible()
  await expect(page.getByText(`fixture-unrelated-${scheduled.download_id}`, { exact: true })).toHaveCount(0)
})
