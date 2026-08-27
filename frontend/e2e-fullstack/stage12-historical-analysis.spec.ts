import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { promisify } from 'node:util'

const execFileAsync = promisify(execFile)

interface KeywordPackFixture {
  id: string
  name: string
}

async function createKeywordPack(request: APIRequestContext): Promise<KeywordPackFixture> {
  const name = `Stage12 Full-stack ${Date.now()}`
  const created = await request.post('/api/v1/keyword-packs', { data: { name } })
  expect(created.status()).toBe(201)
  const pack = await created.json() as { id: string }
  const keyword = await request.post(`/api/v1/keyword-packs/${pack.id}/keywords`, {
    data: { text: '爱玛', priority: 10 },
  })
  expect(keyword.status()).toBe(201)
  return { id: pack.id, name }
}

async function uploadBaseline(
  request: APIRequestContext,
  fixturePath: string,
  packId: string,
): Promise<void> {
  const created = await request.post('/api/v1/import-batches', {
    multipart: {
      file: {
        name: 'stage12-current.xlsx',
        mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        buffer: await readFile(fixturePath),
      },
      keyword_pack_ids: packId,
    },
  })
  expect(created.status()).toBe(202)
  const { batch_id: batchId } = await created.json() as { batch_id: string }
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/import-batches/${batchId}`)
    return (await response.json() as { status: string }).status
  }, { timeout: 60_000 }).toBe('succeeded')
}

async function createAnalysisRun(page: Page, expectedSequence: number): Promise<void> {
  await page.getByLabel(/选择 爱玛 Stage12 当前标题/).check()
  await page.getByRole('button', { name: /AI 打标/ }).click()
  const dialog = page.getByRole('dialog', { name: '创建 AI Analysis Run' })
  await expect(dialog.getByText('预检目标 1 条，拆分 1 个 Shard')).toBeVisible()
  await dialog.getByRole('button', { name: '确认并创建 Analysis Run' }).click()
  await expect(page.getByText(`Run #${expectedSequence} · 已完成`)).toBeVisible({ timeout: 60_000 })
}

async function injectPrewriteChunkFailure(campaignId: string): Promise<void> {
  await execFileAsync(
    'uv',
    [
      'run',
      'python',
      'tests/fullstack/force_stage12_ready_chunk_failed.py',
      campaignId,
    ],
    {
      cwd: resolve(process.cwd(), '..'),
      env: { ...process.env, AIMA_FULLSTACK_SEED: '1' },
    },
  )
}

test('统一导入的服务器历史补空 Campaign 经真实 API/Worker/DB 入库，并保留两轮 Analysis Run', async ({ page, request }) => {
  const ordinaryFixture = process.env.AIMA_STAGE12_ORDINARY_FIXTURE
  expect(ordinaryFixture, 'AIMA_STAGE12_ORDINARY_FIXTURE 必须指向普通导入 Fixture').toBeTruthy()
  const pack = await createKeywordPack(request)
  await uploadBaseline(request, ordinaryFixture!, pack.id)

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const migration = page.getByRole('dialog', { name: '导入数据' })
  await migration.getByRole('button', { name: '服务器目录' }).click()
  await migration.getByLabel('选择 history.xlsx').check()
  await migration.getByLabel(new RegExp(pack.name)).check()
  const campaignResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/api/v1/data-import-campaigns/server'
      && response.request().method() === 'POST'
  })
  await migration.getByRole('button', { name: '创建并预检' }).click()
  const campaignResponse = await campaignResponsePromise
  const { campaign_id: campaignId } = await campaignResponse.json() as { campaign_id: string }
  await expect(migration.getByText('预检完成，可开始导入')).toBeVisible({ timeout: 60_000 })
  await injectPrewriteChunkFailure(campaignId)
  await migration.getByRole('button', { name: '开始导入' }).click()
  await expect(migration.getByText('状态：partial_failed')).toBeVisible({ timeout: 60_000 })
  await migration.getByRole('button', { name: '重试失败项' }).click()
  await expect(migration.getByText('状态：succeeded')).toBeVisible({ timeout: 60_000 })
  await expect(migration.getByText('冲突 1', { exact: true })).toBeVisible()
  await migration.getByRole('button', { name: '查看导入内容' }).click()

  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && Boolean(url.searchParams.get('source_identifier')),
  )
  await expect(page.getByText('爱玛 Stage12 当前标题', { exact: true })).toBeVisible()
  await expect(page.getByText('历史正文补空成功', { exact: true })).toBeVisible()
  await expect(page.getByText('爱玛 Stage12 历史新建', { exact: true })).toBeVisible()
  await expect(page.getByText('爱玛 Stage12 历史冲突标题', { exact: true })).toHaveCount(0)

  await createAnalysisRun(page, 1)
  await page.getByRole('button', { name: '刷新数据' }).click()
  const contentList = page.getByRole('region', { name: '声音广场内容列表' })
  await expect(contentList.getByText('正面', { exact: true })).toBeVisible()
  await createAnalysisRun(page, 2)
  await page.getByRole('button', { name: '刷新数据' }).click()
  await expect(contentList.getByText('负面', { exact: true })).toBeVisible()
  await expect(page.getByText('Run #1 · 已完成')).toBeVisible()
  await expect(page.getByText('Run #2 · 已完成')).toBeVisible()
})
