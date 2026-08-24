import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const importedTitle = '爱玛 Stage8F 浏览器真实导入'

interface KeywordPackFixture {
  id: string
  name: string
}

async function createKeywordPack(
  request: APIRequestContext,
  suffix: string,
  keyword: string,
): Promise<KeywordPackFixture> {
  const name = `Stage8F Full-stack ${suffix} ${Date.now()}`
  const packResponse = await request.post('/api/v1/keyword-packs', {
    data: { name },
  })
  expect(packResponse.status()).toBe(201)
  const pack = await packResponse.json() as { id: string }
  const keywordResponse = await request.post(`/api/v1/keyword-packs/${pack.id}/keywords`, {
    data: { text: keyword, priority: 10 },
  })
  expect(keywordResponse.status()).toBe(201)
  return { id: pack.id, name }
}

async function configureGlobalRelevance(
  request: APIRequestContext,
  packId: string,
): Promise<void> {
  const relevanceResponse = await request.put('/api/v1/relevance-config', {
    data: { keyword_pack_id: packId },
  })
  expect(relevanceResponse.status()).toBe(200)
}

async function uploadExcel(
  page: Page,
  fixturePath: string,
  packs: KeywordPackFixture[],
): Promise<{ batch_id: string; job_id: string }> {
  await page.goto('/collection-runtime')
  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await page.getByRole('button', { name: /导入 Excel/ }).click()
  const dialog = page.getByRole('dialog', { name: '导入 Excel' })
  await expect(dialog).toBeVisible()
  await dialog.locator('input[type="file"]').setInputFiles(fixturePath)
  for (const pack of packs) {
    await dialog.getByLabel(new RegExp(pack.name)).check()
  }
  const createdResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/import-batches',
  )
  await dialog.getByRole('button', { name: '开始导入' }).click()
  const createdResponse = await createdResponsePromise
  expect(createdResponse.status()).toBe(202)
  return createdResponse.json() as Promise<{ batch_id: string; job_id: string }>
}

test('Excel 浏览器多选词包后经过真实 API、Worker 和 PostgreSQL 可在声音广场查看', async ({ page, request }) => {
  const fixturePath = process.env.AIMA_STAGE8F_EXCEL_FIXTURE
  expect(fixturePath, 'AIMA_STAGE8F_EXCEL_FIXTURE 必须指向测试 Excel fixture').toBeTruthy()
  const brandPack = await createKeywordPack(request, 'brand', '爱玛')
  const modelPack = await createKeywordPack(request, 'model', '黑翼')
  await configureGlobalRelevance(request, brandPack.id)
  const created = await uploadExcel(page, fixturePath!, [brandPack, modelPack])

  const detail = page.getByRole('dialog', { name: '批次详情' })
  await expect(detail).toBeVisible()
  await expect(detail.getByText('已完成', { exact: true }).first()).toBeVisible({ timeout: 60_000 })
  await expect(detail.getByText('已入库').locator('..').getByText('1', { exact: true })).toBeVisible()
  const viewContents = detail.getByRole('button', { name: '查看入库内容' })
  await expect(viewContents).toBeEnabled()
  await viewContents.click()
  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('source_identifier') === created.batch_id,
  )
  await expect(page.getByText(importedTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
})

test('结构合法但业务字段非法的 Excel 由真实 Worker 进入 failed 且页面准确解释终态', async ({ page, request }) => {
  const fixturePath = process.env.AIMA_STAGE8F_FAILURE_EXCEL_FIXTURE
  expect(fixturePath, 'AIMA_STAGE8F_FAILURE_EXCEL_FIXTURE 必须指向失败测试 Excel fixture').toBeTruthy()
  const pack = await createKeywordPack(request, 'failure', '爱玛')
  await configureGlobalRelevance(request, pack.id)
  await uploadExcel(page, fixturePath!, [pack])

  const detail = page.getByRole('dialog', { name: '批次详情' })
  await expect(detail.getByText('失败', { exact: true }).first()).toBeVisible({ timeout: 60_000 })
  await expect(detail.getByRole('button', { name: '查看入库内容' })).toBeDisabled()

  await detail.getByRole('button', { name: '处理阶段' }).click()
  await expect(detail.getByText('任务已失败。', { exact: false })).toBeVisible()
  await expect(detail.getByText('失败前最后完成阶段', { exact: false })).toBeVisible()
  await expect(detail.locator('.stage-row')).toHaveCount(0)

  await detail.getByRole('button', { name: 'Job 状态' }).click()
  await expect(detail.getByText('失败', { exact: true })).toBeVisible()
  await detail.getByRole('button', { name: '错误记录' }).click()
  await expect(detail.getByText('invalid_import', { exact: true }).first()).toBeVisible()
})
