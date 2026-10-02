import { expect, test, type Locator } from '@playwright/test'
import { ensureStage3FilterBrand } from './stage3-brand-support'


/** 从共享日历公开控件选择单日，覆盖与生产相同的北京时间边界。 */
async function selectPublishedDay(dialog: Locator, day: string): Promise<void> {
  await dialog.getByRole('button', { name: '内容发布时间', exact: true }).click()
  const calendar = dialog.getByRole('dialog', { name: '选择内容发布时间', exact: true })
  for (let step = 0; step < 24; step++) {
    if (await calendar.locator(`[data-date="${day}"]`).count()) break
    const visibleDay = await calendar.locator('[data-date]').first().getAttribute('data-date')
    await calendar.getByRole('button', { name: visibleDay! > day ? '上个月' : '下个月' }).click()
  }
  await calendar.locator(`[data-date="${day}"]`).click()
  await calendar.getByRole('button', { name: '确定', exact: true }).click()
}

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
  expect((await campaignCreated.json()).campaign_id).toBeTruthy()
  await expect(importDialog.locator('.campaign-status')).toHaveText('预检完成', { timeout: 60_000 })
  await importDialog.getByRole('button', { name: '开始导入' }).click()
  await expect(importDialog.locator('.campaign-status')).toHaveText('导入完成', { timeout: 60_000 })

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '新建辅助补采' }).click()
  const drawer = page.getByRole('dialog', { name: '新建辅助补采' })
  await selectPublishedDay(drawer, '2026-09-17')
  for (const label of labels) {
    await drawer.getByLabel(new RegExp(label)).check()
  }
  await drawer.getByLabel('二级回复').check()
  await test.info().attach('日期补采弹窗', {
    body: await page.screenshot({ path: test.info().outputPath('date-dialog.png') }),
    contentType: 'image/png',
  })
  const runResponse = page.waitForResponse((response) =>
    response.request().method() === 'POST' &&
    new URL(response.url()).pathname === '/api/v1/collection-runs',
  )
  await drawer.getByRole('button', { name: '创建补采任务' }).click()
  const runCreated = await runResponse
  expect(runCreated.status()).toBe(202)
  expect(runCreated.request().postDataJSON()).toMatchObject({
    mode: 'content_supplement',
    supplement_targets: { kind: 'published_date_range',
    published_from: '2026-09-16T16:00:00.000Z',
    published_to: '2026-09-17T15:59:59.999Z' },
    expected_target_count: 5,
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
  expect(runCreated.request().postDataJSON()).not.toHaveProperty('data_import_campaign_id')
  for (const scope of run.scopes) {
    expect(scope.identity_status).toBe('resolved')
    expect(scope.comment_stage).toBe('finished')
    expect(scope.stats.root_comment_count).toBe(1)
  }
  expect(run.scopes.map((scope) => scope.stats.reply_count).sort()).toEqual([0, 0, 0, 0, 2])

  await page.goto('/collection-runtime')
  const runRow = page.locator('.table-row').filter({ hasText: '按发布时间范围' }).first()
  await expect(runRow).toBeVisible()
  await runRow.getByRole('button', { name: '查看详情' }).click()
  const runDetail = page.getByRole('dialog', { name: '辅助补采运行详情' })
  await expect(runDetail).toContainText(runId)
  await expect(runDetail).toContainText('2026/09/17')
  await expect(runDetail).toContainText('按发布时间补采')
  await expect(runDetail).not.toContainText('已关联导入来源')
  await expect(runDetail).toContainText('采集内容：详情、一级评论、二级回复')
  for (const label of labels) {
    await expect(runDetail.getByRole('region', { name: '平台评论覆盖' })).toContainText(label)
  }
  await expect(runDetail.getByText('目标身份：已确认')).toHaveCount(5)
  await expect(runDetail.getByText('抓取结束')).toHaveCount(5)
  await expect(runDetail.getByText('一级评论', { exact: true })).toBeVisible()
  const initialContentResponse = page.waitForResponse((response) =>
    response.request().method() === 'GET' &&
    new URL(response.url()).pathname === '/api/v1/contents',
  )
  await runDetail.getByRole('button', { name: '查看补采结果' }).click()
  const contentResponse = await initialContentResponse
  expect(contentResponse.status()).toBe(200)
  const initialContentUrl = new URL(contentResponse.url())
  expect(initialContentUrl.searchParams.get('cursor')).toBeNull()
  expect(initialContentUrl.searchParams.get('limit')).toBe('20')
  expect(initialContentUrl.searchParams.get('sort_by')).toBe('published_at')
  expect(initialContentUrl.searchParams.get('sort_direction')).toBe('desc')
  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('source_identifier') === runId,
  )
  await expect(page.getByRole('region', { name: '声音广场筛选条件' }).getByLabel('平台')).toBeEnabled()
  await expect(page.getByText('爱玛日期范围外测试', { exact: true })).toHaveCount(0)

  for (const label of labels) {
    const title = `爱玛评论补采全栈${label}`
    const contentRow = page.locator('.content-row').filter({ hasText: title })
    await expect(contentRow).toBeVisible()
    const detailResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'GET' &&
        /^\/api\/v1\/contents\/[^/]+$/.test(url.pathname)
    })
    await contentRow.getByRole('button', { name: '查看详情' }).click()
    const detailResponse = await detailResponsePromise
    expect(detailResponse.status()).toBe(200)
    expect(new URL(detailResponse.url()).searchParams.get('include_comments')).toBe('false')
    const contentDetail = page.getByRole('dialog', { name: '内容详情' })
    await expect(contentDetail.getByText('脱敏一级评论')).toBeVisible()
    if (label === '小红书') {
      await contentDetail.getByRole('button', { name: /查看 \d+ 条回复/ }).click()
      await expect(contentDetail.getByText('脱敏二级回复')).toBeVisible()
      await expect(contentDetail.getByText('脱敏第二页回复')).toBeVisible()
      await expect(contentDetail.getByText('回复 脱敏用户').first()).toBeVisible()
    }
    await contentDetail.getByRole('button', { name: '关闭' }).click()
  }
})

test('声音广场只补采勾选笔记，详情和评论在终态自动刷新且重复评论不新增', async ({ page, request }) => {
  test.setTimeout(180_000)
  await ensureStage3FilterBrand(request)
  const fixturePath = process.env.AIMA_COMMENT_SUPPLEMENT_EXCEL_FIXTURE
  expect(fixturePath).toBeTruthy()
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const importDialog = page.getByRole('dialog', { name: '导入数据' })
  await importDialog.locator('input[type="file"]').first().setInputFiles(fixturePath!)
  await importDialog.getByRole('button', { name: '创建并预检' }).click()
  await expect(importDialog.locator('.campaign-status')).toHaveText('预检完成', { timeout: 60_000 })
  await importDialog.getByRole('button', { name: '开始导入' }).click()
  await expect(importDialog.locator('.campaign-status')).toHaveText('导入完成', { timeout: 60_000 })
  await page.goto('/voice-plaza')
  const action = page.getByRole('button', { name: '评论补采', exact: true })
  await expect(action).toBeDisabled()
  const chosen: string[] = []
  for (const label of ['小红书', '抖音']) {
    const row = page.locator('.content-row').filter({ hasText: `爱玛评论补采全栈${label}` })
    await expect(row).toBeVisible()
    await row.locator('input[type="checkbox"]').check()
  }
  await action.click()
  const dialog = page.getByRole('dialog', { name: '评论补采', exact: true })
  await expect(dialog).toHaveClass(/aima-modal-container/)
  await expect(dialog.getByLabel('评论 · 固定执行', { exact: true })).toBeChecked()
  await expect(dialog.getByLabel(/二级回复/)).not.toBeChecked()
  await expect(dialog.getByLabel(/二级回复/)).toBeEnabled()
  await expect(dialog).toContainText('预计处理 2 条内容')
  const createdPromise = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/collection-runs')
  await dialog.getByRole('button', { name: '创建补采任务' }).click()
  const created = await createdPromise
  expect(created.status()).toBe(202)
  const body = created.request().postDataJSON()
  expect(body).toMatchObject({ mode: 'content_supplement', supplement_targets: { kind: 'selected' }, expected_target_count: 2, include_comments: true, include_sub_comments: false })
  chosen.push(...body.supplement_targets.content_ids)
  const { run_id: runId } = await created.json()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('评论补采任务已创建，共 2 条内容。')).toBeVisible()
  const row = page.locator('.content-row').filter({ hasText: '爱玛评论补采全栈小红书' })
  await row.getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '内容详情' })
  // 在页面停留，依赖真实终态轮询刷新，无手动刷新或重新进入页面。
  await expect(detail.getByText('脱敏一级评论')).toBeVisible({ timeout: 90_000 })
  await expect.poll(async () => {
    const value = await (await request.get(`/api/v1/collection-runs/${runId}`)).json()
    return value.status
  }, { timeout: 90_000 }).toBe('succeeded')
  const run = await (await request.get(`/api/v1/collection-runs/${runId}`)).json()
  const ingested = await (await request.get('/api/v1/contents', { params: { source_identifier: runId, limit: 20 } })).json()
  expect(ingested.items.map((item: { id: string }) => item.id).sort()).toEqual(chosen.sort())
  expect(run.scopes).toHaveLength(2)
  expect(run.stats.requested_count).toBe(4)
  expect(run.scopes.every((scope: { stats: { reply_count: number } }) => scope.stats.reply_count === 0)).toBe(true)
  const identity = ingested.items.find((item: { platform: string }) => item.platform === 'xiaohongshu').id
  const before = await (await request.get(`/api/v1/contents/${identity}/comments`)).json()
  const preview = await (await request.post('/api/v1/collection-supplements/preview', { data: { targets: body.supplement_targets } })).json()
  const repeatedResponse = await request.post('/api/v1/collection-runs', { data: { ...body, expected_target_count: preview.target_count, expected_target_fingerprint: preview.target_fingerprint } })
  expect(repeatedResponse.status()).toBe(202)
  const repeated = await repeatedResponse.json()
  await expect.poll(async () => (await (await request.get(`/api/v1/collection-runs/${repeated.run_id}`)).json()).status, { timeout: 90_000 }).toBe('succeeded')
  const after = await (await request.get(`/api/v1/contents/${identity}/comments`)).json()
  expect(after.total_count).toBe(before.total_count)
  expect(after.items.map((item: { id: string }) => item.id)).toEqual(before.items.map((item: { id: string }) => item.id))
})
