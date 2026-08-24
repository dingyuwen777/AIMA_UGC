import { expect, test } from '@playwright/test'

const manualIncludeTitle = '爱玛 Stage8F 人工相关性复核'
const manualExcludeTitle = '爱玛 Stage8F 人工排除与撤销'

test('AI irrelevant 内容可在真实声音广场人工纳入并进入默认业务列表', async ({ page }) => {
  await page.goto('/voice-plaza')
  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()

  await page.getByLabel('AI 相关性').selectOption('irrelevant')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText(manualIncludeTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
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
    changed_count: 1,
    unchanged_count: 0,
  })
  await expect(page.getByText(/已人工标记 1 条内容为相关/)).toBeVisible()
  await expect(page.getByText(manualIncludeTitle, { exact: true })).toHaveCount(0)

  await page.getByLabel('AI 相关性').selectOption('')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText(manualIncludeTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('人工复核相关', { exact: true })).toBeVisible()
})

test('AI relevant 内容可人工排除并撤销，恢复 AI 业务基线', async ({ page }) => {
  await page.goto('/voice-plaza')
  await page.getByLabel('AI 相关性').selectOption('relevant')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText(manualExcludeTitle, { exact: true })).toBeVisible({ timeout: 30_000 })

  const excludeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/content-relevance-reviews',
  )
  await page.getByRole('button', { name: '人工标记为不相关' }).click()
  const excludeResponse = await excludeResponsePromise
  expect(excludeResponse.status()).toBe(200)
  expect(await excludeResponse.json()).toMatchObject({
    requested_count: 1,
    changed_count: 1,
    unchanged_count: 0,
  })
  await expect(page.getByText(/已人工标记 1 条内容为不相关/)).toBeVisible()
  await expect(page.getByText(manualExcludeTitle, { exact: true })).toHaveCount(0)

  await page.getByLabel('AI 相关性').selectOption('irrelevant')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText(manualExcludeTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('人工复核不相关', { exact: true })).toBeVisible()
  await expect(page.getByText('骑行性能 · 舒适性', { exact: true })).toBeVisible()

  const undoResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/content-relevance-reviews',
  )
  await page.getByRole('button', { name: '撤销人工判断' }).click()
  const undoResponse = await undoResponsePromise
  expect(undoResponse.status()).toBe(200)
  expect(await undoResponse.json()).toMatchObject({
    requested_count: 1,
    changed_count: 1,
    unchanged_count: 0,
  })
  await expect(page.getByText(/已撤销 1 条人工相关性判断/)).toBeVisible()
  await expect(page.getByText(manualExcludeTitle, { exact: true })).toHaveCount(0)

  await page.getByLabel('AI 相关性').selectOption('relevant')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText(manualExcludeTitle, { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('中性', { exact: true })).toBeVisible()
  await expect(page.getByText('骑行性能 · 舒适性', { exact: true })).toBeVisible()
})
