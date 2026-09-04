import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'

test('从页面提交两条内容并通过真实 Worker 保存两份合法打标结果', async ({ page, request }) => {
  const ordinaryFixture = process.env.AIMA_STAGE12_ORDINARY_FIXTURE
  expect(ordinaryFixture, '需要既有 Full-stack Fixture 生成器的输出目录').toBeTruthy()
  const fixture = resolve(dirname(ordinaryFixture!), 'analysis-streaming.xlsx')
  const pack = await request.post('/api/v1/keyword-packs', {
    data: { name: `并发验收 ${Date.now()}`, keywords: [{ text: '爱玛', priority: 10, enabled: true }] },
  })
  expect(pack.status()).toBe(201)
  const uploaded = await request.post('/api/v1/import-batches', {
    multipart: {
      file: { name: 'analysis-streaming.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: await readFile(fixture) },
      keyword_pack_ids: (await pack.json()).id,
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
  await page.getByRole('button', { name: /AI 打标/ }).click()
  const dialog = page.getByRole('dialog', { name: '创建 AI Analysis Run' })
  await expect(dialog.getByText('预检目标 2 条，拆分 1 个 Shard')).toBeVisible()
  const createdResponse = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/analysis/content-runs')
  await dialog.getByRole('button', { name: '确认并创建 Analysis Run' }).click()
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
    .getByText('骑行性能 / 舒适性', { exact: true })).toHaveCount(2, { timeout: 2500 })
  const contents = await request.get('/api/v1/contents', { params: { search: '并发验收' } })
  const items = (await contents.json()).items.filter((item: { title: string }) => item.title.startsWith('爱玛 并发验收'))
  expect(items).toHaveLength(2)
  for (const item of items) {
    expect(item.analysis.status).toBe('completed')
    expect(item.analysis.relevance).toBe('relevant')
    expect(item.analysis.voice_type).toBe('真实用户发声')
    expect(item.analysis.labels).toEqual([{ primary_label: '骑行性能', secondary_label: '舒适性' }])
  }
})
