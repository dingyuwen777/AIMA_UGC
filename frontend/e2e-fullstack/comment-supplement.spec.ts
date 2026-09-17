import { expect, test } from '@playwright/test'
import { ensureStage3FilterBrand } from './stage3-brand-support'

const labels = ['小红书', '抖音', '微博', 'B站', '快手'] as const

test('五平台原生 ID 从浏览器补采到声音广场评论与回复', async ({ page, request }) => {
  test.setTimeout(180_000)
  const fixturePath = process.env.AIMA_COMMENT_SUPPLEMENT_EXCEL_FIXTURE
  expect(fixturePath, '必须提供隔离生成的五平台 Excel Fixture').toBeTruthy()
  await ensureStage3FilterBrand(request)

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const importDialog = page.getByRole('dialog', { name: '导入数据' })
  await importDialog.locator('input[type="file"]').first().setInputFiles(fixturePath!)
  const campaignResponse = page.waitForResponse((response) =>
    response.request().method() === 'POST' &&
    new URL(response.url()).pathname === '/api/v1/data-import-campaigns/local',
  )
  await importDialog.getByRole('button', { name: '创建并预检' }).click()
  const campaignCreated = await campaignResponse
  expect(campaignCreated.status()).toBe(201)
  const { campaign_id: campaignId } = await campaignCreated.json() as { campaign_id: string }
  await expect(importDialog.locator('.campaign-status')).toHaveText('预检完成', { timeout: 60_000 })
  await importDialog.getByRole('button', { name: '开始导入' }).click()
  await expect(importDialog.locator('.campaign-status')).toHaveText('导入完成', { timeout: 60_000 })

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '新建辅助补采' }).click()
  const drawer = page.getByRole('dialog', { name: '新建辅助补采' })
  await drawer.getByRole('button', { name: '基于已有批次补采' }).click()
  await drawer.getByLabel('数据导入来源').selectOption(`campaign:${campaignId}`)
  for (const label of labels) {
    await drawer.getByRole('button', { name: new RegExp(label) }).click()
  }
  await drawer.getByLabel('二级回复').check()
  const runResponse = page.waitForResponse((response) =>
    response.request().method() === 'POST' &&
    new URL(response.url()).pathname === '/api/v1/collection-runs',
  )
  await drawer.getByRole('button', { name: '创建补采任务' }).click()
  const runCreated = await runResponse
  expect(runCreated.status()).toBe(202)
  expect(runCreated.request().postDataJSON()).toMatchObject({
    mode: 'batch_supplement',
    data_import_campaign_id: campaignId,
    include_comments: true,
    include_sub_comments: true,
  })
  const { run_id: runId } = await runCreated.json() as { run_id: string }
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/collection-runs/${runId}`)
    expect(response.status()).toBe(200)
    return (await response.json() as { status: string }).status
  }, { timeout: 90_000 }).toBe('succeeded')
  const completed = await request.get(`/api/v1/collection-runs/${runId}`)
  expect(completed.status()).toBe(200)
  const run = await completed.json() as {
    scopes: { identity_status: string; comment_stage: string; stats: { root_comment_count: number; reply_count: number } }[]
  }
  expect(run.scopes).toHaveLength(5)
  for (const scope of run.scopes) {
    expect(scope.identity_status).toBe('resolved')
    expect(scope.comment_stage).toBe('finished')
    expect(scope.stats.root_comment_count).toBe(1)
  }
  expect(run.scopes.map((scope) => scope.stats.reply_count).sort()).toEqual([0, 0, 0, 0, 2])

  await page.goto('/collection-runtime')
  const runRow = page.locator('.table-row').filter({ hasText: '基于已有导入数据' }).first()
  await expect(runRow).toBeVisible()
  await runRow.getByRole('button', { name: '查看详情' }).click()
  const runDetail = page.getByRole('dialog', { name: '辅助补采运行详情' })
  await expect(runDetail).toContainText(runId)
  for (const label of labels) {
    await expect(runDetail.getByRole('region', { name: '平台评论覆盖' })).toContainText(label)
  }
  await expect(runDetail.getByText('目标身份：已确认')).toHaveCount(5)
  await expect(runDetail.getByText('抓取结束')).toHaveCount(5)
  await expect(runDetail.getByText('一级评论', { exact: true })).toBeVisible()
  await runDetail.getByRole('button', { name: '查看补采结果' }).click()
  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('source_identifier') === runId,
  )

  for (const label of labels) {
    const title = `爱玛评论补采全栈${label}`
    const contentRow = page.locator('.content-row').filter({ hasText: title })
    await expect(contentRow).toBeVisible()
    await contentRow.getByRole('button', { name: '查看详情' }).click()
    const contentDetail = page.getByRole('dialog', { name: '内容详情' })
    await expect(contentDetail.getByText('脱敏一级评论')).toBeVisible()
    if (label === '小红书') {
      await contentDetail.getByRole('button', { name: '查看 2 条回复' }).click()
      await expect(contentDetail.getByText('脱敏二级回复')).toBeVisible()
      await expect(contentDetail.getByText('脱敏第二页回复')).toBeVisible()
    }
    await contentDetail.getByRole('button', { name: '关闭' }).click()
  }
})
