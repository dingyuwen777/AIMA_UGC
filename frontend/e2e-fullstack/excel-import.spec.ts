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
  options: { startImport?: boolean } = {},
): Promise<string> {
  await page.goto('/collection-runtime')
  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await expect(dialog).toBeVisible()
  await dialog.locator('input[type="file"]').first().setInputFiles(fixturePath)
  for (const pack of packs) {
    await dialog.getByLabel(new RegExp(pack.name)).check()
  }
  const createdResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/data-import-campaigns/local',
  )
  await dialog.getByRole('button', { name: '创建并预检' }).click()
  const createdResponse = await createdResponsePromise
  expect(createdResponse.status()).toBe(201)
  const created = await createdResponse.json() as { campaign_id: string }
  if (options.startImport === false) return created.campaign_id
  await expect(dialog.getByText('预检完成，可开始导入')).toBeVisible({ timeout: 60_000 })
  await dialog.getByRole('button', { name: '开始导入' }).click()
  return created.campaign_id
}

test('Excel 浏览器多选词包后经过真实 API、Worker 和 PostgreSQL 可在声音广场查看', async ({ page, request }) => {
  const fixturePath = process.env.AIMA_STAGE8F_EXCEL_FIXTURE
  expect(fixturePath, 'AIMA_STAGE8F_EXCEL_FIXTURE 必须指向测试 Excel fixture').toBeTruthy()
  const brandPack = await createKeywordPack(request, 'brand', '爱玛')
  const modelPack = await createKeywordPack(request, 'model', '黑翼')
  await configureGlobalRelevance(request, brandPack.id)
  const campaignId = await uploadExcel(page, fixturePath!, [brandPack, modelPack])

  const detail = page.getByRole('dialog', { name: '导入数据' })
  await expect(detail.getByText('状态：succeeded')).toBeVisible({ timeout: 60_000 })
  await expect(detail.getByText('新建 1', { exact: true })).toBeVisible()
  const viewContents = detail.getByRole('button', { name: '查看导入内容' })
  await expect(viewContents).toBeEnabled()
  await viewContents.click()
  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('source_identifier') === campaignId,
  )
  await expect(page.getByText(importedTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
})

test('错误表头 Excel 由统一链路在预检阶段拒绝', async ({ page, request }) => {
  const fixturePath = process.env.AIMA_STAGE8F_FAILURE_EXCEL_FIXTURE
  expect(fixturePath, 'AIMA_STAGE8F_FAILURE_EXCEL_FIXTURE 必须指向失败测试 Excel fixture').toBeTruthy()
  const pack = await createKeywordPack(request, 'failure', '爱玛')
  await configureGlobalRelevance(request, pack.id)
  await uploadExcel(page, fixturePath!, [pack], { startImport: false })

  const detail = page.getByRole('dialog', { name: '导入数据' })
  await expect(detail.getByText('状态：failed')).toBeVisible({ timeout: 60_000 })
  await expect(detail.getByText('historical_snapshot_invalid')).toBeVisible()
  await expect(detail.getByRole('button', { name: '开始导入' })).toHaveCount(0)
  await expect(detail.getByRole('button', { name: '查看导入内容' })).toHaveCount(0)
})
