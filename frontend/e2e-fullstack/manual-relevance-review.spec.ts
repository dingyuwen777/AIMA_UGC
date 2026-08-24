import { expect, test } from '@playwright/test'

const manualReviewTitle = '爱玛 Stage8F 人工相关性复核'

test('AI irrelevant 内容可在真实声音广场人工纳入并进入默认业务列表', async ({ page }) => {
  await page.goto('/voice-plaza')
  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()

  await page.getByLabel('AI 相关性').selectOption('irrelevant')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText(manualReviewTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('AI 判定不相关', { exact: true })).toBeVisible()

  const reviewResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/content-relevance-reviews',
  )
  await page.getByRole('button', { name: '人工标记为相关' }).click()
  const reviewResponse = await reviewResponsePromise
  expect(reviewResponse.status()).toBe(200)
  expect(await reviewResponse.json()).toMatchObject({
    requested_count: 1,
    reviewed_count: 1,
    already_reviewed_count: 0,
  })
  await expect(page.getByText(/已人工标记 1 条内容为相关/)).toBeVisible()
  await expect(page.getByText(manualReviewTitle, { exact: true })).toHaveCount(0)

  await page.getByLabel('AI 相关性').selectOption('')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText(manualReviewTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('人工复核相关', { exact: true })).toBeVisible()
})
