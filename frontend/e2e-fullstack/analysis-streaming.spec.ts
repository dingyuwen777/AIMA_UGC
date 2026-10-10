import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { ensureStage3FilterBrand } from './stage3-brand-support'

test('从页面提交两条内容并通过真实 Worker 保存两份合法打标结果', async ({ page, request }) => {
  const ordinaryFixture = process.env.AIMA_STAGE12_ORDINARY_FIXTURE
  expect(ordinaryFixture, '需要既有 Full-stack Fixture 生成器的输出目录').toBeTruthy()
  const fixture = resolve(dirname(ordinaryFixture!), 'analysis-streaming.xlsx')
  const brand = await ensureStage3FilterBrand(request)
  const uploaded = await request.post('/api/v1/import-batches', {
    multipart: {
      file: { name: 'analysis-streaming.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: await readFile(fixture) },
      brand_ids: brand.id,
    },
  })
  expect(uploaded.status()).toBe(202)
  const batchId = (await uploaded.json()).batch_id
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/import-batches/${batchId}`)
    return (await response.json()).status
  }).toBe('succeeded')

  await page.goto('/voice-plaza')
  await page.getByRole('textbox', { name: '搜索内容' }).fill('并发验收')
  await page.getByRole('textbox', { name: '搜索内容' }).press('Enter')
  await page.getByLabel('选择 爱玛 并发验收 A', { exact: true }).check()
  await page.getByLabel('选择 爱玛 并发验收 B', { exact: true }).check()
  await page.getByRole('button', { name: 'AI 分析', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '开始 AI 分析' })
  await expect(dialog.getByText('预计分析 2 条内容', { exact: true })).toBeVisible()
  await expect(dialog.getByText('分析可能产生服务费用。确认开始后执行，运行进度可在任务中心查看。', { exact: true })).toBeVisible()
  const createdResponse = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/analysis/content-runs')
  await dialog.getByRole('button', { name: '确认开始分析' }).click()
  const response = await createdResponse
  expect(response.status()).toBe(202)
  const created = await response.json()
  expect(created.target_count).toBe(2)
  await expect.poll(async () => {
    const run = await request.get(`/api/v1/analysis/content-runs/${created.run_id}`)
    return (await run.json()).stats
  }).toEqual({ pending: 0, succeeded: 2, failed: 0, stale: 0, cancelled: 0 })
  // 完成后必须自动展示最终标签，不能用人工刷新掩盖最后一次轮询丢失。
  await expect(page.getByRole('region', { name: '声音广场内容列表' })
    .getByTitle('骑行性能 / 舒适性', { exact: true })).toHaveCount(2, { timeout: 2500 })
  const contents = await request.get('/api/v1/contents', { params: { search: '并发验收' } })
  const items = (await contents.json()).items.filter((item: { title: string }) => item.title.startsWith('爱玛 并发验收'))
  expect(items).toHaveLength(2)
  for (const item of items) {
    expect(item.analysis.status).toBe('completed')
    expect(item.analysis.relevance).toBe('relevant')
    expect(item.analysis.voice_type).toBe('真实用户发声')
    expect(item.analysis.labels).toEqual([{ primary_label: '骑行性能', secondary_label: '舒适性' }])
  }

  // 同一作者的两条帖子必须分别进入心智分子与分母；通过真实后台快照完成 UI 闭环。
  const params = { date_from: '2026-09-04', date_to: '2026-09-04', brand_ids: brand.id }
  await page.goto('/')
  await page.getByRole('button', { name: '声音流时间范围' }).click()
  const range = page.getByRole('dialog', { name: '选择声音流时间范围' })
  // 日期面板从已确认范围的结束月份打开，使用正式月份导航到 Fixture 日期。
  for (let month = 0; month < 36 && await range.getByRole('button', { name: '2026-09-04', exact: true }).count() === 0; month += 1) {
    await range.getByRole('button', { name: '上个月', exact: true }).click()
  }
  await range.getByRole('button', { name: '2026-09-04', exact: true }).click()
  await range.getByRole('button', { name: '2026-09-04', exact: true }).click()
  await range.getByRole('button', { name: '确定', exact: true }).click()
  await expect.poll(async () => {
    const response = await request.get('/api/v1/workbench/mind', { params })
    expect(response.status()).toBe(200)
    const result = await response.json()
    return { status: result.snapshot_status, count: result.relevant_content_count,
      dimension: result.dimensions.find((item: { primary_label: string }) => item.primary_label === '骑行性能')?.content_count }
  }, { timeout: 30_000 }).toEqual({ status: 'fresh', count: 2, dimension: 2 })
  const mindLabel = page.getByRole('button', { name: '骑行性能 100%', exact: true })
  await expect(mindLabel).toBeVisible({ timeout: 20_000 })
  await mindLabel.focus()
  await page.keyboard.press('Enter')
  await expect(mindLabel).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.mind-detail h3')).toHaveText('骑行性能')
  await page.getByRole('button', { name: '查看该心智的用户原声 →' }).click()
  await expect(page).toHaveURL(/primary_labels=%E9%AA%91%E8%A1%8C%E6%80%A7%E8%83%BD/)
  await expect(page.getByRole('region', { name: '声音广场内容列表' }).getByTitle('骑行性能 / 舒适性', { exact: true })).toHaveCount(2)
})
