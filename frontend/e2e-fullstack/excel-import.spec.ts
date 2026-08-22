import { expect, test } from '@playwright/test'

const importedTitle = '爱玛 Stage8F 浏览器真实导入'

test('Excel 浏览器上传经过真实 API、Worker 和 PostgreSQL 后可在声音广场查看', async ({ page, request }) => {
  const fixturePath = process.env.AIMA_STAGE8F_EXCEL_FIXTURE
  expect(fixturePath, 'AIMA_STAGE8F_EXCEL_FIXTURE 必须指向测试 Excel fixture').toBeTruthy()

  const packResponse = await request.post('/api/v1/keyword-packs', {
    data: { name: `Stage8F Full-stack ${Date.now()}` },
  })
  expect(packResponse.status()).toBe(201)
  const pack = await packResponse.json() as { id: string }

  const keywordResponse = await request.post(`/api/v1/keyword-packs/${pack.id}/keywords`, {
    data: { text: '爱玛', priority: 10 },
  })
  expect(keywordResponse.status()).toBe(201)

  const relevanceResponse = await request.put('/api/v1/relevance-config', {
    data: { keyword_pack_id: pack.id },
  })
  expect(relevanceResponse.status()).toBe(200)

  await page.goto('/collection-runtime')
  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await page.getByRole('button', { name: /导入 Excel/ }).click()
  await expect(page.getByRole('dialog', { name: '导入 Excel' })).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles(fixturePath!)

  const createdResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/import-batches',
  )
  await page.getByRole('button', { name: '开始导入' }).click()
  const createdResponse = await createdResponsePromise
  expect(createdResponse.status()).toBe(202)
  const created = await createdResponse.json() as { batch_id: string; job_id: string }

  const detail = page.getByRole('dialog', { name: '批次详情' })
  await expect(detail).toBeVisible()
  await expect(detail.getByText('已完成', { exact: true }).first()).toBeVisible({ timeout: 60_000 })
  await expect(detail.getByText('已入库').locator('..').getByText('1', { exact: true })).toBeVisible()

  const viewContents = detail.getByRole('button', { name: '查看入库内容' })
  await expect(viewContents).toBeEnabled()
  await viewContents.click()

  await expect(page).toHaveURL((url) => {
    return url.pathname === '/voice-plaza' && url.searchParams.get('source_identifier') === created.batch_id
  })
  await expect(page.getByText(importedTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
})
