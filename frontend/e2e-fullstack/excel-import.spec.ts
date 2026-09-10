import { expect, test, type Page } from '@playwright/test'
import { ensureStage3FilterBrand } from './stage3-brand-support'

const importedTitle = '爱玛 Stage8F 浏览器真实导入'

async function uploadExcel(
  page: Page,
  fixturePath: string,
  options: { startImport?: boolean } = {},
): Promise<string> {
  await page.goto('/collection-runtime')
  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await expect(dialog).toBeVisible()
  await dialog.locator('input[type="file"]').first().setInputFiles(fixturePath)
  await expect(dialog).toContainText('创建任务时冻结品牌与旗下车型目录快照；Excel 导入不会发起 Provider 搜索。')
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
  await expect(dialog.locator('.campaign-status')).toHaveText('预检完成', { timeout: 60_000 })
  await dialog.getByRole('button', { name: '开始导入' }).click()
  return created.campaign_id
}

test('Excel 浏览器使用全部已启用品牌快照后经过真实 API、Worker 和 PostgreSQL 可在声音广场查看', async ({ page, request }) => {
  const fixturePath = process.env.AIMA_STAGE8F_EXCEL_FIXTURE
  expect(fixturePath, 'AIMA_STAGE8F_EXCEL_FIXTURE 必须指向测试 Excel fixture').toBeTruthy()
  await ensureStage3FilterBrand(request)
  const campaignId = await uploadExcel(page, fixturePath!)

  const detail = page.getByRole('dialog', { name: '导入数据' })
  await expect(detail.locator('.campaign-status')).toHaveText('导入完成', { timeout: 60_000 })
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
  await ensureStage3FilterBrand(request)
  await uploadExcel(page, fixturePath!, { startImport: false })

  const detail = page.getByRole('dialog', { name: '导入数据' })
  await expect(detail.locator('.campaign-status')).toHaveText('导入失败', { timeout: 60_000 })
  await detail.locator('details.technical-details summary').click()
  await expect(detail.getByText('historical_snapshot_invalid')).toBeVisible()
  await expect(detail.getByRole('button', { name: '开始导入' })).toHaveCount(0)
  await expect(detail.getByRole('button', { name: '查看导入内容' })).toHaveCount(0)
})
